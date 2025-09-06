from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, NoReturn, TypedDict

import discord as dc
from loguru import logger
from monalisten import Monalisten

from app.components.github_integration.emoji import EmojiName, emojis
from app.components.github_integration.models import GitHubUser
from app.config import config
from app.utils import truncate

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator

    from githubkit.versions.latest.models import SimpleUser
    from monalisten import AuthIssue
    from pydantic import BaseModel
    from pydantic_core import ErrorDetails

    from app.bot import GhosttyBot
    from app.config import WebhookFeedType

type EmbedColor = Literal["green", "red", "purple", "gray", "orange", "blue"]
type SubhookStore[E] = dict[str, Callable[[E], Awaitable[None]]]

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


class Test(Monalisten):
    def __init__(self, source: str, *, token: str | None = None) -> None:
        super().__init__(source, token=token)

    async def on_error(self) -> None:
        @self.on_internal("error")
        async def _(
            event_data: dict[str, Any],
            message: str,
            pydantic_errors: list[ErrorDetails] | None,
        ) -> NoReturn:
            msg = f"{message}\n{event_data}\n{pydantic_errors or []}"
            raise RuntimeError(msg)


@client.on_internal("error")
async def forward_error(
    event_data: dict[str, Any], message: str, pydantic_errors: list[ErrorDetails] | None
) -> None:
    msg = f"{message}\n{event_data}\n{pydantic_errors or []}"
    raise RuntimeError(msg)


@client.on_internal("auth_issue")
async def show_issue(issue: AuthIssue, event_data: dict[str, Any]) -> None:
    guid = event_data.get("x-github-delivery", "<missing-guid>")
    logger.warning("token {} in event {}: {}", issue.value, guid, event_data)


@client.on_internal("ready")
async def ready() -> None:
    logger.info("monalisten client ready")


@contextmanager
def reraise_with_payload(event: BaseModel) -> Generator[None]:
    try:
        yield
    except BaseException as e:
        e.add_note(str(event.model_dump()))
        raise


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

    @property
    def dict(self) -> dict[str, str | None]:
        return {
            "text": self.text,
            "icon_url": emoji.url if (emoji := emojis.get(self.icon)) else None,
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
        .set_footer(**footer.dict)
        .set_author(**author.model_dump())
    )
    await bot.webhook_channels[feed_type].send(embed=embed)


def make_subhook_registrar[H](
    hook_store: dict[str, H],
) -> Callable[[str], Callable[[Any], H]]:
    def register_subhook(action: str) -> Callable[[Any], H]:
        def wrapper(function: Any) -> H:
            hook_store[action] = function
            return function

        return wrapper

    return register_subhook
