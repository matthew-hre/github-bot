import sys

from githubkit import GitHub
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# This maps valid special repo prefixes to appropriate repo names. Since the
# actual repo names are also valid prefixes, they can be viewed as self-mapping aliases.
REPO_ALIASES = {
    "ghostty": "ghostty",
    "main": "ghostty",
    "web": "website",
    "website": "website",
    "discord-bot": "discord-bot",
    "bot": "discord-bot",
    "bobr": "discord-bot",
    "simul": "3504-term-project-simul",
    "3504-term-project-simul": "3504-term-project-simul"
}


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BOT_", env_file=".env", enable_decoding=False
    )

    token: SecretStr

    github_org: str
    github_token: SecretStr
    github_default_repo: str = "3504-term-project-simul"

    guild_id: int | None = None
    log_channel_id: int


# https://github.com/pydantic/pydantic-settings/issues/201
config = Config()  # pyright: ignore[reportCallIssue]
gh = GitHub(config.github_token.get_secret_value())
