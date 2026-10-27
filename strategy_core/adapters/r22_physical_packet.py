from __future__ import annotations

from typing import Any, Mapping

from strategy_core.router import PhysicalEvidence
from strategy_core.shadow_frame import ShadowFrame
from strategy_core.types import MarketSnapshot, Side


def _side(value: Any) -> Side | None:
    if value is None:
        return None
    text = str(value).upper()
    if text == "YES":
        return Side.YES
    if text == "NO":
        return Side.NO
    return None


def _number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _slope_side(*values: Any) -> Side | None:
    nums = [
        value
        for value in (
            _number(item)
            for item in values
        )
        if value is not None
    ]
    if not nums:
        return None
    pos = sum(value > 0 for value in nums)
    neg = sum(value < 0 for value in nums)
    if pos and not neg:
        return Side.YES
    if neg and not pos:
        return Side.NO
    return None


def frame_from_r22_physical_packet(
    *,
    af: Mapping[str, Any],
    facts: Mapping[str, Any],
    now_ts: float,
    ticker: str,
    contract_age_s: float,
    yes_ask: float | None,
    no_ask: float | None,
    quote_current: bool,
    depth_available: bool,
) -> ShadowFrame:
    """Translate R22 physical telemetry into Tool Rack SHADOW evidence.

    The adapter intentionally ignores the legacy R22 routes dictionary and all
    R22 entry permissions/opportunity IDs. It consumes measurements only.

    The Heist bridge is provisional telemetry until the clean Tool Rack Heist
    detector is implemented; legacy Heist may describe a box but cannot trade
    through this adapter by itself.
    """

    evidence = facts.get("evidence") or {}
    ctx = (
        evidence.get("territory_context")
        or {}
    )
    pilot = af.get("command_pilot") or {}
    compass = (
        pilot.get("actual_ema9_compass")
        or {}
    )

    ema9_side = _side(
        compass.get("side")
        or pilot.get("side")
    )
    ema30_side = _slope_side(
        ctx.get("e30d30"),
        ctx.get("e30d60"),
    )

    recent_count = int(
        _number(
            ctx.get(
                "rail_recent_owner_wall_count"
            )
        )
        or 0
    )
    persistence_proven = bool(
        ctx.get("rail_persistence_proven")
        is True
    )
    wall_rollovers = int(
        _number(
            ctx.get(
                "rail_wall_rollovers_observed"
            )
        )
        or 0
    )

    # Rail is derived from current physical measurements, not from R22's
    # terrain_tool or rail_flow_entry permission.
    rail_parallel = bool(
        ctx.get(
            "rail_parallel_ema_geometry"
        )
        is True
    )
    directional_residence = bool(
        rail_parallel
        or ctx.get("rail_price_supported")
        is True
    )

    # Provisional SHADOW telemetry only until Tool Rack implements its own
    # bounded-box Heist detector.
    legacy_heist_described = bool(
        pilot.get("heist_owns_territory")
        is True
        or ctx.get("terrain_tool") == "HEIST"
    )

    territory_handoff = bool(
        ctx.get("territory_handoff_proven")
        is True
        or ctx.get(
            "terrain_release_catcher_ready"
        )
        is True
    )
    release_side = _side(
        ctx.get("territory_handoff_side")
        or ctx.get(
            "terrain_release_catcher_side"
        )
    )

    physical = PhysicalEvidence(
        ema9_direction=ema9_side,
        ema30_direction=ema30_side,
        ema_pair_parallel=rail_parallel,
        directional_residence=(
            directional_residence
        ),
        rolling_mountain_repetitions=(
            recent_count
        ),
        contracts_persistent=(
            max(
                1.0,
                float(wall_rollovers),
            )
            if persistence_proven
            else 0.0
        ),
        alternating_mountain=bool(
            ctx.get(
                "simple_mountain_alternating"
            )
            is True
        ),
        rolling_mountain=bool(
            recent_count >= 1
            or ctx.get(
                "regular_clean_mountain"
            )
            is True
        ),
        qualified_heist=(
            legacy_heist_described
        ),
        compression_unresolved=False,
        release_handoff_confirmed=(
            territory_handoff
        ),
        release_side=release_side,
        heist_takeover_confirmed=bool(
            ctx.get(
                "qualified_heist_handoff_from_rail"
            )
            is True
        ),
    )

    snapshot = MarketSnapshot(
        now_ts=float(now_ts),
        ticker=str(ticker),
        contract_age_s=float(
            contract_age_s
        ),
        yes_ask=(
            None
            if yes_ask is None
            else float(yes_ask)
        ),
        no_ask=(
            None
            if no_ask is None
            else float(no_ask)
        ),
        quote_current=bool(
            quote_current
        ),
        depth_available=bool(
            depth_available
        ),
        metadata={
            "adapter": (
                "R22_PHYSICAL_PACKET_SHADOW_ONLY"
            ),
            "legacy_routes_ignored": True,
            "legacy_heist_is_provisional_telemetry": True,
        },
    )
    return ShadowFrame(
        evidence=physical,
        snapshot=snapshot,
    )
