import unittest

from strategy_core.event_timeline import ShadowEventTimeline


def result(**overrides):
    base = {
        "territory_id": "DOWN_RAIL_0001",
        "owned_territory": "DOWN_RAIL",
        "owned_side": "NO",
        "active_tool": "RAIL",
        "active_overlays": ["RELEASE_WATCHER"],
        "ownership_reason": "RAIL",
        "commander_action": "ENTER",
        "commander_reason": "COMMANDER_ACCEPTED_TOOL_INTENT",
        "accepted_tool": "RAIL",
        "accepted_side": "NO",
        "accepted_opportunity_id": "OP1",
        "accepted_observed_ask": 0.30,
        "accepted_max_price": 0.40,
        "release_boundary_name": None,
        "handoff_confirmed": False,
        "release_transition_pending": False,
    }
    base.update(overrides)
    return base


class ShadowEventTimelineTests(unittest.TestCase):
    def test_repeated_identical_tick_does_not_flood_events(self):
        timeline = ShadowEventTimeline()
        first = timeline.observe(
            ts=1000,
            ticker="KX1",
            result=result(),
        )
        second = timeline.observe(
            ts=1001,
            ticker="KX1",
            result=result(),
        )
        self.assertEqual(len(first), 2)
        self.assertEqual(second, ())
        self.assertEqual(len(timeline.events), 2)

    def test_same_actionable_opportunity_is_not_re_emitted_after_wait_toggle(self):
        timeline = ShadowEventTimeline()
        timeline.observe(
            ts=1000,
            ticker="KX1",
            result=result(),
        )
        timeline.observe(
            ts=1001,
            ticker="KX1",
            result=result(
                commander_action="WAIT",
                commander_reason="OBJECTIVE_QUOTE_STALE",
                accepted_tool=None,
                accepted_side=None,
                accepted_opportunity_id=None,
                accepted_observed_ask=None,
                accepted_max_price=None,
            ),
        )
        repeat = timeline.observe(
            ts=1002,
            ticker="KX1",
            result=result(
                accepted_observed_ask=0.28,
            ),
        )
        self.assertEqual(repeat, ())
        actionable = [
            event
            for event in timeline.events
            if (
                event.event_type == "INTENT"
                and event.action in ("ENTER", "RELAY")
            )
        ]
        self.assertEqual(len(actionable), 1)

    def test_new_rail_slice_opportunity_records_new_intent_not_new_territory(self):
        timeline = ShadowEventTimeline()
        timeline.observe(ts=1000, ticker="KX1", result=result())
        new = timeline.observe(
            ts=1100,
            ticker="KX2",
            result=result(
                accepted_opportunity_id="OP2",
                accepted_observed_ask=0.35,
            ),
        )
        self.assertEqual(
            [event.event_type for event in new],
            ["INTENT"],
        )

    def test_release_records_handoff_then_transition_territory(self):
        timeline = ShadowEventTimeline()
        timeline.observe(ts=1000, ticker="KX1", result=result())

        release = timeline.observe(
            ts=1010,
            ticker="KX1",
            result=result(
                commander_action="WAIT",
                commander_reason="RELEASE_CONFIRMED_BUT_PRICE_ABOVE_SOFT_VALUE",
                accepted_tool=None,
                accepted_side=None,
                accepted_opportunity_id=None,
                accepted_observed_ask=None,
                accepted_max_price=None,
                release_boundary_name="PRICE_ABOVE_EMA9_AGAINST_OLD_OWNER",
                handoff_confirmed=True,
                release_transition_pending=True,
            ),
        )
        self.assertIn("HANDOFF", [event.event_type for event in release])

        transition = timeline.observe(
            ts=1020,
            ticker="KX1",
            result=result(
                territory_id="RELEASE_TRANSITION_0002",
                owned_territory="RELEASE_TRANSITION",
                owned_side="YES",
                active_tool=None,
                commander_action="WAIT",
                commander_reason="RELEASE_CONFIRMED_BUT_PRICE_ABOVE_SOFT_VALUE",
                accepted_tool=None,
                accepted_side=None,
                accepted_opportunity_id=None,
                accepted_observed_ask=None,
                accepted_max_price=None,
                release_boundary_name="RELEASE_TRANSITION_LATCHED",
                handoff_confirmed=True,
                release_transition_pending=False,
            ),
        )
        self.assertIn(
            "TERRITORY",
            [event.event_type for event in transition],
        )

    def test_changed_wait_reason_is_recorded_once(self):
        timeline = ShadowEventTimeline()
        timeline.observe(
            ts=1000,
            ticker="KX1",
            result=result(
                commander_action="WAIT",
                commander_reason="ASK_ABOVE_VALUE",
                accepted_tool=None,
                accepted_side=None,
                accepted_opportunity_id=None,
            ),
        )
        changed = timeline.observe(
            ts=1010,
            ticker="KX1",
            result=result(
                commander_action="WAIT",
                commander_reason="OBJECTIVE_QUOTE_STALE",
                accepted_tool=None,
                accepted_side=None,
                accepted_opportunity_id=None,
            ),
        )
        self.assertEqual(
            [event.event_type for event in changed],
            ["INTENT"],
        )


if __name__ == "__main__":
    unittest.main()
