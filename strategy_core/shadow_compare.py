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
            if (
                ts is None
                or side not in ("YES", "NO")
            ):
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


def _shadow_intents(
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


def compare_shadow_to_paper(
    timeline: dict[str, Any],
    paper_entries: list[PaperEntry],
    *,
    before_seconds: float = 15.0,
    after_seconds: float = 90.0,
) -> dict[str, Any]:
    shadow = _shadow_intents(timeline)
    used_paper: set[int] = set()
    matches: list[dict[str, Any]] = []

    for event in shadow:
        ts = float(event["ts"])
        side = str(event["accepted_side"])
        candidates = [
            entry
            for entry in paper_entries
            if entry.index not in used_paper
            and ts - before_seconds
            <= entry.ts
            <= ts + after_seconds
        ]
        same = [
            entry
            for entry in candidates
            if entry.side == side
        ]
        pool = same if same else candidates
        chosen = (
            min(
                pool,
                key=lambda entry: abs(
                    entry.ts - ts
                ),
            )
            if pool
            else None
        )

        if chosen is None:
            classification = "MISSED_SHADOW"
        elif chosen.side == side:
            classification = "MATCHED_SAME_SIDE"
            used_paper.add(chosen.index)
        else:
            classification = "OPPOSITE_PAPER_ENTRY"
            used_paper.add(chosen.index)

        shadow_ask = _number(
            event.get("observed_ask")
        )
        price_delta = (
            chosen.price - shadow_ask
            if (
                chosen is not None
                and chosen.price is not None
                and shadow_ask is not None
            )
            else None
        )

        matches.append(
            {
                "classification": classification,
                "shadow": {
                    "seq": event.get("seq"),
                    "ts": ts,
                    "ticker": event.get("ticker"),
                    "territory": event.get("territory"),
                    "tool": event.get("tool"),
                    "action": event.get("action"),
                    "side": side,
                    "observed_ask": shadow_ask,
                    "max_price": _number(
                        event.get("max_price")
                    ),
                    "opportunity_id": (
                        event.get(
                            "opportunity_id"
                        )
                    ),
                },
                "paper": (
                    chosen.as_dict()
                    if chosen is not None
                    else None
                ),
                "delay_seconds": (
                    chosen.ts - ts
                    if chosen is not None
                    else None
                ),
                "price_delta": price_delta,
            }
        )

    paper_only: list[dict[str, Any]] = []
    for entry in paper_entries:
        if entry.index in used_paper:
            continue
        territory = _territory_at(
            timeline,
            entry.ts,
        )
        paper_only.append(
            {
                **entry.as_dict(),
                "classification": "PAPER_ONLY",
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
                "alignment": _territory_alignment(
                    territory,
                    entry.side,
                ),
            }
        )

    summary = {
        "shadow_actionable": len(shadow),
        "matched_same_side": sum(
            row["classification"]
            == "MATCHED_SAME_SIDE"
            for row in matches
        ),
        "opposite_paper_entry": sum(
            row["classification"]
            == "OPPOSITE_PAPER_ENTRY"
            for row in matches
        ),
        "missed_shadow": sum(
            row["classification"]
            == "MISSED_SHADOW"
            for row in matches
        ),
        "paper_entries": len(paper_entries),
        "paper_only": len(paper_only),
        "paper_only_against_shadow_territory": sum(
            row["alignment"]
            in (
                "AGAINST_TERRITORY",
                "AGAINST_RELEASE",
            )
            for row in paper_only
        ),
    }

    same_delays = [
        row["delay_seconds"]
        for row in matches
        if (
            row["classification"]
            == "MATCHED_SAME_SIDE"
            and row["delay_seconds"]
            is not None
        )
    ]
    same_deltas = [
        row["price_delta"]
        for row in matches
        if (
            row["classification"]
            == "MATCHED_SAME_SIDE"
            and row["price_delta"]
            is not None
        )
    ]
    summary["average_same_side_delay_seconds"] = (
        sum(same_delays) / len(same_delays)
        if same_delays
        else None
    )
    summary["average_same_side_price_delta"] = (
        sum(same_deltas) / len(same_deltas)
        if same_deltas
        else None
    )

    return {
        "schema": (
            "TACHYOS_TOOL_RACK_SHADOW_VS_PAPER_V1"
        ),
        "summary": summary,
        "matches": matches,
        "paper_only": paper_only,
    }


def markdown_report(
    report: dict[str, Any],
) -> str:
    s = report["summary"]
    lines = [
        "# Tool Rack Shadow vs Legacy PAPER",
        "",
        f"- Shadow actionable intents: **{s['shadow_actionable']}**",
        f"- Matched same side: **{s['matched_same_side']}**",
        f"- Opposite PAPER entry near shadow intent: **{s['opposite_paper_entry']}**",
        f"- Missed shadow intents: **{s['missed_shadow']}**",
        f"- PAPER entries with no matched shadow intent: **{s['paper_only']}**",
        f"- PAPER-only entries against Tool Rack territory/release: **{s['paper_only_against_shadow_territory']}**",
        "",
    ]
    if s["average_same_side_delay_seconds"] is not None:
        lines.append(
            "- Average same-side PAPER delay: "
            f"**{s['average_same_side_delay_seconds']:.1f}s**"
        )
    if s["average_same_side_price_delta"] is not None:
        lines.append(
            "- Average actual entry ask minus shadow ask: "
            f"**{s['average_same_side_price_delta']:+.3f}**"
        )
    lines.extend(
        [
            "",
            "This report is forensic/read-only. It does not authorize or simulate a Tool Rack fill.",
            "",
        ]
    )
    return "\n".join(lines)
