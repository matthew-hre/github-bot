import asyncio
from collections import defaultdict
from itertools import chain
from typing import final

import discord as dc
from discord.ext import tasks

from .cache import entity_cache
from .fmt import entity_message, extract_entities
from app.common.hooks import (
    ItemActions,
    MessageLinker,
    create_delete_hook,
    create_edit_hook,
    remove_view_after_delay,
)
from app.components.github_integration.mentions.resolution import ENTITY_REGEX
from app.components.github_integration.models import Entity
from app.utils import (
    is_dm,
    safe_edit,
    suppress_embeds_after_delay,
    try_dm,
)

IGNORED_MESSAGE_TYPES = frozenset((
    dc.MessageType.thread_created,
    dc.MessageType.channel_name_change,
))

mention_linker = MessageLinker()


@final
class MentionActions(ItemActions):
    linker = mention_linker
    action_singular = "mentioned this entity"
    action_plural = "mentioned these entities"


@tasks.loop(hours=1)
async def update_recent_mentions() -> None:
    mention_linker.free_dangling_links()
    entity_to_message_map = defaultdict[Entity, list[dc.Message]](list)

    # Gather all currently actively mentioned entities
    for msg in mention_linker.refs:
        with safe_edit:
            entities = await extract_entities(msg)
            for entity in entities:
                entity_to_message_map[entity].append(msg)

    # Check which entities changed
    for entity in tuple(entity_to_message_map):
        key = (entity.owner, entity.repo_name, entity.number)
        await entity_cache.fetch(key)
        refreshed_entity = await entity_cache.get(key)
        if entity == refreshed_entity:
            entity_to_message_map.pop(entity)

    # Deduplicate remaining messages
    messages_to_update = set(chain.from_iterable(entity_to_message_map.values()))

    for msg in messages_to_update:
        reply = mention_linker.get(msg)
        assert reply is not None

        new_output = await entity_message(msg)

        with safe_edit:
            await reply.edit(
                content=new_output.content, allowed_mentions=dc.AllowedMentions.none()
            )


async def reply_with_entities(message: dc.Message) -> None:
    if message.author.bot or message.type in IGNORED_MESSAGE_TYPES:
        return

    if is_dm(message.author):
        await try_dm(
            message.author,
            "You can only mention entities in the Ghostty server.",
        )
        return

    output = await entity_message(message)
    if not output.item_count:
        return

    sent_message = await message.reply(
        output.content,
        suppress_embeds=True,
        mention_author=False,
        allowed_mentions=dc.AllowedMentions.none(),
        view=MentionActions(message, output.item_count),
    )
    mention_linker.link(message, sent_message)

    coros = [remove_view_after_delay(sent_message)]
    # The suppress is done here (instead of in resolve_repo_signatures) to prevent
    # blocking I/O for 5 seconds. The regex is run again here because (1) modifying the
    # signature of resolve_repo_signatures to accommodate that would make it ugly (2) we
    # can't modify entity_message's signature as the hook system requires it to return a
    # ProcessedMessage.
    if any(m["site"] for m in ENTITY_REGEX.finditer(message.content)):
        coros.append(suppress_embeds_after_delay(message))
    await asyncio.gather(*coros)


entity_mention_delete_hook = create_delete_hook(linker=mention_linker)

entity_mention_edit_hook = create_edit_hook(
    linker=mention_linker,
    message_processor=entity_message,
    interactor=reply_with_entities,
    view_type=MentionActions,
)
