"""Run one authored sparse-control test through unchanged disposable PG guards.

No root .env, operator database or live provider is used. The canonical service
runner owns verified images, generated credentials, migrations and cleanup.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import test_services


TEST_PATH = "tests/postgres/test_postgres_sparse_generation_control.py"
REPORT_KEYS = frozenset({
    "source_pages", "authored_facts", "published_revisions", "original_requested_count",
    "pending_validated_count", "sets_before_choice", "sets_after_choice",
    "exact_selected_count", "injected_generation_calls", "injected_index_calls",
    "additional_calls_on_choice", "physical_remote_calls", "actual_cost_usd",
    "same_choice_replays", "denied_foreign_choice", "denied_excess_choice",
    "temporary_sources_after_choice", "candidate_stages_after_choice",
    "published_original_preserved",
})


def main() -> int:
    original_runner = test_services.run_service_tests
    original_argv = sys.argv
    output = test_services.ROOT / ".agent" / ".verification" / f"sparse-published-control-{uuid4().hex}"
    output.mkdir(parents=True, exist_ok=False)
    report_path = output / "aggregate.json"

    def focused_runner(command: list[str], *, cwd: Path, environment: dict[str, str]) -> int:
        if cwd != test_services.ROOT / "backend" or "postgres and not smtp_tls" not in command:
            raise RuntimeError("Sparse control refused an unexpected service-test invocation")
        result = original_runner(
            [*command, TEST_PATH], cwd=cwd,
            environment=environment | {"SPARSE_CONTROL_REPORT_PATH": str(report_path)},
        )
        if result == 0:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if not isinstance(report, dict) or set(report) != REPORT_KEYS or any(
                type(value) not in (int, float) or value < 0 for value in report.values()
            ):
                raise RuntimeError("Sparse control refused a nonnumeric aggregate")
            print("SPARSE_PUBLISHED_CONTROL=" + json.dumps(report, sort_keys=True, separators=(",", ":")))
            print("Sparse control aggregate: " + str(report_path.relative_to(test_services.ROOT)))
        return result

    try:
        test_services.run_service_tests = focused_runner
        sys.argv = [str(test_services.ROOT / "scripts" / "test_services.py"), "postgres"]
        return test_services.main()
    finally:
        test_services.run_service_tests = original_runner
        sys.argv = original_argv


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError):
        raise SystemExit("Sparse disposable control failed; no credential values were printed.")
