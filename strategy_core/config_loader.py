from __future__ import annotations

import json
from pathlib import Path

from strategy_core.tools.rail import RailConfig


def load_rail_config(path: str | Path) -> RailConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    opening = raw["opening_value"]
    return RailConfig(
        size_tier=float(raw["size_tier"]),
        first_60s_max=float(opening["first_60s"]),
        sec_60_120_max=float(opening["sec_60_120"]),
        sec_120_240_max=float(opening["sec_120_240"]),
        later_soft_max=float(opening["later_soft"]),
        activation_window_s=float(raw["activation_window_s"]),
        reentry_after_exit=bool(raw["reentry_after_exit"]),
    )
