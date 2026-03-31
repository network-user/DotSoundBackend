from pydantic import BaseModel


class ShareResponse(BaseModel):
    track_id: int
    url: str
    telegram_share_url: str
