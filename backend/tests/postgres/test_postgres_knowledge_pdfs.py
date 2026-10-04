"""Original PDF archive invariants in a guarded disposable PostgreSQL DB."""

import hashlib
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.privacy import delete_account

from tests.postgres.test_postgres_knowledge_schema import knowledge_connection, make_owner

pytestmark = pytest.mark.postgres


async def _revision(connection, owner_values=None):
    values = dict(owner_values or await make_owner(connection))
    values.update(document=uuid4(), revision=uuid4(), digest=hashlib.sha256(b"%PDF-1.7\nfixture").hexdigest())
    await connection.execute(text("""INSERT INTO subject_documents(id,subject_id,uploader_id,title,source_pdf_name,source_sha256)
        VALUES(:document,:subject,:owner,'PDF fixture','fixture.pdf',:digest)"""), values)
    await connection.execute(text("""INSERT INTO subject_document_content_revisions(id,document_id,subject_id,uploader_id,
        revision_no,source_sha256,extraction_version,reserved_page_count,reserved_page_chars,reserved_page_bytes)
        VALUES(:revision,:document,:subject,:owner,1,:digest,'pypdf_bounded_v1',1,7,7)"""), values)
    await connection.execute(text("""INSERT INTO subject_document_pages(content_revision_id,document_id,subject_id,uploader_id,page_number,content)
        VALUES(:revision,:document,:subject,:owner,1,'Fixture')"""), values)
    await connection.execute(text("UPDATE subject_document_content_revisions SET status='pending_index' WHERE id=:revision"), values)
    return values


async def _manifest(connection, values, *, size=16):
    await connection.execute(text("""INSERT INTO subject_document_pdfs(content_revision_id,document_id,subject_id,uploader_id,
        source_sha256,byte_size,page_count,block_count,key_version)
        VALUES(:revision,:document,:subject,:owner,:digest,:size,1,:count,1)"""),
        values | {"size": size, "count": (size+1048575)//1048576})


async def _block(connection, values, *, number=0, size=16):
    await connection.execute(text("""INSERT INTO subject_document_pdf_blocks(content_revision_id,block_number,plaintext_size,nonce,payload)
        VALUES(:revision,:number,:size,:nonce,:payload)"""),
        values | {"number": number, "size": size, "nonce": bytes(12), "payload": bytes(size+16)})


async def test_archive_is_complete_exact_revision_immutable_and_cascades(knowledge_connection):
    connection = knowledge_connection
    values = await _revision(connection)
    await _manifest(connection, values)
    await _block(connection, values)
    await connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    for statement in (
        "UPDATE subject_document_pdfs SET source_sha256=repeat('a',64) WHERE content_revision_id=:revision",
        "UPDATE subject_document_pdf_blocks SET nonce=decode(repeat('01',12),'hex') WHERE content_revision_id=:revision",
        "DELETE FROM subject_document_pdf_blocks WHERE content_revision_id=:revision",
    ):
        with pytest.raises(DBAPIError) as denied:
            async with connection.begin_nested():
                await connection.execute(text(statement), values)
        assert denied.value.orig.sqlstate == "23514"
    await connection.execute(text("DELETE FROM subject_documents WHERE id=:document"), values)
    assert await connection.scalar(text("SELECT count(*) FROM subject_document_pdfs WHERE content_revision_id=:revision"), values) == 0
    assert await connection.scalar(text("SELECT count(*) FROM subject_document_pdf_blocks WHERE content_revision_id=:revision"), values) == 0


async def test_manifest_without_all_blocks_cannot_commit(knowledge_connection):
    connection = knowledge_connection
    values = await _revision(connection)
    with pytest.raises(DBAPIError) as denied:
        async with connection.begin_nested():
            await _manifest(connection, values)
            await connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    assert denied.value.orig.sqlstate == "23514"
    assert await connection.scalar(text("SELECT count(*) FROM subject_document_pdfs WHERE content_revision_id=:revision"), values) == 0


async def test_operator_account_deletion_cascades_original_archive_and_blocks(knowledge_connection):
    connection = knowledge_connection
    values = await _revision(connection)
    await _manifest(connection, values)
    await _block(connection, values)
    await connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    async with AsyncSession(bind=connection, expire_on_commit=False) as session:
        assert (await delete_account(session, values["owner"]))["accounts"] == 1
        for table in ("subject_document_pdfs", "subject_document_pdf_blocks"):
            assert await session.scalar(text(f"SELECT count(*) FROM {table} WHERE content_revision_id=:revision"), values) == 0


@pytest.mark.parametrize("mutation", ["hash", "scope", "pages", "key"])
async def test_archive_identity_cannot_borrow_another_revision(knowledge_connection, mutation):
    connection = knowledge_connection
    values = await _revision(connection)
    fields = dict(values)
    if mutation == "hash": fields["digest"] = "b"*64
    if mutation == "scope": fields["subject"] = uuid4()
    statement = """INSERT INTO subject_document_pdfs(content_revision_id,document_id,subject_id,uploader_id,
        source_sha256,byte_size,page_count,block_count,key_version)
        VALUES(:revision,:document,:subject,:owner,:digest,16,:pages,1,:key)"""
    with pytest.raises(DBAPIError) as denied:
        async with connection.begin_nested():
            await connection.execute(text(statement), fields | {"pages": 2 if mutation=="pages" else 1, "key": 2 if mutation=="key" else 1})
            await connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    assert denied.value.orig.sqlstate in ("23514", "23503")


@pytest.mark.parametrize("number,size", [(1,16), (0,15)])
async def test_block_position_and_length_must_match_manifest(knowledge_connection, number, size):
    connection = knowledge_connection
    values = await _revision(connection)
    with pytest.raises(DBAPIError) as denied:
        async with connection.begin_nested():
            await _manifest(connection, values)
            await _block(connection, values, number=number, size=size)
    assert denied.value.orig.sqlstate == "23514"


async def test_subject_archive_capacity_serializes_before_block_storage(knowledge_connection):
    connection = knowledge_connection
    owner_values = await make_owner(connection)
    for _ in range(2):
        # Uncommitted manifests exercise byte admission without writing hundreds
        # of MiB of synthetic blocks; fixture always rolls back this transaction.
        await _manifest(connection, await _revision(connection, owner_values), size=100*1024*1024)
    third = await _revision(connection, owner_values)
    with pytest.raises(DBAPIError) as denied:
        async with connection.begin_nested():
            await _manifest(connection, third, size=100*1024*1024)
    assert denied.value.orig.sqlstate == "23514"
    assert "storage capacity" in str(denied.value.orig)
