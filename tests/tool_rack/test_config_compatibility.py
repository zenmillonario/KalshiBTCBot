import unittest
from pathlib import Path

from strategy_core.compatibility import ToolName, compatibility
from strategy_core.config_loader import load_rail_config


class ConfigAndCompatibilityTests(unittest.TestCase):
    def test_rail_config_is_external_and_loadable(self):
        root = Path(__file__).resolve().parents[2]
        cfg = load_rail_config(
            root / "strategy_core" / "config" / "rail.json"
        )
        self.assertEqual(cfg.size_tier, 25.0)
        self.assertEqual(cfg.first_60s_max, 0.40)
        self.assertEqual(cfg.sec_60_120_max, 0.42)
        self.assertEqual(cfg.sec_120_240_max, 0.44)
        self.assertTrue(cfg.reentry_after_exit)

    def test_rail_release_watcher_allowed(self):
        rule = compatibility(
            ToolName.RAIL,
            ToolName.RELEASE_WATCHER,
        )
        self.assertTrue(rule.allowed)

    def test_rail_opposite_fade_forbidden(self):
        rule = compatibility(
            ToolName.RAIL,
            ToolName.OPPOSITE_FADE,
        )
        self.assertFalse(rule.allowed)

    def test_unknown_pair_defaults_to_forbidden(self):
        rule = compatibility(
            ToolName.RAIL,
            ToolName.MARKET_HEIST,
        )
        self.assertFalse(rule.allowed)


if __name__ == "__main__":
    unittest.main()
