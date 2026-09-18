"""Historic password-record compatibility without a Passlib runtime dependency."""
import json
from pathlib import Path

import bcrypt
import pytest

from app.services import passwords
from app.services.auth import AuthService


HISTORIC = json.loads((Path(__file__).parent / "fixtures/password_hashes.json").read_text())["cases"]
# Independent known vectors published in Passlib 1.7.4's bcrypt handler tests.
KNOWN = [
    ("password", "$bcrypt-sha256$2a,5$5Hg1DKFqPE8C2aflZ5vVoe$12BjNE0p7axMg55.Y/mHsYiVuFBDQyu"),
    ("password", "$bcrypt-sha256$2b,5$5Hg1DKFqPE8C2aflZ5vVoe$12BjNE0p7axMg55.Y/mHsYiVuFBDQyu"),
    ("password", "$bcrypt-sha256$v=2,t=2b,r=5$5Hg1DKFqPE8C2aflZ5vVoe$wOK1VFFtS8IGTrGa7.h5fs0u84qyPbS"),
    ("abc123" * 12 + "qwr", "$bcrypt-sha256$2b,5$X1g1nh3g0v4h6970O68cxe$021KLEif6epjot5yoxk0m8I0929ohEa"),
    ("abc123" * 12 + "qwr", "$bcrypt-sha256$v=2,t=2b,r=5$X1g1nh3g0v4h6970O68cxe$CBF9csfEdW68xv3DwE6xSULXMtqEFP."),
    ("U*U*U*U*", "$2a$05$c92SVSfjeiCD6F2nAD6y0uBpJDjdRkt0EgeC4/31Rf2LUZbDRDE.O"),
    ("abc", "$2$05$......................XuQjdH.wPVNUZ/bOfstdW/FqB8QSjte"),
    ("", "$2$05$......................J2ihDv8vVf7QZ9BsaRrKyqs2tkn55Yq"),
]


@pytest.mark.parametrize("password,record", KNOWN)
def test_known_historic_vectors(password, record):
    assert AuthService.verify_password(password, record)
    assert not AuthService.verify_password("wrong" + password, record)


@pytest.mark.parametrize("case", HISTORIC, ids=lambda case: case["id"])
def test_records_created_by_prior_runtime(case):
    password, record = case["password"], case["hash"]
    assert AuthService.verify_password(password, record)
    assert not AuthService.verify_password("!" + password, record)
    if record.startswith("$bcrypt-sha256$"):
        assert not AuthService.verify_password(password + "wrong suffix", record)
        assert not AuthService.verify_password(password[:-1], record)


def test_new_hash_matches_published_passlib_v2_vector(monkeypatch):
    # The salt and record are from the official algorithm documentation, so this
    # establishes interoperability rather than testing only our own round trip.
    def fixed_salt(*, rounds, prefix):
        assert rounds == 12 and prefix == b"2b"
        return b"$2b$12$n79VH.0Q2TMWmt3Oqt9uku"

    monkeypatch.setattr(passwords.bcrypt, "gensalt", fixed_salt)
    assert AuthService.hash_password("password") == (
        "$bcrypt-sha256$v=2,t=2b,r=12$n79VH.0Q2TMWmt3Oqt9uku$Kq4Noyk3094Y2QlB8NdRT8SvGiI4ft2"
    )


def test_new_password_hash_uses_random_salt_and_full_utf8_password():
    password = "\U0001f9ea" * 120 + "\0suffix"
    first, second = AuthService.hash_password(password), AuthService.hash_password(password)
    assert first != second
    assert first.startswith("$bcrypt-sha256$v=2,t=2b,r=12$")
    assert AuthService.verify_password(password, first)
    assert not AuthService.verify_password(password[:-1] + "!", first)
    assert not AuthService.verify_password(password[:72], first)


@pytest.mark.parametrize("variant", ["2a", "2b", "2y"])
def test_raw_bcrypt_retains_historical_utf8_byte_truncation(variant):
    case = next(case for case in HISTORIC if case["id"] == "utf8_boundary_raw_" + variant)
    assert AuthService.verify_password(case["password"] + "changed suffix", case["hash"])
    # The NUL policy applies to the whole input, including bytes beyond 72.
    assert not AuthService.verify_password(case["password"] + "\0", case["hash"])


@pytest.mark.parametrize("record", [KNOWN[0][1], KNOWN[2][1], KNOWN[5][1]])
def test_noncanonical_bcrypt64_padding_retains_passlib_compatibility(record):
    password = "U*U*U*U*" if record.startswith("$2a$") else "password"
    # Passlib repairs unused salt/checksum bits before calculating/verifying.
    if record.startswith("$bcrypt-sha256$"):
        prefix, salt, digest = record.rsplit("$", 2)
        salt = salt[:-1] + "f"  # same significant bits as canonical 'e'
        digest = digest[:-1] + passwords._ALPHABET[passwords._ALPHABET.index(digest[-1]) + 1]
        altered = f"{prefix}${salt}${digest}"
    else:
        altered = record[:-1] + "P"  # same significant bits as canonical 'O'
    assert AuthService.verify_password(password, altered)


_VALID = KNOWN[2][1]
@pytest.mark.parametrize("record", [
    "", "garbage", None, b"bytes", "\ud800", _VALID + "\n", _VALID + "suffix",
    _VALID.replace("v=2", "v=1"), _VALID.replace("v=2", "v=3"),
    _VALID.replace("t=2b", "t=2a"), _VALID.replace("t=2b", "t=2x"),
    _VALID.replace("r=5", "r=05"), _VALID.replace("r=5", "r=3"), _VALID.replace("r=5", "r=32"),
    _VALID.replace("5Hg1", "5!g1"), _VALID[:-1], _VALID.rsplit("$", 1)[0],
    KNOWN[0][1].replace("2a,5", "2a,05"), KNOWN[0][1].replace("2a,5", "2y,5"),
    KNOWN[5][1].replace("$2a$", "$2x$"), KNOWN[5][1].replace("$05$", "$5$"),
])
def test_invalid_records_fail_before_backend_call(record, monkeypatch):
    monkeypatch.setattr(bcrypt, "checkpw", lambda *args: pytest.fail("Malformed hash reached bcrypt"))
    assert not AuthService.verify_password("password", record)


@pytest.mark.parametrize("password", [None, b"bytes", "\ud800"])
def test_invalid_password_inputs_fail_closed(password):
    assert not AuthService.verify_password(password, _VALID)


def test_backend_invalid_value_fails_without_disclosing_input(monkeypatch, caplog):
    def failing_backend(*args):
        raise ValueError("internal password/hash diagnostic")

    monkeypatch.setattr(bcrypt, "checkpw", failing_backend)
    assert not AuthService.verify_password("password", _VALID)
    assert not caplog.records
