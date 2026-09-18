"""Scan and inventory the exact external database image without operator data.

Only a reviewed image archive and ignored reports enter the disposable scanner.
Its fresh public advisory database lives in a 4 GiB tmpfs, and scanning is
offline after the advisory download. No provider requests or database volumes
are used.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import time
from uuid import uuid4

from check_runtime_artifacts import validate
from runtime_database import ensure_database_image
from test_services import ROOT, cleanup_containers, system_environment


TRIVY = "aquasec/trivy:0.70.0@sha256:be1190afcb28352bfddc4ddeb71470835d16462af68d310f9f4bca710961a41e"


def docker(*arguments: str, label: str, check: bool = True,
           diagnostic_file: Path | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(["docker", *arguments], cwd=ROOT,
                            env=system_environment(), capture_output=True, text=True)
    if diagnostic_file is not None:
        # Only public-image scanner commands use this path. Never record operator
        # configuration or logs from application/database containers here.
        diagnostic_file.write_text((result.stdout + result.stderr)[-65536:], encoding="utf-8")
        if result.returncode:
            print(f"Public image scanner diagnostic ({label}):\n{(result.stdout + result.stderr)[-8192:]}")
    if check and result.returncode:
        detail = f"; public scanner diagnostics retained in {diagnostic_file.relative_to(ROOT)}" if diagnostic_file else "; details withheld"
        raise RuntimeError(f"{label} failed (exit {result.returncode}){detail}")
    return result


def main() -> int:
    database = validate(ROOT)
    identity, platform = ensure_database_image(ROOT)
    suffix = uuid4().hex[:12]
    scanner = f"cardchemy-database-artifact-{suffix}"
    workspace = (ROOT / ".agent/.verification" / scanner).resolve()
    if not workspace.is_relative_to((ROOT / ".agent/.verification").resolve()):
        raise RuntimeError("Database scanner workspace must remain in the verification directory")
    workspace.mkdir(parents=True, exist_ok=False)
    reports = ROOT / "artifacts/database-artifact" / suffix
    reports.mkdir(parents=True, exist_ok=False)
    archive = workspace / "database.tar"
    owned = []
    started = time.monotonic()
    try:
        if not identity.startswith("sha256:") or len(identity) != 71:
            raise RuntimeError("Immutable database image identity is invalid")
        actual_platform = docker("image", "inspect", "--format", "{{.Os}}/{{.Architecture}}", identity,
                                 label="Inspect database image platform").stdout.strip()
        if actual_platform != platform:
            raise RuntimeError("Database image does not match the supported platform")
        docker("image", "save", "--output", str(archive), identity,
               label="Export immutable public database image")
        with archive.open("rb") as stream:
            archive_sha = hashlib.file_digest(stream, "sha256").hexdigest()
        with tarfile.open(archive) as image_archive:
            manifest_stream = image_archive.extractfile("manifest.json")
            if manifest_stream is None:
                raise RuntimeError("Database image archive has no Docker manifest")
            manifest = json.load(manifest_stream)
            config_stream = image_archive.extractfile(manifest[0]["Config"])
            if config_stream is None:
                raise RuntimeError("Database image archive has no image configuration")
            config_digest = "sha256:" + hashlib.sha256(config_stream.read()).hexdigest()
        docker("pull", "--platform", platform, TRIVY, label="Pull reviewed scanner")
        owned.append(scanner)
        docker("run", "-d", "--rm", "--platform", platform, "--name", scanner, "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges", "--read-only",
               "--tmpfs", "/tmp:rw,size=2g", "--tmpfs", "/cache:rw,size=4g",
               "-v", f"{archive}:/image.tar:ro", "-v", f"{reports}:/reports",
               "--entrypoint", "sleep", TRIVY, "infinity",
               label="Start disposable public-artifact scanner")
        docker("exec", scanner, "trivy", "image", "--cache-dir", "/cache",
               "--download-db-only", label="Download fresh public advisory database")
        advisory_metadata = json.loads(docker("exec", scanner, "cat", "/cache/db/metadata.json",
                                              label="Inspect fresh advisory database metadata").stdout)
        docker("network", "disconnect", "bridge", scanner,
               label="Disable scanner networking before image analysis")
        common = ["exec", scanner, "trivy", "image", "--cache-dir", "/cache",
                  "--input", "/image.tar", "--offline-scan", "--skip-db-update",
                  "--skip-java-db-update"]
        audit = docker(*common, "--scanners", "vuln", "--severity", "HIGH,CRITICAL",
                       "--ignore-unfixed=false", "--exit-code", "1", "--format", "json",
                       "--output", "/reports/database-audit.json",
                       label="Scan exact database artifact", check=False,
                       diagnostic_file=reports / "database-audit.log")
        if not (reports / "database-audit.json").is_file():
            raise RuntimeError(f"Database scanner produced no audit report; public diagnostics retained in {reports.relative_to(ROOT)}")
        docker(*common, "--format", "cyclonedx", "--output", "/reports/database.sbom.json",
               label="Generate exact database artifact SBOM",
               diagnostic_file=reports / "database-sbom.log")
        audit_report = json.loads((reports / "database-audit.json").read_text(encoding="utf-8"))
        sbom = json.loads((reports / "database.sbom.json").read_text(encoding="utf-8"))
        if (audit_report.get("Metadata", {}).get("ImageID") != config_digest
                or not audit_report.get("Results")
                or sbom.get("bomFormat") != "CycloneDX" or not sbom.get("components")):
            raise RuntimeError("Database audit/SBOM identity or package inventory is incomplete")
        finding_count = sum(len(result.get("Vulnerabilities") or [])
                            for result in audit_report["Results"])
        if audit.returncode == 0 and finding_count:
            raise RuntimeError("Database audit exit code disagrees with its serious findings")
        metadata = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database": database,
            "image_id": identity,
            "image_config_digest": config_digest,
            "image_archive_sha256": archive_sha,
            "runtime_inventory_sha256": hashlib.sha256((ROOT / "runtime-artifacts.json").read_bytes()).hexdigest(),
            "scanner": TRIVY,
            "fresh_advisory_database": True,
            "advisory_database": advisory_metadata,
            "scan_network": "none",
            "severity": ["HIGH", "CRITICAL"],
            "ignore_unfixed": False,
            "audit_exit_code": audit.returncode,
            "high_critical_finding_count": finding_count,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        (reports / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        hashes = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}"
                  for path in sorted(reports.iterdir()) if path.is_file()]
        (reports / "SHA256SUMS").write_text("\n".join(hashes) + "\n", encoding="utf-8")
        if audit.returncode:
            print(f"External database vulnerability gate failed; exact-image reports retained in {reports.relative_to(ROOT)}.")
            return 1
        print(f"Reviewed database HIGH/CRITICAL gate and CycloneDX SBOM passed; reports retained in {reports.relative_to(ROOT)}.")
        return 0
    finally:
        try:
            cleanup_containers(owned)
        finally:
            shutil.rmtree(workspace)


if __name__ == "__main__":
    raise SystemExit(main())
