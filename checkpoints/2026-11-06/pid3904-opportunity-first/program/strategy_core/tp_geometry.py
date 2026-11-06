"""Target-price geometry for OneCommander.

Pure evidence.  No entry/exit authority and no calibrated probabilities.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Any, Mapping

from strategy_core.types import MarketSnapshot, Side


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _side(value: Any) -> str | None:
    text = str(value).upper() if value is not None else ""
    return text if text in ("YES", "NO") else None


def build_tp_geometry(snapshot: MarketSnapshot) -> dict[str, Any]:
    mission = _map(snapshot.metadata.get("mission_context"))
    contract = _map(mission.get("contract"))
    direct = _map(snapshot.metadata.get("contract_value_context"))
    current = _map(snapshot.metadata.get("current_geometry"))
    mountain = _map(snapshot.metadata.get("mountain"))
    parent = _map(mountain.get("parent_structure"))
    heist = _map(snapshot.metadata.get("heist"))

    target = _num(contract.get("target")) or _num(direct.get("target"))
    btc = (_num(current.get("btc_price")) or _num(mountain.get("current_btc")))
    ema9 = _num(current.get("ema9")) or _num(mountain.get("current_ema9"))
    ema30 = _num(current.get("ema30")) or _num(mountain.get("current_ema30"))
    gap = btc - target if btc is not None and target is not None else None
    target_side = "YES" if gap is not None and gap > 0 else "NO" if gap is not None and gap < 0 else "AT_TARGET" if gap == 0 else "UNKNOWN"

    target_between_ema_band = bool(
        target is not None and ema9 is not None and ema30 is not None
        and min(ema9, ema30) <= target <= max(ema9, ema30)
    )

    # Exact terrain position is only claimed when physical bounds are actually
    # observed (e.g. a qualified Heist box). Mountain/Rail evidence keeps the
    # target gap and comparable movement capacity without inventing bounds.
    lower = _num(heist.get("lower")) if heist.get("qualified_box") is True else None
    upper = _num(heist.get("upper")) if heist.get("qualified_box") is True else None
    terrain_percentile = None
    if target is not None and lower is not None and upper is not None and upper > lower:
        terrain_percentile = (target - lower) / (upper - lower)

    prior = parent.get("prior_long_parents")
    amplitudes = []
    if isinstance(prior, (list, tuple)):
        for row in prior[-5:]:
            if isinstance(row, Mapping):
                value = _num(row.get("amplitude"))
                if value is not None and value > 0:
                    amplitudes.append(value)
    ref_amp = _num(parent.get("reference_amplitude_median"))
    if ref_amp is None and amplitudes:
        ref_amp = median(amplitudes)
    required_move = abs(gap) if gap is not None else None
    capacity_ratio = required_move / ref_amp if required_move is not None and ref_amp not in (None, 0) else None

    parent_side = _side(parent.get("parent_side")) or _side(mountain.get("owner_side"))
    shape_progress = _num(parent.get("shape_progress"))
    terminal = parent.get("parent_terminal_ready") is True
    turning = parent.get("parent_turning_or_flat") is True

    if parent_side is None:
        ownership = "UNRESOLVED"
        ownership_side = None
        ownership_basis = "NO_CURRENT_PARENT_SIDE"
    elif terminal or (turning and shape_progress is not None and shape_progress >= 1.0):
        ownership = "BOUNCE_FAVORED"
        ownership_side = "NO" if parent_side == "YES" else "YES"
        ownership_basis = "PARENT_AT_OR_BEYOND_COMPARABLE_MATURITY_AND_TURNING"
    elif shape_progress is not None and shape_progress < 1.0:
        ownership = "STARTING_LEG_FAVORED"
        ownership_side = parent_side
        ownership_basis = "PARENT_BELOW_COMPARABLE_AGE_AMPLITUDE_MATURITY"
    elif target_side == parent_side and not turning:
        ownership = "STARTING_LEG_FAVORED"
        ownership_side = parent_side
        ownership_basis = "CURRENT_PARENT_ALIGNS_WITH_SETTLEMENT_SIDE_AND_NOT_TURNING"
    else:
        ownership = "UNRESOLVED"
        ownership_side = None
        ownership_basis = "INSUFFICIENT_COMPARABLE_PARENT_EVIDENCE"

    return {
        "version": "TP_GEOMETRY_V1",
        "execution_authority": False,
        "probabilities_calibrated": False,
        "target": target,
        "btc": btc,
        "ema9": ema9,
        "ema30": ema30,
        "target_between_ema9_ema30": target_between_ema_band,
        "signed_gap_btc": gap,
        "required_move_to_target_btc": required_move,
        "observed_target_side": target_side,
        "terrain_bounds": {"lower": lower, "upper": upper, "source": "QUALIFIED_HEIST_BOX" if lower is not None else None},
        "target_terrain_percentile": terrain_percentile,
        "comparable_parent_amplitude_btc": ref_amp,
        "required_move_vs_comparable_parent_amplitude": capacity_ratio,
        "parent_side": parent_side,
        "parent_shape_progress": shape_progress,
        "parent_terminal_ready": terminal,
        "parent_turning_or_flat": turning,
        "contract_ownership": ownership,
        "contract_ownership_side": ownership_side,
        "contract_ownership_basis": ownership_basis,
        "remaining_seconds": _num(contract.get("remaining_seconds")),
    }
