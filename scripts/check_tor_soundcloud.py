"""Per-circuit Tor health check for SoundCloud and friends.

Iterates over the SOCKS5 ports owned by the backend Tor pool (or
a manually specified range) and reports, per circuit:

 * exit IP + IsTor verdict (via ``https://check.torproject.org``)
 * SoundCloud API reachability  (HEAD ``https://api.soundcloud.com``)
 * SoundCloud website reachability (HEAD ``https://soundcloud.com``)

Optionally also probes Yandex Music (``--target yandex|all``) to
help debug the cascade used by external playlist scans.

Run inside the running ``backend`` container so it talks to the
same ``tor`` process that the live app uses::

    docker compose -f docker-compose.yml -f docker-compose.prod.yml \\
        exec backend poetry run python scripts/check_tor_soundcloud.py

Or locally if the backend is started directly. Exit code is 0 only
when every probed circuit succeeded against every selected target.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from typing import Iterable

import httpx

DEFAULT_TIMEOUT = 20.0
TOR_CHECK_URL = "https://check.torproject.org/api/ip"
SC_API_URL = "https://api.soundcloud.com"
SC_WEB_URL = "https://soundcloud.com/"
YANDEX_URL = "https://music.yandex.ru/"

TARGET_CHOICES = ("soundcloud", "tor", "yandex", "all")


@dataclass
class ProbeResult:
    label: str
    ok: bool
    detail: str
    elapsed_ms: int


@dataclass
class CircuitReport:
    port: int
    probes: list[ProbeResult]

    @property
    def all_ok(self) -> bool:
        return all(p.ok for p in self.probes)


def _parse_ports(spec: str) -> list[int]:
    out: list[int] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo_s, hi_s = chunk.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
            if hi < lo:
                raise ValueError(
                    f"Invalid port range '{chunk}': hi < lo"
                )
            out.extend(range(lo, hi + 1))
        else:
            out.append(int(chunk))
    if not out:
        raise ValueError(f"No ports parsed from '{spec}'")
    return out


def _default_ports_from_settings() -> list[int] | None:
    try:
        from app.config import settings
    except Exception:
        return None
    try:
        base = int(settings.tor_socks_base_port)
        size = int(settings.tor_pool_size)
    except Exception:
        return None
    if size <= 0:
        return None
    return list(range(base, base + size))


async def _probe_tor_identity(
    client: httpx.AsyncClient,
) -> ProbeResult:
    started = time.monotonic()
    try:
        r = await client.get(TOR_CHECK_URL)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        return ProbeResult(
            label="tor-exit",
            ok=False,
            detail=f"ERR {type(exc).__name__}: {str(exc)[:80]}",
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )
    is_tor = bool(data.get("IsTor"))
    ip = data.get("IP", "?")
    return ProbeResult(
        label="tor-exit",
        ok=is_tor,
        detail=f"IP={ip} IsTor={is_tor}",
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )


async def _probe_http(
    client: httpx.AsyncClient,
    url: str,
    label: str,
    *,
    method: str = "HEAD",
    follow_redirects: bool = True,
) -> ProbeResult:
    started = time.monotonic()
    try:
        r = await client.request(
            method,
            url,
            follow_redirects=follow_redirects,
        )
    except Exception as exc:
        return ProbeResult(
            label=label,
            ok=False,
            detail=f"ERR {type(exc).__name__}: {str(exc)[:80]}",
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return ProbeResult(
        label=label,
        ok=r.status_code < 500,
        detail=f"{method} {r.status_code}",
        elapsed_ms=elapsed_ms,
    )


async def _check_circuit(
    port: int,
    targets: set[str],
    timeout: float,
) -> CircuitReport:
    proxy = f"socks5://127.0.0.1:{port}"
    probes: list[ProbeResult] = []
    async with httpx.AsyncClient(
        proxy=proxy,
        timeout=timeout,
        trust_env=False,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        },
    ) as client:
        if "tor" in targets:
            probes.append(await _probe_tor_identity(client))
        if "soundcloud" in targets:
            probes.append(
                await _probe_http(
                    client, SC_API_URL, "sc-api"
                )
            )
            probes.append(
                await _probe_http(
                    client, SC_WEB_URL, "sc-web"
                )
            )
        if "yandex" in targets:
            probes.append(
                await _probe_http(
                    client, YANDEX_URL, "yandex"
                )
            )
    return CircuitReport(port=port, probes=probes)


def _format_probe(p: ProbeResult) -> str:
    mark = "OK " if p.ok else "FAIL"
    return f"{p.label}={mark}[{p.elapsed_ms}ms] {p.detail}"


def _print_report(
    reports: list[CircuitReport], ports: list[int]
) -> tuple[int, int]:
    print(
        f"\nProbed {len(ports)} circuits ({ports[0]}-{ports[-1]})\n"
    )

    ok_count = 0
    for r in reports:
        if r.all_ok:
            ok_count += 1
        prefix = "OK  " if r.all_ok else "FAIL"
        parts = "  ".join(_format_probe(p) for p in r.probes)
        print(f"  [{prefix}] port {r.port}: {parts}")

    print(
        f"\nResult: {ok_count}/{len(reports)} circuits "
        f"passed every probe."
    )
    return ok_count, len(reports)


def _expand_targets(raw: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for t in raw:
        if t == "all":
            out.update({"tor", "soundcloud", "yandex"})
        elif t in TARGET_CHOICES:
            out.add(t)
        else:
            raise ValueError(f"Unknown target: {t}")
    if "all" in out:
        out.discard("all")
        out.update({"tor", "soundcloud", "yandex"})
    return out or {"tor", "soundcloud"}


async def _amain(args: argparse.Namespace) -> int:
    if args.ports:
        ports = _parse_ports(args.ports)
    else:
        ports = _default_ports_from_settings()
        if ports is None:
            print(
                "Could not read tor_socks_base_port / tor_pool_size "
                "from app.config — pass --ports explicitly "
                "(e.g. --ports 9050-9059).",
                file=sys.stderr,
            )
            return 2

    targets = _expand_targets(args.target)
    print(
        f"Targets: {sorted(targets)}  timeout={args.timeout}s  "
        f"concurrency={args.concurrency}"
    )

    sem = asyncio.Semaphore(max(1, args.concurrency))

    async def _bounded(p: int) -> CircuitReport:
        async with sem:
            return await _check_circuit(p, targets, args.timeout)

    reports = await asyncio.gather(
        *(_bounded(p) for p in ports)
    )
    reports.sort(key=lambda r: r.port)
    ok, total = _print_report(reports, ports)
    return 0 if ok == total else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Verify per-circuit Tor health for SoundCloud "
            "(and friends)."
        ),
    )
    parser.add_argument(
        "--ports",
        type=str,
        default=None,
        help=(
            "Comma-separated ports / ranges, e.g. "
            "'9050-9059' or '9050,9051,9055'. "
            "Defaults to tor_socks_base_port..base+pool_size "
            "from app.config."
        ),
    )
    parser.add_argument(
        "--target",
        action="append",
        choices=TARGET_CHOICES,
        default=[],
        help=(
            "Which target(s) to probe per circuit. May be "
            "passed multiple times. Default: tor + soundcloud."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=(
            "Per-request timeout in seconds "
            f"(default {DEFAULT_TIMEOUT})."
        ),
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Max circuits probed in parallel (default 4).",
    )
    args = parser.parse_args()

    try:
        code = asyncio.run(_amain(args))
    except KeyboardInterrupt:
        code = 130
    sys.exit(code)


if __name__ == "__main__":
    main()
