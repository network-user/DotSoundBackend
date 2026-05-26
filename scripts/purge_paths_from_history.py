"""Remove tracked paths from entire git history (safe, with bundle backup).

Default targets: coverage artifacts and Backend import probe scratch files.

Scan (no changes):
    python scripts/purge_paths_from_history.py --repo PATH

Apply (rewrites all refs, creates .bundle backup):
    python scripts/purge_paths_from_history.py --repo PATH --apply \\
        --i-understand-history-rewrite

After apply: git fetch origin && git push --force-with-lease origin main
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPOS = (
    BACKEND_ROOT,
    BACKEND_ROOT.parent / "DotSoundPrivateCore",
    BACKEND_ROOT.parent / "DotSoundBot",
    BACKEND_ROOT.parent / "DotSoundComputeWorker",
)

DEFAULT_EXACT = (
    ".coverage",
    "coverage.json",
    "coverage.xml",
    "htmlcov/.gitignore",
)
DEFAULT_GLOBS = (
    "scripts/_tmp_*",
    ".git-coauthor-backups/**",
)


@dataclass
class ScanResult:
    repo: Path
    paths_in_history: set[str] = field(default_factory=set)
    paths_to_purge: set[str] = field(default_factory=set)


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=check,
    )


def _git_ok(repo: Path) -> bool:
    proc = _run(["git", "-C", str(repo), "rev-parse", "--git-dir"], check=False)
    return proc.returncode == 0


def _is_clean(repo: Path) -> bool:
    proc = _run(["git", "-C", str(repo), "status", "--porcelain"], check=False)
    return proc.returncode == 0 and not proc.stdout.strip()


def _all_paths_in_history(repo: Path) -> set[str]:
    proc = _run(
        ["git", "-C", str(repo), "log", "--all", "--name-only", "--pretty=format:"],
    )
    out: set[str] = set()
    for line in proc.stdout.splitlines():
        p = line.strip().replace("\\", "/")
        if p:
            out.add(p)
    return out


def _match_paths(
    all_paths: set[str],
    exact: tuple[str, ...],
    globs: tuple[str, ...],
) -> set[str]:
    chosen: set[str] = set()
    for p in all_paths:
        norm = p.replace("\\", "/")
        if norm in exact:
            chosen.add(p)
            continue
        for g in globs:
            if fnmatch.fnmatch(norm, g):
                chosen.add(p)
    return chosen


def scan_repo(
    repo: Path,
    exact: tuple[str, ...],
    globs: tuple[str, ...],
) -> ScanResult:
    all_paths = _all_paths_in_history(repo)
    purge = _match_paths(all_paths, exact, globs)
    return ScanResult(
        repo=repo.resolve(),
        paths_in_history=all_paths,
        paths_to_purge=purge,
    )


def _backup_bundle(repo: Path, backups_dir: Path, label: str) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe = repo.name.replace(" ", "_")
    path = backups_dir / f"{safe}-pre-{label}-{stamp}.bundle"
    _run(["git", "-C", str(repo), "bundle", "create", str(path), "--all"])
    return path


def apply_purge(repo: Path, paths: set[str], backups_dir: Path) -> dict[str, object]:
    if not paths:
        return {"bundle": None, "removed_paths": []}
    bundle = _backup_bundle(repo, backups_dir, "purge-paths")
    quoted = " ".join(f'"{p}"' for p in sorted(paths))
    index_filter = f"git rm -rf --cached --ignore-unmatch {quoted}"
    proc = _run(
        [
            "git",
            "-C",
            str(repo),
            "filter-branch",
            "-f",
            "--index-filter",
            index_filter,
            "--prune-empty",
            "--tag-name-filter",
            "cat",
            "--",
            "--all",
        ],
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(detail)
    refs = _run(
        [
            "git",
            "-C",
            str(repo),
            "for-each-ref",
            "--format=%(refname)",
            "refs/original/",
        ],
        check=False,
    )
    for ref in refs.stdout.splitlines():
        ref = ref.strip()
        if ref:
            _run(["git", "-C", str(repo), "update-ref", "-d", ref], check=False)
    _run(
        ["git", "-C", str(repo), "reflog", "expire", "--expire=now", "--all"],
        check=False,
    )
    _run(["git", "-C", str(repo), "gc", "--prune=now"], check=False)
    remaining = scan_repo(repo, DEFAULT_EXACT, DEFAULT_GLOBS).paths_to_purge
    return {
        "bundle": str(bundle),
        "removed_paths": sorted(paths),
        "remaining_in_history": sorted(remaining),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Purge paths from full git history.")
    p.add_argument("--repo", type=Path, action="append", dest="repos")
    p.add_argument("--all-dotsound-public", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--i-understand-history-rewrite", action="store_true")
    p.add_argument("--allow-dirty", action="store_true")
    p.add_argument("--backups-dir", type=Path, default=None)
    p.add_argument("--report", type=Path, default=None)
    return p.parse_args(argv)


def resolve_repos(args: argparse.Namespace) -> list[Path]:
    if args.all_dotsound_public:
        return [
            BACKEND_ROOT,
            BACKEND_ROOT.parent / "DotSoundBot",
            BACKEND_ROOT.parent / "DotSoundComputeWorker",
        ]
    if args.repos:
        return [r.resolve() for r in args.repos]
    return [Path.cwd().resolve()]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.apply and not args.i_understand_history_rewrite:
        print("Need --i-understand-history-rewrite with --apply.", file=sys.stderr)
        return 2
    repos = resolve_repos(args)
    report: dict[str, object] = {
        "mode": "apply" if args.apply else "scan",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repos": [],
    }
    code = 0
    for repo in repos:
        if not _git_ok(repo):
            print(f"SKIP not a git repo: {repo}", file=sys.stderr)
            code = 2
            continue
        scan = scan_repo(repo, DEFAULT_EXACT, DEFAULT_GLOBS)
        print(f"\n=== {scan.repo.name} ===")
        print(f"paths to purge from history: {len(scan.paths_to_purge)}")
        for p in sorted(scan.paths_to_purge)[:30]:
            print(f"  - {p}")
        if len(scan.paths_to_purge) > 30:
            print(f"  ... +{len(scan.paths_to_purge) - 30} more")
        entry: dict[str, object] = {
            "path": str(scan.repo),
            "purge_count": len(scan.paths_to_purge),
            "purge_paths": sorted(scan.paths_to_purge),
        }
        if not args.apply:
            report["repos"].append(entry)
            continue
        if not scan.paths_to_purge:
            print("  nothing to purge")
            report["repos"].append(entry)
            continue
        if not args.allow_dirty and not _is_clean(repo):
            print(f"ABORT dirty tree: {repo}", file=sys.stderr)
            return 2
        backups = args.backups_dir or (repo / ".git-release-backups")
        print("  backup bundle + filter-branch ...")
        try:
            meta = apply_purge(repo, scan.paths_to_purge, backups)
        except RuntimeError as exc:
            print(f"ABORT {exc}", file=sys.stderr)
            return 3
        entry["applied"] = meta
        if meta.get("remaining_in_history"):
            code = 1
            print("  WARNING still in history:", meta["remaining_in_history"])
        else:
            print("  OK history clean for target paths")
        report["repos"].append(entry)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
