#!/usr/bin/env python3
"""Compare OpenAPI paths with /api/v1/ strings in frontend api clients.

Usage:
  poetry run python scripts/check_openapi_frontend_coverage.py \\
    path/to/openapi.json

If openapi.json is omitted, tries OPENAPI_JSON env, then exits 0 with a
hint (CI may skip).

Exit code: 0 always (informational); prints unmatched paths.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

API_TS = ROOT / "frontend" / "src" / "lib" / "api.ts"
ADMIN_API = ROOT / "frontend" / "src" / "admin" / "lib" / "adminApi.ts"

PATH_RE = re.compile(r"[`'\"](/api/v1[^`'\"\s]+)[`'\"]")


def load_openapi(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def openapi_paths(spec: dict) -> list[str]:
    raw = spec.get("paths") or {}
    out: list[str] = []
    for p, methods in raw.items():
        if not isinstance(methods, dict):
            continue
        if not p.startswith("/api/v1"):
            continue
        for m in methods:
            if m.upper() in frozenset(
                {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"},
            ):
                out.append(p)
                break
    return sorted(set(out))


def frontend_literals() -> str:
    parts = []
    if API_TS.exists():
        parts.append(API_TS.read_text(encoding="utf-8"))
    if ADMIN_API.exists():
        parts.append(ADMIN_API.read_text(encoding="utf-8"))
    return "\n".join(parts)


def normalize_candidate(path: str) -> str:
    p = path.split("?", 1)[0]
    for token in (
        "${",
        "${encodeURIComponent(",
        "`",
    ):
        if token in p:
            return ""
    out = re.sub(r"\$\{[^}]+\}", "*", p)
    out = re.sub(r":\w+", "*", out)
    return out


def collected_frontend_paths(text: str) -> set[str]:
    found: set[str] = set()
    for m in PATH_RE.finditer(text):
        n = normalize_candidate(m.group(1))
        if n:
            found.add(n)
    return found


def match_openapi_path(
    template: str,
    literals: set[str],
) -> bool:
    if template in literals:
        return True
    esc = re.escape(template).replace(r"\*", r"[^/]+")
    rx = re.compile("^" + esc + "$")
    return any(rx.match(lit) for lit in literals)


def main() -> None:
    openapi_arg = sys.argv[1] if len(sys.argv) > 1 else None
    env_path = __import__("os").environ.get("OPENAPI_JSON")
    candidate = openapi_arg or env_path
    if not candidate:
        print(
            "check_openapi_frontend_coverage: no openapi.json; "
            "pass path or set OPENAPI_JSON",
        )
        return
    path = Path(candidate)
    if not path.is_file():
        print(f"check_openapi_frontend_coverage: not a file: {path}")
        return

    spec = load_openapi(path)
    oas = openapi_paths(spec)
    literals = collected_frontend_paths(frontend_literals())

    missing_ui: list[str] = []
    for tmpl in oas:
        if "/internal/" in tmpl:
            continue
        if not match_openapi_path(tmpl, literals):
            missing_ui.append(tmpl)

    print(
        f"OpenAPI /api/v1 paths: {len(oas)}, "
        f"frontend literal paths: {len(literals)}",
    )
    if missing_ui:
        print(
            "\nPossibly unused by Mini App / admin client "
            "(heuristic; dynamic segments may false-positive):\n",
        )
        for p in missing_ui[:200]:
            print(f"  {p}")
        if len(missing_ui) > 200:
            print(f"  ... and {len(missing_ui) - 200} more")
    else:
        print("No unmatched paths (heuristic).")


if __name__ == "__main__":
    main()
