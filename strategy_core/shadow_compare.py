from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _epoch(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )
        return parsed.timestamp()
    except ValueError:
        return None


def _number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class PaperEntry:
    index: int
    ts: float
    ticker: str
    trade_id: str
    side: str
    price: float | None
    reason: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "ts": self.ts,
            "ticker": self.ticker,
            "trade_id": self.trade_id,
            "side": self.side,
            "price": self.price,
            "reason": self.reason,
        }


def load_paper_entries(
    ledger_path: Path,
    *,
    run_id: str | None = None,
    session_id: str | None = None,
) -> list[PaperEntry]:
    out: list[PaperEntry] = []
    with ledger_path.open(
        "r",
        encoding="utf-8",
        errors="replace",
        newline="",
    ) as handle:
        for index, row in enumerate(
            csv.DictReader(handle)
        ):
            if str(row.get("event") or "").upper() != "ENTRY":
                continue
            if (
                run_id
                and row.get("run_id")
                and row.get("run_id") != run_id
            ):
                continue
            if (
                session_id
                and row.get("session_id")
                and row.get("session_id") != session_id
            ):
                continue
            ts = _epoch(row.get("timestamp"))
            side = str(row.get("side") or "").upper()
            if ts is None or side not in ("YES", "NO"):
                continue
            out.append(
                PaperEntry(
                    index=index,
                    ts=ts,
                    ticker=str(
                        row.get("ticker") or ""
                    ),
                    trade_id=str(
                        row.get("trade_id") or ""
                    ),
                    side=side,
                    price=_number(
                        row.get("entry_ask")
                    ),
                    reason=(
                        str(row.get("reason"))
                        if row.get("reason")
                        else None
                    ),
                )
            )
    return out


def load_shadow_timeline(
    timeline_path: Path,
) -> dict[str, Any]:
    return json.loads(
        timeline_path.read_text(
            encoding="utf-8"
        )
    )


def load_shadow_event_journal(
    event_path: Path,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    with event_path.open(
        "r",
        encoding="utf-8",
        errors="replace",
    ) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    events.sort(
        key=lambda event: (
            _epoch(event.get("ts"))
            if _epoch(event.get("ts")) is not None
            else float("inf"),
            int(event.get("seq") or 0),
        )
    )
    return {"events": events}


def _all_actionable_events(
    timeline: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        event
        for event in timeline.get("events", [])
        if (
            event.get("event_type") == "INTENT"
            and event.get("action")
            in ("ENTER", "RELAY")
            and event.get("accepted_side")
            in ("YES", "NO")
            and _epoch(event.get("ts"))
            is not None
        )
    ]


def _shadow_opportunities(
    timeline: dict[str, Any],
) -> list[dict[str, Any]]:
    # Shadow does not simulate fills yet. For forensics, one physical
    # opportunity ID must count once, even if quote stale/fresh toggles cause
    # the same intent to be emitted repeatedly.
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for event in _all_actionable_events(timeline):
        opportunity_id = str(
            event.get("opportunity_id") or ""
        )
        if opportunity_id:
            if opportunity_id in seen:
                continue
            seen.add(opportunity_id)
        out.append(event)

    return out


def _territory_at(
    timeline: dict[str, Any],
    ts: float,
) -> dict[str, Any] | None:
    territory = None
    for event in timeline.get("events", []):
        if event.get("event_type") != "TERRITORY":
            continue
        event_ts = _epoch(event.get("ts"))
        if event_ts is None:
            continue
        if event_ts <= ts:
            territory = event
        else:
            break
    return territory


def _territory_alignment(
    territory: dict[str, Any] | None,
    paper_side: str,
) -> str:
    if not territory:
        return "NO_SHADOW_TERRITORY"

    name = str(
        territory.get("territory") or ""
    )
    side = str(
        territory.get("side") or ""
    )

    if name == "DOWN_RAIL":
        return (
            "ALIGNED"
            if paper_side == "NO"
            else "AGAINST_TERRITORY"
        )
    if name == "UP_RAIL":
        return (
            "ALIGNED"
            if paper_side == "YES"
            else "AGAINST_TERRITORY"
        )
    if name == "RELEASE_TRANSITION":
        return (
            "ALIGNED"
            if side == paper_side
            else "AGAINST_RELEASE"
        )
    return "TERRITORY_SIDE_CONTEXT_ONLY"


def _shadow_summary(
    event: dict[str, Any],
) -> dict[str, Any]:
    return {
        "seq": event.get("seq"),
        "ts": _epoch(event.get("ts")),
        "ticker": event.get("ticker"),
        "territory": event.get("territory"),
        "tool": event.get("tool"),
        "action": event.get("action"),
        "side": event.get("accepted_side"),
        "observed_ask": _number(
            event.get("observed_ask")
        ),
        "max_price": _number(
            event.get("max_price")
        ),
        "opportunity_id": event.get(
            "opportunity_id"
        ),
    }


def compare_shadow_to_paper(
    timeline: dict[str, Any],
    paper_entries: list[PaperEntry],
    *,
    before_seconds: float = 120.0,
    after_seconds: float = 120.0,
) -> dict[str, Any]:
    actionable_events = _all_actionable_events(
        timeline
    )
    shadow = _shadow_opportunities(
        timeline
    )

    used_paper: set[int] = set()
    used_shadow: set[int] = set()
    pairings: dict[
        int,
        tuple[int, str],
    ] = {}

    def eligible(
        entry: PaperEntry,
        event: dict[str, Any],
    ) -> tuple[bool, float | None]:
        if (
            str(event.get("ticker") or "")
            != entry.ticker
        ):
            return False, None
        event_ts = _epoch(event.get("ts"))
        if event_ts is None:
            return False, None
        delay = entry.ts - event_ts
        if (
            delay < -after_seconds
            or delay > before_seconds
        ):
            return False, None
        return True, delay

    # Pass 1: same-side Tool Rack opportunities that existed BEFORE the PAPER
    # entry. These are the only pairings that can legitimately measure legacy
    # delay/chase. Choose the closest prior opportunity globally.
    prior_same: list[
        tuple[float, int, int]
    ] = []
    for paper_index, entry in enumerate(
        paper_entries
    ):
        for shadow_index, event in enumerate(
            shadow
        ):
            ok, delay = eligible(
                entry,
                event,
            )
            if (
                not ok
                or delay is None
                or delay < 0
                or str(
                    event.get(
                        "accepted_side"
                    )
                    or ""
                ).upper()
                != entry.side
            ):
                continue
            prior_same.append(
                (
                    delay,
                    paper_index,
                    shadow_index,
                )
            )

    for _, paper_index, shadow_index in sorted(
        prior_same
    ):
        if (
            paper_index in used_paper
            or shadow_index in used_shadow
        ):
            continue
        used_paper.add(paper_index)
        used_shadow.add(shadow_index)
        pairings[paper_index] = (
            shadow_index,
            "TOOL_RACK_LED_SAME_SIDE",
        )

    # Pass 2: same-side opportunity that appears only AFTER PAPER. Preserve it
    # as useful agreement evidence, but never call the PAPER entry "late".
    future_same: list[
        tuple[float, int, int]
    ] = []
    for paper_index, entry in enumerate(
        paper_entries
    ):
        if paper_index in used_paper:
            continue
        for shadow_index, event in enumerate(
            shadow
        ):
            if shadow_index in used_shadow:
                continue
            ok, delay = eligible(
                entry,
                event,
            )
            if (
                not ok
                or delay is None
                or delay >= 0
                or str(
                    event.get(
                        "accepted_side"
                    )
                    or ""
                ).upper()
                != entry.side
            ):
                continue
            future_same.append(
                (
                    abs(delay),
                    paper_index,
                    shadow_index,
                )
            )

    for _, paper_index, shadow_index in sorted(
        future_same
    ):
        if (
            paper_index in used_paper
            or shadow_index in used_shadow
        ):
            continue
        used_paper.add(paper_index)
        used_shadow.add(shadow_index)
        pairings[paper_index] = (
            shadow_index,
            "TOOL_RACK_FOLLOWED_SAME_SIDE",
        )

    # Pass 3: remaining nearby opposite-side opportunities are negative
    # controls. Same-side agreement always has first priority.
    opposite_pairs: list[
        tuple[float, int, int]
    ] = []
    for paper_index, entry in enumerate(
        paper_entries
    ):
        if paper_index in used_paper:
            continue
        for shadow_index, event in enumerate(
            shadow
        ):
            if shadow_index in used_shadow:
                continue
            ok, delay = eligible(
                entry,
                event,
            )
            if not ok or delay is None:
                continue
            opposite_pairs.append(
                (
                    abs(delay),
                    paper_index,
                    shadow_index,
                )
            )

    for _, paper_index, shadow_index in sorted(
        opposite_pairs
    ):
        if (
            paper_index in used_paper
            or shadow_index in used_shadow
        ):
            continue
        used_paper.add(paper_index)
        used_shadow.add(shadow_index)
        pairings[paper_index] = (
            shadow_index,
            "OPPOSITE_PAPER_ENTRY",
        )

    paper_comparisons: list[
        dict[str, Any]
    ] = []

    for paper_index, entry in enumerate(
        paper_entries
    ):
        territory = _territory_at(
            timeline,
            entry.ts,
        )

        chosen = None
        classification = "PAPER_ONLY"
        delay_seconds = None
        price_delta = None

        if paper_index in pairings:
            shadow_index, classification = (
                pairings[paper_index]
            )
            chosen = shadow[shadow_index]
            chosen_ts = _epoch(
                chosen.get("ts")
            )
            if chosen_ts is not None:
                delay_seconds = (
                    entry.ts - chosen_ts
                )

            shadow_ask = _number(
                chosen.get("observed_ask")
            )
            if (
                entry.price is not None
                and shadow_ask is not None
            ):
                price_delta = (
                    entry.price - shadow_ask
                )

        paper_comparisons.append(
            {
                "classification": classification,
                "paper": entry.as_dict(),
                "shadow": (
                    _shadow_summary(chosen)
                    if chosen is not None
                    else None
                ),
                "delay_seconds": delay_seconds,
                "price_delta": price_delta,
                "shadow_territory": (
                    territory.get("territory")
                    if territory
                    else None
                ),
                "shadow_territory_side": (
                    territory.get("side")
                    if territory
                    else None
                ),
                "alignment": (
                    _territory_alignment(
                        territory,
                        entry.side,
                    )
                ),
            }
        )

    unmatched_shadow = [
        _shadow_summary(event)
        for index, event in enumerate(shadow)
        if index not in used_shadow
    ]

    led_rows = [
        row
        for row in paper_comparisons
        if row["classification"]
        == "TOOL_RACK_LED_SAME_SIDE"
    ]
    led_delays = [
        row["delay_seconds"]
        for row in led_rows
        if row["delay_seconds"] is not None
    ]
    led_deltas = [
        row["price_delta"]
        for row in led_rows
        if row["price_delta"] is not None
    ]

    summary = {
        "shadow_actionable_events": len(
            actionable_events
        ),
        "shadow_actionable": len(shadow),
        "shadow_unique_opportunities": len(
            shadow
        ),
        "paper_entries": len(
            paper_entries
        ),
        "tool_rack_led_same_side": sum(
            row["classification"]
            == "TOOL_RACK_LED_SAME_SIDE"
            for row in paper_comparisons
        ),
        "tool_rack_followed_same_side": sum(
            row["classification"]
            == "TOOL_RACK_FOLLOWED_SAME_SIDE"
            for row in paper_comparisons
        ),
        "matched_same_side": sum(
            row["classification"]
            in (
                "TOOL_RACK_LED_SAME_SIDE",
                "TOOL_RACK_FOLLOWED_SAME_SIDE",
            )
            for row in paper_comparisons
        ),
        "opposite_paper_entry": sum(
            row["classification"]
            == "OPPOSITE_PAPER_ENTRY"
            for row in paper_comparisons
        ),
        "paper_only": sum(
            row["classification"]
            == "PAPER_ONLY"
            for row in paper_comparisons
        ),
        "missed_shadow": len(
            unmatched_shadow
        ),
        "paper_only_against_shadow_territory": sum(
            row["classification"]
            == "PAPER_ONLY"
            and row["alignment"]
            in (
                "AGAINST_TERRITORY",
                "AGAINST_RELEASE",
            )
            for row in paper_comparisons
        ),
        "average_tool_rack_lead_seconds": (
            sum(led_delays)
            / len(led_delays)
            if led_delays
            else None
        ),
        "average_paper_price_minus_tool_rack_price_when_tool_rack_led": (
            sum(led_deltas)
            / len(led_deltas)
            if led_deltas
            else None
        ),
        # Backward-compatible aliases now explicitly refer only to rows where
        # Tool Rack existed first.
        "average_same_side_delay_seconds": (
            sum(led_delays)
            / len(led_delays)
            if led_delays
            else None
        ),
        "average_same_side_price_delta": (
            sum(led_deltas)
            / len(led_deltas)
            if led_deltas
            else None
        ),
    }

    return {
        "schema": (
            "TACHYOS_TOOL_RACK_SHADOW_VS_PAPER_V3"
        ),
        "summary": summary,
        "paper_comparisons": paper_comparisons,
        "matches": [
            row
            for row in paper_comparisons
            if row["classification"]
            != "PAPER_ONLY"
        ],
        "paper_only": [
            row
            for row in paper_comparisons
            if row["classification"]
            == "PAPER_ONLY"
        ],
        "unmatched_shadow_opportunities": (
            unmatched_shadow
        ),
    }

def markdown_report(
    report: dict[str, Any],
) -> str:
    s = report["summary"]
    lines = [
        "# Tool Rack Shadow vs Legacy PAPER",
        "",
        (
            "- Raw actionable event observations: "
            f"**{s['shadow_actionable_events']}**"
        ),
        (
            "- Unique physical shadow opportunities: "
            f"**{s['shadow_unique_opportunities']}**"
        ),
        f"- PAPER entries: **{s['paper_entries']}**",
        (
            "- Tool Rack led same-side PAPER entry: "
            f"**{s['tool_rack_led_same_side']}**"
        ),
        (
            "- Tool Rack followed PAPER on same side: "
            f"**{s['tool_rack_followed_same_side']}**"
        ),
        f"- Same-side agreement total: **{s['matched_same_side']}**",
        (
            "- PAPER entry opposite nearby Tool Rack opportunity: "
            f"**{s['opposite_paper_entry']}**"
        ),
        f"- PAPER-only entries: **{s['paper_only']}**",
        (
            "- Unmatched Tool Rack opportunities: "
            f"**{s['missed_shadow']}**"
        ),
        (
            "- PAPER-only entries against Tool Rack Rail/release: "
            f"**{s['paper_only_against_shadow_territory']}**"
        ),
        "",
    ]

    if (
        s["average_same_side_delay_seconds"]
        is not None
    ):
        lines.append(
            "- Average PAPER time minus matched "
            "Tool Rack opportunity time: "
            f"**{s['average_same_side_delay_seconds']:+.1f}s**"
        )

    if (
        s["average_same_side_price_delta"]
        is not None
    ):
        lines.append(
            "- Average PAPER ask minus matched "
            "Tool Rack observed ask: "
            f"**{s['average_same_side_price_delta']:+.3f}**"
        )

    lines.extend(
        [
            "",
            (
                "The comparison uses the full "
                "tool_rack_events.jsonl journal, matches only "
                "within the same Kalshi ticker, and counts each "
                "Tool Rack opportunity ID once."
            ),
            (
                "This report is forensic/read-only. It does not "
                "authorize or simulate a Tool Rack fill."
            ),
            "",
        ]
    )
    return "\n".join(lines)
