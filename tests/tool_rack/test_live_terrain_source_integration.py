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


def write_runtime(run: Path, *, now: float, close: float, yes: float, no: float):
    (run / "tachys_runtime_hf2.json").write_text(
        json.dumps({
            "updated_wall": now,
            "run_id": "RUN",
            "session_id": "SESSION",
            "quote": {
                "ticker": "KXTEST",
                "yes_ask": yes,
                "no_ask": no,
                "valid": True,
                "exchange_age_sec": 1.0,
                "yes_bid_size": 100.0,
                "no_bid_size": 100.0,
                "close_ts": close,
            },
        }),
        encoding="utf-8",
    )


def write_geometry(run: Path, rows):
    with (run / "tachys_ema_geometry_v9_4i.csv").open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for raw in rows:
            row = {key: "" for key in FIELDS}
            row.update(raw)
            row.setdefault("ticker", "KXTEST")
            row.setdefault("range60", 100.0)
            row.setdefault("range180", 180.0)
            row.setdefault("arc_prominence_threshold", 5.0)
            writer.writerow(row)


class LiveTerrainSourceIntegrationTests(unittest.TestCase):
    def run_dir(self):
        temp = tempfile.TemporaryDirectory()
        run = Path(temp.name) / "PAPER_TEST"
        run.mkdir()
        return temp, run

    def test_mature_alternating_mountain_top_reaches_no_relay(self):
        temp, run = self.run_dir()
        try:
            rows = []
            t = 0
            specs = [
                ("A1","UP",180,1000),
                ("A2","DOWN",190,1040),
                ("A3","UP",170,1005),
                ("A4","DOWN",180,1045),
                ("A5","UP",200,1010),
                ("A6","DOWN",170,1050),
            ]
            for arc_id, direction, duration, base in specs:
                sign = 1 if direction == "UP" else -1
                rows.extend([
                    {
                        "epoch_ms": t,
                        "btc_price": base,
                        "ema9": base - sign*3,
                        "ema30": 1025,
                        "struct_slope3m": sign*0.5,
                        "struct_slope6m": sign*0.7,
                        "struct_slope9m": sign*0.8,
                        "ema30_slope3m": 0.0,
                        "arc_id": arc_id,
                        "arc_direction": direction,
                        "arc_phase": "BUILDING",
                        "arc_age_sec": 0,
                        "arc_amplitude": 0,
                        "parent_direction": direction,
                    },
                    {
                        "epoch_ms": t + duration*1000,
                        "btc_price": base + sign*40,
                        "ema9": base + sign*35,
                        "ema30": 1025,
                        "struct_slope3m": sign*0.4,
                        "struct_slope6m": sign*0.7,
                        "struct_slope9m": sign*0.8,
                        "ema30_slope3m": 0.0,
                        "arc_id": arc_id,
                        "arc_direction": direction,
                        "arc_phase": "ROLLING",
                        "arc_age_sec": duration,
                        "arc_amplitude": 35,
                        "parent_direction": direction,
                    },
                ])
                t += (duration+5)*1000

            rows.extend([
                {
                    "epoch_ms": t,
                    "btc_price": 1015,
                    "ema9": 1012,
                    "ema30": 1025,
                    "struct_slope3m": 0.5,
                    "struct_slope6m": 0.8,
                    "struct_slope9m": 0.9,
                    "ema30_slope3m": 0.0,
                    "arc_id": "A7",
                    "arc_direction": "UP",
                    "arc_phase": "BUILDING",
                    "arc_age_sec": 0,
                    "arc_amplitude": 0,
                    "parent_direction": "UP",
                },
                {
                    "epoch_ms": t+115_000,
                    "btc_price": 1050,
                    "ema9": 1045,
                    "ema30": 1025,
                    "struct_slope3m": 0.3,
                    "struct_slope6m": 0.7,
                    "struct_slope9m": 0.8,
                    "ema30_slope3m": 0.0,
                    "arc_id": "A7",
                    "arc_direction": "UP",
                    "arc_phase": "CREST_FORMING",
                    "arc_age_sec": 115,
                    "arc_amplitude": 33,
                    "parent_direction": "UP",
                },
                {
                    "epoch_ms": t+130_000,
                    "btc_price": 1047,
                    "ema9": 1044,
                    "ema30": 1025,
                    "struct_slope3m": 0.25,
                    "struct_slope6m": 0.7,
                    "struct_slope9m": 0.8,
                    "ema30_slope3m": 0.0,
                    "arc_id": "A7",
                    "arc_direction": "UP",
                    "arc_phase": "CREST_FORMING",
                    "arc_age_sec": 130,
                    "arc_amplitude": 33,
                    "parent_direction": "UP",
                },
            ])

            now = (t+130_000)/1000.0
            write_runtime(run, now=now, close=now+500, yes=0.70, no=0.30)
            write_geometry(run, rows)

            state = R22RunShadowSource(run).read()
            out = ToolRackShadowEngine().evaluate(state.frame)

            self.assertEqual(out["owned_territory"], "ALTERNATING_MOUNTAIN")
            self.assertEqual(out["active_tool"], "ALTERNATING_MOUNTAIN")
            self.assertEqual(out["commander_action"], "RELAY")
            self.assertEqual(out["accepted_side"], "NO")
        finally:
            temp.cleanup()

    def test_repeatable_flat_box_upper_edge_reaches_heist_no(self):
        temp, run = self.run_dir()
        try:
            prices = [
                1000,1050,1100,1050,1000,1050,1100,
                1050,1000,1050,1100,1050,1099,
            ]
            rows=[]
            for i,price in enumerate(prices):
                rows.append({
                    "epoch_ms": i*15_000,
                    "btc_price": price,
                    "ema9": 1050,
                    "ema30": 1050,
                    "struct_slope3m": 0.0,
                    "struct_slope6m": 0.0,
                    "struct_slope9m": 0.0,
                    "ema30_slope3m": 0.0,
                    "arc_id": f"H{i//3}",
                    "arc_direction": "UP" if (i//3)%2==0 else "DOWN",
                    "arc_phase": "MATURE",
                    "arc_age_sec": (i%3)*15,
                    "arc_amplitude": 20,
                    "parent_direction": "NONE",
                })
            now=rows[-1]["epoch_ms"]/1000.0
            write_runtime(run, now=now, close=now+600, yes=0.70, no=0.30)
            write_geometry(run, rows)

            state=R22RunShadowSource(run).read()
            out=ToolRackShadowEngine().evaluate(state.frame)

            self.assertEqual(out["owned_territory"], "MARKET_HEIST")
            self.assertEqual(out["active_tool"], "MARKET_HEIST")
            self.assertEqual(out["commander_action"], "ENTER")
            self.assertEqual(out["accepted_side"], "NO")
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
