from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, cast

from app.components.github_integration.models import GitHubUser
from app.components.github_integration.webhooks.core import (
    EmbedContent,
    Footer,
    SubhookStore,
    client,
    make_subhook_registrar,
    reraise_with_payload,
    send_embed,
)

if TYPE_CHECKING:
    from githubkit.versions.latest.models import (
        DiscussionPropCategory,
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
    title: str
    number: int
    html_url: str
    category: DiscussionPropCategory
    answer_html_url: str | None
    state: Literal["open", "closed", "locked", "converting", "transferring"]


def discussion_footer(
    discussion: DiscussionLike, *, emoji: EmojiName | None = None
) -> Footer:
    emoji = emoji or (
        "discussion_answered"
        if discussion.answer_html_url or discussion.state == "closed"
        else "discussion"
    )
    return Footer(emoji, f"Discussion #{discussion.number}: {discussion.title}")


def discussion_embed_content(
    discussion: DiscussionLike, action: str, body: str | None = None
) -> EmbedContent:
    return EmbedContent(
        f"{action} discussion #{discussion.number} in {discussion.category.name}",
        discussion.html_url,
        body,
    )


@client.on("discussion")
async def handle_discussion_event(event: DiscussionEvent) -> None:
    if subhook := discussion_subhooks.get(event.action):
        with reraise_with_payload(event):
            await subhook(event)


@register_discussion_subhook("created")
async def handle_created_discussion(event: WebhookDiscussionCreated) -> None:
    discussion = event.discussion
    await send_embed(
        event.sender,
        discussion_embed_content(discussion, "opened", discussion.body),
        discussion_footer(discussion, emoji="discussion"),
        color="gray",
        feed_type="discussions",
    )


@register_discussion_subhook("closed")
async def handle_closed_discussion(event: WebhookDiscussionClosed) -> None:
    discussion = event.discussion
    await send_embed(
        event.sender,
        discussion_embed_content(discussion, "closed"),
        discussion_footer(discussion, emoji="discussion_answered"),
        color="purple",
        feed_type="discussions",
    )


@register_discussion_subhook("reopened")
async def handle_reopened_discussion(event: WebhookDiscussionReopened) -> None:
    discussion = event.discussion
    emoji = "discussion_answered" if discussion.answer_html_url else "discussion"
    await send_embed(
        event.sender,
        discussion_embed_content(discussion, "reopened"),
        discussion_footer(discussion, emoji=emoji),
        color="gray",
        feed_type="discussions",
    )


@register_discussion_subhook("answered")
async def handle_answered_discussion(event: WebhookDiscussionAnswered) -> None:
    discussion, answer = event.discussion, event.answer
    accepting_user = GitHubUser(**event.sender.model_dump())
    await send_embed(
        cast("SimpleUser", answer.user),
        discussion_embed_content(
            discussion,
            "answered",
            f"-# Answer chosen by {accepting_user.hyperlink}\n{answer.body}",
        ),
        discussion_footer(discussion, emoji="discussion_answered"),
        color="green",
        feed_type="discussions",
    )


@register_discussion_subhook("unanswered")
async def handle_unanswered_discussion(event: WebhookDiscussionUnanswered) -> None:
    discussion = event.discussion
    emoji = "discussion_answered" if discussion.state == "closed" else "discussion"
    await send_embed(
        event.sender or cast("SimpleUser", GitHubUser.default()),
        discussion_embed_content(discussion, "unmarked an answer in"),
        discussion_footer(discussion, emoji=emoji),
        color="red",
        feed_type="discussions",
    )


@register_discussion_subhook("locked")
async def handle_locked_discussion(event: WebhookDiscussionLocked) -> None:
    discussion = event.discussion
    emoji = "discussion_answered" if discussion.answer_html_url else "discussion"
    await send_embed(
        event.sender,
        discussion_embed_content(discussion, "locked"),
        discussion_footer(discussion, emoji=emoji),
        color="orange",
        feed_type="discussions",
    )


@register_discussion_subhook("unlocked")
async def handle_unlocked_discussion(event: WebhookDiscussionUnlocked) -> None:
    discussion = event.discussion
    await send_embed(
        event.sender,
        discussion_embed_content(discussion, "unlocked"),
        discussion_footer(discussion),
        color="blue",
        feed_type="discussions",
    )


@register_discussion_subhook("pinned")
async def handle_pinned_discussion(event: WebhookDiscussionPinned) -> None:
    discussion = event.discussion
    await send_embed(
        event.sender,
        discussion_embed_content(discussion, "pinned"),
        discussion_footer(discussion),
        color="blue",
        feed_type="discussions",
    )


@register_discussion_subhook("unpinned")
async def handle_unpinned_discussion(event: WebhookDiscussionUnpinned) -> None:
    discussion = event.discussion
    await send_embed(
        event.sender,
        discussion_embed_content(discussion, "unpinned"),
        discussion_footer(discussion),
        color="orange",
        feed_type="discussions",
    )
