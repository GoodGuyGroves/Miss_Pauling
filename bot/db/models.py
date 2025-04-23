"""Miss Pauling schema models"""

# pylint: disable=R0903

from tortoise.models import Model
from tortoise import fields


class Servers(Model):
    """Table to hold servers used for pickup games"""

    server_id = fields.IntField(pk=True, generated=True)
    ip = fields.CharField(max_length=15)
    port = fields.IntField(max_length=5)

    class Meta:
        """Servers metadata"""

        table = "servers"
        table_description = "List of rsa.tf servers"
        unique_together = ("ip", "port")


class PugHistory(Model):
    """Table to hold history of pug games organised through Discord"""

    game_id = fields.IntField(pk=True, generated=True)
    date = fields.DatetimeField(auto_now_add=True)
    channel_id = fields.CharField(max_length=18)
    channel_name = fields.CharField(max_length=50)
    players = fields.CharField(max_length=255)

    class Meta:
        """PugHistory metadata"""

        table = "pug_history"
        table_description = "History of all played pug games"
        # Add a unqiue constraint to avoid shenanigans
        unique_together = ("channel_id", "players")


class Players(Model):
    """Table to hold every player that uses the pickup system"""

    steam_id = fields.CharField(pk=True, generated=False, max_length=20)

    class Meta:
        """Players metadata"""

        table = "players"
        table_description = "Stores information on all Players"


class LogstfData(Model):
    """Table to hold top-level info about a logs.tf game"""

    game_id = fields.IntField(pk=True, generated=False)
    uploader_id = fields.IntField()
    game_map = fields.CharField(max_length=25)
    game_date = fields.DatetimeField()
    game_title = fields.CharField(max_length=255)
    game_data = fields.JSONField()

    class Meta:
        """LogstfData metadata"""

        table = "logstf"
        table_description = "Stores raw logstf data for all matches"
        unique_together = ("game_id", "uploader_id")


class MatchData(Model):
    """Table to hold detailed stats about a logs.tf match"""

    match_id = fields.IntField(pk=True, generated=True)
    logstf = fields.ForeignKeyField("models.LogstfData", related_name="match_data")
    match_date = fields.DatetimeField()
    winning_team = fields.CharField(max_length=4)
    # Should we reference Players table for each player in the game?
    players = fields.CharField(max_length=255)
    length = fields.IntField()
    red_score = fields.IntField()
    red_kills = fields.IntField()
    red_deaths = fields.IntField()
    red_dmg = fields.IntField()
    red_charges = fields.IntField()
    red_drops = fields.IntField()
    red_firstcaps = fields.IntField()
    red_caps = fields.IntField()
    blue_score = fields.IntField()
    blue_kills = fields.IntField()
    blue_deaths = fields.IntField()
    blue_dmg = fields.IntField()
    blue_charges = fields.IntField()
    blue_drops = fields.IntField()
    blue_firstcaps = fields.IntField()
    blue_caps = fields.IntField()

    class Meta:
        """MatchData metadata"""

        table = "matches"
        table_description = "Stores data on all matches played"
        unique_together = ("logstf",)


class PlayerStats(Model):
    """Table to hold all game stats for a particular player"""

    stats_id = fields.IntField(pk=True, generated=True)
    match = fields.ForeignKeyField("models.MatchData", related_name="player_stats")
    logstf = fields.ForeignKeyField("models.LogstfData", related_name="player_stats")
    player = fields.ForeignKeyField("models.Players", related_name="player_stats")
    team = fields.CharField(max_length=4)
    # I need to add win here as boolean
    # These need to be broken out into separate tables?
    # demoman = fields.BooleanField(default=False)
    # engineer = fields.BooleanField(default=False)
    # heavyweaponsguy = fields.BooleanField(default=False)
    # medic = fields.BooleanField(default=False)
    # pyro = fields.BooleanField(default=False)
    # scout = fields.BooleanField(default=False)
    # sniper = fields.BooleanField(default=False)
    # soldier = fields.BooleanField(default=False)
    # spy = fields.BooleanField(default=False)
    kills = fields.IntField()
    deaths = fields.IntField()
    assists = fields.IntField()
    suicides = fields.IntField()
    kapd = fields.FloatField()
    kpd = fields.FloatField()
    damage = fields.IntField()
    damage_real = fields.IntField()
    dt = fields.IntField()
    dt_real = fields.IntField()
    hr = fields.IntField()
    lks = fields.IntField()
    stat_as = fields.IntField()
    dapd = fields.IntField()
    dapm = fields.IntField()
    ubers = fields.IntField()
    drops = fields.IntField()
    medkits = fields.IntField()
    medkits_hp = fields.IntField()
    backstabs = fields.IntField()
    headshots = fields.IntField()
    headshots_hit = fields.IntField()
    sentries = fields.IntField()
    heal = fields.IntField()
    cpc = fields.IntField()
    ic = fields.IntField()

    class Meta:
        """PlayerStats metadata"""

        table = "stats"
        table_description = "Contains a players stats for each match"
        unique_together = ("logstf", "player")
