from io import BytesIO

import discord
from zig_codeblocks import (
    DEFAULT_THEME,
    extract_codeblocks,
    highlight_zig_code,
    process_markdown,
)

from app.utils import is_dm, is_mod

MAX_CONTENT = 51_200  # 50 KiB
MAX_ZIG_FILE_SIZE = 8_388_608  # 8 MiB
THEME = DEFAULT_THEME.copy()
THEME.comments = None


class DismissCode(discord.ui.View):
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
    await message.reply(
        content,
        view=DismissCode(message),
        files=files,
        mention_author=False,
    )
