from __future__ import annotations

import re
from functools import partial
from typing import TYPE_CHECKING, Any, Protocol, cast

from loguru import logger

from app.components.github_integration.webhooks.utils import (
    EmbedContent,
    Footer,
    send_edit_difference,
    send_embed,
)

if TYPE_CHECKING:
    from githubkit.typing import Missing
    from githubkit.versions.latest.models import RepositoryWebhooks
    from monalisten import Monalisten, events

    from app.bot import EmojiName, GhosttyBot


GITHUB_DISCUSSION_URL = re.compile(
    # Ignore if already inside a link block
    r"(?<!\()"
        r"https://github\.com/"
        r"(?P<owner>\b[a-zA-Z0-9\-]+/)"
        r"(?P<repo>\b[a-zA-Z0-9\-\._]+)"
        r"(?P<sep>/(?:issues|pull|discussions)/)"
        r"(?P<number>\d+)"
    r"(?!\))"
)  # fmt: skip
SUP_HTML = re.compile(r"\s*<sup>((?:.|\s)+?)</sup>\s*")
DISUCSSION_DIV_TAG = re.compile(
    r"\s*<div type='discussions-op-text'>((?:.|\s)*?)\s*</div>\s*", re.MULTILINE
)


def shorten_same_repo_links(
    origin_repo: RepositoryWebhooks, matchobj: re.Match[str]
) -> str:
    if (
        matchobj.group("owner") == origin_repo.owner.name
        and matchobj.group("repo") == origin_repo.name
    ):
        # Only short hand if link comes from same repo
        return f"[#{matchobj.group('number')}]({matchobj.group()})"
    return matchobj.group()


def reformat_converted_discussion_header(
    body: str | None, repo: RepositoryWebhooks
) -> str | None:
    if not body:
        return body
    body = SUP_HTML.sub(
        lambda x: "".join(f"\n-# {line}\n" for line in x.group(1).splitlines()), body
    )
    body = DISUCSSION_DIV_TAG.sub(r"\g<1>", body)
    body = GITHUB_DISCUSSION_URL.sub(partial(shorten_same_repo_links, repo), body)
    return body  # noqa: RET504


class IssueLike(Protocol):
    title: str
    number: int
    html_url: str
    state: Any
    state_reason: Missing[str | None]


def get_issue_emoji(issue: IssueLike) -> EmojiName:
    if issue.state == "open":
        return "issue_open"
    if issue.state_reason == "completed":
        return "issue_closed_completed"
    return "issue_closed_unplanned"


def issue_footer(issue: IssueLike, /, *, emoji: EmojiName | None = None) -> Footer:
    return Footer(
        emoji or get_issue_emoji(issue), f"Issue #{issue.number}: {issue.title}"
    )


def issue_embed_content(
    issue: IssueLike, template: str, body: str | None = None, /
) -> EmbedContent:
    return EmbedContent(template.format(f"issue #{issue.number}"), issue.html_url, body)


def register_hooks(bot: GhosttyBot, webhook: Monalisten) -> None:
    @webhook.event.issues.opened
    async def _(event: events.IssuesOpened) -> None:
        issue = event.issue
        body = reformat_converted_discussion_header(issue.body, event.repository)
        await send_embed(
            bot,
            event.sender,
            issue_embed_content(issue, "opened {}", body),
            issue_footer(issue, emoji="issue_open"),
            color="green",
        )

    @webhook.event.issues.closed
    async def _(event: events.IssuesClosed) -> None:
        issue = event.issue
        match issue.state_reason:
            case "completed":
                color, emoji_kind = "purple", "completed"
            case "not_planned" | "duplicate":
                color, emoji_kind = "gray", "unplanned"
            case _:
                logger.warning("unexpected state reason: {}", issue.state_reason)
                return

        state_reason = cast("str", issue.state_reason).replace("_", " ")
        await send_embed(
            bot,
            event.sender,
            issue_embed_content(issue, f"closed {{}} as {state_reason}"),
            issue_footer(issue, emoji="issue_closed_" + emoji_kind),
            color=color,
        )

    @webhook.event.issues.reopened
    async def _(event: events.IssuesReopened) -> None:
        issue = event.issue
        await send_embed(
            bot,
            event.sender,
            issue_embed_content(issue, "reopened {}"),
            issue_footer(issue, emoji="issue_open"),
            color="green",
        )

    @webhook.event.issues.edited
    async def _(event: events.IssuesEdited) -> None:
        await send_edit_difference(bot, event, issue_embed_content, issue_footer)

    @webhook.event.issues.locked
    async def _(event: events.IssuesLocked) -> None:
        issue = event.issue
        reason = f" as {r}" if (r := issue.active_lock_reason) else ""
        await send_embed(
            bot,
            event.sender,
            issue_embed_content(issue, f"locked {{}}{reason}"),
            issue_footer(issue),
            color="orange",
        )

    @webhook.event.issues.unlocked
    async def _(event: events.IssuesUnlocked) -> None:
        issue = event.issue
        await send_embed(
            bot,
            event.sender,
            issue_embed_content(issue, "unlocked {}"),
            issue_footer(issue),
            color="blue",
        )

    @webhook.event.issues.pinned
    async def _(event: events.IssuesPinned) -> None:
        issue = event.issue
        await send_embed(
            bot,
            event.sender,
            issue_embed_content(issue, "pinned {}"),
            issue_footer(issue),
            color="blue",
        )

    @webhook.event.issues.unpinned
    async def _(event: events.IssuesUnpinned) -> None:
        issue = event.issue
        await send_embed(
            bot,
            event.sender,
            issue_embed_content(issue, "unpinned {}"),
            issue_footer(issue),
            color="orange",
        )

    @webhook.event.issue_comment.created
    async def _(event: events.IssueCommentCreated) -> None:
        issue = event.issue
        title = "commented on "
        if issue.pull_request:
            entity = f"PR #{issue.number}"
            title += entity
            emoji = "pull_" + (
                ("merged" if issue.pull_request.merged_at else "closed")
                if issue.state == "closed"
                else ("draft" if issue.draft else "open")
            )
        else:
            entity = f"Issue #{issue.number}"
            title += entity.casefold()
            emoji = get_issue_emoji(cast("IssueLike", issue))

        await send_embed(
            bot,
            event.sender,
            EmbedContent(title, event.comment.html_url, event.comment.body),
            Footer(emoji, f"{entity}: {issue.title}"),
        )
