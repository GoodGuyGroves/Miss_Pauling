"""Populates DB from logs.tf data"""

import asyncio
import datetime
from tortoise import Tortoise
from tortoise.exceptions import IntegrityError
import models
from utils.logstf import Match, Uploads
from utils.steam import SteamID


class DataHandler:
    """Queries logs.tf and stores to the Database"""

    def __init__(self):
        pass

    async def db_store_match_stats(self, game_id: int):
        """Stores stats from a particular match"""
        db_obj = await self.db_get_logstf(game_id)
        game_data = db_obj.game_data
        players = game_data["players"]

        logstf_id = await self.db_get_logstf(game_id)
        match_id = await self.db_get_match(game_id)

        for steamid, stats in players.items():
            steamid64 = SteamID().usteamid_to_commid(steamid)
            player_id = await self.db_get_player(steamid64)

            if not player_id:
                await Tortoise.init(
                    db_url="sqlite://pauling.db", modules={"models": ["models"]}
                )
                if not await models.Players.exists(steam_id=steamid64):
                    print(f"User {steamid64} doesn't exist, creating now")
                    player_id = await models.Players.create(steam_id=steamid64)

            await Tortoise.init(
                db_url="sqlite://pauling.db", modules={"models": ["models"]}
            )

            try:
                await models.PlayerStats.create(
                    match=match_id,
                    logstf=logstf_id,
                    player=player_id,
                    team=stats["team"],
                    # demoman=False,
                    # engineer=False,
                    # heavyweaponsguy=False,
                    # medic=False,
                    # pyro=False,
                    # scout=False,
                    # sniper=False,
                    # soldier=False,
                    # spy=False,
                    kills=stats["kills"],
                    deaths=stats["deaths"],
                    assists=stats["assists"],
                    suicides=stats["suicides"],
                    kapd=stats["kapd"],
                    kpd=stats["kpd"],
                    damage=stats["dmg"],
                    damage_real=stats["dmg_real"],
                    dt=stats["dt"],
                    dt_real=stats["dt_real"],
                    hr=stats["hr"],
                    lks=stats["lks"],
                    stat_as=stats["as"],
                    dapd=stats["dapd"],
                    dapm=stats["dapm"],
                    ubers=stats["ubers"],
                    drops=stats["drops"],
                    medkits=stats["medkits"],
                    medkits_hp=stats["medkits_hp"],
                    backstabs=stats["backstabs"],
                    headshots=stats["headshots"],
                    headshots_hit=stats["headshots_hit"],
                    sentries=stats["sentries"],
                    heal=stats["heal"],
                    cpc=stats["cpc"],
                    ic=stats["ic"],
                )
            except IntegrityError:
                print("Entry already exists")
            finally:
                await Tortoise.close_connections()
        await Tortoise.close_connections()

    async def db_store_match(self, game_id: int):
        """Stores top-level info about a logs.tf match"""
        db_obj = await self.db_get_logstf(game_id)
        game_data = db_obj.game_data

        red_score = game_data["teams"]["Red"]["score"]
        blue_score = game_data["teams"]["Blue"]["score"]
        if red_score == blue_score:
            winning_team = "Tie"
        elif red_score > blue_score:
            winning_team = "Red"
        else:
            winning_team = "Blue"

        logstf_id = await self.db_get_logstf(game_id)

        try:
            await Tortoise.init(
                db_url="sqlite://pauling.db", modules={"models": ["models"]}
            )
            await models.MatchData.create(
                logstf=logstf_id,
                match_date=datetime.datetime.fromtimestamp(
                    game_data["info"]["date"], tz=None
                ).isoformat(),
                winning_team=winning_team,
                players=list(game_data["names"].values()),
                length=game_data["length"],
                red_score=game_data["teams"]["Red"]["score"],
                red_kills=game_data["teams"]["Red"]["kills"],
                red_deaths=game_data["teams"]["Red"]["deaths"],
                red_dmg=game_data["teams"]["Red"]["dmg"],
                red_charges=game_data["teams"]["Red"]["charges"],
                red_drops=game_data["teams"]["Red"]["drops"],
                red_firstcaps=game_data["teams"]["Red"]["firstcaps"],
                red_caps=game_data["teams"]["Red"]["caps"],
                blue_score=game_data["teams"]["Blue"]["score"],
                blue_kills=game_data["teams"]["Blue"]["kills"],
                blue_deaths=game_data["teams"]["Blue"]["deaths"],
                blue_dmg=game_data["teams"]["Blue"]["dmg"],
                blue_charges=game_data["teams"]["Blue"]["charges"],
                blue_drops=game_data["teams"]["Blue"]["drops"],
                blue_firstcaps=game_data["teams"]["Blue"]["firstcaps"],
                blue_caps=game_data["teams"]["Blue"]["caps"],
            )
            print(f"Match data stored for {game_id}")
        except IntegrityError:
            print(f"Game {game_id} already stored.")
        finally:
            await Tortoise.close_connections()

    async def db_get_logstf(self, game_id: int) -> list:
        """Queries the DB for logs.tf entries"""
        await Tortoise.init(
            db_url="sqlite://pauling.db", modules={"models": ["models"]}
        )
        try:
            data = await models.LogstfData.filter(game_id=game_id)
        finally:
            await Tortoise.close_connections()
        if len(data) == 0:
            return data
        if len(data) > 1:
            return data
        return data[0]

    async def db_get_match(self, logstf_id: int) -> list:
        """Queries the DB for a particular matches info"""
        await Tortoise.init(
            db_url="sqlite://pauling.db", modules={"models": ["models"]}
        )
        try:
            data = await models.MatchData.filter(logstf=logstf_id)
        finally:
            await Tortoise.close_connections()
        return data[0]

    async def db_get_player(self, steam_id: int) -> list:
        """Queries the DB for a players stats"""
        await Tortoise.init(
            db_url="sqlite://pauling.db", modules={"models": ["models"]}
        )
        try:
            data = await models.Players.filter(steam_id=steam_id)
        finally:
            await Tortoise.close_connections()
        if len(data) == 0:
            return data
        if len(data) > 1:
            return data
        return data[0]

    async def logstf_store_match(self, game_id: int):
        """Stores a matches stats to the DB"""
        game_data = await Match(game_id).get_match()
        uploader_id = game_data["info"]["uploader"]["id"]
        game_map = game_data["info"]["map"]
        game_date = datetime.datetime.fromtimestamp(
            game_data["info"]["date"], tz=None
        ).isoformat()
        game_title = game_data["info"]["title"]
        await Tortoise.init(
            db_url="sqlite://pauling.db", modules={"models": ["models"]}
        )
        try:
            await models.LogstfData.create(
                game_id=game_id,
                uploader_id=uploader_id,
                game_map=game_map,
                game_date=game_date,
                game_title=game_title,
                game_data=game_data,
            )
            print(f"Added game {game_id}")
        except IntegrityError:
            print("Match already added to DB")
        finally:
            await Tortoise.close_connections()


if __name__ == "__main__":
    handler = DataHandler()
    all_uploads = asyncio.run(Uploads(76561198003234706).get_uploads())
    for upload in all_uploads:
        asyncio.run(handler.logstf_store_match(upload))
        asyncio.run(handler.db_store_match(upload))
        asyncio.run(handler.db_store_match_stats(upload))
