from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.flashcard import Enrollment, Flashcard, StudyProgress
from app.models.subject import FlashcardSet, Subject
from app.models.user import User, UserRole
from app.routers.auth import get_current_instructor, get_current_student
from app.routers.flashcards import create_flashcard, get_flashcard
from app.routers.study import update_study_progress
from app.routers.subjects import create_flashcard_set
from app.schemas.flashcard import FlashcardCreateRequest, StudyProgressUpdate
from app.schemas.subject import FlashcardSetCreateRequest
from app.services.auth import AuthService
from app.services.subject import SubjectService


def user(email: str, role: UserRole) -> User:
    return User(
        id=uuid4(),
        email=email,
        hashed_password=AuthService.hash_password("password value"),
        role=role,
    )


async def test_explicit_role_dependencies_reject_the_other_role():
    instructor = user("instructor@example.com", UserRole.INSTRUCTOR)
    student = user("student@example.com", UserRole.STUDENT)
    with pytest.raises(HTTPException) as instructor_error:
        await get_current_instructor(student)
    with pytest.raises(HTTPException) as student_error:
        await get_current_student(instructor)
    assert instructor_error.value.status_code == 403
    assert student_error.value.status_code == 403


async def test_cross_subject_access_is_denied(db):
    owner = user("owner@example.com", UserRole.INSTRUCTOR)
    outsider = user("outsider@example.com", UserRole.INSTRUCTOR)
    student = user("student@example.com", UserRole.STUDENT)
    subject = Subject(id=uuid4(), name="Private", instructor_id=owner.id)
    db.add_all([owner, outsider, student, subject])
    await db.commit()

    for actor in (outsider, student):
        with pytest.raises(HTTPException) as exc:
            await SubjectService.check_subject_access(db, subject.id, actor)
        assert exc.value.status_code == 403

        with pytest.raises(HTTPException) as mutation_exc:
            await SubjectService.check_subject_access(db, subject.id, actor, require_owner=True)
        assert mutation_exc.value.status_code == 403

    db.add(Enrollment(student_id=student.id, subject_id=subject.id))
    await db.commit()
    assert await SubjectService.check_subject_access(db, subject.id, student) == subject


async def test_path_scoped_create_routes_supply_parent_ids(db):
    owner = user("path-owner@example.com", UserRole.INSTRUCTOR)
    subject = Subject(id=uuid4(), name="Path contracts", instructor_id=owner.id)
    db.add_all([owner, subject])
    await db.commit()

    flashcard_set = await create_flashcard_set(
        subject.id,
        FlashcardSetCreateRequest(title="Route-owned subject"),
        owner,
        db,
    )
    assert flashcard_set.subject_id == subject.id

    flashcard = await create_flashcard(
        flashcard_set.id,
        FlashcardCreateRequest(
            front_content="Which ID belongs in the request path?",
            back_content="The parent ID",
            options=["The parent ID", "A child ID", "No ID", "Every ID"],
        ),
        owner,
        db,
    )
    assert flashcard.set_id == flashcard_set.id
    assert flashcard.back_content == "The parent ID"


async def test_progress_requires_enrollment_publication_and_approval(db):
    owner = user("owner@example.com", UserRole.INSTRUCTOR)
    student = user("student@example.com", UserRole.STUDENT)
    subject = Subject(id=uuid4(), name="Private", instructor_id=owner.id)
    flashcard_set = FlashcardSet(
        id=uuid4(),
        subject_id=subject.id,
        title="Set",
        is_published=True,
    )
    card = Flashcard(
        id=uuid4(),
        set_id=flashcard_set.id,
        front_content="Question",
        back_content="Answer",
        options=["Answer", "Distractor 1", "Distractor 2", "Distractor 3"],
        is_approved=True,
    )
    db.add_all([owner, student, subject, flashcard_set, card])
    await db.commit()
    data = StudyProgressUpdate(flashcard_id=card.id, selected_option="Answer")

    with pytest.raises(HTTPException) as unenrolled:
        await update_study_progress(data, student, db)
    assert unenrolled.value.status_code == 403

    db.add(Enrollment(student_id=student.id, subject_id=subject.id))
    await db.commit()
    card.is_approved = False
    await db.commit()
    with pytest.raises(HTTPException) as unapproved:
        await update_study_progress(data, student, db)
    assert unapproved.value.status_code == 404

    card.is_approved = True
    flashcard_set.is_published = False
    await db.commit()
    with pytest.raises(HTTPException) as unpublished:
        await update_study_progress(data, student, db)
    assert unpublished.value.status_code == 404

    count = await db.scalar(select(func.count()).select_from(StudyProgress))
    assert count == 0


async def test_student_cannot_read_an_approved_card_from_an_unpublished_set(db):
    owner = user("owner-unpublished@example.com", UserRole.INSTRUCTOR)
    student = user("student-unpublished@example.com", UserRole.STUDENT)
    subject = Subject(id=uuid4(), name="Private draft", instructor_id=owner.id)
    flashcard_set = FlashcardSet(
        id=uuid4(),
        subject_id=subject.id,
        title="Draft",
        is_published=False,
    )
    card = Flashcard(
        id=uuid4(),
        set_id=flashcard_set.id,
        front_content="Question",
        back_content="Answer",
        options=["Answer", "Distractor 1", "Distractor 2", "Distractor 3"],
        is_approved=True,
    )
    db.add_all([owner, student, subject, flashcard_set, card])
    await db.commit()
    db.add(Enrollment(student_id=student.id, subject_id=subject.id))
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await get_flashcard(card.id, student, db)
    assert exc.value.status_code == 404
