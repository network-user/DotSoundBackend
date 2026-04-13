from app.core.tkq import broker


@broker.task
async def refresh_tor_list() -> int:
    from app.core.tor_checker import (
        refresh_tor_exit_nodes,
    )

    return await refresh_tor_exit_nodes()
