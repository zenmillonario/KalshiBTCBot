"""Source-bound active-pattern display and immutable as-issued comparisons."""
from copy import deepcopy
import json
import math
from pathlib import Path
import unittest

from strategy_core.looking_glass import build_looking_glass
from strategy_core.nautilus_projection import NautilusProjection, looking_glass_pattern_context
from tests.tool_rack.test_nautilus_projection import native, status


def pattern_fixture(kind="UP_RAIL", *, shape="rail", now=3900.0, identity="T1"):
    """Explicit synthetic profiles, never represented as recorded market results."""
    def price(at):
        delta = at - 1800
        return 80000 + .04 * delta if shape == "rail" else 80000 + 50 * math.sin(delta * math.pi / 300)
    bars = []
    for end in range(1800, int(now) + 1, 60):
        e9 = price(end)
        bars.append({"time": float(end - 60), "open": e9 - 4, "high": e9 + 8, "low": e9 - 8,
                     "close": e9 + 2, "e9": e9, "e30": e9 - 15,
                     "complete": True, "known_at": float(end), "quality": "SYNTHETIC_UI_CONSTRUCT"})
    e9 = price(now)
    direction = "UP" if price(now) > price(now - 60) else "DOWN"
    market = {"ticker": "SYNTHETIC_CURRENT", "time": now, "close_ts": 4500.0,
              "target": 80080.0, "btc": e9 + 2, "e9": e9, "e30": e9 - 15, "fresh": True}
    context = {"ticker": market["ticker"], "source_ts": now, "observed_at": now,
               "physical_current": True, "continuity_generation": 0,
               "owned_territory": kind, "owned_side": "NO" if kind == "DOWN_RAIL" else "YES",
               "territory_id": identity, "current_direction": direction,
               "handoff_confirmed": False, "release_in_progress": False}
    return {"market": market, "candles": bars, "now_ts": now, "pattern_context": context}


def sprout_context(context):
    source = context["source_ts"]
    context.update(owned_territory="MARKET_HEIST", owned_side="YES", current_direction="UP",
        mission={"current": True, "source_ts": source, "parent_id": "P000L000017",
                 "side": "YES", "status": "ACTIVE", "supported": True, "invalidated": False,
                 "terminal": False, "current_progress_supported": True},
        gap={"source_ts": source, "stage": "SPROUT", "side": "YES",
             "continued_on_latest_cross_side": True})


def chart_fixture(kind="UP_RAIL", *, shape="rail", now=3900.0):
    args = pattern_fixture(kind, shape=shape, now=now)
    glass = build_looking_glass(**args)
    return {"server_now": now, "run": {"name": "SYNTHETIC_UI_CONSTRUCT", "run_id": "SYNTHETIC_UI_CONSTRUCT", "fresh": True, "stopped": False},
            "market": args["market"], "looking_glass": glass, "candles": args["candles"],
            "emas": [{"time": row["time"], "e9": row["e9"], "e30": row["e30"]} for row in args["candles"]],
            "targets": [], "quotes": [], "trades": []}


def construct_fixtures():
    fixtures = {"rail": chart_fixture(),
                "mountain": chart_fixture("ALTERNATING_MOUNTAIN", shape="mountain"),
                "finite": chart_fixture(shape="mountain")}
    for name, confirmed in (("release", True), ("forming", False)):
        args = pattern_fixture("RELEASE_TRANSITION")
        args["pattern_context"].update(release_in_progress=True, release_candidate_side="YES", handoff_confirmed=confirmed)
        fixtures[name] = {**chart_fixture(), "looking_glass": build_looking_glass(**args)}
    args = pattern_fixture()
    sprout_context(args["pattern_context"])
    fixtures["sprout"] = {**chart_fixture(), "looking_glass": build_looking_glass(**args)}
    source = status(ts=3900.0, book=native(3900.0, ticker=args["market"]["ticker"], close=4500.0), run="SYNTHETIC_UI_CONSTRUCT")
    source["market"].update(target=args["market"]["target"], target_source="KALSHI_MARKET_FLOOR_STRIKE")
    source["rack"].update(owned_territory="UP_RAIL", owned_side="YES", territory_id="T1")
    source["physical"].update(geometry_continuity_generation=0, current_geometry={"current_native_direction": "UP"})
    source["latest_geometry"].update(btc_price=args["market"]["btc"], ema9=args["market"]["e9"], ema30=args["market"]["e30"])
    fixtures["dashboard"] = NautilusProjection().project(source, chart_data={"candles": args["candles"]}, now_ts=3900.0)
    return fixtures


class LookingGlassPatternTests(unittest.TestCase):
    def test_recorded_7304_7584_contexts_feature_current_fresh_up_leg(self):
        source = json.loads((Path(__file__).parent / "fixtures" / "pid10656_looking_glass_contexts.json").read_text(encoding="utf-8"))
        self.assertTrue(source["retrospective_not_original_as_issued"])
        self.assertEqual([case["sequence"] for case in source["cases"]], [7304, 7584])
        for case in source["cases"]:
            with self.subTest(sequence=case["sequence"]):
                self.assertLessEqual(case["last_received_frame_wall"], case["now_ts"])
                result = build_looking_glass(case["market"], case["candles"], now_ts=case["now_ts"], pattern_context=case["pattern_context"])
                active = result["active_pattern"]
                self.assertEqual((active["status"], active["kind"], active["direction"]), ("READY", "FRESH_LEG", "UP"))
                self.assertFalse(active["confirmed_release"])
                self.assertLessEqual(active["reference_end_ts"], case["market"]["close_ts"] - 900)
                self.assertLessEqual(active["horizon_ts"], case["market"]["close_ts"])

    def test_rail_features_a_matching_unchanged_continuation(self):
        args = pattern_fixture()
        original = deepcopy(args)
        generic = build_looking_glass(**{key: value for key, value in args.items() if key != "pattern_context"})
        result = build_looking_glass(**args)
        active = result["active_pattern"]
        self.assertEqual((active["status"], active["kind"], active["direction"]), ("READY", "UP_RAIL", "UP"))
        self.assertEqual(result["paths"], generic["paths"], "Feature selection must not reshape an existing matching path")
        selected = next(row for row in result["paths"] if row["id"] == active["path_id"])
        self.assertTrue(all(b["e9"] >= a["e9"] for a, b in zip(selected["points"], selected["points"][1:])))
        self.assertFalse(active["execution_authority"])
        self.assertFalse(active["selection_is_probability"])
        self.assertEqual(args, original)

    def test_down_rail_uses_down_shape_and_explicit_mirroring(self):
        result = build_looking_glass(**pattern_fixture("DOWN_RAIL"))
        active = result["active_pattern"]
        selected = next(row for row in result["paths"] if row["id"] == active["path_id"])
        self.assertEqual(active["direction"], "DOWN")
        self.assertTrue(active["mirrored"])
        self.assertLess(selected["points"][-1]["e9"], selected["points"][0]["e9"])

    def test_alternating_and_rolling_mountains_keep_an_observed_turn(self):
        for kind in ("ALTERNATING_MOUNTAIN", "ROLLING_MOUNTAIN"):
            with self.subTest(kind=kind):
                result = build_looking_glass(**pattern_fixture(kind, shape="mountain"))
                active = result["active_pattern"]
                self.assertEqual(active["status"], "READY")
                self.assertGreaterEqual(active["historical_ema9_turns"], 1)
                self.assertIn("next arc", active["label"])
                self.assertLessEqual(active["reference_end_ts"], 3600.0)

    def test_fresh_supported_parent_takes_precedence_over_local_heist(self):
        args = pattern_fixture()
        sprout_context(args["pattern_context"])
        active = build_looking_glass(**args)["active_pattern"]
        self.assertEqual((active["kind"], active["direction"], active["local_context"]), ("FRESH_LEG", "UP", "MARKET_HEIST"))
        self.assertIn("Fresh up leg", active["label"])
        self.assertFalse(active["confirmed_release"], "A crossing is not a confirmed handoff")

    def test_stale_or_invalid_parent_cannot_borrow_the_sprout_label(self):
        mutations = [lambda c: c["mission"].update(source_ts=3899),
                     lambda c: c["gap"].update(source_ts=3899),
                     lambda c: c["mission"].update(invalidated=True),
                     lambda c: c["mission"].update(current_progress_supported=False),
                     lambda c: c["mission"].update(terminal=True)]
        for mutate in mutations:
            args = pattern_fixture()
            sprout_context(args["pattern_context"])
            mutate(args["pattern_context"])
            self.assertNotEqual(build_looking_glass(**args)["active_pattern"]["kind"], "FRESH_LEG")

    def test_confirmed_release_and_forming_release_are_distinct(self):
        args = pattern_fixture("RELEASE_TRANSITION")
        args["pattern_context"].update(release_candidate_side="YES", release_in_progress=True)
        forming = build_looking_glass(**args)["active_pattern"]
        self.assertEqual(forming["kind"], "RELEASE_FORMING")
        self.assertIn("forming", forming["label"])
        self.assertFalse(forming["confirmed_release"])
        args["pattern_context"]["handoff_confirmed"] = True
        released = build_looking_glass(**args)["active_pattern"]
        self.assertEqual(released["kind"], "RELEASE")
        self.assertTrue(released["confirmed_release"])

    def test_finite_rail_fallback_stops_at_the_witnessed_shape(self):
        result = build_looking_glass(**pattern_fixture(shape="mountain"))
        active = result["active_pattern"]
        self.assertEqual(active["status"], "READY")
        path = next(row for row in result["paths"] if row["id"] == active["path_id"])
        self.assertEqual(path["family"], "PATTERN")
        self.assertLess(path["horizon_ts"], result["close_ts"])
        self.assertAlmostEqual(path["horizon_ts"] - result["source_ts"], path["reference_end_ts"] - path["reference_start_ts"])
        self.assertFalse(path["time_stretched"])
        self.assertFalse(path["repeated"])
        self.assertEqual(path["historical_ema9_turns"], 0)
        self.assertTrue(path["not_a_settlement_prediction"])

    def test_missing_shape_never_becomes_a_fabricated_next_mountain(self):
        result = build_looking_glass(**pattern_fixture("ALTERNATING_MOUNTAIN"))
        self.assertEqual(result["active_pattern"]["status"], "UNAVAILABLE")
        self.assertIsNone(result["active_pattern"]["path_id"])
        self.assertTrue(result["paths"], "Honest generic alternatives remain separately available")

    def test_no_current_pattern_on_stale_wrong_contract_or_wrong_source(self):
        for mutate in (lambda a: a["pattern_context"].update(physical_current=False),
                       lambda a: a["pattern_context"].update(ticker="PREVIOUS"),
                       lambda a: a["pattern_context"].update(source_ts=3899.9),
                       lambda a: a["pattern_context"].update(observed_at=3894),
                       lambda a: a["market"].update(fresh=False),
                       lambda a: a.update(now_ts=3904.0)):
            args = pattern_fixture()
            mutate(args)
            self.assertNotEqual(build_looking_glass(**args)["active_pattern"]["status"], "READY")

    def test_future_or_unfinished_history_cannot_change_active_trace(self):
        args = pattern_fixture(shape="mountain")
        baseline = build_looking_glass(**args)
        for extra in ({"time": 3900.0, "known_at": 3960.0, "complete": True},
                      {"time": 3540.0, "known_at": 4000.0, "complete": True},
                      {"time": 3540.0, "known_at": 3900.0, "complete": False}):
            args["candles"].append({**extra, "close": 9e8, "e9": 9e8, "e30": 9e8})
        result = build_looking_glass(**args)
        self.assertEqual(result["active_pattern"], baseline["active_pattern"])
        self.assertEqual(result["paths"], baseline["paths"])

    def test_adapter_copies_parent_and_gap_source_without_creating_authority(self):
        source = status(ts=3900.0)
        source["physical"].update(geometry_continuity_generation=0, current_geometry={"current_native_direction": "UP"},
            ema9_ema30_cross_context={"source_ms": 3900000.0, "gap_lifecycle": {"stage": "SPROUT", "current_side": "YES", "continued_on_latest_cross_side": True}})
        source["mission_context"] = {"source_ms": 3900000.0, "current": True,
            "parent": {"id": "P17", "side": "YES", "status": "ACTIVE", "supported": True,
                       "invalidated": False, "terminal": {"qualified": False}},
            "candidates": {"YES": {"current_progress_supported": True}}}
        original = deepcopy(source)
        args = pattern_fixture()
        args["pattern_context"] = looking_glass_pattern_context(source, args["market"], current=True)
        active = build_looking_glass(**args)["active_pattern"]
        self.assertEqual(active["kind"], "FRESH_LEG")
        self.assertEqual(active["source_ts"], 3900.0)
        self.assertEqual(source, original)

    def test_first_issued_sample_stays_fixed_and_detached(self):
        projection = NautilusProjection()
        projection._run_id = "RUN1"
        args = pattern_fixture()
        first = projection._looking_glass_view(args["market"], args["candles"], (), (), {}, 3900.0, args["pattern_context"])
        frozen = deepcopy(first["research"]["as_issued"])
        later = pattern_fixture(now=3901.0)
        later["market"]["btc"] += 20
        later["market"]["e9"] += 10
        second = projection._looking_glass_view(later["market"], later["candles"], (), (), {}, 3901.0, later["pattern_context"])
        self.assertEqual(second["research"]["as_issued"], frozen)
        self.assertNotEqual(second["paths"][0]["points"][0], frozen[0]["anchor"])
        first["research"]["as_issued"][0]["path"]["points"][0]["btc"] = 0
        self.assertEqual(list(projection._glass_issued.values())[0]["anchor"], frozen[0]["anchor"])
        self.assertFalse(second["research"]["persisted"])

    def test_as_issued_is_bounded_source_forward_and_cleared_for_a_new_run(self):
        projection = NautilusProjection()
        projection._run_id = "RUN1"
        for index in range(20):
            args = pattern_fixture(now=3900.0 + index / 10, identity=f"T{index}")
            view = projection._looking_glass_view(args["market"], args["candles"], (), (), {}, args["now_ts"], args["pattern_context"])
        self.assertEqual(len(view["research"]["as_issued"]), 16)
        args = pattern_fixture(identity="BACKDATED")
        backdated = projection._looking_glass_view(args["market"], args["candles"], (), (), {}, 3900.0, args["pattern_context"])
        self.assertEqual(backdated["research"]["as_issued"], [])
        self.assertEqual(len(projection._glass_issued), 16)
        projection.observe(status(ts=3902.0, run="RUN2"))
        self.assertEqual(len(projection._glass_issued), 0)

    def test_as_issued_requires_fresh_source_and_known_continuity(self):
        projection = NautilusProjection()
        for mutate in (lambda c: c.update(continuity_generation=None), lambda c: c.update(physical_current=False)):
            args = pattern_fixture()
            mutate(args["pattern_context"])
            view = projection._looking_glass_view(args["market"], args["candles"], (), (), {}, 3900.0, args["pattern_context"])
            self.assertEqual(view["research"]["as_issued"], [])
        json.dumps(view, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
