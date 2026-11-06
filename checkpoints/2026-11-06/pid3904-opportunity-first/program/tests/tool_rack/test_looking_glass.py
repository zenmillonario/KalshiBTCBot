"""Causal, bounded and non-authoritative Looking Glass display controls."""
from copy import deepcopy
import json
import math
import unittest

from strategy_core.looking_glass import LookingGlassConfig, build_looking_glass


def fixture(*, now=3900., target=80070.):
    bars = []
    for end in range(1800, int(now) + 1, 60):
        e9 = 80000 + .025 * (end - 1800) + 12 * math.sin((end - 1800) * math.pi / 450)
        btc = e9 + 8 * math.sin((end - 1800) * math.pi / 225)
        bars.append({"time": end - 60, "close": btc, "e9": e9, "e30": e9 - 10,
                     "complete": True, "known_at": float(end), "quality": "source"})
    last = bars[-1]
    market = {"ticker": "CURRENT", "time": now, "close_ts": 4500., "target": target,
              "btc": last["close"], "e9": last["e9"], "e30": last["e30"], "fresh": True}
    quote = {"ticker": "CURRENT", "time": now, "quote_id": "NOW", "fresh": True,
             "yes_ask": .30, "yes_bid": .29, "no_ask": .71, "no_bid": .70}
    return {"market": market, "candles": bars, "quote": quote, "now_ts": now}


class LookingGlassTests(unittest.TestCase):
    def test_paths_use_two_previous_contracts_and_end_at_exact_current_expiry(self):
        args = fixture()
        args["market"]["target"] = args["market"]["btc"]
        output = build_looking_glass(**args)
        self.assertEqual(output["status"], "READY")
        refs = output["reference_window"]
        self.assertEqual((refs["start_ts"], refs["end_ts"], refs["completed_prior_contracts"]),
                         (1800., 3600., 2))
        self.assertEqual(len(output["paths"]), 6)
        self.assertEqual({p["family"] for p in output["paths"]},
                         {"CONTINUATION", "ROTATION_STALL", "REVERSAL"})
        for path in output["paths"]:
            self.assertEqual(path["points"][0], {"time": 3900., "btc": args["market"]["btc"],
                                                "e9": args["market"]["e9"]})
            self.assertEqual(path["points"][-1]["time"], 4500.)
            self.assertTrue(all(3900 <= row["time"] <= 4500 for row in path["points"]))
            self.assertTrue(all(a["time"] < b["time"] for a, b in zip(path["points"], path["points"][1:])))
            self.assertLessEqual(path["reference_end_ts"], 3600.)
            self.assertTrue(path["conditional"])
            self.assertTrue(path["not_a_settlement_prediction"])
        self.assertEqual(output["thesis"]["side"], "MIXED")
        self.assertFalse(output["execution_authority"])
        self.assertFalse(output["can_order"])
        self.assertFalse(output["can_veto"])
        self.assertFalse(output["thesis"]["settlement_prediction"])

    def test_future_and_unfinished_bars_cannot_revise_past_profiles(self):
        args = fixture()
        original = build_looking_glass(**args)
        args["candles"].extend([
            {"time": 3900., "close": 1e8, "e9": 1e8, "e30": 1e8, "complete": True},
            {"time": 3540., "close": 1e8, "e9": 1e8, "e30": 1e8,
             "complete": True, "known_at": 4000.},
            {"time": 3540., "close": 1e8, "e9": 1e8, "e30": 1e8, "complete": False},
        ])
        output = build_looking_glass(**args)
        self.assertEqual(output["paths"], original["paths"])
        self.assertEqual(output["thesis"], original["thesis"])
        self.assertEqual(output["observations"], original["observations"])

    def test_a_missing_minute_is_not_bridged_into_a_historical_contract_profile(self):
        args = fixture()
        args["candles"] = [bar for bar in args["candles"] if bar["time"] != 3000.]
        output = build_looking_glass(**args)
        self.assertEqual(output["status"], "PARTIAL")
        self.assertEqual(output["reference_window"]["completed_prior_contracts"], 1)
        self.assertEqual(len(output["paths"]), 3)
        self.assertTrue(output["reference_window"]["gaps"])
        self.assertTrue(all(path["reference_end_ts"] == 2700. for path in output["paths"]))

    def test_insufficient_prior_contract_never_gets_synthetic_paths(self):
        args = fixture()
        args["candles"] = args["candles"][-10:]
        output = build_looking_glass(**args)
        self.assertEqual(output["status"], "UNAVAILABLE")
        self.assertEqual(output["paths"], [])
        self.assertEqual(output["thesis"]["side"], "UNKNOWN")

    def test_old_profiles_cannot_supply_missing_current_ema9_progress(self):
        args = fixture()
        args["candles"] = [row for row in args["candles"] if row["time"] + 60 <= 3600.]
        output = build_looking_glass(**args)
        self.assertEqual(output["reference_window"]["completed_prior_contracts"], 2)
        self.assertEqual(output["observations"]["ema9_direction"], "UNKNOWN")
        self.assertEqual(output["paths"], [])
        self.assertEqual(output["status"], "UNAVAILABLE")
        self.assertEqual(build_looking_glass(**fixture())["status"], "READY")

    def test_flat_current_ema9_has_only_explicit_rotation_context_and_no_directional_thesis(self):
        args = fixture()
        for row in args["candles"]:
            if row["time"] + 60 >= 3720.:
                row["e9"] = 80040.
        args["market"]["e9"] = 80040.
        output = build_looking_glass(**args)
        self.assertEqual(output["observations"]["ema9_direction"], "FLAT")
        self.assertEqual(output["status"], "PARTIAL")
        self.assertEqual({row["family"] for row in output["paths"]}, {"ROTATION_STALL"})
        self.assertEqual(output["thesis"]["side"], "UNKNOWN")
        self.assertEqual(output["thesis"]["continuation_side"], "UNKNOWN")

    def test_flat_prior_remainders_do_not_borrow_the_current_direction(self):
        args = fixture()
        for row in args["candles"]:
            end = row["time"] + 60
            row["e9"] = 80000. if end <= 3600 else 80000. + (end - 3600) / 12
            row["e30"] = 79990.
        args["market"]["e9"] = args["candles"][-1]["e9"]
        args["market"]["e30"] = 79990.
        output = build_looking_glass(**args)
        self.assertEqual(output["observations"]["ema9_direction"], "UP")
        self.assertEqual(output["reference_window"]["coverage"], "COMPLETE")
        self.assertEqual(output["reference_window"]["directional_reference_contracts"], 0)
        self.assertEqual(output["reference_window"]["directional_reference_coverage"], "UNAVAILABLE")
        self.assertEqual(output["status"], "PARTIAL")
        self.assertEqual(output["thesis"]["side"], "UNKNOWN")
        self.assertEqual(output["thesis"]["physical_lean"], "YES")
        self.assertEqual(output["thesis"]["continuation_side"], "UNKNOWN")
        self.assertEqual(len(output["paths"]), 2)
        for path in output["paths"]:
            self.assertEqual(path["family"], "ROTATION_STALL")
            self.assertEqual(path["reference_ema9_remainder_direction"], "FLAT")
            self.assertIn("prior remainder", path["label"])
            self.assertIsNone(path["orientation_to_current_ema9"])

    def test_one_flat_remainder_preserves_the_other_directional_reference(self):
        args = fixture()
        phase_e9 = next(row["e9"] for row in args["candles"] if row["time"] + 60 == 3000.)
        next(row for row in args["candles"] if row["time"] + 60 == 3600.)["e9"] = phase_e9
        output = build_looking_glass(**args)
        self.assertEqual(output["status"], "PARTIAL")
        self.assertEqual(output["reference_window"]["coverage"], "COMPLETE")
        self.assertEqual(output["reference_window"]["directional_reference_contracts"], 1)
        self.assertEqual(output["reference_window"]["directional_reference_coverage"], "PARTIAL")
        directional = [path for path in output["paths"] if path["family"] != "ROTATION_STALL"]
        self.assertEqual({path["family"] for path in directional}, {"CONTINUATION", "REVERSAL"})
        self.assertTrue(all(path["reference_end_ts"] == 2700. for path in directional))
        self.assertNotEqual(output["thesis"]["continuation_side"], "UNKNOWN")
        self.assertIn("Only 1 of 2", output["thesis"]["reason"])

    def test_conflicting_duplicate_price_or_ema_observations_create_a_gap(self):
        args = fixture()
        conflict = deepcopy(next(bar for bar in args["candles"] if bar["time"] == 3000.))
        conflict["close"] += 10
        args["candles"].append(conflict)
        self.assertEqual(build_looking_glass(**args)["status"], "PARTIAL")
        args = fixture()
        args["emas"] = [{"time": bar["time"], "e9": bar.pop("e9"), "e30": bar.pop("e30")}
                        for bar in args["candles"]]
        conflict = deepcopy(next(row for row in args["emas"] if row["time"] == 3000.))
        conflict["e9"] += 10
        args["emas"].append(conflict)
        output = build_looking_glass(**args)
        self.assertEqual(output["status"], "PARTIAL")
        self.assertEqual(output["reference_window"]["completed_prior_contracts"], 1)

    def test_inline_completed_ema_is_not_overwritten_by_current_sample_with_same_minute_label(self):
        args = fixture()
        original = build_looking_glass(**args)
        args["emas"] = [{"time": 3540., "e9": 1e8, "e30": 1e8}]
        self.assertEqual(build_looking_glass(**args)["paths"], original["paths"])

    def test_no_four_minute_deadline_and_only_remaining_profile_is_replayed(self):
        args = fixture(now=4200.)
        output = build_looking_glass(**args)
        self.assertEqual(output["status"], "READY")
        self.assertEqual(output["timing"]["contract_age_seconds"], 600.)
        self.assertIsNone(output["timing"]["hard_cutoff_seconds"])
        for path in output["paths"]:
            self.assertEqual(path["current_contract_phase_seconds"], 600.)
            self.assertEqual(path["points"][-1]["time"] - path["points"][0]["time"], 300.)

    def test_fractional_current_phase_is_labeled_historical_close_interpolation(self):
        args = fixture(now=3930.)
        output = build_looking_glass(**args)
        self.assertEqual(output["status"], "READY")
        for path in output["paths"]:
            self.assertTrue(path["historical_close_interpolation"])
            self.assertEqual(path["points"][0]["time"], 3930.)
            self.assertEqual(path["points"][-1]["time"], 4500.)

    def test_fractional_real_epoch_paths_have_an_exact_terminal_expiry(self):
        epoch = 1800000000.
        for fraction in (.1, .123456, .987654, .999999):
            with self.subTest(fraction=fraction):
                args = fixture(now=3930. + fraction)
                for row in args["candles"]:
                    row["time"] += epoch
                    row["known_at"] += epoch
                for key in ("time", "close_ts"):
                    args["market"][key] += epoch
                args["quote"]["time"] += epoch
                args["now_ts"] += epoch
                output = build_looking_glass(**args)
                self.assertEqual(output["status"], "READY")
                for path in output["paths"]:
                    times = [row["time"] for row in path["points"]]
                    self.assertEqual(times[0], args["market"]["time"])
                    self.assertEqual(times[-1], args["market"]["close_ts"])
                    self.assertTrue(all(a < b for a, b in zip(times, times[1:])))
                    self.assertTrue(all(times[0] <= time <= times[-1] for time in times))

    def test_stale_market_and_expired_contract_hide_hypothetical_paths(self):
        args = fixture()
        args["now_ts"] += 4
        output = build_looking_glass(**args)
        self.assertEqual(output["status"], "STALE")
        self.assertIsNone(output["valid_until"])
        self.assertEqual(output["paths"], [])
        args = fixture()
        args["market"]["close_ts"] = args["now_ts"]
        self.assertEqual(build_looking_glass(**args)["paths"], [])

    def test_missing_target_keeps_unknown_without_inventing_next_contract_target(self):
        args = fixture()
        args["market"]["target"] = None
        output = build_looking_glass(**args)
        self.assertEqual(output["thesis"]["side"], "UNKNOWN")
        self.assertTrue(all(path["endpoint_side"] == "UNKNOWN" for path in output["paths"]))
        self.assertNotIn("next_target", output)

    def test_forty_percent_means_gross_return_on_ask_without_an_automatic_exit(self):
        output = build_looking_glass(**fixture())
        review = output["swing_review"]
        self.assertEqual(review["minimum_gross_roi"], .4)
        self.assertFalse(review["automatic_take_profit"])
        yes = review["sides"]["YES"]
        self.assertEqual(yes["entry_ask"], .30)
        self.assertEqual(yes["required_exit_bid"], .42)
        self.assertEqual(yes["status"], "NOT_ASSESSED")
        self.assertFalse(yes["fees_included"])
        self.assertFalse(yes["exit_depth_proven"])
        changed = build_looking_glass(**fixture(), config={"minimum_gross_roi": .5})
        self.assertEqual(changed["swing_review"]["sides"]["YES"]["required_exit_bid"], .45)

    def test_historical_excursion_uses_earlier_ask_and_later_bid_with_exact_ticker(self):
        args = fixture()
        args["quote_history"] = [
            {"time": 3650., "ticker": "CURRENT", "quote_id": "A", "yes_ask": .30, "yes_bid": .29},
            {"time": 3700., "ticker": "CURRENT", "quote_id": "B", "yes_ask": .43, "yes_bid": .42},
            {"time": 3600., "ticker": "OLD", "quote_id": "C", "yes_ask": .01, "yes_bid": .009},
            {"time": 4000., "ticker": "CURRENT", "quote_id": "FUTURE", "yes_ask": .99, "yes_bid": .98},
        ]
        side = build_looking_glass(**args)["swing_review"]["sides"]["YES"]
        past = side["historical_excursion"]
        self.assertAlmostEqual(past["gross_roi"], .40)
        self.assertEqual((past["entry_quote_id"], past["exit_quote_id"]), ("A", "B"))
        self.assertEqual(side["historical_filter_result"], "AT_OR_ABOVE_FILTER")
        self.assertEqual(side["status"], "NOT_ASSESSED", "An observed old excursion is not a future opportunity")
        self.assertTrue(past["does_not_qualify_new_entry"])
        self.assertFalse(past["full_lot_depth_proven"])
        args["market"]["ticker"] = "ROLLED"
        rolled = build_looking_glass(**args)["swing_review"]["sides"]["YES"]
        self.assertIsNone(rolled["historical_excursion"])
        self.assertIsNone(rolled["entry_ask"])

    def test_historical_bid_cannot_be_paired_with_a_later_cheaper_ask(self):
        args = fixture()
        args["quote_history"] = [
            {"time": 3650., "ticker": "CURRENT", "quote_id": "BID_FIRST", "yes_ask": .43, "yes_bid": .42},
            {"time": 3700., "ticker": "CURRENT", "quote_id": "ASK_LATER", "yes_ask": .30, "yes_bid": .29},
        ]
        side = build_looking_glass(**args)["swing_review"]["sides"]["YES"]
        self.assertLess(side["historical_excursion"]["gross_roi"], 0)
        self.assertEqual(side["historical_filter_result"], "BELOW_FILTER")

    def test_quote_without_freshness_or_hurdle_above_par_cannot_be_assessed(self):
        args = fixture()
        args["quote"]["yes_ask"] = .80
        side = build_looking_glass(**args)["swing_review"]["sides"]["YES"]
        self.assertEqual(side["required_exit_bid"], 1.12)
        self.assertEqual(side["status"], "TARGET_ABOVE_ONE")
        args["quote"]["fresh"] = False
        side = build_looking_glass(**args)["swing_review"]["sides"]["YES"]
        self.assertEqual(side["status"], "UNAVAILABLE")

    def test_invalid_known_time_or_crossed_quote_is_not_usable_evidence(self):
        args = fixture()
        next(bar for bar in args["candles"] if bar["time"] == 3000.)["known_at"] = float("nan")
        output = build_looking_glass(**args)
        self.assertEqual(output["status"], "PARTIAL")
        args["quote"]["yes_bid"] = .31
        side = build_looking_glass(**args)["swing_review"]["sides"]["YES"]
        self.assertEqual(side["status"], "UNAVAILABLE")
        self.assertIsNone(side["entry_ask"])

    def test_configuration_and_output_are_finite_and_read_only(self):
        for bad in (True, float("nan"), float("inf"), -0.1):
            with self.assertRaises(ValueError):
                LookingGlassConfig(minimum_gross_roi=bad)
        for bad in (True, 0, 3, 1.5):
            with self.assertRaises(ValueError):
                LookingGlassConfig(history_contracts=bad)
        with self.assertRaises(ValueError):
            build_looking_glass(**fixture(), config={"unknown": True})
        args = fixture()
        original = deepcopy(args)
        output = build_looking_glass(**args)
        self.assertEqual(args, original)
        self.assertEqual(output, build_looking_glass(**args))
        json.dumps(output, allow_nan=False)
        output["paths"][0]["points"][0]["btc"] = 0
        self.assertEqual(args, original)


if __name__ == "__main__":
    unittest.main()
