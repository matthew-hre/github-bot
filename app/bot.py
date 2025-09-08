import asyncio
import datetime as dt
import os
import re
import sys
from typing import TYPE_CHECKING, Any, cast, final, override

import discord as dc
from discord.ext import commands
from loguru import logger

from app.errors import handle_error, interaction_error_handler
from app.status import BotStatus
from app.utils import try_dm

if TYPE_CHECKING:
    from githubkit import GitHub, TokenAuthStrategy

    from app.config import Config, WebhookFeedType


EMOJI_REGEX = re.compile(r"<(a?):(\w+):(\d+)>", re.ASCII)


@final
class GhosttyBot(commands.Bot):
    def __init__(self, config: "Config", gh: "GitHub[TokenAuthStrategy]") -> None:
        intents = dc.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(
            command_prefix=commands.when_mentioned_or("!"),
            intents=intents,
            allowed_mentions=dc.AllowedMentions(everyone=False, roles=False),
        )

        self.tree.on_error = interaction_error_handler
        self.config = config
        self.gh = gh
        self.ghostty_status = BotStatus()
        self.background_tasks = set[asyncio.Task[None]]()

    @override
    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        handle_error(cast("BaseException", sys.exception()))

    @override
    async def setup_hook(self) -> None:
        await asyncio.gather(
            *(
                self.load_extension(ext)
                for ext in (
                    f"app.components.{filename.rstrip('.py')}"
                    for filename in os.listdir("./app/components")  # noqa: PTH208
                    if not filename.startswith("_")
                )
            )
        )

    async def on_ready(self) -> None:
        # Creating a strong reference

        self.ghostty_status.last_login_time = dt.datetime.now(tz=dt.UTC)
        logger.info("logged in as {}", self.user)

    @dc.utils.cached_property
    def ghostty_guild(self) -> dc.Guild:
        if self.config.guild_id and (guild := self.get_guild(self.config.guild_id)):
            return guild
        return self.guilds[0]

    @dc.utils.cached_property
    def log_channel(self) -> dc.TextChannel:
        channel = self.get_channel(self.config.log_channel_id)
        assert isinstance(channel, dc.TextChannel)
        return channel

    @dc.utils.cached_property
    def help_channel(self) -> dc.ForumChannel:
        channel = self.get_channel(self.config.help_channel_id)
        assert isinstance(channel, dc.ForumChannel)
        return channel

    @dc.utils.cached_property
    def webhook_channels(self) -> dict["WebhookFeedType", dc.TextChannel]:
        channels: dict[WebhookFeedType, dc.TextChannel] = {}
        for feed_type, id_ in self.config.webhook_channel_ids.items():
            channel = self.ghostty_guild.get_channel(id_)
            if not isinstance(channel, dc.TextChannel):
                msg = (
                    "expected {} webhook channel to be a text channel"
                    if channel
                    else "failed to find {} webhook channel"
                )
                raise TypeError(msg.format(feed_type))
            channels[feed_type] = channel
        return channels

    @override
    async def on_message(self, message: dc.Message, /) -> None:
        # Ignore our own messages
        if message.author == self.user:
            return

        # Simple test
        if message.guild is None and message.content == "ping":
            await try_dm(message.author, "pong")
            return

        await self.process_commands(message)

    def convert_nitro_emojis(self, content: str, *, force: bool = False) -> str:
        """
        Convert custom emojis to concealed hyperlinks.  Set `force` to True to convert
        emojis in the current guild too.
        """

        def replace_nitro_emoji(match: re.Match[str]) -> str:
            animated, name, id_ = match.groups()
            emoji = self.get_emoji(int(id_))
            if not force and emoji and emoji.guild_id == self.ghostty_guild.id:
                return match[0]

            ext = "gif" if animated else "webp"
            tag = animated and "&animated=true"
            return f"[{name}](<https://cdn.discordapp.com/emojis/{id_}.{ext}?size=48{tag}&name={name}>)"

        return EMOJI_REGEX.sub(replace_nitro_emoji, content)
