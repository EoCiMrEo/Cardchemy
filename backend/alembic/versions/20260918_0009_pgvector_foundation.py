"""Require the reviewed PostgreSQL 16 and pgvector 0.8.6 foundation.

Revision ID: 20260918_0009
Revises: 20260917_0008
Create Date: 2026-09-18

This revision installs no application tables. The vector extension is shared
database infrastructure, so downgrade deliberately leaves it installed.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError


revision: str = "20260918_0009"
down_revision: str | None = "20260917_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REQUIRED_EXTENSION_VERSION = "0.8.6"
REQUIRED_EXTENSION_SCHEMA = "public"


def _installed_vector(connection: sa.engine.Connection) -> tuple[str, str] | None:
    row = connection.execute(sa.text("""
        SELECT extension.extversion, namespace.nspname
        FROM pg_extension AS extension
        JOIN pg_namespace AS namespace ON namespace.oid = extension.extnamespace
        WHERE extension.extname = 'vector'
    """)).one_or_none()
    return (row[0], row[1]) if row else None


def _verify_installed(connection: sa.engine.Connection) -> bool:
    installed = _installed_vector(connection)
    if installed is None:
        return False
    version, schema = installed
    if version != REQUIRED_EXTENSION_VERSION:
        raise RuntimeError(
            "Installed vector extension version is unsupported; require pgvector 0.8.6 "
            "before migrating. Do not alter an existing extension automatically."
        )
    if schema != REQUIRED_EXTENSION_SCHEMA:
        raise RuntimeError(
            "Installed vector extension must be in the public schema for the supported search path."
        )
    return True


def upgrade() -> None:
    connection = op.get_bind()
    server_version = connection.execute(sa.text(
        "SELECT current_setting('server_version_num')::integer"
    )).scalar_one()
    if not 160000 <= server_version < 170000:
        raise RuntimeError("Cardchemy requires PostgreSQL 16 for the vector schema")

    # The exact extension script/control package must remain available even
    # when another operator already installed the extension in this database.
    available = connection.execute(sa.text("""
        SELECT superuser, trusted
        FROM pg_available_extension_versions
        WHERE name = 'vector' AND version = '0.8.6'
    """)).one_or_none()
    if available is None:
        raise RuntimeError(
            "pgvector 0.8.6 is not installed on the PostgreSQL 16 server; "
            "install the reviewed server package before migrating."
        )

    if _verify_installed(connection):
        return

    # PostgreSQL's extension metadata determines whether a non-superuser may
    # install this exact server package. A preinstalled compatible extension
    # needs no new CREATE privilege and is accepted above.
    can_create, is_superuser = connection.execute(sa.text("""
        SELECT has_database_privilege(current_user, current_database(), 'CREATE'),
               (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
    """)).one()
    if not can_create or (available[0] and not available[1] and not is_superuser):
        raise RuntimeError(
            "Vector extension installation needs database CREATE and the privilege "
            "required by pgvector; have an administrator preinstall pgvector 0.8.6 "
            "in public or run this migration with an authorized role."
        )

    try:
        connection.execute(sa.text("CREATE EXTENSION vector WITH SCHEMA public VERSION '0.8.6'"))
    except SQLAlchemyError:
        raise RuntimeError(
            "Could not install pgvector 0.8.6 in public; verify server package, "
            "database privileges and extension ownership before retrying."
        ) from None
    if not _verify_installed(connection):
        raise RuntimeError("Vector extension installation did not complete")


def downgrade() -> None:
    # An extension may be shared by other schemas/applications, and ownership
    # cannot be inferred from this revision. Re-upgrade accepts 0.8.6 in public.
    pass
