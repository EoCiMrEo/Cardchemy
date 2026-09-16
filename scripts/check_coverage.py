"""Enforce measured offline line+branch coverage globally and at critical boundaries."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    budget = json.loads((root / ".github" / "coverage-budget.json").read_text())
    report = json.loads(args.report.read_text())
    failures: list[str] = []
    total = report["totals"]["percent_covered"]
    print(f"Backend offline line+branch coverage: {total:.2f}% (floor {budget['overall_percent']}%)")
    if total < budget["overall_percent"]:
        failures.append("overall coverage")
    for key, name in (("line_percent", "percent_statements_covered"),
                      ("branch_percent", "percent_branches_covered")):
        value = report["totals"][name]
        print(f"{key}: {value:.2f}% (floor {budget[key]}%)")
        if value < budget[key]:
            failures.append(key)
    files = {path.replace("\\", "/").removeprefix("backend/"): value
             for path, value in report["files"].items()}
    for path, floor in budget["critical_files"].items():
        if path not in files:
            failures.append(f"missing coverage boundary {path}")
            continue
        value = files[path]["summary"]["percent_covered"]
        print(f"{path}: {value:.2f}% (floor {floor}%)")
        if value < floor:
            failures.append(path)
    if failures:
        raise SystemExit("Coverage budget failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()
