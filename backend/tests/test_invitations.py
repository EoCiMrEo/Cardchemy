from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.flashcard import Enrollment
from app.models.subject import Subject
from app.models.user import InviteLink, User, UserRole
from app.routers.auth import register
from app.routers.subjects import join_course_with_token
from app.schemas.user import InvitationAccept, InvitationAcceptResponse, UserRegister
from app.services.auth import AuthService


async def seed_instructor_subject(db):
    instructor = User(
        id=uuid4(),
        email="instructor@example.com",
        hashed_password=AuthService.hash_password("instructor password"),
        role=UserRole.INSTRUCTOR,
    )
    subject = Subject(id=uuid4(), name="Security", instructor_id=instructor.id)
    db.add_all([instructor, subject])
    await db.commit()
    return instructor, subject


async def test_registration_and_enrollment_are_atomic(db):
    await seed_instructor_subject(db)
    data = UserRegister(
        email="new@example.com",
        password="student password",
        invite_token="x" * 20,
    )
    with pytest.raises(HTTPException):
        await register(data, db)
    await db.rollback()
    assert await AuthService.get_user_by_email(db, "new@example.com") is None


async def test_invitation_is_typed_single_use_and_enrolls_student(db):
    instructor, subject = await seed_instructor_subject(db)
    invite, token = await AuthService.create_invitation(db, instructor.id, subject.id, 24)
    await db.commit()
    student = User(
        id=uuid4(),
        email="student@example.com",
        hashed_password=AuthService.hash_password("student password"),
        role=UserRole.STUDENT,
    )
    other = User(
        id=uuid4(),
        email="other@example.com",
        hashed_password=AuthService.hash_password("student password"),
        role=UserRole.STUDENT,
    )
    db.add_all([student, other])
    await db.commit()

    consumed = await AuthService.consume_invitation(db, token, student)
    await db.commit()
    assert consumed.id == invite.id
    enrollment = await db.scalar(
        select(Enrollment).where(Enrollment.student_id == student.id, Enrollment.subject_id == subject.id)
    )
    assert enrollment is not None

    replay = await join_course_with_token(InvitationAccept(token=token), student, db)
    assert isinstance(replay, InvitationAcceptResponse)
    assert replay.message == "Successfully joined course"
    assert replay.subject_name == subject.name
    enrollment_count = await db.scalar(
        select(func.count(Enrollment.id)).where(
            Enrollment.student_id == student.id,
            Enrollment.subject_id == subject.id,
        )
    )
    assert enrollment_count == 1

    with pytest.raises(HTTPException) as exc:
        await AuthService.consume_invitation(db, token, other)
    assert exc.value.status_code == 409
    stored = await db.scalar(select(InviteLink).where(InviteLink.id == invite.id))
    assert stored.used_by == student.id


async def test_instructor_cannot_consume_student_invitation(db):
    instructor, subject = await seed_instructor_subject(db)
    _, token = await AuthService.create_invitation(db, instructor.id, subject.id, 24)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await AuthService.consume_invitation(db, token, instructor)
    assert exc.value.status_code == 403


@pytest.mark.parametrize("hours", [0, -1, 721, 1000000])
async def test_invitation_lifetime_is_bounded(db, hours):
    instructor, subject = await seed_instructor_subject(db)
    with pytest.raises(HTTPException) as exc:
        await AuthService.create_invitation(db, instructor.id, subject.id, hours)
    assert exc.value.status_code == 422
