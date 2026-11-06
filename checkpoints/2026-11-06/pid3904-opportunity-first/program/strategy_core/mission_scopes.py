"""Dependency-free physical scope proof shared by tools and mission policy."""
from __future__ import annotations

import math
from typing import Any, Mapping

PARENT_MISSION_PURPOSES = frozenset(("MAIN_CONTRACT", "ARC_RETURN"))

def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}

def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None

def _side(direction: Any) -> str | None:
    return {"UP": "YES", "DOWN": "NO", "YES": "YES", "NO": "NO"}.get(direction)

def _opposite(side: str | None) -> str | None:
    return {"YES": "NO", "NO": "YES"}.get(side)


def qualified_full_arc_candidate(context: Mapping[str, Any], side: Any,
                                 source_ms: Any = None) -> bool:
    """Bind a full return to the observed parent edge and its incoming scope.

    Contract forecasts and outgoing EMA direction are deliberately absent.
    A small local turn, a cheap quote, or a stale candidate cannot manufacture
    this full-leg purpose. Freshness against wall time remains the caller's
    responsibility; all evidence here must describe this same observation.
    """
    context = _map(context)
    side = _side(getattr(side, "value", side))
    source = _num(context.get("source_ms") if source_ms is None else source_ms)
    generation = context.get("continuity_generation")
    candidate = _map(_map(context.get("candidates")).get(side))
    parent = _map(context.get("parent"))
    edge = _map(parent.get("entry_edge"))
    successor = _map(parent.get("successor"))
    edge_known, successor_known = _num(edge.get("known_ms")), _num(successor.get("known_ms"))
    return bool(side is not None and source is not None and source > 0
        and context.get("current") is True and _num(context.get("source_ms")) == source
        and type(generation) is int and generation >= 0
        and candidate.get("classification") == "PARENT_EDGE_RETURN"
        and candidate.get("qualified_edge") is True and candidate.get("side") == side
        and _num(candidate.get("source_ms")) == source
        and candidate.get("continuity_generation") == generation
        and isinstance(parent.get("id"), str) and bool(parent["id"])
        and parent.get("side") == _opposite(side) and parent.get("status") == "ACTIVE"
        and parent.get("invalidated") is not True
        and edge.get("qualified") is True and edge.get("scope_id") == parent["id"]
        and edge.get("side") == parent.get("side")
        and _num(edge.get("source_ms")) == source
        and edge.get("continuity_generation") == generation
        and edge_known is not None and 0 <= edge_known <= source
        and isinstance(successor.get("id"), str) and bool(successor["id"])
        and successor["id"] != parent["id"]
        and candidate.get("parent_leg_id") == successor["id"]
        and successor.get("side") == side and successor.get("status") == "ANTICIPATED"
        and successor.get("supported") is True and successor.get("invalidated") is not True
        and successor.get("predecessor_id") == parent["id"]
        and _num(successor.get("source_ms")) == source
        and successor.get("continuity_generation") == generation
        and successor_known is not None and 0 <= successor_known <= source)
