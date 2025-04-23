"""A Player that gets added to a pickup.py Game object"""

import discord


class Player:
    """A Player object comprised of a discord.Member object as well as a skill rating and steamid"""

    # def __init__(self, player, rating: int, steamid):
    #     self.display_name = player
    #     self.rating = rating
    #     self.steamid = steamid

    def __init__(self, player: discord.Member, rating: int, steamid):
        self.player = player
        self.id = player.id
        self.mention = player.mention
        self.display_name = player.display_name
        self.rating = rating
        self.steamid = steamid

    def __str__(self):
        return str(self.display_name)

    __repr__ = __str__
