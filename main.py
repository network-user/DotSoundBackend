import asyncio
import subprocess
import sys

import uvicorn

if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsProactorEventLoopPolicy()
    )


if __name__ == "__main__":
    worker_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "taskiq",
            "worker",
            "app.core.tkq:broker",
            "app.services.transcoding",
            "app.services.import_worker",
            "app.services.cover_worker",
            "app.services.lyrics_worker",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    try:
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            loop="asyncio",
        )
    finally:
        worker_proc.terminate()
        worker_proc.wait(timeout=5)
