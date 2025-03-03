from __future__ import annotations

import re
from typing import TYPE_CHECKING

import discord

from .discussions import get_discussion_comment
from .integration import DeleteMention
from .models import Comment, EntityGist

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

COMMENT_PATTERN = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+)/(issues|discussions|pull)/(\d+)#(\w+)-(\d+)"
)


async def get_comments(content: str) -> AsyncIterator[Comment]:
    for match in COMMENT_PATTERN.finditer(content):
        owner, repo, _kind, number, event, event_no = map(str, match.groups())
        entity_gist = EntityGist(owner, repo, int(number))
        if event.startswith("discussion"):
            yield await get_discussion_comment(int(event_no), entity_gist)


def comment_to_embed(comment: Comment) -> discord.Embed:
    return (
        discord.Embed(
            description=comment.body,
            title=comment.entity_title,
            url=comment.html_url,
            timestamp=comment.created_at,
        )
        .set_author(**comment.author.model_dump())
        .set_footer(text=f"Comment on {comment.entity_gist}")
    )


async def reply_with_comments(msg: discord.Message) -> None:
    embeds = [comment_to_embed(comment) async for comment in get_comments(msg.content)]
    await msg.reply(
        embeds=embeds, mention_author=False, view=DeleteMention(msg, len(embeds))
    )
    await msg.edit(suppress=True)
