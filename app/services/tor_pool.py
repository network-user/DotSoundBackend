from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_tor_pool: TorPool | None = None

_STEM_TOR_LOG_LINES = [
    "notice stdout",
    "warn stderr",
]


class TorPoolSettings(Protocol):
    tor_pool_enabled: bool
    tor_pool_fail_closed: bool
    tor_socks_base_port: int
    tor_pool_size: int
    tor_control_port: int
    tor_circuit_max_age_seconds: int
    tor_bin_path: str
    tor_control_password: str
    tor_log_outbound_public_ip: bool
    tor_circuit_max_failure_rate: float
    tor_circuit_health_check_interval: int


async def _log_outbound_public_ip() -> None:
    url = "https://api.ipify.org"
    try:
        async with httpx.AsyncClient(
            timeout=5.0,
            trust_env=False,
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
            text = (r.text or "").strip()
    except Exception as exc:
        logger.warning(
            "tor_outbound_public_ip_failed",
            error=str(exc)[:200],
        )
        return
    if not text:
        logger.warning("tor_outbound_public_ip_empty")
        return
    logger.info(
        "tor_outbound_public_ip",
        public_ip=text,
        check="direct_https",
        note=(
            "Not the Tor exit IP. Same default route as tor.exe to entry "
            "guards if the VPN is not split-tunnel."
        ),
    )


def _tor_bootstrap_line(line: str) -> None:
    t = (line or "").strip()
    if not t:
        return
    if "Bootstrapped" in t:
        logger.info("tor_bootstrap", line=t[:500])
        return
    if "[warn]" in t or "[err]" in t:
        logger.warning("tor_bootstrap", line=t[:500])
        return
    logger.debug("tor_bootstrap", line=t[:500])


def get_tor_pool() -> TorPool | None:
    return _tor_pool


def _set_tor_pool(pool: TorPool | None) -> None:
    global _tor_pool
    _tor_pool = pool


async def start_tor_pool_from_settings(
    settings: TorPoolSettings,
    *,
    component: str,
) -> bool:
    if not getattr(settings, "tor_pool_enabled", False):
        return False
    pool = TorPool(settings)
    try:
        await pool.start()
    except Exception as exc:
        logger.error(
            "tor_pool_start_failed",
            component=component,
            error=str(exc),
            hint="Install Tor (apt) or Tor Browser/Expert (Windows).",
        )
        if getattr(settings, "tor_pool_fail_closed", True):
            raise
        return False
    _set_tor_pool(pool)
    return True


async def stop_tor_pool_from_settings(*, component: str) -> None:
    pool = get_tor_pool()
    if pool is None:
        return
    await pool.stop()
    _set_tor_pool(None)
    logger.info("tor_pool_cleared", component=component)


def _tbb_nest_parts(executable: str) -> tuple[str, ...]:
    return (
        "Tor Browser",
        "Browser",
        "TorBrowser",
        "Tor",
        executable,
    )


def _resolve_tor_control_port(
    base: int, pool_size: int, requested: int
) -> int:
    """Socks use ``[base, base+pool_size)``; control must be outside
    (same failure as: ``Failed to bind one of the listener ports`` if it
    overlaps a SocksPort). Default 9051 collides when pool is >1.
    """
    lo = base
    hi = base + max(pool_size, 0)
    if not (lo <= requested < hi):
        return requested
    return hi


def _dedupe_path_order(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _windows_program_files_tor_paths() -> list[Path]:
    out: list[Path] = []
    tbb = _tbb_nest_parts("tor.exe")
    for env_key in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(env_key)
        if not base:
            continue
        b = Path(base)
        out.append(b / "Tor" / "tor" / "tor.exe")
        out.append(b.joinpath(*tbb))
    return out


def _user_folder_tor_bundles(executable: str) -> list[Path]:
    home = Path.home()
    tbb = _tbb_nest_parts(executable)
    paths: list[Path] = []
    for base in (
        home / "Desktop",
        home / "Downloads",
        home / "OneDrive" / "Desktop",
    ):
        paths.append(base.joinpath(*tbb))
    return paths


def _search_tor_bundles() -> list[Path]:
    if os.name == "nt":
        w = _windows_program_files_tor_paths() + _user_folder_tor_bundles(
            "tor.exe"
        )
        return _dedupe_path_order(w)
    u = _user_folder_tor_bundles("tor")
    return _dedupe_path_order(u)


def resolve_tor_executable(
    tor_bin_path: str,
) -> str:
    """Path to the Tor binary; falls back to ``tor[.exe]`` name."""
    raw = (tor_bin_path or "").strip()
    if raw:
        p = Path(os.path.expanduser(os.path.expandvars(raw)))
        if p.is_file():
            return str(p.resolve())
        if p.is_dir():
            ex = p / "tor.exe" if os.name == "nt" else p / "tor"
            if ex.is_file():
                return str(ex.resolve())
        return str(p)

    suffix = "tor.exe" if os.name == "nt" else "tor"
    w = shutil.which("tor.exe" if os.name == "nt" else "tor")
    if w:
        return w
    for cand in _search_tor_bundles():
        if cand.is_file():
            logger.info(
                "tor_executable_resolved",
                path=str(cand.resolve()),
            )
            return str(cand.resolve())
    logger.info(
        "tor_executable_not_in_path",
        expected=suffix,
        hint="set TOR_BIN_PATH or add tor to PATH; or put TBB on Desktop",
    )
    return suffix


@dataclass
class TorCircuit:
    index: int
    socks_port: int
    ok_count: int = 0
    fail_count: int = 0
    last_renewed: float = field(default_factory=time.time)

    @property
    def failure_rate(self) -> float:
        total = self.ok_count + self.fail_count
        return self.fail_count / total if total > 0 else 0.0

    @property
    def proxy_url(self) -> str:
        return f"socks5://127.0.0.1:{self.socks_port}"


class TorPool:
    def __init__(self, settings: TorPoolSettings) -> None:
        self._settings = settings
        self._circuits: list[TorCircuit] = []
        self._rr_index: int = 0
        self._process: Any = None
        self._controller: Any = None
        self._health_task: asyncio.Task[None] | None = None
        self._renewal_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        import stem.control  # type: ignore[import-untyped]
        import stem.process  # type: ignore[import-untyped]

        s = self._settings
        base_port: int = s.tor_socks_base_port
        pool_size: int = s.tor_pool_size
        requested = int(s.tor_control_port)
        control_port = _resolve_tor_control_port(
            base_port, pool_size, requested
        )
        if control_port != requested:
            logger.warning(
                "tor_control_port_moved",
                from_port=requested,
                to_port=control_port,
                reason="Control port cannot overlap SOCKS range",
            )

        self._circuits = [
            TorCircuit(index=i, socks_port=base_port + i)
            for i in range(pool_size)
        ]

        config: dict[str, str | list[str]] = {
            "SocksPort": [str(base_port + i) for i in range(pool_size)],
            "ControlPort": str(control_port),
            "CookieAuthentication": "1",
            "MaxCircuitDirtiness": str(s.tor_circuit_max_age_seconds),
            "NewCircuitPeriod": "30",
            "Log": _STEM_TOR_LOG_LINES,
        }

        tor_cmd: str = resolve_tor_executable(s.tor_bin_path)

        logger.info(
            "tor_pool_starting",
            pool_size=pool_size,
            base_port=base_port,
            tor_cmd=tor_cmd,
        )
        logger.info(
            "tor_bootstrap_awaiting",
            completion_target_percent=80.0,
            note=(
                "stem parses Bootstrapped% lines from Tor stdout only. "
                "On Windows, stem does not apply launch timeouts; "
                "this step runs in a worker thread, so the timeout "
                "is also not applied on Unix."
            ),
        )

        try:
            self._process = await asyncio.to_thread(
                stem.process.launch_tor_with_config,
                config=config,
                tor_cmd=tor_cmd,
                timeout=90,
                take_ownership=True,
                completion_percent=80.0,
                init_msg_handler=_tor_bootstrap_line,
            )
        except Exception as exc:
            logger.error("tor_pool_launch_failed", error=str(exc))
            raise RuntimeError(f"Failed to launch Tor: {exc}") from exc

        try:
            self._controller = stem.control.Controller.from_port(
                port=control_port
            )
            password: str = s.tor_control_password
            if password:
                self._controller.authenticate(password=password)
            else:
                self._controller.authenticate()
            logger.info(
                "tor_pool_started",
                pool_size=pool_size,
                base_port=base_port,
                control_port=control_port,
            )
        except Exception as exc:
            logger.error(
                "tor_controller_connect_failed",
                error=str(exc),
            )
            self._controller = None

        if s.tor_log_outbound_public_ip:
            await _log_outbound_public_ip()

        self._health_task = asyncio.create_task(
            self._health_check_loop(), name="tor_health_check"
        )
        self._renewal_task = asyncio.create_task(
            self._renewal_loop(), name="tor_renewal"
        )

    async def stop(self) -> None:
        for task in (self._health_task, self._renewal_task):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        if self._controller is not None:
            with contextlib.suppress(Exception):
                self._controller.close()
            self._controller = None

        if self._process is not None:
            with contextlib.suppress(Exception):
                self._process.kill()
            self._process = None

        logger.info("tor_pool_stopped")

    def get_proxy(self, service: str = "") -> str:
        """Round-robin on healthy circuits; if all are degraded, use all."""
        max_fail: float = self._settings.tor_circuit_max_failure_rate
        healthy = [c for c in self._circuits if c.failure_rate < max_fail]
        pool = healthy or self._circuits
        if not pool:
            raise RuntimeError("TorPool: no circuits available")
        circuit = pool[self._rr_index % len(pool)]
        self._rr_index = (self._rr_index + 1) % max(len(pool), 1)
        logger.info(
            "tor_pool_proxy_selected",
            circuit=circuit.index,
            port=circuit.socks_port,
            service=service,
            failure_rate=round(circuit.failure_rate, 2),
        )
        return circuit.proxy_url

    def report_proxy_result(self, proxy_url: str, *, ok: bool) -> None:
        for circuit in self._circuits:
            if circuit.proxy_url != proxy_url:
                continue
            if ok:
                circuit.ok_count += 1
            else:
                circuit.fail_count += 1
            logger.info(
                "tor_pool_proxy_result_recorded",
                circuit=circuit.index,
                port=circuit.socks_port,
                ok=ok,
                failure_rate=round(circuit.failure_rate, 2),
            )
            return

    async def _health_check_loop(self) -> None:
        while True:
            await asyncio.sleep(
                self._settings.tor_circuit_health_check_interval
            )
            for circuit in self._circuits:
                try:
                    async with httpx.AsyncClient(
                        proxy=circuit.proxy_url, timeout=15
                    ) as client:
                        await client.head("https://api.soundcloud.com")
                    circuit.ok_count += 1
                    logger.info(
                        "tor_circuit_healthy",
                        circuit=circuit.index,
                        port=circuit.socks_port,
                        ok=circuit.ok_count,
                        fail=circuit.fail_count,
                        failure_rate=round(circuit.failure_rate, 2),
                    )
                except Exception as exc:
                    circuit.fail_count += 1
                    if (
                        circuit.failure_rate
                        > self._settings.tor_circuit_max_failure_rate
                    ):
                        logger.warning(
                            "tor_circuit_degraded",
                            circuit=circuit.index,
                            port=circuit.socks_port,
                            failure_rate=round(circuit.failure_rate, 2),
                        )
                    else:
                        logger.error(
                            "tor_circuit_check_failed",
                            circuit=circuit.index,
                            port=circuit.socks_port,
                            error=str(exc),
                        )

    async def _renewal_loop(self) -> None:
        while True:
            await asyncio.sleep(self._settings.tor_circuit_max_age_seconds)
            if self._controller is None:
                logger.warning("tor_renewal_skipped_no_controller")
                continue
            try:
                from stem import Signal  # type: ignore[import-untyped]

                self._controller.signal(Signal.NEWNYM)
                now = time.time()
                for circuit in self._circuits:
                    circuit.ok_count = 0
                    circuit.fail_count = 0
                    circuit.last_renewed = now
                    logger.info(
                        "tor_circuit_renewed",
                        circuit=circuit.index,
                        port=circuit.socks_port,
                    )
                logger.info("tor_pool_all_circuits_renewed")
            except Exception as exc:
                logger.error("tor_renewal_failed", error=str(exc))
