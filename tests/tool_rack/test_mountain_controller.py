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


class MountainControllerTests(
    unittest.TestCase
):
    def evidence(
        self,
        side=Side.YES,
    ):
        return PhysicalEvidence(
            ema9_direction=side,
            alternating_mountain=True,
        )

    def snap(
        self,
        *,
        side=Side.YES,
        mature=True,
        no=0.30,
        yes=0.30,
        ts=1000,
    ):
        return MarketSnapshot(
            now_ts=ts,
            ticker="KX1",
            contract_age_s=500,
            yes_ask=yes,
            no_ask=no,
            metadata={
                "mountain": {
                    "owner_side": (
                        side.value
                    ),
                    "mature_edge": mature,
                    "edge_window_active": True,
                    "stall": mature,
                    "edge_id": (
                        f"EDGE-{ts}"
                    ),
                }
            },
        )

    def test_router_activates_mountain_tool_and_commander_accepts_relay(self):
        rack = ToolRackController()
        commander = OneCommander()
        snap = self.snap(
            side=Side.YES,
            no=0.30,
        )
        out = rack.observe(
            self.evidence(
                Side.YES
            ),
            snap,
        )
        decision = commander.decide(
            out.intents,
            snap,
        )
        self.assertEqual(
            out.owned_territory,
            Territory.ALTERNATING_MOUNTAIN,
        )
        self.assertEqual(
            out.active_tool,
            "ALTERNATING_MOUNTAIN",
        )
        self.assertEqual(
            decision.action,
            Action.RELAY,
        )
        self.assertEqual(
            decision.intent.side,
            Side.NO,
        )

    def test_mountain_territory_id_persists_after_relay_side_changes(self):
        rack = ToolRackController()
        first = rack.observe(
            self.evidence(
                Side.YES
            ),
            self.snap(
                side=Side.YES,
                no=0.30,
                ts=1000,
            ),
        )
        second = rack.observe(
            self.evidence(
                Side.NO
            ),
            self.snap(
                side=Side.NO,
                yes=0.30,
                ts=1100,
            ),
        )
        self.assertEqual(
            first.territory_id,
            second.territory_id,
        )
        self.assertEqual(
            second.owned_side,
            Side.NO,
        )
        self.assertEqual(
            second.ownership_reason,
            "MOUNTAIN_TERRITORY_PERSISTS_ACROSS_EDGE_RELAYS",
        )


if __name__ == "__main__":
    unittest.main()
