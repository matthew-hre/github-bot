import datetime as dt
from io import BytesIO

import discord
from zig_codeblocks import (
    DEFAULT_THEME,
    extract_codeblocks,
    highlight_zig_code,
    process_markdown,
)

from app.utils import is_dm, is_mod, remove_view_after_timeout

MAX_CONTENT = 51_200  # 50 KiB
MAX_ZIG_FILE_SIZE = 8_388_608  # 8 MiB
THEME = DEFAULT_THEME.copy()
THEME.comments = None

message_to_codeblocks: dict[discord.Message, discord.Message] = {}
frozen_messages = set[discord.Message]()


class ZigCodeblockActions(discord.ui.View):
    def __init__(self, message: discord.Message) -> None:
        super().__init__()
        self._message = message

    @discord.ui.button(
        label="Dismiss",
        emoji="❌",
        style=discord.ButtonStyle.gray,
    )
    async def dismiss(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ) -> None:
        assert not is_dm(interaction.user)
        if interaction.user.id == self._message.author.id or is_mod(interaction.user):
            assert interaction.message
            await interaction.message.delete()
            return

        await interaction.response.send_message(
            "You can't dismiss this message.", ephemeral=True
        )

    @discord.ui.button(
        label="Freeze",
        emoji="❄️",
        style=discord.ButtonStyle.gray,
    )
    async def freeze(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        assert not is_dm(interaction.user)
        if interaction.user.id == self._message.author.id or is_mod(interaction.user):
            frozen_messages.add(self._message)
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                "Message frozen. I will no longer react to"
                " what happens to your original message.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "You can't freeze this message.", ephemeral=True
            )


async def _prepare_reply(
    message: discord.Message,
) -> tuple[str, list[discord.File]]:
    attachments: list[discord.File] = []
    for att in message.attachments:
        if not att.filename.endswith(".zig") or att.size > MAX_ZIG_FILE_SIZE:
            continue
        content = (await att.read())[:MAX_CONTENT]
        if content.count(b"\n") <= 5 and len(content) <= 1900:
            message.content = f"```zig\n{content.decode()}```\n{message.content}"
            continue
        attachments.append(
            discord.File(
                BytesIO(highlight_zig_code(content, THEME).encode()),
                att.filename + ".ansi",
            )
        )

    codeblocks = list(extract_codeblocks(message.content))
    if codeblocks and any(block.lang == "zig" for block in codeblocks):
        zig_code = process_markdown(message.content, THEME, only_code=True)
        if len(zig_code) <= 2000:
            return zig_code, attachments
    elif attachments:
        return 'Click "View whole file" to see the highlighting.', attachments
    return "", []


async def check_for_zig_code(message: discord.Message) -> None:
    content, files = await _prepare_reply(message)
    if not (content or files):
        return
    reply = await message.reply(
        content,
        view=ZigCodeblockActions(message),
        files=files,
        mention_author=False,
    )
    message_to_codeblocks[message] = reply
    await remove_view_after_timeout(reply)


async def zig_codeblock_edit_handler(
    before: discord.Message, after: discord.Message
) -> None:
    if before.content == after.content and before.attachments == after.attachments:
        return

    old_content, old_files = await _prepare_reply(before)
    new_content, new_files = await _prepare_reply(after)
    if old_content == new_content and old_files == new_files:
        return

    if (reply := message_to_codeblocks.get(before)) is None:
        if not (old_content or before in frozen_messages):
            # There was no code before, so treat this as a new message.
            # Note: No new attachments can appear, their count can only decrease.
            await check_for_zig_code(after)
        # The message was removed from the M2C map at some point
        return

    if not (new_content or new_files or before in frozen_messages):
        # All code was edited out
        del message_to_codeblocks[before]
        await reply.delete()
        return

    # If the message was edited (or created, if never edited) more than 24 hours ago,
    # stop reacting to it and remove its M2C entry.
    last_updated = dt.datetime.now(tz=dt.UTC) - (reply.edited_at or reply.created_at)
    if last_updated > dt.timedelta(hours=24):
        frozen_messages.discard(before)
        del message_to_codeblocks[before]
        return

    if before in frozen_messages:
        return

    await reply.edit(
        content=new_content,
        view=ZigCodeblockActions(after),
        attachments=new_files,
        allowed_mentions=discord.AllowedMentions.none(),
    )
    await remove_view_after_timeout(reply)


def _unlink_original_message(message: discord.Message) -> None:
    original_message = next(
        (msg for msg, reply in message_to_codeblocks.items() if reply == message),
        None,
    )
    if original_message is not None:
        frozen_messages.discard(original_message)
        del message_to_codeblocks[original_message]


async def zig_codeblock_delete_handler(message: discord.Message) -> None:
    if message.author.bot:
        _unlink_original_message(message)
    if not (
        (reply := message_to_codeblocks.get(message)) is None
        or message in frozen_messages
    ):
        await reply.delete()
