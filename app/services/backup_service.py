"""Backup management service.

Wraps the shell-based backup pipeline (``scripts/backup.sh``) with
an async-friendly inventory + run trigger API. The actual backup
work runs through Taskiq so the admin endpoint returns immediately.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
from datetime import UTC, datetime
from typing import Any

import structlog

from app.config import settings
from app.core.tkq import broker

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

BACKUPS_ROOT = pathlib.Path("/backups")
LOCAL_FALLBACK_ROOT = pathlib.Path("./backups")
ALLOWED_KINDS: frozenset[str] = frozenset({"full", "pg", "redis", "minio"})


def _root() -> pathlib.Path:
    if BACKUPS_ROOT.exists():
        return BACKUPS_ROOT
    return LOCAL_FALLBACK_ROOT


def _format_size(num: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num)
    idx = 0
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    return f"{size:.1f} {units[idx]}"


def _scan_dir(
    path: pathlib.Path,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not path.exists() or not path.is_dir():
        return items
    for entry in sorted(
        path.iterdir(),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            stat = entry.stat()
        except OSError:
            continue
        if entry.is_dir():
            total = sum(
                f.stat().st_size for f in entry.rglob("*") if f.is_file()
            )
            items.append(
                {
                    "name": entry.name,
                    "kind": "dir",
                    "size_bytes": total,
                    "size_human": _format_size(total),
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=UTC
                    ).isoformat(),
                }
            )
        else:
            items.append(
                {
                    "name": entry.name,
                    "kind": "file",
                    "size_bytes": stat.st_size,
                    "size_human": _format_size(stat.st_size),
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=UTC
                    ).isoformat(),
                }
            )
    return items


async def list_backups() -> dict[str, Any]:
    root = _root()
    daily = await asyncio.to_thread(_scan_dir, root / "daily")
    weekly = await asyncio.to_thread(_scan_dir, root / "weekly")
    monthly = await asyncio.to_thread(_scan_dir, root / "monthly")
    return {
        "root": str(root),
        "remote_host": settings.bot_internal_url and "" or "",
        "remote_configured": bool(os.environ.get("BACKUP_REMOTE_HOST")),
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "scanned_at": datetime.now(UTC).isoformat(),
    }


@broker.task(task_name="admin.backup.run")
async def run_backup_task(
    kind: str = "full",
) -> dict[str, Any]:
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"unknown backup kind: {kind!r}")
    cmd = ["/scripts/backup.sh", kind]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await proc.communicate()
    code = proc.returncode or 0
    logger.info(
        "admin_backup_finished",
        kind=kind,
        exit_code=code,
    )
    return {
        "kind": kind,
        "exit_code": code,
        "stdout": stdout_bytes.decode("utf-8", errors="replace")[-2000:],
        "stderr": stderr_bytes.decode("utf-8", errors="replace")[-2000:],
    }


async def enqueue_backup(*, kind: str) -> dict[str, Any]:
    if kind not in ALLOWED_KINDS:
        raise ValueError(f"unknown backup kind: {kind!r}")
    try:
        sent = await run_backup_task.kiq(kind)
    except Exception as exc:
        logger.exception(
            "admin_backup_enqueue_failed",
            kind=kind,
        )
        raise RuntimeError(str(exc)) from exc
    task_id = getattr(sent, "task_id", None) or getattr(sent, "id", None)
    return {"task_id": task_id, "kind": kind}
