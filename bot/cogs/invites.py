"""Discord.py plugin for managing Discord users"""

import logging
import discord
from discord.ext import commands


class Invites(commands.Cog, name="Invites"):
    """Handles invite creation for a guild"""

    logger = logging.getLogger(__name__)

    def __init__(self, client):
        self.client = client


    @commands.command(hidden=True)
    @commands.has_any_role("admin")
    async def invite(self, ctx, member: discord.Member, *, reason=None):
        """Creates a single use invite and sends it to a user to share"""
        self.logger.info("%s: %s triggered invite()", ctx.channel.name, ctx.message.author)
        invite_link = await ctx.channel.create_invite(max_age=300, max_uses=1, reason=reason)
        await member.send(f'Your invite will last 300 seconds and is valid for one use: {invite_link}')
        await ctx.send(f'Invite created and sent to {member.mention}')
        self.logger.info("Created invite link for %s", member.mention)

    def cog_unload(self):
        """Gets called when this cog unloads"""
        self.logger.info("Extension invites is being unloaded!")
        self.logger.handlers = []


def setup(client):
    """Sets up this cog"""
    client.add_cog(Invites(client))
