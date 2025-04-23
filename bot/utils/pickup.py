"""Handles Pick-up Game logic"""

import random

try:
    from .player import Player
    from .game_modes import GameMode
except ImportError:
    from player import Player
    from game_modes import GameMode


class Game:
    """Creates a pick up game, handles teams and players added to those teams and overall game status"""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, mode: GameMode = "sixes") -> None:
        self.empty_slot = "?"
        self.teams_count = None
        self.team_size = None
        self.teams = None
        self.max_players = None
        self.player_count = None
        self.game_on = False
        self.game_full = False
        self.server = None
        self.set_mode(mode)

    def set_mode(self, mode):
        """Loads variables based on game mode"""
        game_mode = GameMode("../configs/game_modes.yaml", mode)
        self.team_size = game_mode.players
        self.teams_count = game_mode.teams
        self.map_pool = game_mode.map_pool
        self.server_pool = game_mode.server_pool

    def start(self, mode="sixes") -> None:
        """Starts a pickup game with the specified number of teams. The mode determines number of players per team."""
        if self.game_on is True:
            raise GameOnError("Game already on.")

        if mode is not None:
            self.set_mode(mode)

        self.teams = [
            [self.empty_slot for x in range(self.team_size)]
            for i in range(self.teams_count)
        ]
        self.max_players = self.team_size * self.teams_count
        self.player_count = 0
        self.game_on = True

    def stop(self):
        """Stops a game if one is active"""
        if self.game_on is False:
            raise GameOnError("No game on.")

        self.team_size = None
        self.teams = None
        self.max_players = None
        self.player_count = None
        self.game_on = False
        self.game_full = False

    def restart(self, mode="sixes"):
        """Restarts a game if one is active, can restart to a new mode or with different number of teams"""
        self.stop()
        if mode is not None:
            self.set_mode(mode)
        self.start(mode)

    def status(self) -> str:
        """Returns a JSON object of Player objects that have been added"""
        if self.game_on is False:
            raise GameNotOnError("No game on.")

        teams = {}
        for i in range(0, len(self.teams)):
            teams[i] = self.teams[i]

        return teams

    def pretty_status(self) -> str:
        """Prettifies the output from status()"""
        game_status = self.status()
        teams = []

        for _, value in game_status.items():
            teams.append(value)
        team_count = 0
        all_teams = ""

        for team in teams:
            team_count += 1
            team_lineup = []
            team_empty = []

            for player in team:
                if player != self.empty_slot:
                    team_lineup.append(player.display_name)
                else:
                    team_empty.append(player)

            all_teams += f"Team {team_count} [{len(team_lineup)}/{len(team)}] Players: ({'), ('.join(team_lineup + team_empty)}"
            all_teams += ") "

        return all_teams

    def add(self, player: Player, team: int = None) -> None:
        """Adds a Player to a game. If no team is chosen, one will be randomly chosen"""
        if self.game_on is False:
            raise GameNotOnError("No game on.")

        if any(player in x for x in self.teams):
            raise PlayerAddedError("Player already added.")

        eligible_teams = []
        for index, _ in enumerate(self.teams):
            if not self._is_full(self.teams[index]):
                eligible_teams.append(index)

        if len(eligible_teams) == 0:
            raise GameFullError("The game is full.")

        if team is None:
            selected_team = self.teams[random.choice(eligible_teams)]
        elif team > self.teams_count:
            raise InvalidTeamError("Invalid team selected.")
        elif team - 1 not in eligible_teams:
            raise TeamFullError("Team is full.")
        else:
            selected_team = self.teams[team - 1]

        for index, slot in enumerate(selected_team):
            if slot == self.empty_slot:
                selected_team[index] = player
                break
        self.player_count += 1

        if self.player_count == self.max_players:
            self.game_full = True

    def remove(self, player: Player) -> None:
        """Removes a Player from a running game"""
        if self.game_on is False:
            raise GameNotOnError("No game on")

        if not any(player in x for x in self.teams):
            raise PlayerNotAddedError("Player is not added.")

        for index, _ in enumerate(self.teams):
            if player in self.teams[index]:
                self.teams[index] = [
                    self.empty_slot if x == player else x for x in self.teams[index]
                ]
        self.player_count -= 1

        if self.game_full:
            self.game_full = False

    def transform(self, teams: int = 2, mode="6v6") -> None:
        """Remakes a game into a new game of a different size and retains Players"""
        if self.game_on is False:
            raise GameNotOnError("No game on")

        players = []
        for index, _ in enumerate(self.teams):
            for _, player in enumerate(self.teams[index]):
                if player != self.empty_slot:
                    players.append(player)

        if isinstance(mode, int):
            self.team_size = mode
        elif isinstance(mode, str):
            if mode == "2v2":
                self.team_size = 2
            elif mode == "6v6":
                self.team_size = 6
            elif mode == "7v7":
                self.team_size = 7
            elif mode == "9v9":
                self.team_size = 9
            else:
                self.team_size = 6

        if len(players) > teams * self.team_size:
            raise CannotTransformError("Target game size too small.")

        self.stop()
        self.start()
        for player in players:
            self.add(player)

    def balance(self) -> None:
        """Uses a greedy sort to balance Players into teams based on their rating attribute"""
        if self.game_on is False:
            raise GameNotOnError("No game on")

        pool = []
        new_teams = []
        # Adds all players to the pool list
        for team in self.teams:
            for player in team:
                if player != self.empty_slot:
                    pool.append(player)

        # Sorts the pool list, highest rating first
        pool.sort(key=lambda x: x.rating, reverse=True)

        # Adds the right amount of empty lists to new_teams as there are current teams
        for _ in range(len(self.teams)):
            new_teams.append([])

        for player in range(len(pool)):
            # We put the highest rating player in the first team
            new_teams[0].append(pool.pop(0))
            # We sort the teams such that the lowest ranked team becomes new_teams[0]
            # So that we can add the next highest skilled player to that team
            new_teams.sort(key=lambda x: sum(i.rating for i in x), reverse=False)
        self.teams = new_teams

    def _team_count(self, team: list) -> int:
        player_count = 0
        for player in team:
            if player != self.empty_slot:
                player_count += 1
        return player_count

    def _is_full(self, team: list) -> bool:
        return bool(self._team_count(team) == len(team))


# Errors
class InvalidTeamError(ValueError):
    """Error raised when a player is attempted to be added to a team that does not exist"""


class TeamFullError(ValueError):
    """Error raised when a team is full and a player is attempted to be added anyway"""


class PlayerAddedError(ValueError):
    """Error raised when a player is already added and is attempted to be added again"""


class PlayerNotAddedError(ValueError):
    """Error raised when a player is attempted to be removed but is not added"""


class GameFullError(ValueError):
    """Error raised when the game is full and more players are attempted to be added"""


class GameOnError(ValueError):
    """Error raised when the game on state prevents another action such as starting a game again"""


class GameNotOnError(ValueError):
    """Error raised when there is no pickup game currently started"""


class CannotTransformError(ValueError):
    """Error raised when a pickup game of one size cannot be transformed to another size"""


if __name__ == "__main__":
    game = Game("sixes")
    game.start()
    russ = Player("russ", 0, 0)
    game.add(russ)
    status = game.pretty_status()
    print(status)
    game.restart("test")
    game.add(russ)
    status = game.pretty_status()
    print(status)
