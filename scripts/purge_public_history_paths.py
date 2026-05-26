"""Remove build/probe artifacts from entire git history (safe, with backup).

Default: scan only. Rewrite requires --apply and --i-understand-history-rewrite.

Example (DotSound siblings):
    python scripts/purge_public_history_paths.py --scan-all-dotsound
    python scripts/purge_public_history_paths.py --repo ../DotSoundBot --apply \\
        --i-understand-history-rewrite
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

BACKEND_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_REPOS: tuple[tuple[str, Path], ...] = (
    ("DotSoundBackend", BACKEND_ROOT),
    ("DotSoundPrivateCore", BACKEND_ROOT.parent / "DotSoundPrivateCore"),
    ("DotSoundBot", BACKEND_ROOT.parent / "DotSoundBot"),
    ("DotSoundComputeWorker", BACKEND_ROOT.parent / "DotSoundComputeWorker"),
)

REPO_RULES: dict[str, dict[str, list[str]]] = {
    "DotSoundBackend": {
        "prefixes": ["scripts/_tmp_"],
        "exact": [],
    },
    "DotSoundBot": {
        "prefixes": [],
        "exact": [".coverage", "coverage.json"],
    },
    "DotSoundComputeWorker": {
        "prefixes": [],
        "exact": ["coverage.json"],
    },
    "DotSoundPrivateCore": {
        "prefixes": [],
        "exact": [],
    },
}


@dataclass
class RepoScan:
    name: str
    repo: Path
    all_paths_in_history: set[str] = field(default_factory=set)
    matched_paths: set[str] = field(default_factory=set)
    commits_touching: Counter[str] = field(default_factory=Counter)

    @property
    def match_count(self) -> int:
        return len(self.matched_paths)


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


def _is_worktree_clean(repo: Path) -> bool:
    proc = _run(["git", "-C", str(repo), "status", "--porcelain"], check=False)
    return proc.returncode == 0 and not proc.stdout.strip()


def _rules_for(name: str) -> tuple[list[str], list[str]]:
    rules = REPO_RULES.get(name, {"prefixes": [], "exact": []})
    return list(rules.get("prefixes", [])), list(rules.get("exact", []))


def _path_matches(
    path: str,
    prefixes: list[str],
    exact: list[str],
) -> bool:
    norm = PurePosixPath(path.replace("\\", "/")).as_posix()
    if norm in exact:
        return True
    return any(norm.startswith(p) for p in prefixes)


def _collect_history_paths(repo: Path) -> set[str]:
    proc = _run(
        [
            "git",
            "-C",
            str(repo),
            "log",
            "--all",
            "--pretty=format:",
            "--name-only",
        ],
    )
    out: set[str] = set()
    for line in proc.stdout.splitlines():
        p = line.strip()
        if p:
            out.add(p.replace("\\", "/"))
    return out


def _commits_touching(repo: Path, paths: set[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not paths:
        return counts
    for path in sorted(paths):
        proc = _run(
            [
                "git",
                "-C",
                str(repo),
                "log",
                "--all",
                "--format=%H",
                "--",
                path,
            ],
            check=False,
        )
        for sha in proc.stdout.splitlines():
            sha = sha.strip()
            if sha:
                counts[sha] += 1
    return counts


def scan_repo(name: str, repo: Path) -> RepoScan:
    prefixes, exact = _rules_for(name)
    result = RepoScan(name=name, repo=repo.resolve())
    result.all_paths_in_history = _collect_history_paths(repo)
    result.matched_paths = {
        p
        for p in result.all_paths_in_history
        if _path_matches(p, prefixes, exact)
    }
    result.commits_touching = _commits_touching(repo, result.matched_paths)
    return result


def _backup_bundle(repo: Path, backups_dir: Path) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle = backups_dir / f"{repo.name}-pre-purge-paths-{stamp}.bundle"
    _run(
        ["git", "-C", str(repo), "bundle", "create", str(bundle), "--all"],
    )
    return bundle


def _backup_branch(repo: Path) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"backup/pre-purge-paths-{stamp}"
    _run(["git", "-C", str(repo), "branch", name])
    return name


def apply_purge(repo: Path, paths: list[str], backups_dir: Path) -> dict[str, str]:
    if not paths:
        return {"status": "nothing_to_purge"}
    bundle = _backup_bundle(repo, backups_dir)
    branch = _backup_branch(repo)
    paths_slash = [p.replace("\\", "/") for p in paths]
    rm_args = ["git", "rm", "-rf", "--cached", "--ignore-unmatch", *paths_slash]
    filter_cmd = (
        subprocess.list2cmdline(rm_args)
        if sys.platform == "win32"
        else " ".join(rm_args)
    )
    proc = _run(
        [
            "git",
            "-C",
            str(repo),
            "filter-branch",
            "-f",
            "--index-filter",
            filter_cmd,
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
        raise RuntimeError(f"git filter-branch failed: {detail}")
    cleanup = _run(
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
    for ref in cleanup.stdout.splitlines():
        ref = ref.strip()
        if ref:
            _run(["git", "-C", str(repo), "update-ref", "-d", ref], check=False)
    _run(
        ["git", "-C", str(repo), "reflog", "expire", "--expire=now", "--all"],
        check=False,
    )
    _run(["git", "-C", str(repo), "gc", "--prune=now"], check=False)
    return {"bundle": str(bundle), "backup_branch": branch}


def _print_scan(scan: RepoScan) -> None:
    prefixes, exact = _rules_for(scan.name)
    print(f"\n=== {scan.name} ({scan.repo}) ===")
    print(f"  rules: exact={exact or '-'} prefixes={prefixes or '-'}")
    print(f"  paths matched in history: {scan.match_count}")
    if not scan.matched_paths:
        print("  (nothing to purge)")
        return
    for p in sorted(scan.matched_paths)[:25]:
        print(f"    - {p}")
    if scan.match_count > 25:
        print(f"    ... +{scan.match_count - 25} more")
    print(f"  commits touching matched paths: {len(scan.commits_touching)}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Purge probe/coverage paths from full git history.",
    )
    parser.add_argument("--repo", type=Path, action="append", dest="repos")
    parser.add_argument(
        "--scan-all-dotsound",
        action="store_true",
        help="Scan Backend, Bot, ComputeWorker (not PrivateCore).",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--i-understand-history-rewrite", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--backups-dir", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    return parser.parse_args(argv)


def resolve_targets(args: argparse.Namespace) -> list[tuple[str, Path]]:
    if args.scan_all_dotsound:
        return [
            (n, p)
            for n, p in DEFAULT_REPOS
            if n != "DotSoundPrivateCore" and p.is_dir()
        ]
    if args.repos:
        return [(p.resolve().name, p.resolve()) for p in args.repos]
    cwd = Path.cwd().resolve()
    return [(cwd.name, cwd)]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.apply and not args.i_understand_history_rewrite:
        print(
            "Refusing --apply without --i-understand-history-rewrite.",
            file=sys.stderr,
        )
        return 2

    targets = resolve_targets(args)
    report: dict[str, object] = {
        "mode": "apply" if args.apply else "scan",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repos": [],
    }
    exit_code = 0

    for name, repo in targets:
        if not _git_ok(repo):
            print(f"SKIP (not git): {repo}", file=sys.stderr)
            exit_code = 2
            continue
        scan = scan_repo(name, repo)
        _print_scan(scan)
        entry: dict[str, object] = {
            "name": name,
            "path": str(scan.repo),
            "matched_paths": sorted(scan.matched_paths),
            "commits_touching": len(scan.commits_touching),
        }

        if not args.apply:
            report["repos"].append(entry)
            continue

        if not scan.matched_paths:
            entry["applied"] = False
            report["repos"].append(entry)
            continue

        if not args.allow_dirty and not _is_worktree_clean(repo):
            print(
                f"ABORT: dirty tree in {name}. Commit/stash or --allow-dirty.",
                file=sys.stderr,
            )
            return 2

        backups_dir = args.backups_dir or (repo / ".git-history-backups")
        try:
            meta = apply_purge(
                repo,
                sorted(scan.matched_paths),
                backups_dir,
            )
        except RuntimeError as exc:
            print(f"ABORT {name}: {exc}", file=sys.stderr)
            return 3

        verify = scan_repo(name, repo)
        entry["applied"] = True
        entry["backup"] = meta
        entry["remaining_paths"] = sorted(verify.matched_paths)
        if verify.matched_paths:
            exit_code = 1
            print(
                f"  WARNING: {len(verify.matched_paths)} paths still in history",
                file=sys.stderr,
            )
        else:
            print(f"  Purge OK for {name}.")
        report["repos"].append(entry)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    elif args.apply:
        out = BACKEND_ROOT / ".git-history-backups" / (
            f"purge-report-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nReport: {out}")

    if not args.apply and any(
        r.get("matched_paths") for r in report["repos"]  # type: ignore[union-attr]
    ):
        print(
            "\nScan done. Re-run with --apply --i-understand-history-rewrite per repo."
        )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
