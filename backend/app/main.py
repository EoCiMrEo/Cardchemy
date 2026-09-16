"""FastAPI application and production-aware runtime lifecycle."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.database import check_database_readiness, close_database, verify_database_revision
from app.routers import (
    auth_router,
    flashcards_router,
    generation_router,
    study_router,
    subjects_router,
)


CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
CORS_ALLOWED_HEADERS = ["Accept", "Authorization", "Content-Type", "Idempotency-Key"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Verify migrations on startup and close pooled connections on exit."""

    print("🚀 Starting Flashcard Generator API...")
    try:
        await verify_database_revision()
        print("✅ Database migration revision verified")
        yield
    finally:
        await close_database()
        print("👋 Shutting down...")


def create_app(app_settings: Settings | None = None) -> FastAPI:
    """Build an application using validated runtime settings."""

    configured = app_settings or get_settings()
    docs_enabled = configured.api_docs_are_enabled
    application = FastAPI(
        title=configured.app_name,
        description="""
        ## AI-Powered Flashcard Generator

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
    )

    application.include_router(auth_router)
    application.include_router(subjects_router)
    # Static generation routes must precede ``/flashcards/{flashcard_id}`` or
    # FastAPI will try to parse static route names as UUIDs.
    application.include_router(generation_router)
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
