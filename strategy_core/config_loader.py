from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from strategy_core.tools.heist import HeistConfig
from strategy_core.tools.mountain import MountainConfig
from strategy_core.tools.rail import RailConfig
from strategy_core.tools.release import ReleaseConfig


@dataclass(frozen=True)
class ToolConfigBundle:
    rail: RailConfig
    mountain: MountainConfig
    heist: HeistConfig
    release: ReleaseConfig


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


def load_default_tool_configs() -> ToolConfigBundle:
    config_dir = (
        Path(__file__).resolve().parent
        / "config"
    )
    return ToolConfigBundle(
        rail=load_rail_config(
            config_dir / "rail.json"
        ),
        mountain=load_mountain_config(
            config_dir / "mountain.json"
        ),
        heist=load_heist_config(
            config_dir / "heist.json"
        ),
        release=load_release_config(
            config_dir / "release.json"
        ),
    )
