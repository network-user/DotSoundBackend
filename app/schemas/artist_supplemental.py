from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArtistSupplementalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    content: str | None = None
    fetched_at: datetime | None = None
