"""Parse track titles to extract implied artist credits."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# "Artist - Title" (spaces required around any dash variant)
_PREFIX = re.compile(r'^(.+?)\s+[-–—]\s+(.+)$')

# feat / ft / featuring inside brackets or at end of string
_FEAT = re.compile(
    r'[\(\[]\s*(?:feat\.?|ft\.?|featuring|with)\s+([^\)\]]+?)\s*[\)\]]'
    r'|\b(?:feat\.?|ft\.?|featuring)\b\s+(.+?)(?=\s*[\(\[\-–—]|$)',
    re.IGNORECASE,
)

# Split multiple artists: "A, B & C"
_SPLIT = re.compile(r'\s*,\s*|\s+(?:&|×)\s+')

_FEAT_MARKER = re.compile(r'\b(?:feat\.?|ft\.?|featuring)\b', re.IGNORECASE)


@dataclass
class TitleParseResult:
    prefix_artist: str | None = None   # from "Artist - Title"
    featured: list[str] = field(default_factory=list)  # from feat/ft

    def is_empty(self) -> bool:
        return self.prefix_artist is None and not self.featured

    def all_names(self) -> list[str]:
        out: list[str] = []
        if self.prefix_artist:
            out.append(self.prefix_artist)
        out.extend(self.featured)
        return out


def _clean(s: str) -> str:
    return s.strip(" ()[].,—–-")


def parse_title(title: str) -> TitleParseResult:
    result = TitleParseResult()

    # Pattern 1: "prefix - rest" — only if prefix looks like a name
    m = _PREFIX.match(title)
    if m:
        prefix = _clean(m.group(1))
        if 2 <= len(prefix) <= 80 and not _FEAT_MARKER.search(prefix):
            result.prefix_artist = prefix

    # Pattern 2: feat / ft in parentheses or bare
    for m in _FEAT.finditer(title):
        raw = (m.group(1) or m.group(2) or "").strip()
        for part in _SPLIT.split(raw):
            name = _clean(part)
            if 2 <= len(name) <= 80:
                result.featured.append(name)

    return result
