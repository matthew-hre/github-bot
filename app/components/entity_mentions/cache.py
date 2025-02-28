import datetime as dt
from abc import ABC, abstractmethod
from typing import Literal, Protocol, cast

from githubkit.exception import RequestFailed

from .discussions import get_discussion
from app.setup import gh

type CacheKey = tuple[str, str, int]
type EntityKind = Literal["Pull Request", "Issue", "Discussion"]


class GitHubUser(Protocol):
    login: str


class Entity(Protocol):
    number: int
    title: str
    html_url: str
    user: GitHubUser
    created_at: dt.datetime


class TTRCache[KT, VT](ABC):
    def __init__(self, ttr: int) -> None:
        self._ttr = dt.timedelta(seconds=ttr)
        self._cache: dict[KT, tuple[dt.datetime, VT]] = {}

    def __contains__(self, key: KT) -> bool:
        return key in self._cache

    def __getitem__(self, key: KT) -> tuple[dt.datetime, VT]:
        return self._cache[key]

    def __setitem__(self, key: KT, value: VT) -> None:
        self._cache[key] = (dt.datetime.now(tz=dt.UTC), value)

    @abstractmethod
    async def fetch(self, key: KT) -> None:
        pass

    async def _refresh(self, key: KT) -> None:
        if key not in self:
            await self.fetch(key)
            return
        timestamp, *_ = self[key]
        if dt.datetime.now(tz=dt.UTC) - timestamp >= self._ttr:
            await self.fetch(key)

    async def get(self, key: KT) -> VT:
        await self._refresh(key)
        _, value = self[key]
        return value


class EntityCache(TTRCache[CacheKey, tuple[EntityKind, Entity]]):
    async def fetch(self, key: CacheKey) -> None:
        try:
            entity = (await gh.rest.issues.async_get(*key)).parsed_data
            kind = "Issue"
            if entity.pull_request:
                entity = (await gh.rest.pulls.async_get(*key)).parsed_data
                kind = "Pull Request"
        except RequestFailed:
            entity = await get_discussion(*key)
            kind = "Discussion"
        self[key] = (kind, cast(Entity, entity))


entity_cache = EntityCache(1800)  # 30 minutes
