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
        activation_window_s=float(
            raw["activation_window_s"]
        ),
        reentry_after_exit=bool(
            raw["reentry_after_exit"]
        ),
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
