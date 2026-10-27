import json
from pathlib import Path
import tempfile
from types import MappingProxyType
import unittest
from unittest.mock import patch

from strategy_core.commander import CommanderDecision
from strategy_core.paper_execution import (
    FloorPolicy, OfficialResult, PaperBook, PaperExecutionError,
    PaperExecutioner, PriceLevel, nominal_taker_fee,
)
from strategy_core.types import Action, Lane, Side, ToolIntent


def book(ts=1000.0, *, ticker="KX1", quote_id=None, yes=.16, no="auto",
         yes_qty=1000, no_qty=1000, close_ts=1900.0, **kwargs):
    if no == "auto":
        no = round(1 - (yes if yes is not None else .16) - .01, 9)
    return PaperBook(ticker, quote_id or f"Q{ts}", ts, ts,
        () if yes is None else (PriceLevel(yes, yes_qty),),
        () if no is None else (PriceLevel(no, no_qty),), close_ts, **kwargs)


def decision(ts=1000.0, *, action=Action.ENTER, side=Side.YES,
             opportunity="EDGE1", limit=.17, budget=25, tool="MOUNTAIN",
             lane=Lane.TACTICAL, ticker="KX1"):
    intent = ToolIntent(tool, "T1", lane, side, action, opportunity,
                        limit, budget, "EXPLICIT_COMMANDER_TEST", ts,
                        metadata={"ticker": ticker})
    return CommanderDecision(action, intent, "COMMANDER_ACCEPTED_TOOL_INTENT")


class PaperExecutionAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name) / "run"
        self.executor = PaperExecutioner(self.run)

    def tearDown(self):
        self.executor.close()
        self.temp.cleanup()

    def enter(self, **kwargs):
        b = kwargs.pop("native", book())
        d = kwargs.pop("command", decision())
        return self.executor.execute(d, b, now_ts=b.observed_ts,
                                     command_id=kwargs.pop("command_id", "C1"), **kwargs)

    def exit(self, pid="1", *, ts=1040., bid=.27, quantity=None, command_id="C2", **kwargs):
        b = kwargs.pop("native", book(ts, yes=bid))
        d = kwargs.pop("command", decision(ts, action=Action.EXIT))
        return self.executor.execute(d, b, now_ts=ts, command_id=command_id,
                                     position_id=pid, quantity=quantity, **kwargs)

    def test_sub20_budget_reproduces_138_contracts_and_fee_aware_cash(self):
        receipt = self.enter()
        self.assertEqual(receipt.status, "BOOKED")
        self.assertEqual(receipt.event["qty"], 138)
        self.assertEqual(receipt.event["cost"], "23.4600")
        self.assertEqual(receipt.event["fees"], "1.37")
        self.assertAlmostEqual(self.executor.cash, 975.17)
        self.assertFalse(receipt.event["venue_fill_claim"])
        self.assertEqual(receipt.event["quote_id"], "Q1000.0")

    def test_exact_modeled_round_trip_and_committed_net(self):
        self.enter()
        receipt = self.exit(bid=.27)
        self.assertEqual(receipt.status, "EXITED")
        self.assertEqual(receipt.event["fees"], "1.91")
        self.assertAlmostEqual(float(receipt.event["gross_pnl"]), 13.80)
        self.assertAlmostEqual(float(receipt.event["net_pnl"]), 10.52)
        self.assertAlmostEqual(self.executor.cash, 1010.52)
        self.assertFalse(self.executor.positions)
        checked = PaperExecutioner.inspect_journal(self.run)
        self.assertTrue(checked["committed_boundary"])
        self.assertEqual(len(checked["state"]["events"]), 2)

    def test_fractional_depth_never_creates_integer_contract(self):
        native = book(no_qty=.99)
        receipt = self.enter(native=native)
        self.assertEqual(receipt.status, "REJECTED")
        self.assertEqual(self.executor.cash, 1000)
        self.assertFalse(self.executor.positions)

    def test_each_depth_level_is_floored_not_fractionally_aggregated(self):
        native = PaperBook("KX1", "QD", 1000, 1000, (PriceLevel(.15, 100),),
                          (PriceLevel(.83, 1.8), PriceLevel(.82, 1.8)), 1900)
        receipt = self.enter(native=native, command=decision(limit=.18))
        self.assertEqual(receipt.event["qty"], 2)
        self.assertEqual(receipt.event["depth_sweep"]["levels"], [["0.17", 1], ["0.18", 1]])
        self.assertEqual(float(receipt.event["price"]), .175)

    def test_tool_limit_is_enforced_at_each_ask_level(self):
        native = PaperBook("KX1", "QD", 1000, 1000, (PriceLevel(.15, 100),),
                          (PriceLevel(.83, 2), PriceLevel(.80, 100)), 1900)
        receipt = self.enter(native=native)
        self.assertEqual(receipt.event["qty"], 2)
        self.assertEqual(float(receipt.event["price"]), .17)

    def test_expensive_wait_does_not_consume_opportunity(self):
        self.assertEqual(self.enter(native=book(no=.7)).status, "REJECTED")
        receipt = self.enter(native=book(1001), command=decision(1001), command_id="C2")
        self.assertEqual(receipt.status, "BOOKED")

    def test_same_command_replay_is_idempotent_and_mutation_is_rejected(self):
        first = self.enter()
        second = self.enter()
        self.assertEqual(second.status, "DUPLICATE")
        self.assertEqual(second.event, first.event)
        self.assertEqual(len(self.executor.events), 1)
        with self.assertRaises(PaperExecutionError):
            self.enter(command=decision(budget=10))

    def test_same_opportunity_never_rebooks_after_exit(self):
        self.enter()
        self.exit()
        receipt = self.enter(native=book(1050), command=decision(1050), command_id="C3")
        self.assertEqual(receipt.reason, "OPPORTUNITY_ALREADY_BOOKED")

    def test_same_side_stacking_and_automatic_relay_close_are_forbidden(self):
        self.enter()
        stack = self.enter(native=book(1001), command=decision(1001, opportunity="EDGE2"), command_id="C2")
        self.assertEqual(stack.reason, "SAME_TICKER_SIDE_POSITION_ALREADY_OPEN")
        relay = self.enter(native=book(1002), command=decision(1002, action=Action.RELAY,
            side=Side.NO, opportunity="TURN", limit=.9), command_id="C3")
        self.assertEqual(relay.reason, "TICKER_POSITION_CAPACITY_EXIT_BEFORE_RELAY")
        self.assertEqual(len(self.executor.events), 1)
        self.assertEqual(self.executor.positions["1"].side, Side.YES)

    def test_rollover_preserves_old_ticker_inventory(self):
        self.enter()
        receipt = self.enter(native=book(1001, ticker="KX2", close_ts=2800),
            command=decision(1001, ticker="KX2"), command_id="C2")
        self.assertEqual(receipt.status, "BOOKED")
        self.assertEqual({p.ticker for p in self.executor.positions.values()}, {"KX1", "KX2"})
        wrong = self.exit(native=book(1040, ticker="KX2", close_ts=2800), command_id="C3",
                          command=decision(1040, action=Action.EXIT, ticker="KX2"))
        self.assertEqual(wrong.reason, "EXACT_HELD_POSITION_TICKER_SIDE_REQUIRED")

    def test_losing_position_can_exit_no_sanctuary(self):
        self.enter()
        receipt = self.exit(bid=.08)
        self.assertEqual(receipt.status, "EXITED")
        self.assertLess(float(receipt.event["net_pnl"]), 0)
        self.assertFalse(self.executor.positions)

    def test_one_sided_fresh_held_bid_can_exit_while_entries_are_disabled(self):
        self.enter()
        native = book(1040, yes=.27, no=None, entry_allowed=False, no_sell_allowed=False)
        receipt = self.exit(native=native)
        self.assertEqual(receipt.status, "EXITED")

    def test_partial_sale_preserves_basis_and_requires_continuing_exit(self):
        self.enter()
        receipt = self.exit(native=book(1040, yes=.27, yes_qty=30.9))
        self.assertEqual(receipt.status, "PARTIAL_EXIT")
        self.assertEqual(receipt.event["qty"], 30)
        self.assertEqual(self.executor.positions["1"].qty, 108)
        hold = CommanderDecision(Action.HOLD, None, "HOLD")
        blocked = self.executor.execute(hold, book(1041), now_ts=1041, command_id="H1")
        self.assertEqual(blocked.reason, "MANDATORY_EXIT_REQUIRES_COMMANDER_EXIT")
        finish = self.exit(ts=1042, bid=.26, command_id="C3")
        self.assertEqual(finish.status, "EXITED")
        self.assertFalse(self.executor.positions)
        self.assertEqual(len(self.executor.events), 3)
        PaperExecutioner.inspect_journal(self.run)

    def test_same_native_liquidity_is_not_reused_by_second_sale(self):
        self.enter()
        native = book(1040, yes=.27, yes_qty=30)
        self.exit(native=native)
        second = self.exit(native=native, command_id="C3")
        self.assertEqual(second.reason, "NO_INTEGER_EXECUTABLE_HELD_BID")
        self.assertEqual(self.executor.positions["1"].qty, 108)

    def test_stale_native_book_and_stale_physical_decision_are_rejected(self):
        stale = self.executor.execute(decision(), book(), now_ts=1004, command_id="S1")
        self.assertEqual(stale.reason, "OBJECTIVE_NATIVE_RECEIVE_STALE")
        old = self.executor.execute(decision(), book(1005), now_ts=1005, command_id="S2")
        self.assertEqual(old.reason, "COMMAND_PHYSICAL_SOURCE_STALE_OR_FUTURE")
        self.assertFalse(self.executor.positions)

    def test_quote_identity_reused_for_different_depth_halts(self):
        self.enter()
        with self.assertRaisesRegex(PaperExecutionError, "SAME_QUOTE_ID"):
            self.executor.observe_floors(book(1000.0, yes_qty=50), now_ts=1000, policies={})

    def test_crossed_binary_book_cannot_execute(self):
        receipt = self.enter(native=book(yes=.60, no=.60))
        self.assertEqual(receipt.reason, "OBJECTIVE_CONFLICTING_CROSSED_BINARY_BOOK")
        self.assertFalse(self.executor.positions)

    def test_unknown_exchange_timestamp_requires_explicit_native_proof(self):
        base = book()
        values = dict(base.__dict__)
        values["exchange_ts"] = None
        self.assertEqual(self.enter(native=PaperBook(**values)).status, "REJECTED")
        values["provenance"] = MappingProxyType({"sequence_checked": True,
            "snapshot_verified": True, "monotonic_receive_fresh": True})
        self.assertEqual(self.enter(native=PaperBook(**values), command_id="C2").status, "BOOKED")

    def test_recursively_frozen_feed_and_intent_provenance_executes_and_settles(self):
        nested = MappingProxyType({"source": MappingProxyType({"sequence": 7}), "rows": (1, 2)})
        native = book(provenance=nested)
        original = decision().intent
        intent = ToolIntent(original.tool, original.territory_id, original.lane,
                            original.side, original.action, original.opportunity_id,
                            original.max_price, original.size_tier, original.reason,
                            original.source_time, metadata=MappingProxyType({"ticker": "KX1", "proof": nested}))
        receipt = self.enter(native=native, command=CommanderDecision(Action.ENTER, intent, "ACCEPTED"))
        self.assertEqual(receipt.status, "BOOKED")
        self.assertEqual(receipt.event["quote_provenance"]["provenance"]["source"]["sequence"], 7)
        result = OfficialResult("KX1", "R1", Side.YES, 1900, 1901,
                                "KALSHI_PUBLIC_TLS_GET", provenance=nested)
        settlement = self.executor.settle(result)[0]
        self.assertEqual(settlement.status, "SETTLED")
        self.assertEqual(settlement.event["official_result"]["provenance"]["source"]["sequence"], 7)

    def test_explicit_rail_policy_defers_first_floor_below_100_percent(self):
        self.enter()
        rail = FloorPolicy(arm_roi=1.0, trail_fraction=.10)
        first = self.executor.observe_floors(book(1040, yes=.26), now_ts=1040, policies={"1": rail})
        self.assertFalse(first[0].armed)
        second = self.executor.observe_floors(book(1041, yes=.34), now_ts=1041, policies={"1": rail})
        self.assertTrue(second[0].armed)
        self.assertAlmostEqual(second[0].floor_bid, .306)

    def test_explicit_minimum_age_does_not_arm_ordinary_initial_profit(self):
        self.enter()
        policy = FloorPolicy(.50, .05, 30)
        young = self.executor.observe_floors(book(1010, yes=.26), now_ts=1010, policies={"1": policy})
        self.assertFalse(young[0].armed)
        older = self.executor.observe_floors(book(1040, yes=.26), now_ts=1040, policies={"1": policy})
        self.assertTrue(older[0].armed)

    def test_explicit_100_percent_protection_arms_during_initial_30_seconds(self):
        self.enter()
        policy = FloorPolicy(.50, .05, 30, immediate_arm_roi=1.0)
        first = self.executor.observe_floors(book(1005, yes=.26), now_ts=1005, policies={"1": policy})
        self.assertFalse(first[0].armed)
        hundred = self.executor.observe_floors(book(1006, yes=.34), now_ts=1006, policies={"1": policy})
        self.assertTrue(hundred[0].armed)
        self.assertAlmostEqual(hundred[0].floor_bid, .323)

    def test_armed_floor_cannot_be_lowered_or_waived_and_never_autosells(self):
        self.enter()
        self.executor.observe_floors(book(1040, yes=.34), now_ts=1040, policies={"1": FloorPolicy(1, .10)})
        initial = self.executor.positions["1"].floor_bid
        obs = self.executor.observe_floors(book(1041, yes=.33), now_ts=1041, policies={"1": FloorPolicy(10, .80)})
        self.assertEqual(obs[0].floor_bid, initial)
        breached = self.executor.observe_floors(book(1042, yes=.30), now_ts=1042, policies={})
        self.assertTrue(breached[0].breached)
        self.assertEqual(len(self.executor.events), 1)
        no_exit = self.executor.execute(CommanderDecision(Action.HOLD, None, "HOLD_RELEASE"),
                                       book(1042, yes=.30), now_ts=1042, command_id="H1")
        self.assertEqual(no_exit.reason, "MANDATORY_EXIT_REQUIRES_COMMANDER_EXIT")
        exit_receipt = self.exit(ts=1043, bid=.30)
        self.assertEqual(exit_receipt.status, "EXITED")

    def test_execute_catches_armed_floor_even_without_observer_call(self):
        self.enter()
        self.executor.observe_floors(book(1040, yes=.34), now_ts=1040, policies={"1": FloorPolicy(1, .10)})
        receipt = self.executor.execute(CommanderDecision(Action.WAIT, None, "WAIT"),
                                       book(1041, yes=.30), now_ts=1041, command_id="W1")
        self.assertEqual(receipt.reason, "MANDATORY_EXIT_REQUIRES_COMMANDER_EXIT")

    def test_existing_armed_trail_continues_without_new_tool_policy(self):
        self.enter()
        self.executor.observe_floors(book(1040, yes=.34), now_ts=1040,
                                    policies={"1": FloorPolicy(1, .10)})
        higher = self.executor.observe_floors(book(1041, yes=.40), now_ts=1041, policies={})
        self.assertTrue(higher[0].armed)
        self.assertAlmostEqual(higher[0].floor_bid, .36)

    def test_floor_does_not_accept_older_source_after_a_thin_book(self):
        self.enter()
        self.executor.observe_floors(book(1041, yes=.30, yes_qty=1), now_ts=1041, policies={})
        older = self.executor.observe_floors(book(1040, yes=.8), now_ts=1042,
                                            policies={"1": FloorPolicy(.5, .05)})
        self.assertEqual(older[0].reason, "OBJECTIVE_QUOTE_PRECEDES_POSITION_OR_REGRESSES")
        self.assertFalse(older[0].armed)

    def test_thin_book_cannot_create_whole_position_peak_or_raise_floor(self):
        self.enter()
        obs = self.executor.observe_floors(book(1040, yes=.9, yes_qty=1), now_ts=1040,
                                           policies={"1": FloorPolicy(.5, .05)})
        self.assertFalse(obs[0].full_quantity_visible)
        self.assertFalse(obs[0].armed)
        self.assertIsNone(obs[0].peak_bid)

    def test_only_official_final_exact_contract_result_settles(self):
        self.enter()
        with self.assertRaises(ValueError):
            self.executor.settle(OfficialResult("KX1", "R1", Side.NO, 1900, 1901, "BTC_PROXY"))
        with self.assertRaises(ValueError):
            self.executor.settle(OfficialResult("KX1", "R1", Side.NO, 1900, 1899, "KALSHI_PUBLIC_TLS_GET"))
        with self.assertRaises(ValueError):
            self.executor.settle(OfficialResult("KX1", "R1", Side.NO, 1901, 1902, "KALSHI_PUBLIC_TLS_GET"))
        result = OfficialResult("KX1", "R1", Side.NO, 1900, 1901, "KALSHI_PUBLIC_TLS_GET")
        receipt = self.executor.settle(result)[0]
        self.assertEqual(receipt.status, "SETTLED")
        self.assertEqual(float(receipt.event["price"]), 0)
        self.assertAlmostEqual(float(receipt.event["net_pnl"]), -24.83)
        self.assertEqual(self.executor.settle(result)[0].status, "DUPLICATE")
        with self.assertRaises(PaperExecutionError):
            self.executor.settle(OfficialResult("KX1", "R2", Side.YES, 1900, 1902, "KALSHI_PUBLIC_TLS_GET"))

    def test_pending_expired_lot_is_never_closed_by_new_ticker_quote(self):
        self.enter(native=book(close_ts=1010))
        after = self.executor.execute(decision(1011, action=Action.EXIT), book(1011, close_ts=1010),
                                      now_ts=1011, command_id="C2", position_id="1")
        self.assertEqual(after.reason, "OBJECTIVE_CONTRACT_CLOSED")
        self.assertIn("1", self.executor.positions)

    def test_writer_lock_blocks_second_writer(self):
        with self.assertRaisesRegex(PaperExecutionError, "WRITER_LOCK"):
            PaperExecutioner(self.run)

    def test_existing_ledger_cannot_be_blindly_restarted(self):
        self.enter()
        self.executor.close()
        with self.assertRaisesRegex(PaperExecutionError, "EXPLICIT_REVIEW"):
            PaperExecutioner(self.run)
        with self.assertRaisesRegex(PaperExecutionError, "OPEN_INVENTORY"):
            PaperExecutioner(self.run, resume=True)
        self.assertEqual(len(PaperExecutioner.inspect_journal(self.run)["state"]["positions"]), 1)

    def test_explicit_flat_resume_preserves_cash_and_consumed_identity(self):
        self.enter()
        self.exit()
        cash = self.executor.cash
        self.executor.close()
        self.executor = PaperExecutioner(self.run, resume=True)
        self.assertEqual(self.executor.cash, cash)
        receipt = self.enter(native=book(1050), command=decision(1050), command_id="C3")
        self.assertEqual(receipt.reason, "OPPORTUNITY_ALREADY_BOOKED")

    def test_corrupt_commit_is_refused_instead_of_resetting_cash(self):
        self.enter()
        self.executor.close()
        latest = sorted((self.run / "paper_journal").glob("*.json"))[-1]
        record = json.loads(latest.read_text(encoding="utf-8"))
        record["state"]["cash"] = "1000000"
        latest.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(PaperExecutionError, "JOURNAL_INTEGRITY"):
            PaperExecutioner(self.run, resume=True)

    def test_failed_atomic_commit_never_publishes_uncommitted_position(self):
        with patch("strategy_core.paper_execution.os.replace", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(PaperExecutionError, "COMMIT_FAILED"):
                self.enter()
        self.assertFalse(self.executor.positions)
        self.assertEqual(self.executor.cash, 1000)
        self.assertEqual(PaperExecutioner.inspect_journal(self.run)["records"], 1)

    def test_fee_model_rounds_up_to_cents(self):
        self.assertEqual(str(nominal_taker_fee(138, .17)), "1.37")
        self.assertEqual(str(nominal_taker_fee(138, .27)), "1.91")


if __name__ == "__main__":
    unittest.main()
