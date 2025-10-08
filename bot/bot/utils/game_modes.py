"""TF2 Game Modes"""

import yaml
from pathlib import Path


class GameMode:
    """Sets a Pickup game mode"""

    def __init__(self, config_file, mode: str):
        self.config_file = config_file
        self.mode = mode
        self.load_config()

    def load_config(self):
        """Loads config from yaml"""
        my_path = Path(__file__).resolve()  # resolve to get rid of any symlinks
        config_path = my_path.parent / self.config_file
        with config_path.open() as file_stream:
            try:
                config = yaml.safe_load(file_stream)
                game_config = config["game_modes"][self.mode]
                self.teams = game_config["teams"]
                self.players = game_config["players"]
                self.map_pool = game_config["map_pool"]
                server_pool = []
                for server in game_config["servers"]:
                    server_pool.append((server["address"], server["port"]))
                self.server_pool = server_pool
            except yaml.YAMLError as exc:
                print(exc)


if __name__ == "__main__":
    game_mode = GameMode("../configs/game_modes.yaml", "sixes")
    print(game_mode.server_pool)
