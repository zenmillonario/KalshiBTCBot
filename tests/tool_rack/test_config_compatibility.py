import unittest
from pathlib import Path

from strategy_core.compatibility import ToolName, compatibility
from strategy_core.config_loader import (
    load_default_tool_configs,
    load_rail_config,
)


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

    def test_all_tool_configs_load_from_separate_files(self):
        cfg = load_default_tool_configs()
        self.assertEqual(cfg.rail.size_tier, 25.0)
        self.assertEqual(cfg.mountain.regular_size, 10.0)
        self.assertEqual(cfg.mountain.a_plus_size, 15.0)
        self.assertEqual(cfg.mountain.exceptional_size, 25.0)
        self.assertEqual(cfg.heist.regular_size, 10.0)
        self.assertEqual(cfg.heist.lean_favored_size, 15.0)
        self.assertEqual(cfg.release.structural_size, 25.0)

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
