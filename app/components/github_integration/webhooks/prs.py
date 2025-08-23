from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from app.components.github_integration.webhooks.core import (
    EmbedContent,
    Footer,
    SubhookStore,
    client,
    make_subhook_registrar,
    send_embed,
)

if TYPE_CHECKING:
    from githubkit.versions.v2022_11_28.models import (
        PullRequestWebhook,
        WebhookPullRequestClosed,
        WebhookPullRequestConvertedToDraft,
        WebhookPullRequestEdited,
        WebhookPullRequestLocked,
        WebhookPullRequestOpened,
        WebhookPullRequestReadyForReview,
        WebhookPullRequestReopened,
        WebhookPullRequestUnlocked,
    )
    from monalisten.types import (
        PullRequestEvent,
    )

    from app.components.github_integration.emoji import EmojiName

pr_subhooks: SubhookStore[PullRequestEvent] = {}

register_pr_subhook = make_subhook_registrar(pr_subhooks)


def get_pr_emoji(pull_request: PullRequestWebhook) -> EmojiName:
    return "pull_" + (
        "draft" if pull_request.draft
        else "merged" if pull_request.merged
        else pull_request.state
    )  # fmt: skip


@client.on("pull_request")
async def handle_pr_event(event: PullRequestEvent) -> None:
    if subhook := pr_subhooks.get(event.action):
        await subhook(event)


@register_pr_subhook("opened")
async def handle_opened_pr(event: WebhookPullRequestOpened) -> None:
    pr, number = event.pull_request, event.number
    await send_embed(
        event.sender,
        EmbedContent(f"opened PR #{number}", pr.html_url, pr.body),
        Footer("pull_open", f"PR #{number}: {pr.title}"),
        color="green",
    )


@register_pr_subhook("closed")
async def handle_closed_pr(event: WebhookPullRequestClosed) -> None:
    pr, number = event.pull_request, event.number
    action, color = ("merged", "purple") if pr.merged else ("closed", "red")
    await send_embed(
        event.sender,
        EmbedContent(f"{action} PR #{number}", pr.html_url),
        Footer("pull_" + action, f"PR #{number}: {pr.title}"),
        color=color,
    )


@register_pr_subhook("reopened")
async def handle_reopened_pr(event: WebhookPullRequestReopened) -> None:
    pr, number = event.pull_request, event.number
    await send_embed(
        event.sender,
        EmbedContent(f"reopened PR #{number}", pr.html_url),
        Footer("pull_open", f"PR #{number}: {pr.title}"),
        color="green",
    )


@register_pr_subhook("edited")
async def handle_edited_pr(event: WebhookPullRequestEdited) -> None:
    pr, number, changes = event.pull_request, event.number, event.changes

    if pr.created_at > dt.datetime.now(tz=dt.UTC) - dt.timedelta(minutes=15):
        return

    update_notes: list[str] = []
    if changes.title:
        update_notes.append(f'Renamed from "{changes.title.from_}" to "{pr.title}"')
    if changes.body:
        update_notes.append("Updated description")

    match update_notes:
        case [note]:
            content = note
        case [note1, note2]:
            content = f"* {note1}\n*\n {note2}"
        case _:
            return

    assert event.sender
    await send_embed(
        event.sender,
        EmbedContent(f"edited PR #{number}", pr.html_url, content),
        Footer(get_pr_emoji(pr), f"PR #{number}: {pr.title}"),
    )


@register_pr_subhook("converted_to_draft")
async def handle_drafted_pr(event: WebhookPullRequestConvertedToDraft) -> None:
    pr, number = event.pull_request, event.number
    await send_embed(
        event.sender,
        EmbedContent(f"converted PR #{number} to draft", pr.html_url),
        Footer("pull_draft", f"PR #{number}: {pr.title}"),
        color="gray",
    )


@register_pr_subhook("ready_for_review")
async def handle_undrafted_pr(event: WebhookPullRequestReadyForReview) -> None:
    pr, number = event.pull_request, event.number
    await send_embed(
        event.sender,
        EmbedContent(f"marked PR #{number} as ready for review", pr.html_url),
        Footer("pull_open", f"PR #{number}: {pr.title}"),
        color="green",
    )


@register_pr_subhook("locked")
async def handle_locked_pr(event: WebhookPullRequestLocked) -> None:
    pr, number = event.pull_request, event.number
    title = f"locked PR #{number}"
    if reason := pr.active_lock_reason:
        title += f" as {reason}"
    await send_embed(
        event.sender,
        EmbedContent(title, pr.html_url),
        Footer(get_pr_emoji(pr), f"PR #{number}: {pr.title}"),
        color="orange",
    )


@register_pr_subhook("unlocked")
async def handle_unlocked_pr(event: WebhookPullRequestUnlocked) -> None:
    pr, number = event.pull_request, event.number
    await send_embed(
        event.sender,
        EmbedContent(f"unlocked PR #{number}", pr.html_url),
        Footer(get_pr_emoji(pr), f"PR #{number}: {pr.title}"),
    )
