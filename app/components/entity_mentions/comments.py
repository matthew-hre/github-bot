from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, cast

import discord

from .cache import entity_cache
from .discussions import get_discussion_comment
from .fmt import get_entity_emoji
from .integration import DeleteMention
from .models import Comment, CommentAuthor, EntityGist
from app.setup import gh

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

COMMENT_PATTERN = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+)/(issues|discussions|pull)/(\d+)#(\w+)-(\d+)"
)


async def _get_issue_comment(entity_gist: EntityGist, comment_id: int) -> Comment:
    owner, repo, _ = entity_gist
    comment_resp, entity = await asyncio.gather(
        gh.rest.issues.async_get_comment(owner, repo, comment_id),
        entity_cache.get(entity_gist),
    )
    author = (comment := comment_resp.parsed_data).user
    assert author is not None
    return Comment(
        author=CommentAuthor(
            name=author.login, url=author.html_url, icon_url=author.avatar_url
        ),
        body=cast(str, comment.body),
        entity=entity,
        entity_gist=entity_gist,
        created_at=comment.created_at,
        html_url=comment.html_url,
    )


async def get_comments(content: str) -> AsyncIterator[Comment]:
    for match in COMMENT_PATTERN.finditer(content):
        owner, repo, _kind, number, event, event_no = map(str, match.groups())
        entity_gist = EntityGist(owner, repo, int(number))
        if event.startswith("discussion"):
            yield await get_discussion_comment(entity_gist, int(event_no))
        elif event.startswith("issuecomment"):
            yield await _get_issue_comment(entity_gist, int(event_no))


def comment_to_embed(comment: Comment) -> discord.Embed:
    title = (
        f"{emoji} {comment.entity.title}"
        if (emoji := get_entity_emoji(comment.entity))
        else comment.entity.title
    )
    return (
        discord.Embed(
            description=comment.body,
            title=title,
            url=comment.html_url,
            timestamp=comment.created_at,
            color=comment.color,
        )
        .set_author(**comment.author.model_dump())
        .set_footer(text=f"Comment on {comment.entity_gist}")
    )


async def reply_with_comments(msg: discord.Message) -> None:
    embeds = [comment_to_embed(comment) async for comment in get_comments(msg.content)]
    if not embeds:
        return
    await msg.reply(
        embeds=embeds, mention_author=False, view=DeleteMention(msg, len(embeds))
    )
    await msg.edit(suppress=True)
