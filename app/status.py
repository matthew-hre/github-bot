import datetime as dt
import subprocess
from types import SimpleNamespace
from typing import Any, cast, final

from discord.ext import tasks
from githubkit import TokenAuthStrategy
from githubkit.exception import RequestFailed

from app.config import config, gh
from app.utils import dynamic_timestamp

STATUS_MESSAGE_TEMPLATE = """
### Commit
{commit_hash}
### Uptime
* Launch time: {launch_time}
* Last login time: {last_login_time}
### {help_channel} post scan status
* Last scan: {scan.scanned} scanned, {scan.closed} closed ({scan.time_since})
* Next scan: {scan.time_until_next}
### GitHub status
* Auth: {gh.auth}
* API: {gh.api}
### Sitemap
* Last refresh: {last_sitemap_refresh}
"""


@final
class BotStatus:
    launch_time: dt.datetime
    help_scan_loop: tasks.Loop[Any] | None = None
    last_login_time: dt.datetime | None = None
    last_scan_results: tuple[dt.datetime, int, int] | None = None
    last_sitemap_refresh: dt.datetime | None = None

    def __init__(self) -> None:
        self.launch_time = dt.datetime.now(tz=dt.UTC)

    @property
    def initialized(self) -> bool:
        return all((
            self.last_login_time,
            self.last_sitemap_refresh,
            self.last_scan_results,
        ))

    def _get_scan_data(self) -> SimpleNamespace:
        if not self.help_scan_loop:
            return SimpleNamespace(
                time_since="**disabled**",
                time_until_next="**disabled**",
                scanned=0,
                closed=0,
            )

        next_scan = cast("dt.datetime", self.help_scan_loop.next_iteration)
        assert self.last_scan_results is not None
        last_scan, scanned, closed = self.last_scan_results
        return SimpleNamespace(
            time_since=dynamic_timestamp(last_scan, "R"),
            time_until_next=dynamic_timestamp(next_scan, "R"),
            scanned=scanned,
            closed=closed,
        )

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

    @staticmethod
    def _get_commit_hash() -> str:
        try:
            return (
                subprocess.check_output(["git", "rev-parse", "HEAD"])
                .decode()
                .strip()
                .join("``")
            )
        except subprocess.CalledProcessError:
            return "Unknown"

    async def export(self) -> dict[str, str | SimpleNamespace]:
        """
        Make sure the bot has finished initializing before calling this, using the
        `initialized` property.
        """
        assert self.last_login_time is not None
        assert self.last_sitemap_refresh is not None
        return {
            "commit_hash": self._get_commit_hash(),
            "launch_time": dynamic_timestamp(self.launch_time, "R"),
            "last_login_time": dynamic_timestamp(self.last_login_time, "R"),
            "last_sitemap_refresh": dynamic_timestamp(self.last_sitemap_refresh, "R"),
            "help_channel": f"<#{config.help_channel_id}>",
            "scan": self._get_scan_data(),
            "gh": await self._get_github_data(),
        }

    async def status_message(self) -> str:
        if not self.initialized:
            return "The bot has not finished initializing yet; try again shortly."
        return STATUS_MESSAGE_TEMPLATE.format(**(await self.export()))
