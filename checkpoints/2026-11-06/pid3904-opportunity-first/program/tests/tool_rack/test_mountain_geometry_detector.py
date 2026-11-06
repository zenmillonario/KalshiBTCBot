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
        "ema9": btc - sign * 20,
        "ema30": btc - sign * 30,
        "arc_phase": phase,
        "arc_amplitude": amplitude,
        "arc_prominence_threshold": prominence,
        "range60": range60,
        "struct_slope3m": sign * s3,
        "struct_slope6m": sign * s6,
    }


def completed_arc(arc_id, direction, start_ms, duration_s, base):
    sign = 1 if direction == "UP" else -1
    return [{**row(arc_id=arc_id, direction=direction, epoch_ms=start_ms + age*1000,
                age=age, btc=base + sign*40*age/duration_s,
                phase="ROLLING" if age == duration_s else "BUILDING"),
             "ema9": base + sign*40*age/duration_s}
            for age in range(0, duration_s + 1, 5)]


def native_current(knots):
    """Explicit synthetic five-second observations, never real-data backfill."""
    out = []
    sign = 1 if knots[0]["arc_direction"] == "UP" else -1
    origin = knots[0]["epoch_ms"]
    base_e9 = knots[0]["ema9"]
    for a, b in zip(knots, knots[1:]):
        elapsed = (b["epoch_ms"] - a["epoch_ms"]) / 1000
        for seconds in range(0, int(elapsed), 5):
            fraction = seconds / elapsed
            item = dict(a)
            item.update(epoch_ms=a["epoch_ms"] + seconds*1000,
                        arc_age_sec=a["arc_age_sec"] + seconds,
                        btc_price=a["btc_price"] + fraction*(b["btc_price"]-a["btc_price"]))
            item["ema9"] = base_e9 + sign*.18*(item["epoch_ms"]-origin)/1000
            out.append(item)
    last = dict(knots[-1])
    last["ema9"] = base_e9 + sign*.18*(last["epoch_ms"]-origin)/1000
    out.append(last)
    return out


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
    for item in native_current(current_rows):
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

    def test_under_half_previous_arc_scale_has_hard_peak_veto(self):
        current = [
            row(arc_id="A7", direction="UP", epoch_ms=0, age=0, btc=1015, phase="BUILDING", amplitude=0),
            row(arc_id="A7", direction="UP", epoch_ms=60_000, age=60, btc=1022, phase="CREST_FORMING", amplitude=7),
            row(arc_id="A7", direction="UP", epoch_ms=70_000, age=70, btc=1022, phase="CREST_FORMING", amplitude=8),
        ]
        out = detect_mountain_geometry(alternating_history(current))
        scale = out.diagnostics["scale_progress"]
        self.assertLess(scale["duration_ratio_to_comparable_mean"], .5)
        self.assertLess(scale["amplitude_ratio_to_comparable_mean"], .5)
        self.assertTrue(scale["prehalf_scale_veto"])
        self.assertFalse(out.mature_edge)
        self.assertFalse(out.diagnostics["terminal_evidence_qualified"])

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
                btc=1055, phase="EXPANDING", s3=1.6, s6=2.6, range60=10.0
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


    def _gap_envelope_history(self, *, contracting_tail=False):
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
            rows.extend(completed_arc(arc_id, direction, t, duration, base))
            t += (duration + 5) * 1000
        base_e9 = 1010.0
        for age in range(0, 131, 5):
            e9 = base_e9 + 0.20 * age
            if contracting_tail:
                gap = 5.0 + 0.10 * min(age, 120) - 0.10 * max(0, age - 120)
            else:
                gap = 5.0 + 0.10 * age
            e30 = e9 - gap
            # Price can hesitate before EMA9/EMA30 separation is finished.
            # That hesitation alone must not be mistaken for the arc top.
            btc = e9 + 20.0 - (0.0 if age <= 120 else (age - 120) * 0.40)
            rows.append({
                "arc_id": "A7", "arc_direction": "UP", "epoch_ms": t + age * 1000,
                "arc_age_sec": age, "btc_price": btc, "ema9": e9, "ema30": e30,
                "arc_phase": "CREST_FORMING" if age >= 110 else "BUILDING",
                "arc_amplitude": e9 - base_e9, "arc_prominence_threshold": 5.0,
                "range60": 40.0, "struct_slope3m": 1.0, "struct_slope6m": 1.2,
            })
        return rows

    def test_price_hesitation_cannot_fish_top_while_ema_gap_is_still_expanding_below_previous_arc(self):
        out = detect_mountain_geometry(self._gap_envelope_history(contracting_tail=False))
        guard = out.diagnostics["ema9_ema30_gap_edge_guard"]
        self.assertTrue(out.mature_edge)
        self.assertTrue(out.stall)
        self.assertTrue(out.hesitation)
        self.assertTrue(guard["current_gap_expanding"])
        self.assertTrue(guard["current_gap_below_previous_arc"])
        self.assertTrue(guard["terminal_blocked_while_gap_expands_below_previous"])
        self.assertFalse(out.diagnostics["terminal_evidence_qualified"])

    def test_smaller_mountain_is_still_terminal_after_gap_stops_expanding(self):
        out = detect_mountain_geometry(self._gap_envelope_history(contracting_tail=True))
        guard = out.diagnostics["ema9_ema30_gap_edge_guard"]
        self.assertTrue(out.mature_edge)
        self.assertTrue(guard["current_gap_below_previous_arc"])
        self.assertFalse(guard["current_gap_expanding"])
        self.assertFalse(guard["terminal_blocked_while_gap_expands_below_previous"])
        self.assertTrue(guard["small_mountain_may_terminate_after_expansion_stops"])
        self.assertTrue(out.diagnostics["terminal_evidence_qualified"])

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
        rows.extend(native_current(current))
        out = detect_mountain_geometry(rows)
        self.assertTrue(out.qualified_alternating_mountain)
        self.assertEqual(out.owner_side, Side.NO)
        self.assertTrue(out.mature_edge)
        self.assertTrue(out.hesitation)


if __name__ == "__main__":
    unittest.main()
