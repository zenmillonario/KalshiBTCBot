"""Nautilus reflects real PAPER receipts without creating trading authority."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from strategy_core.commander import CommanderDecision
from strategy_core.nautilus_projection import NautilusProjection
from strategy_core.paper_execution import OfficialResult, PaperBook, PaperExecutioner, PriceLevel
from strategy_core.types import Action, Lane, Side, ToolIntent


def native(ts=1000., *, ticker="KX1", close=1900., bid=.16, quantity=1000):
    return PaperBook(ticker, f"{ticker}:Q{ts}", ts, ts,
        (PriceLevel(bid, quantity),), (PriceLevel(round(.99-bid, 9), 1000),), close)


def command(ts=1000., action=Action.ENTER):
    intent = ToolIntent("MOUNTAIN", "T1", Lane.TACTICAL, Side.YES, action, "EDGE1",
                        .17, 25, "TEST_EXPLICIT_TOOL_INTENT", ts)
    return CommanderDecision(action, intent, "COMMANDER_ACCEPTED_TOOL_INTENT")


def status(executor=None, *, ts=1000., book=None, reason="MOUNTAIN_MIDDLE_PROTECTED", state="RUNNING", run="RUN1"):
    native_book = book or native(ts)
    values = executor.snapshot() if executor else {
        "cash": "1000", "realized_gross": "0", "realized_net": "0", "fees_paid": "0",
        "positions": {}, "events": [], "journal_seq": 0}
    return {"run_id": run, "runtime_revision": "TOOL_RACK_PAPER_V1", "state": state, "updated_at": ts,
        "source_status": {"btc_current": True, "book_current": True, "entry_quote_available": True},
        "physical": {"physical_current": True, "observed_history_seconds": 900},
        "latest_geometry": {"epoch_ms": ts*1000, "btc_price": 80000, "ema9": 80001, "ema30": 80010},
        "market": {"ticker": native_book.ticker, "close_ts": native_book.close_ts}, "book": asdict(native_book),
        "rack": {"owned_territory": "ALTERNATING_MOUNTAIN", "owned_side": "YES", "territory_id": "T1",
                 "active_tool": "MOUNTAIN", "active_overlays": ["RELEASE"], "ownership_reason": "RETAINED_PHYSICAL_OWNER",
                 "intents": [{"tool": "MOUNTAIN", "action": "WAIT", "side": "YES", "reason": reason,
                              "territory_id": "T1", "opportunity_id": "EDGE1", "max_price": .17}]},
        "decisions": [{"scope": "ENTRY", "decision": {"action": "WAIT", "intent": None, "reason": reason}}],
        "positions": values["positions"], "events": values["events"], "cash": values["cash"],
        "realized_gross": values["realized_gross"], "realized_net": values["realized_net"],
        "fees_paid": values["fees_paid"], "ledger_seq": values["journal_seq"]}


class NautilusProjectionTests(unittest.TestCase):
    def test_every_observed_transition_survives_ui_throttle_and_reload_without_candidate_fills(self):
        projection = NautilusProjection()
        first = status()
        projection.observe(first)
        same = status(ts=1000.1, book=native())
        projection.observe(same)
        count = len(projection.project(same, now_ts=1000.1)["feed"])
        projection.observe(same)
        self.assertEqual(len(projection.project(same, now_ts=1000.1)["feed"]), count)
        second = status(ts=1000.2, reason="MATURE_EDGE_NOT_CHEAP")
        projection.observe(second)
        third = status(ts=1000.3, reason="NO_AFFORDABLE_INTEGER_LOT")
        third["decisions"][0]["receipt"] = {"status": "REJECTED", "reason": "NO_INTEGER_EXECUTABLE_HELD_BID"}
        projection.observe(third)
        view = projection.project(third, now_ts=1000.3)
        commands = [row for row in view["feed"] if row["kind"] == "COMMANDER"]
        self.assertEqual([row["time"] for row in commands], [1000., 1000.2, 1000.3])
        self.assertIn("executor REJECTED", commands[-1]["text"])
        self.assertEqual(view["trades"], [])
        self.assertEqual(view["positions"], [])
        self.assertEqual(view["interpretation"]["shadow_ai_status"]["status"], "NOT_RUNNING")
        self.assertEqual(view["feed"], projection.project(third, now_ts=1000.3)["feed"])
        alive = deepcopy(third)
        alive.update(updated_at=1031., sequence=123)
        projection.observe(alive)
        later = projection.project(alive, now_ts=1031.)
        heartbeat = [row for row in later["feed"] if row["kind"] == "HEARTBEAT"]
        self.assertEqual(len(heartbeat), 1)
        self.assertEqual(heartbeat[0]["time"], 1031.)
        self.assertIn("observation 123", heartbeat[0]["text"])
        self.assertIn("native quote age 30.7s", heartbeat[0]["text"])
        self.assertEqual(len([row for row in later["feed"] if row["kind"] == "COMMANDER"]), 3)
        self.assertEqual(len([row for row in projection.project(alive, now_ts=1061.)["feed"]
                              if row["kind"] == "HEARTBEAT"]), 1)

    def test_real_executor_partial_exits_keep_exact_remaining_lot_fees_and_weighted_exit(self):
        with tempfile.TemporaryDirectory() as directory, PaperExecutioner(Path(directory) / "run") as executor:
            projection = NautilusProjection()
            receipt = executor.execute(command(), native(), now_ts=1000., command_id="ENTRY1")
            self.assertEqual(receipt.event["qty"], 138)
            projection.observe(status(executor))
            first_exit = native(1040., bid=.27, quantity=50)
            receipt = executor.execute(command(1040., Action.EXIT), first_exit, now_ts=1040.,
                                       command_id="EXIT1", position_id="1")
            self.assertEqual(receipt.status, "PARTIAL_EXIT")
            partial = status(executor, ts=1040., book=first_exit)
            view = projection.project(partial, now_ts=1040.)
            self.assertEqual(len(view["trades"]), 1)
            trade = view["trades"][0]
            self.assertEqual((trade["qty"], trade["remaining_qty"], trade["partial_exits"]), (138, 88, 1))
            self.assertIsNone(trade["exit_ts"])
            self.assertEqual(view["positions"][0]["remaining_qty"], 88)
            self.assertFalse(view["positions"][0]["mark_valid"])
            self.assertIsNone(view["positions"][0]["open_pnl"])
            final_exit = native(1041., bid=.30)
            receipt = executor.execute(command(1041., Action.EXIT), final_exit, now_ts=1041.,
                                       command_id="EXIT2", position_id="1")
            self.assertEqual(receipt.status, "EXITED")
            final = status(executor, ts=1041., book=final_exit)
            view = projection.project(final, now_ts=1041.)
            trade = view["trades"][0]
            self.assertEqual(trade["exit_ts"], 1041.)
            self.assertAlmostEqual(trade["exit_bid"], (50*.27+88*.30)/138)
            self.assertAlmostEqual(trade["pnl"], float(final["realized_gross"]))
            self.assertAlmostEqual(trade["net_pnl"], float(final["realized_net"]))
            self.assertAlmostEqual(trade["fees_paid"], float(final["fees_paid"]))
            self.assertAlmostEqual(view["accounting"]["cash"], executor.cash)
            self.assertEqual(view["positions"], [])
            self.assertEqual(view["accounting"]["closed"], 1)
            self.assertEqual(len([r for r in view["feed"] if r["category"] == "trade"]), 3)
            projection.observe(final)
            self.assertEqual(len(projection.project(final, now_ts=1041.)["trades"]), 1)

    def test_full_lot_depth_mark_is_conservative_and_same_quote_sold_levels_are_not_reused(self):
        with tempfile.TemporaryDirectory() as directory, PaperExecutioner(Path(directory) / "run") as executor:
            executor.execute(command(), native(), now_ts=1000., command_id="ENTRY1")
            projection = NautilusProjection()
            projection.observe(status(executor))
            layered = PaperBook("KX1", "LAYERS", 1040., 1040.,
                (PriceLevel(.30, 50), PriceLevel(.20, 88)), (PriceLevel(.69, 1000),), 1900.)
            full = projection.project(status(executor, ts=1040., book=layered), now_ts=1040.)
            p = full["positions"][0]
            self.assertTrue(p["mark_valid"])
            self.assertEqual(p["native_top_bid"], .30)
            self.assertAlmostEqual(p["current_bid"], .2362)
            self.assertAlmostEqual(p["open_pnl"], (.2362-.17)*138)
            executor.execute(command(1040., Action.EXIT), layered, now_ts=1040., command_id="PARTIAL",
                             position_id="1", quantity=50)
            same_quote = projection.project(status(executor, ts=1040.1, book=layered), now_ts=1040.1)
            p = same_quote["positions"][0]
            self.assertTrue(p["mark_valid"])
            self.assertAlmostEqual(p["current_bid"], .20)
            self.assertAlmostEqual(p["open_pnl"], (.20-.17)*88)

    def test_rollover_does_not_borrow_new_ticker_quote_and_official_settlement_is_a_committed_event(self):
        with tempfile.TemporaryDirectory() as directory, PaperExecutioner(Path(directory) / "run") as executor:
            executor.execute(command(), native(), now_ts=1000., command_id="ENTRY1")
            projection = NautilusProjection()
            initial = status(executor)
            initial["market"].update(target=80000, target_source="KALSHI_MARKET_FLOOR_STRIKE")
            projection.observe(initial)
            new_book = native(1901., ticker="KX2", close=2800., bid=.99)
            view = projection.project(status(executor, ts=1901., book=new_book), now_ts=1901.)
            self.assertEqual(view["quote"]["ticker"], "KX2")
            self.assertEqual(view["quote"]["last_verified"]["ticker"], "KX2")
            self.assertEqual(view["positions"][0]["ticker"], "KX1")
            self.assertFalse(view["positions"][0]["mark_valid"])
            self.assertIsNone(view["positions"][0]["current_bid"])
            self.assertEqual(view["positions"][0]["state"], "AWAITING OFFICIAL RESULT")
            self.assertIsNone(view["market"]["target"])
            self.assertEqual([(t["ticker"], t["target"]) for t in view["targets"]], [("KX1", 80000)])
            executor.settle(OfficialResult("KX1", "RESULT1", Side.YES, 1900., 1902., "KALSHI_PUBLIC_TLS_GET"))
            settled = status(executor, ts=1902., book=new_book)
            settled["market"].update(target=80123, target_source="KALSHI_MARKET_FLOOR_STRIKE")
            view = projection.project(settled, now_ts=1902.)
            self.assertEqual(view["positions"], [])
            self.assertEqual(view["trades"][0]["exit_type"], "SETTLEMENT")
            self.assertEqual(view["trades"][0]["exit_bid"], 1.)
            self.assertAlmostEqual(view["accounting"]["realized_net"], 113.17)
            self.assertEqual([r for r in view["feed"] if r["kind"] == "SETTLEMENT"][0]["time"], 1902.)
            self.assertEqual(view["market"]["target"], 80123)
            self.assertEqual([(t["ticker"], t["target"]) for t in view["targets"]], [("KX1", 80000), ("KX2", 80123)])

    def test_quote_ages_without_restamping_and_outputs_do_not_alias_status_or_history(self):
        projection = NautilusProjection()
        source = status()
        first = projection.project(source, now_ts=1000.)
        self.assertEqual(first["quote"]["valid_until"], 1003.)
        source["updated_at"] = 1004.
        stale = projection.project(source, now_ts=1004.)
        self.assertFalse(stale["quote"]["fresh"])
        self.assertIsNone(stale["quote"]["yes_bid"])
        self.assertEqual(stale["quote"]["last_verified"]["verified_at"], 1000.)
        first["feed"][0]["text"] = "CHANGED BY BROWSER"
        source["rack"]["active_tool"] = "CHANGED BY CALLER"
        self.assertNotEqual(first["tool_rack"]["active_tool"], source["rack"]["active_tool"])
        self.assertNotEqual(projection.project(status(), now_ts=1000.)["feed"][0]["text"], "CHANGED BY BROWSER")
        unknown = status()
        unknown["book"]["exchange_ts"] = None
        self.assertFalse(NautilusProjection().project(unknown, now_ts=1000.)["quote"]["fresh"])
        unknown["book"]["source"] = "WS_SEQUENCE_CHECKED_BOOK"
        unknown["book"]["provenance"] = {k: True for k in ("sequence_checked", "snapshot_verified", "monotonic_receive_fresh")}
        self.assertTrue(NautilusProjection().project(unknown, now_ts=1000.)["quote"]["fresh"])

    def test_actual_seed_candles_retain_source_and_sampled_geometry_never_invents_missing_bars(self):
        projection = NautilusProjection()
        source = status(ts=1080.)
        rows = [{"epoch_ms": 1001_000, "btc_price": 80000, "ema9": 80001, "ema30": 80002},
                {"epoch_ms": 1079_000, "btc_price": 80010, "ema9": 80004, "ema30": 80003}]
        chart = {"candles": [{"time": 960, "open": 79980, "high": 80020, "low": 79970,
                   "close": 80005, "quality": "coinbase-completed", "complete": True,
                   "source": "COINBASE_PUBLIC_CANDLES", "known_at": 1020}],
                 "history": {"status": "READY", "completed_minutes": 1, "requested_minutes": 1}}
        view = projection.project(source, rows, chart_data=chart, now_ts=1080.)
        self.assertEqual([b["time"] for b in view["candles"]], [960, 1020])
        self.assertEqual(view["candles"][0]["high"], 80020)
        self.assertEqual(view["candles"][0]["quality"], "coinbase-completed")
        self.assertEqual(view["candles"][1]["quality"], "sampled")
        self.assertFalse(view["candles"][1]["complete"])
        self.assertEqual(view["emas"][0]["e9"], 80001)
        self.assertIsNone(view["market"]["target"])
        self.assertEqual(view["targets"], [])
        json.dumps(view, allow_nan=False)

    def test_missing_entry_and_changed_committed_identity_are_reported_without_fabricated_trades(self):
        with tempfile.TemporaryDirectory() as directory, PaperExecutioner(Path(directory) / "run") as executor:
            executor.execute(command(), native(), now_ts=1000., command_id="ENTRY1")
            executor.execute(command(1040., Action.EXIT), native(1040., bid=.27), now_ts=1040., command_id="EXIT1", position_id="1")
            source = status(executor, ts=1040., book=native(1040., bid=.27))
            missing = deepcopy(source)
            missing["events"] = missing["events"][-1:]
            view = NautilusProjection().project(missing, now_ts=1040.)
            self.assertEqual(view["trades"], [])
            self.assertTrue(any("without its entry" in issue for issue in view["diagnostics"]["issues"]))
            self.assertAlmostEqual(view["accounting"]["realized_net"], 10.52)
            projection = NautilusProjection()
            projection.observe(source)
            source["events"][0]["price"] = ".50"
            view = projection.project(source, now_ts=1040.)
            self.assertEqual(view["trades"][0]["entry_ask"], .17)
            self.assertTrue(any("identity changed" in issue for issue in view["diagnostics"]["issues"]))

    def test_feed_is_bounded_new_session_resets_and_stopped_sources_do_not_claim_live(self):
        projection = NautilusProjection()
        for i in range(600):
            projection.observe(status(ts=1000.+i/100, reason=f"WAIT_{i}"))
        view = projection.project(status(ts=1006., reason="WAIT_599"), now_ts=1006.)
        self.assertEqual(len(view["feed"]), 1000)
        next_session = status(ts=1010., run="RUN2", state="STOPPED")
        view = projection.project(next_session, now_ts=1010.)
        self.assertLess(len(view["feed"]), 20)
        self.assertTrue(all(row["id"].startswith("RUN2:") for row in view["feed"]))
        self.assertFalse(view["run"]["fresh"])
        self.assertFalse(view["quote"]["fresh"])
        self.assertFalse(view["clock"]["verified"])
        self.assertEqual(view["health"]["engine"]["status"], "STOPPED")


if __name__ == "__main__":
    unittest.main()
