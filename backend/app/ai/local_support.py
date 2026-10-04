"""Local, fail-closed NLI inference for independent Ask AI support checks.

The artifact is supplied by the self-hosted operator and loaded only from a
local directory.  This module never downloads a model or sends course text to
another service.  The policy using these scores remains a separate, versioned
decision and must be measured on Cardchemy's own corpus before Ask is enabled.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from pathlib import Path
import re
from typing import Literal, Protocol, Sequence

from app.ai.answering import ValidatedAnswerClaim, normalize_text
from app.services.knowledge_retrieval import RetrievedKnowledgeChunk


LOCAL_SUPPORT_POLICY_VERSION = "local_nli_qa_v1"
NLI_MODEL_ID = "cross-encoder/nli-deberta-v3-xsmall"
NLI_MODEL_REVISION = "a150876415327c80daeff35ca6f68f5ed8cf5c24"
NLI_MODEL_SHA256 = "21b14751a95520953bfcc607ceeb617de7cbeaeb6d60f4c8966716c743985337"  # gitleaks:allow - public artifact digest
NLI_TOKENIZER_SHA256 = "5124ef2ead1a10a717703bc436de7f353da76d6340e4587719b42b1693707964"  # gitleaks:allow - public artifact digest
QA_MODEL_ID = "onnx-community/tinyroberta-squad2-ONNX"
QA_MODEL_REVISION = "7c9f69b7e6228375169a4553bcfa6639152e3a69"
QA_MODEL_SHA256 = "4db70e7a019e32bf652fb9d30a5c24d18b6949fae2f1dd00d9fe6d43052b77cd"  # gitleaks:allow - public artifact digest
QA_TOKENIZER_SHA256 = "7b62d797c95d1563d3467f48daad0eca3e150f2d587e7e687b557c9ef1b25473"  # gitleaks:allow - public artifact digest


class LocalSupportUnavailable(RuntimeError):
    """The local verifier is absent, corrupt, unsupported or failed closed."""


@dataclass(frozen=True, slots=True)
class NliScores:
    contradiction: float
    entailment: float
    neutral: float

    def __post_init__(self) -> None:
        values = (self.contradiction, self.entailment, self.neutral)
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in values):
            raise LocalSupportUnavailable("Invalid local support scores")
        if not 0.99 <= sum(values) <= 1.01:
            raise LocalSupportUnavailable("Invalid local support score total")


SupportCheckStatus = Literal["pass", "fail", "not_run"]
EquivalenceCheckStatus = Literal["pass", "fail", "not_required", "not_run"]
SupportReasonCode = Literal[
    "supported",
    "missing_evidence",
    "entailment_rejected",
    "question_relevance_rejected",
    "equivalence_rejected",
    "contradiction_detected",
]


@dataclass(frozen=True, slots=True)
class LocalSupportVerdict:
    """Content-free result for the first rejecting claim, or all passing claims.

    A ``not_run`` status means evaluation stopped at an earlier check. Scores,
    claim text, source identifiers and answer spans must never enter diagnostics.
    """

    supported: bool
    reason_code: SupportReasonCode
    entailment: SupportCheckStatus
    question_relevance: SupportCheckStatus
    equivalence: EquivalenceCheckStatus
    contradiction: SupportCheckStatus

    def __post_init__(self) -> None:
        if (
            self.reason_code not in (
                "supported", "missing_evidence", "entailment_rejected",
                "question_relevance_rejected", "equivalence_rejected",
                "contradiction_detected",
            )
            or self.entailment not in ("pass", "fail", "not_run")
            or self.question_relevance not in ("pass", "fail", "not_run")
            or self.equivalence not in ("pass", "fail", "not_required", "not_run")
            or self.contradiction not in ("pass", "fail", "not_run")
            or self.supported != (self.reason_code == "supported")
        ):
            raise LocalSupportUnavailable("Invalid local support verdict")


class NliScorer(Protocol):
    def score(self, premise: str, hypothesis: str) -> NliScores: ...


class QaScorer(Protocol):
    def answer(self, question: str, context: str) -> str | None: ...


class LocalSupportVerifier:
    """Independent local quote entailment, QA relevance and conflict gate.

    The generated answer supplies candidate claims only.  NLI and extractive QA
    run on local artifacts and fail closed on unknown, truncated or ambiguous
    evidence. Thresholds are provisional until measured on the release corpus.
    """

    def __init__(self, nli: NliScorer, qa: QaScorer) -> None:
        self._nli = nli
        self._qa = qa

    def supports(
        self,
        *,
        question: str,
        claims: Sequence[ValidatedAnswerClaim],
        chunks: Sequence[RetrievedKnowledgeChunk],
    ) -> bool:
        return self.evaluate(question=question, claims=claims, chunks=chunks).supported

    def evaluate(
        self,
        *,
        question: str,
        claims: Sequence[ValidatedAnswerClaim],
        chunks: Sequence[RetrievedKnowledgeChunk],
    ) -> LocalSupportVerdict:
        if not claims or not chunks:
            return LocalSupportVerdict(
                False, "missing_evidence", "not_run", "not_run", "not_run", "not_run"
            )
        any_equivalence_checked = False
        for claim in claims:
            # The trusted quote was checked for contiguous source membership
            # before this call. NLI checks semantic entailment, including
            # paraphrases that an exact-match validator cannot assess.
            entailment = self._nli.score(claim.source_quote, claim.statement)
            if entailment.entailment < 0.80 or entailment.entailment <= max(
                entailment.contradiction, entailment.neutral
            ):
                return LocalSupportVerdict(
                    False, "entailment_rejected", "fail", "not_run", "not_run", "not_run"
                )
            answer_span = self._qa.answer(question, claim.source_quote)
            if not answer_span or not normalize_text(answer_span):
                answer_span = self._extractive_fallback(question, claim)
            if (
                not answer_span or not normalize_text(answer_span)
                or normalize_text(answer_span) not in normalize_text(claim.source_quote)
            ):
                return LocalSupportVerdict(
                    False, "question_relevance_rejected", "pass", "fail", "not_run", "not_run"
                )
            equivalence: EquivalenceCheckStatus = "not_required"
            if normalize_text(answer_span) not in normalize_text(claim.statement):
                # A definition question can extract a phrase such as "the
                # point in an orbit nearest the Sun" while the supported
                # claim says "the nearest orbital point to the Sun". Require
                # independently extracted claim evidence and strong semantic
                # equivalence in both directions; a model assertion alone is
                # insufficient to establish question relevance.
                claim_span = self._qa.answer(question, claim.statement)
                if (
                    not claim_span or not normalize_text(claim_span)
                    or normalize_text(claim_span) not in normalize_text(claim.statement)
                ):
                    return LocalSupportVerdict(
                        False, "question_relevance_rejected", "pass", "fail", "not_run", "not_run"
                    )
                forward = self._nli.score(answer_span, claim_span)
                reverse = self._nli.score(claim_span, answer_span)
                if min(forward.entailment, reverse.entailment) < 0.90 or any(
                    score.entailment <= max(score.contradiction, score.neutral)
                    for score in (forward, reverse)
                ):
                    return LocalSupportVerdict(
                        False, "equivalence_rejected", "pass", "pass", "fail", "not_run"
                    )
                equivalence = "pass"
                any_equivalence_checked = True
            # Evaluate every other retrieved sentence independently to avoid
            # dropping a late contradiction when a chunk exceeds model input.
            for sentence in self._contradiction_candidates(claim, chunks):
                if normalize_text(sentence) == normalize_text(claim.source_quote):
                    continue
                conflict = self._nli.score(sentence, claim.statement)
                if conflict.contradiction >= 0.50 and conflict.contradiction > max(
                    conflict.entailment, conflict.neutral
                ):
                    return LocalSupportVerdict(
                        False, "contradiction_detected", "pass", "pass", equivalence,
                        "fail",
                    )
        return LocalSupportVerdict(
            True, "supported", "pass", "pass",
            "pass" if any_equivalence_checked else "not_required", "pass",
        )

    def _contradiction_candidates(
        self,
        claim: ValidatedAnswerClaim,
        chunks: Sequence[RetrievedKnowledgeChunk],
    ) -> tuple[str, ...]:
        # V1 remains unchanged: every retrieved sentence can veto a claim.
        return tuple(sentence for chunk in chunks for sentence in _sentences(chunk.content))

    def _extractive_fallback(
        self, question: str, claim: ValidatedAnswerClaim,
    ) -> str | None:
        # V1 and the structural V2 do not substitute another relevance gate for
        # independent extractive QA.
        return None


class LocalSupportVerifierV2(LocalSupportVerifier):
    """Candidate policy: scope *unrelated* explicit subject headings.

    A quote already has to pass independent NLI/QA checks. Only a sentence
    explicitly about a different, structurally headed subject can be removed
    from the contradiction scan. Same-topic, anaphoric and structurally unclear
    statements remain in the scan. This candidate is not the shipped policy.
    """

    def _contradiction_candidates(
        self,
        claim: ValidatedAnswerClaim,
        chunks: Sequence[RetrievedKnowledgeChunk],
    ) -> tuple[str, ...]:
        source_text = claim.source.content
        # A duplicated quote can belong to several headings. Ambiguity must
        # preserve the whole contradiction scan.
        quote_offset = source_text.find(claim.source_quote)
        source_heading = None
        if quote_offset >= 0 and source_text.find(claim.source_quote, quote_offset + 1) < 0:
            source_heading = _heading_at(source_text, claim.source.section, quote_offset)
        subject = _specific_subject(source_heading)
        if subject is None or not _contains_subject(claim.statement, subject):
            return super()._contradiction_candidates(claim, chunks)

        selected: list[str] = []
        for chunk in chunks:
            for sentence, heading in _scoped_sentences(chunk.content, chunk.section):
                if _scope_relation(subject, heading, sentence) == "independent":
                    # The sentence states its own different subject inside a
                    # separate explicit region. Lexical subject anchors are
                    # used only to avoid a false conflict; they never establish
                    # quote support, answer correctness or equivalence.
                    continue
                selected.append(sentence)
        return tuple(selected)


class LocalSupportVerifierV3(LocalSupportVerifierV2):
    """Research candidate for exact extractive acronym answers.

    A source-identical atomic sentence can answer a direct expansion question
    even when the small QA model returns no span. This narrow exception also
    scopes explicit same-topic measurement facts away from an acronym conflict
    scan. No runtime factory selects this policy; owner-reviewed positives and
    adversarial negatives are still required before any policy cutover.
    """

    def _extractive_fallback(
        self, question: str, claim: ValidatedAnswerClaim,
    ) -> str | None:
        subject = _direct_acronym_subject(question)
        if subject is None or _acronym_expansion(claim.statement, subject) is None:
            return None
        if not _exact_atomic_source_sentence(claim):
            return None
        return claim.statement

    def _contradiction_candidates(
        self,
        claim: ValidatedAnswerClaim,
        chunks: Sequence[RetrievedKnowledgeChunk],
    ) -> tuple[str, ...]:
        candidates = super()._contradiction_candidates(claim, chunks)
        subject = _acronym_statement_subject(claim.statement)
        if subject is None or not _exact_atomic_source_sentence(claim):
            return candidates
        return tuple(
            sentence for sentence in candidates
            if not _independent_measurement_fact(sentence, subject)
        )


def _normalized_atomic_sentence(text: str) -> str:
    return normalize_text(text).strip(" .!?")


def _exact_atomic_source_sentence(claim: ValidatedAnswerClaim) -> bool:
    if len(_sentences(claim.statement)) != 1 or any(
        mark in claim.statement for mark in "?!"
    ):
        return False
    target = _normalized_atomic_sentence(claim.statement)
    if not target:
        return False
    # The whole statement must be one atomic source sentence. A substring
    # inside "It is false that ..." or a sentence with a trailing caveat
    # is not enough to certify an extractive answer.
    source_sentences = _scoped_sentences(claim.source_quote, None)
    return (
        len(source_sentences) == 1
        and all(mark not in source_sentences[0][0] for mark in "?!")
        and _normalized_atomic_sentence(source_sentences[0][0]) == target
    )


def _direct_acronym_subject(question: str) -> str | None:
    compact = " ".join(question.split())
    match = re.fullmatch(
        r"(?i:what does) ([A-Z][A-Z0-9-]{1,23}) (?i:stand for)\?",
        compact,
    )
    return match.group(1).casefold() if match is not None else None


def _acronym_expansion(statement: str, subject: str) -> str | None:
    if any(mark in statement for mark in "?!"):
        return None
    normalized = _normalized_atomic_sentence(statement)
    match = re.fullmatch(re.escape(subject) + r" stands for (.+)", normalized)
    if match is None:
        return None
    expansion = match.group(1)
    if (
        len(expansion) > 120
        or re.fullmatch(r"[\w]+(?:[\s-]+[\w]+){0,15}", expansion) is None
        or re.search(r"\b(?:but|however|instead|not|never|false)\b", expansion)
    ):
        return None
    return expansion


def _acronym_statement_subject(statement: str) -> str | None:
    compact = " ".join(statement.split())
    match = re.fullmatch(
        r"([A-Z][A-Z0-9-]{1,23}) (?i:stands for) (.+)", compact,
    )
    if match is None:
        return None
    subject = match.group(1).casefold()
    return (
        subject if _acronym_expansion(statement, subject) is not None
        else None
    )


def _independent_measurement_fact(sentence: str, subject: str) -> bool:
    normalized = _normalized_atomic_sentence(sentence).lstrip("-•* ")
    # Both propositions must name the same subject explicitly. Only an
    # affirmative, self-contained measurement fact is orthogonal to what an
    # acronym expands to; all denials, mixed sentences and unresolved clauses
    # retain the NLI contradiction veto.
    if re.search(
        r"\b(?:not|never|no|but|however|instead|rather|false|"
        r"stands for|means|acronym|expansion|abbreviation)\b", normalized,
    ):
        return False
    if len(_sentences(normalized)) != 1:
        return False
    pattern = re.escape(subject) + r" (?:measures|evaluates|compares) [^.?!]{1,200}"
    return re.fullmatch(pattern, normalized) is not None


def _specific_subject(heading: str | None) -> str | None:
    if heading is None:
        return None
    candidate = re.sub(r"^\s*\d+(?:\.\d+)*[.)]\s+", "", heading).strip()
    words = candidate.split()
    if not 1 <= len(words) <= 4 or len(candidate) > 48:
        return None
    if any(not re.fullmatch(r"[\w-]+", word, re.UNICODE) for word in words):
        return None
    if any(word.casefold() in {
        "is", "are", "was", "were", "means", "stands", "uses", "measures",
        "compares", "does", "has", "have", "not",
    } for word in words):
        return None
    if candidate.casefold() in {"overview", "introduction", "summary", "examples", "evaluation"}:
        return None
    return candidate


ScopeRelation = Literal["same_subject", "independent", "unresolved"]


def _scope_relation(
    source_subject: str, heading: str | None, sentence: str,
) -> ScopeRelation:
    other_subject = _specific_subject(heading)
    if _contains_subject(sentence, source_subject) or (
        other_subject is not None and other_subject.casefold() == source_subject.casefold()
    ):
        return "same_subject"
    if (
        other_subject is not None
        and not _contains_subject(other_subject, source_subject)
        and not _contains_subject(source_subject, other_subject)
        and _starts_with_subject(sentence, other_subject)
    ):
        return "independent"
    # Missing markers, coreference and relation ambiguity cannot be cleared
    # with a QA no-answer or low word overlap. Preserve their NLI veto.
    return "unresolved"


def _contains_subject(text: str, subject: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(subject).replace(r"\ ", r"\s+") + r"(?!\w)"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _starts_with_subject(sentence: str, subject: str) -> bool:
    # Only a sentence that names its own subject up front is independently
    # scoped. "It", "this method", and other anaphora stay unresolved.
    prefix = sentence.lstrip("-•* \t")
    pattern = r"^" + re.escape(subject).replace(r"\ ", r"\s+") + r"(?!\w)"
    return re.search(pattern, prefix, flags=re.IGNORECASE) is not None


def _explicit_heading(line: str) -> str | None:
    stripped = line.strip()
    markdown = re.fullmatch(r"#{1,6}\s+(.+?)\s*", stripped)
    if markdown is not None:
        return markdown.group(1)
    if stripped.endswith(":") and not stripped.startswith(("-", "*", "•")):
        return stripped[:-1].strip()
    if re.fullmatch(r"[A-Z][A-Z0-9-]{1,23}", stripped):
        return stripped
    return None


def _heading_at(text: str, default: str | None, offset: int) -> str | None:
    heading = default
    position = 0
    for line in text.splitlines(keepends=True):
        if position > offset:
            break
        detected = _explicit_heading(line)
        if detected is not None:
            heading = detected
        position += len(line)
    return heading


def _scoped_sentences(text: str, default: str | None) -> tuple[tuple[str, str | None], ...]:
    records: list[tuple[str, str | None]] = []
    heading = default
    pending: list[str] = []

    def flush() -> None:
        if pending:
            records.extend((sentence, heading) for sentence in _sentences(" ".join(pending)))
            pending.clear()

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        detected = _explicit_heading(stripped)
        if detected is not None:
            flush()
            heading = detected
            continue
        bullet = re.match(r"^(?:[-*•]|\d+[.)])\s+(.+)$", stripped)
        if bullet is not None:
            flush()
            pending.append(bullet.group(1))
            flush()
            continue
        pending.append(stripped)
    flush()
    return tuple(records)


def _sentences(text: str) -> tuple[str, ...]:
    import re

    values = tuple(part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip())
    return values if values else (text,)


def _verified_artifact(path: Path, expected_sha256: str) -> Path:
    if (
        not expected_sha256
        or len(expected_sha256) != 64
        or any(char not in "0123456789abcdef" for char in expected_sha256)
    ):
        raise LocalSupportUnavailable("Local support artifact digest is missing")
    if not path.is_file() or path.is_symlink():
        raise LocalSupportUnavailable("Local support artifact is unavailable")
    digest = sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    if digest.hexdigest() != expected_sha256:
        raise LocalSupportUnavailable("Local support artifact digest mismatch")
    return path


def _session_options():
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise LocalSupportUnavailable("Local support runtime is unavailable") from exc
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort, options


class OnnxNliScorer:
    """CPU-only local cross-encoder with artifact identity and input bounds.

    The ONNX graph and tokenizer are checked against immutable digests supplied
    by the release manifest.  Missing digests fail closed, preventing an
    operator-supplied path from silently changing the support policy.
    """

    def __init__(
        self,
        model_dir: Path,
        *,
        model_sha256: str,
        tokenizer_sha256: str,
        max_tokens: int = 384,
    ) -> None:
        if not 64 <= max_tokens <= 512:
            raise LocalSupportUnavailable("Unsupported local support token limit")
        model_path = _verified_artifact(model_dir / "model.onnx", model_sha256)
        tokenizer_path = _verified_artifact(
            model_dir / "tokenizer.json", tokenizer_sha256
        )

        try:
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise LocalSupportUnavailable("Local support runtime is unavailable") from exc
        try:
            ort, options = _session_options()
            tokenizer = Tokenizer.from_file(str(tokenizer_path))
            session = ort.InferenceSession(
                str(model_path),
                providers=["CPUExecutionProvider"],
                sess_options=options,
            )
            names = {item.name for item in session.get_inputs()}
            if not {"input_ids", "attention_mask"}.issubset(names) or not names.issubset(
                {"input_ids", "attention_mask", "token_type_ids"}
            ):
                raise LocalSupportUnavailable("Unexpected local support model inputs")
            output_shapes = [item.shape for item in session.get_outputs()]
            if len(output_shapes) != 1 or output_shapes[0][-1] != 3:
                raise LocalSupportUnavailable("Unexpected local support model output")
        except LocalSupportUnavailable:
            raise
        except Exception as exc:
            raise LocalSupportUnavailable("Local support model could not start") from exc
        self._tokenizer = tokenizer
        self._session = session
        self._input_names = names
        self._max_tokens = max_tokens

    def score(self, premise: str, hypothesis: str) -> NliScores:
        if not premise.strip() or not hypothesis.strip():
            raise LocalSupportUnavailable("Empty local support input")
        if len(premise) > 12_000 or len(hypothesis) > 4_000:
            raise LocalSupportUnavailable("Local support input exceeds bounds")
        try:
            import numpy as np

            encoded = self._tokenizer.encode(premise, hypothesis)
            # Truncation can erase the relation being checked. Fail closed
            # instead of classifying a different shortened proposition.
            if len(encoded.ids) > self._max_tokens:
                raise LocalSupportUnavailable("Local support input exceeds model context")
            feed = {
                "input_ids": np.asarray([encoded.ids], dtype=np.int64),
                "attention_mask": np.asarray([encoded.attention_mask], dtype=np.int64),
            }
            if "token_type_ids" in self._input_names:
                feed["token_type_ids"] = np.asarray([encoded.type_ids], dtype=np.int64)
            logits = self._session.run(None, feed)[0]
            if logits.shape != (1, 3) or not np.isfinite(logits).all():
                raise LocalSupportUnavailable("Invalid local support model output")
            shifted = logits[0] - np.max(logits[0])
            exp = np.exp(shifted)
            probabilities = exp / np.sum(exp)
            return NliScores(*(float(value) for value in probabilities))
        except LocalSupportUnavailable:
            raise
        except Exception as exc:
            raise LocalSupportUnavailable("Local support inference failed") from exc


class OnnxQaScorer:
    """Pinned, CPU-only extractive QA used only for question relevance."""

    def __init__(
        self,
        model_dir: Path,
        *,
        model_sha256: str,
        tokenizer_sha256: str,
        max_tokens: int = 384,
        max_answer_tokens: int = 64,
        no_answer_margin: float = 0.0,
    ) -> None:
        if not 64 <= max_tokens <= 512 or not 1 <= max_answer_tokens <= 128:
            raise LocalSupportUnavailable("Unsupported local question relevance bounds")
        model_path = _verified_artifact(model_dir / "model.onnx", model_sha256)
        tokenizer_path = _verified_artifact(
            model_dir / "tokenizer.json", tokenizer_sha256
        )
        try:
            from tokenizers import Tokenizer
        except ImportError as exc:
            raise LocalSupportUnavailable("Local support runtime is unavailable") from exc
        try:
            ort, options = _session_options()
            tokenizer = Tokenizer.from_file(str(tokenizer_path))
            session = ort.InferenceSession(
                str(model_path),
                providers=["CPUExecutionProvider"],
                sess_options=options,
            )
            input_names = {item.name for item in session.get_inputs()}
            if not {"input_ids", "attention_mask"}.issubset(input_names) or not input_names.issubset(
                {"input_ids", "attention_mask", "token_type_ids"}
            ):
                raise LocalSupportUnavailable("Unexpected local question model inputs")
            output_names = [item.name for item in session.get_outputs()]
            if output_names != ["start_logits", "end_logits"]:
                raise LocalSupportUnavailable("Unexpected local question model output")
        except LocalSupportUnavailable:
            raise
        except Exception as exc:
            raise LocalSupportUnavailable("Local question model could not start") from exc
        self._tokenizer = tokenizer
        self._session = session
        self._input_names = input_names
        self._max_tokens = max_tokens
        self._max_answer_tokens = max_answer_tokens
        self._no_answer_margin = no_answer_margin

    def answer(self, question: str, context: str) -> str | None:
        if not question.strip() or not context.strip():
            raise LocalSupportUnavailable("Empty local question relevance input")
        if len(question) > 4_000 or len(context) > 12_000:
            raise LocalSupportUnavailable("Local question relevance input exceeds bounds")
        try:
            import numpy as np

            encoded = self._tokenizer.encode(question, context)
            if len(encoded.ids) > self._max_tokens:
                raise LocalSupportUnavailable("Local question relevance input exceeds model context")
            feed = {
                "input_ids": np.asarray([encoded.ids], dtype=np.int64),
                "attention_mask": np.asarray([encoded.attention_mask], dtype=np.int64),
            }
            if "token_type_ids" in self._input_names:
                feed["token_type_ids"] = np.asarray([encoded.type_ids], dtype=np.int64)
            start_logits, end_logits = self._session.run(None, feed)
            if (
                start_logits.shape != (1, len(encoded.ids))
                or end_logits.shape != (1, len(encoded.ids))
                or not np.isfinite(start_logits).all()
                or not np.isfinite(end_logits).all()
            ):
                raise LocalSupportUnavailable("Invalid local question model output")
            no_answer_score = float(start_logits[0, 0] + end_logits[0, 0])
            context_positions = [
                index for index, sequence_id in enumerate(encoded.sequence_ids)
                if sequence_id == 1 and encoded.offsets[index] != (0, 0)
            ]
            best: tuple[float, int, int] | None = None
            for start in context_positions:
                for end in context_positions:
                    if end < start or end - start + 1 > self._max_answer_tokens:
                        continue
                    score = float(start_logits[0, start] + end_logits[0, end])
                    if best is None or score > best[0]:
                        best = (score, start, end)
            if best is None or best[0] <= no_answer_score + self._no_answer_margin:
                return None
            start_offset = encoded.offsets[best[1]][0]
            end_offset = encoded.offsets[best[2]][1]
            if not 0 <= start_offset < end_offset <= len(context):
                raise LocalSupportUnavailable("Invalid local question answer offsets")
            answer = context[start_offset:end_offset].strip()
            return answer or None
        except LocalSupportUnavailable:
            raise
        except Exception as exc:
            raise LocalSupportUnavailable("Local question relevance inference failed") from exc


def create_local_support_verifier(model_dir: Path | None) -> LocalSupportVerifier:
    """Build the local verifier only when both independent models are pinned."""

    if model_dir is None:
        raise LocalSupportUnavailable("Local support artifacts are unavailable")
    nli = OnnxNliScorer(
        model_dir / "nli",
        model_sha256=NLI_MODEL_SHA256,
        tokenizer_sha256=NLI_TOKENIZER_SHA256,
    )
    qa = OnnxQaScorer(
        model_dir / "qa",
        model_sha256=QA_MODEL_SHA256,
        tokenizer_sha256=QA_TOKENIZER_SHA256,
    )
    return LocalSupportVerifier(nli, qa)


__all__ = [
    "LOCAL_SUPPORT_POLICY_VERSION",
    "NLI_MODEL_ID",
    "NLI_MODEL_REVISION",
    "NLI_MODEL_SHA256",
    "NLI_TOKENIZER_SHA256",
    "QA_MODEL_ID",
    "QA_MODEL_REVISION",
    "QA_MODEL_SHA256",
    "QA_TOKENIZER_SHA256",
    "LocalSupportUnavailable",
    "LocalSupportVerdict",
    "LocalSupportVerifier",
    "LocalSupportVerifierV2",
    "LocalSupportVerifierV3",
    "NliScorer",
    "NliScores",
    "OnnxNliScorer",
    "OnnxQaScorer",
    "QaScorer",
    "create_local_support_verifier",
]
