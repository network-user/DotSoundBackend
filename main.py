import subprocess
import sys

import uvicorn

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
            "app.services.external_import_worker",
            "app.services.import_lyrics_worker",
            "app.services.import_queue_dispatcher",
            "app.services.lyrics_global_orchestrator",
            "app.services.cover_worker",
            "app.services.lyrics_worker",
            "app.services.artist_enrichment_worker",
            "app.services.track_info_worker",
            "app.services.artist_supplemental_worker",
            "app.services.search_index_worker",
            "app.services.artist_backfill_worker",
            "app.services.waveform_worker",
            "app.services.snippet_worker",
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
