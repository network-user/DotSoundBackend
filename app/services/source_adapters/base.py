from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SourceTrack:
    external_id: str
    title: str
    artist: str | None
    duration_seconds: int | None
    artwork_url: str | None
    source_url: str
    source_uri: str | None = None
    genre: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StreamInfo:
    url: str
    protocol: str


class MusicSourceAdapter(abc.ABC):
    @property
    @abc.abstractmethod
    def source_name(self) -> str: ...

    @abc.abstractmethod
    async def search(
        self, query: str, limit: int = 20
    ) -> list[SourceTrack]: ...

    @abc.abstractmethod
    async def resolve_url(
        self, url: str
    ) -> SourceTrack: ...

    @abc.abstractmethod
    async def get_stream_info(
        self,
        source_url: str,
        prefer_hls: bool = False,
    ) -> StreamInfo: ...


class SourceRegistry:
    def __init__(self) -> None:
        self._adapters: dict[
            str, MusicSourceAdapter
        ] = {}

    def register(
        self, adapter: MusicSourceAdapter
    ) -> None:
        self._adapters[adapter.source_name] = adapter

    def get(
        self, source_name: str
    ) -> MusicSourceAdapter | None:
        return self._adapters.get(source_name)

    def list_sources(self) -> list[str]:
        return list(self._adapters.keys())

    def search_all(
        self, query: str, limit: int = 10
    ) -> dict[str, MusicSourceAdapter]:
        return dict(self._adapters)
