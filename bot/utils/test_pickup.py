"""Tests pickup.py"""

# coverage run --source=pauling -m unittest discover -s pauling/utils/
# coverage report -m
# coverage html

import unittest
try:
    from .pickup import Game
except ImportError:
    from pickup import Game

class TestGame(unittest.TestCase):
    """Tests the Game class from pickup.py"""

    def test_start(self):
        """Tests start()"""
        game = Game("sixes")
        game.start()
        self.assertEqual(game.team_size, 6)
        self.assertEqual(game.teams_count, 2)
        self.assertEqual(
            game.map_pool,
            [
                "cp_prolands_rc2p",
                "cp_freight_final1",
                "cp_granary_pro_rc8",
                "cp_gullywash_final1",
                "cp_metalworks",
                "cp_process_final",
                "cp_sunshine",
                "cp_snakewater_final1",
                "cp_reckoner_rc6",
                "cp_villa_b15",
                "koth_product_rcx",
                "koth_clearcut_b15c",
                "cp_logjam_rc12f",
                "koth_bagel_fall_b7",
            ],
        )
        self.assertEqual(
            game.server_pool, [("jhb1.rsa.tf", 27015), ("jhb1.rsa.tf", 27025)]
        )
        self.assertEqual(game.teams, [['?', '?', '?', '?', '?', '?'], ['?', '?', '?', '?', '?', '?']])
        self.assertEqual(game.max_players, 12)
        self.assertEqual(game.player_count, 0)
        self.assertTrue(game.game_on)

    def test_stop(self):
        """Tests stop()"""
        game = Game("sixes")
        game.start()
        game.stop()
        self.assertIsNone(game.team_size)
        self.assertIsNone(game.teams)
        self.assertIsNone(game.max_players)
        self.assertIsNone(game.player_count)
        self.assertFalse(game.game_on)
        self.assertFalse(game.game_full)

    def test_restart(self):
        """Tests restart()"""
        game = Game("sixes")
        game.start()
        game.restart()
        self.assertEqual(game.team_size, 6)
        self.assertEqual(game.teams_count, 2)
        self.assertEqual(
            game.map_pool,
            [
                "cp_prolands_rc2p",
                "cp_freight_final1",
                "cp_granary_pro_rc8",
                "cp_gullywash_final1",
                "cp_metalworks",
                "cp_process_final",
                "cp_sunshine",
                "cp_snakewater_final1",
                "cp_reckoner_rc6",
                "cp_villa_b15",
                "koth_product_rcx",
                "koth_clearcut_b15c",
                "cp_logjam_rc12f",
                "koth_bagel_fall_b7",
            ],
        )
        self.assertEqual(
            game.server_pool, [("jhb1.rsa.tf", 27015), ("jhb1.rsa.tf", 27025)]
        )
        self.assertEqual(game.teams, [['?', '?', '?', '?', '?', '?'], ['?', '?', '?', '?', '?', '?']])
        self.assertEqual(game.max_players, 12)
        self.assertEqual(game.player_count, 0)
        self.assertTrue(game.game_on)

if __name__ == "__main__":
    unittest.main()
