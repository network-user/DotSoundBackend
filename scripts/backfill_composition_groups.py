"""Optional backfill: assign ``composition_group_id`` for known duplicate groups.

This script is a stub. Run ``--help`` for future CLI when batch rules are defined.
By default the API resolves variants heuristically without this column.

Usage (placeholder)::

    poetry run python scripts/backfill_composition_groups.py --help
"""

from __future__ import annotations

import argparse


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Backfill tracks.composition_group_id (stub)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="No database writes",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    print(
        "backfill_composition_groups: not implemented; "
        f"dry_run={args.dry_run}. "
        "Use explicit composition_group_id via admin tooling when ready."
    )


if __name__ == "__main__":
    main()
