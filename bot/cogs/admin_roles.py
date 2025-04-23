"""Discord.py plugin for managing roles"""

import logging
import discord
from discord.ext import commands


class AdminRoles(commands.Cog, name="Roles"):
    """Actions for admins to manage roles"""

    logger = logging.getLogger(__name__)

    def __init__(self, client):
        pass

    @commands.command(hidden=True)
    @commands.has_any_role("admin")
    async def listroles(self, ctx):
        """Lists all server roles"""
        # await ctx.guild.create_role(name="role name")
        # await ctx.send(ctx.guild.roles)
        print(type(ctx.guild.roles[0]))
        embed = discord.Embed(colour=discord.Colour.blue())
        embed.set_footer(text="rsa.tf")
        embed.set_author(
            name="rsa.tf servers", icon_url="https://rsa.tf/img/fist-s.jpg"
        )
        for role in ctx.guild.roles:
            embed.add_field(
                name=f"{role.name}",
                value=(
                    f"ID: {role.id}\n"
                    f"Position: {role.position}\n"
                    f"Colour: {role.colour}\n"
                    f"Hoist: {role.hoist}\n"
                    f"Mentionable: {role.mentionable}\n"
                    f"Mention: {role.mention}\n"
                    f"Permissions: {role.permissions}"
                ),
                inline=True,
            )
        await ctx.send(embed=embed)

    def cog_unload(self):
        """Gets called when this cog is unloaded"""
        self.logger.info("Extension Roles is being unloaded!")
        self.logger.handlers = []


def setup(client):
    """Sets this cog up"""
    client.add_cog(AdminRoles(client))
