"""Authorized exact-v1 hybrid retrieval for Subject Knowledge.

The database query repeats current principal, Subject, publication, revision,
and embedding-space predicates in both candidate channels.  Provider calls are
owned by :class:`WorkerKnowledgeRetrievalCoordinator`; this module deliberately
defines no HTTP route and never accepts a request-supplied vector as authority.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from typing import Mapping, Protocol, Sequence
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, Float, Integer, String, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chunking import estimate_tokens
from app.ai.embeddings import EmbeddingResponse
from app.models.user import User
from app.models.vector import EMBEDDING_DIMENSIONS


_WORD_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class ExactV1RetrievalPolicy:
    """Versioned, deterministic bounds for the initial exact-search policy."""

    policy_id: str = "hybrid_exact_v1"
    fts_configuration: str = "simple"
    max_query_chars: int = 4_000
    max_query_tokens: int = 8_192
    max_document_ids: int = 50
    max_results: int = 5
    candidate_limit_per_channel: int = 20
    context_token_limit: int = 8_192
    minimum_vector_similarity: float = 0.5
    rrf_k: int = 60
    overlap_threshold: float = 0.8
    # These opt-in switches are for isolated corpus ablations. The shipped
    # hybrid_exact_v1 policy keeps its original behavior and thresholds.
    lexical_max_terms: int = 0
    lexical_include_section: bool = False
    lexical_join_or: bool = False
    cross_document_diversity: bool = False


EXACT_V1_POLICY = ExactV1RetrievalPolicy()
SOURCE_SUFFICIENCY_RETRIEVAL_POLICY = replace(
    EXACT_V1_POLICY, policy_id="hybrid_source_sufficiency_v7", max_results=20,
)
SOURCE_NAVIGATION_RETRIEVAL_POLICY = replace(
    EXACT_V1_POLICY, policy_id="hybrid_source_navigation_v9", max_results=20,
    lexical_max_terms=12, lexical_include_section=True, lexical_join_or=True,
)


class KnowledgeRetrievalError(RuntimeError):
    """Base class for fixed, content-free retrieval failures."""

    code = "knowledge_retrieval_failed"


class KnowledgeRetrievalDisabled(KnowledgeRetrievalError):
    code = "knowledge_retrieval_disabled"

    def __init__(self) -> None:
        super().__init__("Knowledge retrieval is disabled.")


class InvalidKnowledgeRetrievalRequest(KnowledgeRetrievalError):
    code = "knowledge_retrieval_invalid_request"

    def __init__(self) -> None:
        super().__init__("Knowledge retrieval request is invalid.")


class KnowledgeScopeUnavailable(KnowledgeRetrievalError):
    code = "knowledge_scope_unavailable"

    def __init__(self) -> None:
        super().__init__("Knowledge scope is unavailable.")


class IncompatibleEmbeddingSpace(KnowledgeRetrievalError):
    code = "knowledge_embedding_space_mismatch"

    def __init__(self) -> None:
        super().__init__("Knowledge embedding space is incompatible.")


class InvalidQueryEmbedding(KnowledgeRetrievalError):
    code = "knowledge_query_embedding_invalid"

    def __init__(self) -> None:
        super().__init__("Knowledge query embedding is invalid.")


class KnowledgeSourceUnavailable(KnowledgeRetrievalError):
    code = "knowledge_source_unavailable"

    def __init__(self) -> None:
        super().__init__("Knowledge source is unavailable.")


@dataclass(frozen=True, slots=True)
class AuthorizedKnowledgeScope:
    principal_id: UUID
    subject_id: UUID
    corpus_revision: int
    embedding_space_hash: str | None
    document_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class RetrievedKnowledgeChunk:
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content_revision_id: UUID
    index_revision_id: UUID
    page_number: int
    section: str | None
    content: str
    token_count: int
    embedding_space_hash: str
    corpus_revision: int
    vector_similarity: float | None
    lexical_score: float | None
    vector_rank: int | None
    lexical_rank: int | None
    fusion_score: float


@dataclass(frozen=True, slots=True)
class ExpandedKnowledgeNeighbor:
    """An eligible adjacent chunk, with its origin kept separate from search scores."""

    chunk: RetrievedKnowledgeChunk
    anchor_chunk_id: UUID
    page_distance: int


@dataclass(frozen=True, slots=True)
class AuthorizedKnowledgeSource:
    chunk_id: UUID
    document_id: UUID
    document_title: str
    content_revision_id: UUID
    index_revision_id: UUID
    page_number: int
    section: str | None
    content: str
    token_count: int
    embedding_space_hash: str
    corpus_revision: int


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalResult:
    policy_id: str
    subject_id: UUID
    corpus_revision: int
    embedding_space_hash: str | None
    chunks: tuple[RetrievedKnowledgeChunk, ...]

    @property
    def insufficient(self) -> bool:
        return not self.chunks


class QueryEmbeddingProvider(Protocol):
    """Small worker-owned boundary implemented by the Phase 15 provider."""

    async def embed_query(self, text: str) -> EmbeddingResponse: ...


_AUTHORIZATION_SQL = text(
    """
    WITH authorized_subject AS (
        SELECT subject.id, subject.corpus_revision,
               subject.active_embedding_space_hash
        FROM subjects AS subject
        JOIN users AS principal ON principal.id = :principal_id
        WHERE subject.id = :subject_id
          AND (
            (principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
            OR
            (principal.role = 'STUDENT' AND EXISTS (
                SELECT 1
                FROM enrollments AS enrollment
                WHERE enrollment.student_id = principal.id
                  AND enrollment.subject_id = subject.id
            ))
          )
    )
    SELECT scope.corpus_revision, scope.active_embedding_space_hash,
           (
               SELECT count(*)
               FROM eligible_subject_knowledge_chunks AS eligible
               WHERE eligible.subject_id = scope.id
                 AND eligible.embedding_space_hash = scope.active_embedding_space_hash
           ) AS eligible_chunk_count,
           CASE WHEN :has_document_filter THEN (
               SELECT count(DISTINCT eligible.document_id)
               FROM eligible_subject_knowledge_chunks AS eligible
               WHERE eligible.subject_id = scope.id
                 AND eligible.embedding_space_hash = scope.active_embedding_space_hash
                 AND eligible.document_id = ANY(:document_ids)
           ) ELSE 0 END AS selected_document_count
    FROM authorized_subject AS scope
    """
).bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("has_document_filter", type_=Boolean()),
    bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
)


_RETRIEVAL_ABLATION_SQL = text(
    """
    WITH authorized_subject AS (
        SELECT subject.id, subject.corpus_revision,
               subject.active_embedding_space_hash
        FROM subjects AS subject
        JOIN users AS principal ON principal.id = :principal_id
        WHERE subject.id = :subject_id
          AND subject.corpus_revision = :corpus_revision
          AND subject.active_embedding_space_hash = :embedding_space_hash
          AND (
            (principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
            OR
            (principal.role = 'STUDENT' AND EXISTS (
                SELECT 1
                FROM enrollments AS enrollment
                WHERE enrollment.student_id = principal.id
                  AND enrollment.subject_id = subject.id
            ))
          )
    ),
    valid_subject AS (
        SELECT scope.*
        FROM authorized_subject AS scope
        WHERE NOT :has_document_filter
           OR :document_count = (
               SELECT count(DISTINCT selected.document_id)
               FROM eligible_subject_knowledge_chunks AS selected
               WHERE selected.subject_id = scope.id
                 AND selected.corpus_revision = scope.corpus_revision
                 AND selected.embedding_space_hash = scope.active_embedding_space_hash
                 AND selected.document_id = ANY(:document_ids)
           )
    ),
    vector_scored AS (
        SELECT eligible.id AS chunk_id,
               (1.0 - (eligible.embedding OPERATOR(public.<=>) :query_embedding))::double precision
                   AS vector_similarity
        FROM eligible_subject_knowledge_chunks AS eligible
        JOIN valid_subject AS scope ON scope.id = eligible.subject_id
        WHERE eligible.subject_id = :subject_id
          AND eligible.corpus_revision = :corpus_revision
          AND eligible.embedding_space_hash = :embedding_space_hash
          AND (NOT :has_document_filter OR eligible.document_id = ANY(:document_ids))
          AND (1.0 - (eligible.embedding OPERATOR(public.<=>) :query_embedding))
                >= :minimum_vector_similarity
    ),
    vector_top AS (
        SELECT chunk_id, vector_similarity
        FROM vector_scored
        ORDER BY vector_similarity DESC, chunk_id
        LIMIT :candidate_limit
    ),
    vector_ranked AS (
        SELECT chunk_id, vector_similarity,
               row_number() OVER (ORDER BY vector_similarity DESC, chunk_id)::integer
                   AS vector_rank
        FROM vector_top
    ),
    lexical_query AS (
        SELECT CASE WHEN :lexical_join_or
            THEN websearch_to_tsquery('simple'::regconfig, :lexical_query)
            ELSE plainto_tsquery('simple'::regconfig, :lexical_query)
        END AS query
    ),
    lexical_scored AS (
        SELECT eligible.id AS chunk_id,
               ts_rank_cd(
                    to_tsvector('simple'::regconfig,
                        CASE WHEN :lexical_include_section
                        THEN concat_ws(' ', eligible.section, eligible.content)
                        ELSE eligible.content END),
                   lexical.query,
                   32
               )::double precision AS lexical_score
        FROM eligible_subject_knowledge_chunks AS eligible
        JOIN valid_subject AS scope ON scope.id = eligible.subject_id
        CROSS JOIN lexical_query AS lexical
        WHERE eligible.subject_id = :subject_id
          AND eligible.corpus_revision = :corpus_revision
          AND eligible.embedding_space_hash = :embedding_space_hash
          AND (NOT :has_document_filter OR eligible.document_id = ANY(:document_ids))
          AND numnode(lexical.query) > 0
          AND to_tsvector('simple'::regconfig,
                CASE WHEN :lexical_include_section
                THEN concat_ws(' ', eligible.section, eligible.content)
                ELSE eligible.content END) @@ lexical.query
    ),
    lexical_top AS (
        SELECT chunk_id, lexical_score
        FROM lexical_scored
        ORDER BY lexical_score DESC, chunk_id
        LIMIT :candidate_limit
    ),
    lexical_ranked AS (
        SELECT chunk_id, lexical_score,
               row_number() OVER (ORDER BY lexical_score DESC, chunk_id)::integer
                   AS lexical_rank
        FROM lexical_top
    ),
    channels AS (
        SELECT chunk_id, vector_similarity, vector_rank,
               NULL::double precision AS lexical_score, NULL::integer AS lexical_rank
        FROM vector_ranked
        UNION ALL
        SELECT chunk_id, NULL::double precision, NULL::integer,
               lexical_score, lexical_rank
        FROM lexical_ranked
    ),
    fused AS (
        SELECT chunk_id,
               max(vector_similarity) AS vector_similarity,
               max(lexical_score) AS lexical_score,
               min(vector_rank) AS vector_rank,
               min(lexical_rank) AS lexical_rank,
               (
                   coalesce(sum(CASE WHEN vector_rank IS NOT NULL
                       THEN 1.0 / (:rrf_k + vector_rank) ELSE 0 END), 0)
                   + coalesce(sum(CASE WHEN lexical_rank IS NOT NULL
                       THEN 1.0 / (:rrf_k + lexical_rank) ELSE 0 END), 0)
               )::double precision AS fusion_score
        FROM channels
        GROUP BY chunk_id
    )
    SELECT scope.corpus_revision, scope.active_embedding_space_hash,
           eligible.id AS chunk_id, eligible.document_id,
           eligible.document_title, eligible.content_revision_id,
           eligible.index_revision_id, eligible.page_number, eligible.section,
           eligible.content, eligible.token_count, eligible.embedding_space_hash,
           fused.vector_similarity, fused.lexical_score,
           fused.vector_rank, fused.lexical_rank, fused.fusion_score
    FROM valid_subject AS scope
    LEFT JOIN fused ON true
    LEFT JOIN eligible_subject_knowledge_chunks AS eligible
      ON eligible.id = fused.chunk_id
     AND eligible.subject_id = scope.id
     AND eligible.corpus_revision = scope.corpus_revision
     AND eligible.embedding_space_hash = scope.active_embedding_space_hash
     AND (NOT :has_document_filter OR eligible.document_id = ANY(:document_ids))
    ORDER BY fused.fusion_score DESC NULLS LAST,
             least(coalesce(fused.vector_rank, 2147483647),
                   coalesce(fused.lexical_rank, 2147483647)),
             coalesce(fused.vector_rank, 2147483647),
             coalesce(fused.lexical_rank, 2147483647),
             eligible.document_id, eligible.page_number,
             eligible.chunk_index, eligible.id
    """
).bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("corpus_revision", type_=BigInteger()),
    bindparam("embedding_space_hash", type_=String(64)),
    bindparam("has_document_filter", type_=Boolean()),
    bindparam("document_count", type_=Integer()),
    bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
    bindparam("query_embedding", type_=Vector(EMBEDDING_DIMENSIONS)),
    bindparam("minimum_vector_similarity", type_=Float()),
    bindparam("candidate_limit", type_=Integer()),
    bindparam("rrf_k", type_=Integer()),
    bindparam("lexical_query", type_=String()),
    bindparam("lexical_include_section", type_=Boolean()),
    bindparam("lexical_join_or", type_=Boolean()),
)

# Preserve the exact shipped SQL shape for hybrid_exact_v1. In particular its
# plain content FTS expression stays indexable without a parameterized CASE.
# The optional section/OR statement is selected only for explicit ablations.
_EXACT_QUERY_FRAGMENT = """SELECT CASE WHEN :lexical_join_or
            THEN websearch_to_tsquery('simple'::regconfig, :lexical_query)
            ELSE plainto_tsquery('simple'::regconfig, :lexical_query)
        END AS query"""
_SECTION_VECTOR_FRAGMENT = """to_tsvector('simple'::regconfig,
                        CASE WHEN :lexical_include_section
                        THEN concat_ws(' ', eligible.section, eligible.content)
                        ELSE eligible.content END)"""
_SECTION_MATCH_FRAGMENT = """to_tsvector('simple'::regconfig,
                CASE WHEN :lexical_include_section
                THEN concat_ws(' ', eligible.section, eligible.content)
                ELSE eligible.content END)"""
_ablation_sql_text = _RETRIEVAL_ABLATION_SQL.text
if (
    _ablation_sql_text.count(_EXACT_QUERY_FRAGMENT) != 1
    or _ablation_sql_text.count(_SECTION_VECTOR_FRAGMENT) != 1
    or _ablation_sql_text.count(_SECTION_MATCH_FRAGMENT) != 1
):
    raise RuntimeError("Retrieval SQL policy fragments are unavailable")
_RETRIEVAL_SQL = text(
    _ablation_sql_text
    .replace(
        _EXACT_QUERY_FRAGMENT,
        "SELECT plainto_tsquery('simple'::regconfig, :lexical_query) AS query",
    )
    .replace(_SECTION_VECTOR_FRAGMENT, "to_tsvector('simple'::regconfig, eligible.content)")
    .replace(_SECTION_MATCH_FRAGMENT, "to_tsvector('simple'::regconfig, eligible.content)")
).bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("corpus_revision", type_=BigInteger()),
    bindparam("embedding_space_hash", type_=String(64)),
    bindparam("has_document_filter", type_=Boolean()),
    bindparam("document_count", type_=Integer()),
    bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
    bindparam("query_embedding", type_=Vector(EMBEDDING_DIMENSIONS)),
    bindparam("minimum_vector_similarity", type_=Float()),
    bindparam("candidate_limit", type_=Integer()),
    bindparam("rrf_k", type_=Integer()),
    bindparam("lexical_query", type_=String()),
)


_LEXICAL_ONLY_SQL = text(
    """
    WITH authorized_subject AS (
        SELECT subject.id, subject.corpus_revision, subject.active_embedding_space_hash
        FROM subjects AS subject JOIN users AS principal ON principal.id = :principal_id
        WHERE subject.id = :subject_id
          AND subject.corpus_revision = :corpus_revision
          AND subject.active_embedding_space_hash = :embedding_space_hash
          AND ((principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
               OR (principal.role = 'STUDENT' AND EXISTS (
                   SELECT 1 FROM enrollments AS enrollment
                   WHERE enrollment.student_id = principal.id AND enrollment.subject_id = subject.id)))
    ), valid_subject AS (
        SELECT scope.* FROM authorized_subject AS scope
        WHERE NOT :has_document_filter OR :document_count = (
            SELECT count(DISTINCT selected.document_id)
            FROM eligible_subject_knowledge_chunks AS selected
            WHERE selected.subject_id = scope.id AND selected.corpus_revision = scope.corpus_revision
              AND selected.embedding_space_hash = scope.active_embedding_space_hash
              AND selected.document_id = ANY(:document_ids))
    ), lexical_query AS (
        SELECT websearch_to_tsquery('simple'::regconfig, :lexical_query) AS query
    ), lexical_scored AS (
        SELECT eligible.id AS chunk_id,
               ts_rank_cd(to_tsvector('simple'::regconfig,
                   concat_ws(' ', eligible.section, eligible.content)), lexical.query, 32)::double precision
                   AS lexical_score
        FROM eligible_subject_knowledge_chunks AS eligible
        JOIN valid_subject AS scope ON scope.id = eligible.subject_id
        CROSS JOIN lexical_query AS lexical
        WHERE eligible.subject_id = :subject_id AND eligible.corpus_revision = :corpus_revision
          AND eligible.embedding_space_hash = :embedding_space_hash
          AND (NOT :has_document_filter OR eligible.document_id = ANY(:document_ids))
          AND numnode(lexical.query) > 0
          AND to_tsvector('simple'::regconfig,
                  concat_ws(' ', eligible.section, eligible.content)) @@ lexical.query
    ), lexical_top AS (
        SELECT * FROM lexical_scored ORDER BY lexical_score DESC, chunk_id LIMIT :candidate_limit
    ), lexical_ranked AS (
        SELECT chunk_id, lexical_score,
               row_number() OVER (ORDER BY lexical_score DESC, chunk_id)::integer AS lexical_rank
        FROM lexical_top
    )
    SELECT scope.corpus_revision, scope.active_embedding_space_hash,
           eligible.id AS chunk_id, eligible.document_id, eligible.document_title,
           eligible.content_revision_id, eligible.index_revision_id, eligible.page_number,
           eligible.section, eligible.content, eligible.token_count, eligible.embedding_space_hash,
           NULL::double precision AS vector_similarity, NULL::integer AS vector_rank,
           lexical.lexical_score, lexical.lexical_rank,
           (1.0 / (:rrf_k + lexical.lexical_rank))::double precision AS fusion_score
    FROM valid_subject AS scope LEFT JOIN lexical_ranked AS lexical ON true
    LEFT JOIN eligible_subject_knowledge_chunks AS eligible
      ON eligible.id = lexical.chunk_id AND eligible.subject_id = scope.id
     AND eligible.corpus_revision = scope.corpus_revision
     AND eligible.embedding_space_hash = scope.active_embedding_space_hash
     AND (NOT :has_document_filter OR eligible.document_id = ANY(:document_ids))
    ORDER BY lexical.lexical_rank NULLS LAST, eligible.document_id, eligible.page_number, eligible.id
    """
).bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("corpus_revision", type_=BigInteger()),
    bindparam("embedding_space_hash", type_=String(64)),
    bindparam("has_document_filter", type_=Boolean()),
    bindparam("document_count", type_=Integer()),
    bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
    bindparam("candidate_limit", type_=Integer()),
    bindparam("rrf_k", type_=Integer()),
    bindparam("lexical_query", type_=String()),
)


_SOURCE_SQL = text(
    """
    WITH authorized_subject AS (
        SELECT subject.id, subject.corpus_revision,
               subject.active_embedding_space_hash
        FROM subjects AS subject
        JOIN users AS principal ON principal.id = :principal_id
        WHERE subject.id = :subject_id
          AND (
            (principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
            OR
            (principal.role = 'STUDENT' AND EXISTS (
                SELECT 1
                FROM enrollments AS enrollment
                WHERE enrollment.student_id = principal.id
                  AND enrollment.subject_id = subject.id
            ))
          )
    )
    SELECT eligible.id AS chunk_id, eligible.document_id,
           eligible.document_title, eligible.content_revision_id,
           eligible.index_revision_id, eligible.page_number, eligible.section,
           eligible.content, eligible.token_count, eligible.embedding_space_hash,
           eligible.corpus_revision
    FROM eligible_subject_knowledge_chunks AS eligible
    JOIN authorized_subject AS scope
      ON scope.id = eligible.subject_id
     AND scope.corpus_revision = eligible.corpus_revision
     AND scope.active_embedding_space_hash = eligible.embedding_space_hash
    WHERE eligible.subject_id = :subject_id
      AND eligible.id = ANY(:chunk_ids)
      AND (NOT :has_document_filter OR eligible.document_id = ANY(:document_ids))
    ORDER BY eligible.document_id, eligible.page_number,
             eligible.chunk_index, eligible.id
    """
).bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("chunk_ids", type_=ARRAY(PGUUID(as_uuid=True))),
    bindparam("has_document_filter", type_=Boolean()),
    bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
)


_NEIGHBOR_SQL = text(
    """
    WITH authorized_subject AS (
        SELECT subject.id, subject.corpus_revision, subject.active_embedding_space_hash
        FROM subjects AS subject
        JOIN users AS principal ON principal.id = :principal_id
        WHERE subject.id = :subject_id
          AND subject.corpus_revision = :corpus_revision
          AND subject.active_embedding_space_hash = :embedding_space_hash
          AND (
            (principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
            OR (principal.role = 'STUDENT' AND EXISTS (
                SELECT 1 FROM enrollments AS enrollment
                WHERE enrollment.student_id = principal.id
                  AND enrollment.subject_id = subject.id
            ))
          )
    ),
    supplied_anchor AS (
        SELECT id, ordinal
        FROM unnest(:anchor_ids) WITH ORDINALITY AS supplied(id, ordinal)
    ),
    valid_anchor AS (
        SELECT anchor.id, supplied.ordinal, anchor.document_id,
               anchor.content_revision_id, anchor.index_revision_id,
               anchor.page_number, anchor.embedding_space_hash
        FROM supplied_anchor AS supplied
        JOIN eligible_subject_knowledge_chunks AS anchor ON anchor.id = supplied.id
        JOIN authorized_subject AS scope ON scope.id = anchor.subject_id
        WHERE anchor.subject_id = :subject_id
          AND anchor.corpus_revision = :corpus_revision
          AND anchor.embedding_space_hash = :embedding_space_hash
          AND (NOT :has_document_filter OR anchor.document_id = ANY(:document_ids))
    ),
    complete_anchor_scope AS (
        SELECT 1 WHERE (SELECT count(*) FROM valid_anchor) = :anchor_count
    ),
    eligible_neighbors AS (
        SELECT neighbor.id AS chunk_id, neighbor.document_id, neighbor.document_title,
               neighbor.content_revision_id, neighbor.index_revision_id,
               neighbor.page_number, neighbor.section, neighbor.content,
               neighbor.token_count, neighbor.embedding_space_hash,
               neighbor.corpus_revision, neighbor.chunk_index,
               anchor.id AS anchor_chunk_id, anchor.ordinal AS anchor_ordinal,
               abs(neighbor.page_number - anchor.page_number) AS page_distance,
               row_number() OVER (
                   PARTITION BY neighbor.id
                   ORDER BY abs(neighbor.page_number - anchor.page_number),
                            anchor.ordinal, anchor.id
               ) AS duplicate_rank
        FROM valid_anchor AS anchor
        JOIN complete_anchor_scope ON true
        JOIN eligible_subject_knowledge_chunks AS neighbor
          ON neighbor.subject_id = :subject_id
         AND neighbor.document_id = anchor.document_id
         AND neighbor.content_revision_id = anchor.content_revision_id
         AND neighbor.index_revision_id = anchor.index_revision_id
         AND neighbor.embedding_space_hash = anchor.embedding_space_hash
         AND neighbor.corpus_revision = :corpus_revision
         AND abs(neighbor.page_number - anchor.page_number) <= :radius
        WHERE neighbor.id <> ALL(:anchor_ids)
          AND neighbor.token_count <= :max_tokens
          AND (NOT :has_document_filter OR neighbor.document_id = ANY(:document_ids))
    )
    SELECT chunk_id, document_id, document_title, content_revision_id,
           index_revision_id, page_number, section, content, token_count,
           embedding_space_hash, corpus_revision, anchor_chunk_id, page_distance
    FROM eligible_neighbors
    WHERE duplicate_rank = 1
    ORDER BY page_distance, anchor_ordinal, page_number, chunk_index, chunk_id
    LIMIT :candidate_limit
    """
).bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("corpus_revision", type_=BigInteger()),
    bindparam("embedding_space_hash", type_=String(64)),
    bindparam("anchor_ids", type_=ARRAY(PGUUID(as_uuid=True))),
    bindparam("has_document_filter", type_=Boolean()),
    bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
    bindparam("anchor_count", type_=Integer()),
    bindparam("radius", type_=Integer()),
    bindparam("max_tokens", type_=Integer()),
    bindparam("candidate_limit", type_=Integer()),
)


_SOURCE_PAGE_SQL = text(
    r"""
    WITH authorized_subject AS (
        SELECT subject.id, subject.corpus_revision, subject.active_embedding_space_hash
        FROM subjects AS subject
        JOIN users AS principal ON principal.id = :principal_id
        WHERE subject.id = :subject_id
          AND subject.corpus_revision = :corpus_revision
          AND subject.active_embedding_space_hash = :embedding_space_hash
          AND (
            (principal.role = 'INSTRUCTOR' AND subject.instructor_id = principal.id)
            OR (principal.role = 'STUDENT' AND EXISTS (
                SELECT 1 FROM enrollments AS enrollment
                WHERE enrollment.student_id = principal.id
                  AND enrollment.subject_id = subject.id
            ))
          )
    ),
    supplied_anchor AS (
        SELECT id, ordinal FROM unnest(:chunk_ids) WITH ORDINALITY AS supplied(id, ordinal)
    ),
    eligible_page AS (
        SELECT page.id AS page_id, page.document_id, page.content_revision_id,
               page.page_number, page.content, min(supplied.ordinal) AS ordinal,
               array_agg(anchor.id ORDER BY supplied.ordinal) AS chunk_ids
        FROM supplied_anchor AS supplied
        JOIN eligible_subject_knowledge_chunks AS anchor ON anchor.id = supplied.id
        JOIN authorized_subject AS scope
          ON scope.id = anchor.subject_id
         AND scope.corpus_revision = anchor.corpus_revision
         AND scope.active_embedding_space_hash = anchor.embedding_space_hash
        JOIN subject_document_pages AS page
          ON page.subject_id = anchor.subject_id
         AND page.document_id = anchor.document_id
         AND page.content_revision_id = anchor.content_revision_id
         AND page.page_number = anchor.page_number
        WHERE anchor.subject_id = :subject_id
          AND (NOT :has_document_filter OR anchor.document_id = ANY(:document_ids))
        GROUP BY page.id, page.document_id, page.content_revision_id, page.page_number, page.content
    ),
    estimated_page AS (
        SELECT eligible_page.*,
               greatest(1, ceil(length(normalize(content, NFKC)) / 3.0),
                        ceil(octet_length(normalize(content, NFKC)) / 4.0),
                        (SELECT count(*) FROM regexp_matches(normalize(content, NFKC),
                                                            '\w+|[^\w\s]', 'g')))::integer AS page_tokens
        FROM eligible_page
        WHERE length(content) > 0
          AND length(content) <= :max_tokens * 3
          AND octet_length(content) <= :max_tokens * 4
    ),
    bounded_page AS (
        SELECT estimated_page.*,
               row_number() OVER (ORDER BY ordinal, page_id) AS page_rank,
               sum(page_tokens) OVER (ORDER BY ordinal, page_id) AS cumulative_tokens
        FROM estimated_page WHERE page_tokens <= :max_tokens
    )
    SELECT chunk_ids, document_id, content_revision_id, page_number, content, page_tokens
    FROM bounded_page
    WHERE page_rank <= :max_pages AND cumulative_tokens <= :max_tokens
    ORDER BY ordinal, page_id
    """
).bindparams(
    bindparam("principal_id", type_=PGUUID(as_uuid=True)),
    bindparam("subject_id", type_=PGUUID(as_uuid=True)),
    bindparam("corpus_revision", type_=BigInteger()),
    bindparam("embedding_space_hash", type_=String(64)),
    bindparam("chunk_ids", type_=ARRAY(PGUUID(as_uuid=True))),
    bindparam("has_document_filter", type_=Boolean()),
    bindparam("document_ids", type_=ARRAY(PGUUID(as_uuid=True))),
    bindparam("max_pages", type_=Integer()),
    bindparam("max_tokens", type_=Integer()),
)


async def read_eligible_source_batch(
    db: AsyncSession,
    *,
    principal_id: UUID,
    subject_id: UUID,
    chunk_ids: Sequence[UUID],
) -> dict[UUID, AuthorizedKnowledgeSource]:
    """Read at most 100 current sources with authorization inside SQL.

    Missing or stale rows are omitted so a caller can hide each complete
    multi-excerpt bundle. This never performs retrieval or a provider call.
    """

    try:
        normalized_ids = tuple(sorted(set(chunk_ids), key=str))
    except (TypeError, ValueError):
        raise InvalidKnowledgeRetrievalRequest() from None
    if (
        len(normalized_ids) > 100
        or any(not isinstance(chunk_id, UUID) for chunk_id in normalized_ids)
    ):
        raise InvalidKnowledgeRetrievalRequest()
    if not normalized_ids:
        return {}
    result = await db.execute(_SOURCE_SQL, {
        "principal_id": principal_id,
        "subject_id": subject_id,
        "chunk_ids": list(normalized_ids),
        "has_document_filter": False,
        "document_ids": [],
    })
    return {
        row["chunk_id"]: AuthorizedKnowledgeSource(
            chunk_id=row["chunk_id"], document_id=row["document_id"],
            document_title=row["document_title"],
            content_revision_id=row["content_revision_id"],
            index_revision_id=row["index_revision_id"],
            page_number=row["page_number"], section=row["section"],
            content=row["content"], token_count=row["token_count"],
            embedding_space_hash=row["embedding_space_hash"],
            corpus_revision=int(row["corpus_revision"]),
        )
        for row in result.mappings().all()
    }


def reciprocal_rank_score(
    vector_rank: int | None,
    lexical_rank: int | None,
    *,
    k: int = EXACT_V1_POLICY.rrf_k,
) -> float:
    """Return an RRF rank score; it is not a confidence or probability."""

    if k <= 0 or any(rank is not None and rank <= 0 for rank in (vector_rank, lexical_rank)):
        raise ValueError("RRF ranks and constant must be positive")
    return sum(1.0 / (k + rank) for rank in (vector_rank, lexical_rank) if rank is not None)


def _normalize_request(
    query: str,
    document_ids: Sequence[UUID] | None,
    limit: int,
    policy: ExactV1RetrievalPolicy,
) -> tuple[str, tuple[UUID, ...], int]:
    if not isinstance(query, str):
        raise InvalidKnowledgeRetrievalRequest()
    normalized_query = query.strip()
    if (
        not normalized_query
        or "\x00" in normalized_query
        or len(normalized_query) > policy.max_query_chars
        or estimate_tokens(normalized_query) > policy.max_query_tokens
        or not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= policy.max_results
    ):
        raise InvalidKnowledgeRetrievalRequest()

    try:
        normalized_documents = tuple(sorted(set(document_ids or ()), key=str))
    except (TypeError, ValueError):
        raise InvalidKnowledgeRetrievalRequest() from None
    if (
        len(normalized_documents) > policy.max_document_ids
        or any(not isinstance(document_id, UUID) for document_id in normalized_documents)
    ):
        raise InvalidKnowledgeRetrievalRequest()
    return normalized_query, normalized_documents, limit


def _validate_embedding(values: Sequence[float]) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)):
        raise InvalidQueryEmbedding()
    try:
        vector = tuple(float(value) for value in values)
    except (TypeError, ValueError, OverflowError):
        raise InvalidQueryEmbedding() from None
    if (
        len(vector) != EMBEDDING_DIMENSIONS
        or not all(math.isfinite(value) for value in vector)
        or not any(value != 0 for value in vector)
    ):
        raise InvalidQueryEmbedding()
    return vector


def _content_terms(content: str) -> frozenset[str]:
    return frozenset(match.group(0).casefold() for match in _WORD_RE.finditer(content))


_LEXICAL_STOP_WORDS = frozenset({
    "a", "an", "and", "are", "can", "do", "does", "for", "from", "how", "in",
    "is", "of", "on", "or", "the", "to", "what", "when", "where", "which",
    "who", "why", "with",
})


def bounded_lexical_query(query: str, max_terms: int) -> str:
    """Keep a small deterministic set of meaningful terms for an ablation."""

    if max_terms <= 0:
        raise ValueError("Lexical term bound must be positive")
    words = [match.group(0).casefold() for match in _WORD_RE.finditer(query)]
    retained: list[str] = []
    for word in words:
        if word in _LEXICAL_STOP_WORDS or word in retained:
            continue
        retained.append(word)
        if len(retained) == max_terms:
            break
    return " ".join(retained or words[:max_terms])


def _is_overlapping(
    candidate: RetrievedKnowledgeChunk,
    retained: RetrievedKnowledgeChunk,
    threshold: float,
    *,
    cross_document_diversity: bool = False,
) -> bool:
    if not cross_document_diversity:
        if (
            candidate.document_id != retained.document_id
            or candidate.content_revision_id != retained.content_revision_id
            or candidate.page_number != retained.page_number
        ):
            return False
    candidate_text = " ".join(candidate.content.casefold().split())
    retained_text = " ".join(retained.content.casefold().split())
    if candidate_text == retained_text:
        return True
    candidate_terms, retained_terms = _content_terms(candidate_text), _content_terms(retained_text)
    if not candidate_terms or not retained_terms:
        return False
    containment = len(candidate_terms & retained_terms) / min(len(candidate_terms), len(retained_terms))
    return containment >= threshold


def select_bounded_candidates(
    candidates: Sequence[RetrievedKnowledgeChunk],
    *,
    limit: int,
    policy: ExactV1RetrievalPolicy = EXACT_V1_POLICY,
) -> tuple[RetrievedKnowledgeChunk, ...]:
    """Apply deterministic overlap and context bounds to authorized rows."""

    if not 1 <= limit <= policy.max_results:
        raise InvalidKnowledgeRetrievalRequest()
    retained: list[RetrievedKnowledgeChunk] = []
    retained_tokens = 0
    for candidate in candidates:
        if candidate.token_count <= 0 or candidate.token_count > policy.context_token_limit:
            continue
        if retained_tokens + candidate.token_count > policy.context_token_limit:
            continue
        if any(
            _is_overlapping(
                candidate, prior, policy.overlap_threshold,
                cross_document_diversity=policy.cross_document_diversity,
            )
            for prior in retained
        ):
            continue
        retained.append(candidate)
        retained_tokens += candidate.token_count
        if len(retained) == limit:
            break
    return tuple(retained)


class KnowledgeRetriever:
    """Reusable retriever bound to an authorized principal/Subject snapshot."""

    def __init__(
        self,
        db: AsyncSession,
        scope: AuthorizedKnowledgeScope,
        query: str,
        limit: int,
        policy: ExactV1RetrievalPolicy,
    ) -> None:
        self._db = db
        self.scope = scope
        self._query = query
        self._limit = limit
        self.policy = policy

    @classmethod
    async def authorize(
        cls,
        db: AsyncSession,
        *,
        principal: User,
        subject_id: UUID,
        query: str,
        document_ids: Sequence[UUID] | None = None,
        limit: int = 5,
        policy: ExactV1RetrievalPolicy = EXACT_V1_POLICY,
    ) -> KnowledgeRetriever:
        normalized_query, normalized_documents, normalized_limit = _normalize_request(
            query, document_ids, limit, policy
        )
        result = await db.execute(
            _AUTHORIZATION_SQL,
            {
                "principal_id": principal.id,
                "subject_id": subject_id,
                "has_document_filter": bool(normalized_documents),
                "document_ids": list(normalized_documents),
            },
        )
        row = result.mappings().one_or_none()
        if row is None:
            raise KnowledgeScopeUnavailable()
        if int(row["eligible_chunk_count"]) <= 0:
            raise KnowledgeScopeUnavailable()
        if normalized_documents and row["selected_document_count"] != len(normalized_documents):
            raise KnowledgeScopeUnavailable()
        scope = AuthorizedKnowledgeScope(
            principal_id=principal.id,
            subject_id=subject_id,
            corpus_revision=int(row["corpus_revision"]),
            embedding_space_hash=row["active_embedding_space_hash"],
            document_ids=normalized_documents,
        )
        return cls(db, scope, normalized_query, normalized_limit, policy)

    def empty_result(self) -> KnowledgeRetrievalResult:
        return KnowledgeRetrievalResult(
            policy_id=self.policy.policy_id,
            subject_id=self.scope.subject_id,
            corpus_revision=self.scope.corpus_revision,
            embedding_space_hash=self.scope.embedding_space_hash,
            chunks=(),
        )

    async def retrieve(
        self,
        query_embedding: Sequence[float],
        *,
        embedding_space_hash: str,
    ) -> KnowledgeRetrievalResult:
        if self.scope.embedding_space_hash is None:
            return self.empty_result()
        if embedding_space_hash != self.scope.embedding_space_hash:
            raise IncompatibleEmbeddingSpace()
        vector = _validate_embedding(query_embedding)
        bounded_terms = (
            bounded_lexical_query(self._query, self.policy.lexical_max_terms)
            if self.policy.lexical_max_terms
            else self._query
        )
        ablation = self.policy.lexical_join_or or self.policy.lexical_include_section
        result = await self._db.execute(
            _RETRIEVAL_ABLATION_SQL if ablation else _RETRIEVAL_SQL,
            {
                "principal_id": self.scope.principal_id,
                "subject_id": self.scope.subject_id,
                "corpus_revision": self.scope.corpus_revision,
                "embedding_space_hash": embedding_space_hash,
                "has_document_filter": bool(self.scope.document_ids),
                "document_count": len(self.scope.document_ids),
                "document_ids": list(self.scope.document_ids),
                "query_embedding": list(vector),
                "minimum_vector_similarity": self.policy.minimum_vector_similarity,
                "candidate_limit": self.policy.candidate_limit_per_channel,
                "rrf_k": self.policy.rrf_k,
                "lexical_query": (
                    " OR ".join(bounded_terms.split())
                    if self.policy.lexical_join_or
                    else bounded_terms
                ),
                "lexical_include_section": self.policy.lexical_include_section,
                "lexical_join_or": self.policy.lexical_join_or,
            },
        )
        rows = result.mappings().all()
        return self._bounded_result(rows, embedding_space_hash=embedding_space_hash)

    def _bounded_result(self, rows: Sequence[Mapping[str, object]], *, embedding_space_hash: str) -> KnowledgeRetrievalResult:
        if not rows:
            raise KnowledgeScopeUnavailable()
        candidates = tuple(
            RetrievedKnowledgeChunk(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                document_title=row["document_title"],
                content_revision_id=row["content_revision_id"],
                index_revision_id=row["index_revision_id"],
                page_number=row["page_number"],
                section=row["section"],
                content=row["content"],
                token_count=row["token_count"],
                embedding_space_hash=row["embedding_space_hash"],
                corpus_revision=int(row["corpus_revision"]),
                vector_similarity=row["vector_similarity"],
                lexical_score=row["lexical_score"],
                vector_rank=row["vector_rank"],
                lexical_rank=row["lexical_rank"],
                fusion_score=row["fusion_score"],
            )
            for row in rows
            if row["chunk_id"] is not None
        )
        selected = select_bounded_candidates(candidates, limit=self._limit, policy=self.policy)
        return KnowledgeRetrievalResult(
            policy_id=self.policy.policy_id,
            subject_id=self.scope.subject_id,
            corpus_revision=self.scope.corpus_revision,
            embedding_space_hash=embedding_space_hash,
            chunks=selected,
        )

    async def retrieve_lexical(self) -> KnowledgeRetrievalResult:
        """Search authorized current Knowledge locally after one embedding outage.

        This channel creates no vector, sends no data to a provider and inherits
        all publication, ownership/enrollment, revision and space predicates.
        It is available only to the immutable navigation policy.
        """

        if self.policy.policy_id != SOURCE_NAVIGATION_RETRIEVAL_POLICY.policy_id:
            raise InvalidKnowledgeRetrievalRequest()
        if self.scope.embedding_space_hash is None:
            return self.empty_result()
        terms = bounded_lexical_query(self._query, self.policy.lexical_max_terms)
        result = await self._db.execute(_LEXICAL_ONLY_SQL, {
            "principal_id": self.scope.principal_id,
            "subject_id": self.scope.subject_id,
            "corpus_revision": self.scope.corpus_revision,
            "embedding_space_hash": self.scope.embedding_space_hash,
            "has_document_filter": bool(self.scope.document_ids),
            "document_count": len(self.scope.document_ids),
            "document_ids": list(self.scope.document_ids),
            "candidate_limit": self.policy.candidate_limit_per_channel,
            "rrf_k": self.policy.rrf_k,
            "lexical_query": " OR ".join(terms.split()),
        })
        return self._bounded_result(result.mappings().all(),
                                    embedding_space_hash=self.scope.embedding_space_hash)

    async def expand_source_neighbors(
        self,
        anchors: Sequence[RetrievedKnowledgeChunk],
        *,
        radius: int = 1,
        max_chunks: int = 30,
        max_pages: int = 12,
        max_tokens: int = 8_192,
    ) -> tuple[ExpandedKnowledgeNeighbor, ...]:
        """Read bounded eligible siblings and nearby pages without another embedding.

        The caps include the supplied anchors. This method returns only new
        chunks; their lexical/vector ranks are deliberately unset. Callers
        must still reauthorize any chosen exact source before persistence.
        """

        if (
            radius not in (1, 2)
            or not 1 <= max_chunks <= 30
            or not 1 <= max_pages <= 12
            or not 1 <= max_tokens <= 8_192
            or len(anchors) > self.policy.max_results
            or any(not isinstance(anchor, RetrievedKnowledgeChunk) for anchor in anchors)
        ):
            raise InvalidKnowledgeRetrievalRequest()
        if not anchors:
            return ()
        anchor_by_id = {anchor.chunk_id: anchor for anchor in anchors}
        if len(anchor_by_id) != len(anchors):
            raise InvalidKnowledgeRetrievalRequest()
        anchor_pages = {(anchor.document_id, anchor.page_number) for anchor in anchors}
        if len(anchors) > max_chunks or len(anchor_pages) > max_pages:
            return ()
        remaining_tokens = max_tokens - sum(anchor.token_count for anchor in anchors)
        if remaining_tokens <= 0:
            return ()

        # The first read rejects a stale or foreign anchor rather than using
        # caller-supplied document/page coordinates as retrieval authority.
        current = await self.read_current_sources(tuple(anchor_by_id))
        if any(
            source.document_id != anchor_by_id[source.chunk_id].document_id
            or source.content_revision_id != anchor_by_id[source.chunk_id].content_revision_id
            or source.index_revision_id != anchor_by_id[source.chunk_id].index_revision_id
            or source.page_number != anchor_by_id[source.chunk_id].page_number
            or source.content != anchor_by_id[source.chunk_id].content
            or source.token_count != anchor_by_id[source.chunk_id].token_count
            or anchor_by_id[source.chunk_id].embedding_space_hash != self.scope.embedding_space_hash
            or anchor_by_id[source.chunk_id].corpus_revision != self.scope.corpus_revision
            or source.embedding_space_hash != self.scope.embedding_space_hash
            or source.corpus_revision != self.scope.corpus_revision
            for source in current
        ):
            raise KnowledgeSourceUnavailable()
        result = await self._db.execute(_NEIGHBOR_SQL, {
            "principal_id": self.scope.principal_id,
            "subject_id": self.scope.subject_id,
            "corpus_revision": self.scope.corpus_revision,
            "embedding_space_hash": self.scope.embedding_space_hash,
            "anchor_ids": [anchor.chunk_id for anchor in anchors],
            "anchor_count": len(anchors),
            "has_document_filter": bool(self.scope.document_ids),
            "document_ids": list(self.scope.document_ids),
            "radius": radius,
            "max_tokens": remaining_tokens,
            "candidate_limit": max_chunks - len(anchors),
        })
        pages = set(anchor_pages)
        neighbors: list[ExpandedKnowledgeNeighbor] = []
        for row in result.mappings():
            page = (row["document_id"], row["page_number"])
            tokens = int(row["token_count"])
            if (page not in pages and len(pages) >= max_pages) or tokens > remaining_tokens:
                continue
            pages.add(page)
            remaining_tokens -= tokens
            chunk = RetrievedKnowledgeChunk(
                chunk_id=row["chunk_id"], document_id=row["document_id"],
                document_title=row["document_title"],
                content_revision_id=row["content_revision_id"],
                index_revision_id=row["index_revision_id"],
                page_number=row["page_number"], section=row["section"],
                content=row["content"], token_count=tokens,
                embedding_space_hash=row["embedding_space_hash"],
                corpus_revision=int(row["corpus_revision"]),
                vector_similarity=None, lexical_score=None,
                vector_rank=None, lexical_rank=None, fusion_score=0.0,
            )
            neighbors.append(ExpandedKnowledgeNeighbor(
                chunk=chunk, anchor_chunk_id=row["anchor_chunk_id"],
                page_distance=int(row["page_distance"]),
            ))
        return tuple(neighbors)

    async def read_current_source_pages(
        self, chunk_ids: Sequence[UUID], *, max_pages: int = 12, max_tokens: int = 8_192,
    ) -> dict[UUID, str]:
        """Read bounded current canonical pages derived from eligible anchor IDs.

        Authorization, publication/readiness, current revisions, selected
        documents and the pinned corpus/space are enforced in SQL. A page is
        returned once and mapped to every requested anchor on that page. Missing,
        stale or over-budget pages are omitted for callers to fail closed.
        No source content is synthesized, copied to references or sent remotely.
        """

        try:
            normalized_ids = tuple(dict.fromkeys(chunk_ids))
        except (TypeError, ValueError):
            raise InvalidKnowledgeRetrievalRequest() from None
        if (len(normalized_ids) > 30
            or any(not isinstance(chunk_id, UUID) for chunk_id in normalized_ids)
            or isinstance(max_pages, bool) or not isinstance(max_pages, int)
            or not 1 <= max_pages <= 12
            or isinstance(max_tokens, bool) or not isinstance(max_tokens, int)
            or not 1 <= max_tokens <= 8_192):
            raise InvalidKnowledgeRetrievalRequest()
        if not normalized_ids:
            return {}
        result = await self._db.execute(_SOURCE_PAGE_SQL, {
            "principal_id": self.scope.principal_id,
            "subject_id": self.scope.subject_id,
            "corpus_revision": self.scope.corpus_revision,
            "embedding_space_hash": self.scope.embedding_space_hash,
            "chunk_ids": list(normalized_ids),
            "has_document_filter": bool(self.scope.document_ids),
            "document_ids": list(self.scope.document_ids),
            "max_pages": max_pages, "max_tokens": max_tokens,
        })
        pages: dict[UUID, str] = {}
        seen_pages: set[tuple[UUID, UUID, int]] = set()
        remaining = max_tokens
        requested = set(normalized_ids)
        for row in result.mappings():
            identity = (row["document_id"], row["content_revision_id"], row["page_number"])
            if identity in seen_pages or len(seen_pages) >= max_pages:
                continue
            content = row["content"]
            tokens = estimate_tokens(content)
            if not content or tokens > remaining:
                continue
            seen_pages.add(identity)
            remaining -= tokens
            for chunk_id in row["chunk_ids"]:
                if chunk_id in requested:
                    pages[chunk_id] = content
        return pages

    async def read_current_sources(
        self,
        chunk_ids: Sequence[UUID],
    ) -> tuple[AuthorizedKnowledgeSource, ...]:
        try:
            normalized_ids = tuple(sorted(set(chunk_ids), key=str))
        except (TypeError, ValueError):
            raise InvalidKnowledgeRetrievalRequest() from None
        if (
            not normalized_ids
            or len(normalized_ids) > self.policy.max_results
            or any(not isinstance(chunk_id, UUID) for chunk_id in normalized_ids)
        ):
            raise InvalidKnowledgeRetrievalRequest()
        result = await self._db.execute(
            _SOURCE_SQL,
            {
                "principal_id": self.scope.principal_id,
                "subject_id": self.scope.subject_id,
                "chunk_ids": list(normalized_ids),
                "has_document_filter": bool(self.scope.document_ids),
                "document_ids": list(self.scope.document_ids),
            },
        )
        rows = result.mappings().all()
        if len(rows) != len(normalized_ids):
            raise KnowledgeSourceUnavailable()
        return tuple(
            AuthorizedKnowledgeSource(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                document_title=row["document_title"],
                content_revision_id=row["content_revision_id"],
                index_revision_id=row["index_revision_id"],
                page_number=row["page_number"],
                section=row["section"],
                content=row["content"],
                token_count=row["token_count"],
                embedding_space_hash=row["embedding_space_hash"],
                corpus_revision=int(row["corpus_revision"]),
            )
            for row in rows
        )


class WorkerKnowledgeRetrievalCoordinator:
    """Worker-only query-embedding coordinator; API routes must enqueue instead."""

    def __init__(
        self,
        *,
        enabled: bool,
        provider: QueryEmbeddingProvider,
        embedding_space_hash: str,
        policy: ExactV1RetrievalPolicy = EXACT_V1_POLICY,
    ) -> None:
        self._enabled = enabled
        self._provider = provider
        self._embedding_space_hash = embedding_space_hash
        self._policy = policy

    async def retrieve(
        self,
        db: AsyncSession,
        *,
        principal: User,
        subject_id: UUID,
        query: str,
        document_ids: Sequence[UUID] | None = None,
        limit: int = 5,
    ) -> KnowledgeRetrievalResult:
        if not self._enabled:
            raise KnowledgeRetrievalDisabled()
        retriever = await KnowledgeRetriever.authorize(
            db,
            principal=principal,
            subject_id=subject_id,
            query=query,
            document_ids=document_ids,
            limit=limit,
            policy=self._policy,
        )
        if retriever.scope.embedding_space_hash is None:
            return retriever.empty_result()
        if self._embedding_space_hash != retriever.scope.embedding_space_hash:
            raise IncompatibleEmbeddingSpace()
        response = await self._provider.embed_query(retriever._query)
        if len(response.vectors) != 1:
            raise InvalidQueryEmbedding()
        return await retriever.retrieve(
            response.vectors[0],
            embedding_space_hash=self._embedding_space_hash,
        )
