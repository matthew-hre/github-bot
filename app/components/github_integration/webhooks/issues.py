from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Protocol, cast

from loguru import logger

from app.components.github_integration.webhooks.core import (
    EmbedContent,
    Footer,
    SubhookStore,
    client,
    make_subhook_registrar,
    send_embed,
)

if TYPE_CHECKING:
    from githubkit.typing import Missing
    from githubkit.versions.latest.models import (
        WebhookIssueCommentCreated,
        WebhookIssuesClosed,
        WebhookIssuesLocked,
        WebhookIssuesOpened,
        WebhookIssuesPinned,
        WebhookIssuesReopened,
        WebhookIssuesUnlocked,
        WebhookIssuesUnpinned,
    )
    from monalisten.types import IssueCommentEvent, IssuesEvent

    from app.components.github_integration.emoji import EmojiName

issue_subhooks: SubhookStore[IssuesEvent] = {}

register_issue_subhook = make_subhook_registrar(issue_subhooks)


CONVERTED_DISCUSSION_HEADER = re.compile(
    r"\s*### Discussed in https://github.com/.*?/discussions/(?P<discussion_number>\d+)"
    r"\s*<div type='discussions-op-text'>"
    r"\s*<sup>(?P<subtext>.+?)</sup>",
    re.MULTILINE,
)


def reformat_converted_discussion_header(body: str | None, repo_url: str) -> str | None:
    if body is None or not (match := CONVERTED_DISCUSSION_HEADER.match(body)):
        return body

    d, subtext = match["discussion_number"], match["subtext"]
    new_heading = f"### Discussed in [#{d}]({repo_url}/discussions/{d})\n-# {subtext}\n"

    _, end = match.span()
    return new_heading + "".join(body[end:].lstrip().rsplit("</div>", maxsplit=1))


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


def issue_footer(issue: IssueLike, *, emoji: EmojiName | None = None) -> Footer:
    return Footer(
        emoji or get_issue_emoji(issue), f"Issue #{issue.number}: {issue.title}"
    )


def issue_embed_content(
    issue: IssueLike, template: str, body: str | None = None
) -> EmbedContent:
    return EmbedContent(template.format(f"issue #{issue.number}"), issue.html_url, body)


@client.on("issues")
async def handle_issue_event(event: IssuesEvent) -> None:
    if subhook := issue_subhooks.get(event.action):
        await subhook(event)


@register_issue_subhook("opened")
async def handle_opened_issue(event: WebhookIssuesOpened) -> None:
    issue = event.issue
    body = reformat_converted_discussion_header(issue.body, event.repository.html_url)
    await send_embed(
        event.sender,
        issue_embed_content(issue, "opened {}", body),
        issue_footer(issue, emoji="issue_open"),
        color="green",
    )


@register_issue_subhook("closed")
async def handle_closed_issue(event: WebhookIssuesClosed) -> None:
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
        event.sender,
        issue_embed_content(issue, f"closed {{}} as {state_reason}"),
        issue_footer(issue, emoji="issue_closed_" + emoji_kind),
        color=color,
    )


@register_issue_subhook("reopened")
async def handle_reopened_issue(event: WebhookIssuesReopened) -> None:
    issue = event.issue
    await send_embed(
        event.sender,
        issue_embed_content(issue, "reopened {}"),
        issue_footer(issue, emoji="issue_open"),
        color="green",
    )


@register_issue_subhook("locked")
async def handle_locked_issue(event: WebhookIssuesLocked) -> None:
    issue = event.issue
    reason = f" as {r}" if (r := issue.active_lock_reason) else ""
    await send_embed(
        event.sender,
        issue_embed_content(issue, f"locked {{}}{reason}"),
        issue_footer(issue),
        color="orange",
    )


@register_issue_subhook("unlocked")
async def handle_unlocked_issue(event: WebhookIssuesUnlocked) -> None:
    issue = event.issue
    await send_embed(
        event.sender,
        issue_embed_content(issue, "unlocked {}"),
        issue_footer(issue),
        color="blue",
    )


@register_issue_subhook("pinned")
async def handle_pinned_issue(event: WebhookIssuesPinned) -> None:
    issue = event.issue
    await send_embed(
        event.sender,
        issue_embed_content(issue, "pinned {}"),
        issue_footer(issue),
        color="blue",
    )


@register_issue_subhook("unpinned")
async def handle_unpinned_issue(event: WebhookIssuesUnpinned) -> None:
    issue = event.issue
    await send_embed(
        event.sender,
        issue_embed_content(issue, "unpinned {}"),
        issue_footer(issue),
        color="orange",
    )


@client.on("issue_comment")
async def handle_issue_comment_event(event: IssueCommentEvent) -> None:
    if event.action == "created":
        await handle_created_issue_comment(event)


async def handle_created_issue_comment(event: WebhookIssueCommentCreated) -> None:
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
        event.sender,
        EmbedContent(title, issue.html_url, event.comment.body),
        Footer(emoji, f"{entity}: {issue.title}"),
    )
