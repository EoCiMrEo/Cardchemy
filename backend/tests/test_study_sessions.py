from datetime import timedelta
from uuid import uuid4

from app.main import app
from app.models.flashcard import Enrollment, Flashcard, StudyProgress
from app.models.subject import FlashcardSet, Subject
from app.models.user import User, UserRole
from app.routers.study import get_study_session
from app.services.flashcard import FlashcardService
from app.time_utils import utcnow


def make_card(set_id, *, answer: str = "Correct", approved: bool = True) -> Flashcard:
    return Flashcard(
        id=uuid4(),
        set_id=set_id,
        front_content=f"Question {uuid4()}",
        back_content=answer,
        options=[answer, "Distractor B", "Distractor C", "Distractor D"],
        is_approved=approved,
    )


async def test_review_all_returns_future_cards_in_least_recently_reviewed_order(db):
    set_id = uuid4()
    flashcard_set = FlashcardSet(id=set_id, subject_id=uuid4(), title="Review")
    older = make_card(set_id, answer="Older")
    newer = make_card(set_id, answer="Newer")
    draft = make_card(set_id, answer="Draft", approved=False)
    student_id = uuid4()
    now = utcnow()
    db.add_all(
        [
            flashcard_set,
            older,
            newer,
            draft,
            StudyProgress(
                student_id=student_id,
                flashcard_id=older.id,
                status="learning",
                interval_days=1,
                next_review=now + timedelta(days=1),
                last_reviewed=now - timedelta(days=2),
            ),
            StudyProgress(
                student_id=student_id,
                flashcard_id=newer.id,
                status="learning",
                interval_days=1,
                next_review=now + timedelta(days=1),
                last_reviewed=now - timedelta(days=1),
            ),
        ]
    )
    await db.commit()

    assert await FlashcardService.get_due_cards(db, student_id, set_id) == []
    review_cards = await FlashcardService.get_review_cards(db, student_id, set_id)
    assert [card.id for card in review_cards] == [older.id, newer.id]
    assert [card.id for card in await FlashcardService.get_review_cards(db, student_id, set_id, 1)] == [older.id]


async def test_review_all_router_starts_a_completed_authorized_session(db):
    owner = User(
        id=uuid4(),
        email="review-owner@example.test",
        hashed_password="not-a-password",
        role=UserRole.INSTRUCTOR,
    )
    student = User(
        id=uuid4(),
        email="review-student@example.test",
        hashed_password="not-a-password",
        role=UserRole.STUDENT,
    )
    subject = Subject(id=uuid4(), name="Review course", instructor_id=owner.id)
    flashcard_set = FlashcardSet(
        id=uuid4(),
        subject_id=subject.id,
        title="Completed set",
        is_published=True,
    )
    card = make_card(flashcard_set.id)
    now = utcnow()
    db.add_all(
        [
            owner,
            student,
            subject,
            flashcard_set,
            card,
            Enrollment(student_id=student.id, subject_id=subject.id),
            StudyProgress(
                student_id=student.id,
                flashcard_id=card.id,
                status="learning",
                interval_days=1,
                next_review=now + timedelta(days=1),
                last_reviewed=now,
            ),
        ]
    )
    await db.commit()

    due = await get_study_session(
        flashcard_set.id,
        limit=20,
        mode="due",
        user=student,
        db=db,
    )
    review = await get_study_session(
        flashcard_set.id,
        limit=20,
        mode="review_all",
        user=student,
        db=db,
    )
    assert due.cards == []
    assert [returned.id for returned in review.cards] == [card.id]


def test_study_openapi_requires_idempotency_and_has_no_offline_sync_contract():
    schema = app.openapi()
    progress_operation = schema["paths"]["/study/progress"]["post"]
    idempotency = next(
        parameter
        for parameter in progress_operation["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )
    assert idempotency["in"] == "header"
    assert idempotency["required"] is True
    assert idempotency["schema"]["minLength"] == 8
    assert idempotency["schema"]["maxLength"] == 128
    assert "/study/sync" not in schema["paths"]

    session_parameters = schema["paths"]["/study/sets/{set_id}/session"]["get"]["parameters"]
    mode = next(parameter for parameter in session_parameters if parameter["name"] == "mode")
    assert mode["schema"]["enum"] == ["due", "review_all"]
