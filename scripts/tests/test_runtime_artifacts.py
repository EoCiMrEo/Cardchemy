"""Critical external-image source contracts reject identity/platform drift."""
from __future__ import annotations

import json
from pathlib import Path
import runpy

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
VALIDATE = runpy.run_path(str(ROOT / "scripts/check_runtime_artifacts.py"))["validate"]


@pytest.fixture
def artifact_root(tmp_path):
    for name in ("runtime-artifacts.json", "docker-compose.yml", ".github/workflows/ci.yml",
                 "docker/database/Dockerfile", "docker/database/database-entrypoint.sh",
                 "docker/database/verify-initial-profile.sh", "docker/database/.dockerignore",
                 "docker/database/.gitattributes"):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((ROOT / name).read_bytes())
    return tmp_path


def test_reviewed_identity_matches_source(artifact_root):
    assert VALIDATE(artifact_root)["postgres_major"] == 16


@pytest.mark.parametrize("scope", ["compose_image", "compose_platform", "volume", "ci_image", "ci_platform"])
def test_drift_is_rejected_before_external_runtime_use(artifact_root, scope):
    path = artifact_root / ("docker-compose.yml" if scope.startswith("compose") or scope == "volume"
                            else ".github/workflows/ci.yml")
    document = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    if scope == "compose_image":
        document["services"]["db"]["image"] = "postgres:16"
    elif scope == "compose_platform":
        document["services"]["db"]["platform"] = "linux/arm64"
    elif scope == "volume":
        document["services"]["db"]["volumes"] = ["different_data:/var/lib/postgresql/data"]
    elif scope == "ci_image":
        document["jobs"]["database-artifact"]["env"]["DB_IMAGE"] = "postgres:16"
    else:
        document["jobs"]["database-artifact"]["env"]["DB_PLATFORM"] = "linux/arm64"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(SystemExit):
        VALIDATE(artifact_root)


def test_unpinned_inventory_is_rejected(artifact_root):
    path = artifact_root / "runtime-artifacts.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["database"]["base_oci_index_digest"] = "latest"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(SystemExit, match="digest"):
        VALIDATE(artifact_root)


@pytest.mark.parametrize("name", ["Dockerfile", "database-entrypoint.sh", "verify-initial-profile.sh"])
def test_crlf_recipe_inputs_are_rejected(artifact_root, name):
    path = artifact_root / "docker/database" / name
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(SystemExit, match="LF line endings"):
        VALIDATE(artifact_root)
