"""FastAPI application and production-aware runtime lifecycle."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.observability import (
    RequestDiagnosticsMiddleware,
    configure_logging,
    http_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)
configure_logging()
try:
    from app.config import Settings, get_settings
    from app.database import check_database_readiness, close_database, verify_database_revision
    from app.routers import (
        auth_router,
        flashcards_router,
        generation_router,
        knowledge_router,
        rag_router,
        study_router,
        subjects_router,
    )
except Exception:
    logging.getLogger(__name__).critical("process_failed", extra={"kind": "api"})
    raise SystemExit("Application startup failed; validate root configuration and runtime dependencies") from None


CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
CORS_ALLOWED_HEADERS = ["Accept", "Authorization", "Content-Type", "Idempotency-Key"]
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Verify migrations on startup and close pooled connections on exit."""

    logger.info("api_started")
    try:
        await verify_database_revision()
        logger.info("database_revision_verified")
        yield
    finally:
        await close_database()
        logger.info("api_stopped")


def create_app(app_settings: Settings | None = None) -> FastAPI:
    """Build an application using validated runtime settings."""

    configured = app_settings or get_settings()
    configure_logging(configured.log_level)
    docs_enabled = configured.api_docs_are_enabled
    application = FastAPI(
        title=configured.app_name,
        description="""
        ## Cardchemy

        Turn documents into memory.

        A platform for instructors to create and manage flashcard sets from PDFs,
        and for students to study using spaced repetition.

        ### Features
        - 📄 Upload PDFs and generate flashcards using AI
        - 👥 Invite students via unique links
        - 📚 Organize content by subjects and sets
        - 🧠 Spaced repetition for optimal learning
        - 📱 Responsive browser-based study experience

        ### Authentication
        Use the `/auth/login` endpoint to get a JWT token, then click
        "Authorize" above and enter: `Bearer <your_token>`
        """,
        version=configured.app_version,
        lifespan=lifespan,
        root_path=configured.api_root_path,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_origin_list,
        allow_credentials=True,
        allow_methods=CORS_ALLOWED_METHODS,
        allow_headers=CORS_ALLOWED_HEADERS,
        expose_headers=["X-Request-ID"],
    )
    application.add_middleware(RequestDiagnosticsMiddleware, settings=configured)
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(Exception, unexpected_exception_handler)

    application.include_router(auth_router)
    application.include_router(subjects_router)
    # Static generation routes must precede ``/flashcards/{flashcard_id}`` or
    # FastAPI will try to parse static route names as UUIDs.
    application.include_router(generation_router)
    application.include_router(knowledge_router)
    application.include_router(rag_router)
    application.include_router(flashcards_router)
    application.include_router(study_router)

    @application.get("/", tags=["Health"])
    async def root() -> dict[str, str]:
        response = {
            "name": configured.app_name,
            "version": configured.app_version,
            "status": "running",
        }
        if docs_enabled:
            response["docs"] = f"{configured.api_root_path}/docs"
        return response

    @application.get("/health/live", tags=["Health"])
    async def liveness_check() -> dict[str, str]:
        return {"status": "healthy"}

    async def readiness_check() -> JSONResponse:
        try:
            await check_database_readiness()
        except Exception:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy"},
            )
        return JSONResponse(content={"status": "healthy"})

    application.add_api_route(
        "/health/ready",
        readiness_check,
        methods=["GET"],
        tags=["Health"],
    )
    # Preserve the original container-health URL while upgrading its semantics
    # from process-only liveness to database-aware readiness.
    application.add_api_route(
        "/health",
        readiness_check,
        methods=["GET"],
        tags=["Health"],
    )

    return application


settings = get_settings()
app = create_app(settings)
