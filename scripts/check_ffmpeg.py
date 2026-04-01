import asyncio
import sys

async def check():
    print(f"Platform: {sys.platform}")
    
    # Имитируем логику из app/main.py
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    print(f"Current loop type: {type(loop).__name__}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        if process.returncode == 0:
            print("SUCCESS: ffmpeg executed successfully via asyncio.create_subprocess_exec")
            print(f"FFmpeg version line: {stdout.decode().splitlines()[0]}")
        else:
            print(f"FAILED: ffmpeg returned code {process.returncode}")
    except NotImplementedError:
        print("FAILED: NotImplementedError - SelectorEventLoop is likely being used")
    except FileNotFoundError:
        print("FAILED: ffmpeg not found in PATH")
    except Exception as e:
        print(f"FAILED: Unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
