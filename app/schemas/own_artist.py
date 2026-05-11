from __future__ import annotations

from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
)


class OwnArtistFields(BaseModel):
    id: int
    name: str
    image_key: str | None = None
    bio: str | None = None
    country: str | None = None
    birth_date: date | None = None
    birthplace: str | None = None
    website_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OwnArtistStatusResponse(BaseModel):
    has_artist: bool
    display_name: str | None = None
    artist: OwnArtistFields | None = None


class OwnArtistUpdateRequest(BaseModel):
    bio: str | None = Field(None, max_length=2000)
    country: str | None = Field(None, max_length=2)
    birth_date: date | None = None
    birthplace: str | None = Field(None, max_length=128)
    website_url: str | None = Field(None, max_length=512)

    @field_validator("website_url")
    @classmethod
    def _validate_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip()
        if not s:
            return None
        # Validate with pydantic's HttpUrl; require http/https scheme.
        try:
            parsed = HttpUrl(s)
        except Exception as exc:
            raise ValueError(
                "website_url must be a valid http(s) URL"
            ) from exc
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                "website_url must use http or https scheme"
            )
        return str(parsed)

    @field_validator("country")
    @classmethod
    def _validate_country(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = v.strip().upper()
        if not s:
            return None
        try:
            from dotsound_private_core.services.country_codes import (
                ISO_COUNTRY_CODES,
            )
        except ImportError:  # pragma: no cover
            return s[:2]
        if s not in ISO_COUNTRY_CODES:
            raise ValueError(
                "country must be a valid ISO 3166-1 alpha-2 code"
            )
        return s


class OwnArtistEnsureResponse(BaseModel):
    artist: OwnArtistFields
