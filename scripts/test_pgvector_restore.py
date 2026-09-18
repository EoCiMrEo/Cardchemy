"""Rehearse a populated pgvector dump/restore in isolated, ephemeral databases.

No operator environment file, existing container, network, or persistent volume is
used. The only content is fixed synthetic text and three-dimensional vectors.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from test_services import cleanup_containers, system_environment
from runtime_database import ensure_database_image


ROOT = Path(__file__).resolve().parents[1]


def docker(*arguments: str, input_bytes: bytes | None = None, label: str) -> bytes:
    result = subprocess.run(["docker", *arguments], input=input_bytes,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=system_environment(),
                            check=False)
    if result.returncode:
        raise RuntimeError(f"{label} failed (exit {result.returncode}); details withheld")
    return result.stdout


def ready(name: str) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        result = subprocess.run(["docker", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres",
                                 "-d", "postgres"], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, env=system_environment(), check=False)
        if result.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("Disposable PostgreSQL did not become ready within 45 seconds")


def main() -> None:
    database = json.loads((ROOT / "runtime-artifacts.json").read_text(encoding="utf-8"))["database"]
    image, platform = ensure_database_image(ROOT)
    suffix = uuid4().hex[:12]
    source = f"cardchemy-vector-restore-source-{suffix}"
    target = f"cardchemy-vector-restore-target-{suffix}"
    owned = []
    try:
        for name in (source, target):
            owned.append(name)
            docker("run", "-d", "--rm", "--network", "none", "--platform", platform,
                   "--tmpfs", "/var/lib/postgresql/data:rw,size=256m",
                   "--name", name, "-e", "POSTGRES_HOST_AUTH_METHOD=trust", image,
                   label="Start isolated PostgreSQL")
            ready(name)

        schema = """
            CREATE EXTENSION vector;
            CREATE TABLE rag_restore_probe (
              id integer PRIMARY KEY,
              body text NOT NULL,
              embedding vector(3) NOT NULL
            );
            INSERT INTO rag_restore_probe VALUES
              (1, 'alpha evidence', '[1,0,0]'),
              (2, 'beta evidence', '[0,1,0]');
            CREATE INDEX rag_restore_probe_embedding_hnsw
              ON rag_restore_probe USING hnsw (embedding vector_cosine_ops);
            CREATE INDEX rag_restore_probe_body_gin
              ON rag_restore_probe USING gin (to_tsvector('simple', body));
        """
        docker("exec", source, "psql", "-U", "postgres", "-d", "postgres",
               "-v", "ON_ERROR_STOP=1", "-c", schema, label="Populate source vectors and indexes")
        archive = docker("exec", source, "pg_dump", "-U", "postgres", "-d", "postgres",
                         "-Fc", "--no-owner", "--no-acl", label="Dump populated vector database")
        if not archive:
            raise RuntimeError("Disposable vector backup is empty")
        docker("exec", "-i", target, "pg_restore", "-U", "postgres", "-d", "postgres",
               "--exit-on-error", "--no-owner", "--no-acl", input_bytes=archive,
               label="Restore populated vector database")

        check = """
            SELECT
              (SELECT extversion FROM pg_extension WHERE extname = 'vector') = '0.8.6'
              AND (SELECT count(*) FROM rag_restore_probe) = 2
              AND (SELECT count(*) FROM pg_index i
                   JOIN pg_class c ON c.oid = i.indexrelid
                   WHERE c.relname IN ('rag_restore_probe_embedding_hnsw',
                                       'rag_restore_probe_body_gin') AND i.indisvalid) = 2
              AND (SELECT id FROM rag_restore_probe
                   ORDER BY embedding <=> '[1,0,0]'::vector LIMIT 1) = 1
              AND (SELECT count(*) FROM rag_restore_probe
                   WHERE to_tsvector('simple', body) @@ plainto_tsquery('simple', 'alpha')) = 1;
        """
        result = docker("exec", target, "psql", "-U", "postgres", "-d", "postgres",
                        "-v", "ON_ERROR_STOP=1", "-tAX", "-c", check,
                        label="Verify restored extension, data, indexes and queries")
        if result.strip() != b"t":
            raise RuntimeError("Restored pgvector extension, indexes or data failed verification")
    finally:
        cleanup_containers(owned)
    print("Disposable populated pgvector dump/restore and vector/lexical checks passed; owned containers removed.")


if __name__ == "__main__":
    main()
