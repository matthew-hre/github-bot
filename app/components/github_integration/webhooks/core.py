from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple, TypedDict

import discord as dc
from githubkit.versions.latest.models import SimpleUser
from monalisten import Monalisten

from app.components.github_integration.emoji import EmojiName, emojis
from app.components.github_integration.models import GitHubUser
from app.setup import config
from app.utils import truncate

if TYPE_CHECKING:
    from monalisten import AuthIssue
client = Monalisten(config.github_webhook_url, token=config.github_webhook_secret)


@client.on_internal("auth_issue")
async def show_issue(issue: AuthIssue, event_data: dict[str, Any]) -> None:
    guid = event_data.get("x-github-delivery", "<missing-guid>")
    print(f"Token {issue.value} in event {guid}: {event_data}")


@client.on_internal("ready")
async def ready() -> None:
    print("Monalisten client ready!")


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
    author = GitHubUser(**actor.model_dump())
    embed = (
        dc.Embed(color=color, **content.dict)
        .set_footer(**footer.dict)
        .set_author(**author.model_dump())
    )
    await config.webhook_channel.send(embed=embed)
