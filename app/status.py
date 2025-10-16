from __future__ import annotations

import datetime as dt
import subprocess
from contextlib import suppress
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast, final

from githubkit import TokenAuthStrategy
from githubkit.exception import RequestFailed

from app.config import config, gh
from app.utils import async_process_check_output, dynamic_timestamp

if TYPE_CHECKING:
    pass

STATUS_MESSAGE_TEMPLATE = """
### Commit
{commit}
### Uptime
* Launch time: {launch_time}
* Last login time: {last_login_time}
### GitHub status
* Auth: {gh.auth}
* API: {gh.api}
### Sitemap
* Last refresh: {last_sitemap_refresh}
"""


@final
class BotStatus:
    launch_time: dt.datetime
    last_login_time: dt.datetime | None = None
    last_sitemap_refresh: dt.datetime | None = None
    commit_url: str | None = None
    # app.components.github_integration.commits.Commits will set this when the bot is
    # ready, assuming it's loaded.
    commit_data: str | None = None

    def __init__(self) -> None:
        self.launch_time = dt.datetime.now(tz=dt.UTC)
        self._commit_hash = None

    async def load_git_data(self) -> None:
        try:
            self._commit_hash = (
                await async_process_check_output("git", "rev-parse", "HEAD")
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return
        if not self._commit_hash:
            return

        remote = "https://github.com/ghostty-org/discord-bot"
        with suppress(subprocess.CalledProcessError, FileNotFoundError):
            if found_remote := (
                (await async_process_check_output("git", "remote", "get-url", "origin"))
                .strip()
                .replace("ssh://git@", "https://", 1)
                .removesuffix(".git")
            ):
                remote = found_remote

        self.commit_url = f"{remote}/commit/{self._commit_hash}"

    @property
    def commit(self) -> str:
        if self.commit_data:
            return self.commit_data
        if self._commit_hash and self.commit_url:
            return f"[`{self._commit_hash}`](<{self.commit_url}>)"
        return "Unknown"

    @property
    def initialized(self) -> bool:
        return all((
            self.last_login_time,
            self.last_sitemap_refresh,
        ))

    @staticmethod
    async def _get_github_data() -> SimpleNamespace:
        match gh.auth:
            case TokenAuthStrategy(token) if token.startswith(("gh", "github")):
                correct_token = True
            case _:
                correct_token = False
        try:
            resp = await gh.rest.users.async_get_authenticated()
            api_ok = resp.status_code == 200
        except RequestFailed:
            api_ok = False
        return SimpleNamespace(
            auth="✅" if correct_token else "❌",
            api="✅" if api_ok else "❌",
        )

    async def export(self) -> dict[str, str | SimpleNamespace]:
        """
        Make sure the bot has finished initializing before calling this, using the
        `initialized` property.
        """
        assert self.last_login_time is not None
        assert self.last_sitemap_refresh is not None
        return {
            "commit": self.commit,
            "launch_time": dynamic_timestamp(self.launch_time, "R"),
            "last_login_time": dynamic_timestamp(self.last_login_time, "R"),
            "last_sitemap_refresh": dynamic_timestamp(self.last_sitemap_refresh, "R"),
            "gh": await self._get_github_data(),
        }

    async def status_message(self) -> str:
        if not self.initialized:
            return "The bot has not finished initializing yet; try again shortly."
        return STATUS_MESSAGE_TEMPLATE.format(**(await self.export()))
