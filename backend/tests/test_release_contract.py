"""No-network release safety contracts: readiness, permissions and tampering."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.error

import pytest
import yaml


REPO = Path(__file__).resolve().parents[2]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = load_script("check_release")
ci = load_script("check_ci")
VERSION = "0.1.0"
SHA = "a" * 40
RUN_ID = 33
RUN_ATTEMPT = 1


@pytest.fixture
def hosted():
    environment = {"GITHUB_REPOSITORY": release.REPOSITORY, "GITHUB_EVENT_NAME": "workflow_dispatch",
                   "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": SHA}
    data = {
        "": {"full_name": release.REPOSITORY, "default_branch": "main", "private": False, "archived": False},
        "private-vulnerability-reporting": {"enabled": True},
        "branches/main": {"commit": {"sha": SHA}, "protected": True},
        "branches/main/protection": {
            "required_status_checks": {"strict": True, "checks": [{"context": "ci-required", "app_id": 15368}]},
            "enforce_admins": {"enabled": True}, "required_conversation_resolution": {"enabled": True},
            "allow_force_pushes": {"enabled": False}, "allow_deletions": {"enabled": False},
            "required_pull_request_reviews": {"dismiss_stale_reviews": True, "required_approving_review_count": 0},
        },
        f"actions/workflows/ci.yml/runs?head_sha={SHA}&status=success&per_page=30": {"workflow_runs": [
            {"id": 22, "head_sha": SHA, "head_branch": "main", "event": "push", "status": "completed", "conclusion": "success"}]},
        f"commits/{SHA}/check-runs?filter=latest&per_page=100": {"check_runs": [
            {"name": "ci-required", "app": {"id": 15368}, "head_sha": SHA, "status": "completed", "conclusion": "success",
             "details_url": f"https://github.com/{release.REPOSITORY}/actions/runs/22/job/7"}]},
        f"git/ref/tags/v{VERSION}": None, f"releases/tags/v{VERSION}": None,
    }
    return environment, data


def remote(hosted):
    environment, data = hosted
    return release.validate_remote(VERSION, SHA, get=lambda path, **_: deepcopy(data[path]), environment=environment)


def test_remote_binds_required_check_to_exact_successful_main_run(hosted):
    result = remote(hosted)
    assert result["ci_run_id"] == 22
    assert result["source_sha"] == SHA
    assert result["certificate_identity"] == release.CERTIFICATE_IDENTITY


@pytest.mark.parametrize("key,value", [
    ("GITHUB_REPOSITORY", "other/Cardchemy"), ("GITHUB_EVENT_NAME", "pull_request"),
    ("GITHUB_REF", "refs/tags/v0.1.0"), ("GITHUB_SHA", "b" * 40),
])
def test_remote_rejects_wrong_repository_event_ref_or_commit(hosted, key, value):
    hosted[0][key] = value
    with pytest.raises(release.ReleaseContractError):
        remote(hosted)


@pytest.mark.parametrize("mutation", [
    "private", "reporting-disabled", "moved-main", "unprotected", "loose-base", "wrong-ci-app",
    "admins-bypass", "unresolved-conversations", "force-push", "delete", "no-pr-flow", "stale-reviews",
    "pr-bypass", "wrong-run-sha", "pr-run", "failed-run", "wrong-check-app", "check-other-run", "failed-check",
    "existing-tag", "existing-release",
])
def test_remote_fails_closed_on_missing_readiness(hosted, mutation):
    _, data = hosted
    protection = data["branches/main/protection"]
    run = data[f"actions/workflows/ci.yml/runs?head_sha={SHA}&status=success&per_page=30"]["workflow_runs"][0]
    check = data[f"commits/{SHA}/check-runs?filter=latest&per_page=100"]["check_runs"][0]
    if mutation == "private": data[""]["private"] = True
    elif mutation == "reporting-disabled": data["private-vulnerability-reporting"]["enabled"] = False
    elif mutation == "moved-main": data["branches/main"]["commit"]["sha"] = "b" * 40
    elif mutation == "unprotected": data["branches/main"]["protected"] = False
    elif mutation == "loose-base": protection["required_status_checks"]["strict"] = False
    elif mutation == "wrong-ci-app": protection["required_status_checks"]["checks"][0]["app_id"] = 999
    elif mutation == "admins-bypass": protection["enforce_admins"]["enabled"] = False
    elif mutation == "unresolved-conversations": protection["required_conversation_resolution"]["enabled"] = False
    elif mutation == "force-push": protection["allow_force_pushes"]["enabled"] = True
    elif mutation == "delete": protection["allow_deletions"]["enabled"] = True
    elif mutation == "no-pr-flow": protection["required_pull_request_reviews"] = None
    elif mutation == "stale-reviews": protection["required_pull_request_reviews"]["dismiss_stale_reviews"] = False
    elif mutation == "pr-bypass": protection["required_pull_request_reviews"]["bypass_pull_request_allowances"] = {"users": [{"login": "bypass"}]}
    elif mutation == "wrong-run-sha": run["head_sha"] = "b" * 40
    elif mutation == "pr-run": run["event"] = "pull_request"
    elif mutation == "failed-run": run["conclusion"] = "failure"
    elif mutation == "wrong-check-app": check["app"]["id"] = 999
    elif mutation == "check-other-run": check["details_url"] = f"https://github.com/{release.REPOSITORY}/actions/runs/222/job/7"
    elif mutation == "failed-check": check["conclusion"] = "failure"
    elif mutation == "existing-tag": data[f"git/ref/tags/v{VERSION}"] = {"object": {"sha": SHA}}
    elif mutation == "existing-release": data[f"releases/tags/v{VERSION}"] = {"id": 1}
    with pytest.raises(release.ReleaseContractError):
        remote(hosted)


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_archive(directory: Path, sha: str, *, member=".env.example"):
    with tarfile.open(directory / f"cardchemy-{VERSION}-source.tar.gz", "w:gz", format=tarfile.PAX_FORMAT,
                      pax_headers={"comment": sha}) as archive:
        content = b"APP_NAME=Cardchemy\n"
        info = tarfile.TarInfo(f"cardchemy-{VERSION}/{member}")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))


def checksums(directory: Path):
    names = sorted(release.required_artifacts(VERSION) - {"SHA256SUMS", "SHA256SUMS.sigstore.json"})
    (directory / "SHA256SUMS").write_text("".join(f"{release.file_digest(directory / name)}  {name}\n" for name in names), encoding="utf-8")


def image_files(directory: Path, sha: str, *, run_id: int = RUN_ID, run_attempt: int = RUN_ATTEMPT):
    images = []
    for index, variant in enumerate(release.VARIANTS):
        image_id = "sha256:" + str(index) * 64
        manifest = json.dumps({"schemaVersion": 2, "config": {"digest": image_id}, "layers": []}).encode()
        (directory / f"{variant}.manifest.json").write_bytes(manifest)
        record = {"image": f"ghcr.io/eocimreo/cardchemy-{variant}",
                  "tag": f"ghcr.io/eocimreo/cardchemy-{variant}:v{VERSION}-{sha}-{run_id}-{run_attempt}",
                  "run_id": run_id, "run_attempt": run_attempt, "image_id": image_id,
                  "digest": "sha256:" + hashlib.sha256(manifest).hexdigest(), "source_sha": sha,
                  "version": VERSION, "platform": "linux/amd64"}
        write_json(directory / f"{variant}.build.json", record)
        write_json(directory / f"{variant}.audit.json", {
            "SchemaVersion": 2, "Trivy": {"Version": "0.70.0"},
            "ArtifactType": "container_image", "Metadata": {"ImageID": image_id,
            "ImageConfig": {"architecture": "amd64", "os": "linux", "config": {"Labels": {
                "org.opencontainers.image.source": f"https://github.com/{release.REPOSITORY}",
                "org.opencontainers.image.revision": sha, "org.opencontainers.image.version": VERSION}}}},
            "Results": [{"Class": "os-pkgs", "Vulnerabilities": None}],
        })
        write_json(directory / f"{variant}.sbom.json", {"bomFormat": "CycloneDX", "metadata": {"component": {
            "type": "container", "properties": [{"name": "aquasecurity:trivy:ImageID", "value": image_id}]}}})
        images.append({"variant": variant, **record})
    return images


@pytest.fixture
def package(tmp_path):
    images = image_files(tmp_path, SHA)
    write_archive(tmp_path, SHA)
    (tmp_path / "release-notes.md").write_text("# Cardchemy 0.1.0\n", encoding="utf-8")
    write_json(tmp_path / "source-provenance.json", {"version": VERSION, "tag": f"v{VERSION}",
        "source_sha": SHA, "repository": release.REPOSITORY, "certificate_identity": release.CERTIFICATE_IDENTITY,
        "oidc_issuer": release.OIDC_ISSUER, "ci_run_id": 22, "schema_version": 1, "platform": "linux/amd64",
        "workflow_ref": release.WORKFLOW_REF,
        "run_url": f"https://github.com/{release.REPOSITORY}/actions/runs/{RUN_ID}",
        "run_attempt": RUN_ATTEMPT, "images": images})
    checksums(tmp_path)
    return tmp_path


def test_package_inventory_and_immutable_linkage(package):
    release.verify_package(package, VERSION, SHA, signed=False)


def test_downloaded_package_rejects_unlisted_files(package):
    (package / "SHA256SUMS.sigstore.json").write_text("signed bundle", encoding="utf-8")
    release.verify_package(package, VERSION, SHA)
    (package / "unexpected.txt").write_text("not signed", encoding="utf-8")
    with pytest.raises(release.ReleaseContractError, match="unexpected files"):
        release.verify_package(package, VERSION, SHA)


@pytest.mark.parametrize("mutation", ["checksum", "omitted", "unsafe-path", "different-config", "different-sbom",
    "manifest-bytes", "vulnerable", "empty-audit", "wrong-source-label", "wrong-platform",
    "provenance-image", "provenance-run", "provenance-attempt", "wrong-tag", "tag-other-attempt",
    "archive-source", "archive-secret", "archive-traversal"])
def test_package_rejects_tampering_even_with_recomputed_inventory(package, mutation):
    if mutation == "checksum":
        (package / "release-notes.md").write_text("modified", encoding="utf-8")
    elif mutation == "omitted":
        lines = (package / "SHA256SUMS").read_text().splitlines()
        (package / "SHA256SUMS").write_text("\n".join(lines[1:]) + "\n", encoding="utf-8")
    elif mutation == "unsafe-path":
        with (package / "SHA256SUMS").open("a") as output: output.write("0" * 64 + "  ../secret\n")
    else:
        if mutation in {"different-config", "vulnerable", "empty-audit", "wrong-source-label", "wrong-platform"}:
            path = package / "backend.audit.json"
            data = json.loads(path.read_text())
            if mutation == "different-config": data["Metadata"]["ImageID"] = "sha256:" + "f" * 64
            elif mutation == "vulnerable": data["Results"][0]["Vulnerabilities"] = [{"Severity": "HIGH"}]
            elif mutation == "empty-audit": data["Results"] = []
            elif mutation == "wrong-source-label": data["Metadata"]["ImageConfig"]["config"]["Labels"]["org.opencontainers.image.revision"] = "b" * 40
            elif mutation == "wrong-platform": data["Metadata"]["ImageConfig"]["architecture"] = "arm64"
            write_json(path, data)
        elif mutation == "different-sbom":
            path = package / "backend.sbom.json"
            data = json.loads(path.read_text())
            data["metadata"]["component"]["properties"][0]["value"] = "sha256:" + "f" * 64
            write_json(path, data)
        elif mutation == "manifest-bytes":
            with (package / "backend.manifest.json").open("ab") as output: output.write(b"\n")
        elif mutation == "provenance-image":
            path = package / "source-provenance.json"
            data = json.loads(path.read_text())
            data["images"][0]["digest"] = "sha256:" + "f" * 64
            write_json(path, data)
        elif mutation in {"provenance-run", "provenance-attempt"}:
            path = package / "source-provenance.json"
            data = json.loads(path.read_text())
            if mutation == "provenance-run":
                data["run_url"] = f"https://github.com/{release.REPOSITORY}/actions/runs/{RUN_ID + 1}"
            else:
                data["run_attempt"] = RUN_ATTEMPT + 1
            write_json(path, data)
        elif mutation in {"wrong-tag", "tag-other-attempt"}:
            path = package / "backend.build.json"
            data = json.loads(path.read_text())
            if mutation == "wrong-tag":
                data["tag"] = data["image"] + ":" + VERSION
            else:
                data["tag"] = f'{data["image"]}:v{VERSION}-{SHA}-{RUN_ID}-{RUN_ATTEMPT + 1}'
            write_json(path, data)
        elif mutation == "archive-source": write_archive(package, "b" * 40)
        elif mutation == "archive-secret": write_archive(package, SHA, member=".env")
        elif mutation == "archive-traversal": write_archive(package, SHA, member="../secret")
        checksums(package)
    with pytest.raises(release.ReleaseContractError):
        release.verify_package(package, VERSION, SHA, signed=False)


def test_prepare_package_archives_exact_git_commit_and_excludes_operator_env(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, text=True, check=True).stdout.strip()
    git("init", "--initial-branch=main")
    (tmp_path / ".gitignore").write_text(".env\nartifacts/\n", encoding="utf-8")
    (tmp_path / ".env").write_text("PRIVATE_OPERATOR_SENTINEL=do-not-package\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Cardchemy\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text("## [Unreleased]\nFuture idea must not release.\n\n## [0.1.0] - 2026-09-17\nPublished behavior.\n", encoding="utf-8")
    git("add", "README.md", ".gitignore", "CHANGELOG.md")
    git("-c", "user.name=Release fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false",
        "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "-m", "Release fixture")
    sha = git("rev-parse", "HEAD")
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", release.WORKFLOW_REF)
    monkeypatch.setenv("GITHUB_RUN_ID", str(RUN_ID))
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", str(RUN_ATTEMPT))
    directory = tmp_path / "artifacts"
    directory.mkdir()
    image_files(directory, sha)
    preflight = {"version": VERSION, "tag": f"v{VERSION}", "source_sha": sha, "repository": release.REPOSITORY,
                 "ci_run_id": 22, "certificate_identity": release.CERTIFICATE_IDENTITY, "oidc_issuer": release.OIDC_ISSUER}
    release.prepare_package(directory, VERSION, sha, preflight)
    release.verify_package(directory, VERSION, sha, signed=False)
    notes = (directory / "release-notes.md").read_text()
    assert "Published behavior." in notes
    assert "Future idea" not in notes
    with tarfile.open(directory / f"cardchemy-{VERSION}-source.tar.gz") as archive:
        assert archive.pax_headers["comment"] == sha
        assert all(not member.name.endswith("/.env") for member in archive.getmembers())


def test_failure_output_never_echoes_untrusted_json_error(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["check_release.py", "--version", VERSION])
    def malformed(_):
        raise json.JSONDecodeError("private-upstream-sentinel", "private-document-sentinel", 0)
    monkeypatch.setattr(release, "validate_local", malformed)
    assert release.main() == 1
    assert capsys.readouterr().out == "Release readiness failed: metadata unavailable\n"


def test_protection_read_uses_separate_readonly_token_without_logging_it(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "unit-workflow-token")
    monkeypatch.delenv("RELEASE_READINESS_TOKEN", raising=False)
    with pytest.raises(release.ReleaseContractError, match="RELEASE_READINESS_TOKEN"):
        release.github_get("branches/main/protection")
    monkeypatch.setenv("RELEASE_READINESS_TOKEN", "unit-administration-read-token")
    requests = []
    def failed(request, **_):
        requests.append(request)
        raise urllib.error.HTTPError(request.full_url, 403, "private-upstream-sentinel", {}, None)
    monkeypatch.setattr(release.urllib.request, "urlopen", failed)
    with pytest.raises(release.ReleaseContractError) as caught:
        release.github_get("branches/main/protection")
    assert str(caught.value) == "GitHub release readiness could not be verified"
    assert requests[0].get_header("Authorization") == "Bearer unit-administration-read-token"


@pytest.mark.parametrize("mutation", [None, "ambiguous-digest", "wrong-manifest"])
def test_registry_capture_checks_raw_digest_and_inventory_before_recording(package, monkeypatch, mutation):
    metadata = json.loads((package / "backend.build.json").read_text())
    monkeypatch.setenv("GITHUB_RUN_ID", str(RUN_ID))
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", str(RUN_ATTEMPT))
    raw = (package / "backend.manifest.json").read_bytes()
    reference = metadata["image"] + "@" + metadata["digest"]
    digests = [reference]
    if mutation == "ambiguous-digest": digests.append(metadata["image"] + "@sha256:" + "f" * 64)
    if mutation == "wrong-manifest": raw = b'{"schemaVersion": 2, "config": {}}'
    responses = [subprocess.CompletedProcess([], 0, json.dumps([{"Id": metadata["image_id"], "RepoDigests": digests}]).encode(), b""),
                 subprocess.CompletedProcess([], 0, raw + b"\n", b"private-upstream-sentinel")]
    commands = []
    def run(command, **_):
        commands.append(command)
        return responses.pop(0)
    monkeypatch.setattr(release.subprocess, "run", run)
    if mutation:
        with pytest.raises(release.ReleaseContractError):
            release.record_registry_image(package, "backend", VERSION, SHA, metadata["tag"])
    else:
        release.record_registry_image(package, "backend", VERSION, SHA, metadata["tag"])
        assert commands[1][-1] == reference
        assert (package / "backend.manifest.json").read_bytes() == raw
        captured = json.loads((package / "backend.build.json").read_text())
        assert captured["digest"] == metadata["digest"]
        assert captured["tag"] == metadata["tag"]
        assert captured["run_id"] == RUN_ID
        assert captured["run_attempt"] == RUN_ATTEMPT


@pytest.mark.parametrize("bad_tag", [
    f"ghcr.io/eocimreo/cardchemy-backend:{VERSION}",
    f"ghcr.io/eocimreo/cardchemy-backend:v{VERSION}-{SHA}-{RUN_ID}-{RUN_ATTEMPT + 1}",
    f"ghcr.io/eocimreo/cardchemy-backend:v{VERSION}-{'b' * 40}-{RUN_ID}-{RUN_ATTEMPT}",
])
def test_registry_capture_rejects_unapproved_or_other_attempt_tag_before_docker(package, monkeypatch, bad_tag):
    monkeypatch.setenv("GITHUB_RUN_ID", str(RUN_ID))
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", str(RUN_ATTEMPT))
    def forbidden(*_args, **_kwargs):
        pytest.fail("Unapproved tag should be rejected before registry commands")
    monkeypatch.setattr(release.subprocess, "run", forbidden)
    with pytest.raises(release.ReleaseContractError):
        release.record_registry_image(package, "backend", VERSION, SHA, bad_tag)


def test_unique_release_tag_must_resolve_to_signed_manifest(package, monkeypatch):
    metadata = json.loads((package / "backend.build.json").read_text())
    raw = (package / "backend.manifest.json").read_bytes()
    commands = []
    def run(command, **_):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, raw + b"\n", b"")
    monkeypatch.setattr(release.subprocess, "run", run)
    release.verify_release_tag(package, "backend", VERSION, SHA)
    assert commands[0][-1] == metadata["tag"]
    def altered(command, **_):
        return subprocess.CompletedProcess(command, 0, b'{"other": true}', b"")
    monkeypatch.setattr(release.subprocess, "run", altered)
    with pytest.raises(release.ReleaseContractError, match="digest"):
        release.verify_release_tag(package, "backend", VERSION, SHA)


@pytest.mark.parametrize("mutation", [
    "ci-write", "preflight-write", "release-extra-write", "unguarded-release", "pr-trigger",
    "unreviewed-cosign", "cosign-version", "missing-cosign", "extra-stable-push",
    "premature-push", "missing-run-attempt", "draft-before-sign", "missing-final-tag-guard",
])
def test_workflow_permissions_and_signer_cannot_be_broadened(mutation):
    document = yaml.load((REPO / ".github/workflows/release-sbom.yml").read_text(), Loader=yaml.BaseLoader)
    filename = "release-sbom.yml"
    if mutation == "ci-write":
        filename = "ci.yml"
        document = yaml.load((REPO / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
        document["jobs"]["backend-offline"]["permissions"] = {"contents": "write"}
    elif mutation == "preflight-write": document["jobs"]["preflight"]["permissions"]["contents"] = "write"
    elif mutation == "release-extra-write": document["jobs"]["release"]["permissions"]["issues"] = "write"
    elif mutation == "unguarded-release": document["jobs"]["release"].pop("needs")
    elif mutation == "pr-trigger": document["on"]["pull_request"] = {}
    elif mutation in {"extra-stable-push", "missing-run-attempt"}:
        step = next(step for step in document["jobs"]["release"]["steps"]
                    if step.get("name") == "Publish unique release tags and verify keyless image signatures")
        if mutation == "extra-stable-push":
            step["run"] += '\ndocker push "$image:${VERSION}"\n'
        else:
            step["run"] = step["run"].replace(
                'release_tag="$image:v$VERSION-$SOURCE_SHA-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT"',
                'release_tag="$image:v$VERSION-$SOURCE_SHA-$GITHUB_RUN_ID"')
    elif mutation == "premature-push":
        document["jobs"]["release"]["steps"].insert(0, {
            "name": "Push before signing", "run": 'docker push "$image:${VERSION}"'})
    elif mutation == "draft-before-sign":
        steps = document["jobs"]["release"]["steps"]
        draft = next(step for step in steps if step.get("name") == "Create annotated version tag and verified draft release")
        steps.remove(draft)
        steps.insert(0, draft)
    elif mutation == "missing-final-tag-guard":
        step = next(step for step in document["jobs"]["release"]["steps"]
                    if step.get("name") == "Final main/CI/registry-tag guard before creating the signed draft")
        step["run"] = step["run"].replace('--verify-release-tag "$variant"', '--verify-package "$variant"')
    else:
        step = next(step for step in document["jobs"]["release"]["steps"] if step.get("uses") == ci.COSIGN_INSTALLER)
        if mutation == "unreviewed-cosign": step["uses"] = "sigstore/cosign-installer@" + "a" * 40
        elif mutation == "missing-cosign": document["jobs"]["release"]["steps"].remove(step)
        else: step["with"]["cosign-release"] = "v0.0.0"
    with pytest.raises(SystemExit):
        ci.validate_workflow(document, filename)
