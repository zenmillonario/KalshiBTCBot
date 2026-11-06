from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from strategy_core.marketdata.kalshi_public import MarketInfo
from strategy_core.paper_execution import FloorPolicy, OfficialResult, PaperBook, PaperExecutioner, PriceLevel
from strategy_core.paper_feed import FeedSnapshot, _ChartHistory, freeze_data
from strategy_core.paper_runtime import GlobalPaperLease, ToolRackPaperEngine
from strategy_core.physical_source import CausalGeometry
from strategy_core.types import Side, Territory


BASE = 1_800_000_000.0
SOURCE_TARGET = object()


def raw_rows(stop=1200, start=0, epoch=1):
    # Current price stays inside the observed three-dollar EMA9 contact band.
    # Retained Rail direction alone is not fresh-entry permission.
    return tuple({"epoch_ms": (BASE + i) * 1000, "btc_price": 79998 - i * .10,
                  "ema9": 80000 - i * .10, "ema30": 80015 - i * .10,
                  "connection_epoch": epoch, "sequence_num": i}
                 for i in range(start, stop + 1))


def pullback_rows(stop=1200):
    """Explicit synthetic observed dip and rejoin inside the old DOWN parent.

    The engine receives every numeric tick, then observes the three causal
    checkpoints before300s and at300s. Quote cheapness alone has no authority.
    """
    out=[]
    for raw in raw_rows(stop):
        row=dict(raw); i=row["sequence_num"]
        if 1150 < i <= 1180:
            row["btc_price"]=79883.+(i-1150)*(14./30.)
        elif 1180 < i <= 1200:
            row["btc_price"]=79897.-(i-1180)*.6
        elif i > 1200:
            row["btc_price"]=79885.-(i-1200)*.1
        out.append(row)
    return tuple(out)


def chart_candles(offset=1200, *, epoch=1, observations=()):
    """Use the real feed chart schema and validation, with causal close times."""
    by_second = {int(round(row["epoch_ms"] / 1000 - BASE)): row
                 for row in observations if row["epoch_ms"] <= (BASE + offset) * 1000}
    first_observed = min(by_second) if by_second else None
    bars = []
    for opened in range(-2700, int(offset // 60) * 60, 60):
        first, last = 79998 - opened * .10, 79998 - (opened + 60) * .10
        high, low = first, last
        e9, e30 = 80000 - (opened + 60) * .10, 80015 - (opened + 60) * .10
        if first_observed is not None and opened + 60 > first_observed:
            # Reconnection fixtures retain their actual observed path. A
            # missing minute is not repaired from the baseline seed or an
            # interpolated transition; historical bars never become ticks.
            samples = [by_second.get(second) for second in range(opened, opened + 61)]
            if any(row is None for row in samples):
                continue
            values = [row["btc_price"] for row in samples]
            first, last, high, low = values[0], values[-1], max(values), min(values)
            e9, e30 = samples[-1]["ema9"], samples[-1]["ema30"]
        bars.append({"time": BASE + opened, "open": first, "high": high,
            "low": low, "close": last, "e9": e9, "e30": e30,
            "known_at": BASE + opened + 60, "complete": True, "full_minute": True,
            "connection_epoch": epoch, "source": "COINBASE_VALIDATED_HISTORY",
            "historical_seed_is_not_forward_observation": True})
    chart = _ChartHistory()
    chart.seed(bars, epoch)
    return chart.snapshot()["candles"]


def capture(offset=1200, *, ticker="KXBTC15M-FIXTURE-A", close=1800,
            no_bid=.18, no_ask=.20, quote_id=None, rows=None, target=SOURCE_TARGET):
    ts = BASE + offset
    book = PaperBook(ticker, quote_id or f"NATIVE:{offset}", ts, ts,
        (PriceLevel(round(1 - no_ask, 8), 1000),), (PriceLevel(no_bid, 1000),), BASE + close,
        provenance=freeze_data({"sequence_checked": True, "snapshot_verified": True,
                                "monotonic_receive_fresh": True, "fixture": True}))
    if target is SOURCE_TARGET:
        target = 79998 - (close - 900) * .10
    market = MarketInfo(ticker, BASE + close - 900, BASE + close, "active",
        target=target, target_source="KALSHI_MARKET_FLOOR_STRIKE" if target is not None else None)
    return FeedSnapshot(offset, ts, market,
                        book, freeze_data(raw_rows(offset) if rows is None else rows),
                        freeze_data({"btc_current": True, "book_current": True}))


class DirectPaperRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name) / "TOOL_RACK_PAPER_FIXTURE"
        self.engine = ToolRackPaperEngine(self.run)

    def tearDown(self):
        self.engine.close(reason="OFFLINE_FIXTURE_COMPLETE")
        self.temp.cleanup()

    def process(self, frame, **kwargs):
        kwargs.setdefault("historical_candles", chart_candles(frame.observed_ts - BASE))
        return self.engine.process(frame, now_ts=frame.observed_ts, **kwargs)

    def earned_rejoin(self, *, no_bid=.08, no_ask=.10):
        for offset in (1150,1180):
            rows=pullback_rows(offset)
            earlier=self.process(capture(offset,rows=rows,no_bid=no_bid,no_ask=no_ask),
                                 historical_candles=chart_candles(offset,observations=rows))
            self.assertFalse(earlier["receipts"])
        rows=pullback_rows(1200)
        return self.process(capture(1200,rows=rows,no_bid=no_bid,no_ask=no_ask),
                            historical_candles=chart_candles(1200,observations=rows))

    def test_raw_monotone_rail_label_and_cheap_quote_wait_for_located_rejoin(self):
        result = self.process(capture(no_bid=.08, no_ask=.10))
        self.assertEqual(result["status"]["rack"]["owned_territory"], Territory.DOWN_RAIL.value)
        self.assertFalse(result["receipts"])
        self.assertEqual(result["status"]["opportunity_review"]["final_reason"],
                         "OPPORTUNITY_MAIN_PHYSICAL_VALUE_REJOIN_REQUIRED")
        self.assertFalse(self.engine.executor.positions)

    def test_numeric_parent_pullback_rejoin_books_after_five_minutes(self):
        result=self.earned_rejoin()
        self.assertEqual(len(result["receipts"]), 1)
        self.assertEqual(result["receipts"][0].status, "BOOKED")
        positions = list(self.engine.executor.positions.values())
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].side, Side.NO)
        self.assertIn(positions[0].tool, {"RAIL","ONE_COMMANDER_PRIMARY"})

    def test_repeat_rail_observation_does_not_spray_same_contract(self):
        first = self.earned_rejoin()
        second = self.process(capture(1201,rows=pullback_rows(1201)))
        self.assertEqual(len(first["receipts"]), 1)
        self.assertFalse(second["receipts"])
        self.assertEqual(len(self.engine.executor.positions), 1)
        entries = [e for e in self.engine.executor.events if e.get("event") == "ENTRY"]
        self.assertEqual(len(entries), 1)

    def test_rail_value_window_waits_expensive_then_books_value(self):
        first = self.earned_rejoin(no_bid=.54, no_ask=.56)
        self.assertFalse(first["receipts"]); self.assertFalse(self.engine.executor.positions)
        result = self.process(capture(1201,rows=pullback_rows(1201)))
        self.assertEqual(len(result["receipts"]), 1)
        self.assertEqual(result["receipts"][0].status, "BOOKED")
        self.assertEqual(len(self.engine.executor.positions), 1)

    def test_reactivated_rail_keeps_existing_custody_policy_unchanged(self):
        first = self.earned_rejoin()
        peak = self.process(capture(1201,rows=pullback_rows(1201),no_bid=.44,no_ask=.46))
        result = self.process(capture(1202,rows=pullback_rows(1202),no_bid=.38,no_ask=.40))
        self.assertEqual(len(first["receipts"]), 1)
        self.assertFalse(peak["receipts"])
        self.assertEqual(len(result["receipts"]), 1)
        self.assertEqual(result["receipts"][0].event.get("event"), "EXIT")
        self.assertEqual(result["receipts"][0].event.get("reason"), "ALREADY_ARMED_EXECUTABLE_BID_FLOOR")
        self.assertFalse(self.engine.executor.positions)

    def test_long_parent_rail_rollover_does_not_create_unearned_first_minute_entry(self):
        first = self.earned_rejoin()
        result = self.process(capture(1801, ticker="KXBTC15M-FIXTURE-B", close=2700, no_bid=.08, no_ask=.10))
        self.assertEqual(len(first["receipts"]), 1)
        self.assertFalse(any(r.event and r.event.get("event")=="ENTRY" for r in result["receipts"]))
        entries = [e for e in self.engine.executor.events if e.get("event") == "ENTRY"]
        self.assertEqual(len(entries), 1)
        self.assertEqual({e.get("ticker") for e in entries}, {"KXBTC15M-FIXTURE-A"})

    def test_stale_native_quote_does_not_book_despite_qualified_rail(self):
        frame = capture()
        frame = replace(frame, book=replace(frame.book, observed_ts=BASE + 1195))
        result = self.process(frame)
        self.assertFalse(result["receipts"])
        self.assertFalse(self.engine.executor.positions)
    def test_seed_history_bootstraps_two_prior_contracts_without_forward_fake_bars(self):
        frame = capture(rows=raw_rows(1200, start=1200))
        result = self.process(frame)
        context = result["status"]["mission_context"]
        refs = context["contract"]["reference_window"]
        self.assertEqual(refs["completed_prior_contracts"], 2)
        self.assertEqual([p["status"] for p in context["prior_contracts"]], ["COMPLETE", "COMPLETE"])
        self.assertEqual(context["parent"]["basis"], "OBSERVED_COMPLETED_CLOSE_CONTEXT")
        self.assertEqual(context["contract"]["thesis_side"], "NO")
        self.assertEqual(len(self.engine.physical.geometry.rows), 1)
        self.assertIsNone(result["status"]["latest_geometry"]["struct_slope3m"])
        self.assertFalse(context["contract"]["settlement_prediction"])
        self.assertFalse(result["receipts"])  # history context does not fabricate a qualified Rail

    def test_current_completed_candles_keep_thesis_available_five_minutes_into_contract(self):
        result = self.process(capture())
        context = result["status"]["mission_context"]
        self.assertEqual(context["contract"]["history_status"], "READY")
        self.assertEqual(context["contract"]["thesis_side"], "NO")
        self.assertEqual(len(context["contract"]["scenarios"]), 6)
        self.assertEqual(context["contract"]["remaining_seconds"], 600.)
        history_log = self.engine.mission_history_log.name
        recorded = json.loads(Path(history_log).read_text(encoding="utf-8").splitlines()[-1])
        times = {row["time"] for row in recorded["candles"]}
        self.assertIn(BASE - 960, times)  # actual opening close of the second prior contract
        self.assertIn(BASE + 1140, times)  # completed current-contract minute ending at this source
        self.assertTrue(all(row["complete"] is True and row["time"] + 60 <= BASE + 1200
                            for row in recorded["candles"]))

    def test_parent_scale_rail_without_history_is_detected_but_paused(self):
        result = self.process(capture(no_bid=.08, no_ask=.10), historical_candles=())
        context = result["status"]["mission_context"]
        self.assertEqual(result["status"]["rack"]["owned_territory"], Territory.DOWN_RAIL.value)
        self.assertEqual(context["contract"]["thesis_side"], "UNKNOWN")
        self.assertEqual(context["contract"]["reference_window"]["completed_prior_contracts"], 0)
        self.assertFalse(result["receipts"]); self.assertFalse(self.engine.executor.positions)

    def test_parent_scale_rail_without_target_is_detected_but_paused(self):
        result = self.process(capture(no_bid=.08, no_ask=.10, target=None))
        context = result["status"]["mission_context"]
        self.assertEqual(context["contract"]["reference_window"]["completed_prior_contracts"], 2)
        self.assertEqual(context["contract"]["thesis_side"], "UNKNOWN")
        self.assertIsNone(context["contract"]["target"])
        self.assertFalse(result["receipts"]); self.assertFalse(self.engine.executor.positions)

    def test_future_known_seed_cannot_create_thesis_and_rail_remains_paused(self):
        history = [{**row, "known_at": BASE + 1201} for row in chart_candles()]
        result = self.process(capture(no_bid=.08, no_ask=.10), historical_candles=history)
        context = result["status"]["mission_context"]
        self.assertEqual(context["contract"]["reference_window"]["completed_prior_contracts"], 0)
        self.assertEqual(context["contract"]["thesis_side"], "UNKNOWN")
        self.assertFalse(result["receipts"]); self.assertFalse(self.engine.executor.positions)

    def test_live_imports_do_not_load_legacy_authority_or_shadow_source(self):
        import sys
        forbidden = ("r3_single_commander", "r17_guarded", "tachys_v9_", "strategy_core.r22_run_source")
        # Other suites intentionally test migration adapters, so inspect live
        # module source dependencies rather than unrelated global test imports.
        for module_name in ("strategy_core.paper_runtime", "strategy_core.paper_feed", "strategy_core.physical_source"):
            module = sys.modules[module_name]
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertFalse(any(f"import {name}" in source or f"from {name}" in source for name in forbidden))


class CausalGeometryTests(unittest.TestCase):
    def test_full_live_horizon_has_no_minute_endpoint_lag(self):
        geometry = CausalGeometry()
        for row in raw_rows(599):
            last = geometry.append(row)
        self.assertAlmostEqual(last["struct_slope3m"], -18.0)
        self.assertAlmostEqual(last["struct_slope6m"], -36.0)
        self.assertAlmostEqual(last["struct_slope9m"], -54.0)

    def test_short_observation_history_cannot_claim_three_minutes(self):
        geometry = CausalGeometry()
        for row in raw_rows(100):
            last = geometry.append(row)
        self.assertIsNone(last["struct_slope3m"])
        self.assertIsNone(last["struct_slope9m"])

    def test_repeated_capture_does_not_append_or_relabel_old_arcs(self):
        geometry = CausalGeometry()
        for row in raw_rows(600):
            geometry.append(row)
        before = json.dumps(list(geometry.rows), sort_keys=True)
        for row in raw_rows(600):
            self.assertIsNone(geometry.append(row))
        self.assertEqual(before, json.dumps(list(geometry.rows), sort_keys=True))

    def test_gap_clears_old_shape_and_does_not_invent_history(self):
        geometry = CausalGeometry()
        for row in raw_rows(600):
            geometry.append(row)
        last = geometry.append(raw_rows(700, start=700, epoch=2)[0])
        self.assertEqual(len(geometry.rows), 1)
        self.assertIsNone(last["struct_slope3m"])
        self.assertEqual(last["geometry_reset"], "BTC_CONNECTION_EPOCH_CHANGED")

    def test_global_lease_rejects_second_engine_even_in_another_run(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "engine.lock"
            with GlobalPaperLease(path):
                with self.assertRaisesRegex(RuntimeError, "ANOTHER_TOOL_RACK"):
                    with GlobalPaperLease(path):
                        self.fail("Second PAPER engine acquired the global lease")
            with GlobalPaperLease(path):
                pass


if __name__ == "__main__":
    unittest.main()
