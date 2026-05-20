from __future__ import annotations


def has_nonempty_synced_lines(value: object) -> bool:
    if not isinstance(value, list):
        return False
    for item in value:
        if not isinstance(item, dict):
            continue
        if not str(item.get("text") or "").strip():
            continue
        time_ms = item.get("time_ms")
        if isinstance(time_ms, bool):
            continue
        if isinstance(time_ms, int | float) and time_ms >= 0:
            return True
    return False
