"""Concurrent instructor bootstrap preserves the additional-account guard."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app import cli
from app.models.audit import AuditEvent
from app.models.user import User, UserRole

pytestmark = pytest.mark.postgres


async def test_concurrent_first_instructor_provisioning_requires_explicit_additional_flag(postgres_engine, monkeypatch, capsys):
    # Clone the two deployed tables into this test's private namespace so the
    # global bootstrap guard does not count other regression fixtures. No
    # operator database or other tests' accounts are modified.
    namespace = f"provision_{uuid4().hex}"
    isolated_engine = postgres_engine.execution_options(schema_translate_map={None: namespace})
    factory = async_sessionmaker(isolated_engine, expire_on_commit=False)
    async with postgres_engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{namespace}"'))
        # schema_translate_map also qualifies enum binds. Give the isolated
        # column the same translated enum type as those binds.
        await connection.execute(text(f"CREATE TYPE \"{namespace}\".userrole AS ENUM ('INSTRUCTOR', 'STUDENT')"))
        await connection.execute(text(f'CREATE TABLE "{namespace}".users (LIKE public.users INCLUDING ALL)'))
        await connection.execute(text(f'ALTER TABLE "{namespace}".users ALTER COLUMN role DROP DEFAULT'))
        await connection.execute(text(f'ALTER TABLE "{namespace}".users ALTER COLUMN role TYPE "{namespace}".userrole USING role::text::"{namespace}".userrole'))
        await connection.execute(text(f'CREATE TABLE "{namespace}".audit_events (LIKE public.audit_events INCLUDING ALL)'))
    password = "test-only provisioning password"
    emails = ["provision-first@example.com", "provision-second@example.com"]
    monkeypatch.setattr(cli, "async_session_maker", factory)
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: password)

    async def provision(email):
        try:
            await cli.create_instructor(email, "Private instructor name", False)
        except SystemExit as exc:
            return str(exc.code)
        return "created"

    try:
        results = await asyncio.wait_for(asyncio.gather(*(provision(email) for email in emails)), timeout=15)
        assert results.count("created") == 1
        assert sum("--allow-additional" in result for result in results) == 1
        async with factory() as db:
            assert await db.scalar(select(func.count(User.id)).where(User.role == UserRole.INSTRUCTOR)) == 1
            assert await db.scalar(select(func.count(AuditEvent.id)).where(AuditEvent.action == "account.instructor_provisioned")) == 1
        output = capsys.readouterr()
        assert password not in output.out + output.err
        assert all(email not in output.out + output.err for email in emails)
        assert "Private instructor name" not in output.out + output.err
        assert output.out.count("instructor_created") == 1
    finally:
        async with postgres_engine.begin() as connection:
            # The name is generated here from a UUID and is used only on the
            # guarded disposable *_test database checked by postgres_engine.
            await connection.execute(text(f'DROP SCHEMA "{namespace}" CASCADE'))
