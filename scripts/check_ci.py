"""Validate local workflow syntax and the mandatory CI/security contract."""
from __future__ import annotations

import json
from pathlib import Path
import re

import yaml

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    workflows = ROOT / ".github" / "workflows"
    trusted = {"actions", "aquasecurity"}
    for path in sorted(workflows.glob("*.yml")):
        # BaseLoader preserves GitHub's YAML 'on' key rather than YAML 1.1 booleans.
        document = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
        require(isinstance(document, dict) and "on" in document and "jobs" in document,
                f"{path.name}: missing event or jobs")
        require("pull_request_target" not in document["on"],
                f"{path.name}: privileged pull_request_target is forbidden")
        require(document.get("permissions") == {"contents": "read"},
                f"{path.name}: workflow token must remain read-only")
        for name, job in document["jobs"].items():
            require("timeout-minutes" in job, f"{path.name}/{name}: missing timeout")
            require("continue-on-error" not in job, f"{path.name}/{name}: cannot ignore job failures")
            for step in job.get("steps", []):
                require("continue-on-error" not in step, f"{path.name}/{name}: cannot ignore step failures")
                if "uses" in step:
                    action = step["uses"]
                    require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}", action)),
                            f"{path.name}/{name}: action must use a full commit SHA")
                    require(action.split("/")[0] in trusted, f"{path.name}/{name}: unreviewed action owner")
        print(f"Validated {path.relative_to(ROOT).as_posix()}")
    ci = yaml.load((workflows / "ci.yml").read_text(), Loader=yaml.BaseLoader)
    require({"push", "pull_request", "merge_group", "workflow_dispatch"} <= set(ci["on"]),
            "CI must run for commits, pull requests, merge queues and manual rehearsals")
    jobs = ci["jobs"]
    mandatory = {"backend-offline", "postgres-migrations", "mailpit", "frontend", "journey",
                 "dependency-audit", "secret-scan", "containers"}
    require(mandatory <= set(jobs), "A mandatory CI gate is missing")
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
    for filename in ("coverage-budget.json", "bundle-budget.json"):
        json.loads((ROOT / ".github" / filename).read_text())
    print("Mandatory CI/protection contracts and budget JSON validated.")


if __name__ == "__main__":
    main()
