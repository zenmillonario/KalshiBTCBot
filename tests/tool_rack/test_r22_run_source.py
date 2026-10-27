import csv
import json
import tempfile
import unittest
from pathlib import Path

from strategy_core.r22_run_source import R22RunShadowSource
from strategy_core.shadow_engine import ToolRackShadowEngine


FIELDS = [
    "timestamp","epoch_ms","ticker","source","seconds_left","btc_price",
    "target_price","target_distance","yes_ask","no_ask","ema9","ema30",
    "ema_gap","range60","range180","micro_slope3s","micro_slope6s",
    "micro_slope9s","micro_curve3v6","micro_curve6v9","struct_slope3m",
    "struct_slope6m","struct_slope9m","struct_curve3v6","struct_curve6v9",
    "ema30_slope3m","arc_id","arc_direction","arc_phase","arc_age_sec",
    "arc_amplitude","arc_prominence_threshold","arc_health","sequence_id",
    "sequence_count","previous_same_arc_id","previous_same_amplitude",
    "amplitude_ratio","crest_progression","ema30_relation","target_relation",
    "parent_direction","parent_maturity","local_regime","geometry_state",
    "geometry_bias","geometry_bias_score","btc_change3","btc_change6",
    "btc_change9",
]


class R22RunShadowSourceTests(unittest.TestCase):
    def make_run(self, *, side="NO", ask=0.30):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        run = root / "PAPER_TEST"
        run.mkdir()

        now = 2000.0
        close = 2700.0
        quote = {
            "ticker": "KXTEST",
            "yes_ask": 0.70 if side == "NO" else ask,
            "no_ask": ask if side == "NO" else 0.70,
            "valid": True,
            "exchange_age_sec": 1.0,
            "yes_bid_size": 100.0,
            "no_bid_size": 100.0,
            "close_ts": close,
        }
        (run / "tachys_runtime_hf2.json").write_text(
            json.dumps({
                "updated_wall": now,
                "run_id": "RUN",
                "session_id": "SESSION",
                "quote": quote,
            }),
            encoding="utf-8",
        )

        sign = -1 if side == "NO" else 1
        with (run / "tachys_ema_geometry_v9_4i.csv").open(
            "w",
            newline="",
            encoding="utf-8",
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for i in range(61):
                t = 1000 + i * 15
                ema30 = 80000 + sign * i * 0.25
                ema9 = ema30 + sign * 10
                btc = ema9 + sign * 5
                writer.writerow({
                    "timestamp": str(t),
                    "epoch_ms": str(t * 1000),
                    "ticker": "KXTEST",
                    "seconds_left": str(max(0, close - t)),
                    "btc_price": str(btc),
                    "ema9": str(ema9),
                    "ema30": str(ema30),
                    "struct_slope3m": str(sign * 1.2),
                    "struct_slope6m": str(sign * 1.1),
                    "struct_slope9m": str(sign * 1.0),
                    "ema30_slope3m": str(sign * 0.4),
                    "arc_id": f"A{i//10:02d}",
                    "arc_direction": "DOWN" if side == "NO" else "UP",
                    "parent_direction": "DOWN" if side == "NO" else "UP",
                })
        return temp, run

    def test_down_rail_run_files_produce_30c_entry_without_legacy_routes(self):
        temp, run = self.make_run(side="NO", ask=0.30)
        try:
            state = R22RunShadowSource(run).read()
            out = ToolRackShadowEngine().evaluate(state.frame)
            self.assertEqual(out["owned_territory"], "DOWN_RAIL")
            self.assertEqual(out["commander_action"], "ENTER")
            self.assertEqual(out["accepted_side"], "NO")
        finally:
            temp.cleanup()

    def test_source_is_read_only_and_requires_only_runtime_and_geometry(self):
        temp, run = self.make_run(side="YES", ask=0.30)
        try:
            before = sorted(path.name for path in run.iterdir())
            state = R22RunShadowSource(run).read()
            after = sorted(path.name for path in run.iterdir())
            self.assertEqual(before, after)
            out = ToolRackShadowEngine().evaluate(state.frame)
            self.assertEqual(out["owned_territory"], "UP_RAIL")
            self.assertEqual(out["accepted_side"], "YES")
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
