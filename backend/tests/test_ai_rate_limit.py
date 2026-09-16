import asyncio

import pytest

from app.ai.rate_limit import ProviderRateGovernor, ProviderRateLimitExceeded


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.delays: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.delays.append(delay)
        self.now += delay
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_governor_counts_attempts_retries_and_waits_by_operation():
    clock = FakeClock()
    governor = ProviderRateGovernor(
        requests_per_minute=2,
        input_tokens_per_minute=1_000,
        safety_percent=50,
        window_seconds=60,
        clock=clock,
        sleep=clock.sleep,
    )

    await governor.reserve(100, operation="summary_map", attempt=0)
    await governor.reserve(100, operation="summary_map", attempt=1)

    snapshot = await governor.snapshot()
    operation = snapshot.by_operation["summary_map"]
    assert governor.requests_per_window == 1
    assert clock.delays == [60]
    assert snapshot.request_attempts == 2
    assert snapshot.retry_attempts == 1
    assert snapshot.wait_count == 1
    assert snapshot.wait_seconds == 60
    assert snapshot.current_window_requests == 1
    assert operation.request_attempts == 2
    assert operation.retry_attempts == 1
    assert operation.wait_count == 1


@pytest.mark.asyncio
async def test_governor_reconciles_estimated_tokens_to_actual_usage():
    clock = FakeClock()
    governor = ProviderRateGovernor(
        requests_per_minute=0,
        input_tokens_per_minute=100,
        safety_percent=100,
        clock=clock,
        sleep=clock.sleep,
    )

    first = await governor.reserve(80, operation="planning", attempt=0)
    await first.commit(20)
    await first.commit(90)  # Reconciliation is idempotent.
    await governor.reserve(80, operation="generation", attempt=0)

    snapshot = await governor.snapshot()
    assert clock.delays == []
    assert snapshot.current_window_input_tokens == 100
    assert snapshot.estimated_input_tokens == 160
    assert snapshot.actual_input_tokens == 20
    assert snapshot.by_operation["planning"].actual_input_tokens == 20


@pytest.mark.asyncio
async def test_cancelled_waiter_is_removed_without_refunding_admitted_request():
    waiting = asyncio.Event()
    never_release = asyncio.Event()

    async def blocked_sleep(_delay: float) -> None:
        waiting.set()
        await never_release.wait()

    governor = ProviderRateGovernor(
        requests_per_minute=1,
        input_tokens_per_minute=0,
        safety_percent=100,
        sleep=blocked_sleep,
    )
    await governor.reserve(10, operation="summary_map", attempt=0)
    blocked = asyncio.create_task(
        governor.reserve(10, operation="card_generation", attempt=0)
    )
    await waiting.wait()

    blocked.cancel()
    with pytest.raises(asyncio.CancelledError):
        await blocked

    snapshot = await governor.snapshot()
    assert snapshot.request_attempts == 1
    assert snapshot.current_window_requests == 1
    assert snapshot.queued_waiters == 0
    assert snapshot.by_operation["card_generation"].wait_count == 1


@pytest.mark.asyncio
async def test_one_request_larger_than_safe_tpm_fails_without_waiting():
    governor = ProviderRateGovernor(
        requests_per_minute=5,
        input_tokens_per_minute=100,
        safety_percent=80,
    )

    with pytest.raises(ProviderRateLimitExceeded):
        await governor.reserve(81, operation="oversized", attempt=0)

    snapshot = await governor.snapshot()
    assert snapshot.request_attempts == 0
    assert snapshot.queued_waiters == 0


def test_governor_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        ProviderRateGovernor(
            requests_per_minute=-1,
            input_tokens_per_minute=100,
            safety_percent=80,
        )
    with pytest.raises(ValueError):
        ProviderRateGovernor(
            requests_per_minute=1,
            input_tokens_per_minute=100,
            safety_percent=0,
        )
