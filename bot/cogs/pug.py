#!/usr/bin/env python3

"""Discord.py Pick-up Game plugin. Handles gathering Players through a Discord guild and desginated channels"""

import logging
import os
import random
import asyncio
import discord
import valve.rcon
import valve.source.a2s
from discord.ext import commands, tasks
from dotenv import load_dotenv
from pauling.utils.pickup import (
    Game,
    GameFullError,
    GameNotOnError,
    GameOnError,
    PlayerAddedError,
    PlayerNotAddedError,
    TeamFullError,
)
from pauling.utils.player import Player


class Timer:
    """Handles timer-based events for the PUG Class."""

    logger = logging.getLogger(__name__)

    def __init__(self, game, chan):
        self.game = game
        self.chan = chan
        self.loop = asyncio.get_event_loop()
        self.game_server = None
        self.game_password = None

    def __del__(self):
        self.logger.info("Reference to object Timer being deleted!")
        self.logger.handlers = []

    async def start_countdown(self):
        """Starts a countdown when a game is full"""
        await self.loop.create_task(self.countdown())

    async def countdown(self):
        """Checks if the game is still full and commences the game if the countdown completes"""
        context = self.game.chaninfo[self.chan]
        count = 1
        while count and context["game"].game_full:
            self.logger.info(
                "%s: Game is still full. Checks remaining: %s", self.chan, count
            )
            count -= 1
            await asyncio.sleep(1)

        if not context["game"].game_full:
            await context["ctx"].send("Game no longer full, cancelling countdown.")
            self.logger.info("%s: Game no longer full", self.chan)

        if context["game"].game_full:
            self.logger.info("Game commencing")
            context = self.game.chaninfo[self.chan]
            # We want to run Pug's game_stop() method which will clear some variables so make copies of them first
            self.game_server = context["game"].server
            self.game_password = random.choice(self.game.passwords)
            game_players = [x for x in context["added_players"].values()]

            # Stop the game so people can't !rem now that the timer has concluded
            await self.game.game_stop(context)

            await context["ctx"].send(
                "Game commencing! PM'ing connection details to all players"
            )
            self.game.reset_password.restart()

            valve.rcon.execute(
                self.game_server,
                self.game.rcon_password,
                f"changelevel {context['game_map']}",
            )
            await self.game.change_password(
                address=self.game_server, password=f"{self.game_password}"
            )

            connect_string = (
                "Your Pick-up Game is ready. "
                f"Please connect to steam://connect/{self.game_server[0]}:{self.game_server[1]}/{self.game_password}"
            )
            for player in game_players:
                await player.player.send(connect_string)

            # self.game.used_servers.append(self.game_server)
            await self.loop.create_task(self.server_readd())

    async def server_readd(self):
        """A timer to re-add a server to the server pool"""
        await asyncio.sleep(60)
        self.logger.info("Removing %s from used servers %s", self.game_server, self.game.used_servers)
        self.game.used_servers.remove(self.game_server)
        self.game_server = None


class PUG(commands.Cog, name="Pick-up Game"):
    """Connects to a Guild and operates pickup games in designated channels"""

    # pylint: disable=too-many-instance-attributes
    # Eval is needed (I believe) to turn a string representation of a list into an actual list loaded with dotenv
    # pylint: disable=eval-used

    logger = logging.getLogger(__name__)

    def __init__(self, client):
        load_dotenv()
        # self.reset_password.start()
        self.client = client
        self.game_guild = int(os.getenv("PRIMARY_GUILD"))
        self.passwords = eval(os.getenv("PUG_PASSWORDS"))
        self.rcon_password = os.getenv("RCON_PASSWORD")
        self.used_servers = []
        self.channels = eval(os.getenv("PUG_CHANNELS"))
        self.chaninfo = {}
        self.pug_init()

    def __del__(self):
        self.logger.info("Reference to object Pug being deleted!")
        self.logger.handlers = []

    def pug_init(self):
        """Creates a separate instance of Game and Timer for each pickup channel"""
        for channel in self.channels:
            self.chaninfo[channel] = {}
            self.chaninfo[channel]["ctx"] = None
            self.chaninfo[channel]["game_message"] = None
            self.chaninfo[channel]["game_map"] = None
            self.chaninfo[channel]["added_players"] = {}
            game = Game(mode="captain")
            self.chaninfo[channel]["game"] = game
            timer = Timer(self, channel)
            self.chaninfo[channel]["timer"] = timer

    @commands.command(help="- Starts a pick-up game")
    @commands.has_any_role("admin", "pug-admin", "captain")
    async def start(self, ctx, mode="captain"):
        """Starts a pickup game if one is not already on"""
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(
            "%s: %s triggered start()", ctx.channel.name, ctx.message.author
        )

        if ctx.message.guild.id != self.game_guild:
            return

        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        if context["game"].game_on:
            await ctx.send("Game already on")
            return

        if not context["game"].game_on:
            try:
                context["game"].start(mode)
            except GameOnError as e:
                await ctx.send(f"{e}")

            context["game"].server = await self.find_server(context)

            if context["game"].server is None:
                await ctx.send("No open servers to use, not starting.")
                return

            if context["game"].server in self.used_servers:
                self.used_servers.remove(context["game"].server)

            if context["game"].server is not None:
                self.logger.info(
                    "Adding server %s to used list %s", context["game"].server, self.used_servers
                )
                self.used_servers.append(context["game"].server)

            context["game_map"] = random.choice(context["game"].map_pool)

            await ctx.send(
                f'Game started! This game will be played on {context["game"].server[0]}:{context["game"].server[1]}'
            )
            context["game_message"] = await ctx.send(
                f'```({context["game_map"]}) {context["game"].pretty_status()}```'
            )
            await context["game_message"].pin()
            await self.change_password(
                address=context["game"].server, password="temppassword"
            )
        return

    @commands.command(help="- Stops an active pick-up game")
    @commands.has_any_role("admin", "pug-admin", "captain")
    async def stop(self, ctx):
        """Stops a pickup game if one is already on"""
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(
            "%s: %s triggered stop()", ctx.channel.name, ctx.message.author
        )

        if ctx.message.guild.id != self.game_guild:
            return

        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        server = context["game"].server

        try:
            await self.game_stop(context)
        except (GameOnError, GameNotOnError) as e:
            await ctx.send(f"{e}")
            return

        self.used_servers.remove(server)
        await ctx.send("Game stopped.")
        await context["game_message"].edit(content="```Game cancelled.```")
        return

    @commands.command(help="- Checks the status of an active pick-up game")
    async def status(self, ctx):
        """Checks the status of the current pickup game"""
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(
            "%s: %s triggered status()", ctx.channel.name, ctx.message.author
        )

        if ctx.message.guild.id != self.game_guild:
            return

        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        if not context["game"].game_on:
            await ctx.send("No game on.")
            return

        if context["game"].game_on:
            status = f'```({context["game_map"]}) {context["game"].pretty_status()}```'
            await ctx.send(status)
        return

    @commands.command(help="- Adds yourself to an active pick-up game")
    @commands.has_any_role("player")
    async def add(self, ctx):
        """Adds to an active pickup game"""
        context = self.chaninfo[ctx.channel.id]
        self.logger.info("%s: %s triggered add()", ctx.channel.name, ctx.message.author)

        if ctx.message.guild.id != self.game_guild:
            return

        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        if not context["game"].game_on:
            await ctx.send("No game on.")
            return

        if ctx.message.author.id in context["added_players"].keys():
            await ctx.send("Already added.")
            return

        for _, value in self.chaninfo.items():
            if ctx.message.author.id in value["added_players"].keys():
                await ctx.send("Already added elsewhere.")
                return

        player = Player(ctx.message.author, 0, None)

        try:
            context["added_players"][ctx.message.author.id] = player
            context["game"].add(context["added_players"][ctx.message.author.id])
        except (PlayerAddedError, GameFullError, TeamFullError) as e:
            del context["added_players"][ctx.message.author.id]
            await ctx.send(f"{e}")
            return

        await self.game_update_pin(ctx.channel.id)
        await self.status(ctx)
        await self.game_start(ctx, context)

    @commands.command(
        aliases=["rem"], help="- Removes yourself from an active pick-up game"
    )
    async def remove(self, ctx):
        """Removes from an active pickup game"""
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(
            "%s: %s triggered remove()", ctx.channel.name, ctx.message.author
        )

        if ctx.message.guild.id != self.game_guild:
            return

        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        if not context["game"].game_on:
            await ctx.send("No game on")

        if ctx.message.author.id not in context["added_players"].keys():
            await ctx.send("Not added.")
            return

        if context["game"].game_on:
            try:
                context["game"].remove(context["added_players"][ctx.message.author.id])
                del context["added_players"][ctx.message.author.id]
            except (GameNotOnError, PlayerNotAddedError) as e:
                await ctx.send(f"{e}")
                return

        await self.game_update_pin(ctx.channel.id)
        await self.status(ctx)
        return

    @commands.command(aliases=["pk"], hidden=True)
    @commands.has_any_role("admin", "pug-admin", "captain")
    async def playerkick(self, ctx, member: discord.Member):
        """Kicks a player from an active pickup game"""
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(
            "%s: %s triggered playerkick()", ctx.channel.name, ctx.message.author
        )

        if ctx.message.guild.id != self.game_guild:
            return

        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        if not context["game"].game_on:
            await ctx.send("No game on")

        if member.id not in context["added_players"].keys():
            await ctx.send("Player not added.")
            return

        if context["game"].game_on:
            try:
                context["game"].remove(context["added_players"][member.id])
                del context["added_players"][member.id]
                await self.game_update_pin(ctx.channel.id)
                await self.status(ctx)
            except (GameNotOnError, PlayerNotAddedError) as e:
                await ctx.send(f"{e}")
                return

    @commands.command(help="- Changes the map of the active game")
    @commands.has_any_role("admin", "pug-admin", "captain")
    async def map(self, ctx, game_map):
        """Changes the map to be played for the active pickup game"""
        context = self.chaninfo[ctx.channel.id]
        self.logger.info("%s: %s triggered map()", ctx.channel.name, ctx.message.author)

        if ctx.message.guild.id != self.game_guild:
            return

        if ctx.message.channel.id not in self.chaninfo.keys():
            return
        mapname = ""
        if True in [game_map in x for x in context["game"].map_pool]:
            for x in context["game"].map_pool:
                if game_map in x:
                    mapname = x
            context["game_map"] = mapname
            await ctx.send(f"Map changed to {context['game_map']}")
            await self.status(ctx)
        else:
            await ctx.send("Invalid map name, !maps to see valid maps.")

    @commands.command(help="- Lists the maps in the map pool")
    @commands.has_any_role("player")
    async def maps(self, ctx):
        """Lists maps added to the map pool"""
        context = self.chaninfo[ctx.channel.id]
        self.logger.info(
            "%s: %s triggered maps()", ctx.channel.name, ctx.message.author
        )

        if ctx.message.guild.id != self.game_guild:
            return

        if ctx.message.channel.id not in self.chaninfo.keys():
            return

        await ctx.send(f"Map pool: {', '.join(context['game'].map_pool)}")
        return

    async def game_start(self, ctx, context):
        """Starts the countdown timer if the game is full"""
        if (
            context["game"].player_count == context["game"].max_players
            and context["game"].game_full
        ):
            await ctx.send("Game is full. Waiting 60 seconds before game starts.")
            context["ctx"] = ctx
            await context["timer"].start_countdown()

    async def game_stop(self, context):
        """Stops a game"""
        try:
            context["game"].stop()
        except (GameOnError, GameNotOnError) as e:
            raise e
        context["game"].server = None
        context["added_players"] = {}
        await context["game_message"].unpin()

    async def find_server(self, context):
        """Finds an open server to use"""
        avail_servs = list(set(context["game"].server_pool) - set(self.used_servers))
        self.logger.info("Looking for an open server from: %s", avail_servs)
        for address in avail_servs:
            try:
                with valve.source.a2s.ServerQuerier(address) as server:
                    server_name = server.info()["server_name"]
                    player_count = server.info()["player_count"]
                    self.logger.info(
                        "Server %s has %s players", server_name, player_count
                    )
                    if player_count < 1:
                        return (server.host, server.port)
            except valve.source.NoResponseError:
                self.logger.warning(
                    "Could not query server %s to see if it is open", address
                )

    async def change_password(self, address, password):
        """Changes the password of a server"""
        command = f"sv_password {password}"
        valve.rcon.execute(address, self.rcon_password, command)

    async def game_update_pin(self, chan):
        """Updates the pinned message with the current game status"""
        context = self.chaninfo[chan]
        await context["game_message"].edit(
            content=(f'```({context["game_map"]}) {context["game"].pretty_status()}```')
        )

    @tasks.loop(seconds=600)
    async def reset_password(self):
        pass
        # """Looks for servers not in use and resets their passwords so people can't rejoin"""
        # self.logger.info("Checking for a server password to reset")
        # if self.used_servers:
        #     for address in self.used_servers:
        #         self.logger.info("Trying to reset password for server %s", address)
        #         try:
        #             with valve.source.a2s.ServerQuerier(address) as server:
        #                 player_count = server.info()["player_count"]
        #                 server_name = server.info()["server_name"]
        #                 if player_count < 1:
        #                     self.logger.info(
        #                         "Changing sv_password of server %s", server_name
        #                     )
        #                     valve.rcon.execute(
        #                         address,
        #                         self.rcon_password,
        #                         "sv_password wedontreallycare",
        #                     )
        #                     self.used_servers.remove(address)
        #                 else:
        #                     self.logger.info(
        #                         "Server %s still in use, not changing password", server
        #                     )
        #         except valve.source.NoResponseError:
        #             self.logger.warning("Could not connect to %s", address)

    def cog_unload(self):
        """Gets called when this plugin is unloaded"""
        self.logger.info("Extension pug is being unloaded!")
        self.logger.handlers = []
        # self.reset_password.cancel()
        del self.chaninfo


def setup(client):
    """Sets up this plugin"""
    client.add_cog(PUG(client))
