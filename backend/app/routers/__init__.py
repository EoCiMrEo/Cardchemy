# Routers package
from app.routers.auth import router as auth_router
from app.routers.subjects import router as subjects_router
from app.routers.flashcards import router as flashcards_router
from app.routers.study import router as study_router
from app.routers.generation import router as generation_router
from app.routers.rag import router as rag_router
from app.routers.knowledge import router as knowledge_router

__all__ = [
    "auth_router",
    "subjects_router",
    "flashcards_router",
    "study_router",
    "generation_router",
    "rag_router",
    "knowledge_router",
]
