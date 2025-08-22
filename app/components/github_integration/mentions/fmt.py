from __future__ import annotations

import asyncio
from functools import partial
from typing import TYPE_CHECKING

from .cache import Entity, Issue, PullRequest, entity_cache
from .resolution import resolve_entity_signatures
from app.common.hooks import ProcessedMessage
from app.common.message_moving import get_ghostty_guild
from app.components.github_integration.models import Discussion
from app.setup import config
from app.utils import dynamic_timestamp, escape_special, format_diff_note

if TYPE_CHECKING:
    import discord as dc

ENTITY_TEMPLATE = "**{entity.kind} [#{entity.number}](<{entity.html_url}>):** {title}"
EMOJI_NAMES = frozenset({
    "commit",
    "discussion_answered",
    "issue_closed_completed",
    "issue_closed_unplanned",
    "issue_draft",
    "issue_open",
    "pull_closed",
    "pull_draft",
    "pull_merged",
    "pull_open",
})

entity_emojis: dict[str, dc.Emoji] = {}


async def load_emojis() -> None:
    guild = get_ghostty_guild()
    for emoji in guild.emojis:
        if emoji.name in EMOJI_NAMES:
            entity_emojis[emoji.name] = emoji
    if len(entity_emojis) < len(EMOJI_NAMES):
        await config.log_channel.send(
            "Failed to load the following emojis: "
            + ", ".join(EMOJI_NAMES - entity_emojis.keys())
        )


def get_entity_emoji(entity: Entity) -> dc.Emoji | None:
    if isinstance(entity, Issue):
        state = "closed_" if entity.closed else "open"
        if entity.closed:
            state += "completed" if entity.state_reason == "completed" else "unplanned"
        emoji_name = f"issue_{state}"
    elif isinstance(entity, PullRequest):
        emoji_name = "pull_" + (
            "draft" if entity.draft
            else "merged" if entity.merged
            else "closed" if entity.closed
            else "open"
        )  # fmt: skip
    elif isinstance(entity, Discussion):
        emoji_name = "discussion_answered" if entity.answered_by else "issue_draft"
    else:
        msg = f"Unknown entity type: {type(entity)}"
        raise TypeError(msg)

    return entity_emojis.get(emoji_name)


def _format_entity_detail(entity: Entity) -> str:
    if isinstance(entity, Issue):
        if not entity.labels:
            return ""
        if len(entity.labels) > 3:
            labels = entity.labels[:3]
            omission_note = f", and {len(entity.labels) - 3} more"
        else:
            labels, omission_note = entity.labels, ""
        body = f"labels: {', '.join(f'`{label}`' for label in labels)}{omission_note}"
    elif isinstance(entity, PullRequest):
        body = format_diff_note(
            entity.additions, entity.deletions, entity.changed_files
        )
        if body is None:
            return ""  # Diff size unavailable
    elif isinstance(entity, Discussion):
        if not entity.answered_by:
            return ""
        body = f"answered by {entity.answered_by.hyperlink}"
    else:
        msg = f"Unknown entity type: {type(entity)}"
        raise TypeError(msg)
    return f"-# {body}\n"


def _format_mention(entity: Entity) -> str:
    headline = ENTITY_TEMPLATE.format(entity=entity, title=escape_special(entity.title))

    owner, name = entity.owner, entity.repo_name
    fmt_ts = partial(dynamic_timestamp, entity.created_at)
    subtext = (
        f"-# by {entity.user.hyperlink}"
        f" in [`{owner}/{name}`](<https://github.com/{owner}/{name}>)"
        f" on {fmt_ts('D')} ({fmt_ts('R')})\n"
    )
    entity_detail = _format_entity_detail(entity)

    emoji = get_entity_emoji(entity) or "❓"
    return f"{emoji} {headline}\n{subtext}{entity_detail}"


async def extract_entities(message: dc.Message) -> list[Entity]:
    matches = list(dict.fromkeys([r async for r in resolve_entity_signatures(message)]))
    cache_hits = await asyncio.gather(
        *(entity_cache.get(m) for m in matches), return_exceptions=True
    )
    return [entity for entity in cache_hits if not isinstance(entity, BaseException)]


async def entity_message(message: dc.Message) -> ProcessedMessage:
    entities = [_format_mention(entity) for entity in await extract_entities(message)]

    if len("\n".join(entities)) > 2000:
        while len("\n".join(entities)) > 1970:  # Accounting for omission note
            entities.pop()
        entities.append("-# Some mentions were omitted")

    return ProcessedMessage(
        content="\n".join(dict.fromkeys(entities)), item_count=len(entities)
    )
