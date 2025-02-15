from __future__ import annotations

import asyncio
from contextlib import suppress
from textwrap import shorten
from typing import TYPE_CHECKING, Any

import discord

from app.setup import config

from .message_data import MessageData, scrape_message_data
from .webhooks import (
    GuildTextChannel,
    format_or_file,
    get_or_create_webhook,
    move_message_via_webhook,
)

__all__ = (
    "Account",
    "GuildTextChannel",
    "MessageData",
    "format_or_file",
    "get_or_create_webhook",
    "is_dm",
    "is_helper",
    "is_mod",
    "move_message_via_webhook",
    "remove_view_after_timeout",
    "scrape_message_data",
    "try_dm",
)

if TYPE_CHECKING:
    from typing_extensions import TypeIs


type Account = discord.User | discord.Member


def is_dm(account: Account) -> TypeIs[discord.User]:
    return not isinstance(account, discord.Member)


def is_mod(member: discord.Member) -> bool:
    return member.get_role(config.MOD_ROLE_ID) is not None


def is_helper(member: discord.Member) -> bool:
    return member.get_role(config.HELPER_ROLE_ID) is not None


async def try_dm(account: Account, content: str, **extras: Any) -> None:
    if account.bot:
        return
    try:
        await account.send(content, **extras)
    except discord.Forbidden:
        print(f"Failed to DM {account} with: {shorten(content, width=50)}")


async def remove_view_after_timeout(
    message: discord.Message,
    timeout: float = 30.0,  # noqa: ASYNC109
) -> None:
    await asyncio.sleep(timeout)
    with suppress(discord.NotFound, discord.HTTPException):
        await message.edit(view=None)
