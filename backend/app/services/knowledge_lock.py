"""Transaction admission order shared with the Knowledge schema triggers.

Acquire before explicit parent row locks for cascades/retention and future
capture/index mutations. The conservative foundation serializes Knowledge
writes; normal authentication, study and generation status writes do not take
this lock. SQLite supports fixture behavior only and deliberately skips it.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


KNOWLEDGE_LOCK_NAMESPACE = 13013
KNOWLEDGE_LOCK_KEY = 0


async def acquire_knowledge_write_lock(db: AsyncSession) -> None:
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(:namespace, :key)"),
                         {"namespace": KNOWLEDGE_LOCK_NAMESPACE, "key": KNOWLEDGE_LOCK_KEY})
