import asyncio
import sys
import uvicorn

if __name__ == "__main__":
    # На Windows для работы подпроцессов (ffmpeg) нужен ProactorEventLoop
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        loop="asyncio",
    )
