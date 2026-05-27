"""Deprecated alias — use scripts/backfill_internal_ugc_transcodes.py."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

if __name__ == "__main__":
    target = _ROOT / "scripts" / "backfill_internal_ugc_transcodes.py"
    raise SystemExit(runpy.run_path(str(target), run_name="__main__"))
