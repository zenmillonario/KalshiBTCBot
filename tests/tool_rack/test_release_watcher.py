import unittest

from strategy_core.lane_resolver import LaneResolver
from strategy_core.tools.release import (
    ReleaseEvidence,
    ReleaseWatcher,
)
from strategy_core.types import (
    Action,
    Lane,
    MarketSnapshot,
    Side,
    ToolIntent,
)


class ReleaseWatcherTests(unittest.TestCase):
    def snap(
        self,
        *,
        yes=0.30,
        no=0.30,
        ts=1000,
    ):
        return MarketSnapshot(
            now_ts=ts,
            ticker="KX1",
            contract_age_s=400,
            yes_ask=yes,
            no_ask=no,
        )

    def watcher(
        self,
        evidence,
        owner=Side.NO,
    ):
        tool = ReleaseWatcher(
            territory_id="DOWN_RAIL_001",
            owner_side=owner,
        )
        tool.update_evidence(evidence)
        return tool

    def test_first_slowdown_is_watch_not_handoff(self):
        tool = self.watcher(
            ReleaseEvidence(
                candidate_side=Side.YES,
                first_slowdown_only=True,
            )
        )
        intent = list(
            tool.on_activate(self.snap())
        )[0]
        self.assertEqual(intent.action, Action.WAIT)
        self.assertIn("FIRST_SLOWDOWN", intent.reason)

    def test_boundary_break_without_expansion_is_not_release(self):
        tool = self.watcher(
            ReleaseEvidence(
                candidate_side=Side.YES,
                boundary_break=True,
                directional_expansion=False,
                old_owner_failed_reextension=True,
            )
        )
        intent = list(
            tool.on_activate(self.snap())
        )[0]
        self.assertEqual(intent.action, Action.WAIT)

    def test_confirmed_release_emits_handoff_leviathan_relay(self):
        tool = self.watcher(
            ReleaseEvidence(
                candidate_side=Side.YES,
                boundary_break=True,
                directional_expansion=True,
                old_owner_failed_reextension=True,
            )
        )
        intent = list(
            tool.on_activate(
                self.snap(yes=0.30)
            )
        )[0]
        self.assertEqual(intent.action, Action.RELAY)
        self.assertEqual(intent.lane, Lane.HANDOFF)
        self.assertEqual(intent.side, Side.YES)
        self.assertEqual(intent.size_tier, 25.0)
        self.assertEqual(
            intent.metadata["custody"],
            "LEVIATHAN_RELEASE",
        )

    def test_new_side_residence_can_confirm_without_old_owner_failure_flag(self):
        tool = self.watcher(
            ReleaseEvidence(
                candidate_side=Side.YES,
                boundary_break=True,
                directional_expansion=True,
                new_side_residence=True,
            )
        )
        intent = list(
            tool.on_activate(
                self.snap(yes=0.35)
            )
        )[0]
        self.assertEqual(intent.action, Action.RELAY)

    def test_lane_resolver_release_suppresses_outgoing_primary_entry(self):
        primary = ToolIntent(
            tool="RAIL",
            territory_id="DOWN_RAIL_001",
            lane=Lane.MAIN,
            side=Side.NO,
            action=Action.ENTER,
            opportunity_id="OLD",
            max_price=0.40,
            size_tier=25.0,
            reason="RAIL_MAIN_VALUE",
            source_time=1000,
        )
        release = ToolIntent(
            tool="RELEASE_WATCHER",
            territory_id="DOWN_RAIL_001",
            lane=Lane.HANDOFF,
            side=Side.YES,
            action=Action.RELAY,
            opportunity_id="NEW",
            max_price=0.50,
            size_tier=25.0,
            reason="RELEASE_CONFIRMED_LEVIATHAN_HANDOFF",
            source_time=1000,
        )
        out = LaneResolver().resolve(
            primary=(primary,),
            overlays=(release,),
        )
        self.assertEqual(len(out.intents), 1)
        self.assertEqual(
            out.intents[0].tool,
            "RELEASE_WATCHER",
        )

    def test_overlay_wait_never_blocks_valid_primary_entry(self):
        primary = ToolIntent(
            tool="RAIL",
            territory_id="DOWN_RAIL_001",
            lane=Lane.MAIN,
            side=Side.NO,
            action=Action.ENTER,
            opportunity_id="OLD",
            max_price=0.40,
            size_tier=25.0,
            reason="RAIL_MAIN_VALUE",
            source_time=1000,
        )
        watch = ToolIntent(
            tool="RELEASE_WATCHER",
            territory_id="DOWN_RAIL_001",
            lane=Lane.HANDOFF,
            side=Side.YES,
            action=Action.WAIT,
            opportunity_id=None,
            max_price=0.50,
            size_tier=None,
            reason="RELEASE_WATCHING_FOR_AFFIRMATIVE_TRANSFER",
            source_time=1000,
        )
        out = LaneResolver().resolve(
            primary=(primary,),
            overlays=(watch,),
        )
        self.assertEqual(len(out.intents), 1)
        self.assertEqual(out.intents[0].tool, "RAIL")


if __name__ == "__main__":
    unittest.main()
