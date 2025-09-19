from __future__ import annotations

from typing import TYPE_CHECKING, Literal, NamedTuple, TypedDict

import discord as dc
import sentry_sdk
from loguru import logger
from monalisten import Monalisten

from app.components.github_integration.models import GitHubUser
from app.config import config
from app.errors import handle_error
from app.utils import truncate

if TYPE_CHECKING:
    from githubkit.versions.latest.models import SimpleUser
    from monalisten import AuthIssue, Error

    from app.bot import EmojiName, GhosttyBot
    from app.config import WebhookFeedType

type EmbedColor = Literal["green", "red", "purple", "gray", "orange", "blue"]

EMBED_COLORS: dict[EmbedColor, int] = {
    "green": 0x3FB950,
    "purple": 0xAB7DF8,
    "red": 0xF85149,
    "gray": 0x9198A1,
    "orange": 0xEDB74A,
    "blue": 0x4C8CED,
}

client = Monalisten(
    config.github_webhook_url.get_secret_value(),
    token=config.github_webhook_secret.get_secret_value()
    if config.github_webhook_secret
    else None,
)


@client.internal.error
async def forward_error(error: Error) -> None:
    error.exc.add_note(f"payload: {error.payload}")
    sentry_sdk.set_context("payload", error.payload or {})  # pyright: ignore[reportArgumentType]
    handle_error(error.exc)


@client.internal.auth_issue
async def show_issue(issue: AuthIssue) -> None:
    guid = issue.payload.get("x-github-delivery", "<missing-guid>")
    logger.warning("token {} in event {}: {}", issue.kind.value, guid, issue.payload)


@client.internal.ready
async def ready() -> None:
    logger.info("monalisten client ready")


class EmbedContentArgs(TypedDict, total=False):
    title: str
    url: str
    description: str | None


class EmbedContent(NamedTuple):
    title: str
    url: str
    body: str | None = None

    @property
    def dict(self) -> EmbedContentArgs:
        args: EmbedContentArgs = {"title": self.title, "url": self.url}
        if self.body:
            args["description"] = truncate(self.body, 500)
        return args


class Footer(NamedTuple):
    icon: EmojiName
    text: str

    def dict(self, bot: GhosttyBot) -> dict[str, str | None]:
        return {
            "text": self.text,
            "icon_url": getattr(bot.ghostty_emojis[self.icon], "url", None),
        }


async def send_embed(  # noqa: PLR0913
    bot: GhosttyBot,
    actor: SimpleUser,
    content: EmbedContent,
    footer: Footer,
    *,
    color: EmbedColor | None = None,
    feed_type: WebhookFeedType = "main",
) -> None:
    author = GitHubUser(**actor.model_dump())
    embed = (
        dc.Embed(color=color and EMBED_COLORS.get(color), **content.dict)
        .set_footer(**footer.dict(bot))
        .set_author(**author.model_dump())
    )
    await bot.webhook_channels[feed_type].send(embed=embed)
