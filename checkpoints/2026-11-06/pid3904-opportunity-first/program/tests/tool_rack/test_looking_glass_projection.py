"""An advisory chart failure cannot hide or rewrite the committed PAPER record."""
from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from strategy_core.nautilus_projection import NautilusProjection
from strategy_core.marketdata.btc_observation import MinuteEMAs, validate_candles
from strategy_core.marketdata.btc_transport import seed_chart_candles
from strategy_core.paper_feed import _ChartHistory
from strategy_core.paper_execution import PaperExecutioner
from tests.tool_rack.test_nautilus_projection import command, native, status


class LookingGlassProjectionTests(unittest.TestCase):
    def test_normal_completed_seed_supplies_both_prior_contract_profiles(self):
        now = 1800000302.0
        minute = int(now // 60) * 60
        close = (int(now // 900) + 1) * 900
        rows = []
        for offset in range(1, 240):
            ts = minute - offset * 60
            price = 80000 + .02 * (ts - minute) + 15 * math.sin(offset * math.pi / 8)
            rows.append([ts, price - 2, price + 2, price - 1, price, 1])
        seed, metadata = validate_candles(rows, now)
        chart_seed = seed_chart_candles(seed, rows, epoch=1, received=now - 1)
        history = _ChartHistory()
        history.seed(chart_seed, 1)
        stream = MinuteEMAs(seed, metadata, 1)
        stream.update(now, 80004.)
        geometry = stream.sample(now, now, 0., 1, "1")
        geometry["epoch_ms"] = now * 1000
        source = status(ts=now, book=native(now, close=close))
        source["latest_geometry"] = geometry
        source["market"].update(target=80000., target_source="KALSHI_MARKET_FLOOR_STRIKE")
        view = NautilusProjection().project(source, [geometry],
                                            chart_data=history.snapshot(), now_ts=now)
        glass = view["looking_glass"]
        self.assertEqual(metadata["completed_bars"], 239)
        self.assertEqual(glass["status"], "READY")
        self.assertEqual(glass["reference_window"]["end_ts"], close - 900)
        self.assertEqual([(row["status"], row["point_count"])
                          for row in glass["reference_window"]["contracts"]],
                         [("COMPLETE", 16), ("COMPLETE", 16)])
        self.assertEqual(len(glass["paths"]), 6)
        for path in glass["paths"]:
            self.assertEqual(path["points"][-1]["time"], close)
            self.assertLessEqual(path["reference_known_by_ts"], now)
        self.assertEqual(view["interpretation"]["pilot"]["action"], "WAIT")
        self.assertEqual(view["positions"], [])

    def test_model_failure_keeps_actual_inventory_accounting_and_decisions(self):
        with tempfile.TemporaryDirectory() as directory, PaperExecutioner(Path(directory) / "run") as executor:
            executor.execute(command(), native(), now_ts=1000., command_id="ENTRY")
            source = status(executor, ts=1001., book=native(1001., bid=.20))
            source["market"].update(target=80000., target_source="KALSHI_MARKET_FLOOR_STRIKE")
            original = deepcopy(source)
            baseline = NautilusProjection().project(source, now_ts=1001.)
            with patch("strategy_core.nautilus_projection.build_looking_glass", side_effect=RuntimeError("observer failure")):
                failed = NautilusProjection().project(source, now_ts=1001.)
            self.assertEqual(failed["looking_glass"]["status"], "UNAVAILABLE")
            self.assertFalse(failed["looking_glass"]["execution_authority"])
            self.assertEqual(failed["looking_glass"]["paths"], [])
            for field in ("positions", "trades", "accounting", "feed", "commands", "tool_rack", "quote"):
                self.assertEqual(failed[field], baseline[field], field)
            self.assertEqual(source, original)
            self.assertEqual(len(executor.positions), 1)
            json.dumps(failed, allow_nan=False)

    def test_observer_result_is_detached_and_configuration_is_passed_explicitly(self):
        source = status(ts=1000.)
        source["market"].update(target=80000., target_source="KALSHI_MARKET_FLOOR_STRIKE")
        model_result = {"execution_authority": False, "can_veto": False, "can_order": False,
                        "probabilities_calibrated": False, "status": "PARTIAL",
                        "paths": [{"points": [{"time": 1000., "btc": 80000.}]}]}
        projection = NautilusProjection()
        projection._looking_glass_config = {"minimum_gross_roi": .60, "history_contracts": 1}
        with patch("strategy_core.nautilus_projection.build_looking_glass", return_value=model_result) as model:
            view = projection.project(source, now_ts=1000.)
        self.assertEqual(model.call_args.kwargs["config"], {"minimum_gross_roi": .60, "history_contracts": 1})
        self.assertEqual(model.call_args.args[0]["ticker"], source["market"]["ticker"])
        model_result["paths"][0]["points"][0]["btc"] = 0
        self.assertEqual(view["looking_glass"]["paths"][0]["points"][0]["btc"], 80000.)
        self.assertEqual(view["interpretation"]["pilot"]["action"], "WAIT")

    def test_invalid_configuration_only_disables_looking_glass(self):
        with patch("strategy_core.nautilus_projection.Path.read_text", return_value="{"):
            projection = NautilusProjection()
        view = projection.project(status(), now_ts=1000.)
        self.assertEqual(view["looking_glass"]["reason"], "LOOKING_GLASS_CONFIGURATION_UNAVAILABLE")
        self.assertEqual(view["accounting"]["cash"], 1000.)
        self.assertTrue(view["run"]["fresh"])
        self.assertTrue(view["feed"])

    def test_nonfinite_or_authoritative_observer_result_does_not_break_publication(self):
        observer = {"execution_authority": False, "can_veto": False, "can_order": False,
                    "probabilities_calibrated": False, "paths": []}
        for result in ({**observer, "paths": [float("nan")]},
                       {**observer, "execution_authority": True},
                       {**observer, "can_veto": True}, {**observer, "can_order": True},
                       {**observer, "probabilities_calibrated": True}, ["invalid"]):
            with self.subTest(result=result):
                with patch("strategy_core.nautilus_projection.build_looking_glass", return_value=result):
                    view = NautilusProjection().project(status(), now_ts=1000.)
                self.assertEqual(view["looking_glass"]["status"], "UNAVAILABLE")
                self.assertFalse(view["looking_glass"]["execution_authority"])
                self.assertEqual(view["interpretation"]["pilot"]["action"], "WAIT")
                json.dumps(view, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
