import unittest

from strategy_core.tools.heist import (
    MarketHeistTool,
)
from strategy_core.types import (
    Action,
    MarketSnapshot,
    Side,
)


class MarketHeistToolTests(
    unittest.TestCase
):
    def snap(
        self,
        *,
        yes=0.30,
        no=0.30,
        heist=None,
        ts=1000,
    ):
        return MarketSnapshot(
            now_ts=ts,
            ticker="KX1",
            contract_age_s=500,
            yes_ask=yes,
            no_ask=no,
            metadata={
                "heist": (
                    heist
                    or {}
                )
            },
        )

    def test_h1_unresolved_compression_waits(self):
        tool = MarketHeistTool(
            territory_id="HEIST_001"
        )
        intent = list(
            tool.on_activate(
                self.snap(
                    heist={
                        "qualified_box": False
                    }
                )
            )
        )[0]
        self.assertEqual(
            intent.action,
            Action.WAIT,
        )
        self.assertEqual(
            intent.reason,
            "HEIST_COMPRESSION_UNRESOLVED_WAIT",
        )

    def test_h2_lower_edge_buys_yes(self):
        tool = MarketHeistTool(
            territory_id="HEIST_001"
        )
        intent = list(
            tool.on_activate(
                self.snap(
                    yes=0.28,
                    heist={
                        "qualified_box": True,
                        "at_lower_edge": True,
                        "at_upper_edge": False,
                        "box_id": "B1",
                        "visit_id": "L1",
                    },
                )
            )
        )[0]
        self.assertEqual(
            intent.action,
            Action.ENTER,
        )
        self.assertEqual(
            intent.side,
            Side.YES,
        )

    def test_h3_upper_edge_buys_no(self):
        tool = MarketHeistTool(
            territory_id="HEIST_001"
        )
        intent = list(
            tool.on_activate(
                self.snap(
                    no=0.27,
                    heist={
                        "qualified_box": True,
                        "at_lower_edge": False,
                        "at_upper_edge": True,
                        "box_id": "B1",
                        "visit_id": "U1",
                    },
                )
            )
        )[0]
        self.assertEqual(
            intent.action,
            Action.ENTER,
        )
        self.assertEqual(
            intent.side,
            Side.NO,
        )

    def test_h4_ema_lean_favors_aligned_edge_without_erasing_box(self):
        tool = MarketHeistTool(
            territory_id="HEIST_001"
        )
        aligned = list(
            tool.on_activate(
                self.snap(
                    no=0.30,
                    heist={
                        "qualified_box": True,
                        "at_upper_edge": True,
                        "at_lower_edge": False,
                        "box_id": "B1",
                        "visit_id": "U1",
                        "lean_side": "NO",
                    },
                )
            )
        )[0]
        self.assertEqual(
            aligned.side,
            Side.NO,
        )
        self.assertEqual(
            aligned.size_tier,
            15.0,
        )
        self.assertIn(
            "ALIGNED_WITH_EMA_LEAN",
            aligned.reason,
        )

    def test_h5_release_stops_box_fades_immediately(self):
        tool = MarketHeistTool(
            territory_id="HEIST_001"
        )
        intent = list(
            tool.on_activate(
                self.snap(
                    no=0.25,
                    heist={
                        "qualified_box": True,
                        "at_upper_edge": True,
                        "release_confirmed": True,
                        "release_side": "NO",
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
            "HEIST_RELEASE_CONFIRMED_STOP_FADING_BOX",
        )

    def test_h6_new_edge_visit_can_trade_after_prior_position_closed(self):
        tool = MarketHeistTool(
            territory_id="HEIST_001"
        )
        first = list(
            tool.on_activate(
                self.snap(
                    yes=0.30,
                    heist={
                        "qualified_box": True,
                        "at_lower_edge": True,
                        "box_id": "B1",
                        "visit_id": "L1",
                    },
                )
            )
        )[0]
        tool.mark_entry_filled(
            first.opportunity_id
        )
        tool.mark_position_closed()

        second = list(
            tool.on_market_event(
                self.snap(
                    no=0.30,
                    ts=1100,
                    heist={
                        "qualified_box": True,
                        "at_upper_edge": True,
                        "box_id": "B1",
                        "visit_id": "U1",
                    },
                )
            )
        )[0]
        self.assertEqual(
            second.action,
            Action.ENTER,
        )
        self.assertEqual(
            second.side,
            Side.NO,
        )
        self.assertNotEqual(
            first.opportunity_id,
            second.opportunity_id,
        )


if __name__ == "__main__":
    unittest.main()
