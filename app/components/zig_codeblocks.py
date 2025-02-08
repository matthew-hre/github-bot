from io import BytesIO

import discord
from zig_codeblocks import extract_codeblocks, highlight_zig_code, process_markdown

from app.utils import is_dm, is_mod

MAX_CONTENT = 51_200  # 50 KiB
MAX_ZIG_FILE_SIZE = 8_388_608  # 8 MiB


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


async def check_for_zig_code(message: discord.Message) -> None:
    attachments = [
        discord.File(
            BytesIO(highlight_zig_code((await att.read())[:MAX_CONTENT]).encode()),
            att.filename + ".ansi",
        )
        for att in message.attachments
        if att.filename.endswith(".zig") and att.size <= MAX_ZIG_FILE_SIZE
    ]
    codeblocks = list(extract_codeblocks(message.content))
    if codeblocks and any(block.lang == "zig" for block in codeblocks):
        zig_code = process_markdown(message.content, only_code=True)
        if len(zig_code) <= 2000:
            await message.reply(
                zig_code,
                view=DismissCode(message),
                files=attachments,
                mention_author=False,
            )
    elif attachments:
        await message.reply(
            'Click "View whole file" to see the highlighting.',
            view=DismissCode(message),
            files=attachments,
            mention_author=False,
        )
