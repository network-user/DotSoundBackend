"""Bidirectional transliteration for cross-script search.

Cyrillic → Latin : unidecode  ("Молодой" → "Molodoy")
Latin   → Cyrillic: phonetic table lookup ("Molodoy" → "Молодой")

Used at both index time (document building) and query time (search
query expansion).  Returns empty string on None/empty input — never
raises.
"""

from __future__ import annotations

from unidecode import unidecode

# Ordered longest → shortest so greedy matching prefers digraphs.
_LATIN_TO_CYR: list[tuple[str, str]] = [
    ("shch", "щ"),
    ("sch", "щ"),
    ("zh", "ж"),
    ("kh", "х"),
    ("ts", "ц"),
    ("ch", "ч"),
    ("sh", "ш"),
    ("yu", "ю"),
    ("ya", "я"),
    ("yo", "ё"),
    ("ye", "е"),
    ("yi", "й"),
    ("a", "а"),
    ("b", "б"),
    ("v", "в"),
    ("g", "г"),
    ("d", "д"),
    ("e", "е"),
    ("z", "з"),
    ("i", "и"),
    ("j", "й"),
    ("k", "к"),
    ("l", "л"),
    ("m", "м"),
    ("n", "н"),
    ("o", "о"),
    ("p", "п"),
    ("r", "р"),
    ("s", "с"),
    ("t", "т"),
    ("u", "у"),
    ("f", "ф"),
    ("h", "х"),
    ("c", "к"),
    ("y", "ы"),
    ("q", "к"),
    ("x", "кс"),
    ("w", "в"),
]


def _has_cyrillic(text: str) -> bool:
    return any("\u0400" <= ch <= "\u04ff" for ch in text)


def _has_latin(text: str) -> bool:
    return any("a" <= ch.lower() <= "z" for ch in text)


def cyrillic_to_latin(text: str) -> str:
    return unidecode(text).strip()


def latin_to_cyrillic(text: str) -> str:
    result: list[str] = []
    lower = text.lower()
    i = 0
    while i < len(lower):
        matched = False
        for lat, cyr in _LATIN_TO_CYR:
            if lower[i : i + len(lat)] == lat:
                result.append(cyr)
                i += len(lat)
                matched = True
                break
        if not matched:
            c = lower[i]
            if not c.isalpha():
                result.append(c)
            i += 1
    return "".join(result)


def transliterate(text: str | None) -> str:
    """Return transliterated variant of *text* for cross-script search.

    Cyrillic-only  → Latin  (via unidecode)
    Latin-only     → Cyrillic (via phonetic table)
    Mixed          → transliterate each whitespace token independently
    Empty / None   → ""
    """
    if not text or not text.strip():
        return ""
    stripped = text.strip()
    has_cyr = _has_cyrillic(stripped)
    has_lat = _has_latin(stripped)

    if has_cyr and not has_lat:
        return cyrillic_to_latin(stripped)
    if has_lat and not has_cyr:
        return latin_to_cyrillic(stripped)

    # Mixed script — transliterate token by token
    parts: list[str] = []
    for tok in stripped.split():
        if _has_cyrillic(tok) and not _has_latin(tok):
            parts.append(cyrillic_to_latin(tok))
        elif _has_latin(tok) and not _has_cyrillic(tok):
            parts.append(latin_to_cyrillic(tok))
        # Else: digits / punctuation-only tokens → skip
    return " ".join(parts)


__all__ = ["transliterate", "cyrillic_to_latin", "latin_to_cyrillic"]
