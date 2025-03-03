from __future__ import annotations

import asyncio
import datetime as dt
import re
from typing import TYPE_CHECKING, cast

import discord

from .cache import entity_cache
from .discussions import get_discussion_comment
from .fmt import get_entity_emoji
from .integration import DeleteMention
from .models import Comment, EntityGist, GitHubUser
from app.setup import gh

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

COMMENT_PATTERN = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+)/(issues|discussions|pull)/(\d+)#(\w+?-?)(\d+)"
)
FALLBACK_AUTHOR = GitHubUser(
    login="GitHub",
    url="https://github.com",
    icon_url="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
)
STATE_TO_COLOR = {
    "APPROVED": 0x2ECC71,  # green
    "CHANGES_REQUESTED": 0xE74C3C,  # red
}
EVENT_COLOR = 0x3498DB  # blue
ENTITY_UPDATE_EVENTS = {
    "closed": "Closed the {entity.kind}",
    "locked": "Locked the {entity.kind}",
    "merged": "Merged the {entity.kind}",
    "reopened": "Reopened the {entity.kind}",
    "unlocked": "Unlocked the {entity.kind}",
}
SUPPORTED_EVENTS = ENTITY_UPDATE_EVENTS | {
    "assigned": "Assigned `{event.assignee}`",
    "labeled": "Added the `{event.label.name}` label",
    "milestoned": "Added the `{event.milestone.title}` milestone",
    "review_requested": "Requested review from `{event.requested_reviewer}`",
    "unassigned": "Unassigned `{event.assignee}`",
    "unlabeled": "Removed the `{event.label.name}` label",
}


async def _get_issue_comment(entity_gist: EntityGist, comment_id: int) -> Comment:
    owner, repo, _ = entity_gist
    comment_resp, entity = await asyncio.gather(
        gh.rest.issues.async_get_comment(owner, repo, comment_id),
        entity_cache.get(entity_gist),
    )
    author = (comment := comment_resp.parsed_data).user
    assert author is not None
    return Comment(
        author=GitHubUser(**author.model_dump()),
        body=cast(str, comment.body),
        entity=entity,
        entity_gist=entity_gist,
        created_at=comment.created_at,
        html_url=comment.html_url,
    )


async def _get_pr_review(entity_gist: EntityGist, comment_id: int) -> Comment:
    comment = (
        await gh.rest.pulls.async_get_review(*entity_gist, comment_id)
    ).parsed_data
    assert comment.user is not None
    return Comment(
        author=GitHubUser(**comment.user.model_dump()),
        body=comment.body,
        entity=await entity_cache.get(entity_gist),
        entity_gist=entity_gist,
        created_at=cast(dt.datetime, comment.submitted_at),
        html_url=comment.html_url,
        color=STATE_TO_COLOR.get(comment.state),
        kind="Review",
    )


async def _get_pr_review_comment(entity_gist: EntityGist, comment_id: int) -> Comment:
    owner, repo, _ = entity_gist
    comment = (
        await gh.rest.pulls.async_get_review_comment(owner, repo, comment_id)
    ).parsed_data
    assert comment.user is not None
    return Comment(
        author=GitHubUser(**comment.user.model_dump()),
        body=comment.body,
        entity=await entity_cache.get(entity_gist),
        entity_gist=entity_gist,
        created_at=cast(dt.datetime, comment.created_at),
        html_url=comment.html_url,
        kind="Review comment",
    )


async def _get_event(entity_gist: EntityGist, comment_id: int) -> Comment:
    owner, repo, _ = entity_gist
    event = (await gh.rest.issues.async_get_event(owner, repo, comment_id)).parsed_data
    if event.event not in SUPPORTED_EVENTS:
        body = f":ghost: Unsupported event: `{event.event}`"
    else:
        template = SUPPORTED_EVENTS[event.event]
        body = (
            template.format(entity=await entity_cache.get(entity_gist))
            if event.event in ENTITY_UPDATE_EVENTS
            else template.format(event=event)
        )
    author = GitHubUser(**event.actor.model_dump()) if event.actor else FALLBACK_AUTHOR
    return Comment(
        author=author,
        body=f"**{body}**",
        entity=await entity_cache.get(entity_gist),
        entity_gist=entity_gist,
        created_at=event.created_at,
        html_url=event.url,
        kind="Event",
        color=EVENT_COLOR,
    )


async def _get_entity_starter(entity_gist: EntityGist) -> Comment:
    entity = await entity_cache.get(entity_gist)
    return Comment(
        author=entity.user,
        body=entity.body,
        entity=entity,
        entity_gist=entity_gist,
        created_at=entity.created_at,
        html_url=entity.html_url,
    )


async def get_comments(content: str) -> AsyncIterator[Comment]:
    for match in COMMENT_PATTERN.finditer(content):
        owner, repo, _kind, number, event, event_no = map(str, match.groups())
        entity_gist = EntityGist(owner, repo, int(number))
        if event.startswith("discussioncomment-"):
            yield await get_discussion_comment(entity_gist, int(event_no))
        if event.startswith(("discussion-", "issue-")):
            yield await _get_entity_starter(entity_gist)
        elif event.startswith("issuecomment-"):
            yield await _get_issue_comment(entity_gist, int(event_no))
        elif event.startswith("pullrequestreview-"):
            yield await _get_pr_review(entity_gist, int(event_no))
        elif event.startswith("discussion_r"):
            yield await _get_pr_review_comment(entity_gist, int(event_no))
        elif event.startswith("event"):
            yield await _get_event(entity_gist, int(event_no))
        else:
            # Unsupported event
            continue


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
        .set_footer(text=f"{comment.kind} on {comment.entity_gist}")
    )


async def reply_with_comments(msg: discord.Message) -> None:
    embeds = [comment_to_embed(comment) async for comment in get_comments(msg.content)]
    if not embeds:
        return
    await msg.reply(
        embeds=embeds, mention_author=False, view=DeleteMention(msg, len(embeds))
    )
    await msg.edit(suppress=True)
