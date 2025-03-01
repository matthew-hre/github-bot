import secrets

from discord import Activity, ActivityType, CustomActivity
from discord.ext import tasks

from app.setup import bot

STATUSES = (
    Activity(type=ActivityType.watching, name="over the Ghostty server 👻"),
    CustomActivity(name="Haunting your threads 🧵"),
    Activity(type=ActivityType.watching, name="posts in #showcase"),
    Activity(type=ActivityType.watching, name="over #help"),
    Activity(type=ActivityType.listening, name="your complaints"),
    Activity(type=ActivityType.playing, name="with my config file"),
    Activity(type=ActivityType.competing, name="the terminal game"),
)


@tasks.loop(hours=2)
async def randomize_activity_status() -> None:
    await bot.change_presence(activity=secrets.choice(STATUSES))
