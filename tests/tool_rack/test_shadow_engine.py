import unittest

from strategy_core.shadow_engine import (
    ToolRackShadowEngine,
)
from strategy_core.shadow_frame import ShadowFrame


class ShadowEngineTests(unittest.TestCase):
    def frame(
        self,
        *,
        no=0.30,
        current=True,
        release=False,
        up=False,
    ):
        side = "YES" if up else "NO"
        other = (
            1.0 - no
            if not up
            else no
        )
        yes_ask = (
            no
            if up
            else other
        )
        no_ask = (
            other
            if up
            else no
        )
        return ShadowFrame.from_mapping(
            {
                "market": {
                    "now_ts": 1000,
                    "ticker": "KX1",
                    "contract_age_s": 20,
                    "yes_ask": yes_ask,
                    "no_ask": no_ask,
                    "quote_current": current,
                    "depth_available": True,
                },
                "physical": {
                    "ema9_direction": side,
                    "ema30_direction": side,
                    "ema_pair_parallel": True,
                    "directional_residence": True,
                    "rolling_mountain_repetitions": 2,
                    "contracts_persistent": 1.0,
                    "rolling_mountain": True,
                    "release_handoff_confirmed": release,
                    "release_side": (
                        side
                        if release
                        else None
                    ),
                },
            }
        )

    def test_shadow_output_is_auditable_30c_rail_enter(self):
        out = ToolRackShadowEngine().evaluate(
            self.frame(no=0.30)
        )
        self.assertEqual(
            out["owned_territory"],
            "DOWN_RAIL",
        )
        self.assertEqual(
            out["active_tool"],
            "RAIL",
        )
        self.assertEqual(
            out["commander_action"],
            "ENTER",
        )
        self.assertEqual(
            out["accepted_side"],
            "NO",
        )
        self.assertTrue(
            out["accepted_opportunity_id"]
        )
        self.assertEqual(
            out["accepted_observed_ask"],
            0.30,
        )
        self.assertEqual(
            out["accepted_max_price"],
            0.40,
        )

    def test_shadow_output_explains_objective_block(self):
        out = ToolRackShadowEngine().evaluate(
            self.frame(
                no=0.30,
                current=False,
            )
        )
        self.assertEqual(
            out["active_tool"],
            "RAIL",
        )
        self.assertEqual(
            out["commander_action"],
            "WAIT",
        )
        self.assertEqual(
            out["commander_reason"],
            "OBJECTIVE_QUOTE_STALE",
        )


if __name__ == "__main__":
    unittest.main()
