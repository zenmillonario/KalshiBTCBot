"""Positive-only independent MAIN/TACTICAL lane policy.

This is a briefing/calibration layer, NOT a second Commander or executor.
A first countertrend tactical *mission* is an observation sample; repeated
callbacks of the same physical swing cannot count as a second fade.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Mapping

from strategy_core.directional_parent import directional_parent_evidence
from strategy_core.source_freshness import current_source_is_fresh
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _current_mission_parent(snapshot: MarketSnapshot) -> Mapping[str, Any]:
    """Use the already-known current parent without inventing its origin.

    An ACTIVE completed-close mission can be current before a historical gap
    qualifies. Its unobserved origin remains unobserved; this supplies only
    the existing first-counter observation context, never an entry trigger.
    Owner labels alone and stale/unrelated mission packets supply no context.
    """
    md = snapshot.metadata
    geometry = _map(md.get("current_geometry"))
    context = _map(md.get("mission_context"))
    parent = _map(context.get("parent"))
    source = _number(geometry.get("epoch_ms"))
    known = _number(parent.get("known_ms"))
    generation = md.get("geometry_continuity_generation")
    if (md.get("physical_current") is not True or context.get("current") is not True
            or source is None or known is None or not 0 <= known <= source
            or type(generation) is not int or generation < 0
            or type(context.get("continuity_generation")) is not int
            or type(parent.get("continuity_generation")) is not int
            or context.get("continuity_generation") != generation
            or parent.get("continuity_generation") != generation
            or _number(context.get("source_ms")) != source
            or _number(parent.get("source_ms")) != source
            or not isinstance(parent.get("id"), str) or not parent["id"]
            or parent.get("side") not in {"YES", "NO"}
            or parent.get("status") != "ACTIVE" or parent.get("invalidated") is True
            or not current_source_is_fresh(snapshot, source, max_age_seconds=3.)):
        return {}
    return parent


def _direction(snapshot: MarketSnapshot) -> Side | None:
    history = directional_parent_evidence(snapshot)
    if history.get("qualified") is True and history.get("side") in {"YES", "NO"}:
        return Side(history["side"])
    mountain = _map(snapshot.metadata.get("mountain"))
    cross = _map(snapshot.metadata.get("ema9_ema30_cross_context"))
    gap = _map(cross.get("gap_lifecycle"))
    if mountain.get("strong_active_release") is True or snapshot.metadata.get("release_confirmed_current") is True:
        side = str(gap.get("current_side") or mountain.get("owner_side") or "")
        return Side(side) if side in {"YES", "NO"} else None
    current = _current_mission_parent(snapshot)
    return Side(current["side"]) if current else None


def _physical_chapter(snapshot: MarketSnapshot, side: Side) -> tuple[Any, ...]:
    cross = _map(snapshot.metadata.get("ema9_ema30_cross_context"))
    gap = _map(cross.get("gap_lifecycle"))
    age = gap.get("age_seconds_since_observed_cross")
    parent_history = directional_parent_evidence(snapshot)
    try:
        # Only a witnessed cross can be named as a cross timestamp.
        crossed_at = round(snapshot.now_ts - float(age), -1)
    except (TypeError, ValueError, OverflowError):
        crossed_at = parent_history.get("observed_residence_start_source_ms")
        if crossed_at is not None:
            crossed_at = round(float(crossed_at) / 1000.0, -1)
    parent = _map(_map(snapshot.metadata.get("mountain")).get("parent_structure"))
    return (side.value, crossed_at if crossed_at is not None else str(parent.get("parent_id") or "UNKNOWN"))


def _swing_identity(intent: ToolIntent, snapshot: MarketSnapshot) -> str | None:
    heist = _map(snapshot.metadata.get("heist"))
    geometry = _map(snapshot.metadata.get("current_geometry"))
    mountain = _map(snapshot.metadata.get("mountain"))
    # A repeated price/quote update of the same edge remains one swing.
    value = (heist.get("visit_id") or heist.get("current_visit_id")
             or intent.metadata.get("entry_arc_id") or geometry.get("arc_id")
             or mountain.get("current_arc_id") or mountain.get("edge_id"))
    return str(value) if value else None


def early_main_policy(intent: ToolIntent, snapshot: MarketSnapshot) -> bool:
    """MAIN normally waits for last ten minutes; earned early routes survive.

    Applied ONLY to the *new* independent MAIN overlay, leaving existing
    operator-authorized rollover / Release candidates intact.
    """
    if snapshot.contract_age_s >= 300.0:
        return True
    md = _map(intent.metadata)
    return bool(md.get("inherited_rollover") is True
        or md.get("confirmed_release_handoff") is True
        or md.get("early_main_exception") is True)


@dataclass
class CounterfadeObservation:
    chapter: tuple[Any, ...]
    first_swing: str
    first_seen_ts: float
    min_ask: float | None = None
    max_ask: float | None = None
    min_btc: float | None = None
    max_btc: float | None = None
    observed_ticks: int = 0
    later_swings: set[str] = field(default_factory=set)

    def update(self, snapshot: MarketSnapshot, side: Side) -> None:
        price = snapshot.ask_for(side)
        if price is not None and 0 < price < 1:
            self.min_ask = price if self.min_ask is None else min(self.min_ask, price)
            self.max_ask = price if self.max_ask is None else max(self.max_ask, price)
        geometry = _map(snapshot.metadata.get("current_geometry"))
        try:
            btc = float(geometry.get("btc_price"))
        except (TypeError, ValueError):
            btc = None
        if btc is not None:
            self.min_btc = btc if self.min_btc is None else min(self.min_btc, btc)
            self.max_btc = btc if self.max_btc is None else max(self.max_btc, btc)
        self.observed_ticks += 1

    def briefing(self, side: Side) -> dict[str, Any]:
        return {"tool":"TACTICAL_COUNTERFADE_CALIBRATION", "state":"OBSERVE",
            "side": side.value, "first_swing":self.first_swing,
            "first_seen_ts":self.first_seen_ts,"ticks":self.observed_ticks,
            "min_ask":self.min_ask,"max_ask":self.max_ask,
            "min_btc":self.min_btc,"max_btc":self.max_btc,
            "execution_authority":False,"can_veto":False}


class DualLaneCounterfadeMemory:
    """Observe and skip one distinct opposing tactical swing per EMA chapter."""
    def __init__(self) -> None:
        self._records: dict[tuple[Any, ...], CounterfadeObservation] = {}
        self._last: dict[str, Any] | None = None
        self._chapter_aliases: dict[tuple[Any, ...], tuple[Any, ...]] = {}
        self._last_calibration: dict[str, Any] | None = None
        self._last_considered: tuple[ToolIntent, MarketSnapshot] | None = None

    @property
    def last_observation(self) -> dict[str, Any] | None:
        return dict(self._last) if self._last else None

    def _chapter(self, snapshot: MarketSnapshot, side: Side) -> tuple[Any, ...]:
        """Keep one parent through rollover and historical qualification.

        A current mission is named by its own identity and continuity. Bind
        its same-side historical gap to that chapter, so gaining 900 seconds
        of observed residence does not create another first fade. An opposite
        gap cannot name the current mission. Qualified history still takes
        direction precedence when the local mission is on the other side.
        """
        md = snapshot.metadata
        geometry = _map(md.get("current_geometry"))
        continuity = (md.get("geometry_continuity_generation"), geometry.get("connection_epoch"))
        historical = _physical_chapter(snapshot, side) + continuity
        parent = _current_mission_parent(snapshot)
        gap = _map(_map(md.get("ema9_ema30_cross_context")).get("gap_lifecycle"))
        if parent and parent["side"] == side.value:
            chapter = (side.value, "CURRENT_MISSION", parent["id"], *continuity)
            # UNKNOWN is not a demonstrated historical identity. A genuine
            # new current parent replaces this alias and starts a new sample.
            if gap.get("current_side") == side.value and historical[1] != "UNKNOWN":
                self._chapter_aliases[historical] = chapter
            return chapter
        return self._chapter_aliases.get(historical, historical)

    def calibration_for(self, intent: ToolIntent, snapshot: MarketSnapshot) -> dict[str, Any] | None:
        """Proof from this exact consideration, never a stale last briefing."""
        considered = self._last_considered
        if (self._last_calibration is None or considered is None
                or considered[0] is not intent or considered[1] is not snapshot):
            return None
        return dict(self._last_calibration)

    def observe_first_physical_swing(self, snapshot: MarketSnapshot) -> None:
        """Calibrate first counter-arc even before a paid Heist idea exists.

        The parent must have qualified history or source-bound current mission
        context and the child arc must be observed in the opposite direction.
        A wick or quote alone is not a physical swing. No order is booked.
        """
        self._last_calibration = None
        self._last_considered = None
        parent = _direction(snapshot)
        if parent is None:
            return
        geometry = _map(snapshot.metadata.get("current_geometry"))
        arc_direction = str(geometry.get("arc_direction") or "").upper()
        opposite = "DOWN" if parent is Side.YES else "UP"
        if arc_direction != opposite or not geometry.get("arc_id"):
            return
        side = Side.NO if parent is Side.YES else Side.YES
        chapter = self._chapter(snapshot, parent)
        swing = str(geometry["arc_id"])
        sample = self._records.get(chapter)
        if sample is None:
            sample = self._records[chapter] = CounterfadeObservation(
                chapter, swing, snapshot.now_ts)
        if sample.first_swing == swing:
            sample.update(snapshot, side)
            self._last = sample.briefing(side)

    def consider(self, intent: ToolIntent, snapshot: MarketSnapshot) -> bool:
        # Every bypass clears later-swing permission. Historical observation
        # may remain visible as research, but cannot annotate another offer.
        self._last_calibration = None
        self._last_considered = (intent, snapshot)
        if intent.action not in (Action.ENTER, Action.RELAY) or intent.side is None:
            return True
        # Evaluate counterfade calibration for ALL proposed entry families,
        # including Commander-created MAIN-labelled cheap-return shortcuts.
        # A confirmed Release or a current earned parent terminal with TP
        # transfer is a new physical chapter, not an ordinary first fade.
        if intent.tool == "RELEASE_WATCHER" and intent.lane is Lane.HANDOFF:
            return True
        parent = _direction(snapshot)
        if parent is not None and intent.side is not parent:
            mountain = _map(snapshot.metadata.get("mountain"))
            tp = _map(snapshot.metadata.get("tp_geometry"))
            confirmed = bool(snapshot.metadata.get("release_confirmed_current") is True
                and str(snapshot.metadata.get("release_candidate_side") or "") == intent.side.value)
            genuine_terminal = bool(mountain.get("terminal_evidence_qualified") is True
                and mountain.get("edge_window_active") is True
                and mountain.get("failed_reextension") is True
                and str(tp.get("contract_ownership_side") or "") == intent.side.value)
            if confirmed or genuine_terminal:
                return True
        if parent is None or parent is intent.side:
            return True
        swing = _swing_identity(intent, snapshot)
        if swing is None:
            # Missing physical identity cannot count as a new second swing.
            return False
        chapter = self._chapter(snapshot, parent)
        # Keep bounded memory without letting contract rollover reset chapter.
        if len(self._records) > 50:
            self._records = {k:v for k,v in self._records.items() if k == chapter}
            self._chapter_aliases = {k:v for k,v in self._chapter_aliases.items() if v == chapter}
        sample = self._records.get(chapter)
        if sample is None:
            sample = self._records[chapter] = CounterfadeObservation(chapter, swing, snapshot.now_ts)
        if swing == sample.first_swing:
            sample.update(snapshot, intent.side)
            self._last = sample.briefing(intent.side)
            return False
        sample.later_swings.add(swing)
        self._last = sample.briefing(intent.side)
        self._last_calibration = {"chapter": chapter, "parent_side": parent.value,
            "side": intent.side.value, "first_swing": sample.first_swing,
            "later_swing": swing, "now_ts": snapshot.now_ts,
            "source_ms": _map(snapshot.metadata.get("current_geometry")).get("epoch_ms")}
        return True
