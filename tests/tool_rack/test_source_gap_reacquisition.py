"""A fresh BTC sample cannot reuse pre-gap entry authority.

These fixtures pass actual timestamped BTC/EMA observations through the direct
measurement source, detectors, rack, Commander, and PAPER executioner. They
exercise physical reacquisition rather than a timer or a mocked classifier.
"""
from pathlib import Path
import tempfile
import unittest

from strategy_core.paper_runtime import ToolRackPaperEngine
from tests.tool_rack.test_direct_paper_runtime import BASE, capture, raw_rows


REACQUISITION_REASON = "PHYSICAL_CONTINUITY_RESET_AWAIT_TOOL_REACQUISITION"


def up_rows(start, stop, *, anchor=1200, epoch=1, base=79880):
    return tuple({
        "epoch_ms": (BASE + offset) * 1000,
        "btc_price": base + (offset - anchor) * .5 + 5,
        "ema9": base + (offset - anchor) * .5,
        "ema30": base + (offset - anchor) * .5 - 15,
        "connection_epoch": epoch,
        "sequence_num": offset,
    } for offset in range(start, stop + 1))


class SourceGapReacquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = ToolRackPaperEngine(Path(self.temp.name) / "SOURCE_GAP_FIXTURE")

    def tearDown(self):
        self.engine.close(reason="SOURCE_GAP_FIXTURE_COMPLETE")
        self.temp.cleanup()

    def process(self, frame):
        return self.engine.process(frame, now_ts=frame.observed_ts)

    def establish_unfilled_down_rail(self):
        result = self.process(capture(no_bid=.54, no_ask=.56))
        self.assertEqual(result["status"]["rack"]["owned_territory"], "DOWN_RAIL")
        self.assertEqual(result["status"]["physical"]["geometry_continuity_generation"], 0)
        self.assertFalse(result["status"]["awaiting_physical_reacquisition"])
        self.assertFalse(result["receipts"])
        return result

    def assert_entry_waits_for_reacquisition(self, result):
        self.assertTrue(result["status"]["awaiting_physical_reacquisition"])
        self.assertEqual(result["decisions"][-1]["decision"]["reason"], REACQUISITION_REASON)
        self.assertFalse(any(receipt.status == "BOOKED" for receipt in result["receipts"]))

    def test_one_fresh_row_after_actual_btc_gap_cannot_enter_retained_rail(self):
        before = self.establish_unfilled_down_rail()
        result = self.process(capture(1230, rows=raw_rows(1230, start=1230)))
        self.assertTrue(result["status"]["physical"]["physical_current"])
        self.assertEqual(result["status"]["physical"]["geometry_rows_used"], 1)
        self.assertEqual(result["status"]["physical"]["geometry_reset_reason"], "BTC_OBSERVATION_GAP")
        self.assertEqual(result["status"]["physical"]["geometry_continuity_generation"], 1)
        self.assertEqual(result["status"]["rack"]["raw_decision"]["territory"], "UNKNOWN")
        self.assertEqual(result["status"]["rack"]["territory_id"], before["status"]["rack"]["territory_id"])
        self.assert_entry_waits_for_reacquisition(result)
        self.assertFalse(self.engine.executor.positions)

    def test_epoch_change_blocks_even_without_a_long_observation_gap(self):
        self.establish_unfilled_down_rail()
        frame = capture(1201, rows=raw_rows(1201, start=1201, epoch=2))
        result = self.process(frame)
        self.assertEqual(result["status"]["physical"]["geometry_reset_reason"], "BTC_CONNECTION_EPOCH_CHANGED")
        self.assertEqual(result["status"]["physical"]["geometry_rows_used"], 1)
        self.assert_entry_waits_for_reacquisition(result)
        repeated = self.process(frame)
        self.assertEqual(repeated["status"]["physical"]["geometry_continuity_generation"], 1)
        self.assertEqual(repeated["status"]["physical"]["geometry_rows_used"], 1)
        self.assert_entry_waits_for_reacquisition(repeated)

    def test_fresh_qualified_rail_reacquires_without_an_arbitrary_cooldown(self):
        self.establish_unfilled_down_rail()
        self.assert_entry_waits_for_reacquisition(self.process(
            capture(1230, rows=raw_rows(1230, start=1230))))
        # Five minutes of fresh direction are still not a qualified Rail.
        partial = self.process(capture(1530, rows=raw_rows(1530, start=1231)))
        self.assertEqual(partial["status"]["physical"]["geometry_rows_used"], 301)
        self.assertFalse(partial["status"]["physical"]["territory_detector_summary"]["rail_established"])
        self.assert_entry_waits_for_reacquisition(partial)
        # Actual post-gap qualification clears on that observation, including
        # a new contract slice. No additional elapsed-time gate is introduced.
        recovered = self.process(capture(2130, ticker="KXBTC15M-FIXTURE-B", close=2980,
                                         rows=raw_rows(2130, start=1531)))
        self.assertEqual(recovered["status"]["physical"]["geometry_rows_used"], 901)
        self.assertEqual(recovered["status"]["rack"]["raw_decision"]["territory"], "DOWN_RAIL")
        self.assertFalse(recovered["status"]["awaiting_physical_reacquisition"])
        self.assertEqual([receipt.status for receipt in recovered["receipts"]], ["BOOKED"])
        self.assertEqual(recovered["receipts"][0].event["side"], "NO")

    def test_current_affirmative_release_can_reacquire_before_new_rail_qualification(self):
        self.establish_unfilled_down_rail()
        self.assert_entry_waits_for_reacquisition(self.process(capture(
            1230, no_bid=.70, no_ask=.72,
            rows=up_rows(1230, 1230, anchor=1230, epoch=2))))
        released = self.process(capture(1410, no_bid=.70, no_ask=.72,
            rows=up_rows(1231, 1410, anchor=1230, epoch=2)))
        rack = released["status"]["rack"]
        self.assertTrue(rack["handoff_confirmed"])
        self.assertEqual(rack["release_boundary_name"], "PRICE_ABOVE_EMA9_AGAINST_OLD_OWNER")
        self.assertNotEqual(rack["raw_decision"]["territory"], "UP_RAIL")
        self.assertFalse(released["status"]["awaiting_physical_reacquisition"])
        self.assertEqual([receipt.status for receipt in released["receipts"]], ["BOOKED"])
        self.assertEqual(released["receipts"][0].event["tool"], "RELEASE_WATCHER")
        self.assertEqual(released["receipts"][0].event["side"], "YES")

    def test_old_latched_release_cannot_clear_post_reset_reacquisition(self):
        self.establish_unfilled_down_rail()
        released = self.process(capture(1260, no_bid=.30, no_ask=.32,
                                        rows=up_rows(1201, 1260)))
        self.assertTrue(released["status"]["rack"]["handoff_confirmed"])
        self.assertFalse(released["receipts"])
        # The earlier genuine release remains the owner. It is not fresh
        # evidence authorizing a new fill after source continuity is lost.
        reset = self.process(capture(1300, no_bid=.70, no_ask=.72,
                                     rows=up_rows(1300, 1300, epoch=2)))
        self.assertEqual(reset["status"]["physical"]["geometry_rows_used"], 1)
        self.assertEqual(reset["status"]["rack"]["owned_territory"], "RELEASE_TRANSITION")
        self.assertEqual(reset["status"]["rack"]["raw_decision"]["territory"], "UNKNOWN")
        self.assertEqual(reset["status"]["rack"]["release_boundary_name"], "RELEASE_TRANSITION_LATCHED")
        self.assertTrue(reset["status"]["rack"]["handoff_confirmed"])
        self.assert_entry_waits_for_reacquisition(reset)
        self.assertFalse(self.engine.executor.positions)
        # A fully measured replacement owner is sufficient to clear the gate.
        recovered = self.process(capture(2200, ticker="KXBTC15M-FIXTURE-B", close=2980,
            no_bid=.70, no_ask=.72, rows=up_rows(1301, 2200, epoch=2)))
        self.assertEqual(recovered["status"]["rack"]["raw_decision"]["territory"], "UP_RAIL")
        self.assertEqual(recovered["status"]["rack"]["owned_territory"], "UP_RAIL")
        self.assertFalse(recovered["status"]["awaiting_physical_reacquisition"])
        self.assertEqual([receipt.status for receipt in recovered["receipts"]], ["BOOKED"])

    def test_reacquisition_retains_custody_and_does_not_suspend_armed_floor_exit(self):
        opened = self.process(capture())
        position_id = opened["receipts"][0].position_id
        self.process(capture(1201, no_bid=.66, no_ask=.68))
        before = self.engine.executor.positions[position_id]
        self.assertAlmostEqual(before.floor_bid, .594)
        held = self.process(capture(1230, no_bid=.64, no_ask=.66,
                                    rows=raw_rows(1230, start=1230)))
        self.assert_entry_waits_for_reacquisition(held)
        self.assertEqual(len(self.engine.executor.positions), 1)
        self.assertEqual(self.engine.executor.positions[position_id].opportunity_id, before.opportunity_id)
        self.assertEqual(held["decisions"][0]["decision"]["action"], "HOLD")
        broken = self.process(capture(1231, no_bid=.58, no_ask=.60,
                                      rows=raw_rows(1231, start=1231)))
        self.assert_entry_waits_for_reacquisition(broken)
        self.assertEqual([receipt.status for receipt in broken["receipts"]], ["EXITED"])
        self.assertFalse(self.engine.executor.positions)
        self.assertEqual(broken["decisions"][0]["decision"]["action"], "EXIT")
        self.assertFalse(self.engine.rack._filled_tools)
        next_quote = self.process(capture(1232, rows=raw_rows(1232, start=1232)))
        self.assert_entry_waits_for_reacquisition(next_quote)
        self.assertEqual([event["event"] for event in self.engine.executor.events], ["ENTRY", "EXIT"])

    def test_new_reverse_release_can_reacquire_from_retained_release_custody(self):
        self.establish_unfilled_down_rail()
        released = self.process(capture(1260, no_bid=.30, no_ask=.32,
                                        rows=up_rows(1201, 1260)))
        self.assertTrue(released["status"]["rack"]["handoff_confirmed"])
        reset = self.process(capture(1300, rows=raw_rows(1300, start=1300, epoch=2)))
        self.assertEqual(reset["status"]["rack"]["owned_territory"], "RELEASE_TRANSITION")
        self.assertEqual(reset["status"]["rack"]["owned_side"], "YES")
        self.assert_entry_waits_for_reacquisition(reset)
        reversal = self.process(capture(1480, rows=raw_rows(1480, start=1301, epoch=2)))
        rack = reversal["status"]["rack"]
        self.assertTrue(rack["handoff_confirmed"])
        self.assertEqual(rack["release_boundary_name"], "PRICE_BELOW_EMA9_AGAINST_OLD_OWNER")
        self.assertTrue(rack["release_transition_pending"])
        self.assertNotEqual(rack["raw_decision"]["territory"], "DOWN_RAIL")
        self.assertFalse(reversal["status"]["awaiting_physical_reacquisition"])
        self.assertEqual([receipt.status for receipt in reversal["receipts"]], ["BOOKED"])
        self.assertEqual(reversal["receipts"][0].event["tool"], "RELEASE_WATCHER")
        self.assertEqual(reversal["receipts"][0].event["side"], "NO")


if __name__ == "__main__":
    unittest.main()
