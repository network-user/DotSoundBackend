"""Standalone daemon that keeps SC_CLIENT_ID fresh in .env.

Scrapes the current SoundCloud client_id from public JS bundles
and writes it to the project .env file once a week.

Usage:
    # Запустить как демон (еженедельное обновление):
    poetry run python scripts/sc_id_refresher.py

    # Разовый запуск (тест / ручной триггер):
    poetry run python scripts/sc_id_refresher.py --now

    # С уровнем логирования DEBUG:
    poetry run python scripts/sc_id_refresher.py --now --log-level DEBUG

После обновления .env нужно перезапустить FastAPI-приложение,
чтобы pydantic-settings подхватил новое значение SC_CLIENT_ID.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

import httpx
import structlog

# Гарантируем, что корень проекта в sys.path при любом cwd
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from app.core.logging import configure_logging  # noqa: E402

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).parent.parent
ENV_FILE: Path = PROJECT_ROOT / ".env"
REFRESH_INTERVAL: int = 7 * 24 * 60 * 60  # 1 неделя в секундах

_SC_HOME = "https://soundcloud.com/"

# Ищем <script src="https://a-v2.sndcdn.com/assets/....js">
_RE_SCRIPT_URL = re.compile(
    r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"'
)
# Ищем client_id:"<value>" в JS-бандле
_RE_CLIENT_ID = re.compile(r'client_id:"([a-zA-Z0-9_-]+)"')

_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Парсинг SoundCloud
# ---------------------------------------------------------------------------


async def _fetch_script_urls(client: httpx.AsyncClient) -> list[str]:
    """GET soundcloud.com и вернуть список URL JS-бандлов."""
    response = await client.get(
        _SC_HOME, headers=_HEADERS, follow_redirects=True
    )
    response.raise_for_status()
    return _RE_SCRIPT_URL.findall(response.text)


async def _find_client_id_in_bundle(
    client: httpx.AsyncClient, url: str
) -> str | None:
    """Скачать один бандл и найти client_id, либо вернуть None."""
    try:
        response = await client.get(
            url, headers=_HEADERS, follow_redirects=True
        )
        response.raise_for_status()
    except httpx.HTTPStatusError:
        logger.warning("sc_bundle_fetch_failed", url=url)
        return None
    match = _RE_CLIENT_ID.search(response.text)
    return match.group(1) if match else None


async def scrape_client_id() -> str | None:
    """
    Полный цикл парсинга: главная страница → бандлы → client_id.
    Возвращает строку client_id или None при неудаче.
    """
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            script_urls = await _fetch_script_urls(client)
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            logger.error("sc_home_fetch_failed", error=str(exc))
            return None

        if not script_urls:
            logger.error("sc_no_script_urls_found")
            return None

        logger.info("sc_bundles_found", count=len(script_urls))

        for url in script_urls:
            client_id = await _find_client_id_in_bundle(client, url)
            if client_id:
                return client_id

    logger.error("sc_client_id_not_found_in_any_bundle")
    return None


# ---------------------------------------------------------------------------
# Обновление .env
# ---------------------------------------------------------------------------


def update_env_file(env_path: Path, key: str, value: str) -> bool:
    """
    Обновить KEY=VALUE в .env файле.
    Заменяет строку на месте если ключ найден, иначе дописывает в конец.
    Возвращает True если значение изменилось, False если уже актуально.
    """
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    new_line = f"{key}={value}"

    original = env_path.read_text(encoding="utf-8") if env_path.exists() else ""

    if pattern.search(original):
        current_match = pattern.search(original)
        assert current_match is not None  # pattern.search гарантирует это
        if current_match.group(0) == new_line:
            return False  # значение уже актуально
        updated = pattern.sub(new_line, original)
    else:
        # Дописываем в конец, обеспечивая перенос строки перед записью
        updated = original.rstrip("\r\n") + "\n" + new_line + "\n"

    env_path.write_text(updated, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Цикл обновления
# ---------------------------------------------------------------------------


async def refresh_once() -> bool:
    """
    Один цикл: спарсить → обновить .env.
    Возвращает True при успехе, False при неудаче.
    """
    logger.info("sc_refresh_starting")
    client_id = await scrape_client_id()

    if not client_id:
        logger.error("sc_refresh_failed_no_client_id")
        return False

    # Логируем только первые 8 символов
    partial = client_id[:8] + "..."
    changed = update_env_file(ENV_FILE, "SC_CLIENT_ID", client_id)

    if changed:
        logger.info(
            "sc_client_id_updated",
            partial_id=partial,
            env_file=str(ENV_FILE),
        )
        logger.warning(
            "sc_app_restart_required",
            message=(
                "Перезапустите FastAPI-приложение, "
                "чтобы подхватить новый SC_CLIENT_ID"
            ),
        )
    else:
        logger.info("sc_client_id_unchanged", partial_id=partial)

    return True


async def run_daemon() -> None:
    """Бесконечный цикл: обновляем раз в REFRESH_INTERVAL секунд."""
    logger.info(
        "sc_daemon_started",
        interval_days=REFRESH_INTERVAL // 86400,
    )
    while True:
        await refresh_once()
        logger.info(
            "sc_daemon_sleeping",
            next_refresh_in_days=REFRESH_INTERVAL // 86400,
        )
        await asyncio.sleep(REFRESH_INTERVAL)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Парсит SC_CLIENT_ID из SoundCloud и обновляет .env"
    )
    parser.add_argument(
        "--now",
        action="store_true",
        help="Запустить один раз и завершиться (без daemon-цикла)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Уровень логирования (по умолчанию: INFO)",
    )
    return parser.parse_args()


def main() -> None:
    """Точка входа."""
    args = _parse_args()
    configure_logging(args.log_level)

    if args.now:
        success = asyncio.run(refresh_once())
        sys.exit(0 if success else 1)
    else:
        asyncio.run(run_daemon())


if __name__ == "__main__":
    main()
