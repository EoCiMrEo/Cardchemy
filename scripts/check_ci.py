"""Validate local workflow syntax and the mandatory CI/security contract."""
from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]
COSIGN_INSTALLER = "sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6"
RELEASE_PERMISSIONS = {
    "contents": "write", "packages": "write", "id-token": "write",
    "actions": "read", "checks": "read",
}


def validate_runtime_artifacts() -> None:
    """Load the sibling checker from its path for CLI and importlib test callers."""
    path = ROOT / "scripts" / "check_runtime_artifacts.py"
    spec = importlib.util.spec_from_file_location("check_runtime_artifacts", path)
    require(spec is not None and spec.loader is not None,
            "Cannot load the database runtime artifact checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.validate(ROOT)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def validate_workflow(document: dict, filename: str) -> None:
    trusted = {"actions", "aquasecurity"}
    require(isinstance(document, dict) and "on" in document and "jobs" in document,
            f"{filename}: missing event or jobs")
    require("pull_request_target" not in document["on"],
            f"{filename}: privileged pull_request_target is forbidden")
    require(document.get("permissions") == {"contents": "read"},
            f"{filename}: workflow token must remain read-only")
    if filename == "production-rehearsal.yml":
        require(set(document["on"]) == {"workflow_dispatch"}
                and set(document["jobs"]) == {"clean-install-recovery"},
                "Production rehearsal must remain a single manually dispatched job")
        rehearsal = document["jobs"]["clean-install-recovery"]
        require(rehearsal.get("if") == "github.repository == 'EoCiMrEo/Cardchemy' && github.ref == 'refs/heads/main'"
                and "secrets." not in json.dumps(document),
                "Production rehearsal must run only approved main without repository secrets")
    if filename == "release-sbom.yml":
        require(set(document["on"]) == {"workflow_dispatch"}
                and set(document["jobs"]) == {"preflight", "release"},
                "Signed release must be manually dispatched through its two guarded jobs")
        preflight = document["jobs"]["preflight"]
        require(preflight.get("if") == "github.repository == 'EoCiMrEo/Cardchemy' && github.ref == 'refs/heads/main'",
                "Release preflight must run only in approved main")
        require(preflight.get("permissions") == {"contents": "read", "actions": "read", "checks": "read"},
                "Release preflight permissions must remain narrowly read-only")
        require(any(step.get("uses") == COSIGN_INSTALLER for step in document["jobs"]["release"].get("steps", [])),
                "Signed release must install the reviewed Cosign bootstrap")
        steps = document["jobs"]["release"].get("steps", [])
        scanner = next((step for step in steps if step.get("name") == "Audit default backend and install the pinned scanner"), None)
        require(scanner is not None and scanner.get("with", {}).get("cache-dir")
                == "${{ runner.temp }}/cardchemy-trivy-cache",
                "Trivy action must not write its database under the checkout")
        inventory = next((step for step in steps if step.get("name") == "Audit remaining runtimes and inventory all exact images"), None)
        require(inventory is not None and inventory.get("env", {}).get("TRIVY_CACHE_DIR")
                == "${{ runner.temp }}/cardchemy-trivy-cache",
                "Direct Trivy scans must reuse the runner-temporary database cache")
        ordered = (
            "Publish unique release tags and verify keyless image signatures",
            "Prepare source, notes and provenance",
            "Sign and verify the checksum manifest",
            "Final main/CI/registry-tag guard before creating the signed draft",
            "Create annotated version tag and verified draft release",
        )
        positions = [next((index for index, step in enumerate(steps) if step.get("name") == name), -1)
                     for name in ordered]
        require(all(position >= 0 and sum(step.get("name") == name for step in steps) == 1
                    for name, position in zip(ordered, positions))
                and positions == sorted(positions),
                "Signed release must publish unique images, sign and draft in order")
        publish = steps[positions[0]].get("run", "")
        pushes = [(index, match.group()) for index, step in enumerate(steps)
                  for match in re.finditer(r"\bdocker\s+push\b", step.get("run", ""))]
        require(pushes == [(positions[0], 'docker push')]
                and re.search(r'(?m)^\s*release_tag="\$image:v\$VERSION-\$SOURCE_SHA-\$GITHUB_RUN_ID-\$GITHUB_RUN_ATTEMPT"\s*$', publish) is not None
                and re.search(r'(?m)^\s*docker push "\$release_tag"\s*$', publish) is not None
                and '--record-image "$variant" --image-tag "$release_tag"' in publish
                and '--verify-release-tag "$variant"' in publish
                and "cosign sign --yes" in publish
                and "cosign verify-blob" in steps[positions[2]].get("run", "")
                and "--remote" in steps[positions[3]].get("run", "")
                and '--verify-release-tag "$variant"' in steps[positions[3]].get("run", "")
                and "gh release create" in steps[positions[4]].get("run", "")
                and "--draft" in steps[positions[4]].get("run", ""),
                "Only unique release tags may be pushed; image/signature inventory and draft must follow")
    for name, job in document["jobs"].items():
        require("timeout-minutes" in job, f"{filename}/{name}: missing timeout")
        require("continue-on-error" not in job, f"{filename}/{name}: cannot ignore job failures")
        permissions = job.get("permissions", {})
        if filename == "release-sbom.yml" and name == "release":
            require("TRIVY_CACHE_DIR" not in job.get("env", {}),
                    "Runner temp must be resolved in a Trivy step, not job-level env")
            require(permissions == RELEASE_PERMISSIONS,
                    "Only the guarded release job may write approved contents/packages and obtain signing identity")
            require(job.get("needs") == "preflight"
                    and job.get("if") == "github.repository == 'EoCiMrEo/Cardchemy' && github.ref == 'refs/heads/main'",
                    "Privileged release job requires successful preflight in approved main")
        else:
            require(isinstance(permissions, dict) and all(value == "read" for value in permissions.values()),
                    f"{filename}/{name}: non-release tokens must remain read-only")
        for step in job.get("steps", []):
            require("continue-on-error" not in step, f"{filename}/{name}: cannot ignore step failures")
            if "uses" in step:
                action = step["uses"]
                require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}", action)),
                        f"{filename}/{name}: action must use a full commit SHA")
                require(action.split("/")[0] in trusted or (filename == "release-sbom.yml" and name == "release" and action == COSIGN_INSTALLER),
                        f"{filename}/{name}: unreviewed action")
                if action == COSIGN_INSTALLER:
                    require(step.get("with", {}).get("cosign-release") == "v3.1.3",
                            "Cosign binary must use the reviewed version")


def main() -> None:
    workflows = ROOT / ".github" / "workflows"
    for path in sorted(workflows.glob("*.yml")):
        # BaseLoader preserves GitHub's YAML 'on' key rather than YAML 1.1 booleans.
        document = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        validate_workflow(document, path.name)
        print(f"Validated {path.relative_to(ROOT).as_posix()}")
    ci = yaml.load((workflows / "ci.yml").read_text(), Loader=yaml.BaseLoader)
    require({"push", "pull_request", "merge_group", "workflow_dispatch"} <= set(ci["on"]),
            "CI must run for commits, pull requests, merge queues and manual rehearsals")
    jobs = ci["jobs"]
    require(any(step.get("run") == "python scripts/check_context.py"
                for step in jobs["backend-offline"]["steps"]),
            "Backend CI must validate required repository context and local documentation links")
    require(any(step.get("run") == "python scripts/check_release.py --version 0.1.0"
                for step in jobs["backend-offline"]["steps"]),
            "Backend CI must validate local release/governance metadata")
    require(any(step.get("run") == "python scripts/prepare_release_notices.py --check"
                for step in jobs["backend-offline"]["steps"]),
            "Backend CI must validate redistributed code and brand notices")
    mandatory = {"backend-offline", "postgres-migrations", "database-artifact", "mailpit", "frontend", "journey",
                 "dependency-audit", "secret-scan", "containers"}
    require(any(step.get("run") == "python scripts/test_smtp_tls.py"
                for step in jobs["mailpit"]["steps"]),
            "Mandatory email CI must verify actual authenticated TLS delivery and recovery")
    require(mandatory <= set(jobs), "A mandatory CI gate is missing")
    database_steps = jobs["database-artifact"]["steps"]
    require(any(step.get("run") == "python scripts/check_runtime_artifacts.py"
                for step in database_steps), "Database CI must validate the artifact inventory")
    require(any(step.get("run") == "python scripts/runtime_database.py"
                for step in database_steps), "Database CI must inspect the reviewed extension runtime")
    require(any(step.get("run") == "python scripts/test_pgvector_restore.py"
                for step in database_steps),
            "Database CI must verify a populated pgvector backup and restore")
    require(any(step.get("run") == "python scripts/test_database_volume_upgrade.py"
                for step in database_steps),
            "Database CI must verify prior PostgreSQL16 data-path compatibility on an owned disposable volume")
    require(sum(step.get("run") == "python scripts/test_database_artifact.py"
                for step in database_steps) == 1,
            "Database CI must run one immutable-archive vulnerability/SBOM/provenance owner")
    database_upload = next((step for step in database_steps
                            if step.get("uses", "").startswith("actions/upload-artifact@")), {})
    retained = set(database_upload.get("with", {}).get("path", "").splitlines())
    require({"runtime-artifacts.json", "artifacts/database-artifact/*/database-audit.json",
             "artifacts/database-artifact/*/database.sbom.json",
             "artifacts/database-artifact/*/metadata.json",
             "artifacts/database-artifact/*/SHA256SUMS",
             "artifacts/database-volume-upgrade/*/metadata.json"} <= retained,
            "Database CI must retain exact image/config/archive/recipe audit/SBOM/recovery provenance")
    validate_runtime_artifacts()
    require(set(jobs["ci-required"]["needs"]) == set(jobs) - {"ci-required"},
            "ci-required must depend on every mandatory job")
    require(jobs["ci-required"].get("if") == "always()", "ci-required must report earlier failures")
    audit_commands = [step.get("run", "") for step in jobs["dependency-audit"]["steps"]]
    require(any(command.startswith("npm audit ") and "--omit" not in command
                and "--audit-level=low" in command for command in audit_commands),
            "Mandatory dependency review fallback must audit every npm scope")
    require(any("pip_audit --require-hashes" in command and "--strict" in command
                for command in audit_commands), "Python dependency review must audit the full hashed graph")
    protection = json.loads((ROOT / ".github" / "branch-protection.json").read_text())
    require(not protection["required_status_checks"].get("contexts")
            and protection["required_status_checks"]["checks"] == [{"context": "ci-required", "app_id": 15368}],
            "Branch protection and the CI aggregator disagree")
    require(protection["required_status_checks"]["strict"] and protection["enforce_admins"],
            "Protection must require current-base checks and include administrators")
    require(isinstance(protection.get("required_pull_request_reviews"), dict)
            and protection["required_pull_request_reviews"].get("dismiss_stale_reviews") is True
            and protection.get("required_conversation_resolution") is True
            and protection.get("allow_force_pushes") is False
            and protection.get("allow_deletions") is False,
            "Protection must preserve required PR flow, resolved conversations and shared history")
    for filename in ("coverage-budget.json", "bundle-budget.json"):
        json.loads((ROOT / ".github" / filename).read_text())
    print("Mandatory CI/protection contracts and budget JSON validated.")


if __name__ == "__main__":
    main()
