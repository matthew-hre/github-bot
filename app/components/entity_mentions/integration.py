from __future__ import annotations

import discord

from .fmt import entity_message
from app.utils import (
    DeleteMessage,
    MessageLinker,
    is_dm,
    remove_view_after_timeout,
    try_dm,
)

IGNORED_MESSAGE_TYPES = frozenset(
    (discord.MessageType.thread_created, discord.MessageType.channel_name_change)
)

mention_linker = MessageLinker()


class DeleteMention(DeleteMessage):
    linker = mention_linker
    action_singular = "mentioned this entity"
    action_plural = "mentioned these entities"


async def reply_with_entities(message: discord.Message) -> None:
    if message.author.bot or message.type in IGNORED_MESSAGE_TYPES:
        return

    if is_dm(message.author):
        await try_dm(
            message.author,
            "You can only mention entities in the Ghostty server.",
        )
        return

    msg_content, entity_count = await entity_message(message)
    if not entity_count:
        return

    sent_message = await message.reply(
        msg_content,
        suppress_embeds=True,
        mention_author=False,
        allowed_mentions=discord.AllowedMentions.none(),
        view=DeleteMention(message, entity_count),
    )
    mention_linker.link(message, sent_message)
    await remove_view_after_timeout(sent_message)


async def entity_mention_delete_handler(message: discord.Message) -> None:
    if message.author.bot:
        mention_linker.unlink_from_reply(message)
    elif replies := mention_linker.get(message):
        for reply in replies:
            await reply.delete()


async def entity_mention_edit_handler(
    before: discord.Message, after: discord.Message
) -> None:
    if before.content == after.content:
        return
    old_entities = await entity_message(before)
    new_entities = await entity_message(after)
    if old_entities == new_entities:
        # Message changed but mentions are the same
        return

    if not (replies := mention_linker.get(before)):
        if not old_entities[1]:
            # There were no mentions before, so treat this as a new message
            await reply_with_entities(after)
        # The message was removed from the M2M map at some point
        return

    reply = replies[0]
    content, count = new_entities
    if not count:
        # All mentions were edited out
        mention_linker.unlink(before)
        await reply.delete()
        return

    if mention_linker.unlink_if_expired(reply):
        return

    await reply.edit(
        content=content,
        suppress=True,
        view=DeleteMention(after, count),
        allowed_mentions=discord.AllowedMentions.none(),
    )
    await remove_view_after_timeout(reply)
