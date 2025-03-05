from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from .fetching import get_comments
from app.components.entity_mentions.fmt import get_entity_emoji
from app.utils import DeleteMessage, MessageLinker, remove_view_after_timeout

if TYPE_CHECKING:
    from app.components.entity_mentions.models import Comment


comment_linker = MessageLinker()


class DeleteMention(DeleteMessage):
    linker = comment_linker
    action_singular = "linked this comment"
    action_plural = "linked these comments"


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
    if message.author.bot:
        return
    embeds = [
        comment_to_embed(comment) async for comment in get_comments(message.content)
    ]
    if not embeds:
        return
    if len(embeds) > 10:
        omitted = len(embeds) - 10
        note = f"{omitted} comment{'s were' if omitted > 1 else ' was'} omitted"
        embeds = embeds[:10]
    else:
        note = None
    sent_message = await message.reply(
        content=note,
        embeds=embeds,
        mention_author=False,
        view=DeleteMention(message, len(embeds)),
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
