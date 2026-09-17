import json
import os
from uuid import uuid4

import pytest

from app import cli
from tests.support.privacy_fixtures import seed_private_course


async def test_export_is_private_non_overwriting_and_omits_content_from_stdout(session_factory, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(cli, "async_session_maker", session_factory)
    async with session_factory() as db:
        course = await seed_private_course(db)
        await db.commit()
        account_id = course.owner.id
    target = tmp_path / "private-account.json"
    await cli.export_account_file(account_id, target)
    result = json.loads(capsys.readouterr().out)
    assert result == {"event": "account_exported", "account_id": str(account_id)}
    original = target.read_bytes()
    exported = json.loads(original)
    assert exported["profile"]["id"] == str(account_id)
    assert exported["cards"][0]["front_content"] == "Authored fact?"
    assert "DO_NOT_EXPORT_PASSWORD" not in original.decode()
    if os.name != "nt":
        assert target.stat().st_mode & 0o777 == 0o600
    else:
        import subprocess
        permissions = subprocess.run(["icacls", str(target)], capture_output=True, text=True, check=True).stdout
        assert "(I)" not in permissions  # Inherited access was removed before writing.
    with pytest.raises(FileExistsError):
        await cli.export_account_file(account_id, target)
    assert target.read_bytes() == original


@pytest.mark.parametrize("apply,writers_stopped", [(False, False), (False, True), (True, False)])
async def test_delete_account_requires_both_operator_acknowledgements(apply, writers_stopped):
    with pytest.raises(SystemExit, match="--apply --writers-stopped"):
        await cli.remove_account(uuid4(), apply=apply, writers_stopped=writers_stopped)


async def test_instructor_validation_error_does_not_echo_password_or_email(monkeypatch, capsys):
    secret = "PRIVATE_PASSWORD_SENTINEL_" * 10
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: secret)
    with pytest.raises(SystemExit) as failure:
        await cli.create_instructor("PRIVATE_EMAIL_SENTINEL", None, True)
    assert str(failure.value) == "Invalid instructor account fields"
    assert secret not in str(failure.value)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("entry", ["app.main", "app.cli", "app.worker", "app.email_worker"])
def test_invalid_startup_does_not_dump_configuration_or_traceback(entry):
    import subprocess
    import sys
    environment = os.environ.copy()
    environment.update({"ENVIRONMENT": "test", "DATABASE_URL": "PRIVATE_INVALID_DATABASE_SENTINEL",
                        "SECRET_KEY": "test-only-secret-with-adequate-entropy-1234567890",
                        "GENERATION_SOURCE_ENCRYPTION_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"})
    command = [sys.executable, "-c", "import app.main"] if entry == "app.main" else [sys.executable, "-m", entry]
    result = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=30)
    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "PRIVATE_INVALID_DATABASE_SENTINEL" not in output
    assert "Traceback" not in output
