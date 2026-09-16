"""Shared bounded-drain behavior for durable background workers."""

import asyncio
from collections.abc import Collection


async def drain_active_tasks(
    tasks: Collection[asyncio.Task[None]], grace_seconds: float
) -> int:
    """Wait for active tasks, then cancel only those exceeding the grace period."""

    active = tuple(task for task in tasks if not task.done())
    if not active:
        return 0

    done, pending = await asyncio.wait(active, timeout=grace_seconds)
    if done:
        await asyncio.gather(*done, return_exceptions=True)
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    return len(pending)
