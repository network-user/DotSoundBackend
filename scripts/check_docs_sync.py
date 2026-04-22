"""Verify that duplicated policy docs are byte-identical across repos.

Source of truth is always DotSoundBackend. Copies in DotSoundBot and
DotSoundPrivateCore must match the Backend version exactly.

Usage:
    python scripts/check_docs_sync.py

Exit codes:
    0 - all synced docs are in sync
    1 - one or more docs diverge; unified diff is printed
    2 - a peer repo path is missing (configurable via env vars)

Peer repo paths default to ``../DotSoundBot`` and ``../DotSoundPrivateCore``
relative to this Backend repo. Override with:
    DOTSOUND_BOT_PATH=...
    DOTSOUND_PRIVATE_CORE_PATH=...
"""

from __future__ import annotations

import difflib
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _peer(env_name: str, default_sibling: str) -> Path:
    override = os.environ.get(env_name)
    if override:
        return Path(override).resolve()
    return (BACKEND_ROOT.parent / default_sibling).resolve()


BOT_ROOT = _peer("DOTSOUND_BOT_PATH", "DotSoundBot")
PRIVATE_CORE_ROOT = _peer(
    "DOTSOUND_PRIVATE_CORE_PATH", "DotSoundPrivateCore"
)

# Each entry: (relative-path, [peer-roots-that-must-match-backend])
#
# Only true duplicates go here. Current state: all policy-style docs
# with the same filename across the three repos are actually per-repo
# variants (each tuned to its own scope), not true duplicates. This
# list is intentionally empty; it is kept as scaffolding so that if a
# future policy doc must be kept byte-identical, we only add an entry
# here.
#
# Examples of docs that LOOK duplicated but are NOT synced by design:
#   - docs/ai-boundary-policy.md
#   - docs/private-boundary-inventory.md
#   - docs/private-core-dependency-policy.md
#   - docs/public-release-cut.md
SYNCED_DOCS: list[tuple[str, list[Path]]] = []


def _read(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def _compare(source: Path, copy: Path, rel: str) -> bool:
    src_lines = _read(source)
    cpy_lines = _read(copy)
    if src_lines == cpy_lines:
        return True
    diff = difflib.unified_diff(
        src_lines,
        cpy_lines,
        fromfile=f"{source} (source of truth)",
        tofile=f"{copy} (copy)",
        n=2,
    )
    sys.stdout.write(f"\nDRIFT in {rel}:\n")
    sys.stdout.writelines(diff)
    return False


def main() -> int:
    missing: list[Path] = []
    for root in (BOT_ROOT, PRIVATE_CORE_ROOT):
        if not root.exists():
            missing.append(root)
    if missing:
        sys.stderr.write(
            "Peer repo path(s) not found:\n  "
            + "\n  ".join(str(p) for p in missing)
            + "\nSet DOTSOUND_BOT_PATH / "
            + "DOTSOUND_PRIVATE_CORE_PATH to override.\n"
        )
        return 2

    drift = 0
    checked = 0
    for rel, peers in SYNCED_DOCS:
        src = BACKEND_ROOT / rel
        if not src.exists():
            sys.stderr.write(
                f"[skip] source missing: {src}\n"
            )
            continue
        for peer_root in peers:
            cpy = peer_root / rel
            if not cpy.exists():
                sys.stderr.write(
                    f"[skip] copy missing: {cpy}\n"
                )
                continue
            checked += 1
            if not _compare(src, cpy, rel):
                drift += 1

    if drift:
        sys.stdout.write(
            f"\n{drift} drift(s) out of {checked} check(s). "
            "Sync copies to match Backend source of truth.\n"
        )
        return 1

    sys.stdout.write(
        f"OK: {checked} synced doc(s) match across repos.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
