from pydantic import BaseModel


class AdminPlaybackVerifyResponse(BaseModel):
    ok: bool
    detail: str = ""
    http_status: int | None = None
    effective_track_id: int | None = None
    stream_protocol: str | None = None
