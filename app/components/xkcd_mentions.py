from __future__ import annotations

import asyncio
import datetime as dt
import re
from typing import TYPE_CHECKING, NamedTuple, final, override

import discord as dc
import httpx
from discord.ext import commands
from pydantic import BaseModel, Field

from app.common.cache import TTRCache
from app.common.linker import (
    ItemActions,
    MessageLinker,
    ProcessedMessage,
    remove_view_after_delay,
)

if TYPE_CHECKING:
    from app.bot import GhosttyBot

type XKCDResult = XKCD | UnknownXKCD | XKCDFetchFailed

XKCD_REGEX = re.compile(r"\bxkcd#(\d+)", re.IGNORECASE)


class XKCD(BaseModel):
    comic_id: int = Field(alias="num")
    day: int
    month: int
    year: int
    img: str
    title: str
    alt: str

    @property
    def url(self) -> str:
        return f"https://xkcd.com/{self.comic_id}"


class UnknownXKCD(NamedTuple):
    comic_id: int


class XKCDFetchFailed(NamedTuple):
    comic_id: int


class XKCDMentionCache(TTRCache[int, XKCDResult]):
    @override
    async def fetch(self, key: int) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"https://xkcd.com/{key}/info.0.json")
        if resp.is_success:
            self[key] = XKCD(**resp.json())
        else:
            self[key] = (
                UnknownXKCD(key) if resp.status_code == 404 else XKCDFetchFailed(key)
            )

    @override
    async def get(self, key: int) -> XKCDResult:
        if xkcd_result := await super().get(key):
            return xkcd_result
        msg = "fetch always sets the key so this should not be reachable"
        raise AssertionError(msg)


@final
class XKCDActions(ItemActions):
    action_singular = "linked this xkcd comic"
    action_plural = "linked these xkcd comics"


@final
class XKCDMentions(commands.Cog):
    def __init__(self, bot: GhosttyBot) -> None:
        self.bot = bot
        self.linker = MessageLinker()
        XKCDActions.linker = self.linker
        self.cache = XKCDMentionCache(hours=12)

    @staticmethod
    def get_embed(xkcd: XKCDResult) -> dc.Embed:
        match xkcd:
            case XKCD():
                date = dt.datetime(
                    day=xkcd.day, month=xkcd.month, year=xkcd.year, tzinfo=dt.UTC
                )
                return (
                    dc.Embed(title=xkcd.title, url=xkcd.url)
                    .set_image(url=xkcd.img)
                    .set_footer(text=f"{xkcd.alt} • {date:%B %-d, %Y}")
                )
            case UnknownXKCD(comic_id):
                return dc.Embed(color=dc.Color.red()).set_footer(
                    text=f"xkcd #{comic_id} does not exist"
                )
            case XKCDFetchFailed(comic_id):
                return dc.Embed(color=dc.Color.red()).set_footer(
                    text=f"Unable to fetch xkcd #{comic_id}"
                )

    async def process(self, message: dc.Message) -> ProcessedMessage:
        matches = dict.fromkeys(m[1] for m in XKCD_REGEX.finditer(message.content))
        xkcds = await asyncio.gather(*(self.cache.get(int(m)) for m in matches))
        embeds = list(map(self.get_embed, xkcds))
        if len(embeds) > 10:
            omitted = dc.Embed(color=dc.Color.orange()).set_footer(
                text=f"{len(embeds) - 9} xkcd comics were omitted"
            )
            embeds = [*embeds[:9], omitted]
        return ProcessedMessage(embeds=embeds, item_count=len(embeds))

    @commands.Cog.listener("on_message")
    async def handle_mentions(self, message: dc.Message) -> None:
        if message.author.bot:
            return
        output = await self.process(message)
        if output.item_count < 1:
            return
        try:
            sent_message = await message.reply(
                embeds=output.embeds,
                mention_author=False,
                view=XKCDActions(message, output.item_count),
            )
        except dc.HTTPException:
            return
        self.linker.link(message, sent_message)
        await remove_view_after_delay(sent_message)

    @commands.Cog.listener()
    async def on_message_delete(self, message: dc.Message) -> None:
        await self.linker.delete(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: dc.Message, after: dc.Message) -> None:
        await self.linker.edit(
            before,
            after,
            message_processor=self.process,
            interactor=self.handle_mentions,
            view_type=XKCDActions,
        )


async def setup(bot: GhosttyBot) -> None:
    await bot.add_cog(XKCDMentions(bot))
