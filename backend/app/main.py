"""
main.py - FastAPI Application Entry Point

This is the main file that creates and configures the FastAPI application.
It:
- Creates the FastAPI app with metadata
- Sets up CORS (Cross-Origin Resource Sharing) for frontend
- Registers all routers
- Provides startup/shutdown event handlers
- Verifies that Alembic migrations were applied before startup

To run the application:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

The --reload flag enables hot reloading during development.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import verify_database_revision
from app.routers import (
    auth_router,
    flashcards_router,
    generation_router,
    study_router,
    subjects_router,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown events.
    
    Startup:
    - Verify the database is at the current Alembic revision
    - Any other setup (e.g., connecting to external services)
    
    Shutdown:
    - Clean up resources
    """
    # Startup
    print("🚀 Starting Flashcard Generator API...")
    await verify_database_revision()
    print("✅ Database migration revision verified")
    
    yield  # Application runs here
    
    # Shutdown
    print("👋 Shutting down...")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="""
    ## AI-Powered Flashcard Generator
    
    A platform for instructors to create and manage flashcard sets from PDFs,
    and for students to study using spaced repetition.
    
    ### Features
    - 📄 Upload PDFs and generate flashcards using AI
    - 👥 Invite students via unique links
    - 📚 Organize content by subjects and sets
    - 🧠 Spaced repetition for optimal learning
    - 📱 Mobile-friendly PWA with offline support
    
    ### Authentication
    Use the `/auth/login` endpoint to get a JWT token, then click
    "Authorize" above and enter: `Bearer <your_token>`
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",      # Swagger UI at /docs
    redoc_url="/redoc",    # ReDoc at /redoc
)


# ============================================
# CORS Configuration
# ============================================
# CORS allows the frontend (running on a different port/domain)
# to make requests to this API.

app.add_middleware(
    CORSMiddleware,
    # In development, allow requests from the frontend dev server
    # In production, replace with your actual frontend domain
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,  # Allow cookies/auth headers
    allow_methods=["*"],     # Allow all HTTP methods
    allow_headers=["*"],     # Allow all headers
)


# ============================================
# Register Routers
# ============================================
# Each router handles a group of related endpoints

app.include_router(auth_router)       # /auth/*
app.include_router(subjects_router)   # /subjects/*
# Static generation routes must precede ``/flashcards/{flashcard_id}`` or
# FastAPI will try to parse "generation-limits" and "generation-jobs" as UUIDs.
app.include_router(generation_router) # /flashcards/generation-*
app.include_router(flashcards_router) # /flashcards/*
app.include_router(study_router)      # /study/*


# ============================================
# Root Endpoint
# ============================================

@app.get("/", tags=["Health"])
async def root():
    """
    Root endpoint - basic health check.
    
    Returns API info and status.
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Used by Docker/Kubernetes to verify the container is healthy.
    """
    return {"status": "healthy"}
