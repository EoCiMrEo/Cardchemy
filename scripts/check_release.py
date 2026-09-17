"""Validate release metadata and immutable hosted readiness; never publish.

Normal validation reads maintained source/templates, not operator settings.
Remote validation uses only the explicitly supplied GH_TOKEN and GitHub API.
Packaging archives the exact Git commit, excluding ignored/private files.
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "EoCiMrEo/Cardchemy"
VARIANTS = ("backend", "backend-ocr", "frontend")
CERTIFICATE_IDENTITY = f"https://github.com/{REPOSITORY}/.github/workflows/release-sbom.yml@refs/heads/main"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
VERSION_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
WORKFLOW_REF = f"{REPOSITORY}/.github/workflows/release-sbom.yml@refs/heads/main"


class ReleaseContractError(ValueError):
    """An authored, content-free failure that is safe to show to operators."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReleaseContractError(message)


def git(*arguments: str) -> str:
    result = subprocess.run(["git", "-C", str(ROOT), *arguments], capture_output=True, text=True, timeout=30)
    require(result.returncode == 0, "Git release metadata could not be verified")
    return result.stdout.strip()


def setting_default(source: str, name: str):
    """Inspect a literal default without importing settings or reading .env."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            value = node.value
            if isinstance(value, ast.Constant):
                return value.value
            if isinstance(value, ast.Call):
                for keyword in value.keywords:
                    if keyword.arg == "default" and isinstance(keyword.value, ast.Constant):
                        return keyword.value.value
    raise ReleaseContractError(f"Missing literal setting default: {name}")


def validate_local(version: str, *, root: Path = ROOT) -> dict:
    require(bool(VERSION_PATTERN.fullmatch(version)), "Release version must be a stable MAJOR.MINOR.PATCH")
    package = json.loads((root / "frontend/package.json").read_text(encoding="utf-8"))
    lock = json.loads((root / "frontend/package-lock.json").read_text(encoding="utf-8"))
    require(package.get("version") == version, "Frontend version does not match release")
    require(package.get("name") == "cardchemy-web", "Frontend package must use Cardchemy branding")
    require(package.get("license") == "Apache-2.0", "Frontend package license must match approved code license")
    require(lock.get("version") == version and lock.get("name") == package["name"], "Package lock root metadata disagrees")
    require(lock.get("packages", {}).get("", {}).get("version") == version
            and lock["packages"][""]["name"] == package["name"]
            and lock["packages"][""].get("license") == "Apache-2.0", "Package lock package metadata disagrees")
    source = (root / "backend/app/config.py").read_text(encoding="utf-8")
    require(setting_default(source, "app_name") == "Cardchemy", "API default product name is stale")
    require(setting_default(source, "app_version") == version, "API default version does not match release")
    template = (root / ".env.example").read_text(encoding="utf-8")
    require(re.search(r"(?m)^APP_NAME=Cardchemy$", template) is not None, "Root template name is stale")
    require(re.search(rf"(?m)^APP_VERSION={re.escape(version)}$", template) is not None, "Root template version disagrees")
    require(not (root / "backend/.env.example").exists() and not (root / "frontend/.env.example").exists(), "Only root configuration template is supported")
    required = ("LICENSE", "NOTICE", "BRANDING.md", "CONTRIBUTING.md", "SECURITY.md", "CODE_OF_CONDUCT.md", "ROADMAP.md", "README.md", "docs/RELEASING.md")
    for filename in required:
        path = root / filename
        require(path.is_file() and path.stat().st_size > 0, f"Required release document missing: {filename}")
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    require("Apache License" in license_text and "Version 2.0" in license_text, "Approved Apache-2.0 license missing")
    for filename in ("LICENSE", "NOTICE", "BRANDING.md"):
        canonical = (root / filename).read_bytes()
        for component in ("backend/legal", "frontend/public/legal"):
            redistributed = root / component / filename
            require(redistributed.is_file() and not redistributed.is_symlink()
                    and redistributed.read_bytes() == canonical,
                    "Redistributed code/brand notice copies must match the canonical terms")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    require(len(re.findall(rf"(?m)^## \[{re.escape(version)}\]", changelog)) == 1, "Changelog needs exactly one target-version section")
    require("https://github.com/EoCiMrEo/Cardchemy/security/advisories/new" in (root / "SECURITY.md").read_text(encoding="utf-8"), "Private reporting channel missing")
    if int(version.split(".")[0]) >= 1:
        roadmap = (root / "issues-required-remediation.md").read_text(encoding="utf-8")
        gate = roadmap.split("## v1.0 release gate", 1)[-1]
        require("- [ ]" not in gate, "v1.0 release gate still has incomplete items")
    return {"version": version, "tag": f"v{version}", "repository": REPOSITORY}


def github_get(path: str, *, missing_ok: bool = False):
    # Administration(read) is not a supported GITHUB_TOKEN permission. Only
    # the protection read uses this separately scoped read-only secret.
    protection_read = path == "branches/main/protection"
    token = os.environ.get("RELEASE_READINESS_TOKEN" if protection_read else "GH_TOKEN")
    require(bool(token), "Protection verification requires RELEASE_READINESS_TOKEN" if protection_read else "Remote release verification requires an explicit GH_TOKEN")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Cardchemy-release-preflight"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if missing_ok and error.code == 404:
            return None
        raise ReleaseContractError("GitHub release readiness could not be verified") from None
    except (OSError, ValueError):
        raise ReleaseContractError("GitHub release readiness could not be verified") from None


def validate_remote(version: str, source_sha: str, *, get=github_get, environment=None) -> dict:
    env = os.environ if environment is None else environment
    require(bool(VERSION_PATTERN.fullmatch(version)), "Release version must be a stable MAJOR.MINOR.PATCH")
    require(bool(SHA_PATTERN.fullmatch(source_sha)), "Source SHA must be exactly 40 lowercase hexadecimal characters")
    require(env.get("GITHUB_REPOSITORY") == REPOSITORY, "Release workflow must run in the approved repository")
    require(env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("GITHUB_REF") == "refs/heads/main", "Release requires manual dispatch on main")
    require(env.get("GITHUB_SHA") == source_sha, "Dispatched commit differs from approved source SHA")
    repository = get("")
    require(repository.get("full_name") == REPOSITORY and repository.get("default_branch") == "main", "Unexpected repository/default branch")
    require(repository.get("private") is False and not repository.get("archived"), "Public release requires the approved repository to be public and active")
    require(get("private-vulnerability-reporting").get("enabled") is True, "Private vulnerability reporting must be enabled before release")
    branch = get("branches/main")
    require(branch.get("commit", {}).get("sha") == source_sha and branch.get("protected") is True, "Source must equal current protected main HEAD")
    protection = get("branches/main/protection")
    checks = protection.get("required_status_checks", {})
    require(checks.get("strict") is True and {"context": "ci-required", "app_id": 15368} in checks.get("checks", []), "Current-base ci-required enforcement is missing")
    require(protection.get("enforce_admins", {}).get("enabled") is True and protection.get("required_conversation_resolution", {}).get("enabled") is True, "Required administrator/conversation protection is missing")
    require(protection.get("allow_force_pushes", {}).get("enabled") is False and protection.get("allow_deletions", {}).get("enabled") is False, "Shared-history protection is missing")
    reviews = protection.get("required_pull_request_reviews")
    require(isinstance(reviews, dict) and reviews.get("dismiss_stale_reviews") is True
            and type(reviews.get("required_approving_review_count")) is int
            and reviews["required_approving_review_count"] >= 0,
            "Required pull-request flow/stale-review protection is missing")
    require(not reviews.get("bypass_pull_request_allowances", {}).get("users")
            and not reviews.get("bypass_pull_request_allowances", {}).get("teams")
            and not reviews.get("bypass_pull_request_allowances", {}).get("apps"),
            "Pull-request protection must not permit bypass actors")
    runs = get(f"actions/workflows/ci.yml/runs?head_sha={source_sha}&status=success&per_page=30").get("workflow_runs", [])
    eligible = [run for run in runs if run.get("head_sha") == source_sha and run.get("head_branch") == "main" and run.get("event") in {"push", "workflow_dispatch"} and run.get("status") == "completed" and run.get("conclusion") == "success"]
    require(bool(eligible), "Exact main commit needs a successful mandatory CI workflow run")
    check_runs = get(f"commits/{source_sha}/check-runs?filter=latest&per_page=100").get("check_runs", [])
    eligible_ids = {run["id"] for run in eligible if type(run.get("id")) is int and run["id"] > 0}
    require(bool(eligible_ids), "Verified CI run identity is missing")
    candidates = [item for item in check_runs if item.get("name") == "ci-required" and item.get("app", {}).get("id") == 15368 and item.get("head_sha") == source_sha and item.get("status") == "completed" and item.get("conclusion") == "success" and any(str(item.get("details_url", "")).startswith(f"https://github.com/{REPOSITORY}/actions/runs/{run_id}/") for run_id in eligible_ids)]
    require(bool(candidates), "Exact commit lacks successful ci-required from the verified CI run")
    tag = f"v{version}"
    require(get(f"git/ref/tags/{tag}", missing_ok=True) is None, "Version tag already exists; never overwrite it")
    require(get(f"releases/tags/{tag}", missing_ok=True) is None, "Release already exists; never overwrite it")
    matched_run_ids = {run_id for run_id in eligible_ids for item in candidates
                       if str(item.get("details_url", "")).startswith(f"https://github.com/{REPOSITORY}/actions/runs/{run_id}/")}
    return {"version": version, "tag": tag, "source_sha": source_sha, "repository": REPOSITORY, "ci_run_id": max(matched_run_ids), "certificate_identity": CERTIFICATE_IDENTITY, "oidc_issuer": OIDC_ISSUER}


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_record(directory: Path, variant: str, version: str, source_sha: str) -> dict:
    """Bind inventory, audit, image config and exact registry manifest bytes."""
    metadata = json.loads((directory / f"{variant}.build.json").read_text(encoding="utf-8"))
    expected = f"ghcr.io/eocimreo/cardchemy-{variant}"
    require(metadata.get("image") == expected and bool(DIGEST_PATTERN.fullmatch(metadata.get("digest", ""))), "Release image must have its approved registry and immutable digest")
    require(bool(DIGEST_PATTERN.fullmatch(metadata.get("image_id", ""))), "Immutable image config identity is missing")
    require(metadata.get("source_sha") == source_sha and metadata.get("version") == version
            and metadata.get("platform") == "linux/amd64", "Image source/version/platform provenance disagrees")
    manifest_path = directory / f"{variant}.manifest.json"
    require(f"sha256:{file_digest(manifest_path)}" == metadata["digest"], "Registry manifest bytes do not match the signed image digest")
    manifest = json.loads(manifest_path.read_bytes())
    require(manifest.get("schemaVersion") == 2 and manifest.get("config", {}).get("digest") == metadata["image_id"], "Registry manifest does not bind the inventoried image config")
    audit = json.loads((directory / f"{variant}.audit.json").read_text(encoding="utf-8"))
    require(audit.get("SchemaVersion") == 2 and audit.get("Trivy", {}).get("Version") == "0.70.0"
            and isinstance(audit.get("Results"), list) and bool(audit["Results"])
            and any(result.get("Class") == "os-pkgs" for result in audit["Results"]),
            "Release audit is missing a supported full OS vulnerability scan")
    require(audit.get("ArtifactType") == "container_image"
            and audit.get("Metadata", {}).get("ImageID") == metadata["image_id"], "Vulnerability audit belongs to a different image")
    config = audit.get("Metadata", {}).get("ImageConfig", {})
    require(config.get("architecture") == "amd64" and config.get("os") == "linux", "Audited image platform disagrees")
    labels = config.get("config", {}).get("Labels", {})
    require(labels.get("org.opencontainers.image.source") == f"https://github.com/{REPOSITORY}"
            and labels.get("org.opencontainers.image.revision") == source_sha
            and labels.get("org.opencontainers.image.version") == version, "Audited image source labels disagree")
    require(not any(vulnerability.get("Severity") in {"HIGH", "CRITICAL"}
                    for result in audit.get("Results", [])
                    for vulnerability in (result.get("Vulnerabilities") or [])),
            "Release audit contains a high or critical vulnerability")
    sbom = json.loads((directory / f"{variant}.sbom.json").read_text(encoding="utf-8"))
    component = sbom.get("metadata", {}).get("component", {})
    require(sbom.get("bomFormat") == "CycloneDX" and component.get("type") == "container"
            and any(item.get("name") == "aquasecurity:trivy:ImageID" and item.get("value") == metadata["image_id"]
                    for item in component.get("properties", [])), "SBOM belongs to a different image")
    return {"variant": variant, **metadata}


def record_registry_image(directory: Path, variant: str, version: str, source_sha: str) -> None:
    """Capture a pushed manifest by digest; never print registry/tool errors."""
    require(variant in VARIANTS and bool(VERSION_PATTERN.fullmatch(version))
            and bool(SHA_PATTERN.fullmatch(source_sha)), "Image recording requires approved variant/version/source")
    image = f"ghcr.io/eocimreo/cardchemy-{variant}"
    result = subprocess.run(["docker", "image", "inspect", f"{image}:{version}"], capture_output=True, timeout=30)
    require(result.returncode == 0, "Pushed image identity could not be read")
    inspected = json.loads(result.stdout)[0]
    digests = [item.partition("@")[2] for item in inspected.get("RepoDigests", []) if item.startswith(image + "@")]
    require(len(digests) == 1 and bool(DIGEST_PATTERN.fullmatch(digests[0])), "Pushed registry image digest is ambiguous or missing")
    raw = registry_manifest_bytes(f"{image}@{digests[0]}", digests[0])
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{variant}.manifest.json").write_bytes(raw)
    metadata = {"image": image, "digest": digests[0], "image_id": inspected.get("Id"), "source_sha": source_sha, "version": version, "platform": "linux/amd64"}
    (directory / f"{variant}.build.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    image_record(directory, variant, version, source_sha)


def registry_manifest_bytes(reference: str, expected_digest: str) -> bytes:
    result = subprocess.run(["docker", "buildx", "imagetools", "inspect", "--raw", reference], capture_output=True, timeout=60)
    require(result.returncode == 0, "Immutable registry manifest could not be read")
    raw = result.stdout
    # buildx may append a display newline. Remove it only when the exact
    # content hash then equals the immutable registry manifest digest.
    if f"sha256:{hashlib.sha256(raw).hexdigest()}" != expected_digest and raw.endswith(b"\n"):
        raw = raw[:-1]
    require(f"sha256:{hashlib.sha256(raw).hexdigest()}" == expected_digest, "Registry manifest digest could not be verified")
    return raw


def verify_version_tag(directory: Path, variant: str, version: str, source_sha: str) -> None:
    """Require a public version tag to resolve to the already signed candidate bytes."""
    require(variant in VARIANTS, "Unexpected release image variant")
    record = image_record(directory, variant, version, source_sha)
    raw = registry_manifest_bytes(f"{record['image']}:{version}", record["digest"])
    require(raw == (directory / f"{variant}.manifest.json").read_bytes(),
            "Version tag does not resolve to the signed candidate manifest")


def prepare_package(directory: Path, version: str, source_sha: str, preflight: dict) -> None:
    require(git("rev-parse", "HEAD") == source_sha, "Package source must equal checked-out commit")
    require(git("status", "--porcelain") == "", "Packaging requires a clean committed source checkout")
    require(preflight.get("source_sha") == source_sha and preflight.get("version") == version, "Package preflight provenance disagrees")
    require(type(preflight.get("ci_run_id")) is int and preflight["ci_run_id"] > 0, "Verified CI provenance is missing")
    require(preflight.get("repository") == REPOSITORY and preflight.get("tag") == f"v{version}"
            and preflight.get("certificate_identity") == CERTIFICATE_IDENTITY
            and preflight.get("oidc_issuer") == OIDC_ISSUER, "Package signing identity disagrees")
    require(os.environ.get("GITHUB_WORKFLOW_REF") == WORKFLOW_REF
            and os.environ.get("GITHUB_RUN_ID", "").isdigit(), "Release workflow/run provenance is missing")
    images = [image_record(directory, variant, version, source_sha) for variant in VARIANTS]
    tracked = git("ls-tree", "-r", "--name-only", source_sha).splitlines()
    require(not any(any(part.casefold().startswith(".env") and part != ".env.example" for part in PurePosixPath(path).parts)
                    or path.casefold().endswith((".key", ".pem", ".p12", ".pfx", ".jks", ".keystore"))
                    for path in tracked), "Tracked private configuration/key material blocks source packaging")
    tar_path = directory / f"cardchemy-{version}-source.tar"
    git("archive", "--format=tar", f"--prefix=cardchemy-{version}/", f"--output={tar_path.resolve()}", source_sha)
    archive = tar_path.with_suffix(".tar.gz")
    with tar_path.open("rb") as source, archive.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                compressed.write(chunk)
    tar_path.unlink()
    provenance = {**preflight, "schema_version": 1, "platform": "linux/amd64", "workflow_ref": os.environ.get("GITHUB_WORKFLOW_REF"), "run_url": f"https://github.com/{REPOSITORY}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}", "images": images}
    (directory / "source-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    release = re.search(rf"(?ms)^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", changelog)
    notes = release.group(1).strip() if release else ""
    require(bool(notes), "Release notes cannot be empty")
    (directory / "release-notes.md").write_text(
        f"# Cardchemy {version}\n\nSource commit: `{source_sha}`. Platform: Linux/amd64.\n\n"
        "Verify the Sigstore checksum bundle and image digests using docs/RELEASING.md before deployment. "
        "This pre-1.0 release does not establish a production deployment, paid-provider evaluation, "
        "or completion of the separate v1.0 gate. Provider calls can incur charges; demo/tests need no paid quota.\n\n"
        + notes + "\n", encoding="utf-8",
    )
    names = sorted(required_artifacts(version) - {"SHA256SUMS", "SHA256SUMS.sigstore.json"})
    require(all((directory / name).is_file() for name in names), "A required release inventory artifact is missing")
    (directory / "SHA256SUMS").write_text("".join(f"{file_digest(directory / name)}  {name}\n" for name in names), encoding="utf-8")


def required_artifacts(version: str) -> set[str]:
    return {"source-provenance.json", "release-notes.md", "SHA256SUMS", "SHA256SUMS.sigstore.json", f"cardchemy-{version}-source.tar.gz"} | {f"{variant}.{suffix}.json" for variant in VARIANTS for suffix in ("sbom", "audit", "build", "manifest")}


def verify_package(directory: Path, version: str, source_sha: str, *, signed: bool = True) -> None:
    require(bool(VERSION_PATTERN.fullmatch(version)) and bool(SHA_PATTERN.fullmatch(source_sha)), "Package verification needs exact stable version/source")
    required = required_artifacts(version) - (set() if signed else {"SHA256SUMS.sigstore.json"})
    require(all((directory / name).is_file() and not (directory / name).is_symlink() and (directory / name).stat().st_size > 0 for name in required), "Release package inventory is incomplete")
    if signed:
        require({entry.name for entry in directory.iterdir()} == required,
                "Downloaded release package contains unexpected files")
    expected = required_artifacts(version) - {"SHA256SUMS", "SHA256SUMS.sigstore.json"}
    observed = set()
    for line in (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
        require(match is not None, "Checksum manifest contains an unsafe or malformed path")
        digest, filename = match.groups()
        require(filename in expected and filename not in observed, "Checksum manifest inventory disagrees")
        require(file_digest(directory / filename) == digest, "A release artifact checksum does not match")
        observed.add(filename)
    require(observed == expected, "Checksum manifest omits required artifacts")
    provenance = json.loads((directory / "source-provenance.json").read_text(encoding="utf-8"))
    require(provenance.get("source_sha") == source_sha and provenance.get("version") == version and provenance.get("tag") == f"v{version}", "Signed source/version metadata disagrees")
    require(provenance.get("repository") == REPOSITORY and provenance.get("certificate_identity") == CERTIFICATE_IDENTITY and provenance.get("oidc_issuer") == OIDC_ISSUER, "Signing provenance disagrees")
    require(provenance.get("schema_version") == 1 and provenance.get("platform") == "linux/amd64"
            and provenance.get("workflow_ref") == WORKFLOW_REF
            and type(provenance.get("ci_run_id")) is int and provenance["ci_run_id"] > 0
            and re.fullmatch(rf"https://github.com/{re.escape(REPOSITORY)}/actions/runs/[1-9][0-9]*", provenance.get("run_url", "")) is not None,
            "Hosted workflow/CI provenance disagrees")
    images = provenance.get("images", [])
    require(len(images) == len(VARIANTS) and {image.get("variant") for image in images} == set(VARIANTS), "Image inventory disagrees")
    require(images == [image_record(directory, variant, version, source_sha) for variant in VARIANTS], "Published image artifacts and signed provenance disagree")
    with tarfile.open(directory / f"cardchemy-{version}-source.tar.gz", "r:gz") as archive:
        prefix = f"cardchemy-{version}/"
        members = archive.getmembers()
        require(bool(members), "Source archive is empty")
        for member in members:
            parts = PurePosixPath(member.name).parts
            require((member.name.startswith(prefix) or (member.isdir() and member.name == prefix.rstrip("/")))
                    and ".." not in parts and "\\" not in member.name
                    and (member.isfile() or member.isdir())
                    and not any(part.casefold().startswith(".env") and part != ".env.example" for part in parts)
                    and not member.name.casefold().endswith((".key", ".pem", ".p12", ".pfx", ".jks", ".keystore")), "Source archive contains an unsafe/private member")
        comment = archive.pax_headers.get("comment")
        require(comment == source_sha, "Source archive Git commit does not match provenance")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-sha")
    parser.add_argument("--remote", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--package-dir", type=Path)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--verify-package", type=Path)
    parser.add_argument("--record-image", choices=VARIANTS)
    parser.add_argument("--verify-version-tag", choices=VARIANTS)
    args = parser.parse_args()
    try:
        require(sum(bool(item) for item in (args.remote, args.package_dir and not (args.record_image or args.verify_version_tag), args.verify_package, args.record_image, args.verify_version_tag)) <= 1, "Choose one release operation")
        local = {"version": args.version} if args.verify_package else validate_local(args.version)
        if args.remote or args.package_dir or args.verify_package or args.record_image or args.verify_version_tag:
            require(bool(args.source_sha) and bool(SHA_PATTERN.fullmatch(args.source_sha)), "Exact source SHA is required")
        if args.remote:
            require(git("status", "--porcelain") == "", "Remote release requires a clean committed checkout")
            local = validate_remote(args.version, args.source_sha)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(local, indent=2) + "\n", encoding="utf-8")
        if args.record_image:
            require(args.package_dir is not None, "Image metadata requires an artifact directory")
            record_registry_image(args.package_dir, args.record_image, args.version, args.source_sha)
        elif args.verify_version_tag:
            require(args.package_dir is not None, "Version tag verification requires an artifact directory")
            verify_version_tag(args.package_dir, args.verify_version_tag, args.version, args.source_sha)
        elif args.package_dir:
            require(args.preflight is not None, "Verified preflight file is required")
            prepare_package(args.package_dir, args.version, args.source_sha, json.loads(args.preflight.read_text(encoding="utf-8")))
            verify_package(args.package_dir, args.version, args.source_sha, signed=False)
        if args.verify_package:
            verify_package(args.verify_package, args.version, args.source_sha)
        print(f"Cardchemy {args.version}: release metadata verified; cryptographic signatures require Cosign verification")
        return 0
    except (ValueError, OSError, KeyError, TypeError, IndexError, SyntaxError, tarfile.TarError, subprocess.SubprocessError) as error:
        # Only our authored contract errors are shown; IO/provider output is not.
        print(f"Release readiness failed: {error}" if isinstance(error, ReleaseContractError) else "Release readiness failed: metadata unavailable")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
