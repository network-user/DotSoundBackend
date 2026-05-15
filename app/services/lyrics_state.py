from __future__ import annotations


def has_nonempty_synced_lines(value: object) -> bool:
    if not isinstance(value, list):
        return False
    for item in value:
        if isinstance(item, dict) and str(item.get("text") or "").strip():
            return True
    return False
