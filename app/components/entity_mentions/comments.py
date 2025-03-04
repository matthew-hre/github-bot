from __future__ import annotations

import asyncio
import datetime as dt
import re
from contextlib import suppress
from typing import TYPE_CHECKING, cast

import discord
from githubkit.exception import RequestFailed
from zig_codeblocks import extract_codeblocks

from .cache import TTRCache, entity_cache
from .discussions import get_discussion_comment
from .fmt import get_entity_emoji
from .models import Comment, EntityGist, GitHubUser
from app.setup import config, gh
from app.utils import MessageLinker, is_dm, is_mod, remove_view_after_timeout

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from githubkit.versions.latest.models import PullRequestReviewComment

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
    "assigned": "Assigned `{event.assignee.login}`",
    "labeled": "Added the `{event.label.name}` label",
    "milestoned": "Added this to the `{event.milestone.title}` milestone",
    "review_requested": "Requested review from `{reviewer}`",
    "unassigned": "Unassigned `{event.assignee.login}`",
    "unlabeled": "Removed the `{event.label.name}` label",
}


class CommentCache(TTRCache[tuple[EntityGist, str, int], Comment]):
    async def fetch(self, key: tuple[EntityGist, str, int]) -> None:
        entity_gist, event_type, event_no = key
        coro = {
            "discussioncomment-": get_discussion_comment,
            "issuecomment-": _get_issue_comment,
            "pullrequestreview-": _get_pr_review,
            "discussion_r": _get_pr_review_comment,
            "event-": _get_event,
            "discussion-": _get_entity_starter,
            "issue-": _get_entity_starter,
        }.get(event_type)
        if coro is None:
            return
        with suppress(RequestFailed):
            self[key] = await coro(entity_gist, event_no)


comment_cache = CommentCache(1800)  # 30 minutes


class DeleteMention(discord.ui.View):
    def __init__(self, message: discord.Message, link_count: int) -> None:
        super().__init__()
        self.message = message
        self.plural = link_count > 1

    @discord.ui.button(
        label="Delete",
        emoji="🗑️",
        style=discord.ButtonStyle.gray,
    )
    async def delete(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ) -> None:
        assert not is_dm(interaction.user)
        if interaction.user.id == self.message.author.id or is_mod(interaction.user):
            assert interaction.message
            await interaction.message.delete()
            comment_linker.unlink_from_reply(interaction.message)
            return

        await interaction.response.send_message(
            "Only the person who linked "
            + ("these comments" if self.plural else "this comment")
            + " can remove this message.",
            ephemeral=True,
        )


comment_linker = MessageLinker()


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


def _prettify_suggestions(comment: PullRequestReviewComment) -> str:
    suggestions = [
        c for c in extract_codeblocks(comment.body) if c.lang == "suggestion"
    ]
    body = comment.body
    if not suggestions:
        return body

    start = cast(int | None, comment.original_start_line)
    end = cast(int, comment.original_line)
    hunk_size = end - (end if start is None else start) + 1
    hunk_as_deleted_diff = "\n".join(
        ("-" + line[1:] if line[0] == "+" else line)
        for line in comment.diff_hunk.splitlines()[-hunk_size:]
    )

    for sug in suggestions:
        suggestion_as_added_diff = f"{hunk_as_deleted_diff}\n" + "\n".join(
            f"+{line}" for line in sug.body.splitlines()
        )
        body = body.replace(
            _make_crlf_codeblock("suggestion", sug.body.replace("\r\n", "\n")),
            _make_crlf_codeblock("diff", suggestion_as_added_diff),
            1,
        )
    return body


def _make_crlf_codeblock(lang: str, body: str) -> str:
    # GitHub seems to use CRLF for everything...
    return f"```{lang}\n{body}\n```".replace("\n", "\r\n")


async def _get_pr_review_comment(entity_gist: EntityGist, comment_id: int) -> Comment:
    owner, repo, _ = entity_gist
    comment = (
        await gh.rest.pulls.async_get_review_comment(owner, repo, comment_id)
    ).parsed_data
    assert comment.user is not None
    return Comment(
        author=GitHubUser(**comment.user.model_dump()),
        body=_prettify_suggestions(comment),
        entity=await entity_cache.get(entity_gist),
        entity_gist=entity_gist,
        created_at=cast(dt.datetime, comment.created_at),
        html_url=comment.html_url,
        kind="Review comment",
    )


async def _get_event(entity_gist: EntityGist, comment_id: int) -> Comment:
    owner, repo, entity_no = entity_gist
    event = (await gh.rest.issues.async_get_event(owner, repo, comment_id)).parsed_data
    if event.event not in SUPPORTED_EVENTS:
        body = f":ghost: Unsupported event: `{event.event}`"
    elif event.event == "review_requested":
        # Special-cased to handle requests for both users and teams
        if event.requested_reviewer:
            reviewer = event.requested_reviewer.login
        else:
            assert event.requested_team
            # Throwing in the org name to make it clear that it's a team
            reviewer = f"{config.GITHUB_ORG}/{event.requested_team.name}"
        body = SUPPORTED_EVENTS[event.event].format(reviewer=reviewer)
    elif event.event.endswith("locked"):
        body = SUPPORTED_EVENTS[event.event].format(
            entity=await entity_cache.get(entity_gist)
        )
        if event.lock_reason:
            body += f"\nReason: `{event.lock_reason or 'no reason'}`"
    else:
        template = SUPPORTED_EVENTS[event.event]
        body = (
            template.format(entity=await entity_cache.get(entity_gist))
            if event.event in ENTITY_UPDATE_EVENTS
            else template.format(event=event)
        )
    author = GitHubUser(**event.actor.model_dump()) if event.actor else FALLBACK_AUTHOR
    # The API doesn't return an html_url, gotta construct it manually.
    # It's fine to say "issues" here, GitHub will resolve the correct type
    url = f"https://github.com/{owner}/{repo}/issues/{entity_no}#event-{comment_id}"
    return Comment(
        author=author,
        body=f"**{body}**",
        entity=await entity_cache.get(entity_gist),
        entity_gist=entity_gist,
        created_at=event.created_at,
        html_url=url,
        kind="Event",
        color=EVENT_COLOR,
    )


async def _get_entity_starter(entity_gist: EntityGist, _: int) -> Comment:
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
        owner, repo, _, number, event, event_no = map(str, match.groups())
        entity_gist = EntityGist(owner, repo, int(number))
        with suppress(KeyError):
            yield await comment_cache.get((entity_gist, event, int(event_no)))


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


async def reply_with_comments(message: discord.Message) -> None:
    embeds = [
        comment_to_embed(comment) async for comment in get_comments(message.content)
    ]
    if not embeds:
        return
    sent_message = await message.reply(
        embeds=embeds, mention_author=False, view=DeleteMention(message, len(embeds))
    )
    await message.edit(suppress=True)
    comment_linker.link(message, sent_message)
    await remove_view_after_timeout(sent_message)


async def entity_comment_delete_handler(message: discord.Message) -> None:
    if message.author.bot:
        comment_linker.unlink_from_reply(message)
    elif replies := comment_linker.get(message):
        for reply in replies:
            await reply.delete()


async def entity_comment_edit_handler(
    before: discord.Message, after: discord.Message
) -> None:
    if before.content == after.content:
        return
    old_comments = [i async for i in get_comments(before.content)]
    new_comments = [i async for i in get_comments(after.content)]
    if old_comments == new_comments:
        # Message changed but linked comments are the same
        return

    if not (replies := comment_linker.get(before)):
        if not old_comments:
            # There were no linked comments before, so treat this as a new message
            await reply_with_comments(after)
        # The message was removed from the M2C map at some point
        return

    reply = replies[0]
    if not new_comments:
        # All comment links were edited out
        comment_linker.unlink(before)
        await reply.delete()
        return

    if comment_linker.unlink_if_expired(reply):
        return

    await reply.edit(
        embeds=list(map(comment_to_embed, new_comments)),
        view=DeleteMention(after, len(new_comments)),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    await remove_view_after_timeout(reply)
