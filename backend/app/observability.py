"""Structured, allowlisted diagnostics that never serialize private content."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import re
import sys
from time import monotonic
from uuid import UUID, uuid4

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse


_request_id: ContextVar[UUID | None] = ContextVar("request_id", default=None)
_job_id: ContextVar[UUID | None] = ContextVar("job_id", default=None)
_outbox_id: ContextVar[UUID | None] = ContextVar("outbox_id", default=None)
_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
SAFE_ERROR_CODES = frozenset({
    "internal_error", "invalid_request", "authentication_required", "access_denied", "not_found",
    "method_not_allowed", "conflict", "validation_failed", "rate_limited", "service_unavailable", "request_failed",
    "ai_context_window_limit", "ai_cost_limit", "ai_estimated_cost_limit", "ai_input_token_limit",
    "ai_model_unavailable", "ai_output_token_limit", "ai_provider_access_denied",
    "ai_provider_authentication_failed", "ai_provider_invalid_request", "ai_provider_not_configured",
    "ai_provider_rate_limited", "ai_provider_request_token_limit", "ai_provider_timeout", "ai_provider_unavailable",
    "invalid_ai_output", "card_count_out_of_range", "deployment_source_storage_limit", "document_has_no_text",
    "email_event_expired", "email_internal_error", "email_worker_lease_expired", "empty_pdf", "empty_upload",
    "encrypted_pdf", "generation_internal_error", "generation_job_not_found", "generation_job_timeout",
    "generation_queue_full", "generation_temporarily_unavailable", "idempotency_conflict", "idempotency_key_reused",
    "image_only_pdf", "insufficient_grounded_cards", "invalid_content_length", "invalid_email_header",
    "invalid_filename", "invalid_generated_cards", "invalid_idempotency_key", "invalid_pdf_signature",
    "invalid_recipient", "invitation_invalidated", "invitation_recipient_missing", "invitation_subject_missing",
    "job_not_awaiting_upload", "job_not_retryable", "job_source_conflict", "malformed_pdf", "manual_retry_limit",
    "ocr_failed", "ocr_timeout", "ocr_unavailable", "page_limit_exceeded", "password_change_event_invalid",
    "password_reset_invalidated", "pdf_extraction_timeout", "pdf_resource_limit", "smtp_authentication_failed",
    "smtp_connection_failed", "smtp_delivery_ambiguous", "smtp_disconnected", "smtp_protocol_error", "smtp_tls_failed",
    "smtp_starttls_unavailable", "smtp_feature_unsupported", "smtp_temporary_rejection", "smtp_rejected",
    "source_decryption_failed", "source_missing", "text_limit_exceeded", "unsupported_email_type",
    "unsupported_media_type", "upload_reservation_expired", "upload_too_large", "user_active_job_limit",
    "user_daily_job_limit", "user_daily_card_limit", "user_daily_upload_limit", "user_source_storage_limit",
    "deployment_daily_job_limit", "deployment_daily_card_limit", "deployment_daily_upload_limit", "worker_lease_expired",
    "pdf_processing_failed",
})
EVENTS = frozenset({
    "api_started", "database_revision_verified", "api_stopped", "request_completed",
    "request_failed", "request_record_failed", "worker_started", "worker_stopped",
    "worker_disabled", "worker_heartbeat_failed", "worker_shutdown_expired",
    "generation_started", "generation_stage", "generation_completed", "generation_failed",
    "generation_heartbeat_failed", "generation_lease_lost", "generation_cancelled",
    "email_started", "email_sent", "email_failed", "email_lease_lost",
    "password_reset_enqueue_failed", "process_failed", "telemetry_failed", "telemetry_sent",
    "external_log",
})
NUMERIC_FIELDS = frozenset({
    "status_code", "latency_milliseconds", "duration_milliseconds", "attempt_count",
    "active_count", "card_count", "input_tokens", "output_tokens", "cost_microusd",
    "provider_request_count", "provider_retry_count",
})
ENUM_FIELDS = {
    "kind": {"generation", "email", "api"},
    "status": {"running", "disabled", "draining", "completed", "failed", "cancelled", "queued"},
    "stage": {"starting", "validating_pdf", "extracting_text", "generating_cards", "persisting"},
}


def current_request_id() -> UUID | None:
    return _request_id.get()


@contextmanager
def job_context(identifier: UUID, *, email: bool = False, request_id: UUID | None = None):
    variable = _outbox_id if email else _job_id
    token = variable.set(identifier)
    request_token = _request_id.set(request_id)
    try:
        yield
    finally:
        variable.reset(token)
        _request_id.reset(request_token)


class SafeLogFilter(logging.Filter):
    """Discard third-party text, formatted args, tracebacks, and stack dumps."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not isinstance(record.msg, str) or record.msg not in EVENTS:
            record.msg = "external_log"
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


class SafeJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = record.msg if isinstance(record.msg, str) and record.msg in EVENTS else "external_log"
        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname if record.levelname in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO",
            "event": event,
        }
        for key, value in (("request_id", _request_id.get()), ("job_id", _job_id.get()), ("outbox_id", _outbox_id.get())):
            candidate = getattr(record, key, value)
            if isinstance(candidate, UUID):
                payload[key] = str(candidate)
        for key in NUMERIC_FIELDS:
            value = getattr(record, key, None)
            if type(value) is int and 0 <= value <= 2**63 - 1:
                payload[key] = value
        for key, allowed in ENUM_FIELDS.items():
            value = getattr(record, key, None)
            if isinstance(value, str) and value in allowed:
                payload[key] = value
        code = getattr(record, "error_code", None)
        if isinstance(code, str) and code in SAFE_ERROR_CODES:
            payload["error_code"] = code
        # Routes and all arbitrary text/objects are deliberately absent. The
        # durable request record owns its trusted route template.
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def initialize_logging(level: str = "INFO") -> None:
    """Sanitize every configured sink, including Uvicorn and SQLAlchemy."""

    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(logging.StreamHandler(sys.stderr))
    loggers = [root] + [value for value in logging.Logger.manager.loggerDict.values() if isinstance(value, logging.Logger)]
    for logger in loggers:
        for handler in logger.handlers:
            handler.setFormatter(SafeJsonFormatter())
            if not any(isinstance(item, SafeLogFilter) for item in handler.filters):
                handler.addFilter(SafeLogFilter())
    # Access text includes tokens in URLs; request_completed replaces it.
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


configure_logging = initialize_logging


def safe_error_code(value: object) -> str:
    return value if isinstance(value, str) and value in SAFE_ERROR_CODES else "internal_error"


DEFAULT_ERRORS = {
    400: ("invalid_request", "The request could not be accepted."),
    401: ("authentication_required", "Could not validate credentials"),
    403: ("access_denied", "Access denied"),
    404: ("not_found", "Not Found"),
    405: ("method_not_allowed", "Method Not Allowed"),
    409: ("conflict", "The request conflicts with the current state."),
    422: ("validation_failed", "The request contains invalid values."),
    429: ("rate_limited", "Too many requests. Please try again later."),
    503: ("service_unavailable", "The service is temporarily unavailable."),
}
# These strings are application-authored contracts, never request/model text.
SAFE_MESSAGES = frozenset({
    "Could not validate credentials", "Email already registered", "Only students can join subjects",
    "Invalid invitation", "Invitation has already been used", "Invitation has expired",
    "Already enrolled in this subject", "This invitation was sent to another email address",
    "Invalid or expired reset token", "Instructor access required", "Student access required",
    "Incorrect email or password", "Refresh cookie is missing", "Subject not found",
    "Flashcard set not found", "Flashcard not found", "This flashcard set is not yet published",
    "You don't have access to this subject", "Only instructors can perform this action",
    "You are not enrolled in this subject", "Access denied", "Not Found", "Method Not Allowed",
    "Too many requests. Please try again later.", "selected_option_index does not identify an option",
    "selected_option does not identify an option",
    "A flashcard set must contain at least one approved card before publication",
    "Invalid credentials", "Invalid refresh token", "Invalid or expired invitation",
    "Invalid or expired invitation token", "Invalid or expired reset token",
    "Invitation registration requires the invited email address",
    "Registration is only available through a valid invitation",
    "User account is disabled", "Account is disabled", "Inactive user",
    "Only instructors can create subjects", "Only instructors can create flashcard sets",
    "Only instructors can create flashcards", "Only instructors can modify flashcards",
    "Only instructors can delete flashcards", "Only instructors can approve flashcards",
    "You don't have permission to modify this flashcard set",
    "You don't have permission to delete this flashcard set",
    "You don't have permission to modify this flashcard",
    "You don't have permission to delete this flashcard",
    "You don't have permission to approve this flashcard",
    "Students can only view published flashcard sets", "Students can only view approved flashcards",
    "Invalid or expired token", "Session is invalid or expired",
    "Invitation was already consumed or enrollment already exists",
    "Registration or enrollment conflicts with an existing record",
})
SAFE_DOMAIN_MESSAGES = frozenset({
    "A PDF filename is required.", "Content-Length must be a non-negative integer.",
    "Encrypted or password-protected PDFs are not supported.",
    "Finish or cancel an active generation job before starting another.",
    "Generation is unavailable until an AI provider is configured.", "Generation job not found.",
    "Idempotency-Key must contain 8 to 128 visible ASCII characters.",
    "No selectable text was found. Enable OCR or upload a text-based PDF.",
    "OCR could not recognize one of the PDF pages.", "OCR could not render one of the PDF pages.",
    "OCR did not find readable text in the PDF.", "OCR exceeded the configured per-page timeout.",
    "OCR is enabled but the worker is missing Poppler or Tesseract.",
    "PDF extraction exceeded the configured timeout.",
    "PDF extraction stopped after reaching a worker resource limit.",
    "The OCR output exceeds the configured character limit.", "The PDF does not contain any pages.",
    "The PDF filename cannot exceed 255 characters.", "The PDF is malformed or cannot be read.",
    "The PDF upload is empty.", "The deployment daily PDF upload-byte limit has been reached.",
    "The deployment daily generated-card limit has been reached.",
    "The deployment daily generation-job limit has been reached.", "The deployment temporary PDF storage is at capacity.",
    "The extracted PDF text exceeds the configured character limit.", "The generation queue is full. Try again later.",
    "The upload reservation expired. Start a new generation job.", "The uploaded file does not have a valid PDF signature.",
    "The uploaded file must use the application/pdf media type.", "This Idempotency-Key was already used for another operation.",
    "This Idempotency-Key was already used for different job metadata.", "This generation job can no longer be retried.",
    "This generation job reached its manual retry limit.", "This job already has a different source PDF.",
    "This job is not accepting a source upload.", "Your daily PDF upload-byte limit has been reached.",
    "Your daily generated-card limit has been reached.", "Your daily generation-job limit has been reached.",
    "Your retained temporary PDF storage is at capacity.", "card_count is outside the configured generation limits.",
    "This Idempotency-Key was already used for a different answer.",
})


def sanitize_validation(errors: list) -> list[dict]:
    """Return field/type hints without submitted values or validator context."""

    result = []
    allowed_types = {"missing", "string_too_short", "string_too_long", "int_parsing", "uuid_parsing", "value_error", "literal_error", "json_invalid", "extra_forbidden", "greater_than_equal", "less_than_equal", "string_type", "list_type", "bool_parsing", "int_type", "uuid_type"}
    for error in errors[:20]:
        if not isinstance(error, dict):
            continue
        error_type = error.get("type")
        safe_type = error_type if isinstance(error_type, str) and error_type in allowed_types else "value_error"
        # Extra JSON keys and UUID/token path values can enter validation loc.
        # Only schema-owned identifiers are permitted; never echo user keys.
        safe_fields = {
            "body", "query", "path", "header", "email", "password", "full_name", "role",
            "token", "invitation_token", "reset_token", "new_password", "refresh_token",
            "subject_id", "set_id", "flashcard_id", "job_id", "id", "title", "description",
            "front_content", "back_content", "options", "card_type", "is_approved", "is_published",
            "time_limit_seconds", "time_limit", "time_limit_per_card", "expires_in_hours", "recipient_email",
            "card_count", "target_count", "requested_card_count", "source_pdf_name", "set_title", "set_description",
            "selected_option", "selected_option_index", "time_spent_seconds", "mode", "limit", "offset",
            "Idempotency-Key", "idempotency-key",
        }
        location = error.get("loc", ())
        safe_location = [part if isinstance(part, str) and part in safe_fields else part if type(part) is int and 0 <= part < 10000 else "field" for part in location[:8]] if isinstance(location, (list, tuple)) else ["field"]
        result.append({"type": safe_type, "loc": safe_location, "msg": "Field required" if safe_type == "missing" else "Invalid value"})
    return result


def _error_response(request: Request, status_code: int, detail, code: str, headers=None) -> JSONResponse:
    request.state.error_code = code
    identifier = getattr(request.state, "request_id", None) or current_request_id()
    response_headers = {}
    for key, value in (headers or {}).items():
        if key.lower() == "www-authenticate" and value == "Bearer":
            response_headers[key] = value
        elif key.lower() == "retry-after" and isinstance(value, str) and re.fullmatch(r"[0-9]{1,6}", value):
            response_headers[key] = value
    if isinstance(identifier, UUID):
        response_headers["X-Request-ID"] = str(identifier)
    response_headers["Cache-Control"] = "no-store"
    return JSONResponse(status_code=status_code, content={"detail": detail, "code": code, "request_id": str(identifier) if identifier else None}, headers=response_headers)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code, detail = DEFAULT_ERRORS.get(exc.status_code, ("request_failed", "The request could not be completed."))
    if isinstance(exc.detail, str) and exc.detail in SAFE_MESSAGES:
        detail = exc.detail
    elif isinstance(exc.detail, str) and re.fullmatch(r"Invitation lifetime must be between [0-9]{1,3} and [0-9]{1,3} hours", exc.detail):
        detail = exc.detail
    elif isinstance(exc.detail, list):
        detail = sanitize_validation(exc.detail)
    elif isinstance(exc.detail, dict):
        # Explicit domain codes mark server-authored safe errors. No arbitrary
        # metadata survives; messages are supplied by the trusted error helper.
        safe_detail = getattr(exc, "safe_detail", None)
        if isinstance(safe_detail, dict):
            domain_code = safe_detail.get("code")
            message = safe_detail.get("message")
            if isinstance(domain_code, str) and domain_code in SAFE_ERROR_CODES:
                code = domain_code
                detail = {"code": code, "message": message if isinstance(message, str) and message in SAFE_DOMAIN_MESSAGES else detail}
    return _error_response(request, exc.status_code, detail, code, exc.headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_response(request, 422, sanitize_validation(exc.errors()), "validation_failed")


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).error("request_failed", extra={"error_code": "internal_error"})
    return _error_response(request, 500, "An unexpected error occurred. Use the request ID when contacting the operator.", "internal_error")


class RequestDiagnosticsMiddleware:
    def __init__(self, app, *, settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        identifier = uuid4()
        context_token = _request_id.set(identifier)
        scope.setdefault("state", {})["request_id"] = identifier
        started = monotonic()
        status_code = 500
        response_started = False

        async def correlated_send(message):
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                message["headers"] = [(key, value) for key, value in message.get("headers", []) if key.lower() != b"x-request-id"] + [(b"x-request-id", str(identifier).encode("ascii"))]
            await send(message)

        try:
            try:
                await self.app(scope, receive, correlated_send)
            except Exception as exc:
                status_code = 500
                response = await unexpected_exception_handler(Request(scope), exc)
                if response_started:
                    raise
                await response(scope, receive, correlated_send)
        finally:
            elapsed = min(2**31 - 1, max(0, int((monotonic() - started) * 1000)))
            error_code = scope["state"].get("error_code")
            if error_code is not None:
                error_code = safe_error_code(error_code)
            diagnostic_fields = {"status_code": status_code, "latency_milliseconds": elapsed, "error_code": error_code}
            job_parameter = scope.get("path_params", {}).get("job_id")
            try:
                if job_parameter is not None:
                    diagnostic_fields["job_id"] = job_parameter if isinstance(job_parameter, UUID) else UUID(job_parameter)
            except (ValueError, TypeError, AttributeError):
                pass
            logging.getLogger(__name__).info("request_completed", extra=diagnostic_fields)
            route = getattr(scope.get("route"), "path", "unmatched")
            application = scope.get("app")
            known_routes = getattr(getattr(application, "router", None), "routes", ())
            if not isinstance(route, str) or len(route) > 160 or scope.get("route") not in known_routes:
                route = "unmatched"
            method = scope.get("method", "OTHER")
            if method not in {"GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"}:
                method = "OTHER"
            try:
                from app.database import async_session_maker
                from app.services.operations import record_request
                factory = getattr(getattr(application, "state", None), "operations_session_factory", async_session_maker)
                await asyncio.wait_for(record_request(factory, identifier, route, method, status_code, elapsed, error_code), timeout=1.0)
            except Exception:
                logging.getLogger(__name__).warning("request_record_failed")
            finally:
                _request_id.reset(context_token)
