"""Portable ORM declaration for the reviewed 1,536-dimensional vector space.

SQLite's JSON variant supports offline fixture construction only. PostgreSQL
and the pgvector extension enforce the actual VECTOR type and operators.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON


EMBEDDING_DIMENSIONS = 1536


def embedding_vector_type() -> Vector:
    """Return the PostgreSQL VECTOR(1536) type with a SQLite fixture variant."""

    return Vector(EMBEDDING_DIMENSIONS).with_variant(JSON(), "sqlite")
