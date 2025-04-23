"""Discord.py plugin for managing Discord users"""

import logging
import discord
from discord.ext import commands


class AdminUsers(commands.Cog, name="Users"):
    """Actions for admins to manage users"""

    logger = logging.getLogger(__name__)

    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Gets called when a Discord user joins the Guild"""
        self.logger.info("%s has joined the server", member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Gets called when a Discord user leaves the Guild"""
        self.logger.info("%s has left the server", member)

    @commands.command(hidden=True)
    @commands.has_any_role("admin")
    async def kick(self, ctx, member: discord.Member, *, reason=None):
        """Kicks a Discord user"""
        self.logger.info(
            "%s: %s triggered kick()", ctx.channel.name, ctx.message.author
        )
        await member.kick(reason=reason)
        await ctx.send("Kicked user %s", member.mention)
        self.logger.info("Kicked user %s", member.mention)

    @commands.command(hidden=True)
    @commands.has_any_role("admin")
    async def ban(self, ctx, member: discord.Member, *, reason=None):
        """Bans a Discord user"""
        self.logger.info("%s: %s triggered ban()", ctx.channel.name, ctx.message.author)
        await member.ban(reason=reason)
        await ctx.send("Banned user %s", member.mention)
        self.logger.info("Banned user %s", member.mention)

    @commands.command(hidden=True)
    @commands.has_any_role("admin")
    async def unban(self, ctx, *, member: discord.Member):
        """Unbans a Discord user"""
        self.logger.info(
            "%s: %s triggered unban()", ctx.channel.name, ctx.message.author
        )
        banned_users = await ctx.guild.bans()
        member_name, member_discriminator = member.split("#")
        for ban_entry in banned_users:
            user = ban_entry.user
            if (user.name, user.descriminator) == (member_name, member_discriminator):
                await ctx.guild.unban(user)
                await ctx.send("Unbanned user %s", member.mention)
                self.logger.info("Unbanned user %s", member.mention)
                return

    ## # # # # # # # # # # # #
    # Cleanup when unloading #
    ## # # # # # # # # # # # #

    def cog_unload(self):
        """Gets called when this cog unloads"""
        self.logger.info("Extension admin_users is being unloaded!")
        self.logger.handlers = []


def setup(client):
    """Sets up this cog"""
    client.add_cog(AdminUsers(client))
