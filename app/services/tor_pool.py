from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import tempfile
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
    exit_ip: str | None = None
    exit_ip_checked_at: float = 0.0
    exit_ip_probe_pending: bool = False

    @property
    def failure_rate(self) -> float:
        total = self.ok_count + self.fail_count
        return self.fail_count / total if total > 0 else 0.0

    @property
    def proxy_url(self) -> str:
        # SOCKS5 username acts as circuit-isolation key via IsolateClientAuth.
        # Tor ignores the password; unique usernames → independent circuits →
        # genuinely diverse exit IPs even within a single Tor process.
        # httpx (socksio) sends the target hostname as a domain-name SOCKS5
        # address type (atyp=0x03), so DNS is still resolved inside Tor —
        # no need for the socks5h:// scheme that httpx does not support.
        return f"socks5://c{self.index}:dotsound@127.0.0.1:{self.socks_port}"


class TorPool:
    def __init__(self, settings: TorPoolSettings) -> None:
        self._settings = settings
        self._circuits: list[TorCircuit] = []
        self._rr_index: int = 0
        self._process: Any = None
        self._controller: Any = None
        self._control_port: int = 0
        self._newnym_callbacks: list[object] = []
        self._health_task: asyncio.Task[None] | None = None
        self._renewal_task: asyncio.Task[None] | None = None
        self._data_dir: Path | None = None
        self._force_newnym_lock = asyncio.Lock()
        self._last_force_newnym_at: float = 0.0

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

        self._control_port = control_port
        self._circuits = [
            TorCircuit(index=i, socks_port=base_port + i)
            for i in range(pool_size)
        ]

        data_dir = Path(tempfile.mkdtemp(prefix="tor_pool_"))
        os.chmod(data_dir, 0o700)
        self._data_dir = data_dir

        config: dict[str, str | list[str]] = {
            "DataDirectory": str(data_dir),
            "SocksPort": [
                f"{base_port + i} IsolateClientAuth" for i in range(pool_size)
            ],
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

        if self._data_dir is not None:
            shutil.rmtree(self._data_dir, ignore_errors=True)
            self._data_dir = None

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
        self._schedule_exit_ip_refresh(circuit)
        return circuit.proxy_url

    def describe_proxy(self, proxy_url: str) -> dict[str, Any] | None:
        for circuit in self._circuits:
            if circuit.proxy_url != proxy_url:
                continue
            self._schedule_exit_ip_refresh(circuit)
            return {
                "transport": "tor",
                "identity": f"tor:c{circuit.index}",
                "egress_ip": circuit.exit_ip,
                "socks_port": circuit.socks_port,
            }
        return None

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

    async def _try_reconnect_controller(self) -> None:
        """Attempt to re-establish the stem controller connection.

        Called by ``_renewal_loop`` when ``_controller`` is ``None``
        (e.g. initial auth failure or connection drop). A failed
        reconnect is logged as a warning and the renewal is skipped
        for this cycle — the next sleep interval will retry.
        """
        if not self._control_port:
            return
        try:
            import stem.control  # type: ignore[import-untyped]

            ctrl = stem.control.Controller.from_port(port=self._control_port)
            password: str = self._settings.tor_control_password
            if password:
                ctrl.authenticate(password=password)
            else:
                ctrl.authenticate()
            self._controller = ctrl
            logger.info(
                "tor_controller_reconnected",
                control_port=self._control_port,
            )
        except Exception as exc:
            logger.warning(
                "tor_controller_reconnect_failed",
                control_port=self._control_port,
                error=str(exc),
            )

    def circuit_proxy_urls(self) -> list[str]:
        """Return the proxy URL of every circuit in the pool."""
        return [c.proxy_url for c in self._circuits]

    async def force_newnym(
        self,
        *,
        reason: str = "manual",
        cooldown_s: float = 30.0,
    ) -> bool:
        """Force a NEWNYM signal across the pool, bypassing the timer.

        Used by the Backend recovery loop after sustained outbound
        exhaustion (Tor circuits all burned). Has a cooldown so callers
        cannot hammer the Tor network — Tor itself rate-limits NEWNYM
        and will silently drop signals that arrive too fast.

        Returns ``True`` if NEWNYM was actually sent, ``False`` if it
        was throttled, the controller is unavailable, or the call
        failed. Either way the caller should fall back to direct
        egress for the immediate request.
        """
        if self._controller is None:
            await self._try_reconnect_controller()
        if self._controller is None:
            logger.warning(
                "tor_force_newnym_skipped_no_controller",
                reason=reason,
                control_port=self._control_port,
            )
            return False
        async with self._force_newnym_lock:
            now = time.time()
            elapsed = now - self._last_force_newnym_at
            if elapsed < cooldown_s:
                logger.info(
                    "tor_force_newnym_throttled",
                    reason=reason,
                    elapsed=round(elapsed, 1),
                    cooldown=cooldown_s,
                )
                return False
            try:
                from stem import Signal

                self._controller.signal(Signal.NEWNYM)
                self._last_force_newnym_at = now
                for circuit in self._circuits:
                    circuit.ok_count = 0
                    circuit.fail_count = 0
                    circuit.exit_ip = None
                    circuit.exit_ip_checked_at = 0.0
                    circuit.last_renewed = now
                logger.warning(
                    "tor_force_newnym_signaled",
                    reason=reason,
                    pool_size=len(self._circuits),
                )
            except Exception as exc:
                logger.error(
                    "tor_force_newnym_failed",
                    reason=reason,
                    error=str(exc),
                )
                return False
        await self._run_newnym_callbacks()
        return True

    def register_newnym_callback(self, cb: object) -> None:
        """Register a callable invoked after each NEWNYM signal.

        The callback may be a plain function or an async coroutine function.
        It is called with no arguments.  Exceptions are caught and logged so
        a broken callback cannot block circuit renewal.
        """
        self._newnym_callbacks.append(cb)

    async def _run_newnym_callbacks(self) -> None:
        for cb in list(self._newnym_callbacks):
            try:
                result = cb()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.warning("tor_newnym_callback_failed", error=str(exc))

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
                        r = await client.get("https://api.ipify.org")
                        r.raise_for_status()
                        ip = (r.text or "").strip()
                        if ip:
                            circuit.exit_ip = ip[:64]
                            circuit.exit_ip_checked_at = time.time()
                            circuit.exit_ip_probe_pending = False
                    circuit.ok_count += 1
                    logger.info(
                        "tor_circuit_healthy",
                        circuit=circuit.index,
                        port=circuit.socks_port,
                        exit_ip=circuit.exit_ip,
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
                try:
                    from app.core.observability import (
                        tor_circuit_health_observed,
                    )

                    tor_circuit_health_observed(
                        circuit=circuit.index,
                        failure_rate=circuit.failure_rate,
                    )
                except Exception:
                    pass

    def _schedule_exit_ip_refresh(self, circuit: TorCircuit) -> None:
        if circuit.exit_ip_probe_pending:
            return
        if circuit.exit_ip and time.time() - circuit.exit_ip_checked_at < 300:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        circuit.exit_ip_probe_pending = True
        loop.create_task(self._refresh_circuit_exit_ip(circuit))

    async def _refresh_circuit_exit_ip(
        self,
        circuit: TorCircuit,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        close_client = client is None
        if client is None:
            client = httpx.AsyncClient(proxy=circuit.proxy_url, timeout=10)
        try:
            response = await client.get("https://api.ipify.org")
            response.raise_for_status()
            value = (response.text or "").strip()
            if value:
                circuit.exit_ip = value[:64]
                circuit.exit_ip_checked_at = time.time()
        except Exception as exc:
            logger.debug(
                "tor_circuit_exit_ip_probe_failed",
                circuit=circuit.index,
                port=circuit.socks_port,
                error=str(exc)[:200],
            )
        finally:
            circuit.exit_ip_probe_pending = False
            if close_client:
                await client.aclose()

    async def _renewal_loop(self) -> None:
        while True:
            await asyncio.sleep(self._settings.tor_circuit_max_age_seconds)
            if self._controller is None:
                await self._try_reconnect_controller()
            if self._controller is None:
                logger.warning(
                    "tor_renewal_skipped_no_controller",
                    control_port=self._control_port,
                )
                continue
            try:
                from stem import Signal

                self._controller.signal(Signal.NEWNYM)
                now = time.time()
                for circuit in self._circuits:
                    circuit.ok_count = 0
                    circuit.fail_count = 0
                    circuit.exit_ip = None
                    circuit.exit_ip_checked_at = 0.0
                    circuit.last_renewed = now
                    logger.info(
                        "tor_circuit_renewed",
                        circuit=circuit.index,
                        port=circuit.socks_port,
                    )
                logger.info("tor_pool_all_circuits_renewed")
                await self._run_newnym_callbacks()
            except Exception as exc:
                logger.error("tor_renewal_failed", error=str(exc))
