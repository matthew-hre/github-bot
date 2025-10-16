from __future__ import annotations

from typing import TYPE_CHECKING, override

from githubkit.exception import RequestFailed

from app.common.cache import TTRCache
from app.components.github_integration.models import Entity, Issue, PullRequest
from app.config import gh

if TYPE_CHECKING:
    from githubkit import GitHub, TokenAuthStrategy

type EntitySignature = tuple[str, str, int]


class EntityCache(TTRCache[EntitySignature, Entity]):
    def __init__(self, gh: GitHub[TokenAuthStrategy], **ttr: float) -> None:
        super().__init__(**ttr)
        self.gh: GitHub[TokenAuthStrategy] = gh

    @override
    async def fetch(self, key: EntitySignature) -> None:
        try:
            entity = (await self.gh.rest.issues.async_get(*key)).parsed_data
            model = Issue
            if entity.pull_request:
                entity = (await self.gh.rest.pulls.async_get(*key)).parsed_data
                model = PullRequest
            self[key] = model.model_validate(entity, from_attributes=True)
        except RequestFailed:
            pass


entity_cache = EntityCache(gh, minutes=30)
