from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, NamedTuple

import discord

if TYPE_CHECKING:
    import datetime as dt

MAX_ATTACHMENT_SIZE = 67_108_864  # 64 MiB


class MessageData(NamedTuple):
    content: str
    channel: discord.abc.MessageableChannel
    created_at: dt.datetime
    edited_at: dt.datetime | None
    attachments: list[discord.File]
    skipped_attachments: int
    reactions: list[discord.Reaction]


async def scrape_message_data(message: discord.Message) -> MessageData:
    return MessageData(
        message.content,
        message.channel,
        message.created_at,
        message.edited_at,
        *await _get_attachments(message),
        message.reactions,
    )


async def _get_attachments(message: discord.Message) -> tuple[list[discord.File], int]:
    if not message.attachments:
        return [], 0

    attachments: list[discord.File] = []
    skipped_attachments = 0
    for attachment in message.attachments:
        if attachment.size > MAX_ATTACHMENT_SIZE:
            skipped_attachments += 1
            continue

        fp = BytesIO(await attachment.read())
        attachments.append(discord.File(fp, filename=attachment.filename))

    return attachments, skipped_attachments
