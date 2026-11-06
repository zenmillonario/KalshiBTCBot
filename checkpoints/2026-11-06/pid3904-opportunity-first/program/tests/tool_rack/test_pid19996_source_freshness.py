"""PID19996 exact observation repair and adverse source/receipt boundaries.

Recorded inputs are hashed originals.  Reconstruction uses the same new
runtime bridge over each record's frozen source_status; it never rewrites a
source time, adds a later quote, or claims an alternative trade outcome.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from strategy_core.commander import OneCommander
from strategy_core.mission_policy import MissionPolicy
from strategy_core.paper_execution import PaperBook, PaperExecutioner, PriceLevel
from strategy_core.paper_runtime import ToolRackPaperEngine, plain, snapshot_from_book
from strategy_core.position_roles import normal_role_entry_denial
from strategy_core.recovery import independent_entry_denial
from strategy_core.source_freshness import (
    RECEIPT_KEY, capture_source_receipt, current_source_is_fresh,
    current_source_receipt, source_receipt_is_fresh,
)
from strategy_core.tool_rack import ToolRackController
from strategy_core.tools.management import (
    entry_candle_evidence, mission_collection_evidence, physical_management_evidence,
)
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


@lru_cache(maxsize=1)
def corpus():
    path = Path(__file__).with_name("fixtures") / "pid19996_source_freshness_cases.json.gz"
    data = json.loads(gzip.decompress(path.read_bytes()))
    if data["schema"] != "TACHYOS_PID19996_SOURCE_FRESHNESS_CASES_V1":
        raise ValueError("Unexpected PID19996 source case schema")
    for sequence, item in data["records"].items():
        payload = dict(item["record"])
        expected = payload.pop("sha256")
        actual = hashlib.sha256(json.dumps(payload, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if actual != expected or actual != item["original_record_sha256"] or int(sequence) != payload["sequence"]:
            raise ValueError("Original PID19996 record changed: " + sequence)
    for position_id, item in data["entries"].items():
        payload = dict(item["journal_record"])
        expected = payload.pop("sha256")
        actual = hashlib.sha256(json.dumps(payload, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if actual != expected:
            raise ValueError("Original PID19996 entry journal changed: " + position_id)
    return data


def recorded_snapshot(sequence, *, receipt=True):
    record = deepcopy(corpus()["records"][str(sequence)]["record"])
    metadata = record["physical_metadata"]
    if receipt:
        status = record["source_status"]
        # source_age = captured_at - source_epoch/1000 in the frozen feed.
        # Recover that original capture clock algebraically; neither clock is
        # aligned or shifted to make the frame pass a check.
        captured_at = (metadata["current_geometry"]["epoch_ms"] / 1000.
                       + status["btc_geometry_age_seconds"])
        metadata[RECEIPT_KEY] = capture_source_receipt(metadata, status,
            captured_at=captured_at, source_generation=record["source_generation"])
    raw = record["native_book"]
    raw["yes_bids"] = tuple(PriceLevel(**level) for level in raw["yes_bids"])
    raw["no_bids"] = tuple(PriceLevel(**level) for level in raw["no_bids"])
    return snapshot_from_book(PaperBook(**raw), now_ts=record["now_ts"],
        metadata=metadata, ticker=record["market"]["ticker"], close_ts=record["market"]["close_ts"])


def original_position(position_id):
    key = str(position_id)
    return deepcopy(corpus()["entries"][key]["journal_record"]["state"]["positions"][key])


def scene(*, now=1000., source_age=-1., receive_age=.1, receipt=True):
    """Labelled synthetic boundary; no recorded input or later outcome."""
    source = (now - source_age) * 1000.
    metadata = {
        "source": "DIRECT_BTC_AND_NATIVE_KALSHI", "physical_current": True,
        "geometry_last_epoch_ms": source, "geometry_max_source_age_seconds": 5.,
        "geometry_max_future_skew_seconds": 2., "geometry_continuity_generation": 0,
        "source_generation": 41,
        "current_geometry": {"epoch_ms": source, "source_sequence": 31,
            "connection_epoch": 1, "measurement_source": "DIRECT_CAUSAL_BTC_EMA9_V2_NATIVE_CURRENT_LEG",
            "btc_price": 100., "ema9": 99., "ema30": 98., "range60": 20.},
        "quote_id": "NATIVE:1", "quote_observed_ts": now,
        "native_depth": {"ticker": "KX-FRESH", "quote_id": "NATIVE:1",
            "yes_bids": ((.49, 100),), "no_bids": ((.49, 100),)},
    }
    if receipt:
        status = {"revision": "TOOL_RACK_DIRECT_MARKET_DATA_V1",
            "geometry_source": "DIRECT_COINBASE_PUBLIC_TRADES",
            "captured_together_without_producer_reread": True,
            "btc_current": True, "btc_geometry_age_seconds": source_age,
            "btc_geometry_receive_age_seconds": receive_age, "btc_connection_epoch": 1}
        metadata[RECEIPT_KEY] = capture_source_receipt(metadata, status,
            captured_at=now, source_generation=41)
    return MarketSnapshot(now, "KX-FRESH", 100., .51, .51,
        metadata=metadata, yes_bid=.49, no_bid=.49, yes_sell_allowed=True, no_sell_allowed=True)


def source(snapshot):
    return snapshot.metadata["current_geometry"]["epoch_ms"]


def changed(snapshot, key, value):
    metadata = deepcopy(snapshot.metadata)
    metadata[key] = value
    return replace(snapshot, metadata=metadata)


def role_scene(snapshot, *, recovery=False):
    held = {"position_id": "P1", "ticker": snapshot.ticker, "side": "YES",
        "position_role": "PRIMARY", "custody_state": "LAZARUS" if recovery else "NORMAL",
        "territory_id": "OLD", "opportunity_id": "OLD:1",
        "entry_metadata": {"physical_mission_id": "OLD:MISSION"}}
    intent = ToolIntent(tool="RAIL", territory_id="NEW", lane=Lane.TACTICAL,
        side=Side.NO, action=Action.ENTER, opportunity_id="NEW:1", max_price=.51,
        size_tier=10., reason="FRESHNESS_BOUNDARY", source_time=snapshot.now_ts,
        metadata={"position_role": "TACTICAL", "physical_mission_id": "NEW:MISSION",
            "physical_renewal": {"independent": True, "renewal_kind": "NEW_RAIL_TERRITORY",
                "observed_at": source(snapshot) / 1000.}})
    return held, intent


class PID19996RecordedSourceFreshnessTests(unittest.TestCase):
    def test_all_thirteen_recorded_frames_keep_their_original_hash(self):
        self.assertEqual(len(corpus()["records"]), 13)
        self.assertEqual(len(corpus()["entries"]), 3)

    def test_quote_observer_replaces_stale_eleven_cent_quote_with_current_six_cents(self):
        old, repaired = MissionPolicy(), MissionPolicy()
        for sequence in (4608, 4609, 4728):
            legacy, current = recorded_snapshot(sequence, receipt=False), recorded_snapshot(sequence)
            old.observe(legacy)
            repaired.observe(current)
        self.assertEqual(old.quote_wave_briefing(legacy)["observed_points"], 2)
        self.assertAlmostEqual(old.quote_wave_briefing(legacy)["sides"]["NO"]["current_ask"], .11)
        briefing = repaired.quote_wave_briefing(current)
        self.assertEqual(briefing["observed_points"], 3)
        self.assertAlmostEqual(briefing["sides"]["NO"]["current_ask"], .06)
        self.assertEqual(repaired._quotes[-1]["source_ms"], source(current))
        self.assertEqual(repaired._quotes[-1]["time"], current.now_ts)
        self.assertEqual(repaired._quotes[-1]["quote_time"], current.metadata["quote_observed_ts"])

    def test_new_contract_observer_accepts_exact_received_quote_and_clears_old_contract(self):
        observer = MissionPolicy()
        for sequence in (4608, 4609, 4728, 7793):
            current = recorded_snapshot(sequence)
            observer.observe(current)
        briefing = observer.quote_wave_briefing(current)
        self.assertEqual(briefing["observed_points"], 1)
        self.assertAlmostEqual(briefing["sides"]["NO"]["current_ask"], .047)
        self.assertEqual(briefing["ticker"], current.ticker)
        old = MissionPolicy()
        old.observe(recorded_snapshot(7793, receipt=False))
        self.assertEqual(old.quote_wave_briefing(current)["observed_points"], 0)

    def test_nine_held_frames_use_received_geometry_and_actual_filled_candle(self):
        cases = ((3127, 1, False), (4556, 1, True), (4557, 1, True),
                 (6321, 2, False), (7788, 2, True), (8724, 3, False),
                 (9018, 3, True), (9173, 3, True), (9439, 3, True))
        for sequence, position_id, complete in cases:
            with self.subTest(sequence=sequence):
                position, current = original_position(position_id), recorded_snapshot(sequence)
                before = deepcopy(position)
                candle = entry_candle_evidence(position, current)
                self.assertTrue(current_source_is_fresh(current, source(current)))
                self.assertTrue(physical_management_evidence(position, current)["physical_current"])
                self.assertTrue(candle["current_source_is_fresh"])
                self.assertEqual(candle["entry_candle_complete"], complete)
                self.assertIsNone(candle["entry_source_epoch_ms"], "No invented proof for a historical entry")
                legacy = recorded_snapshot(sequence, receipt=False)
                self.assertFalse(physical_management_evidence(position, legacy)["physical_current"])
                self.assertEqual(position, before)

    def test_quote_identity_and_local_receive_clock_remain_strict(self):
        current = recorded_snapshot(4728)
        mutations = (
            changed(current, "quote_observed_ts", current.now_ts + .001),
            changed(current, "quote_observed_ts", current.now_ts - 3.001),
            changed(current, "quote_id", "FOREIGN-QUOTE"),
            changed(current, "native_depth", {**current.metadata["native_depth"], "ticker": "FOREIGN"}),
            replace(current, quote_current=False), replace(current, entry_allowed=False),
        )
        for bad in mutations:
            with self.subTest(metadata=bad.metadata.get("quote_id"), time=bad.metadata.get("quote_observed_ts")):
                observer = MissionPolicy()
                observer.observe(bad)
                self.assertFalse(observer._quotes)
        observer = MissionPolicy()
        observer.observe(current)
        observer.observe(current)
        self.assertEqual(len(observer._quotes), 1, "The same quote cannot become two independent observations")

    def test_recorded_holds_successful_peak_exits_and_final_exit_keep_exact_floor_results(self):
        # These are isolated decision-boundary checks, not an alternative
        # run. Restore original treasury/held state, evaluate the same native
        # book with the real floor writer, then let Commander decide. The
        # recorded post-floor outcome is an assertion, never the input floor.
        from tests.tool_rack.pid19996_rail_fixtures import (
            record, snapshot_from_record, intent_from_dict, book_from_record,
        )
        for sequence in (3127, 4303, 4557, 6321, 7788, 9308, 9439):
            with self.subTest(sequence=sequence), tempfile.TemporaryDirectory() as directory:
                data = record(sequence)
                current, book = snapshot_from_record(data), book_from_record(data)
                position = data["physical_metadata"]["position_inventory"][0]
                position_id = position["position_id"]
                original = next(row for row in data["decisions"] if row["scope"] == "POSITION")
                intents = tuple(intent_from_dict(row) for row in original["tool_intents"])
                executor = PaperExecutioner(Path(directory))
                try:
                    executor._state = deepcopy(corpus()["entries"][position_id]["journal_record"]["state"])
                    executor._state["positions"][position_id] = position
                    executor._reconcile(executor._state)
                    mark = executor.remaining_exit_mark(book, position_id=position_id, now_ts=current.now_ts)
                    current = replace(current, metadata={**current.metadata, "paper_exit_mark": mark,
                        "paper_execution_state": {"journal_seq": mark["journal_seq"],
                            "journal_sha256": mark["journal_sha256"]}})
                    policy = ToolRackPaperEngine._floor_policy(intents, executor.positions[position_id], current)
                    floors = executor.observe_floors(book, now_ts=current.now_ts,
                        policies={position_id: policy} if policy else {}, position_ids=(position_id,))
                    decision = OneCommander().decide_position(intents, current,
                        plain(executor.positions[position_id]), floor_breached=floors[0].breached,
                        recovery_review=original["decision"].get("custody_review"))
                    self.assertEqual(plain(floors), original["floors"])
                    self.assertEqual(decision.action.value, original["decision"]["action"])
                    if sequence in (3127,9308):
                        # Same held lot and exact floor observations. The new
                        # parent-scale review names why no collection is due;
                        # the old local-child label is no longer its authority.
                        self.assertIs(decision.action,Action.HOLD)
                        self.assertEqual(decision.reason,'COMMANDER_MAIN_PARENT_COLLECTION_UNVERIFIED')
                        self.assertEqual(decision.intent.reason,'COMMANDER_MAIN_PARENT_COLLECTION_UNVERIFIED')
                    else:
                        self.assertEqual(decision.reason, original["decision"]["reason"])
                        self.assertEqual(decision.intent.reason, original["decision"]["intent"]["reason"])
                finally:
                    executor.close()


class PID19996ReceiptBoundaryTests(unittest.TestCase):
    def test_runtime_carries_existing_monotonic_receipt_without_changing_feed_or_source_time(self):
        from tests.tool_rack.test_direct_paper_runtime import capture, raw_rows
        frame = capture(rows=tuple({**row, "epoch_ms": row["epoch_ms"] + 1000.}
            for row in raw_rows()))
        frame = replace(frame, source_status={"revision": "TOOL_RACK_DIRECT_MARKET_DATA_V1",
            "geometry_source": "DIRECT_COINBASE_PUBLIC_TRADES", "btc_current": True,
            "book_current": True, "btc_geometry_age_seconds": -1.,
            "btc_geometry_receive_age_seconds": .1, "btc_connection_epoch": 1,
            "captured_together_without_producer_reread": True})
        before = frame.to_dict()
        with tempfile.TemporaryDirectory() as directory:
            engine = ToolRackPaperEngine(Path(directory))
            try:
                result = engine.process(frame, now_ts=frame.observed_ts, entry_window_closed=True)
                metadata = result["status"]["physical"]
                receipt = metadata[RECEIPT_KEY]
                self.assertEqual(receipt["captured_at"], frame.observed_ts)
                self.assertEqual(receipt["source_ms"], frame.geometry_rows[-1]["epoch_ms"])
                self.assertEqual(receipt["receive_age_seconds_at_capture"], .1)
                self.assertEqual(len(engine.rack.mission_policy._quotes), 1)
                self.assertEqual(engine.rack.mission_policy._quotes[0]["source_ms"], receipt["source_ms"])
                self.assertEqual(frame.to_dict(), before)
                self.assertFalse(result["receipts"])
            finally:
                engine.close(reason="OFFLINE_FRESHNESS_FIXTURE_COMPLETE")

    def test_existing_source_age_ceilings_and_two_second_future_boundary(self):
        for age, maximum, expected in ((-2., 3., True), (-2.0001, 3., False),
                (-1., 3., True), (0., 3., True), (3., 3., True),
                (3.0001, 3., False), (5., 5., True), (5.0001, 5., False)):
            with self.subTest(age=age, maximum=maximum):
                current = scene(source_age=age)
                self.assertEqual(current_source_is_fresh(current, source(current),
                    max_age_seconds=maximum), expected)

    def test_legacy_nonnegative_age_is_preserved_but_future_never_gets_a_free_pass(self):
        for age, expected in ((0., True), (3., True), (-.001, False), (5.001, False)):
            current = scene(source_age=age, receipt=False)
            self.assertEqual(current_source_is_fresh(current, source(current)), expected)

    def test_missing_stale_future_or_false_receipt_cannot_grant_source_currentness(self):
        current = scene()
        mutations = (("receive_age_seconds_at_capture", None),
            ("receive_age_seconds_at_capture", 5.001), ("receive_age_seconds_at_capture", -.001),
            ("captured_at", current.now_ts + .001), ("source_age_seconds_at_capture", -.5),
            ("btc_current_at_capture", False), ("physical_current_at_capture", False),
            ("connection_epoch", 2), ("source_sequence", None),
            ("continuity_generation", None), ("source_generation", None),
            ("measurement_source", "UNVERIFIED"))
        for key, value in mutations:
            with self.subTest(field=key, value=value):
                proof = {**current.metadata[RECEIPT_KEY], key: value}
                bad = changed(current, RECEIPT_KEY, proof)
                self.assertFalse(current_source_is_fresh(bad, source(bad)))
        self.assertFalse(current_source_is_fresh(changed(current, "physical_current", False), source(current)))
        self.assertFalse(current_source_is_fresh(changed(current, RECEIPT_KEY, None), source(current)))

    def test_receipt_must_belong_to_exact_geometry_epoch_sequence_and_continuity(self):
        current = scene()
        for key, value in (("epoch_ms", source(current) + 1), ("connection_epoch", 2),
                           ("source_sequence", 32), ("measurement_source", "UNKNOWN")):
            bad = changed(current, "current_geometry", {**current.metadata["current_geometry"], key: value})
            self.assertFalse(current_source_is_fresh(bad, source(current)), key)
        for key, value in (("geometry_last_epoch_ms", source(current) - 1),
                ("geometry_continuity_generation", 1), ("geometry_continuity_generation", False),
                ("source_generation", 42),
                ("source", "UNVERIFIED"), ("geometry_max_future_skew_seconds", 3.)):
            self.assertFalse(current_source_is_fresh(changed(current, key, value), source(current)), key)
        self.assertFalse(current_source_is_fresh(current, source(current) - 1))

    def test_current_label_cannot_keep_an_old_local_receipt_alive(self):
        current = scene(receive_age=1.)
        later = replace(current, now_ts=current.now_ts + 4.001)
        self.assertLess(later.now_ts - source(later) / 1000., 5.)
        self.assertFalse(current_source_is_fresh(later, source(later)))
        positive = scene(source_age=1., receive_age=5.001)
        self.assertFalse(current_source_is_fresh(positive, source(positive)))

    def test_configured_future_allowance_can_be_stricter_but_never_exceed_two_seconds(self):
        for age, configured, expected in ((-1., .5, False), (-.5, .5, True), (-2.5, 3., False)):
            current = scene(source_age=age)
            metadata = deepcopy(current.metadata)
            metadata["geometry_max_future_skew_seconds"] = configured
            metadata[RECEIPT_KEY]["max_future_skew_seconds"] = configured
            current = replace(current, metadata=metadata)
            self.assertEqual(current_source_is_fresh(current, source(current)), expected)

    def test_source_ahead_cannot_complete_the_actual_filled_minute_early(self):
        position = {"entry_time": 59.5, "entry_metadata": {"entry_geometry_source_ms": 59000.}}
        current = scene(now=59.8)
        candle = entry_candle_evidence(position, current)
        self.assertTrue(candle["current_source_is_fresh"])
        self.assertEqual(candle["current_source_candle_start_ms"], 60000.)
        self.assertFalse(candle["entry_candle_complete"])
        self.assertTrue(entry_candle_evidence(position, scene(now=60.1))["entry_candle_complete"])

    def test_source_ahead_at_entry_preserves_its_actual_source_candle_with_frozen_receipt(self):
        entry = scene(now=59.5)
        position = {"entry_time": entry.now_ts, "entry_metadata": {
            "entry_geometry_source_ms": source(entry),
            "entry_source_receipt": current_source_receipt(entry, source(entry))}}
        candle = entry_candle_evidence(position, scene(now=60.1))
        self.assertEqual(candle["entry_fill_candle_start_ms"], 0.)
        self.assertEqual(candle["entry_source_candle_start_ms"], 60000.)
        self.assertFalse(candle["entry_candle_complete"])
        self.assertTrue(entry_candle_evidence(position, scene(now=120.1))["entry_candle_complete"])

    def test_frozen_entry_receipt_is_required_for_new_future_source_mission(self):
        current = scene()
        metadata = deepcopy(current.metadata)
        metadata["mission_context"] = {"current": True, "source_ms": source(current),
            "continuity_generation": 0, "parent": {"id": "P", "status": "ACTIVE",
                "side": "YES", "supported": True, "invalidated": False}}
        current = replace(current, metadata=metadata)
        mission = {"purpose": "MAIN_CONTRACT", "side": "YES", "source_ms": source(current),
            "continuity_generation": 0, "parent_leg_id": "P"}
        position = {"ticker": current.ticker, "side": "YES", "entry_time": current.now_ts,
            "close_ts": current.now_ts + 600., "entry_metadata": {"mission": mission}}
        self.assertFalse(mission_collection_evidence(position, current)["valid"])
        mission["source_receipt"] = current_source_receipt(current, source(current))
        evidence = mission_collection_evidence(position, current)
        self.assertTrue(evidence["valid"])
        self.assertTrue(evidence["current"])
        self.assertFalse(evidence["collection_qualified"], "Freshness alone does not earn an exit")
        self.assertFalse(source_receipt_is_fresh(mission["source_receipt"],
            now_ts=current.now_ts + 6., source_ms=source(current)))

    def test_normal_role_proof_separates_source_and_local_time_and_rechecks_at_boundary(self):
        current = scene()
        held, intent = role_scene(current)
        qualified = ToolRackController().qualify_independent_role_mission(intent, current, {"P1": held})
        proof = qualified.metadata["independent_role_mission"]
        self.assertEqual(proof["observed_ts"], current.now_ts)
        self.assertGreater(proof["source_ms"] / 1000., proof["observed_ts"])
        self.assertIsNone(normal_role_entry_denial(qualified, [held], now_ts=current.now_ts, continuity_generation=0))
        for key, value in (("source_receipt", None), ("observed_ts", current.now_ts + .001)):
            bad = replace(qualified, metadata={**qualified.metadata,
                "independent_role_mission": {**proof, key: value}})
            self.assertEqual(normal_role_entry_denial(bad, [held], now_ts=current.now_ts),
                "CURRENT_NORMAL_ROLE_SOURCE_REQUIRED")
        self.assertEqual(normal_role_entry_denial(qualified, [held], now_ts=current.now_ts,
            continuity_generation=1), "NORMAL_ROLE_SOURCE_GENERATION_MISMATCH")

    def test_recovery_mission_receipt_cannot_be_downgraded_to_an_unproved_future_source(self):
        current = scene()
        held, intent = role_scene(current, recovery=True)
        rack = ToolRackController()
        rack._recovery_detached.add((held["ticker"], held["territory_id"], held["opportunity_id"]))
        qualified = rack.qualify_independent_recovery_mission(intent, current, {"P1": held})
        proof = qualified.metadata["independent_recovery_mission"]
        self.assertEqual(proof["observed_ts"], current.now_ts)
        self.assertIsNone(independent_entry_denial(qualified, [held], now_ts=current.now_ts, continuity_generation=0))
        missing = dict(proof)
        missing.pop("source_receipt")
        bad = replace(qualified, metadata={**qualified.metadata, "independent_recovery_mission": missing})
        self.assertEqual(independent_entry_denial(bad, [held], now_ts=current.now_ts),
            "INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED")
        unproven = changed(current, RECEIPT_KEY, None)
        self.assertNotIn("independent_recovery_mission",
            rack.qualify_independent_recovery_mission(intent, unproven, {"P1": held}).metadata)

    def test_recent_swing_source_alias_uses_physical_receipt_but_settlement_time_stays_local(self):
        current = scene()
        metadata = deepcopy(current.metadata)
        metadata["recovery_swing_terrain"] = {"active": True, "observed_ts": source(current) / 1000.}
        metadata["verified_settlement_geometry"] = {"verified": True, "ticker": current.ticker,
            "target": 500., "observed_ts": current.now_ts + .001}
        current = replace(current, metadata=metadata)
        position = {"side": "YES", "ticker": current.ticker, "close_ts": current.now_ts + 30.}
        evidence = physical_management_evidence(position, current)
        self.assertTrue(evidence["credible_recovery_terrain"])
        self.assertFalse(evidence["terminal_impossibility"])


if __name__ == "__main__":
    unittest.main()
