from pathlib import Path


def _service_block(compose: str, service: str) -> str:
    marker = f"\n  {service}:\n"
    start = compose.index(marker) + len(marker)
    next_service = compose.find("\n  ", start)
    while next_service != -1:
        line_end = compose.find("\n", next_service + 1)
        line = compose[next_service + 1 : line_end]
        if line.startswith("  ") and not line.startswith("    "):
            return compose[start:next_service]
        next_service = compose.find("\n  ", line_end)
    return compose[start:]


def test_compose_backend_uses_bot_service_internal_url() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "BOT_INTERNAL_URL: http://bot:8081" in _service_block(
        compose,
        "backend",
    )
    assert "BOT_INTERNAL_URL: http://bot:8081" in _service_block(
        compose,
        "worker",
    )


def test_compose_dev_services_mount_private_core_source() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    mount = "../DotSoundPrivateCore:/DotSoundPrivateCore:ro"
    pythonpath = "PYTHONPATH: /DotSoundPrivateCore/src"

    for service in ("backend", "worker"):
        block = _service_block(compose, service)
        assert mount in block
        assert pythonpath in block
