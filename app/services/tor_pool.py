from __future__ import annotations

import asyncio
import platform
import time
from dataclasses import dataclass, field

import httpx
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_tor_pool: TorPool | None = None


def get_tor_pool() -> TorPool | None:
    return _tor_pool


def _set_tor_pool(pool: TorPool | None) -> None:
    global _tor_pool
    _tor_pool = pool


def get_outbound_proxy(service: str = "") -> str | None:
    """Return a Tor SOCKS5 proxy URL for the given service, or None."""
    pool = get_tor_pool()
    if pool is None:
        return None
    return pool.get_proxy(service)


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
    def __init__(self, settings: object) -> None:
        self._settings = settings
        self._circuits: list[TorCircuit] = []
        self._rr_index: int = 0
        self._process: object = None
        self._controller: object = None
        self._health_task: asyncio.Task[None] | None = None
        self._renewal_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        import stem.control
        import stem.process

        s = self._settings
        base_port: int = s.tor_socks_base_port
        pool_size: int = s.tor_pool_size
        control_port: int = s.tor_control_port

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
            "Log": "notice stderr",
        }

        tor_cmd: str = s.tor_bin_path or (
            "tor.exe" if platform.system() == "Windows" else "tor"
        )

        logger.info(
            "tor_pool_starting",
            pool_size=pool_size,
            base_port=base_port,
            tor_cmd=tor_cmd,
        )

        try:
            self._process = await asyncio.to_thread(
                stem.process.launch_tor_with_config,
                config=config,
                tor_cmd=tor_cmd,
                timeout=90,
                take_ownership=True,
                completion_percent=80.0,
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
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self._controller is not None:
            try:
                self._controller.close()  # type: ignore[union-attr]
            except Exception:
                pass
            self._controller = None

        if self._process is not None:
            try:
                self._process.kill()  # type: ignore[union-attr]
            except Exception:
                pass
            self._process = None

        logger.info("tor_pool_stopped")

    def get_proxy(self, service: str = "") -> str:
        """Round-robin over healthy circuits; falls back to all if all degraded."""
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
            await asyncio.sleep(
                self._settings.tor_circuit_max_age_seconds
            )
            if self._controller is None:
                logger.warning("tor_renewal_skipped_no_controller")
                continue
            try:
                from stem import Signal

                self._controller.signal(Signal.NEWNYM)  # type: ignore[union-attr]
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
