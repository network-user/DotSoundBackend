from __future__ import annotations

import tomllib
from pathlib import Path

FORBIDDEN_LITERALS = (
    "X-Internal-Secret",
    "/internal/profile-audios/",
    "/internal/download-audio",
    "/internal/send-auth-code",
    "/internal/send-login-notification",
    "/api/v1/auth/generate-code",
)

SKIP_PARTS = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "alembic",
}


def _iter_python_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_root.rglob("*.py"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        files.append(path)
    return files


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    violations: list[str] = []

    for file_path in _iter_python_files(repo_root):
        if file_path.name == "check_boundary_policy.py":
            continue
        text = file_path.read_text(encoding="utf-8")
        for token in FORBIDDEN_LITERALS:
            if token in text:
                rel = file_path.relative_to(repo_root)
                violations.append(f"{rel}: contains `{token}`")

    if violations:
        print("Boundary policy violations found:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    pyproject_path = repo_root / "pyproject.toml"
    pyproject_raw = pyproject_path.read_text(encoding="utf-8")
    pyproject_data = tomllib.loads(pyproject_raw)
    deps = pyproject_data["tool"]["poetry"]["dependencies"]
    private_core_dep = deps.get("dotsound-private-core")
    if private_core_dep is None:
        print("Missing `dotsound-private-core` dependency.")
        return 1
    if (
        isinstance(private_core_dep, dict)
        and "git" in private_core_dep
        and "tag" not in private_core_dep
        and "rev" not in private_core_dep
    ):
        print(
            "Git dependency for dotsound-private-core must pin "
            "tag or rev."
        )
        return 1

    print("Boundary policy checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

