from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from strategy_core.detectors.heist_geometry import HeistGeometryConfig
from strategy_core.detectors.mountain_geometry import MountainGeometryConfig
from strategy_core.detectors.release_geometry import ReleaseGeometryConfig
from strategy_core.detectors.rail_geometry import RailGeometryConfig
from strategy_core.tools.heist import HeistConfig
from strategy_core.tools.mountain import MountainConfig
from strategy_core.tools.rail import RailConfig
from strategy_core.tools.release import ReleaseConfig


@dataclass(frozen=True)
class ToolConfigBundle:
    rail: RailConfig
    rail_detector: RailGeometryConfig
    mountain: MountainConfig
    mountain_detector: MountainGeometryConfig
    heist: HeistConfig
    heist_detector: HeistGeometryConfig
    release: ReleaseConfig
    release_detector: ReleaseGeometryConfig


def _read(path: str | Path) -> dict:
    return json.loads(
        Path(path).read_text(
            encoding="utf-8"
        )
    )


def _floor_fields(raw: dict) -> dict[str, float | None]:
    policy = raw.get("floor_policy") or {}
    return {
        "floor_" + key: float(value) if value is not None else None
        for key, value in policy.items()
        if key in ("arm_roi", "trail_fraction", "min_age_s", "immediate_arm_roi")
    }


def load_rail_config(
    path: str | Path,
) -> RailConfig:
    raw = _read(path)
    opening = raw["opening_value"]
    return RailConfig(
        size_tier=float(raw["size_tier"]),
        first_60s_max=float(
            opening["first_60s"]
        ),
        sec_60_120_max=float(
            opening["sec_60_120"]
        ),
        sec_120_240_max=float(
            opening["sec_120_240"]
        ),
        later_soft_max=float(
            opening["later_soft"]
        ),
        hard_max_price=float(raw.get("hard_max_price", 0.399)),
        activation_window_s=float(
            raw["activation_window_s"]
        ),
        reentry_after_exit=bool(
            raw["reentry_after_exit"]
        ),
        opposite_fades=bool(raw.get("opposite_fades", False)),
        rollover_creates_new_slice=bool(raw.get("rollover_creates_new_slice", True)),
        parallel_release_max_price=float(raw.get("parallel_release_max_price", 0.20)),
        **_floor_fields(raw),
    )


def load_rail_detector_config(
    path: str | Path,
) -> RailGeometryConfig:
    raw = _read(path)["detector"]
    return RailGeometryConfig(
        ema9_slope_epsilon=float(
            raw["ema9_slope_epsilon"]
        ),
        ema30_slope_epsilon=float(
            raw["ema30_slope_epsilon"]
        ),
        current_residence_window_s=float(
            raw["current_residence_window_s"]
        ),
        current_residence_min_fraction=float(
            raw["current_residence_min_fraction"]
        ),
        current_residence_min_samples=int(
            raw["current_residence_min_samples"]
        ),
        persistence_windows_s=tuple(
            float(value)
            for value in raw["persistence_windows_s"]
        ),
        persistence_alignment_min_fraction=float(
            raw["persistence_alignment_min_fraction"]
        ),
        persistence_residence_min_fraction=float(
            raw["persistence_residence_min_fraction"]
        ),
        persistence_min_samples=int(
            raw["persistence_min_samples"]
        ),
        qualification_min_persistence_s=float(
            raw["qualification_min_persistence_s"]
        ),
        early_launch_min_persistence_s=float(raw.get("early_launch_min_persistence_s", 600.0)),
        chapter_history_window_s=float(raw.get("chapter_history_window_s", 2700.0)),
        opposite_arc_break_fraction=float(raw.get("opposite_arc_break_fraction", 0.55)),
        min_same_direction_arcs=int(raw.get("min_same_direction_arcs", 1)),
    )


def load_mountain_config(
    path: str | Path,
) -> MountainConfig:
    raw = _read(path)
    return MountainConfig(
        regular_size=float(
            raw["regular_size"]
        ),
        a_plus_size=float(
            raw["a_plus_size"]
        ),
        exceptional_size=float(
            raw["exceptional_size"]
        ),
        soft_max_price=float(
            raw["soft_max_price"]
        ),
        mid_leg_entries=bool(raw.get("mid_leg_entries", False)),
        strong_active_release_defers_fade=bool(raw.get("strong_active_release_defers_fade", True)),
        tactical_fades_enabled=bool(raw.get("tactical_fades_enabled", False)),
        aligned_leg_entries_enabled=bool(raw.get("aligned_leg_entries_enabled", False)),
        edge_only_custody=bool(raw.get("edge_only_custody", True)),
        **_floor_fields(raw),
        late_counter_window_s=float(raw.get("late_counter_window_s", 60.0)),
        late_counter_max_ask=float(raw.get("late_counter_max_ask", 0.01)),
        ordinary_min_age_s=float(raw.get("ordinary_min_age_s", 30.0)),
        first_exhaustion_review_s=float(raw.get("first_exhaustion_review_s", 120.0)),
        failure_persistence_s=float(raw.get("failure_persistence_s", 6.0)),
        rollover_skip_last_s=float(raw.get("rollover_skip_last_s", 120.0)),
        rollover_reentry_window_s=float(raw.get("rollover_reentry_window_s", 240.0)),
        rollover_reentry_max_ask=float(raw.get("rollover_reentry_max_ask", 0.20)),
        edge_value_max_ask=float(raw.get("edge_value_max_ask", 0.20)),
        cheap_hover_min_ask=float(raw.get("cheap_hover_min_ask", 0.11)),
        cheap_hover_max_ask=float(raw.get("cheap_hover_max_ask", 0.16)),
        cheap_hover_min_seconds_left=float(raw.get("cheap_hover_min_seconds_left", 300.0)),
        small_arc_immediate_max_age_s=float(raw.get("small_arc_immediate_max_age_s", 180.0)),
        small_arc_immediate_max_ask=float(raw.get("small_arc_immediate_max_ask", 0.20)),
        fast_handoff_max_arc_age_s=float(raw.get("fast_handoff_max_arc_age_s", 360.0)),
        fast_handoff_max_terminal_window_age_s=float(raw.get("fast_handoff_max_terminal_window_age_s", 90.0)),
        value_ladder_stage1_ask=float(raw.get("value_ladder_stage1_ask", 0.10)),
        value_ladder_stage2_ask=float(raw.get("value_ladder_stage2_ask", 0.15)),
        value_ladder_stage1_seconds=float(raw.get("value_ladder_stage1_seconds", 90.0)),
        value_ladder_stage2_seconds=float(raw.get("value_ladder_stage2_seconds", 150.0)),
        wide_top_patient_target_ask=float(raw.get("wide_top_patient_target_ask", 0.15)),
        wide_top_patient_seconds=float(raw.get("wide_top_patient_seconds", 240.0)),
        low_wide_min_parent_age_s=float(raw.get("low_wide_min_parent_age_s", 90.0)),
        low_wide_max_parent_age_s=float(raw.get("low_wide_max_parent_age_s", 600.0)),
        low_wide_max_average_ema9_rate_btc_s=float(raw.get("low_wide_max_average_ema9_rate_btc_s", 0.20)),
        low_wide_max_abs_ema_gap_btc=float(raw.get("low_wide_max_abs_ema_gap_btc", 65.0)),
        low_wide_max_parent_amplitude_btc=float(raw.get("low_wide_max_parent_amplitude_btc", 150.0)),
        low_wide_min_child_arcs=int(raw.get("low_wide_min_child_arcs", 2)),
        low_wide_stage1_ask=float(raw.get("low_wide_stage1_ask", 0.30)),
        low_wide_stage2_ask=float(raw.get("low_wide_stage2_ask", 0.35)),
        low_wide_hard_max_ask=float(raw.get("low_wide_hard_max_ask", 0.40)),
        low_wide_stage1_seconds=float(raw.get("low_wide_stage1_seconds", 45.0)),
        low_wide_stage2_seconds=float(raw.get("low_wide_stage2_seconds", 90.0)),
        low_wide_profit_arm_roi=float(raw.get("low_wide_profit_arm_roi", 0.65)),
        low_wide_profit_trail_fraction=float(raw.get("low_wide_profit_trail_fraction", 0.03)),
        low_wide_contract_open_wait_s=float(raw.get("low_wide_contract_open_wait_s", 60.0)),
        low_wide_late_min_seconds_left=float(raw.get("low_wide_late_min_seconds_left", 120.0)),
        low_wide_late_exception_max_ask=float(raw.get("low_wide_late_exception_max_ask", 0.10)),
    )


def load_mountain_detector_config(
    path: str | Path,
) -> MountainGeometryConfig:
    raw = _read(path)["detector"]
    return MountainGeometryConfig(
        protected_middle_fraction=float(
            raw["protected_middle_fraction"]
        ),
        minimum_comparable_count=int(
            raw["minimum_comparable_count"]
        ),
        preferred_comparable_count=int(
            raw["preferred_comparable_count"]
        ),
        edge_window_min_s=float(
            raw["edge_window_min_s"]
        ),
        edge_window_max_s=float(
            raw["edge_window_max_s"]
        ),
        edge_window_duration_fraction=float(
            raw["edge_window_duration_fraction"]
        ),
        edge_tolerance_range60_fraction=float(
            raw["edge_tolerance_range60_fraction"]
        ),
        retreat_range60_fraction=float(
            raw["retreat_range60_fraction"]
        ),
        min_retreat_dollars=float(
            raw["min_retreat_dollars"]
        ),
        mature_phase_fallback_min_age_s=float(
            raw["mature_phase_fallback_min_age_s"]
        ),
        gap_relative_tolerance=float(raw.get("gap_relative_tolerance", 0.18)),
        height_relative_tolerance=float(raw.get("height_relative_tolerance", 0.20)),
        normalized_shape_tolerance=float(raw.get("normalized_shape_tolerance", 0.25)),
        native_max_gap_s=float(raw.get("native_max_gap_s", 15.0)),
        slowdown_window_s=float(raw.get("slowdown_window_s", 6.0)),
        sideways_min_btc_per_s=float(raw.get("sideways_min_btc_per_s", 0.15)),
        sideways_range60_fraction_per_s=float(raw.get("sideways_range60_fraction_per_s", 0.01)),
        contact_min_dollars=float(raw.get("contact_min_dollars", 3.0)),
        contact_range60_fraction=float(raw.get("contact_range60_fraction", 0.12)),
        expansion_ratio=float(raw.get("expansion_ratio", 1.10)),
        parent_guard_min_age_s=float(raw.get("parent_guard_min_age_s", 360.0)),
        slow_rolling_min_age_s=float(raw.get("slow_rolling_min_age_s", 900.0)),
        parent_shape_progress_fraction=float(raw.get("parent_shape_progress_fraction", 0.60)),
    )


def load_heist_config(
    path: str | Path,
) -> HeistConfig:
    raw = _read(path)
    return HeistConfig(
        regular_size=float(
            raw["regular_size"]
        ),
        lean_favored_size=float(
            raw["lean_favored_size"]
        ),
        soft_max_price=float(
            raw["soft_max_price"]
        ),
        wide_normal_max_price=float(raw.get("wide_normal_max_price", raw["soft_max_price"])),
        wide_exceptional_max_price=float(raw.get("wide_exceptional_max_price", raw["soft_max_price"])),
        release_ends_box_immediately=bool(raw.get("release_ends_box_immediately", True)),
        parallel_profit_arm_roi=float(raw.get("parallel_profit_arm_roi", 0.40)),
        parallel_profit_trail_fraction=float(raw.get("parallel_profit_trail_fraction", 0.03)),
        **_floor_fields(raw),
        late_counter_window_s=float(raw.get("late_counter_window_s", 60.0)),
        late_counter_max_ask=float(raw.get("late_counter_max_ask", 0.01)),
    )


def load_heist_detector_config(
    path: str | Path,
) -> HeistGeometryConfig:
    raw = _read(path)["detector"]
    return HeistGeometryConfig(
        candidate_windows_s=tuple(
            float(value)
            for value in raw["candidate_windows_s"]
        ),
        min_observed_span_s=float(
            raw["min_observed_span_s"]
        ),
        min_box_range_dollars=float(
            raw["min_box_range_dollars"]
        ),
        prominence_multiple=float(
            raw["prominence_multiple"]
        ),
        edge_band_fraction=float(
            raw["edge_band_fraction"]
        ),
        edge_band_min_dollars=float(
            raw["edge_band_min_dollars"]
        ),
        center_low_fraction=float(
            raw["center_low_fraction"]
        ),
        center_high_fraction=float(
            raw["center_high_fraction"]
        ),
        minimum_lower_visits=int(
            raw["minimum_lower_visits"]
        ),
        minimum_upper_visits=int(
            raw["minimum_upper_visits"]
        ),
        minimum_center_traversals=int(
            raw["minimum_center_traversals"]
        ),
        max_ema9_drift_fraction=float(
            raw["max_ema9_drift_fraction"]
        ),
        max_ema30_drift_fraction=float(
            raw["max_ema30_drift_fraction"]
        ),
        max_box_range_price_fraction=float(raw.get("max_box_range_price_fraction", 0.0015)),
        compression_drift_fraction=float(raw.get("compression_drift_fraction", 0.20)),
        parallel_drift_difference_fraction=float(raw.get("parallel_drift_difference_fraction", 0.10)),
        lean_min_drift_fraction=float(
            raw["lean_min_drift_fraction"]
        ),
    )


def load_release_config(
    path: str | Path,
) -> ReleaseConfig:
    raw = _read(path)
    return ReleaseConfig(
        structural_size=float(
            raw["structural_size"]
        ),
        soft_max_price=float(
            raw["soft_max_price"]
        ),
        first_slowdown_confirms_release=bool(raw.get("first_slowdown_confirms_release", False)),
        requires_boundary_break=bool(raw.get("requires_boundary_break", True)),
        requires_directional_expansion=bool(raw.get("requires_directional_expansion", True)),
        **_floor_fields(raw),
    )


def load_release_detector_config(
    path: str | Path,
) -> ReleaseGeometryConfig:
    raw = _read(path)["detector"]
    return ReleaseGeometryConfig(
        ema9_cross_range60_fraction=float(
            raw["ema9_cross_range60_fraction"]
        ),
        min_cross_dollars=float(
            raw["min_cross_dollars"]
        ),
        new_side_residence_fraction=float(
            raw["new_side_residence_fraction"]
        ),
        new_side_stack_fraction=float(
            raw["new_side_stack_fraction"]
        ),
        heist_break_edge_tolerance_fraction=float(
            raw["heist_break_edge_tolerance_fraction"]
        ),
    )


def load_default_tool_configs() -> ToolConfigBundle:
    config_dir = (
        Path(__file__).resolve().parent
        / "config"
    )
    rail_path = config_dir / "rail.json"
    mountain_path = config_dir / "mountain.json"
    heist_path = config_dir / "heist.json"
    release_path = config_dir / "release.json"

    return ToolConfigBundle(
        rail=load_rail_config(rail_path),
        rail_detector=load_rail_detector_config(
            rail_path
        ),
        mountain=load_mountain_config(mountain_path),
        mountain_detector=load_mountain_detector_config(
            mountain_path
        ),
        heist=load_heist_config(heist_path),
        heist_detector=load_heist_detector_config(
            heist_path
        ),
        release=load_release_config(release_path),
        release_detector=load_release_detector_config(
            release_path
        ),
    )
