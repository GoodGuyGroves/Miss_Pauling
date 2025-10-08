"""Discord.py plugin for managing extentions"""

import logging
import traceback
from discord.ext import commands
from discord.ext.commands import (
    ExtensionNotFound,
    ExtensionAlreadyLoaded,
    ExtensionFailed,
    NoEntryPointError,
)


class AdminExtensions(commands.Cog, name="Extensions"):
    """Actions for admins to manage plugins"""

    logger = logging.getLogger(__name__)

    def __init__(self, client):
        self.client = client

    @commands.command(hidden=True)
    @commands.has_any_role("admin")
    async def load(self, ctx, extension):
        """Loads a plugin that has not been loaded yet"""
        try:
            self.client.load_extension(f"pauling.cogs.{extension}")
            self.logger.info("Loaded extension %s", extension)
            await ctx.send(f"Loaded extension {extension}")
        except (
            ExtensionNotFound,
            ExtensionAlreadyLoaded,
            ExtensionFailed,
            NoEntryPointError,
        ):
            self.logger.warning("Failed to load extension %s", extension)
            self.logger.warning(traceback.format_exc())
            await ctx.send(f"Failed to load extension {extension}")

    @commands.command(hidden=True)
    @commands.has_any_role("admin")
    async def unload(self, ctx, extension):
        """Unloads a loaded plugin"""
        try:
            self.client.unload_extension(f"pauling.cogs.{extension}")
            self.logger.info("Unloaded extension %s", extension)
            await ctx.send(f"Unloaded extension {extension}")
        except (
            ExtensionNotFound,
            ExtensionAlreadyLoaded,
            ExtensionFailed,
            NoEntryPointError,
        ):
            self.logger.warning("Failed to unload extension %s", extension)
            self.logger.warning(traceback.format_exc())
            await ctx.send(f"Failed to unload extension {extension}")

    @commands.command(hidden=True)
    @commands.has_any_role("admin")
    async def reload(self, ctx, extension):
        """Reloads a loaded plugin"""
        try:
            self.client.unload_extension(f"pauling.cogs.{extension}")
            self.client.load_extension(f"pauling.cogs.{extension}")
            self.logger.info("Reloaded extension %s", extension)
            await ctx.send(f"Reloaded extension {extension}")
        except (
            ExtensionNotFound,
            ExtensionAlreadyLoaded,
            ExtensionFailed,
            NoEntryPointError,
        ):
            self.logger.warning("Reload of %s failed", extension)
            self.logger.warning(traceback.format_exc())
            await ctx.send(f"Reload of {extension} failed")

    ## # # # # # # # # # # # #
    # Cleanup when unloading #
    ## # # # # # # # # # # # #

    def cog_unload(self):
        """Gets called wehn this plugin is unloaded"""
        self.logger.info("Extension admin_extensions is being unloaded!")
        self.logger.handlers = []


def setup(client):
    """Sets up this plugin"""
    client.add_cog(AdminExtensions(client))
