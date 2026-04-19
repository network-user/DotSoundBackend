"""Bootstrap the first administrator (or grant full set of caps).

Usage::

    poetry run python scripts/bootstrap_admin.py --email me@example.com
    poetry run python scripts/bootstrap_admin.py --telegram-id 123456
    poetry run python scripts/bootstrap_admin.py --user-id 1

    # Grant only a subset (default = all KNOWN_CAPABILITIES):
    poetry run python scripts/bootstrap_admin.py --email me@x.com \
        --capabilities users.manage,tracks.manage

    # Drop admin (revoke flag + all capabilities):
    poetry run python scripts/bootstrap_admin.py --email me@x.com --revoke

Inside Docker compose::

    docker compose exec backend \
        poetry run python scripts/bootstrap_admin.py --email me@x.com

Idempotent: re-running just makes sure ``is_admin`` is set and every
listed capability has a row in ``admin_capabilities``. Existing rows
are never duplicated thanks to ``ON CONFLICT DO NOTHING``.

After running this, open the admin panel and the user will see the
TOTP onboarding screen on first visit.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import delete, select  # noqa: E402

from app.core.db import (  # noqa: E402
    AsyncSessionLocal,
    dispose_engine,
)
from app.models.admin_capability import (  # noqa: E402
    AdminCapability,
)
from app.models.user import User  # noqa: E402
from app.services.admin_manifest_service import (  # noqa: E402
    KNOWN_CAPABILITIES,
)


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m"


def _yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m"


def _red(text: str) -> str:
    return f"\033[31m{text}\033[0m"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap or update an admin user "
            "in DotSound."
        ),
    )
    target = parser.add_mutually_exclusive_group(
        required=True,
    )
    target.add_argument(
        "--email",
        help="User email",
    )
    target.add_argument(
        "--telegram-id",
        type=int,
        help="Telegram numeric id",
    )
    target.add_argument(
        "--user-id",
        type=int,
        help="Internal users.id",
    )
    parser.add_argument(
        "--capabilities",
        default="",
        help=(
            "Comma-separated list of capabilities "
            "to grant. Default = all known."
        ),
    )
    parser.add_argument(
        "--revoke",
        action="store_true",
        help=(
            "Revoke admin role and all "
            "capabilities for the user."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Show what would change without "
            "writing to the database."
        ),
    )
    return parser.parse_args()


async def _find_user(
    session, *, email, telegram_id, user_id
):
    if user_id is not None:
        result = await session.execute(
            select(User).where(User.id == user_id),
        )
        return result.scalar_one_or_none()
    if telegram_id is not None:
        result = await session.execute(
            select(User).where(
                User.telegram_id == telegram_id,
            ),
        )
        return result.scalar_one_or_none()
    if email:
        result = await session.execute(
            select(User).where(
                User.email == email.lower().strip(),
            ),
        )
        return result.scalar_one_or_none()
    return None


def _resolve_capabilities(
    raw: str,
) -> list[str]:
    if not raw:
        return sorted(KNOWN_CAPABILITIES)
    requested = {
        item.strip()
        for item in raw.split(",")
        if item.strip()
    }
    unknown = requested - KNOWN_CAPABILITIES
    if unknown:
        print(
            _red(
                "Unknown capabilities: "
                + ", ".join(sorted(unknown)),
            ),
        )
        print(
            "Allowed: "
            + ", ".join(sorted(KNOWN_CAPABILITIES)),
        )
        sys.exit(2)
    return sorted(requested)


async def _run() -> int:
    args = _parse_args()
    requested_caps = _resolve_capabilities(
        args.capabilities,
    )

    try:
        return await _run_with_session(
            args, requested_caps,
        )
    finally:
        await dispose_engine()


async def _run_with_session(
    args, requested_caps,
):
    async with AsyncSessionLocal() as session:
        user = await _find_user(
            session,
            email=args.email,
            telegram_id=args.telegram_id,
            user_id=args.user_id,
        )
        if user is None:
            target = (
                args.email
                or args.telegram_id
                or args.user_id
            )
            print(
                _red(
                    f"User not found: {target}",
                ),
            )
            print(
                "Tip: the user must already exist "
                "(login at least once via Telegram "
                "or email magic-link).",
            )
            return 1

        print(
            _bold("Target user:"),
            f"id={user.id}",
            f"telegram_id={user.telegram_id}",
            f"email={user.email}",
            f"is_admin={user.is_admin}",
        )

        if args.revoke:
            return await _revoke(
                session, user, dry=args.dry_run,
            )
        return await _grant(
            session,
            user,
            capabilities=requested_caps,
            dry=args.dry_run,
        )


async def _grant(
    session, user, *, capabilities, dry
):
    existing_result = await session.execute(
        select(AdminCapability.capability).where(
            AdminCapability.user_id == user.id,
        ),
    )
    existing = {
        str(row)
        for row in existing_result.scalars().all()
    }
    to_add = [
        cap
        for cap in capabilities
        if cap not in existing
    ]

    will_flip_admin = not user.is_admin

    if dry:
        print(_bold("DRY-RUN — no DB writes."))
        if will_flip_admin:
            print(
                _yellow(
                    "  + would set is_admin=true"
                ),
            )
        else:
            print("  · is_admin already true")
        if to_add:
            for cap in to_add:
                print(
                    _yellow(
                        f"  + would grant {cap}"
                    ),
                )
        else:
            print(
                "  · all requested capabilities "
                "already granted",
            )
        return 0

    if will_flip_admin:
        user.is_admin = True
        print(_green("  ✓ set is_admin=true"))
    else:
        print("  · is_admin already true")

    if to_add:
        now = datetime.now(UTC)
        for cap in to_add:
            session.add(
                AdminCapability(
                    user_id=user.id,
                    capability=cap,
                    granted_by=user.id,
                    granted_at=now,
                ),
            )
            print(_green(f"  ✓ granted {cap}"))
    else:
        print(
            "  · all requested capabilities "
            "already granted",
        )

    await session.commit()
    print(
        _bold(
            "\nDone. The user can now open /admin "
            "and complete TOTP onboarding.",
        ),
    )
    return 0


async def _revoke(session, user, *, dry):
    existing_result = await session.execute(
        select(AdminCapability.capability).where(
            AdminCapability.user_id == user.id,
        ),
    )
    existing = sorted(
        {
            str(row)
            for row in existing_result.scalars().all()
        }
    )

    if dry:
        print(_bold("DRY-RUN — no DB writes."))
        if user.is_admin:
            print(
                _yellow(
                    "  - would set is_admin=false",
                ),
            )
        for cap in existing:
            print(
                _yellow(f"  - would revoke {cap}"),
            )
        if (
            not user.is_admin
            and not existing
        ):
            print("  · nothing to revoke")
        return 0

    if user.is_admin:
        user.is_admin = False
        print(_green("  ✓ set is_admin=false"))
    if existing:
        await session.execute(
            delete(AdminCapability).where(
                AdminCapability.user_id == user.id,
            ),
        )
        for cap in existing:
            print(_green(f"  ✓ revoked {cap}"))
    if (
        not user.is_admin
        and not existing
    ):
        print("  · nothing to revoke")
    await session.commit()
    return 0


def main() -> None:
    code = asyncio.run(_run())
    sys.exit(code)


if __name__ == "__main__":
    main()
