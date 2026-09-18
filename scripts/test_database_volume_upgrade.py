"""Prove a populated prior PG16 database restores into a separate ICU target.

Creates one random, labeled verification volume, seeds the prior application
head and synthetic learning content, stops its vanilla PG16 writer, then
logically restores into a separate reviewed pgvector/ICU volume. No operator file,
container or volume is used. This is not an operational upgrade command.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
from uuid import uuid4

from check_runtime_artifacts import validate
from runtime_database import ensure_database_image
from test_pgvector_restore import docker
from test_services import ROOT, cleanup_containers, port, system_environment, wait_postgres_ready


PRIOR_HEAD = "20260917_0008"
VECTOR_HEAD = "20260918_0009"
OWNER_LABEL = "cardchemy.verification.database-volume-upgrade"
LEGACY_IMAGE = "postgres:16-bookworm@sha256:bb3e1a57e5407e0a5280b4211980a5e537f4abd234a87014ac979849a78dd825"


def migrate(database_port: int, password: str, target: str) -> None:
    environment = system_environment() | {
        "ENVIRONMENT": "test", "PYTHONUTF8": "1",
        "DATABASE_URL": f"postgresql+asyncpg://qa:{password}@127.0.0.1:{database_port}/volume_compatibility_test",
        "SECRET_KEY": "test-only-secret-with-adequate-entropy-1234567890",
        "GENERATION_SOURCE_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    }
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", target],
                            cwd=ROOT / "backend", env=environment, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("Disposable data-volume application migration failed; details withheld")


def sql(name: str, statement: str, *, label: str = "Check synthetic existing-volume application data") -> bytes:
    return docker("exec", name, "psql", "-U", "qa", "-d", "volume_compatibility_test",
                  "-v", "ON_ERROR_STOP=1", "-tAX", "-c", statement,
                  label=label)


def main() -> None:
    database = validate(ROOT)
    target_image, platform = ensure_database_image(ROOT)
    suffix = uuid4().hex[:12]
    volume = f"cardchemy-db-volume-upgrade-{suffix}"
    source_volume = f"{volume}-legacy"
    target_volume = f"{volume}-icu"
    source = f"{volume}-source"
    target = f"{volume}-target"
    owned = []
    owned_volumes = []
    try:
        existing = set(docker("volume", "ls", "--format", "{{.Name}}",
                             label="Inventory verification volume names").decode().splitlines())
        if {source_volume, target_volume}.intersection(existing):
            raise RuntimeError("Random verification volume already exists; refusing reuse")
        for task_volume in (source_volume, target_volume):
            docker("volume", "create", "--label", f"{OWNER_LABEL}={suffix}", task_volume,
                   label="Create labeled disposable verification volume")
            owned_volumes.append(task_volume)
        docker("pull", "--platform", database["supported_platform"], LEGACY_IMAGE,
               label="Pull prior vanilla PostgreSQL 16 reference")
        prior_identity = docker("image", "inspect", "--format", "{{.Id}}", LEGACY_IMAGE,
                                label="Snapshot prior PostgreSQL image identity").decode().strip()
        if not prior_identity.startswith("sha256:") or len(prior_identity) != 71:
            raise RuntimeError("Prior PostgreSQL image identity is invalid")
        password = secrets.token_urlsafe(36)
        with tempfile.TemporaryDirectory(prefix="cardchemy-volume-upgrade-") as temporary:
            environment_file = Path(temporary) / "postgres.env"
            environment_file.write_text(
                f"POSTGRES_USER=qa\nPOSTGRES_DB=volume_compatibility_test\nPOSTGRES_PASSWORD={password}\n",
                encoding="utf-8")
            environment_file.chmod(0o600)
            for name, image, task_volume in ((source, prior_identity, source_volume),
                                           (target, target_image, target_volume)):
                owned.append(name)
                docker("run", "-d", "--rm", "--name", name, "--platform", platform,
                       "--env-file", str(environment_file), "-p", "127.0.0.1::5432",
                       "-v", f"{task_volume}:{database['postgres_data_directory']}", image,
                       label="Start isolated existing-data-path database")
                database_port = port(name, 5432)
                wait_postgres_ready(database_port, password, "volume_compatibility_test")
                if name == source:
                    if sql(name, "SELECT current_setting('server_version_num')::integer / 10000").strip() != b"16":
                        raise RuntimeError("Prior database image is not PostgreSQL 16")
                    prior_version = sql(name, "SELECT version()").decode().strip()
                    prior_collation = sql(name, """
                        SELECT concat(datlocprovider, ':', datcollate, ':', coalesce(datcollversion, ''))
                        FROM pg_database WHERE datname = current_database();
                    """, label="Capture legacy PG16 libc locale/collation").decode().strip()
                    if not prior_collation.startswith("c:en_US.utf8:"):
                        raise RuntimeError("Legacy reference must exercise Bookworm en_US.utf8 libc collation")
                    migrate(database_port, password, PRIOR_HEAD)
                    sql(name, """
                        INSERT INTO users(id, email, hashed_password, role)
                          VALUES ('10000000-0000-0000-0000-000000000001',
                                  'volume-proof@example.invalid', 'synthetic-nonlogin-hash', 'INSTRUCTOR');
                        INSERT INTO subjects(id, name, instructor_id)
                          VALUES ('20000000-0000-0000-0000-000000000001', 'Synthetic volume proof',
                                  '10000000-0000-0000-0000-000000000001');
                        INSERT INTO flashcard_sets(id, subject_id, title)
                          VALUES ('30000000-0000-0000-0000-000000000001',
                                  '20000000-0000-0000-0000-000000000001', 'Synthetic preserved set');
                        INSERT INTO flashcards(id, set_id, front_content, back_content, options)
                          VALUES ('40000000-0000-0000-0000-000000000001',
                                  '30000000-0000-0000-0000-000000000001', 'Which symbol is alpha?', 'Alpha',
                                  '["Alpha","Beta","Gamma","Delta"]');
                        CREATE TABLE unicode_volume_probe(value text NOT NULL);
                        INSERT INTO unicode_volume_probe VALUES
                          ('Ångström'), ('angstrom'), ('中文'), ('Zebra'), ('Éclair'), ('é');
                        CREATE UNIQUE INDEX unicode_volume_probe_btree ON unicode_volume_probe(value);
                        CREATE INDEX unicode_volume_probe_gin
                          ON unicode_volume_probe USING gin(to_tsvector('simple', value));
                    """, label="Seed prior-head learning content and Unicode indexes")
                    archive = docker("exec", name, "pg_dump", "-U", "qa", "-d", "volume_compatibility_test",
                                     "-Fc", "--no-owner", "--no-acl",
                                     label="Back up synthetic legacy PG16 learning content")
                    docker("stop", "--time", "30", name, label="Drain and stop prior database writer")
                    baseline_control = docker(
                        "run", "--rm", "--network", "none", "--platform", platform,
                        "-v", f"{source_volume}:{database['postgres_data_directory']}:ro",
                        "--entrypoint", "sh", target_image, "-ec",
                        'sha256sum "$PGDATA/global/pg_control"',
                        label="Snapshot synthetic legacy cluster control before guard probes")
                    for marker_mode in ("unmarked", "wrong_marked"):
                        if marker_mode == "wrong_marked":
                            docker("run", "--rm", "--network", "none", "--platform", platform,
                                   "-v", f"{source_volume}:{database['postgres_data_directory']}",
                                   "--entrypoint", "sh", target_image, "-ec",
                                   'printf "%s\\n" wrong-profile > "$PGDATA/.cardchemy-runtime-profile"',
                                   label="Prepare wrong marker on exact owned synthetic legacy volume")
                        probe_name = f"{volume}-reject-{marker_mode}"
                        owned.append(probe_name)
                        rejected = subprocess.run(
                            ["docker", "run", "--rm", "--network", "none", "--platform", platform,
                             "--name", probe_name,
                             "-v", f"{source_volume}:{database['postgres_data_directory']}",
                             target_image, "postgres"], env=system_environment(),
                            capture_output=True, timeout=20)
                        if (rejected.returncode != 1
                                or b"legacy or incompatible data requires logical backup/restore" not in rejected.stderr):
                            raise RuntimeError("Synthetic legacy cluster guard failed closed-startup verification")
                        after_control = docker(
                            "run", "--rm", "--network", "none", "--platform", platform,
                            "-v", f"{source_volume}:{database['postgres_data_directory']}:ro",
                            "--entrypoint", "sh", target_image, "-ec",
                            'sha256sum "$PGDATA/global/pg_control"',
                            label="Verify synthetic legacy cluster control unchanged after rejected startup")
                        if after_control != baseline_control:
                            raise RuntimeError("Rejected synthetic legacy startup modified cluster control")
                    docker("run", "--rm", "--network", "none", "--platform", platform,
                           "-v", f"{source_volume}:{database['postgres_data_directory']}",
                           "--entrypoint", "sh", target_image, "-ec",
                           'rm "$PGDATA/.cardchemy-runtime-profile"',
                           label="Remove only the synthetic wrong-marker fixture")
                else:
                    if sql(name, """
                        SELECT datlocprovider = 'i' AND daticulocale = 'en-US'
                          AND pg_encoding_to_char(encoding) = 'UTF8'
                        FROM pg_database WHERE datname = current_database();
                    """, label="Verify separate target ICU locale").strip() != b"t":
                        raise RuntimeError("Separate restored database target must use ICU en-US UTF8")
                    docker("exec", "-i", name, "pg_restore", "-U", "qa", "-d", "volume_compatibility_test",
                           "--exit-on-error", "--no-owner", "--no-acl", input_bytes=archive,
                           label="Restore synthetic legacy application into separate ICU target")
                    if sql(name, f"SELECT version_num FROM alembic_version").strip() != PRIOR_HEAD.encode():
                        raise RuntimeError("Prior application head did not survive the image change")
                    if sql(name, """
                        SELECT count(*) = 1 FROM flashcards AS c
                        JOIN flashcard_sets AS s ON c.set_id = s.id
                        JOIN subjects AS j ON s.subject_id = j.id
                        JOIN users AS u ON j.instructor_id = u.id
                        WHERE c.id = '40000000-0000-0000-0000-000000000001'
                          AND c.back_content = 'Alpha'
                          AND c.options = '["Alpha","Beta","Gamma","Delta"]'::jsonb
                          AND u.email = 'volume-proof@example.invalid';
                    """).strip() != b"t":
                        raise RuntimeError("Synthetic learning content did not survive the image change")
                    migrate(database_port, password, VECTOR_HEAD)
                    if sql(name, """
                        SELECT count(*) = 6 FROM unicode_volume_probe;
                        SELECT count(*) = 2 FROM pg_index AS i JOIN pg_class AS c ON c.oid = i.indexrelid
                          WHERE c.relname IN ('unicode_volume_probe_btree', 'unicode_volume_probe_gin')
                            AND i.indisvalid;
                        SELECT count(*) = 1 FROM unicode_volume_probe
                          WHERE to_tsvector('simple', value) @@ plainto_tsquery('simple', '中文');
                        SELECT count(*) = 1 FROM unicode_volume_probe WHERE value = 'Ångström';
                    """).strip() != b"t\nt\nt\nt":
                        raise RuntimeError("Restored Unicode text, unique/lexical indexes or queries failed")
                    sql(name, """
                        DO $$ BEGIN
                          INSERT INTO unicode_volume_probe VALUES ('Ångström');
                          RAISE EXCEPTION 'Duplicate Unicode value unexpectedly inserted';
                        EXCEPTION WHEN unique_violation THEN NULL;
                        END $$;
                    """)
                    if sql(name, f"""
                        SELECT (SELECT version_num FROM alembic_version) = '{VECTOR_HEAD}'
                          AND (SELECT extversion FROM pg_extension WHERE extname = 'vector') = '0.8.6'
                          AND ('[1,0,0]'::vector <=> '[1,0,0]'::vector) = 0;
                    """).strip() != b"t":
                        raise RuntimeError("Migrated existing data path failed vector/head verification")
        reports = ROOT / "artifacts/database-volume-upgrade" / suffix
        reports.mkdir(parents=True, exist_ok=False)
        (reports / "metadata.json").write_text(json.dumps({
            "created_at": datetime.now(timezone.utc).isoformat(),
            "prior_image": prior_identity, "prior_image_reference": LEGACY_IMAGE, "prior_server_version": prior_version,
            "database": database, "prior_head": PRIOR_HEAD, "verified_target_head": VECTOR_HEAD,
            "target_image_id": target_image, "prior_collation": prior_collation,
            "upgrade_mode": "logical_restore_to_separate_ICU_target",
            "legacy_unmarked_and_wrong_marked_startups_rejected": True,
            "legacy_pg_control_unchanged_after_rejection": True,
            "preserved_synthetic_records": ["instructor", "subject", "flashcard_set", "flashcard"],
        }, indent=2) + "\n", encoding="utf-8")
    finally:
        cleanup_containers(owned)
        for task_volume in owned_volumes:
            owner = docker("volume", "inspect", "--format",
                           f'{{{{ index .Labels "{OWNER_LABEL}" }}}}', task_volume,
                           label="Verify exact disposable volume ownership").decode().strip()
            if (task_volume not in {source_volume, target_volume}
                    or owner != suffix):
                raise RuntimeError("Disposable volume ownership check failed; refusing removal")
            docker("volume", "rm", task_volume, label="Remove exact owned disposable verification volume")
            remaining = set(docker("volume", "ls", "--format", "{{.Name}}",
                                   label="Verify disposable volume cleanup").decode().splitlines())
            if task_volume in remaining:
                raise RuntimeError("Owned disposable verification volume remains")
    print("Legacy PG16 application head, learning content and Unicode indexes restored into a separate ICU target and migrated to vector head; owned containers/volumes removed.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError):
        raise SystemExit("Disposable database volume compatibility proof failed; no credentials printed.")
