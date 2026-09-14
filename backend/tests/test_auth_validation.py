import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate, UserLogin


def test_email_is_trimmed_and_normalized():
    created = UserCreate(email="  Student@Example.COM ", password="password value")
    login = UserLogin(email="  Student@Example.COM ", password="password value")
    assert str(created.email) == "student@example.com"
    assert str(login.email) == "student@example.com"


@pytest.mark.parametrize("length", [7, 129])
def test_password_length_is_bounded(length):
    with pytest.raises(ValidationError):
        UserCreate(email="student@example.com", password="x" * length)
