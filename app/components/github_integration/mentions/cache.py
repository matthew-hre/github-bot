from githubkit.exception import RequestFailed

from .discussions import get_discussion
from app.common.cache import TTRCache
from app.components.github_integration.models import Entity, Issue, PullRequest
from app.setup import gh

type CacheKey = tuple[str, str, int]


class EntityCache(TTRCache[CacheKey, Entity]):
    async def fetch(self, key: CacheKey) -> None:
        try:
            entity = (await gh.rest.issues.async_get(*key)).parsed_data
            model = Issue
            if entity.pull_request:
                entity = (await gh.rest.pulls.async_get(*key)).parsed_data
                model = PullRequest
            self[key] = model.model_validate(entity, from_attributes=True)
        except RequestFailed:
            self[key] = await get_discussion(*key)


entity_cache = EntityCache(minutes=30)
