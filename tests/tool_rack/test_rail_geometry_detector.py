import unittest

from strategy_core.detectors.rail_geometry import (
    detect_rail_geometry,
)
from strategy_core.types import Side


def rail_rows(
    *,
    side,
    start_s,
    count,
    step_s=15,
):
    sign = 1 if side == Side.YES else -1
    rows = []
    for i in range(count):
        t = start_s + i * step_s
        e30 = 80000 + sign * i * 0.25
        e9 = e30 + sign * 10
        btc = e9 + sign * 5
        rows.append({
            "epoch_ms": t * 1000,
            "btc_price": btc,
            "ema9": e9,
            "ema30": e30,
            "struct_slope3m": sign * 1.2,
            "struct_slope6m": sign * 1.1,
            "struct_slope9m": sign * 1.0,
            "ema30_slope3m": sign * 0.4,
        })
    return rows


class RailGeometryDetectorTests(unittest.TestCase):
    def test_full_new_up_contract_qualifies_despite_older_down_history(self):
        rows = rail_rows(
            side=Side.NO,
            start_s=0,
            count=61,
        )
        rows += rail_rows(
            side=Side.YES,
            start_s=1020,
            count=61,
        )
        out = detect_rail_geometry(rows)
        self.assertEqual(out.side, Side.YES)
        self.assertTrue(out.directional_residence)
        self.assertTrue(out.ema_pair_parallel)
        self.assertGreaterEqual(
            out.persistence_seconds,
            900.0,
        )
        self.assertTrue(out.qualified_rail)

    def test_short_opposite_escape_does_not_instantly_become_new_rail(self):
        rows = rail_rows(
            side=Side.NO,
            start_s=0,
            count=61,
        )
        rows += rail_rows(
            side=Side.YES,
            start_s=915,
            count=8,
        )
        out = detect_rail_geometry(rows)
        self.assertEqual(out.side, Side.YES)
        self.assertFalse(out.qualified_rail)

    def test_shallow_fakeout_fraction_does_not_destroy_established_down_rail(self):
        rows = rail_rows(
            side=Side.NO,
            start_s=0,
            count=61,
        )
        # Inject a small local price fakeout while preserving EMA slopes.
        for i in range(5):
            idx = -1 - i
            rows[idx] = {
                **rows[idx],
                "btc_price": rows[idx]["ema9"] + 2,
            }
        out = detect_rail_geometry(rows)
        self.assertEqual(out.side, Side.NO)
        self.assertTrue(out.qualified_rail)
        self.assertGreater(
            out.current_residence_fraction,
            0.62,
        )

    def test_mixed_ema_slopes_do_not_form_rail(self):
        rows = rail_rows(
            side=Side.NO,
            start_s=0,
            count=61,
        )
        rows[-1] = {
            **rows[-1],
            "struct_slope3m": 1.0,
        }
        out = detect_rail_geometry(rows)
        self.assertIsNone(out.side)
        self.assertFalse(out.qualified_rail)


if __name__ == "__main__":
    unittest.main()
