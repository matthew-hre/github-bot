from typing import NamedTuple, TypedDict

import discord as dc
from githubkit.versions.latest.models import SimpleUser
from monalisten import Monalisten

from app.components.github_integration.emoji import EmojiName, emojis
from app.setup import config
from app.utils import truncate

client = Monalisten(
    config.github_webhook_url,
    token=config.github_webhook_secret,
    log_auth_warnings=True,
)


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


async def send_embed(
    actor: SimpleUser,
    content: EmbedContent,
    footer: Footer,
    *,
    color: int | None = None,
) -> None:
    embed = (
        dc.Embed(color=color, **content.dict)
        .set_footer(**footer.dict)
        .set_author(name=actor.login, url=actor.html_url, icon_url=actor.avatar_url)
    )
    await config.webhook_channel.send(embed=embed)
