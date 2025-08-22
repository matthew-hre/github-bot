from typing import Literal, cast, get_args

import discord as dc

from app.common.message_moving import get_ghostty_guild
from app.setup import config

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

emojis: dict[EmojiName, dc.Emoji] = {}


async def load_emojis() -> None:
    valid_emoji_names = frozenset(get_args(EmojiName))

    for emoji in get_ghostty_guild().emojis:
        if emoji.name in valid_emoji_names:
            emojis[cast("EmojiName", emoji.name)] = emoji

    if missing_emojis := valid_emoji_names - emojis.keys():
        await config.log_channel.send(
            "Failed to load the following emojis: " + ", ".join(missing_emojis)
        )
