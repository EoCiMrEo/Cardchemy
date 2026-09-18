"""Build/verify the reviewed database recipe lazily and return immutable bytes."""
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import subprocess


ROOT = Path(__file__).resolve().parents[1]
RECIPE_LABEL = "org.cardchemy.database.recipe-sha256"


def _environment() -> dict[str, str]:
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
               "HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "PROGRAMDATA",
               "PROGRAMFILES", "PROGRAMFILES(X86)", "CI"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


def _docker(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(["docker", *arguments], cwd=root, env=_environment(),
                            capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError("Reviewed database build/verification failed; Docker details withheld")
    return result


def ensure_database_image(root: Path = ROOT) -> tuple[str, str]:
    """No import side effects; consumers start only the returned immutable ID."""
    root = Path(root).resolve()
    validate = runpy.run_path(str(root / "scripts/check_runtime_artifacts.py"))["validate"]
    database = validate(root)
    if database.get("kind") != "reviewed_local_build":
        raise RuntimeError("Database runtime must use the reviewed local build recipe")
    recipe_hash = database["recipe_sha256"]
    image = database["image"]
    platform = database["supported_platform"]
    inspected = _docker(root, "image", "inspect", image, check=False)
    metadata = json.loads(inspected.stdout)[0] if inspected.returncode == 0 else None
    if (metadata is None or metadata.get("Config", {}).get("Labels", {}).get(RECIPE_LABEL) != recipe_hash
            or f"{metadata.get('Os')}/{metadata.get('Architecture')}" != platform):
        _docker(root, "build", "--platform", platform, "--file", database["recipe_path"],
                "--label", f"{RECIPE_LABEL}={recipe_hash}", "--tag", image,
                str((root / database["recipe_path"]).parent))
        inspected = _docker(root, "image", "inspect", image)
        metadata = json.loads(inspected.stdout)[0]
    identity = metadata.get("Id", "")
    if (not identity.startswith("sha256:") or len(identity) != 71
            or metadata.get("Config", {}).get("Labels", {}).get(RECIPE_LABEL) != recipe_hash
            or f"{metadata.get('Os')}/{metadata.get('Architecture')}" != platform):
        raise RuntimeError("Reviewed database recipe identity/platform verification failed")
    probe = """
        test "$(postgres --version)" = "postgres (PostgreSQL) 16.15"
        pg_config --configure | grep -F -- --with-icu >/dev/null
        test -f /usr/local/lib/postgresql/vector.so
        grep -Fqx "default_version = '0.8.6'" /usr/local/share/postgresql/extension/vector.control
        test "$(readlink /usr/local/bin/gosu)" = /sbin/su-exec
        test "$(gosu postgres id -u)" = "$(id -u postgres)"
        test "$(gosu postgres id -g)" = "$(id -g postgres)"
        expected_groups="$(id -G postgres)"
        export expected_groups
        probe_marker='two words $literal'
        export probe_marker
        gosu postgres sh -ec '
            test "$(id -G)" = "$expected_groups"
            test "$#" = 3
            test "$1" = "$probe_marker"
            test -z "$2"
            test "$3" = "tail words"
        ' -- "$probe_marker" "" "tail words"
        test "$POSTGRES_INITDB_ARGS" = "--encoding=UTF8 --locale-provider=icu --icu-locale=en-US"
        test ! -x /usr/bin/gcc
    """
    _docker(root, "run", "--rm", "--network", "none", "--platform", platform,
            "--entrypoint", "sh", identity, "-ec", probe)
    return identity, platform


if __name__ == "__main__":
    identity, platform = ensure_database_image()
    print(f"Reviewed database recipe verified: {identity} ({platform}).")
