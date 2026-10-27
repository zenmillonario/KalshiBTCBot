import unittest

from strategy_core.tools.rail import RailTool
from strategy_core.types import Action, MarketSnapshot, Side


class RailToolAcceptanceTests(unittest.TestCase):
    def snap(
        self,
        *,
        ts,
        ticker="KX1",
        age=20,
        yes=0.70,
        no=0.30,
        current=True,
        depth=True,
    ):
        return MarketSnapshot(
            now_ts=ts,
            ticker=ticker,
            contract_age_s=age,
            yes_ask=yes,
            no_ask=no,
            quote_current=current,
            depth_available=depth,
        )

    def test_r1_down_rail_new_contract_30c_enters_25(self):
        tool = RailTool(
            territory_id="DOWN_RAIL_004",
            side=Side.NO,
            activated_at=1000,
        )
        intent = list(tool.on_activate(self.snap(ts=1020, no=0.30)))[0]
        self.assertEqual(intent.action, Action.ENTER)
        self.assertEqual(intent.side, Side.NO)
        self.assertEqual(intent.size_tier, 25.0)
        self.assertEqual(intent.max_price, 0.40)

    def test_r2_expensive_wait_does_not_consume_then_30c_enters(self):
        tool = RailTool(
            territory_id="DOWN_RAIL_004",
            side=Side.NO,
            activated_at=1000,
        )
        first = list(tool.on_activate(self.snap(ts=1020, no=0.58)))[0]
        self.assertEqual(first.action, Action.WAIT)
        second = list(
            tool.on_market_event(self.snap(ts=1030, no=0.30, age=30))
        )[0]
        self.assertEqual(second.action, Action.ENTER)
        self.assertEqual(second.opportunity_id, first.opportunity_id)

    def test_r3_profit_exit_rearms_same_rail_reentry(self):
        tool = RailTool(
            territory_id="DOWN_RAIL_004",
            side=Side.NO,
            activated_at=1000,
        )
        first = list(tool.on_activate(self.snap(ts=1020, no=0.35)))[0]
        self.assertEqual(first.action, Action.ENTER)
        tool.mark_entry_filled(first.opportunity_id)

        held = list(
            tool.on_market_event(self.snap(ts=1040, no=0.36, age=40))
        )[0]
        self.assertEqual(held.action, Action.WAIT)
        self.assertEqual(held.reason, "RAIL_POSITION_ALREADY_OPEN")

        tool.mark_position_closed(release_handoff=False)
        reentry = list(
            tool.on_market_event(self.snap(ts=1050, no=0.36, age=50))
        )[0]
        self.assertEqual(reentry.action, Action.ENTER)
        self.assertNotEqual(reentry.opportunity_id, first.opportunity_id)

    def test_r4_rollover_creates_fresh_slice_same_physical_rail(self):
        tool = RailTool(
            territory_id="DOWN_RAIL_004",
            side=Side.NO,
            activated_at=1000,
        )
        first = list(
            tool.on_activate(self.snap(ts=1020, ticker="KX1", no=0.35))
        )[0]
        tool.mark_entry_filled(first.opportunity_id)

        rollover = list(
            tool.on_market_event(
                self.snap(ts=1905, ticker="KX2", age=5, no=0.30)
            )
        )[0]
        self.assertEqual(rollover.action, Action.ENTER)
        self.assertIn("KX2", rollover.opportunity_id)

    def test_r5_release_handoff_ends_reentry_cycle(self):
        tool = RailTool(
            territory_id="DOWN_RAIL_004",
            side=Side.NO,
            activated_at=1000,
        )
        first = list(tool.on_activate(self.snap(ts=1020, no=0.35)))[0]
        tool.mark_entry_filled(first.opportunity_id)
        tool.mark_position_closed(release_handoff=True)

        self.assertFalse(tool.active)
        after = list(tool.on_market_event(self.snap(ts=1030, no=0.30)))
        self.assertEqual(after, [])

    def test_objective_safety_still_blocks(self):
        tool = RailTool(
            territory_id="DOWN_RAIL_004",
            side=Side.NO,
            activated_at=1000,
        )
        stale = list(
            tool.on_activate(self.snap(ts=1020, no=0.30, current=False))
        )[0]
        self.assertEqual(stale.action, Action.WAIT)
        self.assertEqual(stale.reason, "OBJECTIVE_QUOTE_STALE")


if __name__ == "__main__":
    unittest.main()
