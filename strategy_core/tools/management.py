"""Shared intent construction for tool-owned position management.

These helpers do not select a strategy, place an order, or apply quote safety.
The active tool supplies its structural HOLD/EXIT; Commander and the PAPER
executor retain objective safety and exact-contract execution authority.
"""

from __future__ import annotations

from typing import Any, Mapping

from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


def as_side(value: Any) -> Side | None:
    if isinstance(value, Side):
        return value
    try:
        return Side(str(value).upper())
    except ValueError:
        return None


def number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def entry_metadata(position: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = position.get("entry_metadata") or {}
    return raw if isinstance(raw, Mapping) else {}


def rack_context(snapshot: MarketSnapshot) -> Mapping[str, Any]:
    raw = snapshot.metadata.get("tool_rack") or {}
    return raw if isinstance(raw, Mapping) else {}


def opposing_transfer(position: Mapping[str, Any], snapshot: MarketSnapshot) -> bool:
    side = as_side(position.get("side"))
    release_side = as_side(rack_context(snapshot).get("confirmed_release_side"))
    return side is not None and release_side is not None and side is not release_side


def floor_policy(config: Any) -> dict[str, float | None]:
    return {
        "arm_roi": config.floor_arm_roi,
        "trail_fraction": config.floor_trail_fraction,
        "min_age_s": config.floor_min_age_s,
        "immediate_arm_roi": config.floor_immediate_arm_roi,
    }


def position_intent(
    *,
    tool: str,
    territory_id: str,
    lane: Lane,
    position: Mapping[str, Any],
    snapshot: MarketSnapshot,
    action: Action,
    reason: str,
    config: Any,
    metadata: Mapping[str, Any] | None = None,
) -> ToolIntent:
    return ToolIntent(
        tool=tool,
        territory_id=territory_id,
        lane=lane,
        side=as_side(position.get("side")),
        action=action,
        opportunity_id=position.get("opportunity_id"),
        max_price=None,
        size_tier=None,
        reason=reason,
        source_time=snapshot.now_ts,
        metadata={"floor_policy": floor_policy(config), **(metadata or {})},
    )
