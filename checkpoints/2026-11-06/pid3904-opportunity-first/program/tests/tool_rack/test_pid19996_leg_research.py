"""PID19996 accounting controls: physical identity and exact-contract quotes.

The compact fixture contains exact selected callback fields and source hashes.
It is sufficient to reproduce all 233 original label-fragment boundaries and
the invalid cross-contract endpoint pairs, without modifying the original run.
These tests do not claim an engine replay or alternative executed profits.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import gzip
from itertools import groupby
import json
from pathlib import Path
import tempfile
import unittest

from strategy_core.custody_evidence import build_custody_evidence
from strategy_core.leg_ledger import LegPerformanceLedger, QuoteOpportunity, validated_contract_opportunities
from strategy_core.types import MarketSnapshot, Side


FIXTURE = Path(__file__).with_name("fixtures") / "pid19996_leg_accounting.json.gz"


def snapshot(t=1000.0, *, ticker="CONTRACT_A", leg="P1", side="YES", terrain="UP_RAIL",
             generation=0, yes_ask=.20, yes_bid=.19, no_ask=.81, no_bid=.80,
             btc=100.0, child="C1", child_side=None, current=True, quote_current=True):
    return MarketSnapshot(
        now_ts=t, ticker=ticker, contract_age_s=60.0,
        yes_ask=yes_ask, no_ask=no_ask, yes_bid=yes_bid, no_bid=no_bid,
        quote_current=quote_current,
        metadata={"physical_current": current, "geometry_continuity_generation": generation,
                  "current_geometry": {"btc_price": btc, "ema9": btc - 1},
                  "mountain": {"current_arc_id": child, "owner_side": child_side or side,
                               "parent_structure": {"parent_id": leg, "parent_side": side}},
                  "commander_strategy": {"owned_territory": terrain, "owned_side": side,
                                         "active_tool": "RAIL"}},
    )


def complete_leg(*, name="P1", tickers=("CONTRACT_A",)):
    """Create a known physical boundary on each end; each ticker gains 50%."""
    ledger = LegPerformanceLedger()
    ledger.observe(snapshot(999, leg="BEFORE", side="NO"))
    t = 1000
    for ticker in tickers:
        ledger.observe(snapshot(t, leg=name, ticker=ticker, yes_ask=.20, yes_bid=.19))
        ledger.observe(snapshot(t + 1, leg=name, ticker=ticker, yes_ask=.31, yes_bid=.30))
        t += 2
    ledger.observe(snapshot(t, leg="AFTER", side="NO"))
    return ledger.completed[1]


class RecordedPID19996LegResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(FIXTURE, "rt", encoding="utf-8") as handle:
            cls.fixture = json.load(handle)
        cls.records = cls.fixture["records"]
        cls.by_sequence = {row["sequence"]: row for row in cls.records}
        cls.by_time = {row["snapshot"]["now_ts"]: row for row in cls.records}

    def test_actual_233_label_fragments_are_four_physical_observations(self):
        def old_key(row):
            md = row["snapshot"]["metadata"]
            p = md["mountain"]["parent_structure"]
            return p["parent_id"], p["parent_side"], md["commander_strategy"]["owned_territory"]

        old_groups = [list(group) for _, group in groupby(self.records, old_key)]
        self.assertEqual(len(old_groups), 233)
        self.assertEqual(sum(group[0]["snapshot"]["now_ts"] == group[-1]["snapshot"]["now_ts"]
                             for group in old_groups), 222)
        ledger = LegPerformanceLedger()
        for row in self.records:
            ledger.observe(MarketSnapshot(**row["snapshot"]))
        ledger.finalize(reason="PAPER_ENTRY_WINDOW_COMPLETE_FLAT")
        self.assertEqual([row["leg_id"] for row in ledger.completed],
                         ["E000A000001", "E000A000002", "E000A000003", "E000A000004"])
        first = ledger.completed[0]
        self.assertEqual(first["contract_count"], 4)
        self.assertEqual(len(first["terrain_sequence"]), 230)
        self.assertGreater(first["duration_s"], 2700)
        self.assertTrue(first["end_boundary_observed"])
        self.assertFalse(first["start_boundary_observed"])
        self.assertFalse(first["comparable_eligible"])
        self.assertTrue(ledger.completed[1]["comparable_eligible"])
        self.assertTrue(ledger.completed[2]["comparable_eligible"])
        self.assertEqual(ledger.completed[-1]["record_kind"], "OBSERVATION_SEGMENT")
        self.assertFalse(ledger.completed[-1]["end_boundary_observed"])
        self.assertTrue(all(row["execution_authority"] is False for row in ledger.completed))

    def test_actual_invalid_63900_and_79900_percent_pairs_stay_separate(self):
        for old, erroneous_roi in zip(self.fixture["legacy_bad_records"], (639.0, 799.0)):
            with self.subTest(roi=erroneous_roi):
                opportunity = old["no_opportunity"]
                self.assertEqual(opportunity["potential_roi_from_best_observed_basis"], erroneous_roi)
                before = MarketSnapshot(**self.by_time[opportunity["min_ask_ts"]]["snapshot"])
                after = MarketSnapshot(**self.by_time[opportunity["max_bid_ts"]]["snapshot"])
                self.assertNotEqual(before.ticker, after.ticker)
                self.assertAlmostEqual((after.no_bid - before.no_ask) / before.no_ask, erroneous_roi)
                ledger = LegPerformanceLedger()
                ledger.observe(before)
                earlier = deepcopy(ledger.live.contract_opportunities[before.ticker].payload())
                ledger.observe(after)
                ledger.finalize()
                result = ledger.completed[0]
                self.assertIsNone(result["no_opportunity"]["potential_roi_from_best_observed_basis"])
                by_ticker = {r["ticker"]: r for r in result["contract_opportunities"]}
                self.assertEqual(by_ticker[before.ticker], earlier)
                self.assertEqual(set(by_ticker), {before.ticker, after.ticker})
                for ticker, row in by_ticker.items():
                    quote = row["no_opportunity"]
                    self.assertEqual(quote["min_ask_ticker"], ticker)
                    if quote["max_bid_after_min_ask"] is None:
                        self.assertIsNone(quote["max_bid_ticker"])
                        self.assertIsNone(quote["potential_roi_from_best_observed_basis"])
                        self.assertFalse(quote["ticker_scope_valid"])
                    else:
                        self.assertEqual(quote["max_bid_ticker"], ticker)
                        self.assertLessEqual(quote["potential_roi_from_best_observed_basis"], 0)

    def test_actual_same_contract_six_to_twenty_one_cent_move_is_preserved(self):
        ledger = LegPerformanceLedger()
        for seq in (4728, 5115):
            ledger.observe(MarketSnapshot(**self.by_sequence[seq]["snapshot"]))
        ledger.finalize()
        result = ledger.completed[0]
        opportunity = result["no_opportunity"]
        self.assertEqual(result["contract_count"], 1)
        self.assertEqual(opportunity["ticker"], "KXBTC15M-26NOV041730-30")
        self.assertAlmostEqual(opportunity["min_ask"], .06)
        self.assertAlmostEqual(opportunity["max_bid_after_min_ask"], .21)
        self.assertAlmostEqual(opportunity["potential_roi_from_best_observed_basis"], 2.5)
        self.assertTrue(opportunity["ticker_scope_valid"])
        self.assertEqual(opportunity["quantity_basis"], "TOP_OF_BOOK_ONLY")
        self.assertFalse(opportunity["execution_authority"])

    def test_actual_legacy_mixed_records_are_not_comparable_or_custody_mfe(self):
        rows = self.fixture["legacy_bad_records"]
        ledger = LegPerformanceLedger()
        ledger.completed.extend(deepcopy(rows))
        echo = ledger.observe(snapshot())
        self.assertEqual(echo["comparison_count"], 0)
        self.assertEqual(echo["legacy_record_count"], 2)
        md = dict(snapshot().metadata)
        md["leg_echo"] = {"completed_comparable_legs": rows}
        evidence = build_custody_evidence({"side": "YES", "entry_price": .2}, replace(snapshot(), metadata=md))
        self.assertEqual(evidence["excluded_historical_leg_rows"], 2)
        self.assertEqual(evidence["comparable_leg_count"], 0)
        self.assertIsNone(evidence["historical_median_potential_roi"])
        self.assertEqual(evidence["recommendation"], "HOLD")


class PhysicalLegAccountingTests(unittest.TestCase):
    def test_label_flicker_and_child_pullbacks_do_not_end_parent(self):
        ledger = LegPerformanceLedger()
        for i in range(230):
            ledger.observe(snapshot(1000 + i, side=Side.YES,
                                    terrain=("UP_RAIL", "MARKET_HEIST", "UNKNOWN")[i % 3],
                                    child="C1" if i < 100 else "C2",
                                    child_side=Side.YES if i < 100 else Side.NO, btc=100 + i / 10))
        self.assertEqual(ledger.completed, [])
        ledger.finalize()
        row = ledger.completed[0]
        self.assertEqual(row["sample_count"], 230)
        self.assertEqual(row["pullback_count"], 1)
        self.assertEqual(row["push_count"], 1)
        self.assertEqual(row["duration_s"], 229)
        self.assertFalse(row["terrain_has_boundary_authority"])

    def test_each_side_rollover_keeps_one_leg_and_two_return_bases(self):
        for side in ("YES", "NO"):
            with self.subTest(side=side):
                ledger = LegPerformanceLedger()
                quote_a = {"yes_ask": .001, "yes_bid": .0005, "no_ask": .9995, "no_bid": .999}
                quote_b = {"yes_ask": .81, "yes_bid": .80, "no_ask": .20, "no_bid": .19}
                if side == "NO":
                    quote_a = {"yes_ask": .9995, "yes_bid": .999, "no_ask": .001, "no_bid": .0005}
                    quote_b = {"yes_ask": .20, "yes_bid": .19, "no_ask": .81, "no_bid": .80}
                ledger.observe(snapshot(side=side, **quote_a))
                ledger.observe(snapshot(1001, side=side, ticker="CONTRACT_B", **quote_b))
                ledger.finalize()
                self.assertEqual(len(ledger.completed), 1)
                row = ledger.completed[0]
                key = side.lower() + "_opportunity"
                self.assertIsNone(row[key]["potential_roi_from_best_observed_basis"])
                self.assertEqual(len(row["contract_opportunities"]), 2)
                self.assertTrue(all(c[key]["potential_roi_from_best_observed_basis"] < 0
                                    for c in row["contract_opportunities"]))

    def test_accumulator_cannot_be_fed_a_different_ticker(self):
        quote = QuoteOpportunity("CONTRACT_A", "YES")
        quote.observe(ticker="CONTRACT_A", ask=.001, bid=None, now=1)
        with self.assertRaisesRegex(ValueError, "TICKER_MISMATCH"):
            quote.observe(ticker="CONTRACT_B", ask=.81, bid=.80, now=2)
        self.assertIsNone(quote.payload()["potential_roi_from_best_observed_basis"])

    def test_stale_and_unidentified_quotes_add_no_return_evidence(self):
        ledger = LegPerformanceLedger()
        ledger.observe(snapshot(1000, ticker="", yes_ask=.001, yes_bid=.0005))
        ledger.observe(snapshot(1001, quote_current=False, yes_ask=.001, yes_bid=.0005))
        ledger.observe(snapshot(1002, yes_ask=.81, yes_bid=.80))
        ledger.finalize()
        row = ledger.completed[0]
        self.assertEqual(row["contract_opportunities"][0]["sample_count"], 1)
        self.assertAlmostEqual(row["yes_opportunity"]["min_ask"], .81)
        self.assertLess(row["yes_opportunity"]["potential_roi_from_best_observed_basis"], 0)

    def test_true_boundary_observed_legs_and_run_close_have_distinct_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legs.jsonl"
            ledger = LegPerformanceLedger(path)
            for s in (snapshot(1000, leg="P0", side="NO"), snapshot(1001),
                      snapshot(1002, btc=101), snapshot(1003, leg="P2", side="NO")):
                ledger.observe(s)
            ledger.finalize(reason="PAPER_ENTRY_WINDOW_COMPLETE_FLAT")
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertFalse(rows[0]["comparable_eligible"])
        self.assertEqual(rows[1]["record_kind"], "PHYSICAL_LEG")
        self.assertTrue(rows[1]["comparable_eligible"])
        self.assertEqual(rows[2]["record_kind"], "OBSERVATION_SEGMENT")
        self.assertFalse(rows[2]["comparable_eligible"])
        self.assertEqual(ledger.comparable(terrain="UP_RAIL", side="YES"), [rows[1]])

    def test_continuity_reset_never_joins_an_old_quote_to_a_new_generation(self):
        ledger = LegPerformanceLedger()
        ledger.observe(snapshot(1000, yes_ask=.001, yes_bid=.0005))
        ledger.observe(snapshot(1001, generation=1, yes_ask=.81, yes_bid=.80))
        ledger.finalize()
        self.assertEqual(len(ledger.completed), 2)
        self.assertEqual(ledger.completed[0]["end_reason"], "GEOMETRY_CONTINUITY_CHANGED")
        self.assertTrue(all(row["record_kind"] == "OBSERVATION_SEGMENT" for row in ledger.completed))
        self.assertTrue(all(not row["comparable_eligible"] for row in ledger.completed))
        self.assertLess(ledger.completed[1]["yes_opportunity"]["potential_roi_from_best_observed_basis"], 0)

    def test_source_update_counter_is_not_physical_continuity_generation(self):
        ledger = LegPerformanceLedger()
        for t, counter in ((1000, 1), (1001, 2), (1002, 999)):
            s = snapshot(t)
            ledger.observe(replace(s, metadata={**s.metadata, "source_generation": counter}))
        self.assertEqual(ledger.completed, [])
        self.assertEqual(ledger.live.sample_count, 3)

    def test_regressed_clock_and_unavailable_physical_source_close_segments(self):
        for changed, reason in ((snapshot(999), "OBSERVATION_TIME_REGRESSION"),
                                (snapshot(1001, current=False), "PHYSICAL_SOURCE_NOT_CURRENT")):
            with self.subTest(reason=reason):
                ledger = LegPerformanceLedger()
                ledger.observe(snapshot(1000))
                ledger.observe(changed)
                self.assertEqual(ledger.completed[0]["end_reason"], reason)
                self.assertEqual(ledger.completed[0]["record_kind"], "OBSERVATION_SEGMENT")

    def test_territory_without_any_physical_identity_does_not_create_a_leg(self):
        ledger = LegPerformanceLedger()
        for terrain in ("UP_RAIL", "UNKNOWN", "UP_RAIL", "MARKET_HEIST"):
            ledger.observe(snapshot(leg=None, child=None, terrain=terrain))
        self.assertIsNone(ledger.live)
        self.assertEqual(ledger.completed, [])


class CustodyResearchValidityTests(unittest.TestCase):
    def test_valid_single_contract_opportunity_is_backwards_readable(self):
        row = complete_leg()
        opportunity = row["yes_opportunity"]
        self.assertAlmostEqual(opportunity["potential_roi_from_best_observed_basis"], .5)
        self.assertEqual(opportunity, row["contract_opportunities"][0]["yes_opportunity"])
        self.assertEqual(len(validated_contract_opportunities(row, "YES")), 1)

    def test_rollover_contracts_do_not_inflate_comparable_leg_count(self):
        row = complete_leg(tickers=("A", "B", "C", "D"))
        s = snapshot()
        s = replace(s, metadata={**s.metadata, "leg_echo": {"completed_comparable_legs": [row]}})
        evidence = build_custody_evidence({"side": "YES", "entry_price": .20}, s)
        self.assertEqual(evidence["comparable_leg_count"], 1)
        self.assertEqual(evidence["historical_opportunity_count"], 4)
        self.assertAlmostEqual(evidence["historical_median_potential_roi"], .5)
        self.assertFalse(evidence["low_motion_history_35_80"])
        self.assertEqual(evidence["recommendation"], "HOLD")

    def test_valid_history_retains_research_but_adds_no_exit_rule(self):
        rows = [complete_leg(name=f"P{i}") for i in range(3)]
        s = snapshot(yes_ask=.50, yes_bid=.49)
        md = deepcopy(s.metadata)
        md["mountain"]["stall"] = True
        md["leg_echo"] = {"completed_comparable_legs": rows}
        evidence = build_custody_evidence({"side": "YES", "entry_price": .20}, replace(s, metadata=md))
        self.assertEqual(evidence["comparable_leg_count"], 3)
        self.assertTrue(evidence["low_motion_history_35_80"])
        self.assertEqual(evidence["recommendation"], "HOLD")
        self.assertEqual(evidence["reason"], "COMMANDER_MOUNTAIN_ONLY_LEG_STILL_ACTIVE")

    def test_forged_cross_ticker_or_noncausal_pair_is_rejected(self):
        for key, value in (("max_bid_ticker", "OTHER_CONTRACT"), ("max_bid_ts", 999),
                           ("potential_roi_from_best_observed_basis", 799.0)):
            with self.subTest(field=key):
                row = complete_leg()
                row["contract_opportunities"][0]["yes_opportunity"][key] = value
                self.assertEqual(validated_contract_opportunities(row, "YES"), [])


if __name__ == "__main__":
    unittest.main()
