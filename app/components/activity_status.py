from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, final, override

from discord import Activity, ActivityType, CustomActivity
from discord.ext import commands, tasks

if TYPE_CHECKING:
    from app.bot import GhosttyBot

STATUSES = (
    Activity(type=ActivityType.watching, name="over the Ghostty server 👻"),
    CustomActivity(name="Haunting your threads 🧵"),
    Activity(type=ActivityType.watching, name="posts in #showcase"),
    Activity(type=ActivityType.watching, name="over #help"),
    Activity(type=ActivityType.listening, name="your complaints"),
    Activity(type=ActivityType.playing, name="with my config file"),
    Activity(type=ActivityType.competing, name="the terminal game"),
)


@final
class ActivityStatus(commands.Cog):
    def __init__(self, bot: GhosttyBot) -> None:
        self.bot = bot

        self.randomize_activity_status.start()

    @override
    async def cog_unload(self) -> None:
        self.randomize_activity_status.cancel()

    @tasks.loop(hours=2)
    async def randomize_activity_status(self) -> None:
        await self.bot.change_presence(activity=secrets.choice(STATUSES))

    @randomize_activity_status.before_loop
    async def before_randomize_activity_satatus(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: GhosttyBot) -> None:
    await bot.add_cog(ActivityStatus(bot))
