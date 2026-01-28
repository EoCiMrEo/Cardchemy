"""
flashcards.py - Flashcards Router

API endpoints for managing individual flashcards.

Endpoints:
- GET /flashcards/sets/{set_id}/cards - List cards in a set
- POST /flashcards/sets/{set_id}/cards - Create a card manually
- GET /flashcards/{id} - Get a single flashcard
- PUT /flashcards/{id} - Update a flashcard
- DELETE /flashcards/{id} - Delete a flashcard
- POST /flashcards/sets/{set_id}/approve-all - Approve all cards
- POST /flashcards/generate - Generate cards from PDF (AI)
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.routers.auth import get_current_user, get_current_instructor
from app.schemas.flashcard import (
    FlashcardCreate,
    FlashcardUpdate,
    FlashcardResponse,
)
from app.services.flashcard import FlashcardService
from app.services.subject import SubjectService

router = APIRouter(prefix="/flashcards", tags=["Flashcards"])


# ============================================
# CRUD Endpoints
# ============================================

@router.get("/sets/{set_id}/cards", response_model=List[FlashcardResponse])
async def list_flashcards(
    set_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all flashcards in a set.
    
    - Instructors see all cards (including unapproved)
    - Students only see approved cards
    """
    # Get the set to verify access
    flashcard_set = await SubjectService.get_flashcard_set(db, set_id)
    if not flashcard_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    # Check subject access
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user)
    
    # Students can only see published sets
    if user.role == UserRole.STUDENT and not flashcard_set.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    only_approved = user.role == UserRole.STUDENT
    flashcards = await FlashcardService.get_set_flashcards(db, set_id, only_approved)
    
    return flashcards


@router.post("/sets/{set_id}/cards", response_model=FlashcardResponse, status_code=status.HTTP_201_CREATED)
async def create_flashcard(
    set_id: UUID,
    data: FlashcardCreate,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually create a flashcard.
    
    Manually created cards are auto-approved since the instructor
    is explicitly adding them.
    """
    # Verify access
    flashcard_set = await SubjectService.get_flashcard_set(db, set_id)
    if not flashcard_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user, require_owner=True)
    
    # Override set_id from path
    data.set_id = set_id
    
    # Manually created = auto-approved with high confidence
    flashcard = await FlashcardService.create_flashcard(
        db, data, confidence_score=1.0
    )
    
    return flashcard


@router.get("/{flashcard_id}", response_model=FlashcardResponse)
async def get_flashcard(
    flashcard_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a single flashcard by ID."""
    flashcard = await FlashcardService.get_flashcard(db, flashcard_id)
    
    if not flashcard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found"
        )
    
    # Get parent set to check access
    flashcard_set = await SubjectService.get_flashcard_set(db, flashcard.set_id)
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user)
    
    # Students can only see approved cards
    if user.role == UserRole.STUDENT and not flashcard.is_approved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found"
        )
    
    return flashcard


@router.put("/{flashcard_id}", response_model=FlashcardResponse)
async def update_flashcard(
    flashcard_id: UUID,
    data: FlashcardUpdate,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a flashcard.
    
    Use this to edit AI-generated cards or approve them.
    """
    flashcard = await FlashcardService.get_flashcard(db, flashcard_id)
    
    if not flashcard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found"
        )
    
    # Verify ownership
    flashcard_set = await SubjectService.get_flashcard_set(db, flashcard.set_id)
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user, require_owner=True)
    
    updated = await FlashcardService.update_flashcard(db, flashcard, data)
    return updated


@router.delete("/{flashcard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flashcard(
    flashcard_id: UUID,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """Delete a flashcard."""
    flashcard = await FlashcardService.get_flashcard(db, flashcard_id)
    
    if not flashcard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard not found"
        )
    
    # Verify ownership
    flashcard_set = await SubjectService.get_flashcard_set(db, flashcard.set_id)
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user, require_owner=True)
    
    await FlashcardService.delete_flashcard(db, flashcard)
    return None


# ============================================
# Bulk Operations
# ============================================

@router.post("/sets/{set_id}/approve-all")
async def approve_all_flashcards(
    set_id: UUID,
    min_confidence: float = 0.0,
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Approve all flashcards in a set (optionally above a confidence threshold).
    
    Query params:
        - min_confidence: Only approve cards with confidence >= this value (0.0-1.0)
    
    Returns:
        Number of cards approved
    """
    # Verify access
    flashcard_set = await SubjectService.get_flashcard_set(db, set_id)
    if not flashcard_set:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flashcard set not found"
        )
    
    await SubjectService.check_subject_access(db, flashcard_set.subject_id, user, require_owner=True)
    
    count = await FlashcardService.approve_all_flashcards(db, set_id, min_confidence)
    
    return {"approved_count": count}


# ============================================
# AI Generation (placeholder - will be implemented in agents module)
# ============================================

@router.post("/generate")
async def generate_flashcards(
    subject_id: UUID = Form(...),
    set_title: str = Form(...),
    set_description: str = Form(None),
    card_count: int = Form(20),
    pdf_file: UploadFile = File(...),
    user: User = Depends(get_current_instructor),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate flashcards from a PDF using AI.
    
    This endpoint:
    1. Creates a new FlashcardSet
    2. Extracts text from the PDF
    3. Uses LangGraph agents to generate Q&A pairs
    4. Saves generated flashcards (some auto-approved, some for review)
    """
    # Verify access
    await SubjectService.check_subject_access(db, subject_id, user, require_owner=True)
    
    # Validate file
    if not pdf_file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    # 1. Create the FlashcardSet first (so we have an ID)
    from app.schemas.subject import FlashcardSetCreate
    set_data = FlashcardSetCreate(
        subject_id=subject_id,
        title=set_title,
        description=set_description
    )
    
    flashcard_set = await SubjectService.create_flashcard_set(
        db, set_data, source_pdf_name=pdf_file.filename
    )
    
    try:
        # 2. Extract Text from PDF
        from app.services.pdf_processor import PDFProcessor
        content = await pdf_file.read()
        full_text = PDFProcessor.extract_text_from_bytes(content)
        
        # Chunk text (simple chunking for now, can be improved)
        # We limit to first 15k chars for MVP to avoid token limits/timeouts
        # In prod, this would be a background job (Celery/RQ)
        # UPDATED: Map-Reduce now handles large texts, removing 15k limit.
        text_to_process = full_text 
        
        if not text_to_process.strip():
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract text from PDF. It might be an image-only scan."
            )

        # 3. Run AI Pipeline (LangGraph)
        from app.agents.graph import create_flashcard_graph
        graph = create_flashcard_graph()
        
        # Initialize state - just pass the full text, the graph splitter will handle chunks
        initial_state = {
            "pdf_text": text_to_process,
            "chunks": [],
            "mapped_generated_cards": [],
            "final_cards": [],
            "errors": [],
            "target_count": card_count,
            "summary": ""
        }
        
        # Invoke the graph
        result_state = await graph.ainvoke(initial_state)
        
        print(f"🏁 Graph finished. Keys in result: {result_state.keys()}")
        if 'final_cards' in result_state:
             print(f"🃏 Final cards count: {len(result_state['final_cards'])}")
        
        # Check for errors from the graph
        if result_state.get('errors'):
            error_msg = "; ".join(result_state['errors'])
            print(f"❌ Graph returned errors: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI generation failed: {error_msg}"
            )

        # 4. Save Results
        final_cards = result_state.get("final_cards", [])
        
        # Batch create in DB
        # Map agent output to DB schema
        cards_data = []
        auto_approved_count = 0
        
        for card in final_cards:
            # Check for high confidence
            confidence = card.get('confidence', 0.5)
            if confidence >= 0.7:
                auto_approved_count += 1
            
            cards_data.append({
                "front_content": card['front'],
                "back_content": card['back'],
                "options": card.get('options'),
                "confidence_score": confidence,
                "source_chunk": card.get('source', '')[:500] # Truncate source if too long
            })
            
        created_cards = await FlashcardService.create_flashcards_bulk(
            db, cards_data, flashcard_set.id
        )
        
        return {
            "flashcard_set": flashcard_set,
            "flashcards": created_cards,
            "total_generated": len(created_cards),
            "auto_approved": auto_approved_count,
            "needs_review": len(created_cards) - auto_approved_count
        }
        
    except Exception as e:
        # If AI fails, still return the empty set but logic error
        print(f"AI Generation Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI generation failed: {str(e)}"
        )
