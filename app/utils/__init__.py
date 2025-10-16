from __future__ import annotations

import asyncio
import re
import subprocess
from contextlib import suppress
from io import BytesIO
from textwrap import shorten
from typing import TYPE_CHECKING, Any, TypeIs

import discord as dc
from loguru import logger

from .message_data import MAX_ATTACHMENT_SIZE, ExtensibleMessage, MessageData, get_files

__all__ = (
    "MAX_ATTACHMENT_SIZE",
    "Account",
    "ExtensibleMessage",
    "MessageData",
    "aenumerate",
    "dynamic_timestamp",
    "escape_special",
    "format_diff_note",
    "format_or_file",
    "get_files",
    "is_dm",
    "is_mod",
    "pretty_print_account",
    "safe_edit",
    "suppress_embeds_after_delay",
    "truncate",
    "try_dm",
)

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import AsyncGenerator, AsyncIterable, Callable, Iterable

_INVITE_LINK_REGEX = re.compile(r"\b(?:https?://)?(discord\.gg/[^\s]+)\b")
_ORDERED_LIST_REGEX = re.compile(r"^(\d+)\. (.*)")

type Account = dc.User | dc.Member
# Not a PEP 695 type alias because of runtime isinstance() checks
GuildTextChannel = dc.TextChannel | dc.Thread

safe_edit = suppress(dc.NotFound, dc.HTTPException)


def truncate(s: str, length: int, *, suffix: str = "…") -> str:
    if len(s) <= length:
        return s
    return s[: length - len(suffix)] + suffix


def dynamic_timestamp(dt: dt.datetime, fmt: str | None = None) -> str:
    fmt = f":{fmt}" if fmt is not None else ""
    return f"<t:{int(dt.timestamp())}{fmt}>"


def is_dm(account: Account) -> TypeIs[dc.User]:
    return not isinstance(account, dc.Member)


def is_mod(member: dc.Member) -> bool:
    # Note: is_mod is only used by linker.py for UI interactions.
    # For this minimal bot, all members are considered mod for button interactions.
    return True


async def try_dm(account: Account, content: str, **extras: Any) -> None:
    if account.bot:
        logger.warning(
            "attempted to DM {}, who is a bot", pretty_print_account(account)
        )
        return
    try:
        await account.send(content, **extras)
    except dc.Forbidden:
        logger.error("failed to DM {} with: {}", account, shorten(content, width=50))


async def aenumerate[T](
    it: AsyncIterable[T], start: int = 0
) -> AsyncGenerator[tuple[int, T]]:
    i = start
    async for x in it:
        yield i, x
        i += 1


def escape_special(content: str) -> str:
    """
    Escape all text that Discord considers to be special.

    Consider adding the following kwargs to `send()`-like functions too:
        suppress_embeds=True,
        allowed_mentions=dc.AllowedMentions.none(),
    """
    escaped = dc.utils.escape_mentions(content)
    escaped = dc.utils.escape_markdown(escaped)
    # escape_mentions() doesn't deal with anything other than username mentions.
    escaped = escaped.replace("<", r"\<").replace(">", r"\>")
    # Invite links are not embeds and are hence not suppressed by that flag.
    escaped = _INVITE_LINK_REGEX.sub(r"<https://\g<1>>", escaped)
    # escape_markdown() doesn't deal with ordered lists.
    return "\n".join(
        _ORDERED_LIST_REGEX.sub(r"\g<1>\. \g<2>", line) for line in escaped.splitlines()
    )


async def suppress_embeds_after_delay(message: dc.Message, delay: float = 5.0) -> None:
    logger.trace("waiting {}s to suppress embeds of {}", delay, message)
    await asyncio.sleep(delay)
    with safe_edit:
        logger.debug("suppressing embeds of {}", message)
        await message.edit(suppress=True)


def format_diff_note(additions: int, deletions: int, changed_files: int) -> str | None:
    if not (changed_files and (additions or deletions)):
        return None  # Diff size unavailable
    return f"diff size: `+{additions}` `-{deletions}` ({changed_files} files changed)"


def format_or_file(
    message: str,
    *,
    template: str | None = None,
    transform: Callable[[str], str] | None = None,
) -> tuple[str, dc.File | None]:
    if template is None:
        template = "{}"

    full_message = template.format(message)
    if transform is not None:
        full_message = transform(full_message)

    if len(full_message) > 2000:
        return template.format(""), dc.File(
            BytesIO(message.encode()), filename="content.md"
        )
    return full_message, None


async def async_process_check_output(program: str, *args: str, **kwargs: Any) -> str:
    if "stdout" in kwargs:
        msg = "stdout argument not allowed, it will be overridden."
        raise ValueError(msg)
    proc = await asyncio.create_subprocess_exec(
        program, *args, stdout=subprocess.PIPE, **kwargs
    )
    assert proc.stdout is not None  # set to PIPE above
    if rc := await proc.wait():
        raise subprocess.CalledProcessError(
            returncode=rc,
            cmd=[program, *args],
            output=await proc.stdout.read(),
            stderr=proc.stderr and await proc.stderr.read(),
        )
    return (await proc.stdout.read()).decode()


def pretty_print_account(user: Account) -> str:
    return f"<{user.name} - {user.id}>"
