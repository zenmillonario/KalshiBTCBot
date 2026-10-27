import unittest

from strategy_core.detectors.release_geometry import (
    ReleaseProbe,
    detect_release_for_owner,
)
from strategy_core.types import Side, Territory


def probe(**overrides):
    values = dict(
        btc=1000.0,
        ema9=1000.0,
        ema30=1000.0,
        range60=100.0,
        arc_side=Side.NO,
        arc_phase="MATURE",
        short_struct_side=Side.NO,
        medium_struct_side=Side.NO,
        micro_side=Side.NO,
        yes_residence_fraction=0.20,
        no_residence_fraction=0.80,
        yes_stack_fraction=0.10,
        no_stack_fraction=0.70,
        heist_lower=None,
        heist_upper=None,
        heist_edge_tolerance=None,
        mountain_extreme_btc=None,
        mountain_edge_age_s=None,
        diagnostics={},
    )
    values.update(overrides)
    return ReleaseProbe(**values)


class ReleaseGeometryDetectorTests(unittest.TestCase):
    def test_first_slowdown_inside_down_rail_is_watch_only(self):
        out = detect_release_for_owner(
            probe(
                btc=995,
                ema9=1000,
                arc_side=Side.NO,
                arc_phase="MATURE",
            ),
            owner_territory=Territory.DOWN_RAIL,
            owner_side=Side.NO,
        )
        self.assertTrue(out.evidence.first_slowdown_only)
        self.assertFalse(out.evidence.boundary_break)

    def test_one_price_fakeout_without_structural_expansion_is_not_release(self):
        out = detect_release_for_owner(
            probe(
                btc=1012,
                ema9=1000,
                arc_side=Side.NO,
                arc_phase="MATURE",
                short_struct_side=Side.NO,
                micro_side=Side.YES,
                yes_residence_fraction=0.35,
                no_residence_fraction=0.65,
            ),
            owner_territory=Territory.DOWN_RAIL,
            owner_side=Side.NO,
        )
        self.assertTrue(out.evidence.boundary_break)
        self.assertFalse(out.evidence.directional_expansion)
        self.assertFalse(out.evidence.old_owner_failed_reextension)
        self.assertFalse(out.evidence.new_side_residence)

    def test_down_rail_to_up_release_is_affirmative(self):
        out = detect_release_for_owner(
            probe(
                btc=1015,
                ema9=1000,
                arc_side=Side.YES,
                arc_phase="BUILDING",
                short_struct_side=Side.YES,
                medium_struct_side=Side.NO,
                micro_side=Side.YES,
                yes_residence_fraction=0.75,
                no_residence_fraction=0.25,
                yes_stack_fraction=0.45,
                no_stack_fraction=0.20,
            ),
            owner_territory=Territory.DOWN_RAIL,
            owner_side=Side.NO,
        )
        e = out.evidence
        self.assertEqual(e.candidate_side, Side.YES)
        self.assertTrue(e.boundary_break)
        self.assertTrue(e.directional_expansion)
        self.assertTrue(e.old_owner_failed_reextension)
        self.assertTrue(e.new_side_residence)

    def test_up_mountain_to_down_release_mirrors(self):
        out = detect_release_for_owner(
            probe(
                btc=985,
                ema9=1000,
                arc_side=Side.NO,
                arc_phase="EXPANDING",
                short_struct_side=Side.NO,
                medium_struct_side=Side.YES,
                micro_side=Side.NO,
                no_residence_fraction=0.80,
                yes_residence_fraction=0.20,
                no_stack_fraction=0.45,
                yes_stack_fraction=0.15,
            ),
            owner_territory=Territory.ALTERNATING_MOUNTAIN,
            owner_side=Side.YES,
        )
        e = out.evidence
        self.assertEqual(e.candidate_side, Side.NO)
        self.assertTrue(e.boundary_break)
        self.assertTrue(e.directional_expansion)

    def test_heist_upper_break_releases_yes(self):
        out = detect_release_for_owner(
            probe(
                btc=1108,
                ema9=1098,
                arc_side=Side.YES,
                arc_phase="BUILDING",
                short_struct_side=Side.YES,
                medium_struct_side=Side.YES,
                micro_side=Side.YES,
                yes_residence_fraction=0.80,
                no_residence_fraction=0.20,
                yes_stack_fraction=0.65,
                no_stack_fraction=0.10,
                heist_lower=1000,
                heist_upper=1100,
                heist_edge_tolerance=12,
            ),
            owner_territory=Territory.MARKET_HEIST,
            owner_side=None,
        )
        e = out.evidence
        self.assertEqual(e.candidate_side, Side.YES)
        self.assertTrue(e.boundary_break)
        self.assertTrue(e.directional_expansion)
        self.assertTrue(e.new_side_residence)

    def test_heist_inside_box_has_no_release_candidate(self):
        out = detect_release_for_owner(
            probe(
                btc=1098,
                ema9=1090,
                heist_lower=1000,
                heist_upper=1100,
                heist_edge_tolerance=12,
            ),
            owner_territory=Territory.MARKET_HEIST,
            owner_side=None,
        )
        self.assertIsNone(out.evidence.candidate_side)
        self.assertFalse(out.evidence.boundary_break)


if __name__ == "__main__":
    unittest.main()
