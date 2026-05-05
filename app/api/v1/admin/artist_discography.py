"""Admin HTTP API for manual artist discography overrides."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_admin_session
from app.models.user import User
from app.repositories.artist import ArtistRepository
from app.schemas.artist import DiscographyItemResponse

router = APIRouter(prefix="/artists", tags=["admin-artist-discography"])


@router.get(
    "/{artist_id}/discography",
    response_model=list[DiscographyItemResponse],
)
async def admin_get_artist_discography(
    artist_id: int,
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> list[ArtistDiscographyResponse]:
    repo = ArtistRepository(session)
    artist = await repo.get_by_id(artist_id)
    if artist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )
    raw = artist.discography or []
    items: list[DiscographyItemResponse] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            continue
        items.append(
            DiscographyItemResponse(
                title=title,
                year=item.get("year"),
                type=item.get("type"),
                url=item.get("url"),
            )
        )
    return items


@router.put(
    "/{artist_id}/discography",
    response_model=list[DiscographyItemResponse],
)
async def admin_put_artist_discography(
    artist_id: int,
    body: list[DiscographyItemResponse],
    session: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin_session),
) -> list[DiscographyItemResponse]:
    repo = ArtistRepository(session)
    artist = await repo.get_by_id(artist_id)
    if artist is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artist not found",
        )
    cleaned: list[dict] = []
    for item in body:
        title = item.title.strip()
        if not title:
            continue
        row: dict[str, object] = {"title": title[:256]}
        if item.year is not None:
            row["year"] = int(item.year)
        if item.type is not None:
            row["type"] = item.type[:64]
        if item.url is not None:
            row["url"] = item.url[:1024]
        cleaned.append(row)
    artist.discography = cleaned or None
    artist.discography_manual_lock = True
    await session.commit()
    return [
        DiscographyItemResponse(
            title=row["title"],
            year=row.get("year"),
            type=row.get("type"),
            url=row.get("url"),
        )
        for row in cleaned
    ]

