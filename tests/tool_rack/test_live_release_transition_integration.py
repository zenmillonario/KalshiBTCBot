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


def write_geometry(run: Path, rows):
    with (run / "tachys_ema_geometry_v9_4i.csv").open(
        "w", newline="", encoding="utf-8"
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


def write_runtime(run: Path, *, now, yes, no):
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
                "close_ts": now + 900.0,
            },
        }),
        encoding="utf-8",
    )


def rail_rows(*, side: str, start_s: int, count: int, step_s: int = 15):
    sign = 1 if side == "YES" else -1
    direction = "UP" if side == "YES" else "DOWN"
    rows = []
    for i in range(count):
        t = start_s + i * step_s
        ema30 = 80000 + sign * (t - start_s) * 0.20
        ema9 = ema30 + sign * 10
        btc = ema9 + sign * 5
        rows.append({
            "epoch_ms": t * 1000,
            "btc_price": btc,
            "ema9": ema9,
            "ema30": ema30,
            "struct_slope3m": sign * 1.2,
            "struct_slope6m": sign * 1.1,
            "struct_slope9m": sign * 1.0,
            "ema30_slope3m": sign * 0.5,
            "micro_slope9s": sign * 1.0,
            "btc_change9": sign * 8.0,
            "arc_id": f"{direction}_RAIL",
            "arc_direction": direction,
            "arc_phase": "BUILDING",
            "arc_age_sec": i * step_s,
            "arc_amplitude": 20 + i,
            "parent_direction": direction,
        })
    return rows


class LiveReleaseTransitionIntegrationTests(unittest.TestCase):
    def test_down_rail_physical_up_release_to_release_transition_to_up_rail(self):
        temp = tempfile.TemporaryDirectory()
        try:
            run = Path(temp.name) / "PAPER_TEST"
            run.mkdir()
            source = R22RunShadowSource(run)
            engine = ToolRackShadowEngine()

            # 15 minutes of clean DOWN Rail.
            rows = rail_rows(side="NO", start_s=0, count=61)
            write_geometry(run, rows)
            write_runtime(run, now=900.0, yes=0.70, no=0.30)

            first = engine.evaluate(source.read().frame)
            self.assertEqual(first["owned_territory"], "DOWN_RAIL")
            self.assertEqual(first["commander_action"], "ENTER")
            self.assertEqual(first["accepted_side"], "NO")

            # Physical UP escape: price crosses above EMA9, the current arc
            # changes UP, short structure expands UP, and new-side residence
            # becomes dominant. The YES quote is intentionally expensive.
            release_rows = []
            for j in range(1, 8):
                t = 900 + j * 15
                ema30 = 79820 + j * 0.3
                ema9 = 79825 + j * 1.0
                btc = ema9 + 15
                release_rows.append({
                    "epoch_ms": t * 1000,
                    "btc_price": btc,
                    "ema9": ema9,
                    "ema30": ema30,
                    "struct_slope3m": 1.4,
                    "struct_slope6m": 0.4,
                    "struct_slope9m": 0.2,
                    "ema30_slope3m": -0.1,
                    "micro_slope9s": 1.0,
                    "btc_change9": 12.0,
                    "arc_id": "UP_RELEASE",
                    "arc_direction": "UP",
                    "arc_phase": "BUILDING",
                    "arc_age_sec": j * 15,
                    "arc_amplitude": 20 + j,
                    "parent_direction": "DOWN",
                })
            rows.extend(release_rows)
            write_geometry(run, rows)
            write_runtime(run, now=1005.0, yes=0.70, no=0.30)

            release = engine.evaluate(source.read().frame)
            self.assertEqual(release["owned_territory"], "DOWN_RAIL")
            self.assertTrue(release["handoff_confirmed"])
            self.assertTrue(release["release_transition_pending"])
            self.assertEqual(release["accepted_tool"], None)
            self.assertEqual(release["commander_action"], "WAIT")
            self.assertIn(
                "SUPPRESSES_OLD_TERRITORY",
                release["lane_resolution_reason"],
            )

            # Next beat: old Rail is gone even without a release fill.
            write_runtime(run, now=1020.0, yes=0.65, no=0.30)
            transition = engine.evaluate(source.read().frame)
            self.assertEqual(
                transition["owned_territory"],
                "RELEASE_TRANSITION",
            )
            self.assertIsNone(transition["active_tool"])

            # Build a full new UP Rail chapter. RELEASE_TRANSITION should hand
            # directly to the UP Rail tool when it becomes physically clear.
            start = 1020
            up_rows = rail_rows(
                side="YES",
                start_s=start,
                count=61,
            )
            rows.extend(up_rows)
            write_geometry(run, rows)
            write_runtime(
                run,
                now=float(start + 60 * 15),
                yes=0.30,
                no=0.70,
            )

            acquired = engine.evaluate(source.read().frame)
            self.assertEqual(acquired["owned_territory"], "UP_RAIL")
            self.assertEqual(acquired["active_tool"], "RAIL")
            self.assertEqual(acquired["commander_action"], "ENTER")
            self.assertEqual(acquired["accepted_side"], "YES")
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
