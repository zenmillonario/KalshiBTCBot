import unittest

from strategy_core.router import PhysicalEvidence
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, MarketSnapshot, Side, Territory


class ReleaseTransitionControllerTests(unittest.TestCase):
    def snap(
        self,
        *,
        ts,
        yes=0.70,
        no=0.30,
        age=20,
    ):
        return MarketSnapshot(
            now_ts=ts,
            ticker="KX1",
            contract_age_s=age,
            yes_ask=yes,
            no_ask=no,
        )

    def down_rail(self, **overrides):
        values = dict(
            ema9_direction=Side.NO,
            ema30_direction=Side.NO,
            ema_pair_parallel=True,
            directional_residence=True,
            contracts_persistent=1.0,
            rolling_mountain=True,
        )
        values.update(overrides)
        return PhysicalEvidence(**values)

    def up_rail(self):
        return PhysicalEvidence(
            ema9_direction=Side.YES,
            ema30_direction=Side.YES,
            ema_pair_parallel=True,
            directional_residence=True,
            contracts_persistent=1.0,
            rolling_mountain=True,
        )

    def confirmed_up_release(self):
        return self.down_rail(
            release_candidate_side=Side.YES,
            release_boundary_break=True,
            release_directional_expansion=True,
            release_old_owner_failed_reextension=True,
        )

    def test_expensive_confirmed_release_ends_old_rail_without_fill(self):
        rack = ToolRackController()

        first = rack.observe(
            self.down_rail(),
            self.snap(ts=1000, no=0.30),
        )
        self.assertEqual(first.owned_territory, Territory.DOWN_RAIL)
        self.assertEqual(first.intents[0].action, Action.ENTER)
        self.assertEqual(first.intents[0].side, Side.NO)

        release = rack.observe(
            self.confirmed_up_release(),
            self.snap(ts=1010, yes=0.70, no=0.30),
        )
        self.assertTrue(release.handoff_confirmed)
        self.assertTrue(release.release_transition_pending)
        self.assertEqual(release.owned_territory, Territory.DOWN_RAIL)
        self.assertEqual(release.intents[0].tool, "RELEASE_WATCHER")
        self.assertEqual(release.intents[0].action, Action.WAIT)
        self.assertIn(
            "SUPPRESSES_OLD_TERRITORY",
            release.lane_resolution_reason,
        )

        # No release fill/commit is required for the physical territory to end.
        # A lagging old DOWN classifier cannot regain authority.
        transition = rack.observe(
            self.down_rail(),
            self.snap(ts=1020, yes=0.65, no=0.30),
        )
        self.assertEqual(
            transition.owned_territory,
            Territory.RELEASE_TRANSITION,
        )
        self.assertIsNone(transition.active_tool)
        self.assertEqual(
            transition.active_overlays,
            ("RELEASE_WATCHER",),
        )
        self.assertNotEqual(
            transition.raw_decision.side,
            transition.owned_side,
        )

        # When the new side becomes a real tool territory, ownership transfers.
        acquired = rack.observe(
            self.up_rail(),
            self.snap(ts=1030, yes=0.30, no=0.70),
        )
        self.assertEqual(acquired.owned_territory, Territory.UP_RAIL)
        self.assertEqual(acquired.active_tool, "RAIL")
        self.assertEqual(acquired.intents[0].action, Action.ENTER)
        self.assertEqual(acquired.intents[0].side, Side.YES)

    def test_release_transition_does_not_accept_wrong_side_mountain(self):
        rack = ToolRackController()
        rack.observe(
            self.down_rail(),
            self.snap(ts=1000, no=0.30),
        )
        rack.observe(
            self.confirmed_up_release(),
            self.snap(ts=1010, yes=0.30, no=0.30),
        )

        wrong = PhysicalEvidence(
            ema9_direction=Side.NO,
            alternating_mountain=True,
        )
        out = rack.observe(
            wrong,
            self.snap(ts=1020, yes=0.35, no=0.35),
        )
        self.assertEqual(out.owned_territory, Territory.RELEASE_TRANSITION)
        self.assertIsNone(out.active_tool)


if __name__ == "__main__":
    unittest.main()
