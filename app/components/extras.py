from typing import TYPE_CHECKING, Any, final

import discord as dc
from discord.ext import commands

from app.utils import is_dm, is_mod, try_dm

if TYPE_CHECKING:
    from app.bot import GhosttyBot


@final
class Extras(commands.Cog):
    def __init__(self, bot: "GhosttyBot") -> None:
        self.bot = bot

    @commands.command(name="sync", description="Accept a pending tester invite.")
    @commands.guild_only()
    async def sync(self, ctx: commands.Context[Any]) -> None:
        assert not is_dm(ctx.author)
        if not is_mod(ctx.author):
            return

        await self.bot.tree.sync()
        await try_dm(ctx.author, "Command tree synced.")

    @dc.app_commands.command(name="status")
    async def ghostty_bot_status(self, interaction: dc.Interaction) -> None:
        user = interaction.user
        member = self.bot.ghostty_guild.get_member(user.id)
        if member is None or not is_mod(member):
            await interaction.response.send_message(
                "Sorry, only mods can use this command", ephemeral=True
            )
        await interaction.response.send_message(
            await self.bot.ghostty_status.status_message()
        )


async def setup(bot: "GhosttyBot") -> None:
    await bot.add_cog(Extras(bot))
