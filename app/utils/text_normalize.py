"""Lightweight text normalization helpers for matching purposes.

Used by the import pipeline to compare ``title``/``artist`` strings
across providers without burning an external search call when the
same track already exists locally. Keep this purely transport-level:
lower + strip. Mirrors the SQL prefilter shape (``lower(trim(...))``)
so a Python-side comparison cannot diverge from the DB-side filter.
"""

from __future__ import annotations


def normalize_for_match(value: str | None) -> str:
    if not value:
        return ""
    return value.lower().strip()
