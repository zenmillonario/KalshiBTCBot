import unittest

from strategy_core.tools.mountain import (
    AlternatingMountainTool,
)
from strategy_core.types import (
    Action,
    MarketSnapshot,
    Side,
)


class MountainToolAcceptanceTests(
    unittest.TestCase
):
    def snap(
        self,
        *,
        yes=0.30,
        no=0.30,
        mountain=None,
        ts=1000,
    ):
        return MarketSnapshot(
            now_ts=ts,
            ticker="KX1",
            contract_age_s=500,
            yes_ask=yes,
            no_ask=no,
            metadata={
                "mountain": (
                    mountain
                    or {}
                )
            },
        )

    def test_m1_midleg_12c_is_wait_not_entry(self):
        tool = AlternatingMountainTool(
            territory_id="MOUNTAIN_001",
            owner_side=Side.YES,
        )
        intent = list(
            tool.on_activate(
                self.snap(
                    no=0.12,
                    mountain={
                        "owner_side": "YES",
                        "mature_edge": False,
                    },
                )
            )
        )[0]
        self.assertEqual(
            intent.action,
            Action.WAIT,
        )
        self.assertIn(
            "NEVER_MIDDLE",
            intent.reason,
        )

    def test_m2_mature_upper_edge_stall_relays_no(self):
        tool = AlternatingMountainTool(
            territory_id="MOUNTAIN_001",
            owner_side=Side.YES,
        )
        intent = list(
            tool.on_activate(
                self.snap(
                    no=0.30,
                    mountain={
                        "owner_side": "YES",
                        "mature_edge": True,
                        "edge_window_active": True,
                        "stall": True,
                        "edge_id": "TOP-1",
                    },
                )
            )
        )[0]
        self.assertEqual(
            intent.action,
            Action.RELAY,
        )
        self.assertEqual(
            intent.side,
            Side.NO,
        )

    def test_m3_mature_lower_edge_failed_reextension_relays_yes(self):
        tool = AlternatingMountainTool(
            territory_id="MOUNTAIN_001",
            owner_side=Side.NO,
        )
        intent = list(
            tool.on_activate(
                self.snap(
                    yes=0.28,
                    mountain={
                        "owner_side": "NO",
                        "mature_edge": True,
                        "edge_window_active": True,
                        "failed_reextension": True,
                        "edge_id": "BOTTOM-1",
                    },
                )
            )
        )[0]
        self.assertEqual(
            intent.action,
            Action.RELAY,
        )
        self.assertEqual(
            intent.side,
            Side.YES,
        )

    def test_m4_strong_active_release_defers_fade(self):
        tool = AlternatingMountainTool(
            territory_id="MOUNTAIN_001",
            owner_side=Side.YES,
        )
        intent = list(
            tool.on_activate(
                self.snap(
                    no=0.20,
                    mountain={
                        "owner_side": "YES",
                        "mature_edge": True,
                        "stall": True,
                        "strong_active_release": True,
                    },
                )
            )
        )[0]
        self.assertEqual(
            intent.action,
            Action.WAIT,
        )
        self.assertEqual(
            intent.reason,
            "MOUNTAIN_EDGE_DEFER_ACTIVE_RELEASE",
        )

    def test_m5_meaningful_retreat_can_relay_without_perfect_curl(self):
        tool = AlternatingMountainTool(
            territory_id="MOUNTAIN_001",
            owner_side=Side.YES,
        )
        intent = list(
            tool.on_activate(
                self.snap(
                    no=0.32,
                    mountain={
                        "owner_side": "YES",
                        "mature_edge": True,
                        "edge_window_active": True,
                        "meaningful_retreat": True,
                        "visible_ema9_curl": False,
                    },
                )
            )
        )[0]
        self.assertEqual(
            intent.action,
            Action.RELAY,
        )
        self.assertEqual(
            intent.side,
            Side.NO,
        )

    def test_m6_soft_price_ceiling_requires_value_exception(self):
        tool = AlternatingMountainTool(
            territory_id="MOUNTAIN_001",
            owner_side=Side.YES,
        )
        blocked = list(
            tool.on_activate(
                self.snap(
                    no=0.55,
                    mountain={
                        "owner_side": "YES",
                        "mature_edge": True,
                        "stall": True,
                        "premium_value_qualified": False,
                    },
                )
            )
        )[0]
        self.assertEqual(
            blocked.action,
            Action.WAIT,
        )

        allowed = list(
            tool.on_market_event(
                self.snap(
                    no=0.55,
                    ts=1001,
                    mountain={
                        "owner_side": "YES",
                        "mature_edge": True,
                        "stall": True,
                        "premium_value_qualified": True,
                    },
                )
            )
        )[0]
        self.assertEqual(
            allowed.action,
            Action.RELAY,
        )
        self.assertEqual(
            allowed.side,
            Side.NO,
        )


if __name__ == "__main__":
    unittest.main()
