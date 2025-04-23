"""Discord.py bot creation and startup"""

import os
import logging
import discord
from dotenv import load_dotenv
from pauling.bot import Bot


logger = logging.getLogger(__name__)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


pauling = Bot(command_prefix="!", activity=discord.Game("!help"), case_insensitive=True)

pauling.load_extension("pauling.cogs.pug")
pauling.load_extension("pauling.cogs.servers")
pauling.load_extension("pauling.cogs.admin_extensions")
pauling.load_extension("pauling.cogs.admin_users")
pauling.load_extension("pauling.cogs.admin_roles")

pauling.run(TOKEN)
