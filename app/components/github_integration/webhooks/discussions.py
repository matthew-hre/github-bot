from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, cast

from app.components.github_integration.models import GitHubUser
from app.components.github_integration.webhooks.core import (
    EmbedContent,
    Footer,
    SubhookStore,
    client,
    make_subhook_registrar,
    send_embed,
)

if TYPE_CHECKING:
    from githubkit.versions.latest.models import (
        SimpleUser,
        WebhookDiscussionAnswered,
        WebhookDiscussionClosed,
        WebhookDiscussionCreated,
        WebhookDiscussionLocked,
        WebhookDiscussionPinned,
        WebhookDiscussionReopened,
        WebhookDiscussionUnanswered,
        WebhookDiscussionUnlocked,
        WebhookDiscussionUnpinned,
    )
    from monalisten.types import DiscussionEvent

    from app.components.github_integration.emoji import EmojiName

discussion_subhooks: SubhookStore[DiscussionEvent] = {}

register_discussion_subhook = make_subhook_registrar(discussion_subhooks)


class DiscussionLike(Protocol):
    answer_html_url: str | None
    state: Literal["open", "closed", "locked", "converting", "transferring"]


def get_discussion_emoji(discussion: DiscussionLike) -> EmojiName:
    return (
        "discussion_answered"
        if discussion.answer_html_url or discussion.state == "closed"
        else "discussion"
    )


@client.on("discussion")
async def handle_discussion_event(event: DiscussionEvent) -> None:
    if subhook := discussion_subhooks.get(event.action):
        await subhook(event)


@register_discussion_subhook("created")
async def handle_created_discussion(event: WebhookDiscussionCreated) -> None:
    discussion, number = event.discussion, event.discussion.number
    await send_embed(
        event.sender,
        EmbedContent(
            f"opened discussion #{number} in {discussion.category.name}",
            discussion.html_url,
            discussion.body,
        ),
        Footer("discussion", f"Discussion #{number}: {discussion.title}"),
        color="gray",
    )


@register_discussion_subhook("closed")
async def handle_closed_discussion(event: WebhookDiscussionClosed) -> None:
    discussion, number = event.discussion, event.discussion.number
    await send_embed(
        event.sender,
        EmbedContent(
            f"closed discussion #{number} in {discussion.category.name}",
            discussion.html_url,
        ),
        Footer("discussion_answered", f"Discussion #{number}: {discussion.title}"),
        color="purple",
    )


@register_discussion_subhook("reopened")
async def handle_reopened_discussion(event: WebhookDiscussionReopened) -> None:
    discussion, number = event.discussion, event.discussion.number
    emoji = "discussion_answered" if discussion.answer_html_url else "discussion"
    await send_embed(
        event.sender,
        EmbedContent(
            f"reopened discussion #{number} in {discussion.category.name}",
            discussion.html_url,
        ),
        Footer(emoji, f"Discussion #{number}: {discussion.title}"),
        color="gray",
    )


@register_discussion_subhook("answered")
async def handle_answered_discussion(event: WebhookDiscussionAnswered) -> None:
    discussion, number, answer = event.discussion, event.discussion.number, event.answer
    accepting_user = GitHubUser(**event.sender.model_dump())
    await send_embed(
        cast("SimpleUser", answer.user),
        EmbedContent(
            f"answered discussion #{number} in {discussion.category.name}",
            discussion.html_url,
            f"-# Answer chosen by {accepting_user.hyperlink}\n{answer.body}",
        ),
        Footer("discussion_answered", f"Discussion #{number}: {discussion.title}"),
        color="green",
    )


@register_discussion_subhook("unanswered")
async def handle_unanswered_discussion(event: WebhookDiscussionUnanswered) -> None:
    discussion, number = event.discussion, event.discussion.number
    emoji = "discussion_answered" if discussion.state == "closed" else "discussion"
    await send_embed(
        event.sender or cast("SimpleUser", GitHubUser.default()),
        EmbedContent(
            f"unmarked an answer in discussion #{number} in {discussion.category.name}",
            discussion.html_url,
        ),
        Footer(emoji, f"Discussion #{number}: {discussion.title}"),
        color="red",
    )


@register_discussion_subhook("locked")
async def handle_locked_discussion(event: WebhookDiscussionLocked) -> None:
    discussion, number = event.discussion, event.discussion.number
    emoji = "discussion_answered" if discussion.answer_html_url else "discussion"
    await send_embed(
        event.sender,
        EmbedContent(
            f"locked discussion #{number} in {discussion.category.name}",
            discussion.html_url,
        ),
        Footer(emoji, f"Discussion #{number}: {discussion.title}"),
        color="orange",
    )


@register_discussion_subhook("unlocked")
async def handle_unlocked_discussion(event: WebhookDiscussionUnlocked) -> None:
    discussion, number = event.discussion, event.discussion.number
    await send_embed(
        event.sender,
        EmbedContent(
            f"unlocked discussion #{number} in {discussion.category.name}",
            discussion.html_url,
        ),
        Footer(
            get_discussion_emoji(discussion),
            f"Discussion #{number}: {discussion.title}",
        ),
        color="blue",
    )


@register_discussion_subhook("pinned")
async def handle_pinned_discussion(event: WebhookDiscussionPinned) -> None:
    discussion, number = event.discussion, event.discussion.number
    await send_embed(
        event.sender,
        EmbedContent(
            f"pinned discussion #{number} in {discussion.category.name}",
            discussion.html_url,
        ),
        Footer(
            get_discussion_emoji(discussion),
            f"Discussion #{number}: {discussion.title}",
        ),
        color="blue",
    )


@register_discussion_subhook("unpinned")
async def handle_unpinned_discussion(event: WebhookDiscussionUnpinned) -> None:
    discussion, number = event.discussion, event.discussion.number
    await send_embed(
        event.sender,
        EmbedContent(
            f"unpinned discussion #{number} in {discussion.category.name}",
            discussion.html_url,
        ),
        Footer(
            get_discussion_emoji(discussion),
            f"Discussion #{number}: {discussion.title}",
        ),
        color="orange",
    )
