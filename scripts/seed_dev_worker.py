"""Seed a local dev compute worker so `make dev-full` works
end-to-end without manually clicking through the admin UI.

Idempotent: if a worker named ``local-dev`` already exists with
the gpu_full profile, the script reuses it and rotates its
secret so the freshly printed value is the one to paste into
``../DotSoundComputeWorker/.env``.

Output is shown ONCE — same UX as the admin "create worker" flow.

Usage::

    poetry run python scripts/seed_dev_worker.py
    poetry run python scripts/seed_dev_worker.py --name remote-gpu

The script intentionally sets ``allowed_ip_cidrs`` to the dev
defaults (loopback + RFC1918) so the worker can reach the
Backend from a container or the host machine. In prod you should
configure the allowlist through the admin UI instead.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.db import (  # noqa: E402
    AsyncSessionLocal,
    dispose_engine,
)
from app.models.compute_worker import (  # noqa: E402
    ComputeWorker,
)
from app.services import (  # noqa: E402
    compute_worker_service as cws,
)

DEV_ALLOWLIST: list[str] = [
    "127.0.0.1/32",
    "::1/128",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
]


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m"


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def _yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed or rotate the local dev compute worker."
        ),
    )
    parser.add_argument(
        "--name", default="local-dev"
    )
    parser.add_argument(
        "--profile",
        default="gpu_full",
        choices=("gpu_full", "cpu_light"),
    )
    parser.add_argument(
        "--max-concurrent-jobs",
        type=int,
        default=1,
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    async with AsyncSessionLocal() as session:
        existing = (
            await session.execute(
                select(ComputeWorker).where(
                    ComputeWorker.name == args.name,
                    ComputeWorker.profile == args.profile,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            worker, secret = await cws.register_worker(
                session,
                name=args.name,
                profile=args.profile,
                allowed_ip_cidrs=DEV_ALLOWLIST,
                allowed_profiles=[args.profile],
                max_concurrent_jobs=(
                    args.max_concurrent_jobs
                ),
            )
            await session.commit()
            print(
                _green(
                    "Created new compute worker."
                )
            )
        else:
            secret = secrets.token_urlsafe(36)
            existing.token_hash = cws._hash_token(secret)
            existing.active = True
            existing.suspended_reason = None
            existing.suspended_until = None
            existing.revoked_at = None
            existing.allowed_ip_cidrs = DEV_ALLOWLIST
            existing.allowed_profiles = [args.profile]
            existing.max_concurrent_jobs = (
                args.max_concurrent_jobs
            )
            await session.commit()
            await cws.invalidate_worker_nonces(
                existing.id
            )
            worker = existing
            print(
                _yellow(
                    "Re-used existing compute worker; "
                    "rotated secret."
                )
            )

    print()
    print(_bold("Copy these into DotSoundComputeWorker/.env:"))
    print()
    print(f"WORKER_ID={worker.id}")
    print(f"WORKER_SECRET={secret}")
    print(
        "WORKER_BACKEND_BASE_URL="
        "http://localhost:8000"
    )
    print()
    print(
        _yellow(
            "These values are shown ONCE. Save them now."
        )
    )
    return 0


def main() -> None:
    args = _parse_args()
    try:
        rc = asyncio.run(_run(args))
    finally:
        try:
            asyncio.run(dispose_engine())
        except RuntimeError:
            pass
    sys.exit(rc)


if __name__ == "__main__":
    main()
