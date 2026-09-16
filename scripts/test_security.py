"""Isolated local equivalents of CI secret/container gates; never mounts operator data."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
from datetime import datetime, timezone

from test_services import ROOT, system_environment

GITLEAKS = "ghcr.io/gitleaks/gitleaks:v8.24.2@sha256:b5918eb91b8d2473cec722f066abb4352e4ffdc4ec9f4283ec143aba9ec9ebc4"
TRIVY = "aquasec/trivy:0.70.0@sha256:be1190afcb28352bfddc4ddeb71470835d16462af68d310f9f4bca710961a41e"
IMAGES = ("backend", "backend-ocr", "frontend")


def run(*command: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=ROOT, env=system_environment(), check=check)


def scan_workspace() -> int:
    workspace = (ROOT / ".agent/.verification/security").resolve()
    if not workspace.is_relative_to(ROOT / ".agent/.verification"):
        raise RuntimeError("Security workspace must stay within the repository verification directory")
    if workspace.exists():
        raise RuntimeError("Security workspace already exists; inspect it before a new run")
    reports = ROOT / "artifacts/security"
    reports.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True)
    try:
        source, history = workspace / "source", workspace / "history.git"
        # This retained directory contains only Trivy's public advisory database.
        cache = reports.parent / "trivy-cache"
        source.mkdir()
        cache.mkdir(exist_ok=True)
        paths = subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT, env=system_environment(),
        ).decode().split("\0")
        for name in set(paths):
            if not name:
                continue
            original = ROOT / name
            resolved = original.resolve()
            if original.is_symlink() or not resolved.is_relative_to(ROOT) or not original.is_file():
                continue
            relative = original.relative_to(ROOT)
            if any(part.startswith(".env") and part != ".env.example" for part in relative.parts):
                raise RuntimeError("An operator environment file cannot enter a scanner snapshot")
            copied = source / relative
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, copied)
        run("git", "clone", "--bare", "--no-hardlinks", "--local", ".", str(history))
        run("git", "-C", str(history), "config", "--unset", "remote.origin.url")
        # Scan the prospective local change too, without writing the real Git
        # checkout or inheriting hooks/signing credentials into this export.
        exported_git = ["git", "--git-dir", str(history), "--work-tree", str(source)]
        run(*exported_git, "add", "--all")
        run(*exported_git, "-c", "user.name=Isolated security verification",
            "-c", "user.email=verification@example.invalid", "-c", "commit.gpgsign=false",
            "-c", "core.hooksPath=/dev/null", "commit", "--allow-empty", "--quiet",
            "-m", "Isolated Git-visible working-tree snapshot")

        # Public database download happens before any private source/image is mounted.
        run("docker", "run", "--rm", "-v", f"{cache}:/cache", TRIVY, "--quiet",
            "image", "--cache-dir", "/cache", "--download-db-only")
        failures = []
        result = run("docker", "run", "--rm", "--network", "none",
                     "-v", f"{history}:/repo:ro", "-v", f"{source}:/source:ro",
                     "-v", f"{reports}:/reports", GITLEAKS,
                     "git", "/repo", "--redact", "--exit-code=1",
                     "--config=/source/.gitleaks.toml",
                     "--gitleaks-ignore-path=/source/.gitleaksignore",
                     "--report-format=json", "--report-path=/reports/gitleaks.json", check=False)
        if result.returncode:
            failures.append("git-history-secrets")
        result = run("docker", "run", "--rm", "--network", "none",
                     "-v", f"{source}:/source:ro", "-v", f"{cache}:/cache",
                     TRIVY, "fs", "--cache-dir", "/cache", "--scanners", "secret",
                     "--offline-scan", "--skip-db-update", "--exit-code", "1", "/source", check=False)
        if result.returncode:
            failures.append("worktree-secrets")
        identities = {}
        for image in IMAGES:
            image_ref = f"cardchemy-{image}:phase9-ci"
            archive = workspace / f"{image}.tar"
            identities[image] = subprocess.check_output(
                ["docker", "image", "inspect", "--format", "{{.Id}}", image_ref],
                env=system_environment(),
            ).decode().strip()
            # Save the immutable identity, even if a concurrent rebuild moves
            # the local tag while the archive is being scanned.
            run("docker", "image", "save", "--output", str(archive), identities[image])
            common = ["docker", "run", "--rm", "--network", "none",
                      "-v", f"{archive}:/image.tar:ro", "-v", f"{cache}:/cache",
                      "-v", f"{reports}:/reports", TRIVY, "image",
                      "--cache-dir", "/cache", "--input", "/image.tar",
                      "--offline-scan", "--skip-db-update", "--skip-java-db-update"]
            result = run(*common, "--scanners", "vuln", "--severity", "HIGH,CRITICAL",
                         "--exit-code", "1", "--format", "json",
                         "--output", f"/reports/{image}.audit.json", check=False)
            if result.returncode:
                failures.append(f"{image}-vulnerabilities")
            run(*common, "--format", "cyclonedx", "--output", f"/reports/{image}.sbom.json")
            archive.unlink()
        metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
            "source_has_local_changes": bool(subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=ROOT, env=system_environment(),
            ).strip()),
            "snapshot_commit": subprocess.check_output(
                [*exported_git, "rev-parse", "HEAD"], cwd=ROOT, env=system_environment(),
            ).decode().strip(),
            "image_ids": identities,
            "scanners": {"gitleaks": GITLEAKS, "trivy": TRIVY}, "failed_gates": failures,
        }
        (reports / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        hashes = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}" for p in sorted(reports.iterdir())
                  if p.is_file() and p.name != "SHA256SUMS"]
        (reports / "SHA256SUMS").write_text("\n".join(hashes) + "\n")
        if failures:
            print("Security gates failed: " + ", ".join(failures))
            return 1
        print("Git/worktree secrets and all three container gates passed; SBOMs and checksums retained in artifacts/security.")
        return 0
    finally:
        # Resolved target checked above; it contains only this run's private scanner snapshots.
        def remove_readonly(function, name, error):
            target = Path(name).resolve()
            if not target.is_relative_to(workspace) or not isinstance(error[1], PermissionError):
                raise error[1]
            os.chmod(target, target.stat().st_mode | stat.S_IWUSR)
            function(name)

        # Git object files are read-only on Windows; keep cleanup bounded while
        # allowing their generated export to be removed on all supported hosts.
        shutil.rmtree(workspace, onerror=remove_readonly)


if __name__ == "__main__":
    raise SystemExit(scan_workspace())
