import unittest

from strategy_core.detectors.heist_geometry import (
    detect_heist_geometry,
)
from strategy_core.types import Side


def make_rows(
    prices,
    *,
    ema9_start=1050.0,
    ema9_end=1050.0,
    ema30_start=1050.0,
    ema30_end=1050.0,
    step_s=15,
):
    rows = []
    n = max(1, len(prices) - 1)
    for i, price in enumerate(prices):
        f = i / n
        rows.append({
            "epoch_ms": i * step_s * 1000,
            "btc_price": price,
            "ema9": ema9_start + f * (ema9_end - ema9_start),
            "ema30": ema30_start + f * (ema30_end - ema30_start),
            "arc_prominence_threshold": 5.0,
        })
    return rows


class HeistGeometryDetectorTests(unittest.TestCase):
    def test_repeated_sideways_box_qualifies_upper_edge(self):
        prices = [
            1000, 1050, 1100, 1050, 1002, 1050, 1098,
            1050, 1001, 1050, 1100, 1050, 1099,
        ]
        out = detect_heist_geometry(make_rows(prices))
        self.assertTrue(out.qualified_box)
        self.assertGreaterEqual(out.lower_visits, 2)
        self.assertGreaterEqual(out.upper_visits, 2)
        self.assertTrue(out.at_upper_edge)
        self.assertFalse(out.at_lower_edge)
        self.assertIsNotNone(out.visit_id)

    def test_repeated_sideways_box_qualifies_lower_edge(self):
        prices = [
            1100, 1050, 1000, 1050, 1098, 1050, 1002,
            1050, 1099, 1050, 1000, 1050, 1001,
        ]
        out = detect_heist_geometry(make_rows(prices))
        self.assertTrue(out.qualified_box)
        self.assertTrue(out.at_lower_edge)

    def test_unresolved_compression_waits_until_repetition_exists(self):
        prices = [
            1000, 1020, 1050, 1080, 1100, 1080, 1050,
            1030, 1010, 1040, 1060,
        ]
        out = detect_heist_geometry(make_rows(prices, step_s=18))
        self.assertFalse(out.qualified_box)
        self.assertTrue(out.compression_unresolved)

    def test_middle_of_qualified_box_is_not_an_edge(self):
        prices = [
            1000, 1050, 1100, 1050, 1000, 1050, 1100,
            1050, 1000, 1050, 1100, 1050, 1050,
        ]
        out = detect_heist_geometry(make_rows(prices))
        self.assertTrue(out.qualified_box)
        self.assertFalse(out.at_lower_edge)
        self.assertFalse(out.at_upper_edge)
        self.assertIsNone(out.visit_id)

    def test_gentle_ema_lean_favors_lean_side_without_destroying_box(self):
        prices = [
            1000, 1050, 1100, 1050, 1000, 1050, 1100,
            1050, 1000, 1050, 1100, 1050, 1099,
        ]
        out = detect_heist_geometry(
            make_rows(
                prices,
                ema9_start=1040,
                ema9_end=1058,
                ema30_start=1045,
                ema30_end=1057,
            )
        )
        self.assertTrue(out.qualified_box)
        self.assertEqual(out.lean_side, Side.YES)

    def test_strong_directional_ema_drift_is_not_heist(self):
        prices = [
            1000, 1050, 1100, 1050, 1000, 1050, 1100,
            1050, 1000, 1050, 1100, 1050, 1099,
        ]
        out = detect_heist_geometry(
            make_rows(
                prices,
                ema9_start=1000,
                ema9_end=1080,
                ema30_start=1005,
                ema30_end=1060,
            )
        )
        self.assertFalse(out.qualified_box)

    def test_same_edge_visit_id_is_stable_until_zone_is_left(self):
        base = [
            1000, 1050, 1100, 1050, 1000, 1050, 1100,
            1050, 1000, 1050, 1100,
        ]
        first = detect_heist_geometry(make_rows(base + [1098, 1099], step_s=14))
        second = detect_heist_geometry(make_rows(base + [1098, 1099, 1097], step_s=13))
        self.assertTrue(first.qualified_box)
        self.assertTrue(second.qualified_box)
        self.assertEqual(
            first.visit_id.split(":")[0],
            "UPPER",
        )
        self.assertEqual(
            second.visit_id.split(":")[0],
            "UPPER",
        )


if __name__ == "__main__":
    unittest.main()
