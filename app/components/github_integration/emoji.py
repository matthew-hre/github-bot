from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, cast, get_args

import discord as dc

if TYPE_CHECKING:
    from app.bot import GhosttyBot

EmojiName = Literal[
    "commit",
    "discussion",
    "discussion_answered",
    "issue_closed_completed",
    "issue_closed_unplanned",
    "issue_open",
    "pull_closed",
    "pull_draft",
    "pull_merged",
    "pull_open",
]

_emojis: dict[EmojiName, dc.Emoji] = {}
emojis = MappingProxyType(_emojis)


async def load_emojis(bot: "GhosttyBot") -> None:
    valid_emoji_names = frozenset(get_args(EmojiName))

    for emoji in bot.ghostty_guild.emojis:
        if emoji.name in valid_emoji_names:
            _emojis[cast("EmojiName", emoji.name)] = emoji

    if missing_emojis := valid_emoji_names - _emojis.keys():
        await bot.log_channel.send(
            "Failed to load the following emojis: " + ", ".join(missing_emojis)
        )
