"""Fail if JSON coverage report branch % is below minimum (default 95)."""

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "path",
        nargs="?",
        default="coverage.json",
        type=Path,
        help="Path to coverage JSON (from --cov-report=json:...)",
    )
    parser.add_argument(
        "--min",
        type=float,
        default=95.0,
        dest="min_pct",
        help="Minimum percent_branches_covered (default 95)",
    )
    args = parser.parse_args()
    p: Path = args.path
    if not p.is_file():
        print(f"Missing {p}", file=sys.stderr)
        return 1
    data = json.loads(p.read_text(encoding="utf-8"))
    totals = data.get("totals", {})
    if "percent_branches_covered" not in totals:
        print("No branch data in report; use --cov-branch", file=sys.stderr)
        return 1
    got = float(totals["percent_branches_covered"])
    if got < args.min_pct - 0.0001:
        print(
            f"Branch coverage {got:.2f}% is below {args.min_pct}%.",
            file=sys.stderr,
        )
        return 1
    print(f"Branch coverage OK: {got:.2f}% (min {args.min_pct}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
