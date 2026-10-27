from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ShadowEvent:
    seq: int
    ts: float
    ticker: str
    event_type: str
    territory: str | None
    side: str | None
    tool: str | None
    overlay: tuple[str, ...]
    action: str | None
    accepted_side: str | None
    opportunity_id: str | None
    reason: str | None
    observed_ask: float | None
    max_price: float | None
    release_boundary: str | None
    metadata: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "ticker": self.ticker,
            "event_type": self.event_type,
            "territory": self.territory,
            "side": self.side,
            "tool": self.tool,
            "overlay": list(self.overlay),
            "action": self.action,
            "accepted_side": self.accepted_side,
            "opportunity_id": self.opportunity_id,
            "reason": self.reason,
            "observed_ask": self.observed_ask,
            "max_price": self.max_price,
            "release_boundary": self.release_boundary,
            "metadata": dict(self.metadata),
        }


class ShadowEventTimeline:
    """Deduplicated read-only Tool Rack history.

    This is observability only. It never feeds events back into strategy.
    """

    def __init__(self, max_events: int = 300) -> None:
        self.max_events = max(20, int(max_events))
        self._events: list[ShadowEvent] = []
        self._seq = 0
        self._territory_key: tuple[Any, ...] | None = None
        self._decision_key: tuple[Any, ...] | None = None
        self._handoff_key: tuple[Any, ...] | None = None

    @property
    def events(self) -> tuple[ShadowEvent, ...]:
        return tuple(self._events)

    def _append(
        self,
        *,
        ts: float,
        ticker: str,
        event_type: str,
        result: Mapping[str, Any],
        reason: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ShadowEvent:
        self._seq += 1
        event = ShadowEvent(
            seq=self._seq,
            ts=float(ts),
            ticker=str(ticker),
            event_type=event_type,
            territory=(
                str(result.get("owned_territory"))
                if result.get("owned_territory") is not None
                else None
            ),
            side=(
                str(result.get("owned_side"))
                if result.get("owned_side") is not None
                else None
            ),
            tool=(
                str(result.get("active_tool"))
                if result.get("active_tool") is not None
                else None
            ),
            overlay=tuple(
                str(value)
                for value in (result.get("active_overlays") or [])
            ),
            action=(
                str(result.get("commander_action"))
                if result.get("commander_action") is not None
                else None
            ),
            accepted_side=(
                str(result.get("accepted_side"))
                if result.get("accepted_side") is not None
                else None
            ),
            opportunity_id=(
                str(result.get("accepted_opportunity_id"))
                if result.get("accepted_opportunity_id") is not None
                else None
            ),
            reason=(
                reason
                if reason is not None
                else (
                    str(result.get("commander_reason"))
                    if result.get("commander_reason") is not None
                    else None
                )
            ),
            observed_ask=(
                float(result["accepted_observed_ask"])
                if result.get("accepted_observed_ask") is not None
                else None
            ),
            max_price=(
                float(result["accepted_max_price"])
                if result.get("accepted_max_price") is not None
                else None
            ),
            release_boundary=(
                str(result.get("release_boundary_name"))
                if result.get("release_boundary_name") is not None
                else None
            ),
            metadata=dict(metadata or {}),
        )
        self._events.append(event)
        if len(self._events) > self.max_events:
            del self._events[:-self.max_events]
        return event

    def observe(
        self,
        *,
        ts: float,
        ticker: str,
        result: Mapping[str, Any],
    ) -> tuple[ShadowEvent, ...]:
        new: list[ShadowEvent] = []

        territory_key = (
            result.get("territory_id"),
            result.get("owned_territory"),
            result.get("owned_side"),
            result.get("active_tool"),
            tuple(result.get("active_overlays") or []),
        )
        if territory_key != self._territory_key:
            self._territory_key = territory_key
            new.append(
                self._append(
                    ts=ts,
                    ticker=ticker,
                    event_type="TERRITORY",
                    result=result,
                    reason=str(result.get("ownership_reason") or ""),
                )
            )

        handoff_key = (
            bool(result.get("handoff_confirmed")),
            bool(result.get("release_transition_pending")),
            result.get("release_boundary_name"),
            result.get("owned_territory"),
            result.get("owned_side"),
        )
        if handoff_key != self._handoff_key:
            previous = self._handoff_key
            self._handoff_key = handoff_key
            # Record only an affirmative handoff/transition change, not every
            # initial false state.
            if (
                bool(result.get("handoff_confirmed"))
                or bool(result.get("release_transition_pending"))
                or (
                    previous is not None
                    and previous[0]
                    and result.get("owned_territory") == "RELEASE_TRANSITION"
                )
            ):
                new.append(
                    self._append(
                        ts=ts,
                        ticker=ticker,
                        event_type="HANDOFF",
                        result=result,
                        reason=str(
                            result.get("lane_resolution_reason")
                            or result.get("ownership_reason")
                            or ""
                        ),
                        metadata={
                            "handoff_confirmed": bool(
                                result.get("handoff_confirmed")
                            ),
                            "release_transition_pending": bool(
                                result.get("release_transition_pending")
                            ),
                        },
                    )
                )

        decision_key = (
            result.get("commander_action"),
            result.get("accepted_tool"),
            result.get("accepted_side"),
            result.get("accepted_opportunity_id"),
            result.get("commander_reason"),
        )
        if decision_key != self._decision_key:
            self._decision_key = decision_key
            action = result.get("commander_action")
            # ENTER/RELAY are always useful. WAIT is recorded only when its
            # reason changes, making block transitions visible without flooding.
            if action in ("ENTER", "RELAY", "EXIT", "HOLD", "WAIT"):
                new.append(
                    self._append(
                        ts=ts,
                        ticker=ticker,
                        event_type="INTENT",
                        result=result,
                    )
                )

        return tuple(new)

    def snapshot(self) -> list[dict[str, Any]]:
        return [event.as_dict() for event in self._events]
