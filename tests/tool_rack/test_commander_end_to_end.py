import unittest

from strategy_core.commander import OneCommander
from strategy_core.router import PhysicalEvidence
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, MarketSnapshot, Side


class FakePaperExecutor:
    def __init__(self):
        self.fills = []

    def execute(self, decision, snapshot):
        if (
            decision.action is not Action.ENTER
            or decision.intent is None
        ):
            return None
        fill = {
            "ticker": snapshot.ticker,
            "side": decision.intent.side,
            "price": snapshot.ask_for(decision.intent.side),
            "size_tier": decision.intent.size_tier,
            "opportunity_id": decision.intent.opportunity_id,
        }
        self.fills.append(fill)
        return fill


class RailEndToEndAcceptanceTests(unittest.TestCase):
    def evidence(self):
        return PhysicalEvidence(
            ema9_direction=Side.NO,
            ema30_direction=Side.NO,
            ema_pair_parallel=True,
            directional_residence=True,
            rolling_mountain_repetitions=2,
            contracts_persistent=1.0,
            rolling_mountain=True,
        )

    def snap(
        self,
        *,
        no=0.30,
        current=True,
        depth=True,
        ticker="KX1",
        age=20,
        ts=1000,
    ):
        return MarketSnapshot(
            now_ts=ts,
            ticker=ticker,
            contract_age_s=age,
            yes_ask=1.0 - no,
            no_ask=no,
            quote_current=current,
            depth_available=depth,
        )

    def test_source_router_tool_commander_executor_30c_down_rail(self):
        rack = ToolRackController()
        commander = OneCommander()
        executor = FakePaperExecutor()
        snap = self.snap(no=0.30)

        shadow = rack.observe(self.evidence(), snap)
        decision = commander.decide(shadow.intents, snap)
        fill = executor.execute(decision, snap)

        self.assertEqual(decision.action, Action.ENTER)
        self.assertIsNotNone(fill)
        self.assertEqual(fill["side"], Side.NO)
        self.assertEqual(fill["price"], 0.30)
        self.assertEqual(fill["size_tier"], 25.0)

    def test_stale_quote_blocked_by_commander_not_rail_tool(self):
        rack = ToolRackController()
        commander = OneCommander()
        snap = self.snap(no=0.30, current=False)

        shadow = rack.observe(self.evidence(), snap)
        self.assertEqual(
            shadow.intents[0].action,
            Action.ENTER,
        )
        decision = commander.decide(
            shadow.intents,
            snap,
        )

        self.assertEqual(decision.action, Action.WAIT)
        self.assertEqual(
            decision.reason,
            "OBJECTIVE_QUOTE_STALE",
        )

    def test_depth_blocked_by_commander_not_rail_tool(self):
        rack = ToolRackController()
        commander = OneCommander()
        snap = self.snap(no=0.30, depth=False)

        shadow = rack.observe(self.evidence(), snap)
        self.assertEqual(
            shadow.intents[0].action,
            Action.ENTER,
        )
        decision = commander.decide(
            shadow.intents,
            snap,
        )

        self.assertEqual(decision.action, Action.WAIT)
        self.assertEqual(
            decision.reason,
            "OBJECTIVE_DEPTH_UNAVAILABLE",
        )

    def test_price_move_rechecked_at_commander_boundary(self):
        rack = ToolRackController()
        commander = OneCommander()
        original = self.snap(no=0.30)
        shadow = rack.observe(
            self.evidence(),
            original,
        )

        moved = self.snap(no=0.55, ts=1001)
        decision = commander.decide(
            shadow.intents,
            moved,
        )

        self.assertEqual(decision.action, Action.WAIT)
        self.assertEqual(
            decision.reason,
            "OBJECTIVE_PRICE_MOVED_ABOVE_TOOL_LIMIT",
        )


if __name__ == "__main__":
    unittest.main()
