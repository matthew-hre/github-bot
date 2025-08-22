from __future__ import annotations

import sys
from functools import cached_property
from typing import Any

import discord as dc
from discord.ext import commands
from githubkit import GitHub
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def cache_channel[T](field: str, _: type[T]) -> cached_property[T]:
    @cached_property
    def prop(self: Config) -> Any:
        return bot.get_channel(self.model_dump()[field])

    return prop


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOT_", env_file=".env", enable_decoding=False
    )

    token: str

    github_org: str
    github_repos: dict[str, str]
    github_token: str
    github_webhook_url: str
    github_webhook_secret: str | None = None

    accept_invite_url: str
    sentry_dsn: str | None = None

    help_channel_tag_ids: dict[str, int]

    help_channel_id: int
    log_channel_id: int
    media_channel_id: int
    showcase_channel_id: int
    webhook_channel_id: int

    mod_role_id: int
    helper_role_id: int

    @field_validator("github_repos", mode="before")
    @classmethod
    def parse_repos(cls, value: str) -> dict[str, str]:
        return dict(val.split(":") for val in value.split(","))

    @field_validator("help_channel_tag_ids", mode="before")
    @classmethod
    def parse_tag_ids(cls, value: str) -> dict[str, int]:
        return {
            name: int(id_)
            for name, id_ in (pair.split(":") for pair in value.split(","))
        }

    log_channel = cache_channel("log_channel_id", dc.TextChannel)
    help_channel = cache_channel("help_channel_id", dc.ForumChannel)
    webhook_channel = cache_channel("webhook_channel_id", dc.TextChannel)


if "pytest" in sys.modules:
    Config.model_config["env_file"] = ".env.example"

# https://github.com/pydantic/pydantic-settings/issues/201
config = Config()  # pyright: ignore [reportCallIssue]

intents = dc.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    intents=intents,
    allowed_mentions=dc.AllowedMentions(everyone=False, roles=False),
)

gh = GitHub(config.github_token)
