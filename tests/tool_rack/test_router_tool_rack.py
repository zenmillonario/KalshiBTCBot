import unittest

from strategy_core.commander import OneCommander
from strategy_core.router import PhysicalEvidence, TerritoryRouter
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, MarketSnapshot, Side, Territory


class RouterAndToolRackTests(unittest.TestCase):
    def snap(
        self,
        *,
        ts=1000,
        ticker="KX1",
        age=20,
        yes=0.70,
        no=0.30,
    ):
        return MarketSnapshot(
            now_ts=ts,
            ticker=ticker,
            contract_age_s=age,
            yes_ask=yes,
            no_ask=no,
        )

    def down_rail_evidence(self, **overrides):
        values = dict(
            ema9_direction=Side.NO,
            ema30_direction=Side.NO,
            ema_pair_parallel=True,
            directional_residence=True,
            rolling_mountain_repetitions=2,
            contracts_persistent=1.0,
            rolling_mountain=True,
        )
        values.update(overrides)
        return PhysicalEvidence(**values)

    def test_router_acquires_down_rail_after_persistent_parallel_structure(self):
        d = TerritoryRouter().classify(self.down_rail_evidence())
        self.assertEqual(d.territory, Territory.DOWN_RAIL)
        self.assertEqual(d.side, Side.NO)

    def test_one_short_rolling_mountain_is_not_premature_rail(self):
        e = self.down_rail_evidence(
            rolling_mountain_repetitions=1,
            contracts_persistent=0.25,
        )
        d = TerritoryRouter().classify(e)
        self.assertEqual(d.territory, Territory.ROLLING_MOUNTAIN)

    def test_qualified_sideways_box_remains_heist_even_with_ema_lean(self):
        e = self.down_rail_evidence(qualified_heist=True)
        d = TerritoryRouter().classify(e)
        self.assertEqual(d.territory, Territory.MARKET_HEIST)
        self.assertEqual(d.side, Side.NO)

    def test_shadow_controller_turns_down_rail_into_30c_entry(self):
        rack = ToolRackController()
        result = rack.observe(
            self.down_rail_evidence(),
            self.snap(no=0.30),
        )
        self.assertEqual(
            result.owned_territory,
            Territory.DOWN_RAIL,
        )
        self.assertEqual(result.active_tool, "RAIL")
        self.assertEqual(
            result.active_overlays,
            ("RELEASE_WATCHER",),
        )
        self.assertEqual(result.intents[0].action, Action.ENTER)
        self.assertEqual(result.intents[0].side, Side.NO)
        self.assertEqual(result.intents[0].size_tier, 25.0)

    def test_rail_owner_survives_raw_classifier_flicker(self):
        rack = ToolRackController()
        rack.observe(
            self.down_rail_evidence(),
            self.snap(no=0.35),
        )
        flicker = PhysicalEvidence(
            ema9_direction=Side.NO,
            ema30_direction=None,
            ema_pair_parallel=False,
            directional_residence=False,
            rolling_mountain=False,
        )
        result = rack.observe(
            flicker,
            self.snap(ts=1010, no=0.36),
        )
        self.assertEqual(
            result.owned_territory,
            Territory.DOWN_RAIL,
        )
        self.assertIn(
            "LATCHED_RAIL_OWNER",
            result.ownership_reason,
        )

    def test_confirmed_release_suppresses_old_rail_then_next_beat_acquires_up_rail(self):
        rack = ToolRackController()
        commander = OneCommander()
        rack.observe(
            self.down_rail_evidence(),
            self.snap(no=0.35),
        )

        release = PhysicalEvidence(
            ema9_direction=Side.YES,
            ema30_direction=Side.YES,
            ema_pair_parallel=True,
            directional_residence=True,
            rolling_mountain_repetitions=2,
            contracts_persistent=1.0,
            rolling_mountain=True,
            release_candidate_side=Side.YES,
            release_boundary_break=True,
            release_directional_expansion=True,
            release_old_owner_failed_reextension=True,
        )
        snap = self.snap(
            ts=1100,
            yes=0.30,
            no=0.30,
        )
        result = rack.observe(release, snap)

        self.assertEqual(
            result.owned_territory,
            Territory.DOWN_RAIL,
        )
        self.assertEqual(len(result.intents), 1)
        self.assertEqual(
            result.intents[0].tool,
            "RELEASE_WATCHER",
        )
        self.assertEqual(
            result.intents[0].action,
            Action.RELAY,
        )
        self.assertEqual(
            result.intents[0].side,
            Side.YES,
        )

        decision = commander.decide(
            result.intents,
            snap,
        )
        self.assertEqual(decision.action, Action.RELAY)
        rack.commit_accepted_intent(
            decision.intent,
            snap,
        )

        next_result = rack.observe(
            PhysicalEvidence(
                ema9_direction=Side.YES,
                ema30_direction=Side.YES,
                ema_pair_parallel=True,
                directional_residence=True,
                rolling_mountain_repetitions=2,
                contracts_persistent=1.0,
                rolling_mountain=True,
            ),
            self.snap(
                ts=1110,
                yes=0.30,
                no=0.70,
            ),
        )
        self.assertEqual(
            next_result.owned_territory,
            Territory.UP_RAIL,
        )
        self.assertEqual(
            next_result.intents[0].action,
            Action.ENTER,
        )
        self.assertEqual(
            next_result.intents[0].side,
            Side.YES,
        )


if __name__ == "__main__":
    unittest.main()
