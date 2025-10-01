from __future__ import annotations

import inspect
from contextlib import suppress
from typing import TYPE_CHECKING, final

import discord as dc
from discord.app_commands import Choice
from discord.ext import commands
from loguru import logger

from app.utils import pretty_print_account, try_dm

if TYPE_CHECKING:
    from app.bot import GhosttyBot


@final
class Developer(commands.Cog):
    def __init__(self, bot: GhosttyBot) -> None:
        self.bot = bot

    async def existing_extension_autocomplete(
        self, _: dc.Interaction, current: str
    ) -> list[Choice[str]]:
        return sorted(
            (
                Choice(name=name, value=cog_module.__name__)
                for name, cog in self.bot.cogs.items()
                if (
                    current.casefold() in name.casefold()
                    and (cog_module := inspect.getmodule(cog))
                )
            ),
            key=lambda x: x.name,
        )[:25]

    @commands.Cog.listener()
    async def on_message(self, message: dc.Message) -> None:
        # Handle !sync command. This can't be a slash command because this command is
        # the one that actually adds the slash commands in the first place.
        if message.content.strip() != "!sync":
            return

        if not self.bot.is_ghostty_mod(message.author):
            logger.debug(
                "!sync called by {} who is not a mod",
                pretty_print_account(message.author),
            )
            return

        logger.info("syncing command tree")
        await self.bot.tree.sync()
        await try_dm(message.author, "Command tree synced.")

    @dc.app_commands.command(name="status", description="View Ghostty Bot's status.")
    @dc.app_commands.guild_only()
    # Hide interaction from non-mods
    @dc.app_commands.default_permissions(ban_members=True)
    async def status(self, interaction: dc.Interaction) -> None:
        # The client-side check with `default_permissions` isn't guaranteed to work.
        if not self.bot.is_ghostty_mod(interaction.user):
            await interaction.response.send_message(
                "Only mods can use this command.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            await self.bot.bot_status.status_message(), ephemeral=True
        )

    @dc.app_commands.command(description="Reload bot extensions.")
    @dc.app_commands.guild_only()
    # Hide interaction from non-mods
    @dc.app_commands.default_permissions(ban_members=True)
    @dc.app_commands.autocomplete(extension=existing_extension_autocomplete)
    async def reload(
        self, interaction: dc.Interaction, extension: str | None = None
    ) -> None:
        # The client-side check with `default_permissions` isn't guaranteed to work.
        if not self.bot.is_ghostty_mod(interaction.user):
            await interaction.response.send_message(
                "Only mods can use this command.", ephemeral=True
            )
            return

        if extension:
            if not self.bot.is_valid_extension(extension):
                await interaction.response.send_message(
                    f"Extension `{extension}` does not exist or is invalid.",
                    ephemeral=True,
                )
                return
            extensions = [extension]
        else:
            # If no extension is provided, reload all extensions
            extensions = self.bot.get_component_extension_names()

        reloaded_extensions: list[str] = []
        failed_reloaded_extensions: list[str] = []

        await interaction.response.defer(thinking=True, ephemeral=True)
        for ext in extensions:
            try:
                with suppress(commands.ExtensionNotLoaded):
                    # If already not loaded, ignore error
                    await self.bot.unload_extension(ext)
                await self.bot.load_extension(ext)
                reloaded_extensions.append(ext)
            except commands.ExtensionFailed as error:
                logger.opt(exception=error).exception(
                    f"{pretty_print_account(interaction.user)} failed to reload `{ext}`"
                )
                failed_reloaded_extensions.append(ext)
            except commands.ExtensionError as error:
                logger.warning(
                    "{} failed to reload `{}`: {}",
                    pretty_print_account(interaction.user),
                    ext,
                    error,
                )
                failed_reloaded_extensions.append(ext)

        reload_message = ""
        if reloaded_extensions and extension:
            reload_message = f"Reloaded `{extension}`"
        elif reloaded_extensions:
            reload_message = "Reloaded:\n* " + "\n* ".join(
                f"`{e}`" for e in reloaded_extensions
            )
        if failed_reloaded_extensions:
            reload_message += "\nFailed to reload:\n* " + "\n* ".join(
                f"`{e}`" for e in failed_reloaded_extensions
            )
        # Remove the newline if all extensions failed to reload
        reload_message = reload_message.strip()

        await interaction.followup.send(reload_message, ephemeral=True)

    @dc.app_commands.command(description="Unload bot extension.")
    @dc.app_commands.guild_only()
    # Hide interaction from non-mods
    @dc.app_commands.default_permissions(ban_members=True)
    @dc.app_commands.autocomplete(extension=existing_extension_autocomplete)
    async def unload(self, interaction: dc.Interaction, extension: str) -> None:
        # The client-side check with `default_permissions` isn't guaranteed to work.
        if not self.bot.is_ghostty_mod(interaction.user):
            await interaction.response.send_message(
                "Only mods can use this command.", ephemeral=True
            )
            return
        if not self.bot.is_valid_extension(extension):
            await interaction.response.send_message(
                f"Extension `{extension}` does not exist or is invalid.", ephemeral=True
            )
            return

        try:
            await self.bot.unload_extension(extension)
            await interaction.response.send_message(
                f"Unloaded `{extension}`", ephemeral=True
            )
        except commands.ExtensionFailed as error:
            logger.opt(exception=error).exception(
                f"{pretty_print_account(interaction.user)} failed to unload "
                f"`{extension}`"
            )
        except commands.ExtensionError as error:
            logger.warning(
                "{} failed to unload `{}`: {}",
                pretty_print_account(interaction.user),
                extension,
                error,
            )
        else:
            return

        await interaction.response.send_message(
            f"Failed to unload `{extension}`", ephemeral=True
        )

    @dc.app_commands.command(description="Load bot extension.")
    @dc.app_commands.guild_only()
    # Hide interaction from non-mods
    @dc.app_commands.default_permissions(ban_members=True)
    async def load(self, interaction: dc.Interaction, extension: str) -> None:
        # The client-side check with `default_permissions` isn't guaranteed to work.
        if not self.bot.is_ghostty_mod(interaction.user):
            await interaction.response.send_message(
                "Only mods can use this command.", ephemeral=True
            )
            return
        if not self.bot.is_valid_extension(extension):
            await interaction.response.send_message(
                f"Extension `{extension}` does not exist or is invalid.", ephemeral=True
            )
            return

        try:
            await self.bot.load_extension(extension)
            await interaction.response.send_message(
                f"Loaded `{extension}`", ephemeral=True
            )
        except commands.ExtensionFailed as error:
            logger.opt(exception=error).exception(
                f"{pretty_print_account(interaction.user)} failed to load `{extension}`"
            )
        except commands.ExtensionError as error:
            logger.warning(
                "{} failed to load `{}`: {}",
                pretty_print_account(interaction.user),
                extension,
                error,
            )
        else:
            return

        await interaction.response.send_message(
            f"Failed to load `{extension}`", ephemeral=True
        )

    @load.autocomplete("extension")
    async def unloaded_extensions_autocomplete(
        self, _: dc.Interaction, current: str
    ) -> list[Choice[str]]:
        loaded_extensions = {
            cog_module.__name__
            for cog in self.bot.cogs.values()
            if (cog_module := inspect.getmodule(cog))
        }
        unloaded_extension_paths = (
            self.bot.get_component_extension_names() - loaded_extensions
        )
        return sorted(
            (
                Choice(name=name, value=name)
                for name in unloaded_extension_paths
                if current.casefold() in name.casefold()
            ),
            key=lambda x: x.name,
        )[:25]


async def setup(bot: GhosttyBot) -> None:
    await bot.add_cog(Developer(bot))
