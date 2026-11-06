"""Exact-lot admission for one directional primary and one tactical mission.

This module validates tool-supplied identity, not physical trading signals.
Lazarus admission remains its separate existing protocol.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from strategy_core.types import ToolIntent
from strategy_core.source_freshness import source_receipt_is_fresh


POSITION_ROLES = frozenset(("PRIMARY", "TACTICAL"))


def field(position: Any, key: str, default: Any = None) -> Any:
    return position.get(key, default) if isinstance(position, Mapping) else getattr(position, key, default)


def position_role(position: Any) -> str | None:
    entry = field(position, "entry_metadata", {}) or {}
    role = field(position, "position_role") or entry.get("position_role")
    return role if role in POSITION_ROLES else None


def role_pair_proof_valid(older: Mapping[str, Any], newer: Mapping[str, Any]) -> bool:
    """Durable identity check, including after an independently managed exit."""
    proof = (newer.get("entry_metadata") or {}).get("independent_role_mission") or {}
    older_entry, newer_entry = older.get("entry_metadata") or {}, newer.get("entry_metadata") or {}
    return bool(proof.get("protocol") == "NORMAL_PRIMARY_TACTICAL_V1"
        and type(proof.get("continuity_generation")) is int
        and proof["continuity_generation"] >= 0
        and position_role(older) in POSITION_ROLES and position_role(newer) in POSITION_ROLES
        and position_role(older) != position_role(newer)
        and older.get("side") != newer.get("side")
        and older.get("ticker") == newer.get("ticker") == proof.get("ticker")
        and proof.get("held_position_id") == str(older.get("position_id"))
        and proof.get("held_role") == position_role(older)
        and proof.get("new_role") == position_role(newer)
        and proof.get("held_mission_id") == older_entry.get("physical_mission_id")
        and proof.get("mission_id") == newer_entry.get("physical_mission_id")
        and bool(proof.get("held_mission_id")) and bool(proof.get("mission_id"))
        and proof.get("held_mission_id") != proof.get("mission_id"))


def normal_role_entry_denial(intent: ToolIntent, held: Sequence[Any], *, now_ts: float,
                            continuity_generation: int | None = None) -> str | None:
    if len(held) != 1:
        return "NORMAL_ROLE_CAPACITY_ONE_PRIMARY_ONE_TACTICAL"
    old = held[0]
    if field(old, "exit_required", False) or field(old, "custody_state", "NORMAL") not in ("NORMAL", "RECOVERED_NORMAL"):
        return "NORMAL_ROLE_COMPANION_REQUIRES_STABLE_HELD_CUSTODY"
    role, old_role = intent.metadata.get("position_role"), position_role(old)
    if role not in POSITION_ROLES or old_role not in POSITION_ROLES:
        return "NORMAL_ROLE_EXPLICIT_PRIMARY_TACTICAL_IDENTITY_REQUIRED"
    if role == old_role:
        return "NORMAL_ROLE_ALREADY_OCCUPIED"
    side = field(old, "side")
    side = getattr(side, "value", side)
    if intent.side is None or intent.side.value == side:
        return "SAME_SIDE_NORMAL_ROLE_STACKING_FORBIDDEN"
    proof = intent.metadata.get("independent_role_mission")
    entry = field(old, "entry_metadata", {}) or {}
    if not isinstance(proof, Mapping):
        return "INDEPENDENT_NORMAL_ROLE_MISSION_REQUIRED"
    if (proof.get("protocol") != "NORMAL_PRIMARY_TACTICAL_V1"
            or proof.get("held_position_id") != str(field(old, "position_id"))
            or proof.get("ticker") != field(old, "ticker")
            or proof.get("held_role") != old_role or proof.get("new_role") != role
            or proof.get("held_mission_id") != entry.get("physical_mission_id")
            or not proof.get("held_mission_id") or not proof.get("mission_id")
            or proof.get("mission_id") != intent.metadata.get("physical_mission_id")
            or proof.get("mission_id") == proof.get("held_mission_id")
            or intent.opportunity_id == field(old, "opportunity_id")):
        return "EXACT_DISTINCT_NORMAL_ROLE_MISSION_REQUIRED"
    try:
        observed = float(proof["observed_ts"])
        source_ms = float(proof["source_ms"])
        fresh = (math.isfinite(observed) and math.isfinite(source_ms)
                 and 0 <= now_ts - observed <= 3.0 and abs(observed * 1000 - source_ms) <= .001)
        if proof.get("source_receipt") is not None:
            # New direct captures keep local proof time and exchange source
            # time separate. Old proof packets retain their exact equality.
            fresh = (math.isfinite(observed) and 0 <= now_ts - observed <= 3.0
                and source_receipt_is_fresh(proof["source_receipt"], now_ts=now_ts,
                    source_ms=source_ms, max_age_seconds=3.,
                    continuity_generation=proof.get("continuity_generation")))
    except (KeyError, TypeError, ValueError, OverflowError):
        fresh = False
    if not fresh:
        return "CURRENT_NORMAL_ROLE_SOURCE_REQUIRED"
    if (type(proof.get("continuity_generation")) is not int or proof["continuity_generation"] < 0
            or continuity_generation is not None and (type(continuity_generation) is not int
                or continuity_generation < 0 or proof["continuity_generation"] != continuity_generation)):
        return "NORMAL_ROLE_SOURCE_GENERATION_MISMATCH"
    return None
