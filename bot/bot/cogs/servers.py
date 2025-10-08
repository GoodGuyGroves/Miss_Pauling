"""Discord.py plugin to report game server statuses"""

import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
import aiohttp
import aioquery


class Servers(commands.Cog, name="Servers"):
    """Reports server status from a define list of servers"""

    # pylint: disable=eval-used

    logger = logging.getLogger(__name__)

    def __init__(self, client):
        load_dotenv()
        self.client = client

    @commands.group(invoke_without_command=True)
    async def servers(self, ctx):
        """Groups together the comp and pub commands"""
        await self.comp(ctx)
        await self.pub(ctx)

    @servers.command()
    async def comp(self, ctx):
        """Returns server status of comp servers only"""
        serv_addr_list = eval(os.getenv("PUG_SERVERS"))
        embed = discord.Embed(colour=discord.Colour.blue())
        embed.set_footer(text="rsa.tf")
        embed.set_author(
            name="rsa.tf servers", icon_url="https://rsa.tf/img/fist-s.jpg"
        )
        servers_with_players = 0
        for addr in serv_addr_list:
            serv_info = await self.comp_query(addr)
            if not serv_info:
                continue

            if len(serv_info["players"]) == 0:
                continue

            servers_with_players += 1
            embed.add_field(
                name=f'{serv_info["name"]}\n \
                    Server: {addr[0]}:{addr[1]}\n \
                    SourceTV: {addr[0]}:{addr[1] + 5}',
                value=f'({serv_info["player_count"]}/{serv_info["max_players"]}) {serv_info["map"]}\n \
                    Players: ```{", ".join(serv_info["players"])}```',
                inline=False,
            )
        if servers_with_players != 0:
            await ctx.send(embed=embed)
        else:
            await ctx.send("No activity on rsa.tf servers")

    @servers.command()
    async def pub(self, ctx):
        """Returns the status of pub servers only"""
        api_base = "https://api.battlemetrics.com/servers?sort=rank"
        query_opts = [
            "&fields[server]=name,players,maxPlayers,details",
            "&relations[server]=player,game,serverGroup",
            "&filter[game]=tf2",
            "&filter[countries][0]=ZA",
            "&filter[status]=online",
            "&filter[players][min]=1",
        ]
        full_query = api_base + "".join(query_opts)
        res = await self.pub_query(full_query)
        embed = discord.Embed(colour=discord.Colour.blue())
        embed.set_footer(text="rsa.tf")
        embed.set_author(name="pub servers", icon_url="https://rsa.tf/img/fist-s.jpg")
        for server in res["data"]:
            if "rsa.tf" in server["attributes"]["name"]:
                continue
            embed.add_field(
                name=f"{server['attributes']['name']}",
                value=f'({server["attributes"]["players"]}/{server["attributes"]["maxPlayers"]})\
                     {server["attributes"]["details"]["map"]}',
                inline=False,
            )
        await ctx.send(embed=embed)

    async def comp_query(self, addr) -> dict:
        """Comp server query"""
        query = aioquery.client(addr[0], addr[1], timeout=1)
        info = await query.info()
        players = await query.players()
        all_players = []
        if info and players:
            for player in players:
                all_players.append(player["name"])
            server_data = {}
            server_data["name"] = info["hostname"]
            server_data["map"] = info["map"]
            server_data["player_count"] = info["players"]
            server_data["max_players"] = info["max_players"]
            server_data["players"] = all_players
            return server_data

    async def pub_query(self, url) -> list:
        """Pub server query"""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                return data

    ## # # # # # # # # # # # #
    # Cleanup when unloading #
    ## # # # # # # # # # # # #

    def cog_unload(self):
        """Gets called when this cog is unloaded"""
        self.logger.info("Extension servers is being unloaded!")
        self.logger.handlers = []


def setup(client):
    """Sets this cog up"""
    client.add_cog(Servers(client))
