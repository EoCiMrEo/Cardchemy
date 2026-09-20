"""Restore actual Subject Knowledge only in owned disposable child databases."""

import asyncio
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine


pytestmark = pytest.mark.postgres
ROOT = Path(__file__).resolve().parents[3]


async def docker_bytes(environment, *arguments, input_bytes=None):
    result = await asyncio.to_thread(
        subprocess.run, ["docker", *arguments], env=environment,
        input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=60, check=False,
    )
    if result.returncode:
        raise RuntimeError("Owned Knowledge backup/restore command failed; details withheld")
    return result.stdout


async def assert_restored_knowledge(connection, values):
    assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260920_0013"
    assert await connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'")) == "0.8.6"
    assert (await connection.execute(text("""
        SELECT page_number,length(content) FROM subject_document_pages
        WHERE content_revision_id=:content_revision ORDER BY page_number
    """), values)).all() == [(1, values["chars"]), (2, 0)]
    assert (await connection.execute(text("""
        SELECT actual_page_count,actual_page_chars,actual_page_bytes,reviewed_by_id,
               published_at IS NOT NULL,is_active
        FROM subject_document_content_revisions WHERE id=:content_revision
    """), values)).one() == (2, values["chars"], values["bytes"], values["owner"], True, True)
    assert (await connection.execute(text("""
        SELECT actual_chunk_count,actual_embedded_count,actual_index_bytes,is_active
        FROM subject_document_index_revisions WHERE id=:index_revision
    """), values)).one() == (1, 1, values["charged"], True)
    assert await connection.scalar(text("""
        SELECT vector_dims(embedding) FROM subject_document_chunks WHERE id=:chunk
    """), values) == 1536
    assert await connection.scalar(text("""
        SELECT id FROM eligible_subject_knowledge_chunks WHERE subject_id=:subject
        ORDER BY embedding OPERATOR(public.<=>)
          array_prepend(1::real,array_fill(0::real,ARRAY[1535]))::public.vector LIMIT 1
    """), values) == values["chunk"]
    assert await connection.scalar(text("""
        SELECT count(*) FROM eligible_subject_knowledge_chunks WHERE subject_id=:subject
          AND to_tsvector('simple'::regconfig,content) @@ plainto_tsquery('simple','Synthetic')
    """), values) == 1
    assert await connection.scalar(text("""
        SELECT count(*) FROM pg_index entry JOIN pg_class index_class ON index_class.oid=entry.indexrelid
          WHERE index_class.relname='ix_knowledge_chunks_fts' AND entry.indisvalid
    """)) == 1
    charges = (await connection.execute(text("""
        SELECT scope_type,document_count,charged_bytes FROM knowledge_storage_usage ORDER BY scope_type
    """))).all()
    assert charges == [(scope, 1, values["bytes"] + values["charged"])
                       for scope in ("global", "subject", "uploader")]
    assert (await connection.execute(text("""
        SELECT document_id,knowledge_capture_removed FROM generation_jobs WHERE id=:job
    """), values)).one() == (values["document"], False)
    assert (await connection.execute(text("""
        SELECT document_id,generation_job_id,source_pdf_name FROM flashcard_sets WHERE id=:set_id
    """), values)).one() == (values["document"], values["job"], "fixture.pdf")
    assert (await connection.execute(text("""
        SELECT index_revision_id,corpus_revision,claim_token FROM subject_document_index_jobs WHERE id=:index_job
    """), values)).one() == (values["index_revision"], values["corpus_revision"], None)


async def test_actual_knowledge_vector_publication_claim_and_links_dump_restore(postgres_engine):
    # The canonical service runner injects only its exact generated container
    # name. Manual non-container database runs deliberately skip this verifier.
    container = os.environ.get("POSTGRES_TEST_CONTAINER_NAME")
    if container is None:
        pytest.skip("Owned Docker PostgreSQL backup/restore verification is not configured")
    if re.fullmatch(r"flashcard-regression-db-[0-9a-f]{12}", container) is None:
        pytest.fail("Knowledge recovery requires an owned regression container", pytrace=False)
    url = postgres_engine.url
    if url.database != "regression_test" or url.username != "qa" or url.host != "127.0.0.1":
        pytest.fail("Knowledge recovery requires the canonical disposable PostgreSQL profile", pytrace=False)
    service = runpy.run_path(str(ROOT / "scripts/test_services.py"))
    environment = service["system_environment"]()
    image, _ = await asyncio.to_thread(service["ensure_database_image"])
    assert (await docker_bytes(environment, "inspect", "--format", "{{.Image}}", container)).decode().strip() == image
    assert (await docker_bytes(environment, "port", container, "5432/tcp")).decode().strip() == f"127.0.0.1:{url.port}"
    helpers = runpy.run_path(str(Path(__file__).with_name("test_postgres_knowledge_schema.py")))
    source = f"knowledge_recovery_source_{uuid4().hex}_test"
    target = f"knowledge_recovery_target_{uuid4().hex}_test"
    owned_databases = []
    child_engines = []
    try:
        async with postgres_engine.connect() as admin:
            admin = await admin.execution_options(isolation_level="AUTOCOMMIT")
            for name in (source, target):
                await admin.execute(text(f'CREATE DATABASE "{name}" TEMPLATE template0'))
                owned_databases.append(name)
        child_url = url.set(database=source)
        migration_environment = environment | {
            "ENVIRONMENT": "test", "DATABASE_URL": child_url.render_as_string(hide_password=False),
            "SECRET_KEY": "test-only-secret-with-adequate-entropy-1234567890",
            "GENERATION_SOURCE_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "PYTHONUTF8": "1",
        }
        migrated = await asyncio.to_thread(
            subprocess.run, [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=ROOT / "backend", env=migration_environment, capture_output=True, timeout=60, check=False,
        )
        if migrated.returncode:
            raise RuntimeError("Owned Knowledge recovery source migration failed; details withheld")
        source_engine = create_async_engine(child_url, hide_parameters=True)
        target_engine = create_async_engine(url.set(database=target), hide_parameters=True)
        child_engines.extend((source_engine, target_engine))
        async with source_engine.begin() as connection:
            assert await connection.scalar(text("SELECT current_database()")) == source
            values = await helpers["make_ready"](connection, await helpers["make_owner"](connection))
            values.update(job=uuid4(), set_id=uuid4(), card=uuid4(), index_job=uuid4())
            await connection.execute(text("""
                UPDATE subject_document_content_revisions SET reviewed_at=now(),reviewed_by_id=:owner,published_at=now()
                WHERE id=:content_revision
            """), values)
            values["corpus_revision"] = await connection.scalar(text("SELECT corpus_revision FROM subjects WHERE id=:subject"), values)
            await connection.execute(text("""
                INSERT INTO generation_jobs(id,user_id,subject_id,document_id,idempotency_key_hash,request_fingerprint,
                  status,set_title,requested_card_count,source_pdf_name)
                VALUES(:job,:owner,:subject,:document,repeat('b',64),repeat('c',64),'awaiting_upload','Fixture',5,'fixture.pdf')
            """), values)
            await connection.execute(text("""
                INSERT INTO flashcard_sets(id,subject_id,title,generation_job_id,document_id,source_pdf_name)
                VALUES(:set_id,:subject,'Fixture',:job,:document,'fixture.pdf')
            """), values)
            await connection.execute(text("""
                INSERT INTO flashcards(id,set_id,front_content,back_content,options)
                VALUES(:card,:set_id,'Recovery fixture?','A','["A","B","C","D"]'::jsonb)
            """), values)
            await connection.execute(text("""
                INSERT INTO subject_document_index_jobs(id,index_revision_id,content_revision_id,document_id,subject_id,uploader_id,
                  operation_key_hash,request_fingerprint,corpus_revision,deadline_at)
                VALUES(:index_job,:index_revision,:content_revision,:document,:subject,:owner,repeat('d',64),repeat('e',64),
                  :corpus_revision,now()+interval '1 hour')
            """), values)
            await assert_restored_knowledge(connection, values)
        archive = await docker_bytes(environment, "exec", container, "pg_dump", "-U", "qa", "-d", source,
                                     "-Fc", "--no-owner", "--no-acl")
        assert 0 < len(archive) <= 4 * 1024 * 1024
        await docker_bytes(environment, "exec", "-i", container, "pg_restore", "-U", "qa", "-d", target,
                           "--exit-on-error", "--no-owner", "--no-acl", input_bytes=archive)
        del archive  # No backup file or synthetic content is written to disk.
        async with target_engine.begin() as connection:
            assert await connection.scalar(text("SELECT current_database()")) == target
            await assert_restored_knowledge(connection, values)
            with pytest.raises(DBAPIError) as failure:
                async with connection.begin_nested():
                    await connection.execute(text("UPDATE knowledge_storage_usage SET charged_bytes=0 WHERE scope_type='subject'"))
            assert failure.value.orig.sqlstate == "23514"
            await connection.execute(text("DELETE FROM subject_documents WHERE id=:document"), values)
            assert await connection.scalar(text("SELECT count(*) FROM subject_document_pages")) == 0
            assert await connection.scalar(text("SELECT count(*) FROM subject_document_chunks")) == 0
            assert await connection.scalar(text("SELECT count(*) FROM subject_document_index_jobs")) == 0
            assert (await connection.execute(text("SELECT document_id,knowledge_capture_removed FROM generation_jobs WHERE id=:job"), values)).one() == (None, True)
            assert await connection.scalar(text("SELECT document_id FROM flashcard_sets WHERE id=:set_id"), values) is None
            assert await connection.scalar(text("SELECT count(*) FROM flashcards WHERE id=:card"), values) == 1
            assert (await connection.execute(text("SELECT document_count,charged_bytes FROM knowledge_storage_usage WHERE scope_type='global'"))).one() == (0, 0)
    finally:
        for engine in child_engines:
            await engine.dispose()
        async with postgres_engine.connect() as admin:
            admin = await admin.execution_options(isolation_level="AUTOCOMMIT")
            for name in reversed(owned_databases):
                await admin.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
            assert await admin.scalar(text("SELECT count(*) FROM pg_database WHERE datname IN (:source,:target)"),
                                      {"source": source, "target": target}) == 0
