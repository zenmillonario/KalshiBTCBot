import unittest

from strategy_core.detectors.mountain_geometry import (
    detect_mountain_geometry,
)
from strategy_core.types import Side


def row(
    *,
    arc_id,
    direction,
    epoch_ms,
    age,
    btc,
    phase,
    amplitude=20.0,
    prominence=5.0,
    range60=100.0,
    s3=1.0,
    s6=1.2,
):
    sign = 1 if direction == "UP" else -1
    return {
        "arc_id": arc_id,
        "arc_direction": direction,
        "epoch_ms": epoch_ms,
        "arc_age_sec": age,
        "btc_price": btc,
        "ema9": btc - sign * 3,
        "ema30": btc - sign * 10,
        "arc_phase": phase,
        "arc_amplitude": amplitude,
        "arc_prominence_threshold": prominence,
        "range60": range60,
        "struct_slope3m": sign * s3,
        "struct_slope6m": sign * s6,
    }


def completed_arc(arc_id, direction, start_ms, duration_s, base):
    sign = 1 if direction == "UP" else -1
    return [
        row(
            arc_id=arc_id,
            direction=direction,
            epoch_ms=start_ms,
            age=0,
            btc=base,
            phase="BUILDING",
        ),
        row(
            arc_id=arc_id,
            direction=direction,
            epoch_ms=start_ms + duration_s * 1000,
            age=duration_s,
            btc=base + sign * 40,
            phase="ROLLING",
        ),
    ]


def alternating_history(current_rows):
    rows = []
    t = 0
    specs = [
        ("A1", "UP", 180, 1000),
        ("A2", "DOWN", 190, 1040),
        ("A3", "UP", 170, 1005),
        ("A4", "DOWN", 180, 1045),
        ("A5", "UP", 200, 1010),
        ("A6", "DOWN", 170, 1050),
    ]
    for arc_id, direction, duration, base in specs:
        rows.extend(
            completed_arc(
                arc_id,
                direction,
                t,
                duration,
                base,
            )
        )
        t += (duration + 5) * 1000
    offset = t
    for item in current_rows:
        item = dict(item)
        item["epoch_ms"] += offset
        rows.append(item)
    return rows


class MountainGeometryDetectorTests(unittest.TestCase):
    def test_empty_geometry_returns_safe_unqualified_detection(self):
        out = detect_mountain_geometry([])
        self.assertFalse(out.qualified_alternating_mountain)
        self.assertIsNone(out.owner_side)
        self.assertFalse(out.mature_edge)
        self.assertEqual(
            out.diagnostics.get("reason"),
            "NO_ARC_EPISODES",
        )

    def test_mature_up_crest_stall_qualifies_alternating_edge(self):
        current = [
            row(arc_id="A7", direction="UP", epoch_ms=0, age=0, btc=1015, phase="BUILDING"),
            row(arc_id="A7", direction="UP", epoch_ms=100_000, age=100, btc=1045, phase="MATURE"),
            row(arc_id="A7", direction="UP", epoch_ms=115_000, age=115, btc=1050, phase="CREST_FORMING"),
            row(arc_id="A7", direction="UP", epoch_ms=130_000, age=130, btc=1047, phase="CREST_FORMING"),
        ]
        out = detect_mountain_geometry(alternating_history(current))
        self.assertTrue(out.qualified_alternating_mountain)
        self.assertEqual(out.owner_side, Side.YES)
        self.assertTrue(out.mature_edge)
        self.assertTrue(out.edge_window_active)
        self.assertTrue(out.stall)
        self.assertTrue(out.hesitation)
        self.assertFalse(out.strong_active_release)

    def test_middle_of_arc_is_not_mature_edge(self):
        current = [
            row(arc_id="A7", direction="UP", epoch_ms=0, age=0, btc=1015, phase="BUILDING"),
            row(arc_id="A7", direction="UP", epoch_ms=60_000, age=60, btc=1030, phase="BUILDING"),
        ]
        out = detect_mountain_geometry(alternating_history(current))
        self.assertTrue(out.qualified_alternating_mountain)
        self.assertFalse(out.mature_edge)

    def test_expanding_mature_leg_is_active_release_not_fade(self):
        current = [
            row(arc_id="A7", direction="UP", epoch_ms=0, age=0, btc=1015, phase="BUILDING"),
            row(arc_id="A7", direction="UP", epoch_ms=115_000, age=115, btc=1045, phase="MATURE"),
            row(
                arc_id="A7", direction="UP", epoch_ms=130_000, age=130,
                btc=1055, phase="EXPANDING", s3=1.6, s6=1.0
            ),
        ]
        out = detect_mountain_geometry(alternating_history(current))
        self.assertTrue(out.mature_edge)
        self.assertTrue(out.strong_active_release)

    def test_meaningful_retreat_after_strict_top_is_terminal_evidence(self):
        current = [
            row(arc_id="A7", direction="UP", epoch_ms=0, age=0, btc=1015, phase="BUILDING"),
            row(arc_id="A7", direction="UP", epoch_ms=110_000, age=110, btc=1050, phase="CREST_FORMING"),
            row(arc_id="A7", direction="UP", epoch_ms=140_000, age=140, btc=1035, phase="MATURE"),
        ]
        out = detect_mountain_geometry(alternating_history(current))
        self.assertTrue(out.mature_edge)
        self.assertTrue(out.meaningful_retreat)

    def test_failed_reextension_after_retreat_is_detected(self):
        current = [
            row(arc_id="A7", direction="UP", epoch_ms=0, age=0, btc=1015, phase="BUILDING"),
            row(arc_id="A7", direction="UP", epoch_ms=110_000, age=110, btc=1050, phase="CREST_FORMING"),
            row(arc_id="A7", direction="UP", epoch_ms=125_000, age=125, btc=1035, phase="MATURE"),
            row(arc_id="A7", direction="UP", epoch_ms=140_000, age=140, btc=1045, phase="MATURE"),
        ]
        out = detect_mountain_geometry(alternating_history(current))
        self.assertTrue(out.failed_reextension)
        self.assertTrue(out.mature_edge)

    def test_down_trough_mirrors_up_crest(self):
        # Build an alternating history ending with current DOWN instead.
        rows = []
        t = 0
        specs = [
            ("A1", "DOWN", 180, 1050),
            ("A2", "UP", 190, 1010),
            ("A3", "DOWN", 170, 1045),
            ("A4", "UP", 180, 1005),
            ("A5", "DOWN", 200, 1040),
            ("A6", "UP", 170, 1000),
        ]
        for arc_id, direction, duration, base in specs:
            rows.extend(completed_arc(arc_id, direction, t, duration, base))
            t += (duration + 5) * 1000
        current = [
            row(arc_id="A7", direction="DOWN", epoch_ms=t, age=0, btc=1035, phase="BUILDING"),
            row(arc_id="A7", direction="DOWN", epoch_ms=t+115_000, age=115, btc=1000, phase="TROUGH_FORMING"),
            row(arc_id="A7", direction="DOWN", epoch_ms=t+130_000, age=130, btc=1004, phase="TROUGH_FORMING"),
        ]
        rows.extend(current)
        out = detect_mountain_geometry(rows)
        self.assertTrue(out.qualified_alternating_mountain)
        self.assertEqual(out.owner_side, Side.NO)
        self.assertTrue(out.mature_edge)
        self.assertTrue(out.hesitation)


if __name__ == "__main__":
    unittest.main()
