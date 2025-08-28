from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, cast

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


class IssueLike(Protocol):
    state: Missing[Literal["open", "closed"]]
    state_reason: Missing[str | None]


def get_issue_emoji(issue: IssueLike) -> EmojiName:
    if issue.state == "open":
        return "issue_open"
    if issue.state_reason == "completed":
        return "issue_closed_completed"
    return "issue_closed_unplanned"


@client.on("issues")
async def handle_issue_event(event: IssuesEvent) -> None:
    if subhook := issue_subhooks.get(event.action):
        await subhook(event)


@register_issue_subhook("opened")
async def handle_opened_issue(event: WebhookIssuesOpened) -> None:
    issue, number = event.issue, event.issue.number
    await send_embed(
        event.sender,
        EmbedContent(f"opened issue #{number}", issue.html_url, issue.body),
        Footer("issue_open", f"Issue #{number}: {issue.title}"),
        color="green",
    )


@register_issue_subhook("closed")
async def handle_closed_issue(event: WebhookIssuesClosed) -> None:
    issue, number = event.issue, event.issue.number
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
        EmbedContent(f"closed issue #{number} as {state_reason}", issue.html_url),
        Footer("issue_closed_" + emoji_kind, f"Issue #{number}: {issue.title}"),
        color=color,
    )


@register_issue_subhook("reopened")
async def handle_reopened_issue(event: WebhookIssuesReopened) -> None:
    issue, number = event.issue, event.issue.number
    await send_embed(
        event.sender,
        EmbedContent(f"reopened issue #{number}", issue.html_url),
        Footer("issue_open", f"Issue #{number}: {issue.title}"),
        color="green",
    )


@register_issue_subhook("locked")
async def handle_locked_issue(event: WebhookIssuesLocked) -> None:
    issue, number = event.issue, event.issue.number
    title = f"locked issue #{number}"
    if reason := issue.active_lock_reason:
        title += f" as {reason}"
    await send_embed(
        event.sender,
        EmbedContent(title, issue.html_url),
        Footer(get_issue_emoji(issue), f"Issue #{number}: {issue.title}"),
        color="orange",
    )


@register_issue_subhook("unlocked")
async def handle_unlocked_issue(event: WebhookIssuesUnlocked) -> None:
    issue, number = event.issue, event.issue.number
    await send_embed(
        event.sender,
        EmbedContent(f"unlocked issue #{number}", issue.html_url),
        Footer(get_issue_emoji(issue), f"Issue #{number}: {issue.title}"),
        color="blue",
    )


@register_issue_subhook("pinned")
async def handle_pinned_issue(event: WebhookIssuesPinned) -> None:
    issue, number = event.issue, event.issue.number
    await send_embed(
        event.sender,
        EmbedContent(f"pinned issue #{number}", issue.html_url),
        Footer(get_issue_emoji(issue), f"Issue #{number}: {issue.title}"),
        color="blue",
    )


@register_issue_subhook("unpinned")
async def handle_unpinned_issue(event: WebhookIssuesUnpinned) -> None:
    issue, number = event.issue, event.issue.number
    await send_embed(
        event.sender,
        EmbedContent(f"unpinned issue #{number}", issue.html_url),
        Footer(get_issue_emoji(issue), f"Issue #{number}: {issue.title}"),
        color="orange",
    )


@client.on("issue_comment")
async def handle_issue_comment_event(event: IssueCommentEvent) -> None:
    if event.action == "created":
        await handle_created_issue_comment(event)


async def handle_created_issue_comment(event: WebhookIssueCommentCreated) -> None:
    issue, number = event.issue, event.issue.number

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
        entity = f"Issue #{number}"
        title += entity.casefold()
        emoji = get_issue_emoji(cast("IssueLike", issue))

    await send_embed(
        event.sender,
        EmbedContent(title, issue.html_url, event.comment.body),
        Footer(emoji, f"{entity}: {issue.title}"),
    )
