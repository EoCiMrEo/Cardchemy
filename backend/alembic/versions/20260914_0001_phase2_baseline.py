"""Phase 2 clean baseline with integrity constraints and indexes.

Revision ID: 20260914_0001
Revises: None
Create Date: 2026-09-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260914_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UUID = postgresql.UUID(as_uuid=True)
TIMESTAMPTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    user_role = postgresql.ENUM(
        "INSTRUCTOR", "STUDENT", name="userrole", create_type=False
    )
    user_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", user_role, server_default=sa.text("'STUDENT'"), nullable=False),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(email)) BETWEEN 3 AND 255", name="ck_users_email_length"),
        sa.CheckConstraint(
            "full_name IS NULL OR length(trim(full_name)) BETWEEN 1 AND 255",
            name="ck_users_full_name_length",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_users_email_normalized", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "subjects",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instructor_id", UUID, nullable=False),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) BETWEEN 1 AND 255", name="ck_subjects_name_length"),
        sa.CheckConstraint(
            "description IS NULL OR length(trim(description)) BETWEEN 1 AND 10000",
            name="ck_subjects_description_length",
        ),
        sa.ForeignKeyConstraint(["instructor_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subjects_instructor_id", "subjects", ["instructor_id"])

    op.create_table(
        "flashcard_sets",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("subject_id", UUID, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_pdf_name", sa.String(255), nullable=True),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("time_limit", sa.Integer(), nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 255", name="ck_flashcard_sets_title_length"),
        sa.CheckConstraint(
            "description IS NULL OR length(trim(description)) BETWEEN 1 AND 10000",
            name="ck_flashcard_sets_description_length",
        ),
        sa.CheckConstraint(
            "source_pdf_name IS NULL OR length(source_pdf_name) <= 255",
            name="ck_flashcard_sets_source_name_length",
        ),
        sa.CheckConstraint(
            "time_limit IS NULL OR time_limit BETWEEN 5 AND 3600",
            name="ck_flashcard_sets_time_limit",
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flashcard_sets_subject_id", "flashcard_sets", ["subject_id"])

    op.execute(
        """
        CREATE FUNCTION flashcard_options_valid(card_options jsonb, answer text)
        RETURNS boolean
        LANGUAGE sql
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
            SELECT CASE
                WHEN jsonb_typeof(card_options) <> 'array' THEN false
                ELSE (
                    WITH elements AS (
                        SELECT value, trim(value #>> '{}') AS option_text
                        FROM jsonb_array_elements(card_options) AS item(value)
                    )
                    SELECT count(*) = 4
                       AND bool_and(jsonb_typeof(value) = 'string')
                       AND bool_and(length(option_text) BETWEEN 1 AND 10000)
                       AND count(DISTINCT lower(option_text)) = 4
                       AND count(*) FILTER (
                           WHERE lower(option_text) = lower(trim(answer))
                       ) = 1
                    FROM elements
                )
            END
        $$
        """
    )

    op.create_table(
        "flashcards",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("set_id", UUID, nullable=False),
        sa.Column("front_content", sa.Text(), nullable=False),
        sa.Column("back_content", sa.Text(), nullable=False),
        sa.Column("options", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("card_type", sa.String(32), server_default=sa.text("'multiple_choice'"), nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_approved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("source_chunk", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "length(trim(front_content)) BETWEEN 1 AND 10000",
            name="ck_flashcards_front_length",
        ),
        sa.CheckConstraint(
            "length(trim(back_content)) BETWEEN 1 AND 10000",
            name="ck_flashcards_back_length",
        ),
        sa.CheckConstraint(
            "source_chunk IS NULL OR length(source_chunk) <= 10000",
            name="ck_flashcards_source_length",
        ),
        sa.CheckConstraint("confidence_score BETWEEN 0 AND 1", name="ck_flashcards_confidence"),
        sa.CheckConstraint("card_type = 'multiple_choice'", name="ck_flashcards_card_type"),
        sa.CheckConstraint(
            "flashcard_options_valid(options, back_content)",
            name="ck_flashcards_options_valid",
        ),
        sa.ForeignKeyConstraint(["set_id"], ["flashcard_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_flashcards_set_id", "flashcards", ["set_id"])
    op.create_index(
        "ix_flashcards_approved_due_source",
        "flashcards",
        ["set_id", "created_at", "id"],
        postgresql_where=sa.text("is_approved = true"),
    )

    op.create_table(
        "enrollments",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("student_id", UUID, nullable=False),
        sa.Column("subject_id", UUID, nullable=False),
        sa.Column("enrolled_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "subject_id", name="unique_enrollment"),
    )
    op.create_index("ix_enrollments_subject_id", "enrollments", ["subject_id"])

    op.create_table(
        "study_progress",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("student_id", UUID, nullable=False),
        sa.Column("flashcard_id", UUID, nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'new'"), nullable=False),
        sa.Column("ease_factor", sa.Float(), server_default=sa.text("2.5"), nullable=False),
        sa.Column("interval_days", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_review", TIMESTAMPTZ, nullable=True),
        sa.Column("last_reviewed", TIMESTAMPTZ, nullable=True),
        sa.Column("correct_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("incorrect_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint(
            "status IN ('new', 'learning', 'review', 'mastered')",
            name="ck_study_progress_status",
        ),
        sa.CheckConstraint("ease_factor >= 1.3", name="ck_study_progress_ease_factor"),
        sa.CheckConstraint("interval_days >= 0", name="ck_study_progress_interval"),
        sa.CheckConstraint("correct_count >= 0", name="ck_study_progress_correct_count"),
        sa.CheckConstraint("incorrect_count >= 0", name="ck_study_progress_incorrect_count"),
        sa.CheckConstraint(
            "(status = 'new' AND interval_days = 0) OR "
            "(status = 'learning' AND interval_days BETWEEN 0 AND 6) OR "
            "(status = 'review' AND interval_days BETWEEN 7 AND 20) OR "
            "(status = 'mastered' AND interval_days >= 21)",
            name="ck_study_progress_status_interval",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["flashcard_id"], ["flashcards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "flashcard_id", name="unique_progress"),
    )
    op.create_index("ix_study_progress_flashcard_id", "study_progress", ["flashcard_id"])
    op.create_index(
        "ix_study_progress_student_due",
        "study_progress",
        ["student_id", "next_review", "flashcard_id"],
    )

    op.create_table(
        "invite_links",
        sa.Column("id", UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("instructor_id", UUID, nullable=False),
        sa.Column("subject_id", UUID, nullable=False),
        sa.Column("expires_at", TIMESTAMPTZ, nullable=False),
        sa.Column("used_by", UUID, nullable=True),
        sa.Column("used_at", TIMESTAMPTZ, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(code)) BETWEEN 1 AND 20", name="ck_invite_links_code_length"),
        sa.CheckConstraint(
            "expires_at >= created_at + INTERVAL '1 hour' AND "
            "expires_at <= created_at + INTERVAL '720 hours'",
            name="ck_invite_links_lifetime",
        ),
        sa.ForeignKeyConstraint(["instructor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["used_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_invite_links_code"),
    )
    op.create_index("ix_invite_links_instructor_id", "invite_links", ["instructor_id"])
    op.create_index("ix_invite_links_subject_id", "invite_links", ["subject_id"])
    op.create_index("ix_invite_links_used_by", "invite_links", ["used_by"])

    op.create_table(
        "auth_sessions",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("refresh_jti_hash", sa.String(64), nullable=False),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", TIMESTAMPTZ, nullable=False),
        sa.Column("revoked_at", TIMESTAMPTZ, nullable=True),
        sa.Column("reuse_detected_at", TIMESTAMPTZ, nullable=True),
        sa.CheckConstraint("length(refresh_jti_hash) = 64", name="ck_auth_sessions_jti_hash_length"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_jti_hash", name="uq_auth_sessions_refresh_jti_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("created_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", TIMESTAMPTZ, nullable=False),
        sa.Column("used_at", TIMESTAMPTZ, nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])

    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", UUID, nullable=False),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("window_started_at", TIMESTAMPTZ, nullable=False),
        sa.Column("count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", TIMESTAMPTZ, server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(scope)) BETWEEN 1 AND 64", name="ck_rate_limit_scope_length"),
        sa.CheckConstraint("length(key_hash) = 64", name="ck_rate_limit_key_hash_length"),
        sa.CheckConstraint("count >= 0", name="ck_rate_limit_count_nonnegative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "key_hash", name="unique_rate_limit_bucket"),
    )

    op.execute(
        """
        CREATE FUNCTION reject_unpublishable_set()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.is_published AND NOT EXISTS (
                SELECT 1 FROM flashcards
                WHERE set_id = NEW.id AND is_approved = true
            ) THEN
                RAISE EXCEPTION 'published flashcard sets require at least one approved card'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER flashcard_sets_require_approved_card
        BEFORE INSERT OR UPDATE OF is_published ON flashcard_sets
        FOR EACH ROW WHEN (NEW.is_published = true)
        EXECUTE FUNCTION reject_unpublishable_set()
        """
    )
    op.execute(
        """
        CREATE FUNCTION preserve_published_set_content()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE parent_is_published boolean;
        BEGIN
            SELECT is_published INTO parent_is_published
            FROM flashcard_sets WHERE id = OLD.set_id;
            IF parent_is_published AND OLD.is_approved THEN
                IF TG_OP = 'DELETE' THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM flashcards
                        WHERE set_id = OLD.set_id
                          AND is_approved = true
                          AND id <> OLD.id
                    ) THEN
                        RAISE EXCEPTION 'cannot remove the final approved card from a published set'
                            USING ERRCODE = 'check_violation';
                    END IF;
                ELSIF (NOT NEW.is_approved OR NEW.set_id <> OLD.set_id)
                      AND NOT EXISTS (
                          SELECT 1 FROM flashcards
                          WHERE set_id = OLD.set_id
                            AND is_approved = true
                            AND id <> OLD.id
                      ) THEN
                    RAISE EXCEPTION 'cannot remove the final approved card from a published set'
                        USING ERRCODE = 'check_violation';
                END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER flashcards_preserve_published_content
        BEFORE DELETE OR UPDATE OF is_approved, set_id ON flashcards
        FOR EACH ROW
        EXECUTE FUNCTION preserve_published_set_content()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS flashcards_preserve_published_content ON flashcards")
    op.execute("DROP FUNCTION IF EXISTS preserve_published_set_content()")
    op.execute("DROP TRIGGER IF EXISTS flashcard_sets_require_approved_card ON flashcard_sets")
    op.execute("DROP FUNCTION IF EXISTS reject_unpublishable_set()")
    op.drop_table("rate_limit_buckets")
    op.drop_table("password_reset_tokens")
    op.drop_table("auth_sessions")
    op.drop_table("invite_links")
    op.drop_table("study_progress")
    op.drop_table("enrollments")
    op.drop_table("flashcards")
    op.execute("DROP FUNCTION IF EXISTS flashcard_options_valid(jsonb, text)")
    op.drop_table("flashcard_sets")
    op.drop_table("subjects")
    op.drop_table("users")
    postgresql.ENUM("INSTRUCTOR", "STUDENT", name="userrole").drop(op.get_bind(), checkfirst=True)
