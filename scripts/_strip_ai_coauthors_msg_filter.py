"""stdin/stdout helper for git filter-branch --msg-filter (do not run directly)."""

from __future__ import annotations

import re
import sys

CLAUDE_COAUTHOR = re.compile(r"^Co-Authored-By:\s*Claude\b.*$", re.IGNORECASE)
CURSOR_COAUTHOR = re.compile(r"^Co-Authored-By:\s*Cursor\b.*$", re.IGNORECASE)
CURSOR_EMAIL_COAUTHOR = re.compile(
    r"^Co-Authored-By:.*cursoragent@cursor\.com\s*$",
    re.IGNORECASE,
)
ANTHROPIC_COAUTHOR = re.compile(
    r"^Co-Authored-By:.*@anthropic\.com\s*$",
    re.IGNORECASE,
)
MADE_WITH_CURSOR = re.compile(r"^Made-with:\s*Cursor\s*$", re.IGNORECASE)

RULES = (
    CLAUDE_COAUTHOR,
    CURSOR_COAUTHOR,
    CURSOR_EMAIL_COAUTHOR,
    ANTHROPIC_COAUTHOR,
    MADE_WITH_CURSOR,
)


def main() -> None:
    body = sys.stdin.read()
    kept: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if any(p.match(stripped) for p in RULES):
            continue
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    out = "\n".join(kept)
    if body.endswith("\n") and out:
        out += "\n"
    sys.stdout.write(out)


if __name__ == "__main__":
    main()
