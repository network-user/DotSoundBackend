from __future__ import annotations

import sys
from pathlib import Path

SKIP_PARTS = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".venv",
    "venv",
    "coverage",
    "htmlcov",
}

SCAN_SUFFIXES = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".html",
    ".css",
    ".yml",
    ".yaml",
    ".toml",
)


def _has_cyrillic(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if 0x0400 <= code <= 0x04FF:
            return True
    return False


def _iter_text_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        files.append(path)
    return files


def _scan_file(path: Path) -> list[tuple[int, str, str]]:
    try:
        data = path.read_bytes()
    except OSError:
        return []
    violations: list[tuple[int, str, str]] = []
    for lineno, raw in enumerate(data.split(b"\n"), 1):
        try:
            decoded = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        try:
            recovered = decoded.encode("cp1251").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if recovered == decoded:
            continue
        if not _has_cyrillic(recovered):
            continue
        violations.append(
            (lineno, decoded.rstrip(), recovered.rstrip())
        )
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    violations: list[str] = []

    for file_path in _iter_text_files(repo_root):
        if file_path.name == "check_no_mojibake.py":
            continue
        for lineno, broken, fixed in _scan_file(file_path):
            rel = file_path.relative_to(repo_root)
            violations.append(
                f"{rel}:{lineno}: "
                f"{broken.strip()[:90]}  ->  "
                f"{fixed.strip()[:90]}"
            )

    if violations:
        print(
            "Mojibake detected (UTF-8 bytes saved as cp1251 "
            "and re-encoded). Fix the listed lines:",
            file=sys.stderr,
        )
        for line in violations:
            print(f"  {line}", file=sys.stderr)
        return 1

    print("No mojibake found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
