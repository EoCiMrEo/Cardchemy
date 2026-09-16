"""Worker-local rolling-window limits for physical AI provider requests.

The generation worker shares one governor across all jobs in its process.  A
reservation represents provider capacity that may already have been consumed;
therefore admitted reservations deliberately remain charged when a request is
cancelled or fails with unknown usage.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
import math
import time
from typing import Awaitable, Callable


Clock = Callable[[], float]
Sleeper = Callable[[float], Awaitable[None]]


class ProviderRateLimitExceeded(RuntimeError):
    """One request can never fit inside the configured input-token budget."""


@dataclass(slots=True)
class _WindowReservation:
    admitted_at: float
    input_tokens: int
    operation: str
    attempt: int
    actual_input_tokens: int | None = None


@dataclass(slots=True)
class _OperationMetrics:
    request_attempts: int = 0
    retry_attempts: int = 0
    wait_count: int = 0
    wait_seconds: float = 0.0
    estimated_input_tokens: int = 0
    actual_input_tokens: int = 0


@dataclass(frozen=True, slots=True)
class OperationRateMetrics:
    request_attempts: int
    retry_attempts: int
    wait_count: int
    wait_seconds: float
    estimated_input_tokens: int
    actual_input_tokens: int


@dataclass(frozen=True, slots=True)
class ProviderRateSnapshot:
    request_attempts: int
    retry_attempts: int
    wait_count: int
    wait_seconds: float
    estimated_input_tokens: int
    actual_input_tokens: int
    current_window_requests: int
    current_window_input_tokens: int
    queued_waiters: int
    by_operation: dict[str, OperationRateMetrics]


@dataclass(slots=True)
class _Totals:
    request_attempts: int = 0
    retry_attempts: int = 0
    wait_count: int = 0
    wait_seconds: float = 0.0
    estimated_input_tokens: int = 0
    actual_input_tokens: int = 0
    by_operation: dict[str, _OperationMetrics] = field(default_factory=dict)

    def operation(self, name: str) -> _OperationMetrics:
        return self.by_operation.setdefault(name, _OperationMetrics())


class ProviderRateReservation:
    """An admitted request whose token estimate can be reconciled once."""

    def __init__(
        self,
        governor: ProviderRateGovernor,
        reservation: _WindowReservation,
        *,
        waited_seconds: float,
    ) -> None:
        self._governor = governor
        self._reservation = reservation
        self.waited_seconds = max(0.0, waited_seconds)

    async def commit(self, actual_input_tokens: int) -> None:
        if actual_input_tokens < 0:
            raise ValueError("actual provider input tokens cannot be negative")
        await self._governor._commit(self._reservation, actual_input_tokens)


class ProviderRateGovernor:
    """FIFO asynchronous RPM/TPM governor shared by provider adapters.

    Limits use a strict rolling window.  A value of zero disables that one
    dimension, which keeps custom/local providers backwards compatible while
    allowing deployments to configure either or both provider quotas.
    """

    def __init__(
        self,
        *,
        requests_per_minute: int,
        input_tokens_per_minute: int,
        safety_percent: int | float,
        window_seconds: float = 60.0,
        clock: Clock | None = None,
        sleep: Sleeper | None = None,
    ) -> None:
        if requests_per_minute < 0 or input_tokens_per_minute < 0:
            raise ValueError("provider rate limits cannot be negative")
        if not 0 < float(safety_percent) <= 100:
            raise ValueError("provider rate-limit safety percent must be in (0, 100]")
        if window_seconds <= 0:
            raise ValueError("provider rate-limit window must be positive")

        self.requests_per_window = self._effective_limit(
            requests_per_minute, safety_percent
        )
        self.input_tokens_per_window = self._effective_limit(
            input_tokens_per_minute, safety_percent
        )
        self.window_seconds = float(window_seconds)
        self._clock = clock or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._condition = asyncio.Condition()
        self._capacity_changed = asyncio.Event()
        self._reservations: deque[_WindowReservation] = deque()
        self._waiters: deque[object] = deque()
        self._totals = _Totals()

    @classmethod
    def from_settings(cls, settings: object) -> ProviderRateGovernor:
        return cls(
            requests_per_minute=int(getattr(settings, "ai_requests_per_minute", 0)),
            input_tokens_per_minute=int(
                getattr(settings, "ai_input_tokens_per_minute", 0)
            ),
            safety_percent=float(
                getattr(settings, "ai_rate_limit_safety_percent", 100)
            ),
        )

    @staticmethod
    def _effective_limit(configured: int, safety_percent: int | float) -> int:
        if configured == 0:
            return 0
        return max(1, math.floor(configured * float(safety_percent) / 100))

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._reservations and self._reservations[0].admitted_at <= cutoff:
            self._reservations.popleft()

    def _required_delay(self, now: float, input_tokens: int) -> float:
        delays = [0.0]
        if (
            self.requests_per_window
            and len(self._reservations) >= self.requests_per_window
        ):
            delays.append(
                self._reservations[0].admitted_at + self.window_seconds - now
            )

        if self.input_tokens_per_window:
            used = sum(item.input_tokens for item in self._reservations)
            if used + input_tokens > self.input_tokens_per_window:
                remaining = used
                for item in self._reservations:
                    remaining -= item.input_tokens
                    if remaining + input_tokens <= self.input_tokens_per_window:
                        delays.append(item.admitted_at + self.window_seconds - now)
                        break
        return max(0.0, max(delays))

    async def reserve(
        self,
        input_tokens: int,
        *,
        operation: str,
        attempt: int,
    ) -> ProviderRateReservation:
        if input_tokens < 0:
            raise ValueError("estimated provider input tokens cannot be negative")
        if attempt < 0:
            raise ValueError("provider attempt cannot be negative")
        if not operation:
            raise ValueError("provider operation cannot be empty")
        if (
            self.input_tokens_per_window
            and input_tokens > self.input_tokens_per_window
        ):
            raise ProviderRateLimitExceeded(
                "One AI request exceeds the configured safe input-token rate budget."
            )

        ticket = object()
        started_at = self._clock()
        waited = False
        admitted = False
        async with self._condition:
            self._waiters.append(ticket)

        try:
            while True:
                delay: float | None = None
                async with self._condition:
                    if self._waiters and self._waiters[0] is ticket:
                        now = self._clock()
                        self._prune(now)
                        delay = self._required_delay(now, input_tokens)
                        if delay <= 0:
                            reservation = _WindowReservation(
                                admitted_at=now,
                                input_tokens=input_tokens,
                                operation=operation,
                                attempt=attempt,
                            )
                            self._reservations.append(reservation)
                            self._waiters.popleft()
                            admitted = True
                            self._record_admission(reservation)
                            if waited:
                                self._record_wait(
                                    operation, max(0.0, now - started_at)
                                )
                            self._condition.notify_all()
                            return ProviderRateReservation(
                                self,
                                reservation,
                                waited_seconds=max(0.0, now - started_at),
                            )
                        self._capacity_changed.clear()

                    if delay is None:
                        waited = True
                        await self._condition.wait()
                        continue

                waited = True
                await self._wait_for_capacity_change(delay)
        finally:
            if not admitted:
                async with self._condition:
                    try:
                        self._waiters.remove(ticket)
                    except ValueError:
                        pass
                    if waited:
                        self._record_wait(
                            operation, max(0.0, self._clock() - started_at)
                        )
                    self._condition.notify_all()
                    self._capacity_changed.set()

    async def _wait_for_capacity_change(self, delay: float) -> None:
        """Wake early when actual usage reconciliation frees token capacity."""

        tasks = [
            asyncio.create_task(self._sleep(delay)),
            asyncio.create_task(self._capacity_changed.wait()),
        ]
        try:
            done, _ = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                task.result()
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def _record_admission(self, reservation: _WindowReservation) -> None:
        self._totals.request_attempts += 1
        self._totals.estimated_input_tokens += reservation.input_tokens
        operation = self._totals.operation(reservation.operation)
        operation.request_attempts += 1
        operation.estimated_input_tokens += reservation.input_tokens
        if reservation.attempt > 0:
            self._totals.retry_attempts += 1
            operation.retry_attempts += 1

    def _record_wait(self, operation_name: str, duration: float) -> None:
        self._totals.wait_count += 1
        self._totals.wait_seconds += duration
        operation = self._totals.operation(operation_name)
        operation.wait_count += 1
        operation.wait_seconds += duration

    async def _commit(
        self,
        reservation: _WindowReservation,
        actual_input_tokens: int,
    ) -> None:
        async with self._condition:
            if reservation.actual_input_tokens is not None:
                return
            reservation.actual_input_tokens = actual_input_tokens
            reservation.input_tokens = actual_input_tokens
            self._totals.actual_input_tokens += actual_input_tokens
            self._totals.operation(
                reservation.operation
            ).actual_input_tokens += actual_input_tokens
            self._condition.notify_all()
            self._capacity_changed.set()

    async def snapshot(self) -> ProviderRateSnapshot:
        async with self._condition:
            self._prune(self._clock())
            by_operation = {
                name: OperationRateMetrics(
                    request_attempts=value.request_attempts,
                    retry_attempts=value.retry_attempts,
                    wait_count=value.wait_count,
                    wait_seconds=value.wait_seconds,
                    estimated_input_tokens=value.estimated_input_tokens,
                    actual_input_tokens=value.actual_input_tokens,
                )
                for name, value in self._totals.by_operation.items()
            }
            return ProviderRateSnapshot(
                request_attempts=self._totals.request_attempts,
                retry_attempts=self._totals.retry_attempts,
                wait_count=self._totals.wait_count,
                wait_seconds=self._totals.wait_seconds,
                estimated_input_tokens=self._totals.estimated_input_tokens,
                actual_input_tokens=self._totals.actual_input_tokens,
                current_window_requests=len(self._reservations),
                current_window_input_tokens=sum(
                    item.input_tokens for item in self._reservations
                ),
                queued_waiters=len(self._waiters),
                by_operation=by_operation,
            )


__all__ = [
    "OperationRateMetrics",
    "ProviderRateGovernor",
    "ProviderRateLimitExceeded",
    "ProviderRateReservation",
    "ProviderRateSnapshot",
]
