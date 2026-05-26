"""Strip AI co-author trailers from git history (safe, with backup).

Detects and removes common Cursor / Claude attribution lines from commit
messages, then rewrites history via ``git filter-branch``. Default mode is
read-only scan; rewriting requires explicit flags.

Typical workflow (from any repo, scan all DotSound siblings):

    python scripts/strip_ai_coauthors.py --scan-all-dotsound

Apply to one repo (creates bundle backup first):

    python scripts/strip_ai_coauthors.py \\
        --repo C:/path/to/repo \\
        --apply \\
        --i-understand-history-rewrite

After apply you must force-push every rewritten remote branch and ask
collaborators to re-clone or reset. Keep the ``.bundle`` backup until remotes
are verified.

Exit codes: 0 ok, 1 commits still contain trailers after apply, 2 usage/safety
block, 3 git/tool failure.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DOTSOUND_REPOS = (
    BACKEND_ROOT,
    BACKEND_ROOT.parent / "DotSoundPrivateCore",
    BACKEND_ROOT.parent / "DotSoundBot",
    BACKEND_ROOT.parent / "DotSoundComputeWorker",
)

CLAUDE_COAUTHOR = re.compile(
    r"^Co-Authored-By:\s*Claude\b.*$",
    re.IGNORECASE,
)
CURSOR_COAUTHOR = re.compile(
    r"^Co-Authored-By:\s*Cursor\b.*$",
    re.IGNORECASE,
)
CURSOR_EMAIL_COAUTHOR = re.compile(
    r"^Co-Authored-By:.*cursoragent@cursor\.com\s*$",
    re.IGNORECASE,
)
ANTHROPIC_COAUTHOR = re.compile(
    r"^Co-Authored-By:.*@anthropic\.com\s*$",
    re.IGNORECASE,
)
MADE_WITH_CURSOR = re.compile(
    r"^Made-with:\s*Cursor\s*$",
    re.IGNORECASE,
)

TRAILER_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("claude_coauthor", CLAUDE_COAUTHOR),
    ("cursor_coauthor", CURSOR_COAUTHOR),
    ("cursor_email_coauthor", CURSOR_EMAIL_COAUTHOR),
    ("anthropic_coauthor", ANTHROPIC_COAUTHOR),
    ("made_with_cursor", MADE_WITH_CURSOR),
)


@dataclass
class CommitHit:
    sha: str
    categories: set[str] = field(default_factory=set)
    sample_lines: list[str] = field(default_factory=list)


@dataclass
class RepoScan:
    repo: Path
    total_commits: int = 0
    hits: dict[str, CommitHit] = field(default_factory=dict)
    line_counts: Counter[str] = field(default_factory=Counter)

    @property
    def affected_commits(self) -> int:
        return len(self.hits)


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
    if not (repo / ".git").exists():
        return False
    proc = _run(["git", "-C", str(repo), "rev-parse", "--git-dir"], check=False)
    return proc.returncode == 0


def _is_worktree_clean(repo: Path) -> bool:
    proc = _run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        check=False,
    )
    return proc.returncode == 0 and not proc.stdout.strip()


def _iter_commits(repo: Path) -> list[tuple[str, str]]:
    proc = _run(
        [
            "git",
            "-C",
            str(repo),
            "log",
            "--all",
            "--format=%H%x1e%B%x1e",
        ],
    )
    blocks = [b for b in proc.stdout.split("\x1e\n") if b.strip()]
    out: list[tuple[str, str]] = []
    for block in blocks:
        parts = block.split("\x1e", 1)
        if len(parts) != 2:
            continue
        sha, body = parts[0].strip(), parts[1]
        if not sha:
            continue
        out.append((sha, body))
    return out


def classify_message(body: str) -> tuple[set[str], list[str]]:
    categories: set[str] = set()
    samples: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for name, pattern in TRAILER_RULES:
            if pattern.match(stripped):
                categories.add(name)
                if len(samples) < 8:
                    samples.append(stripped)
    return categories, samples


def strip_trailers(body: str) -> tuple[str, set[str]]:
    removed: set[str] = set()
    kept: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        matched = False
        for name, pattern in TRAILER_RULES:
            if pattern.match(stripped):
                removed.add(name)
                matched = True
                break
        if not matched:
            kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    new_body = "\n".join(kept)
    if body.endswith("\n") and new_body:
        new_body += "\n"
    return new_body, removed


def scan_repo(repo: Path) -> RepoScan:
    result = RepoScan(repo=repo.resolve())
    commits = _iter_commits(repo)
    result.total_commits = len(commits)
    for sha, body in commits:
        categories, samples = classify_message(body)
        if not categories:
            continue
        hit = CommitHit(sha=sha, categories=categories, sample_lines=samples)
        result.hits[sha] = hit
        for line in body.splitlines():
            stripped = line.strip()
            for name, pattern in TRAILER_RULES:
                if pattern.match(stripped):
                    result.line_counts[name] += 1
                    break
    return result


def _backup_bundle(repo: Path, backups_dir: Path) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_name = repo.name.replace(" ", "_")
    bundle_path = backups_dir / f"{safe_name}-pre-strip-coauthors-{stamp}.bundle"
    _run(
        [
            "git",
            "-C",
            str(repo),
            "bundle",
            "create",
            str(bundle_path),
            "--all",
        ],
    )
    return bundle_path


def _backup_branch(repo: Path) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"backup/pre-strip-coauthors-{stamp}"
    _run(["git", "-C", str(repo), "branch", name])
    return name


def _msg_filter_path() -> Path:
    helper = Path(__file__).with_name("_strip_ai_coauthors_msg_filter.py")
    if not helper.is_file():
        msg = f"Missing helper: {helper}"
        raise FileNotFoundError(msg)
    return helper


def apply_rewrite(repo: Path, backups_dir: Path) -> dict[str, object]:
    bundle = _backup_bundle(repo, backups_dir)
    branch = _backup_branch(repo)
    helper = _msg_filter_path()
    python = sys.executable
    filter_cmd = f'"{python}" "{helper}"'
    proc = _run(
        [
            "git",
            "-C",
            str(repo),
            "filter-branch",
            "-f",
            "--msg-filter",
            filter_cmd,
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
    return {
        "bundle": str(bundle),
        "backup_branch": branch,
    }


def verify_clean(repo: Path) -> list[CommitHit]:
    remaining: list[CommitHit] = []
    for sha, body in _iter_commits(repo):
        categories, samples = classify_message(body)
        if categories:
            remaining.append(
                CommitHit(sha=sha, categories=categories, sample_lines=samples)
            )
    return remaining


def _print_scan(scan: RepoScan) -> None:
    print(f"\n=== {scan.repo} ===")
    print(f"  commits total:     {scan.total_commits}")
    print(f"  commits affected:  {scan.affected_commits}")
    if not scan.line_counts:
        print("  (no AI co-author trailers found)")
        return
    print("  trailer lines by kind:")
    for kind, count in scan.line_counts.most_common():
        print(f"    {kind}: {count}")
    sample = list(scan.hits.values())[:3]
    for hit in sample:
        print(f"  example {hit.sha[:12]}:")
        for line in hit.sample_lines[:3]:
            print(f"    - {line}")


def _write_report(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan or strip Cursor/Claude co-author trailers from git history.",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        action="append",
        dest="repos",
        help="Repository path (repeatable). Default: current repo only.",
    )
    parser.add_argument(
        "--scan-all-dotsound",
        action="store_true",
        help="Scan Backend, PrivateCore, Bot, and ComputeWorker sibling repos.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Rewrite history (implies backup). Default is scan-only.",
    )
    parser.add_argument(
        "--i-understand-history-rewrite",
        action="store_true",
        help="Required with --apply: confirms you accept force-push / collaborator reset.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow non-clean working tree (not recommended).",
    )
    parser.add_argument(
        "--backups-dir",
        type=Path,
        default=None,
        help="Directory for .bundle backups (default: <repo>/.git-coauthor-backups).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write JSON report to this path.",
    )
    return parser.parse_args(argv)


def resolve_repos(args: argparse.Namespace) -> list[Path]:
    if args.scan_all_dotsound:
        return list(DEFAULT_DOTSOUND_REPOS)
    if args.repos:
        return [p.resolve() for p in args.repos]
    return [Path.cwd().resolve()]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repos = resolve_repos(args)

    if args.apply and not args.i_understand_history_rewrite:
        print(
            "Refusing --apply without --i-understand-history-rewrite.",
            file=sys.stderr,
        )
        return 2

    report: dict[str, object] = {
        "mode": "apply" if args.apply else "scan",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "repos": [],
    }

    exit_code = 0
    for repo in repos:
        if not repo.is_dir() or not _git_ok(repo):
            print(f"SKIP (not a git repo): {repo}", file=sys.stderr)
            exit_code = 2
            continue

        scan = scan_repo(repo)
        _print_scan(scan)
        repo_entry: dict[str, object] = {
            "path": str(scan.repo),
            "total_commits": scan.total_commits,
            "affected_commits": scan.affected_commits,
            "line_counts": dict(scan.line_counts),
            "sample_shas": list(scan.hits.keys())[:20],
        }

        if not args.apply:
            report["repos"].append(repo_entry)
            continue

        if scan.affected_commits == 0:
            print(f"  Nothing to rewrite in {repo.name}.")
            repo_entry["applied"] = False
            report["repos"].append(repo_entry)
            continue

        if not args.allow_dirty and not _is_worktree_clean(repo):
            print(
                f"ABORT: working tree not clean in {repo}. "
                "Commit/stash or pass --allow-dirty.",
                file=sys.stderr,
            )
            return 2

        backups_dir = args.backups_dir or (repo / ".git-coauthor-backups")
        print(f"\n  Creating backup bundle under {backups_dir} ...")
        try:
            backup_meta = apply_rewrite(repo, backups_dir)
        except (RuntimeError, FileNotFoundError) as exc:
            print(f"ABORT: {exc}", file=sys.stderr)
            return 3

        remaining = verify_clean(repo)
        repo_entry["applied"] = True
        repo_entry["backup"] = backup_meta
        repo_entry["remaining_affected"] = len(remaining)
        if remaining:
            exit_code = 1
            repo_entry["remaining_sample"] = [
                {"sha": h.sha, "categories": sorted(h.categories)}
                for h in remaining[:10]
            ]
            print(
                f"  WARNING: {len(remaining)} commits still have trailers "
                f"after rewrite.",
                file=sys.stderr,
            )
        else:
            print("  Rewrite OK; no AI trailers left in history.")
            print(
                "  Next: force-push branches you need, then delete old remote "
                "refs. Restore from .bundle if anything looks wrong:",
            )
            print(f"    git clone {backup_meta['bundle']} restored-repo")

        report["repos"].append(repo_entry)

    if args.report:
        _write_report(args.report.resolve(), report)
        print(f"\nReport written: {args.report.resolve()}")
    elif args.apply:
        default_report = (
            BACKEND_ROOT
            / ".git-coauthor-backups"
            / f"strip-report-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        _write_report(default_report, report)
        print(f"\nReport written: {default_report}")

    if not args.apply and any(
        r.get("affected_commits", 0) for r in report["repos"]  # type: ignore[union-attr]
    ):
        print(
            "\nScan complete. To rewrite, re-run with --apply "
            "--i-understand-history-rewrite."
        )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
