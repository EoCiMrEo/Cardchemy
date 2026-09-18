"""Stage allowlisted audit metadata without owning a transaction commit."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditAction, AuditEvent


class AuditService:
    @staticmethod
    def record(
        db: AsyncSession,
        *,
        action: AuditAction,
        actor_kind: str = "user",
        actor_id: UUID | None = None,
        target_type: str,
        target_id: UUID,
        subject_id: UUID | None = None,
        state_before: bool | None = None,
        state_after: bool | None = None,
        affected_count: int | None = None,
        role_before: str | None = None,
        role_after: str | None = None,
        request_id: UUID | None = None,
    ) -> AuditEvent:
        """Only fixed fields can enter an audit record; no arbitrary metadata.

        The caller's domain commit also commits this record. A failure before
        commit rolls both back; audit failures must never be silently dropped.
        """
        if not isinstance(action, AuditAction):
            raise ValueError("Unsupported audit action")
        if actor_kind not in {"user", "operator", "operator_database"}:
            raise ValueError("Unsupported audit actor kind")
        if target_type not in {"invitation", "card", "set", "account"}:
            raise ValueError("Unsupported audit target type")
        for role in (role_before, role_after):
            if role is not None and role not in {"student", "instructor"}:
                raise ValueError("Unsupported audit role")
        if affected_count is not None and (type(affected_count) is not int or affected_count < 0):
            raise ValueError("Invalid audit count")
        if any(value is not None and type(value) is not bool for value in (state_before, state_after)):
            raise ValueError("Invalid audit state")
        if request_id is None:
            # Lazy import keeps the persistence service independent of HTTP setup.
            from app.observability import current_request_id

            correlation = current_request_id()
            if correlation:
                request_id = UUID(str(correlation))
        event = AuditEvent(
            action=action.value,
            actor_kind=actor_kind,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            subject_id=subject_id,
            request_id=request_id,
            state_before=state_before,
            state_after=state_after,
            affected_count=affected_count,
            role_before=role_before,
            role_after=role_after,
        )
        db.add(event)
        return event
