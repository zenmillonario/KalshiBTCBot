import unittest

from strategy_core.commander import OneCommander
from strategy_core.router import PhysicalEvidence
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import (
    Action,
    MarketSnapshot,
    Side,
    Territory,
)


class HeistControllerTests(
    unittest.TestCase
):
    def snap(
        self,
        *,
        heist,
        yes=0.30,
        no=0.30,
        ts=1000,
    ):
        return MarketSnapshot(
            now_ts=ts,
            ticker="KX1",
            contract_age_s=500,
            yes_ask=yes,
            no_ask=no,
            metadata={
                "heist": heist
            },
        )

    def test_heist_router_activates_tool_and_lower_edge_enters_yes(self):
        rack = ToolRackController()
        commander = OneCommander()
        evidence = PhysicalEvidence(
            ema9_direction=None,
            qualified_heist=True,
        )
        snap = self.snap(
            yes=0.28,
            heist={
                "qualified_box": True,
                "at_lower_edge": True,
                "at_upper_edge": False,
                "box_id": "B1",
                "visit_id": "L1",
            },
        )
        out = rack.observe(
            evidence,
            snap,
        )
        decision = commander.decide(
            out.intents,
            snap,
        )
        self.assertEqual(
            out.owned_territory,
            Territory.MARKET_HEIST,
        )
        self.assertEqual(
            out.active_tool,
            "MARKET_HEIST",
        )
        self.assertEqual(
            decision.action,
            Action.ENTER,
        )
        self.assertEqual(
            decision.intent.side,
            Side.YES,
        )

    def test_heist_release_can_handoff_into_down_rail(self):
        rack = ToolRackController()
        heist_evidence = PhysicalEvidence(
            qualified_heist=True,
            ema9_direction=Side.NO,
        )
        rack.observe(
            heist_evidence,
            self.snap(
                heist={
                    "qualified_box": True,
                    "at_upper_edge": True,
                    "box_id": "B1",
                    "visit_id": "U1",
                },
            ),
        )

        rail_evidence = PhysicalEvidence(
            ema9_direction=Side.NO,
            ema30_direction=Side.NO,
            ema_pair_parallel=True,
            directional_residence=True,
            rolling_mountain_repetitions=2,
            contracts_persistent=1.0,
            rolling_mountain=True,
            release_handoff_confirmed=True,
            release_side=Side.NO,
        )
        out = rack.observe(
            rail_evidence,
            self.snap(
                ts=1100,
                no=0.30,
                yes=0.70,
                heist={
                    "qualified_box": False,
                    "release_confirmed": True,
                    "release_side": "NO",
                },
            ),
        )
        self.assertEqual(
            out.owned_territory,
            Territory.DOWN_RAIL,
        )
        self.assertEqual(
            out.active_tool,
            "RAIL",
        )
        self.assertEqual(
            out.intents[0].action,
            Action.ENTER,
        )
        self.assertEqual(
            out.intents[0].side,
            Side.NO,
        )


if __name__ == "__main__":
    unittest.main()
