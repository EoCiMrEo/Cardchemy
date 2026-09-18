"""Provider-neutral, bounded, source-grounded flashcard generation pipeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
import math
from typing import Any

from app.ai.chunking import (
    allocate_card_targets,
    chunk_document,
    estimate_tokens,
    pack_chunks_for_requests,
)
from app.ai.contracts import (
    CandidateBatch,
    DocumentChunk,
    ExtractedDocument,
    SummaryOutput,
    ValidatedCard,
)
from app.ai.grounding import (
    REJECTION_CATEGORIES, append_if_distinct, inspect_grounded_candidate,
)
from app.ai.prompts import (
    PROMPT_VERSIONS, REFILL_PROMPT_TOKEN_RESERVE, SYSTEM_BOUNDARY,
    accepted_exclusions, generation_prompt, summary_map_prompt, summary_reduce_prompt,
)
from app.ai.providers import (
    AIProvider,
    AIProviderError,
    ProviderAttemptTelemetry,
    ProviderUsage,
    get_ai_provider,
)
from app.ai.rate_limit import ProviderRateGovernor
from app.config import Settings, get_settings


@dataclass(slots=True)
class UsageTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    estimated: bool = False

    def add(self, usage: ProviderUsage) -> None:
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        self.cached_input_tokens += usage.cached_input_tokens
        self.estimated = self.estimated or usage.estimated


@dataclass(frozen=True, slots=True)
class CardRequestBatch:
    chunks: tuple[DocumentChunk, ...]
    requested_by_chunk_id: dict[str, int]
    context_chunks: tuple[DocumentChunk, ...] = ()

    @property
    def requested_count(self) -> int:
        return sum(self.requested_by_chunk_id.values())

    @property
    def evidence_chunks(self) -> tuple[DocumentChunk, ...]:
        return self.context_chunks or self.chunks


@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    summary: str
    source_chunk_ids: tuple[str, ...]


class PipelineError(RuntimeError):
    def __init__(
        self,
        code: str,
        safe_message: str,
        *,
        retryable: bool,
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
        estimated_cost_microusd: int | None = None,
        actual_input_tokens: int = 0,
        actual_output_tokens: int = 0,
        actual_cost_microusd: int | None = None,
        usage_estimated: bool = False,
        rejected_card_count: int = 0,
        estimated_request_count: int = 0,
        provider_request_count: int = 0,
        provider_retry_count: int = 0,
        provider_rate_limit_wait_milliseconds: int = 0,
        cached_input_tokens: int = 0,
        provider_request_counts_by_stage: dict[str, int] | None = None,
        quality_diagnostics: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.retryable = retryable
        self.estimated_input_tokens = estimated_input_tokens
        self.estimated_output_tokens = estimated_output_tokens
        self.estimated_cost_microusd = estimated_cost_microusd
        self.actual_input_tokens = actual_input_tokens
        self.actual_output_tokens = actual_output_tokens
        self.actual_cost_microusd = actual_cost_microusd
        self.usage_estimated = usage_estimated
        self.rejected_card_count = rejected_card_count
        self.estimated_request_count = estimated_request_count
        self.provider_request_count = provider_request_count
        self.provider_retry_count = provider_retry_count
        self.provider_rate_limit_wait_milliseconds = (
            provider_rate_limit_wait_milliseconds
        )
        self.cached_input_tokens = cached_input_tokens
        self.provider_request_counts_by_stage = (
            provider_request_counts_by_stage or {}
        )
        self.quality_diagnostics = quality_diagnostics or {}


def cost_microusd(settings: Settings, input_tokens: int, output_tokens: int) -> int | None:
    if not settings.flashcard_ai_pricing_configured:
        return None
    value = (
        Decimal(input_tokens) * settings.flashcard_ai_input_cost_per_million_usd
        + Decimal(output_tokens) * settings.flashcard_ai_output_cost_per_million_usd
    )
    return int(value.to_integral_value(rounding=ROUND_CEILING))


class FlashcardGenerationPipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        provider: AIProvider | None = None,
        provider_semaphore: asyncio.Semaphore | None = None,
        rate_governor: ProviderRateGovernor | None = None,
    ):
        self.settings = settings or get_settings()
        self.provider = provider or get_ai_provider(
            self.settings, rate_governor=rate_governor
        )
        self.provider_semaphore = provider_semaphore or asyncio.Semaphore(
            self.settings.flashcard_ai_concurrency
        )
        self.usage = UsageTotals()
        self.estimated_input_tokens = 0
        self.estimated_output_tokens = 0
        self.estimated_cost_microusd: int | None = None
        self.estimated_request_count = 0
        self.provider_request_count = 0
        self.provider_retry_count = 0
        self.provider_rate_limit_wait_milliseconds = 0
        self.provider_request_counts_by_stage: dict[str, int] = {}
        self._logical_request_count = 0
        self._logical_request_counts_by_stage: dict[str, int] = {}
        self._provider_telemetry_baseline = self._provider_telemetry_snapshot()
        self.rejected = 0
        self._quality_rounds: list[dict[str, int]] = []
        self._rejection_counts = dict.fromkeys(REJECTION_CATEGORIES, 0)
        self._pending_input_tokens = 0
        self._pending_output_tokens = 0
        self._uncertain_input_tokens = 0
        self._uncertain_output_tokens = 0
        self._uncertain_request_count = 0
        self._running = False

    def quality_diagnostics(self) -> dict[str, Any]:
        """Bounded metadata only; never include IDs, prompts or card content."""

        return {
            "prompt_versions": dict(PROMPT_VERSIONS),
            "rounds": [dict(item) for item in self._quality_rounds],
            "rejections": dict(self._rejection_counts),
            "refill_rounds_used": max(0, len(self._quality_rounds) - 1),
            "uncertain_request_count": self._uncertain_request_count,
        }

    def _reject(self, reason: str) -> None:
        # Reasons originate only in the fixed local validator/admission paths.
        if reason not in self._rejection_counts:
            raise ValueError("Unknown rejection category")
        self.rejected += 1
        self._rejection_counts[reason] += 1

    def _provider_telemetry_snapshot(self) -> ProviderAttemptTelemetry | None:
        snapshot = getattr(self.provider, "telemetry_snapshot", None)
        if not callable(snapshot):
            return None
        value = snapshot()
        return value if isinstance(value, ProviderAttemptTelemetry) else None

    @staticmethod
    def _stage_name(operation: str) -> str:
        if operation.startswith("card_generation_"):
            return "card_generation"
        return operation

    def _refresh_provider_telemetry(self) -> None:
        current = self._provider_telemetry_snapshot()
        baseline = self._provider_telemetry_baseline
        if current is None or baseline is None:
            self.provider_request_count = self._logical_request_count
            self.provider_retry_count = 0
            self.provider_rate_limit_wait_milliseconds = 0
            self.provider_request_counts_by_stage = dict(
                self._logical_request_counts_by_stage
            )
            return
        self.provider_request_count = max(
            0, current.request_count - baseline.request_count
        )
        self.provider_retry_count = max(0, current.retry_count - baseline.retry_count)
        wait_seconds = max(
            0.0,
            current.rate_limit_wait_seconds - baseline.rate_limit_wait_seconds,
        )
        self.provider_rate_limit_wait_milliseconds = int(round(wait_seconds * 1_000))
        by_stage: dict[str, int] = {}
        for operation, count in current.request_counts_by_stage.items():
            delta = count - baseline.request_counts_by_stage.get(operation, 0)
            if delta > 0:
                stage = self._stage_name(operation)
                by_stage[stage] = by_stage.get(stage, 0) + delta
        self.provider_request_counts_by_stage = by_stage

    def _error(self, code: str, message: str, *, retryable: bool) -> PipelineError:
        return PipelineError(
            code,
            message,
            retryable=retryable,
            estimated_input_tokens=self.estimated_input_tokens,
            estimated_output_tokens=self.estimated_output_tokens,
            estimated_cost_microusd=self.estimated_cost_microusd,
            actual_input_tokens=self.usage.input_tokens,
            actual_output_tokens=self.usage.output_tokens,
            actual_cost_microusd=cost_microusd(
                self.settings, self.usage.input_tokens, self.usage.output_tokens
            ),
            usage_estimated=self.usage.estimated,
            rejected_card_count=self.rejected,
            estimated_request_count=self.estimated_request_count,
            provider_request_count=self.provider_request_count,
            provider_retry_count=self.provider_retry_count,
            provider_rate_limit_wait_milliseconds=(
                self.provider_rate_limit_wait_milliseconds
            ),
            cached_input_tokens=self.usage.cached_input_tokens,
            provider_request_counts_by_stage=dict(
                self.provider_request_counts_by_stage
            ),
            quality_diagnostics=self.quality_diagnostics(),
        )

    def job_timeout_error(self) -> PipelineError:
        """Snapshot completed usage and physical attempts after job cancellation."""

        self._refresh_provider_telemetry()
        return self._error(
            "generation_job_timeout",
            "Generation reached the configured job time limit. Retry later or reduce the requested cards.",
            retryable=True,
        )

    def _prompt_tokens(self, user_prompt: str) -> int:
        return estimate_tokens(f"{SYSTEM_BOUNDARY}\n{user_prompt}")

    def _summary_map_prompt(self, chunks: tuple[DocumentChunk, ...]) -> str:
        return summary_map_prompt(chunks)

    def _summary_packs(
        self, chunks: list[DocumentChunk]
    ) -> list[tuple[DocumentChunk, ...]]:
        return pack_chunks_for_requests(
            chunks,
            max_tokens=self.settings.flashcard_ai_request_input_target_tokens,
            estimate_prompt_tokens=lambda pack: self._prompt_tokens(
                self._summary_map_prompt(pack)
            ),
            max_chunks=500,
        )

    def _generation_prompt(
        self,
        batch: CardRequestBatch,
        global_summary: str | None,
        exclusions: list[dict[str, str]] | None = None,
    ) -> str:
        return generation_prompt(
            batch.evidence_chunks, batch.requested_by_chunk_id, global_summary, exclusions,
        )

    def _generation_batches(
        self,
        chunks: list[DocumentChunk],
        allocations: dict[str, int],
        global_summary: str | None,
        context_chunks: tuple[DocumentChunk, ...] = (),
        exclusions: list[dict[str, str]] | None = None,
        reserved_exclusion_tokens: int = 0,
    ) -> list[CardRequestBatch]:
        batches: list[CardRequestBatch] = []
        current_chunks: list[DocumentChunk] = []
        current_allocations: dict[str, int] = {}

        def flush() -> None:
            nonlocal current_chunks, current_allocations
            if current_allocations:
                batches.append(
                    CardRequestBatch(
                        chunks=tuple(current_chunks),
                        requested_by_chunk_id=dict(current_allocations),
                        context_chunks=context_chunks,
                    )
                )
            current_chunks = []
            current_allocations = {}

        for chunk in chunks:
            remaining = allocations.get(chunk.chunk_id, 0)
            while remaining > 0:
                capacity = self.settings.flashcard_ai_cards_per_request - sum(
                    current_allocations.values()
                )
                if capacity <= 0:
                    flush()
                    continue
                take = min(remaining, capacity)
                candidate_chunks = (
                    current_chunks
                    if chunk.chunk_id in current_allocations
                    else [*current_chunks, chunk]
                )
                candidate_allocations = dict(current_allocations)
                candidate_allocations[chunk.chunk_id] = (
                    candidate_allocations.get(chunk.chunk_id, 0) + take
                )
                candidate = CardRequestBatch(
                    chunks=tuple(candidate_chunks),
                    requested_by_chunk_id=candidate_allocations,
                    context_chunks=context_chunks,
                )
                if not context_chunks and current_allocations and self._prompt_tokens(
                    self._generation_prompt(candidate, global_summary, exclusions)
                ) + reserved_exclusion_tokens > self.settings.flashcard_ai_request_input_target_tokens:
                    flush()
                    continue
                current_chunks = list(candidate_chunks)
                current_allocations = candidate_allocations
                remaining -= take
                if sum(current_allocations.values()) >= self.settings.flashcard_ai_cards_per_request:
                    flush()
        flush()
        return batches

    @staticmethod
    def _reduce_call_count(map_calls: int) -> int:
        reduce_calls = 0
        level_size = map_calls
        while level_size > 1:
            full_groups, remainder = divmod(level_size, 8)
            reduce_calls += full_groups + (1 if remainder > 1 else 0)
            level_size = math.ceil(level_size / 8)
        return reduce_calls

    def _preflight(
        self,
        chunks: list[DocumentChunk],
        target_count: int,
        summary_packs: list[tuple[DocumentChunk, ...]],
    ) -> None:
        uses_planning = len(summary_packs) > 1
        map_calls = len(summary_packs) if uses_planning else 0
        reduce_calls = self._reduce_call_count(map_calls)
        summary_calls = map_calls + reduce_calls
        allocation = allocate_card_targets(chunks, target_count)
        summary_placeholder = (
            "summary " * self.settings.flashcard_ai_summary_output_tokens
            if uses_planning
            else None
        )
        generation_batches = self._generation_batches(
            chunks,
            allocation,
            summary_placeholder,
            context_chunks=summary_packs[0] if not uses_planning else (),
        )
        # Reserve the entire bounded exclusion envelope for every refill batch.
        # This also includes the field/list/key overhead and any changed packing.
        refill_batches = self._generation_batches(
            chunks, allocation, summary_placeholder,
            context_chunks=summary_packs[0] if not uses_planning else (),
            reserved_exclusion_tokens=REFILL_PROMPT_TOKEN_RESERVE,
        ) if self.settings.flashcard_ai_refill_rounds else []
        self.estimated_request_count = summary_calls + len(generation_batches) + (
            len(refill_batches) * self.settings.flashcard_ai_refill_rounds
        )
        map_input_tokens = sum(
            self._prompt_tokens(self._summary_map_prompt(pack))
            for pack in summary_packs
        ) if uses_planning else 0
        reduce_input_tokens = reduce_calls * self._prompt_tokens(
            summary_reduce_prompt([summary_placeholder or ""] * 8)
        )
        generation_input_per_round = sum(
            self._prompt_tokens(self._generation_prompt(batch, summary_placeholder))
            for batch in generation_batches
        )
        refill_input_per_round = sum(
            self._prompt_tokens(self._generation_prompt(batch, summary_placeholder)) + REFILL_PROMPT_TOKEN_RESERVE
            for batch in refill_batches
        )
        self.estimated_input_tokens = map_input_tokens + reduce_input_tokens + generation_input_per_round + (
            refill_input_per_round * self.settings.flashcard_ai_refill_rounds
        )
        generation_output_per_round = sum(
            min(
                self.settings.flashcard_ai_max_output_tokens,
                batch.requested_count * 512 + 256,
            )
            for batch in generation_batches
        )
        self.estimated_output_tokens = (
            summary_calls * self.settings.flashcard_ai_summary_output_tokens
            + generation_output_per_round
            + sum(min(self.settings.flashcard_ai_max_output_tokens, batch.requested_count * 512 + 256)
                  for batch in refill_batches) * self.settings.flashcard_ai_refill_rounds
        )
        self.estimated_cost_microusd = cost_microusd(
            self.settings, self.estimated_input_tokens, self.estimated_output_tokens
        )
        if self.estimated_input_tokens > self.settings.flashcard_ai_max_job_input_tokens:
            raise self._error(
                "ai_input_token_limit",
                "The document would exceed the configured AI input-token budget.",
                retryable=False,
            )
        if self.estimated_output_tokens > self.settings.flashcard_ai_max_job_output_tokens:
            raise self._error(
                "ai_output_token_limit",
                "The requested cards would exceed the configured AI output-token budget.",
                retryable=False,
            )
        maximum_cost = int(
            (self.settings.flashcard_ai_max_estimated_cost_usd * Decimal(1_000_000)).to_integral_value()
        )
        if self.estimated_cost_microusd is not None and self.estimated_cost_microusd > maximum_cost:
            raise self._error(
                "ai_estimated_cost_limit",
                "The job would exceed the configured estimated AI cost budget.",
                retryable=False,
            )

    async def _call(self, **kwargs: Any):
        prompt_tokens = estimate_tokens(
            f"{kwargs['system_prompt']}\n{kwargs['user_prompt']}"
        )
        if prompt_tokens + int(kwargs["max_output_tokens"]) > self.settings.flashcard_ai_context_window_tokens:
            raise self._error(
                "ai_context_window_limit",
                "One AI request would exceed the configured context window.",
                retryable=False,
            )
        output_tokens = int(kwargs["max_output_tokens"])
        try:
            async with self.provider_semaphore:
                # Reconcile completed usage with outstanding request envelopes.
                # Reservation is synchronous, so concurrent tasks cannot both
                # admit against the same remaining per-job token/cost capacity.
                planned_input = self.usage.input_tokens + self._pending_input_tokens + self._uncertain_input_tokens + prompt_tokens
                planned_output = self.usage.output_tokens + self._pending_output_tokens + self._uncertain_output_tokens + output_tokens
                if planned_input > self.settings.flashcard_ai_max_job_input_tokens:
                    raise self._error("ai_input_token_limit", "One request would exceed the remaining AI input-token budget.", retryable=False)
                if planned_output > self.settings.flashcard_ai_max_job_output_tokens:
                    raise self._error("ai_output_token_limit", "One request would exceed the remaining AI output-token budget.", retryable=False)
                planned_cost = cost_microusd(self.settings, planned_input, planned_output)
                if planned_cost is not None and planned_cost > self.settings.flashcard_ai_max_estimated_cost_usd * Decimal(1_000_000):
                    raise self._error("ai_cost_limit", "One request would exceed the remaining AI cost budget.", retryable=False)
                self._pending_input_tokens += prompt_tokens
                self._pending_output_tokens += output_tokens
                operation = self._stage_name(str(kwargs["operation"]))
                self._logical_request_count += 1
                self._logical_request_counts_by_stage[operation] = (
                    self._logical_request_counts_by_stage.get(operation, 0) + 1
                )
                try:
                    response = await self.provider.generate_structured(**kwargs)
                except BaseException:
                    # No successful usage receipt: release outstanding capacity
                    # into a conservative uncertain envelope. It remains charged
                    # until the run ends, rather than pretending cancellation or
                    # a provider error consumed no remote capacity. This is not
                    # a billing ledger; physical retries may have unknown usage.
                    self._pending_input_tokens -= prompt_tokens
                    self._pending_output_tokens -= output_tokens
                    self._uncertain_input_tokens += prompt_tokens
                    self._uncertain_output_tokens += output_tokens
                    self._uncertain_request_count += 1
                    raise
                self._pending_input_tokens -= prompt_tokens
                self._pending_output_tokens -= output_tokens
                self.usage.add(response.usage)
        except AIProviderError as exc:
            self._refresh_provider_telemetry()
            raise self._error(exc.code, exc.safe_message, retryable=exc.retryable) from exc
        self._refresh_provider_telemetry()
        if self.usage.input_tokens > self.settings.flashcard_ai_max_job_input_tokens:
            raise self._error(
                "ai_input_token_limit",
                "The job reached the configured AI input-token budget.",
                retryable=False,
            )
        if self.usage.output_tokens > self.settings.flashcard_ai_max_job_output_tokens:
            raise self._error(
                "ai_output_token_limit",
                "The job reached the configured AI output-token budget.",
                retryable=False,
            )
        current_cost = cost_microusd(
            self.settings, self.usage.input_tokens, self.usage.output_tokens
        )
        maximum_cost = int(
            (self.settings.flashcard_ai_max_estimated_cost_usd * Decimal(1_000_000)).to_integral_value()
        )
        if current_cost is not None and current_cost > maximum_cost:
            raise self._error(
                "ai_cost_limit",
                "The job reached the configured AI cost budget.",
                retryable=False,
            )
        return response.data

    @staticmethod
    async def _gather_fail_fast(*coroutines: Any) -> list[Any]:
        """Preserve ordering while cancelling siblings after the first error."""

        if not coroutines:
            return []
        tasks = [asyncio.create_task(coroutine) for coroutine in coroutines]
        try:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_EXCEPTION
            )
            failure = next(
                (
                    task.exception()
                    for task in done
                    if not task.cancelled() and task.exception() is not None
                ),
                None,
            )
            if failure is not None:
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                raise failure
            if pending:
                await asyncio.gather(*pending)
            return [task.result() for task in tasks]
        finally:
            unfinished = [task for task in tasks if not task.done()]
            for task in unfinished:
                task.cancel()
            if unfinished:
                await asyncio.gather(*unfinished, return_exceptions=True)

    async def _summarize_pack(
        self, chunks: tuple[DocumentChunk, ...]
    ) -> EvidenceSummary:
        user_prompt = self._summary_map_prompt(chunks)
        result: SummaryOutput = await self._call(
            response_model=SummaryOutput,
            system_prompt=SYSTEM_BOUNDARY,
            user_prompt=user_prompt,
            max_output_tokens=self.settings.flashcard_ai_summary_output_tokens,
            operation="summary_map",
        )
        # Coverage is server-owned. Asking the model to repeat hundreds of IDs
        # wastes output tokens and cannot prove that it retained every fact.
        return EvidenceSummary(
            summary=result.summary,
            source_chunk_ids=tuple(chunk.chunk_id for chunk in chunks),
        )

    async def _reduce_summaries(
        self, summaries: list[EvidenceSummary]
    ) -> EvidenceSummary:
        current = summaries
        while len(current) > 1:
            next_level: list[EvidenceSummary] = []
            for start in range(0, len(current), 8):
                group = current[start : start + 8]
                if len(group) == 1:
                    next_level.append(group[0])
                    continue
                allowed = [source for item in group for source in item.source_chunk_ids]
                user_prompt = summary_reduce_prompt([item.summary for item in group])
                reduced: SummaryOutput = await self._call(
                    response_model=SummaryOutput,
                    system_prompt=SYSTEM_BOUNDARY,
                    user_prompt=user_prompt,
                    max_output_tokens=self.settings.flashcard_ai_summary_output_tokens,
                    operation="summary_reduce",
                )
                next_level.append(
                    EvidenceSummary(
                        summary=reduced.summary,
                        source_chunk_ids=tuple(allowed),
                    )
                )
            current = next_level
        return current[0]

    async def _generate(
        self,
        batch: CardRequestBatch,
        summary: str | None,
        round_index: int,
        exclusions: list[dict[str, str]] | None = None,
    ):
        if batch.requested_count <= 0:
            return []
        user_prompt = self._generation_prompt(batch, summary, exclusions)
        result: CandidateBatch = await self._call(
            response_model=CandidateBatch,
            system_prompt=SYSTEM_BOUNDARY,
            user_prompt=user_prompt,
            max_output_tokens=min(
                self.settings.flashcard_ai_max_output_tokens,
                batch.requested_count * 512 + 256,
            ),
            operation=f"card_generation_{round_index}",
        )
        return result.cards

    async def run(self, document: ExtractedDocument, target_count: int) -> dict[str, Any]:
        # A reused facade must not reset accounting while its previous requests
        # are still active. Fail-fast/cancellation drains every spawned sibling.
        if self._running:
            raise RuntimeError("The pipeline already has an active run")
        self._running = True
        try:
            return await self._run(document, target_count)
        finally:
            self._running = False

    async def _run(self, document: ExtractedDocument, target_count: int) -> dict[str, Any]:
        # A graph facade can be invoked more than once in tests or integrations;
        # telemetry is per run and must never leak across invocations.
        self.usage = UsageTotals()
        self.estimated_input_tokens = 0
        self.estimated_output_tokens = 0
        self.estimated_cost_microusd = None
        self.estimated_request_count = 0
        self.provider_request_count = 0
        self.provider_retry_count = 0
        self.provider_rate_limit_wait_milliseconds = 0
        self.provider_request_counts_by_stage = {}
        self._logical_request_count = 0
        self._logical_request_counts_by_stage = {}
        self._provider_telemetry_baseline = self._provider_telemetry_snapshot()
        self.rejected = 0
        self._quality_rounds = []
        self._rejection_counts = dict.fromkeys(REJECTION_CATEGORIES, 0)
        self._pending_input_tokens = 0
        self._pending_output_tokens = 0
        self._uncertain_input_tokens = 0
        self._uncertain_output_tokens = 0
        self._uncertain_request_count = 0
        chunks = chunk_document(
            document,
            max_tokens=self.settings.flashcard_ai_chunk_input_tokens,
            overlap_tokens=self.settings.flashcard_ai_chunk_overlap_tokens,
        )
        if not chunks:
            raise self._error(
                "document_has_no_text", "The document contains no usable text.", retryable=False
            )
        summary_packs = self._summary_packs(chunks)
        self._preflight(chunks, target_count, summary_packs)
        global_summary: str | None = None
        if len(summary_packs) > 1:
            async def bounded_summary(pack: tuple[DocumentChunk, ...]):
                return await self._summarize_pack(pack)

            # Probe one pack before fan-out. Provider-wide configuration
            # failures then cost one bounded retry sequence instead of one per
            # evidence pack.
            summaries = [await bounded_summary(summary_packs[0])]
            summaries.extend(
                await self._gather_fail_fast(
                    *(bounded_summary(pack) for pack in summary_packs[1:])
                )
            )
            global_summary = (await self._reduce_summaries(list(summaries))).summary
        accepted: list[ValidatedCard] = []

        for round_index in range(self.settings.flashcard_ai_refill_rounds + 1):
            missing = target_count - len(accepted)
            if missing <= 0:
                break
            allocations = allocate_card_targets(chunks, missing)
            exclusions = accepted_exclusions(accepted) if round_index > 0 else None
            round_counts = {
                "round": round_index, "raw_count": 0, "grounded_count": 0,
                "distinct_count": 0, "accepted_count": len(accepted), "missing_count": missing,
            }
            self._quality_rounds.append(round_counts)

            request_batches = self._generation_batches(
                chunks,
                allocations,
                global_summary,
                context_chunks=summary_packs[0] if len(summary_packs) == 1 else (),
                exclusions=exclusions,
            )

            async def bounded_generation(batch: CardRequestBatch):
                candidates = await self._generate(
                    batch, global_summary, round_index, exclusions
                )
                round_counts["raw_count"] += len(candidates)
                return batch, candidates

            batches = []
            if request_batches:
                # Card generation has a different schema from summaries, so it
                # receives its own single-call compatibility probe.
                batches.append(await bounded_generation(request_batches[0]))
                batches.extend(
                    await self._gather_fail_fast(
                        *(
                            bounded_generation(batch)
                            for batch in request_batches[1:]
                        )
                    )
                )
            for request_batch, candidates in batches:
                accepted_by_chunk_id: dict[str, int] = {}
                batch_chunks_by_id = {
                    chunk.chunk_id: chunk for chunk in request_batch.chunks
                }
                for candidate in candidates:
                    allowed_count = request_batch.requested_by_chunk_id.get(
                        candidate.source_chunk_id
                    )
                    if allowed_count is None:
                        self._reject("unknown_source")
                        continue
                    if (
                        accepted_by_chunk_id.get(candidate.source_chunk_id, 0)
                        >= allowed_count
                    ):
                        self._reject("chunk_quota")
                        continue
                    validated, reason = inspect_grounded_candidate(
                        candidate, batch_chunks_by_id
                    )
                    if validated is None:
                        self._reject(reason or "unknown_source")
                        continue
                    round_counts["grounded_count"] += 1
                    if not append_if_distinct(
                        accepted,
                        validated,
                        threshold=self.settings.flashcard_ai_duplicate_similarity_threshold,
                    ):
                        self._reject("near_duplicate")
                        continue
                    accepted_by_chunk_id[candidate.source_chunk_id] = (
                        accepted_by_chunk_id.get(candidate.source_chunk_id, 0) + 1
                    )
                    round_counts["distinct_count"] += 1
                    round_counts["accepted_count"] = len(accepted)
                    round_counts["missing_count"] = target_count - len(accepted)
                    if len(accepted) >= target_count:
                        break

        if len(accepted) != target_count:
            raise self._error(
                "insufficient_grounded_cards",
                "The provider could not produce enough distinct, source-grounded cards.",
                retryable=True,
            )
        actual_cost = cost_microusd(
            self.settings, self.usage.input_tokens, self.usage.output_tokens
        )
        return {
            "final_cards": [card.model_dump(mode="json") for card in accepted],
            "rejected_card_count": self.rejected,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "estimated_cost_microusd": self.estimated_cost_microusd,
            "actual_input_tokens": self.usage.input_tokens,
            "actual_output_tokens": self.usage.output_tokens,
            "actual_cost_microusd": actual_cost,
            "usage_estimated": self.usage.estimated,
            "estimated_request_count": self.estimated_request_count,
            "provider_request_count": self.provider_request_count,
            "provider_retry_count": self.provider_retry_count,
            "provider_rate_limit_wait_milliseconds": (
                self.provider_rate_limit_wait_milliseconds
            ),
            "cached_input_tokens": self.usage.cached_input_tokens,
            "provider_request_counts_by_stage": dict(
                self.provider_request_counts_by_stage
            ),
            "quality_diagnostics": self.quality_diagnostics(),
        }
