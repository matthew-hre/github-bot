import datetime as dt
import subprocess
from types import SimpleNamespace
from typing import Any, cast, final

from discord.ext import tasks
from githubkit import TokenAuthStrategy
from githubkit.exception import RequestFailed

from app.config import config, gh
from app.utils import dynamic_timestamp


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
                time_since="Disabled",
                time_until_next="Disabled",
                scanned=-1,
                closed=-1,
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

    def _get_github_data(self) -> SimpleNamespace:
        match gh.auth:
            case TokenAuthStrategy(token) if token.startswith(("gh", "github")):
                correct_token = True
            case _:
                correct_token = False
        try:
            resp = gh.rest.users.get_authenticated()
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

    def status_message(self) -> str:
        assert self.last_login_time is not None
        assert self.last_sitemap_refresh is not None
        scan = self._get_scan_data()
        gh_stats = self._get_github_data()
        return f"""
        ### Commit
        {self._get_commit_hash}
        ### Uptime
        * Launch time: {dynamic_timestamp(self.launch_time, "R")}
        * Last login time: {dynamic_timestamp(self.last_login_time, "R")}
        ### <#{config.help_channel_id}> post scan status
        * Last scan: {scan.scanned} scanned, {scan.closed} closed ({scan.time_since})
        * Next scan: {scan.time_until_next}
        ### GitHub status
        * Auth: {gh_stats.auth}
        * API: {gh_stats.api}
        ### Sitemap
        * Last refresh: {dynamic_timestamp(self.last_sitemap_refresh, "R")}
        """
