from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PromotionEntityType = Literal["artist", "track", "playlist", "album"]
PromotionSurface = Literal["hero", "section", "in_feed", "search_pin"]
PromotionEventType = Literal["impression", "click"]
PromotionAvailability = Literal["available", "hidden", "missing"]


class PromotionEntityRef(BaseModel):
    entity_type: PromotionEntityType
    entity_id: int
    title: str
    subtitle: str | None = None
    cover_url: str | None = None


class PromotionPublic(BaseModel):
    id: int
    entity_type: PromotionEntityType
    entity_id: int
    surfaces: list[PromotionSurface]
    priority: int
    title: str
    subtitle: str | None = None
    cta_label: str | None = None
    cover_url: str | None = None
    entity: PromotionEntityRef


class PromotionListResponse(BaseModel):
    items: list[PromotionPublic]


class PromotionAdminItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: PromotionEntityType
    entity_id: int
    entity_label: str | None = None
    surfaces: list[PromotionSurface]
    priority: int
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    availability: PromotionAvailability
    impressions_total: int = 0
    clicks_total: int = 0
    created_at: datetime
    updated_at: datetime


class PromotionAdminListResponse(BaseModel):
    items: list[PromotionAdminItem]
    total: int
    page: int
    size: int


class PromotionAdminDetail(PromotionAdminItem):
    title_override: str | None = None
    subtitle_override: str | None = None
    cta_label_override: str | None = None
    cover_url_override: str | None = None
    created_by_id: int | None = None
    updated_by_id: int | None = None


class PromotionCreateRequest(BaseModel):
    entity_type: PromotionEntityType
    entity_id: int = Field(gt=0)
    surfaces: list[PromotionSurface] = Field(default_factory=list)
    priority: int = Field(default=0, ge=-1000, le=1000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    title_override: str | None = Field(default=None, max_length=256)
    subtitle_override: str | None = Field(default=None, max_length=512)
    cta_label_override: str | None = Field(default=None, max_length=64)
    cover_url_override: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def _check_window(self) -> PromotionCreateRequest:
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at <= self.starts_at
        ):
            raise ValueError("ends_at must be strictly after starts_at")
        return self

    @model_validator(mode="after")
    def _check_surfaces_unique(self) -> PromotionCreateRequest:
        if len(set(self.surfaces)) != len(self.surfaces):
            raise ValueError("surfaces must be unique")
        return self


class PromotionPatchRequest(BaseModel):
    surfaces: list[PromotionSurface] | None = None
    priority: int | None = Field(default=None, ge=-1000, le=1000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None
    title_override: str | None = Field(default=None, max_length=256)
    subtitle_override: str | None = Field(default=None, max_length=512)
    cta_label_override: str | None = Field(default=None, max_length=64)
    cover_url_override: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def _check_surfaces_unique(self) -> PromotionPatchRequest:
        if self.surfaces is not None and len(set(self.surfaces)) != len(
            self.surfaces
        ):
            raise ValueError("surfaces must be unique")
        return self


class PromotionEventCreateRequest(BaseModel):
    event_type: PromotionEventType
    surface: PromotionSurface | None = None


class PromotionEventAck(BaseModel):
    ok: bool = True


class PromotionStatsResponse(BaseModel):
    promotion_id: int
    period_days: int
    impressions: int
    clicks: int
    plays: int
    ctr: float = 0.0
