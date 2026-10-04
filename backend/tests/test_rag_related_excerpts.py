"""An unverified excerpt is visible only with a complete current source bundle."""

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config import Settings
from app.schemas.rag import RagRelatedExcerptResponse
from app.services.knowledge_retrieval import AuthorizedKnowledgeSource
from app.services.rag_answers import RagAnswerService, _read_related_pages
from app.time_utils import utcnow


pytestmark = pytest.mark.asyncio


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _DB:
    def __init__(self, rows):
        self.rows = rows

    async def scalars(self, _query):
        return _Rows(self.rows)


def _fixture():
    user_id, subject_id, thread_id, job_id = (uuid4() for _ in range(4))
    first_id, second_id = uuid4(), uuid4()
    document_id, revision_id, index_id = uuid4(), uuid4(), uuid4()
    now = utcnow()
    job = SimpleNamespace(
        id=job_id, user_id=user_id, subject_id=subject_id,
        thread_id=thread_id, status="failed", error_code="rag_answer_failed",
        answer_message_id=None, manual_retry_count=0, document_ids=[],
        corpus_revision=7, embedding_space_hash="a" * 64,
    )
    sources = {
        chunk_id: AuthorizedKnowledgeSource(
            chunk_id=chunk_id, document_id=document_id,
            document_title="Lecture", content_revision_id=revision_id,
            index_revision_id=index_id, page_number=page, section="Topic",
            content=content, token_count=20,
            embedding_space_hash="a" * 64, corpus_revision=7,
        )
        for chunk_id, page, content in (
            (first_id, 2, "First exact published passage."),
            (second_id, 3, "Second exact published passage."),
        )
    }
    refs = [
        SimpleNamespace(
            job_id=job_id, excerpt_order=order, thread_id=thread_id,
            user_id=user_id, subject_id=subject_id, chunk_id=chunk_id,
            document_id=document_id, content_revision_id=revision_id,
            index_revision_id=index_id, start_offset=0,
            source_kind="chunk",
            end_offset=len(sources[chunk_id].content), manual_retry_number=0,
            bundle_size=2, expires_at=now + timedelta(days=1),
        )
        for order, chunk_id in enumerate((first_id, second_id), start=1)
    ]
    return SimpleNamespace(id=user_id), subject_id, job, refs, sources


@pytest.fixture(autouse=True)
def canonical_page_reads(monkeypatch):
    async def pages(db, *, chunk_ids, **_kwargs):
        return {row.chunk_id: (
            "First exact published passage." if row.excerpt_order == 1
            else "Second exact published passage."
        ) for row in db.rows if row.chunk_id in chunk_ids}

    monkeypatch.setattr("app.services.rag_answers._read_related_pages", pages)


def _service():
    return RagAnswerService(Settings(
        _env_file=None, environment="test",
        secret_key="test-only-secret-key-with-adequate-entropy-1234567890",
        generation_source_encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    ))


async def test_terminal_failure_shows_only_exact_bounded_source_text(monkeypatch):
    user, subject_id, job, refs, sources = _fixture()

    async def authorized(_db, **_kwargs):
        return sources

    monkeypatch.setattr("app.services.rag_answers.read_eligible_source_batch", authorized)
    result = await _service()._related_excerpts_for_jobs(
        _DB(refs), jobs=[job], user=user, subject_id=subject_id,
    )
    assert [item.source_quote for item in result[job.id]] == [
        "First exact published passage.", "Second exact published passage.",
    ]
    assert all("claim_text" not in item.model_dump() for item in result[job.id])


async def test_source_only_completed_bundle_is_ordered_and_never_an_answer(monkeypatch):
    user, subject_id, job, refs, sources = _fixture()
    job.status = "completed"
    job.error_code = None
    job.answer_policy_version = "related_knowledge_v1"
    job.result_kind = "related_knowledge"
    job.answer_message_id = None

    async def authorized(_db, **_kwargs):
        return sources

    monkeypatch.setattr("app.services.rag_answers.read_eligible_source_batch", authorized)
    result = await _service()._related_excerpts_for_jobs(
        _DB(refs), jobs=[job], user=user, subject_id=subject_id,
    )
    assert [(item.excerpt_order, item.source_quote) for item in result[job.id]] == [
        (1, "First exact published passage."),
        (2, "Second exact published passage."),
    ]
    refs.pop()
    assert await _service()._related_excerpts_for_jobs(
        _DB(refs), jobs=[job], user=user, subject_id=subject_id,
    ) == {}


@pytest.mark.parametrize("mutation", [
    "missing_second", "wrong_revision", "wrong_retry", "wrong_document_scope",
    "wrong_offset", "answered_job", "unknown_kind", "expired",
])
async def test_incomplete_stale_or_verified_bundles_are_hidden(monkeypatch, mutation):
    user, subject_id, job, refs, sources = _fixture()
    if mutation == "missing_second":
        refs.pop()
    elif mutation == "wrong_revision":
        sources[refs[0].chunk_id] = replace(
            sources[refs[0].chunk_id], corpus_revision=8,
        )
    elif mutation == "wrong_retry":
        job.manual_retry_count = 1
    elif mutation == "wrong_document_scope":
        job.document_ids = [str(uuid4())]
    elif mutation == "wrong_offset":
        refs[0].end_offset = 480
    elif mutation == "answered_job":
        job.status = "completed"
        job.error_code = None
    elif mutation == "unknown_kind":
        refs[0].source_kind = "unknown"
    elif mutation == "expired":
        refs[0].expires_at = utcnow() - timedelta(seconds=1)

    async def authorized(_db, **_kwargs):
        return sources

    monkeypatch.setattr("app.services.rag_answers.read_eligible_source_batch", authorized)
    result = await _service()._related_excerpts_for_jobs(
        _DB(refs), jobs=[job], user=user, subject_id=subject_id,
    )
    assert result == {}


async def test_canonical_reference_reads_exact_page_slice_beyond_chunk_offsets(monkeypatch):
    user, subject_id, job, refs, sources = _fixture()
    page = "Owning heading\n\n" + sources[refs[0].chunk_id].content
    refs[0].source_kind = "canonical_page"
    refs[0].end_offset = len(page)

    async def authorized(_db, **_kwargs):
        return sources

    async def pages(_db, *, chunk_ids, **_kwargs):
        return {refs[0].chunk_id: page, refs[1].chunk_id: sources[refs[1].chunk_id].content}

    monkeypatch.setattr("app.services.rag_answers.read_eligible_source_batch", authorized)
    monkeypatch.setattr("app.services.rag_answers._read_related_pages", pages)
    result = await _service()._related_excerpts_for_jobs(
        _DB(refs), jobs=[job], user=user, subject_id=subject_id,
    )
    assert result[job.id][0].source_quote == page
    assert result[job.id][1].source_quote == sources[refs[1].chunk_id].content


async def test_legacy_chunk_bundle_remains_visible_without_page_load(monkeypatch):
    user, subject_id, job, refs, sources = _fixture()

    async def authorized(_db, **_kwargs):
        return sources

    async def no_pages(_db, *, chunk_ids, **_kwargs):
        assert chunk_ids == []
        return {}

    monkeypatch.setattr("app.services.rag_answers.read_eligible_source_batch", authorized)
    monkeypatch.setattr("app.services.rag_answers._read_related_pages", no_pages)
    result = await _service()._related_excerpts_for_jobs(
        _DB(refs), jobs=[job], user=user, subject_id=subject_id,
    )
    assert len(result[job.id]) == 2


async def test_canonical_page_reader_rechecks_authorization_inside_sql():
    user, subject_id, job, refs, _sources = _fixture()

    class Result:
        def mappings(self):
            return self

        def all(self):
            return [{"chunk_id": refs[0].chunk_id, "content": "Title\nBody"}]

    class DB:
        async def execute(self, query, params):
            sql = str(query)
            assert "eligible_subject_knowledge_chunks" in sql
            assert "JOIN users AS principal" in sql
            assert "enrollment.student_id = principal.id" in sql
            assert "subject.corpus_revision = :corpus_revision" in sql
            assert "subject.active_embedding_space_hash = :embedding_space_hash" in sql
            assert "page.uploader_id = eligible.uploader_id" in sql
            assert "page.page_number = eligible.page_number" in sql
            assert params == {
                "principal_id": user.id, "subject_id": subject_id,
                "corpus_revision": job.corpus_revision,
                "embedding_space_hash": job.embedding_space_hash,
                "chunk_ids": [refs[0].chunk_id],
            }
            return Result()

    assert await _read_related_pages(
        DB(), principal_id=user.id, subject_id=subject_id,
        corpus_revision=job.corpus_revision,
        embedding_space_hash=job.embedding_space_hash,
        chunk_ids=[refs[0].chunk_id],
    ) == {refs[0].chunk_id: "Title\nBody"}


async def test_multiple_jobs_share_one_bounded_canonical_page_read(monkeypatch):
    user, subject_id, job, refs, sources = _fixture()
    second_job = SimpleNamespace(**vars(job))
    second_job.id = uuid4()
    second_refs = [SimpleNamespace(**vars(ref)) for ref in refs]
    for ref in second_refs:
        ref.job_id = second_job.id
    refs[0].source_kind = "canonical_page"
    second_refs[1].source_kind = "canonical_page"
    pages = {chunk_id: source.content for chunk_id, source in sources.items()}
    calls = []

    async def authorized(_db, **_kwargs):
        return sources

    async def current_pages(_db, *, chunk_ids, **_kwargs):
        calls.append(chunk_ids)
        assert len(chunk_ids) <= 100
        return {chunk_id: pages[chunk_id] for chunk_id in chunk_ids}

    monkeypatch.setattr("app.services.rag_answers.read_eligible_source_batch", authorized)
    monkeypatch.setattr("app.services.rag_answers._read_related_pages", current_pages)
    result = await _service()._related_excerpts_for_jobs(
        _DB(refs + second_refs), jobs=[job, second_job], user=user,
        subject_id=subject_id,
    )
    assert set(result) == {job.id, second_job.id}
    assert len(calls) == 1
    assert set(calls[0]) == set(sources)


async def test_page_open_uses_saved_canonical_offsets_for_duplicate_quote(monkeypatch):
    user, subject_id, job, refs, _sources = _fixture()
    job.status = "completed"
    job.error_code = None
    job.answer_policy_version = "related_knowledge_v1"
    job.result_kind = "related_knowledge"
    job.answer_message_id = None
    page_text = "Same phrase. More context. Same phrase."
    quote = "Same phrase."
    later = page_text.rfind(quote)
    refs[0].source_kind = "canonical_page"
    refs[0].start_offset, refs[0].end_offset = later, later + len(quote)

    async def owned(_db, **_kwargs):
        return job

    async def excerpts(_db, **_kwargs):
        return {job.id: [RagRelatedExcerptResponse(
            excerpt_order=1, document_title="Lecture", page_number=2,
            section="Topic", source_quote=quote,
        )]}

    async def lock(_db):
        return None

    async def current_page(_db, **_kwargs):
        return {refs[0].chunk_id: page_text}

    class DB:
        async def get(self, _model, _key):
            return refs[0]

        async def scalar(self, _query):
            return SimpleNamespace(content=page_text)

    service = _service()
    monkeypatch.setattr(service, "owned_job", owned)
    monkeypatch.setattr(service, "_related_excerpts_for_jobs", excerpts)
    monkeypatch.setattr("app.services.rag_answers.acquire_knowledge_write_lock", lock)
    monkeypatch.setattr("app.services.rag_answers._read_related_pages", current_page)
    result = await service.related_page(
        DB(), subject_id=subject_id, thread_id=job.thread_id,
        job_id=job.id, excerpt_order=1, user=user,
    )
    assert (result.reference_start, result.reference_end) == (later, later + len(quote))


@pytest.mark.parametrize("mutation", ["page_missing", "page_short", "anchor_missing", "cross_subject", "too_long", "blank"])
async def test_any_canonical_page_or_anchor_drift_hides_entire_bundle(monkeypatch, mutation):
    user, subject_id, job, refs, sources = _fixture()
    pages = {key: "Title\n" + source.content for key, source in sources.items()}
    refs[0].source_kind = "canonical_page"
    refs[0].end_offset = len(pages[refs[0].chunk_id])
    if mutation == "page_missing":
        pages.pop(refs[0].chunk_id)
    elif mutation == "page_short":
        pages[refs[0].chunk_id] = "Title"
    elif mutation == "anchor_missing":
        sources.pop(refs[0].chunk_id)
    elif mutation == "cross_subject":
        refs[0].subject_id = uuid4()
    elif mutation == "too_long":
        pages[refs[0].chunk_id] = "a" * 481
        refs[0].end_offset = 481
    elif mutation == "blank":
        pages[refs[0].chunk_id] = " \n\t "
        refs[0].end_offset = 4

    async def authorized(_db, **_kwargs):
        return sources

    async def current_pages(_db, *, chunk_ids, **_kwargs):
        return pages

    monkeypatch.setattr("app.services.rag_answers.read_eligible_source_batch", authorized)
    monkeypatch.setattr("app.services.rag_answers._read_related_pages", current_pages)
    assert await _service()._related_excerpts_for_jobs(
        _DB(refs), jobs=[job], user=user, subject_id=subject_id,
    ) == {}
