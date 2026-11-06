"""Detached, read-only Nautilus presentation of the standalone PAPER engine.

This adapter observes dictionaries already published by the one engine. It does
not read legacy files, call a tool, decide, trade, or certify venue fills. All
history here is bounded presentation history; the engine journal owns truth.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Mapping, Sequence
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import json
import math
from pathlib import Path
import time
from typing import Any

from strategy_core.looking_glass import build_looking_glass

VERSION = "TOOL_RACK_NAUTILUS_TV_V12_PATTERN_PATHS"


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def mapping(value: Any) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def position_role(record: Mapping) -> str | None:
    """Show explicit engine roles; historical tool names are not role proof."""
    role = record.get("position_role") or mapping(record.get("entry_metadata")).get("position_role")
    return role if role in ("PRIMARY", "TACTICAL") else None


def _display_text(value: Any) -> str | None:
    return value[:1000] if isinstance(value, str) and value else None


def _display_data(value: Any, depth: int = 0) -> Any:
    """Bounded JSON-safe evidence copy; never derive a decision from it."""
    if depth > 6:
        return None
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _display_text(value)
    if isinstance(value, Mapping):
        return {key: _display_data(item, depth + 1) for key, item in list(value.items())[:64]
                if isinstance(key, str)}
    if isinstance(value, (list, tuple)):
        return [_display_data(item, depth + 1) for item in value[:32]]
    return number(value)


def tactical_economics_view(value: Any) -> dict:
    """Publish recorded engine economics, without completing missing forecasts."""
    raw = mapping(value)
    return {"available": bool(raw),
            **{key: number(raw.get(key)) for key in (
                "minimum_gross_roi", "entry_ask", "required_exit_bid", "estimated_exit_bid",
                "gross_roi", "net_after_fees", "quantity", "best_ask")},
            "reason": _display_text(raw.get("reason")), "status": _display_text(raw.get("status")),
            "estimate_method": _display_text(raw.get("estimate_method")),
            "uncertainty": _display_data(raw.get("uncertainty")),
            "future_exit_depth_proven": raw.get("future_exit_depth_proven")
                if isinstance(raw.get("future_exit_depth_proven"), bool) else None}


def position_mission_view(value: Any) -> dict:
    raw = mapping(value)
    destination = mapping(raw.get("destination"))
    purpose = raw.get("purpose")
    return {"available": bool(raw),
            "purpose": purpose if purpose in ("MAIN_CONTRACT", "ARC_RETURN", "TACTICAL_RETURN") else None,
            "parent_leg_id": _display_text(raw.get("parent_leg_id")),
            "swing_id": _display_text(raw.get("swing_id")),
            "target_kind": _display_text(raw.get("target_kind")),
            "destination": {"kind": _display_text(destination.get("kind")),
                            "btc": number(destination.get("btc")),
                            "tolerance": number(destination.get("tolerance"))},
            "source_ms": number(raw.get("source_ms")),
            "collection_policy": _display_text(raw.get("collection_policy")),
            "continuity_generation": number(raw.get("continuity_generation"))}


def collection_review_view(value: Any) -> dict:
    raw = mapping(value)
    return {"available": bool(raw), "source_ms": number(raw.get("source_ms")),
            "scope_id": _display_text(raw.get("scope_id")),
            "collection_policy": _display_text(raw.get("collection_policy")),
            "weakness_count": number(raw.get("weakness_count")),
            "weakness_required_count": number(raw.get("weakness_required_count")),
            "weakness_proof_valid": raw.get("weakness_proof_valid") is True,
            "collection_qualified": raw.get("collection_qualified") is True,
            "collection_authority": _display_text(raw.get("collection_authority")),
            "reason": _display_text(raw.get("reason")),
            "display_only": True}


def candidate_review_view(value: Any) -> list[dict]:
    rows = mapping(value).get("entries") if isinstance(value, Mapping) else value
    if not isinstance(rows, (list, tuple)):
        return []
    return [{"side": raw.get("side") if raw.get("side") in ("YES", "NO") else None,
             "purpose": raw.get("purpose") if raw.get("purpose") in ("MAIN_CONTRACT", "ARC_RETURN", "TACTICAL_RETURN") else None,
             "decision": _display_text(raw.get("decision")), "reason": _display_text(raw.get("reason")),
             "economics": tactical_economics_view(raw.get("economics"))}
            for item in rows[:32] if (raw := mapping(item))]


def mission_context_view(value: Any, *, fresh: bool, physical_current: bool,
                         now: float, updated: float | None) -> dict:
    raw = mapping(value)
    parent, contract = mapping(raw.get("parent")), mapping(raw.get("contract"))
    source_ms = number(raw.get("source_ms"))
    source_ts = source_ms / 1000 if source_ms is not None else None
    current = bool(fresh and physical_current and raw.get("current") is True
                   and source_ts is not None and -2 <= now - source_ts <= 3)
    prior = contract.get("prior_contracts")
    count = len(prior) if isinstance(prior, (list, tuple)) else number(prior)
    count = int(count) if count is not None and count >= 0 and count == int(count) else None
    return {"available": bool(raw), "version": _display_text(raw.get("version")),
            "reported_current": raw.get("current") if isinstance(raw.get("current"), bool) else None,
            "current": current, "display_status": "CURRENT" if current else "LAST_RECORDED" if raw else "UNAVAILABLE",
            "source_ms": source_ms, "continuity_generation": number(raw.get("continuity_generation")),
            "valid_until": min(source_ts + 3, updated + 5) if current and updated is not None else None,
            "basis": "ENGINE_REPORTED_DECISION_CONTEXT", "display_only": True,
            "parent": {"id": _display_text(parent.get("id")),
                       "side": parent.get("side") if parent.get("side") in ("YES", "NO") else None,
                       "direction": parent.get("direction") if parent.get("direction") in ("UP", "DOWN") else None,
                       "terminal": _display_data(parent.get("terminal")),
                       "weakness": _display_data(parent.get("weakness")),
                       "successor": _display_data(parent.get("successor"))},
            "contract": {"thesis_side": contract.get("thesis_side") if contract.get("thesis_side") in ("YES", "NO") else None,
                         "thesis_status": contract.get("thesis_side") if contract.get("thesis_side") in
                             ("YES", "NO", "MIXED", "UNKNOWN") else None,
                         "reason": _display_text(contract.get("reason")),
                         "history_status": _display_text(contract.get("history_status")),
                         "remaining_seconds": number(contract.get("remaining_seconds")),
                         "prior_contracts": _display_data(prior), "prior_contract_count": count},
            "candidates": candidate_review_view(raw.get("candidates"))}


def contract_exposure(positions: list[dict]) -> list[dict]:
    """Aggregate exact-contract inventory without netting different expiries.

    Paired YES/NO quantities and net contracts describe exposure, not P&L or
    independent venue positions. Cash and fees remain the committed ledger's.
    """
    grouped: dict[str, dict] = {}
    for position in positions:
        ticker = position.get("ticker")
        if not isinstance(ticker, str) or not ticker:
            continue
        row = grouped.setdefault(ticker, {"ticker": ticker, "yes_qty": 0, "no_qty": 0,
            "position_ids": [], "primary_positions": 0, "tactical_positions": 0,
            "inventory_verified": True})
        row["position_ids"].append(str(position.get("position_id")))
        role = position_role(position)
        if role:
            row[role.lower() + "_positions"] += 1
        qty = number(position.get("remaining_qty", position.get("qty")))
        side = position.get("side")
        if qty is None or qty < 0 or qty != int(qty) or side not in ("YES", "NO"):
            row["inventory_verified"] = False
            continue
        row[side.lower() + "_qty"] += int(qty)
        row["inventory_verified"] = row["inventory_verified"] and position.get("inventory_verified") is True
    for row in grouped.values():
        verified = row["inventory_verified"]
        net = row["yes_qty"] - row["no_qty"]
        row.update(net_yes_qty=net if verified else None,
                   net_side=("YES" if net > 0 else "NO" if net < 0 else "BALANCED") if verified else None,
                   net_qty=abs(net) if verified else None,
                   paired_qty=min(row["yes_qty"], row["no_qty"]) if verified else None,
                   basis="EXACT_CONTRACT_STRATEGY_INVENTORY; NET_CONTRACTS_ARE_NOT_PROFIT")
    return list(grouped.values())


def looking_glass_pattern_context(status: Mapping, market: Mapping, *, current: bool) -> dict:
    """Copy current engine pattern evidence without running any strategy helper."""
    rack, physical = mapping(status.get("rack")), mapping(status.get("physical"))
    mission = mapping(status.get("mission_context"))
    parent = mapping(mission.get("parent"))
    candidate = mapping(mapping(mission.get("candidates")).get(parent.get("side")))
    cross = mapping(physical.get("ema9_ema30_cross_context"))
    gap = mapping(cross.get("gap_lifecycle"))
    parent_source, gap_source = number(mission.get("source_ms")), number(cross.get("source_ms"))
    return {"ticker": market.get("ticker"), "source_ts": market.get("time"),
            "observed_at": number(status.get("updated_at")), "physical_current": current,
            "continuity_generation": number(physical.get("geometry_continuity_generation")),
            "current_direction": mapping(physical.get("current_geometry")).get("current_native_direction"),
            **{key: rack.get(key) for key in ("owned_territory", "owned_side", "territory_id",
                "handoff_confirmed", "release_in_progress", "release_candidate_side")},
            "mission": {"current": mission.get("current") is True,
                "source_ts": parent_source / 1000 if parent_source is not None else None,
                "parent_id": parent.get("id"), "side": parent.get("side"),
                "status": parent.get("status"), "supported": parent.get("supported"),
                "invalidated": parent.get("invalidated"),
                "terminal": mapping(parent.get("terminal")).get("qualified"),
                "current_progress_supported": candidate.get("current_progress_supported")},
            "gap": {"source_ts": gap_source / 1000 if gap_source is not None else None,
                "stage": gap.get("stage"), "side": gap.get("current_side"),
                "continued_on_latest_cross_side": gap.get("continued_on_latest_cross_side")}}


def label(value: Any, default: str = "Unavailable") -> str:
    return str(value).replace("_", " ") if value is not None and value != "" else default


def best(book: Mapping, side: str) -> float | None:
    levels = book.get("yes_bids" if side == "YES" else "no_bids") or ()
    value = number(mapping(levels[0]).get("price")) if levels else None
    return value if value is not None and 0 < value < 1 else None


def full_lot_bid(book: Mapping, side: str, quantity: Any, used: Mapping | None = None) -> float | None:
    """Indicative conservative full-lot sell VWAP; insufficient depth is unknown.

    This display calculation cannot execute. Previously consumed PAPER sell
    levels from the same exact native quote are subtracted before making a mark.
    """
    qty = number(quantity)
    if qty is None or qty <= 0 or qty != int(qty):
        return None
    remaining, amount, prior = int(qty), Decimal(0), Decimal(1)
    try:
        for raw in book.get("yes_bids" if side == "YES" else "no_bids") or ():
            raw = mapping(raw)
            price, depth = Decimal(str(raw.get("price"))), Decimal(str(raw.get("quantity")))
            if not price.is_finite() or not depth.is_finite() or not 0 < price < prior or depth <= 0:
                return None
            prior = price
            consumed = (used or {}).get(price, 0)
            count = min(remaining, max(0, int(depth.to_integral_value(rounding=ROUND_FLOOR)) - consumed))
            remaining -= count
            amount += count * price
            if remaining == 0:
                return float((amount / int(qty)).quantize(Decimal("0.0001"), rounding=ROUND_FLOOR))
    except (InvalidOperation, ValueError, TypeError, OverflowError):
        return None
    return None


def quote_view(book: Mapping, now: float, *, running: bool) -> dict:
    observed, exchange, close = (number(book.get(k)) for k in ("observed_ts", "exchange_ts", "close_ts"))
    receive_fresh = observed is not None and 0 <= now - observed <= 3
    exchange_fresh = exchange is None or -2 <= now - exchange <= 15
    proven = book.get("current") is True and bool(book.get("quote_id")) and bool(book.get("ticker"))
    if exchange is None:
        provenance = mapping(book.get("provenance"))
        proven = proven and book.get("source") == "WS_SEQUENCE_CHECKED_BOOK" and all(
            provenance.get(k) is True for k in ("sequence_checked", "snapshot_verified", "monotonic_receive_fresh"))
    usable = bool(running and proven and receive_fresh and exchange_fresh and close is not None and now < close)
    deadline = min(observed + 3, close, exchange + 15 if exchange is not None else math.inf) if usable else None
    yes, no = best(book, "YES"), best(book, "NO")
    result = {"ticker": book.get("ticker"), "quote_id": book.get("quote_id"),
              "source": book.get("source"), "observed_wall": observed, "time": observed,
              "exchange_ts": exchange, "exchange_age_sec": now - exchange if exchange is not None else None,
              "valid_until": deadline, "fresh": False,
              "reason": "CURRENT_NATIVE_BOOK" if usable else "NATIVE_BOOK_UNAVAILABLE_OR_STALE"}
    result.update(yes_bid=yes if usable and book.get("yes_sell_allowed") is True else None,
                  no_bid=no if usable and book.get("no_sell_allowed") is True else None,
                  yes_ask=1 - no if usable and book.get("entry_allowed") is True and no is not None else None,
                  no_ask=1 - yes if usable and book.get("entry_allowed") is True and yes is not None else None)
    result["fresh"] = any(result[k] is not None for k in ("yes_bid", "no_bid", "yes_ask", "no_ask"))
    if result["fresh"] and book.get("entry_allowed") is not True:
        result["reason"] = "CURRENT_HELD_SIDE_BID_ENTRIES_UNAVAILABLE"
    return result


class NautilusProjection:
    """`observe(status)` every cycle, `project(status, rows, chart_data)` at UI cadence.

    Repeated observations are idempotent. `project` returns a completely detached
    JSON-safe object; HTTP workers never receive mutable engine or adapter state.
    """

    def __init__(self) -> None:
        self._run_id = None
        self._feed = deque(maxlen=1000)
        self._commands = deque(maxlen=1500)
        self._timeline = deque(maxlen=160)
        self._quotes = deque(maxlen=40000)
        self._targets: OrderedDict[str, dict] = OrderedDict()
        self._trades: OrderedDict[str, dict] = OrderedDict()
        self._seen_events: OrderedDict[str, tuple] = OrderedDict()
        self._sell_usage: OrderedDict[tuple, dict] = OrderedDict()
        self._marks: dict[str, dict] = {}
        self._floor_keys: dict[str, tuple] = {}
        self._custody_keys: dict[str, str] = {}
        self._decision_keys: dict[str, tuple] = {}
        self._intent_keys: dict[str, tuple] = {}
        self._protection: dict[str, dict] = {}
        self._last_quote: dict[str, dict] = {}
        self._last_quote_key = None
        self._last_source_key = None
        self._last_owner_key = None
        self._last_state = None
        self._last_heartbeat_at: float | None = None
        self._feed_serial = 0
        self._issues: deque[str] = deque(maxlen=30)
        self._clock_sample: tuple[float, float] | None = None
        self._history_truncated = False
        # First issued pattern trace per exact contract/context. These observer
        # samples are immutable, bounded and process-local, never trade input.
        self._glass_issued: OrderedDict[tuple, dict] = OrderedDict()
        self._glass_last_source: float | None = None
        # Observer configuration never participates in the engine's readiness
        # or trading configuration. A malformed file disables this view only.
        self._looking_glass_config = None
        self._looking_glass_config_error = None
        try:
            config = json.loads((Path(__file__).with_name("config") / "looking_glass.json").read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                raise ValueError("LOOKING_GLASS_CONFIG_MUST_BE_AN_OBJECT")
            self._looking_glass_config = config
        except Exception as exc:
            self._looking_glass_config_error = type(exc).__name__

    def _looking_glass_view(self, market: Mapping, bars: Sequence, emas: Sequence,
                            targets: Sequence, quote: Mapping, now: float,
                            pattern_context: Mapping | None = None) -> dict:
        """Keep advisory failures local so the ledger/feed still publish."""
        try:
            if self._looking_glass_config_error:
                raise ValueError("LOOKING_GLASS_CONFIG_UNAVAILABLE")
            view = build_looking_glass(market, bars, emas, targets, quote,
                                      tuple(self._quotes), now_ts=now,
                                      pattern_context=pattern_context,
                                      config=self._looking_glass_config)
            if (not isinstance(view, dict) or view.get("execution_authority") is not False
                    or view.get("can_veto") is not False or view.get("can_order") is not False
                    or view.get("probabilities_calibrated") is not False):
                raise ValueError("LOOKING_GLASS_INVALID_OBSERVER_RESULT")
            # Reject nonfinite observer output before it can interrupt the
            # otherwise valid immutable dashboard publication.
            json.dumps(view, allow_nan=False)
            self._remember_looking_glass(view, now)
            return view
        except Exception as exc:
            return {"version": "LOOKING_GLASS_V1", "status": "UNAVAILABLE",
                    "reason": "LOOKING_GLASS_CONFIGURATION_UNAVAILABLE" if self._looking_glass_config_error
                              else "LOOKING_GLASS_OBSERVER_ERROR",
                    "error_type": self._looking_glass_config_error or type(exc).__name__,
                    "source_ts": market.get("time"), "valid_until": None,
                    "ticker": market.get("ticker"), "close_ts": market.get("close_ts"),
                    "execution_authority": False, "can_veto": False, "can_order": False,
                    "probabilities_calibrated": False,
                    "paths": [], "reference_window": {}, "observations": {},
                    "thesis": {"side": "UNKNOWN", "reason": "ADVISORY_UNAVAILABLE",
                               "settlement_prediction": False},
                    "timing": {}, "swing_review": {"status": "NOT_ASSESSED", "sides": {}}}

    def _remember_looking_glass(self, view: dict, now: float) -> None:
        """Freeze the first actually issued trace; later anchors never rewrite it."""
        active = mapping(view.get("active_pattern"))
        source, close = number(view.get("source_ts")), number(view.get("close_ts"))
        generation = number(active.get("continuity_generation"))
        path = next((row for row in view.get("paths") or ()
                     if isinstance(row, Mapping) and row.get("id") == active.get("path_id")), None)
        forward = source is not None and (self._glass_last_source is None or source >= self._glass_last_source)
        if (view.get("status") in ("READY", "PARTIAL") and active.get("status") == "READY"
                and active.get("execution_authority") is False and path and forward
                and generation is not None and generation >= 0 and generation == int(generation)
                and 0 <= now - source <= 3 and close is not None and now < close):
            key = (view.get("ticker"), close, active.get("key"), generation)
            if key not in self._glass_issued:
                self._glass_issued[key] = deepcopy({"id": f"{self._run_id}:{source}:{active.get('key')}",
                    "run_id": self._run_id, "ticker": view.get("ticker"), "close_ts": close,
                    "source_ts": source, "issued_at_ts": now, "pattern_key": active.get("key"),
                    "continuity_generation": generation, "label": active.get("label"),
                    "anchor": path["points"][0], "path": path,
                    "conditional": True, "execution_authority": False, "frozen": True})
                while len(self._glass_issued) > 16:
                    self._glass_issued.popitem(last=False)
        if source is not None and forward:
            self._glass_last_source = source
        view["research"] = {"basis": "FIRST_ISSUED_PATTERN_PATH_PER_CONTRACT",
            "process_local": True, "persisted": False, "repainted": False, "maximum_samples": 16,
            "as_issued": [deepcopy(row) for row in self._glass_issued.values()
                if source is not None and row["source_ts"] <= source and row["issued_at_ts"] <= now],
            "note": "Fixed when first published by this observer process; retained across browser refresh, cleared on engine restart. Not a recorded trade forecast."}

    def _emit(self, when: float | None, kind: str, text: str, category: str = "info") -> dict:
        self._feed_serial += 1
        row = {"id": f"{self._run_id}:{self._feed_serial}", "time": when,
               "kind": kind, "category": category, "text": text[:6000], "source": "TOOL_RACK_PAPER"}
        self._feed.append(row)
        return row

    def _issue(self, text: str) -> None:
        if text not in self._issues:
            self._issues.append(text)

    @staticmethod
    def _trade_key(event: Mapping) -> str:
        return str(event.get("ticker") or "") + ":" + str(event.get("position_id") or event.get("trade_id") or "")

    def _event(self, event: Mapping) -> None:
        kind = event.get("event")
        if kind not in ("ENTRY", "PARTIAL_EXIT", "EXIT", "SETTLEMENT"):
            return
        identity = str(event.get("command_id") or "")
        key = self._trade_key(event)
        stamp, qty, price = (number(event.get(k)) for k in ("timestamp", "qty", "price"))
        fingerprint = (kind, key, stamp, qty, price, event.get("gross_pnl"), event.get("net_pnl"), event.get("fees"))
        if not identity or not event.get("ticker") or not event.get("position_id") or stamp is None:
            self._issue("Committed event identity is incomplete; no trade was invented from it.")
            return
        if identity in self._seen_events:
            if self._seen_events[identity] != fingerprint:
                self._issue("A committed event identity changed; displayed trade history requires journal review.")
            return
        self._seen_events[identity] = fingerprint
        while len(self._seen_events) > 10000:
            self._seen_events.popitem(last=False)
        if qty is None or qty <= 0 or qty != int(qty) or price is None or not 0 <= price <= 1:
            self._issue("Committed event has invalid display quantity or price; no fill was reconstructed.")
            return
        fee, gross, net = (number(event.get(k)) for k in ("fees", "gross_pnl", "net_pnl"))
        if any(v is None for v in (fee, gross, net)):
            self._issue("Committed event accounting fields are incomplete; trade accounting was withheld.")
            return
        if kind in ("PARTIAL_EXIT", "EXIT") and event.get("quote_id"):
            usage_key = (event.get("ticker"), event.get("quote_id"), event.get("side"))
            used = self._sell_usage.setdefault(usage_key, {})
            try:
                for level in mapping(event.get("depth_sweep")).get("levels") or ():
                    level_price, level_qty = Decimal(str(level[0])), int(level[1])
                    used[level_price] = used.get(level_price, 0) + level_qty
            except (InvalidOperation, ValueError, TypeError, IndexError):
                self._issue("Committed exit depth is incomplete; current lot marks require a new native quote.")
                used["invalid"] = True
            while len(self._sell_usage) > 1000:
                self._sell_usage.popitem(last=False)
        if kind == "ENTRY":
            if key in self._trades:
                self._issue("Duplicate entry position identity; no second trade was invented.")
                return
            cost = number(event.get("cost"))
            net_return_basis = (number(cost + fee)
                                if cost is not None and cost > 0 and fee >= 0 else None)
            self._trades[key] = {
                "key": key, "trade_id": str(event["position_id"]), "position_id": str(event["position_id"]),
                "ticker": event["ticker"], "side": event.get("side"), "tool": event.get("tool"),
                "role": event.get("tool"), "intent": event.get("opportunity_id"),
                "position_role": position_role(event),
                "mission": position_mission_view(mapping(event.get("entry_metadata")).get("mission")),
                "tactical_economics": tactical_economics_view(mapping(event.get("entry_metadata")).get("tactical_economics")),
                "territory_id": event.get("territory_id"), "entry_ts": stamp, "entry_ask": price,
                "qty": int(qty), "original_qty": int(qty), "remaining_qty": int(qty), "cost": cost,
                "entry_reason": event.get("reason"), "entry_fee": fee, "exit_fee": 0.0,
                "fees_paid": fee, "exit_ts": None, "exit_bid": None, "exit_reason": None, "exit_type": None,
                "partial_exits": 0, "partial_realized": 0.0, "pnl": None, "net_pnl": None, "roi": None,
                "net_roi": None, "net_return_basis": net_return_basis,
                "mfe": None, "mae": None, "evidence": [], "inventory_verified": True,
                "_exit_proceeds": 0.0, "_exit_qty": 0, "_realized_net": 0.0,
            }
        elif key not in self._trades:
            self._issue("An exit is present without its entry in this viewer's observed window; no entry was invented.")
        else:
            trade = self._trades[key]
            after = number(event.get("position_qty_after"))
            valid = (trade["exit_ts"] is None and stamp >= trade["entry_ts"] and qty <= trade["remaining_qty"]
                     and after == trade["remaining_qty"] - qty)
            if not valid or (kind in ("EXIT", "SETTLEMENT") and after != 0) or (kind == "PARTIAL_EXIT" and after <= 0):
                self._issue("Exit quantity or ordering disagrees with the observed entry; trade update withheld.")
                return
            trade["remaining_qty"] = int(after)
            trade["partial_realized"] += gross
            trade["_realized_net"] += net
            trade["exit_fee"] += fee
            trade["fees_paid"] += fee
            trade["_exit_proceeds"] += qty * price
            trade["_exit_qty"] += int(qty)
            trade["pnl"], trade["net_pnl"] = trade["partial_realized"], trade["_realized_net"]
            trade["roi"] = 100 * trade["pnl"] / trade["cost"] if trade["cost"] else None
            trade["exit_reason"], trade["exit_type"] = event.get("reason"), kind
            if kind == "PARTIAL_EXIT":
                trade["partial_exits"] += 1
            else:
                trade["exit_ts"] = stamp
                trade["exit_bid"] = trade["_exit_proceeds"] / trade["_exit_qty"]
                # Realized return for the original whole lot, including entry
                # and exit fees. Open/partially exited positions remain unknown.
                basis = trade["net_return_basis"]
                trade["net_roi"] = (100 * trade["net_pnl"] / basis
                                    if basis is not None and basis > 0 else None)
        command = {"time": stamp, "event": kind, "side": event.get("side"), "reason": event.get("reason"),
                   "key": key, "position_id": event.get("position_id"), "command_id": identity,
                   "quote_id": event.get("quote_id"), "tool": event.get("tool"),
                   "position_role": position_role(event), "committed": True}
        self._commands.append(command)
        if key in self._trades:
            self._trades[key]["evidence"] = (self._trades[key]["evidence"] + [command])[-30:]
        pnl_text = f" · gross ${gross:+.2f} · net ${net:+.2f}" if kind != "ENTRY" else ""
        role_text = f" · {position_role(event)}" if position_role(event) else ""
        self._emit(stamp, kind, f"PAPER {kind}{role_text} · {event.get('tool')} {event.get('side')} · {event.get('ticker')} "
                   f"· #{event.get('position_id')} · {int(qty)} contracts @ {price:.4f} "
                   f"· fee ${fee:.2f}{pnl_text} · {label(event.get('reason'))}", "trade")
        while len(self._trades) > 2000:
            expired = next((k for k, v in self._trades.items() if v["exit_ts"] is not None), None)
            if expired is None:
                break
            del self._trades[expired]
            self._history_truncated = True

    def observe(self, status: Mapping[str, Any]) -> None:
        """Capture meaningful transitions before the next browser publication."""
        if not isinstance(status, Mapping):
            return
        run_id = status.get("run_id")
        if self._run_id is not None and run_id != self._run_id:
            self.__init__()
        self._run_id = run_id
        now = number(status.get("updated_at"))
        if now is None:
            return
        market = mapping(status.get("market"))
        target, close = number(market.get("target")), number(market.get("close_ts"))
        if (target is not None and target > 0 and close is not None and market.get("ticker")
                and market.get("target_source") == "KALSHI_MARKET_FLOOR_STRIKE"):
            ticker = str(market["ticker"])
            recorded = self._targets.get(ticker)
            candidate = {"ticker": ticker, "target": target, "start_ts": close-900, "close_ts": close,
                         "source": market["target_source"], "observed_at": now}
            if recorded is None:
                self._targets[ticker] = candidate
                while len(self._targets) > 256:
                    self._targets.popitem(last=False)
            elif recorded["target"] != target or recorded["close_ts"] != close:
                self._issue("Venue target metadata changed for an already observed contract; its prior target line was retained for review.")
        source, physical, rack = (mapping(status.get(k)) for k in ("source_status", "physical", "rack"))
        state = status.get("state")
        if state != self._last_state:
            detail = " · new entries closed; held strategy and protection continue" if state == "DRAINING" else ""
            self._emit(now, "SESSION", f"Tool Rack PAPER {label(state)} · one Commander · {run_id}{detail}")
            self._last_state = state
        if self._last_heartbeat_at is None:
            self._last_heartbeat_at = now
        elif state in ("RUNNING", "DRAINING", "STOPPING") and now - self._last_heartbeat_at >= 30:
            entry = next((mapping(row).get("decision") for row in status.get("decisions") or ()
                          if mapping(row).get("scope") == "ENTRY"), {})
            entry = mapping(entry)
            observed_book = mapping(status.get("book"))
            quote_stamp = number(observed_book.get("observed_ts"))
            btc_stamp = number(mapping(status.get("latest_geometry")).get("epoch_ms"))
            quote_age = f"{now-quote_stamp:.1f}s" if quote_stamp is not None else "unavailable"
            btc_age = f"{now-btc_stamp/1000:.1f}s" if btc_stamp is not None else "unavailable"
            action = entry.get('action') or 'WAIT'
            commander_note = (f"Commander {action} · {label(entry.get('reason'))}"
                              if action != 'WAIT' else "Commander idle · awaiting positive briefing")
            self._emit(now, "HEARTBEAT", f"Engine heartbeat · observation {status.get('sequence', 'unknown')} "
                f"· {rack.get('active_tool') or 'SOURCE WARMUP'} · {commander_note} "
                f"· BTC source age {btc_age} · native quote age {quote_age}", "info")
            self._last_heartbeat_at = now
        source_key = (source.get("btc_current"), source.get("book_current"), source.get("entry_quote_available"),
                      physical.get("physical_current"), status.get("awaiting_physical_reacquisition"),
                      source.get("source_error"), source.get("discovery_error"), source.get("rest_diagnostic_error"))
        if source_key != self._last_source_key:
            self._last_source_key = source_key
            btc = "current" if source.get("btc_current") is True else "warming/stale"
            native = "current" if source.get("book_current") is True else "unavailable/stale"
            geometry = "current" if physical.get("physical_current") is True else "warming/stale"
            detail = "; ".join(str(v) for v in source_key[5:] if v)
            self._emit(now, "SOURCE", f"Sources · BTC {btc} · native book {native} · physical {geometry}"
                + (" · new entries await physical reacquisition" if status.get("awaiting_physical_reacquisition") else "")
                + (" · " + detail if detail else ""),
                "warning" if any(v is not True for v in source_key[:2]) or detail else "info")
        owner_key = (rack.get("owned_territory"), rack.get("owned_side"), rack.get("territory_id"),
                     rack.get("active_tool"), tuple(rack.get("active_overlays") or ()),
                     rack.get("handoff_confirmed"), rack.get("release_transition_pending"), rack.get("ownership_reason"))
        if rack and owner_key != self._last_owner_key:
            self._last_owner_key = owner_key
            row = self._emit(now, "HANDOFF" if rack.get("handoff_confirmed") else "TERRITORY",
                f"{label(rack.get('owned_territory'))} · owner {rack.get('active_tool') or 'NONE'} "
                f"{rack.get('owned_side') or ''} · overlay {', '.join(rack.get('active_overlays') or ()) or 'NONE'} "
                f"· {label(rack.get('ownership_reason'))}", "watch")
            self._timeline.append({**row, "territory": rack.get("owned_territory"), "tool": rack.get("active_tool"),
                                   "side": rack.get("owned_side"), "handoff_confirmed": rack.get("handoff_confirmed") is True})
        if physical.get("physical_current") is True:
            for index, briefing in enumerate(rack.get("briefings") or ()):
                briefing = mapping(briefing)
                k = "BRIEFING:" + str(briefing.get("tool")) + ":" + str(index)
                sig = tuple(briefing.get(v) for v in ("tool", "state", "side", "opportunity_id", "max_price", "reason"))
                if self._intent_keys.get(k) != sig:
                    self._intent_keys[k] = sig
                    value = number(briefing.get("max_price"))
                    state_name = str(briefing.get("state") or "PREPARE").replace("_", " ")
                    price_note = f" · fish <= {value:.3f}" if value is not None and briefing.get("state") in ("FISH", "ENTRY_WINDOW") else ""
                    self._emit(now, "BRIEFING", f"{briefing.get('tool')} · {state_name} · "
                        f"{briefing.get('side') or ''}{price_note} · {label(briefing.get('reason'))}", "watch")
        for event in status.get("events") or ():
            if isinstance(event, Mapping):
                self._event(event)
        for row in status.get("decisions") or ():
            row = mapping(row)
            decision, receipt = mapping(row.get("decision")), mapping(row.get("receipt"))
            intent = mapping(decision.get("intent"))
            key = str(row.get("scope")) + ":" + str(row.get("position_id") or "")
            signature = (decision.get("action"), decision.get("reason"), intent.get("opportunity_id"),
                         intent.get("tool"), intent.get("side"), receipt.get("status"), receipt.get("reason"))
            if signature == self._decision_keys.get(key):
                continue
            self._decision_keys[key] = signature
            command = {"time": now, "event": decision.get("action"), "side": intent.get("side"),
                       "reason": decision.get("reason"), "scope": row.get("scope"),
                       "key": None, "position_id": row.get("position_id"), "tool": intent.get("tool"), "committed": False}
            if row.get("position_id") is not None:
                position = mapping(mapping(status.get("positions")).get(str(row["position_id"])))
                command["key"] = self._trade_key(position) if position else next(
                    (k for k, v in reversed(self._trades.items()) if v["position_id"] == str(row["position_id"])), None)
            self._commands.append(command)
            suffix = f" · executor {receipt.get('status')}: {label(receipt.get('reason'))}" if receipt else ""
            # Keep the General's feed quiet while idle. Strategy WAIT reasons live
            # in diagnostics/tool records; only actions and objective execution
            # safety interruptions reach the main Commander feed.
            action = decision.get("action")
            reason = str(decision.get("reason") or "")
            objective_wait = action == "WAIT" and reason.startswith((
                "OBJECTIVE_", "DIRECT_PHYSICAL_", "NATIVE_", "PAPER_",
                "PHYSICAL_CONTINUITY_", "EXIT_COMMITTED_", "SOURCE_"))
            if action != "WAIT" or objective_wait or receipt:
                self._emit(now, "COMMANDER", f"Commander {row.get('scope')} {action}"
                    + (f" #{row.get('position_id')}" if row.get("position_id") is not None else "")
                    + f" · {label(reason)}{suffix}",
                    "warning" if receipt.get("status") == "REJECTED" or objective_wait else "watch")
        positions = mapping(status.get("positions"))
        for pid, position in positions.items():
            position = mapping(position)
            key = self._trade_key(position)
            metadata = mapping(position.get("entry_metadata"))
            if key in self._trades:
                # Entry metadata is an explicit ledger fact, retained for the
                # later trade review. Current context cannot replace it.
                if isinstance(metadata.get("mission"), Mapping):
                    self._trades[key]["mission"] = position_mission_view(metadata["mission"])
                if isinstance(metadata.get("tactical_economics"), Mapping):
                    self._trades[key]["tactical_economics"] = tactical_economics_view(metadata["tactical_economics"])
            custody_state = position.get("custody_state")
            custody_metadata = mapping(position.get("custody_metadata"))
            if custody_state and self._custody_keys.get(key) != custody_state:
                self._custody_keys[key] = str(custody_state)
                reviewed = number(custody_metadata.get("reviewed_at"))
                when = reviewed if reviewed is not None else now
                reason = custody_metadata.get("reason") or "ENGINE_RECORDED_CUSTODY_STATE"
                self._emit(when, "CUSTODY", f"Custody #{pid} {position.get('side')} · "
                    f"{label(custody_state)} · {label(reason)} · same position identity", "protection")
                if key in self._trades:
                    evidence = {"event": "CUSTODY", "time": when, "key": key,
                                "state": custody_state, "reason": reason, "economic_event": False}
                    self._trades[key]["evidence"] = (self._trades[key]["evidence"] + [evidence])[-30:]
            signature = (position.get("peak_bid"), position.get("protected_peak_bid"), position.get("floor_bid"), position.get("trail_fraction"),
                         position.get("exit_required"), position.get("exit_reason"), position.get("tool"))
            if self._floor_keys.get(key) != signature:
                self._floor_keys[key] = signature
                floor, peak = number(position.get("floor_bid")), number(position.get("peak_bid"))
                text = f"Protection #{pid} {position.get('side')} · "
                text += f"floor {floor:.4f}" if floor is not None else "floor not armed"
                text += f" · full-lot peak {peak:.4f}" if peak is not None else " · full-lot peak not recorded"
                text += " · EXIT REQUIRED" if position.get("exit_required") is True else ""
                self._emit(now, "PROTECTION", text, "protection")
                record = {"event": "POSITION", "time": now, "fresh": True, "armed": floor is not None,
                          "stop_bid": floor, "peak_bid": peak, "reason": position.get("exit_reason") or
                          ("ARMED_FLOOR_PERSISTED" if floor is not None else "FLOOR_NOT_ARMED"),
                          "protected_peak_bid": number(position.get("protected_peak_bid")),
                          "trail_fraction": number(position.get("trail_fraction")), "key": key}
                self._protection[key] = record
                if key in self._trades:
                    self._trades[key]["evidence"] = (self._trades[key]["evidence"] + [record])[-30:]
        active_keys = {self._trade_key(mapping(p)) for p in positions.values()}
        self._floor_keys = {k: v for k, v in self._floor_keys.items() if k in active_keys}
        self._custody_keys = {k: v for k, v in self._custody_keys.items() if k in active_keys}
        self._marks = {k: v for k, v in self._marks.items() if k in active_keys}
        self._protection = {k: v for k, v in self._protection.items() if k in active_keys}
        self._decision_keys = {k: v for k, v in self._decision_keys.items()
                               if k == "ENTRY:" or k.split(":", 1)[-1] in positions}
        book = mapping(status.get("book"))
        q = quote_view(book, now, running=state in ("RUNNING", "DRAINING", "STOPPING"))
        quote_key = (book.get("ticker"), book.get("quote_id"), q["fresh"])
        if quote_key != self._last_quote_key:
            self._last_quote_key = quote_key
            self._quotes.append({"time": q.get("time") if q["fresh"] else now,
                                 "ticker": q.get("ticker"), "quote_id": q.get("quote_id"),
                                 **{k: q[k] for k in ("yes_bid", "yes_ask", "no_bid", "no_ask")}})
        if q["fresh"]:
            self._last_quote[str(q["ticker"])] = {**{k: q[k] for k in ("yes_bid", "yes_ask", "no_bid", "no_ask")},
                "verified_at": q["observed_wall"], "ticker": q["ticker"], "quote_id": q["quote_id"],
                "source": q["source"], "exchange_ts": q["exchange_ts"]}
            for position in positions.values():
                position = mapping(position)
                if position.get("ticker") != q["ticker"]:
                    continue
                side = str(position.get("side"))
                usage = self._sell_usage.get((book.get("ticker"), book.get("quote_id"), side), {})
                bid = full_lot_bid(book, side, position.get("qty"), usage) if q.get(side.lower()+"_bid") is not None and not usage.get("invalid") else None
                entry, qty = number(position.get("entry_price")), number(position.get("qty"))
                if bid is not None and entry is not None and entry > 0 and qty is not None:
                    self._marks[self._trade_key(position)] = {"bid": bid, "pnl": (bid-entry)*qty,
                        "roi": (bid/entry-1)*100, "verified_at": q["observed_wall"], "quote_id": q["quote_id"], "qty": qty}
        # Previous-ticker quotes are useful only inside the bounded chart; they
        # must never be borrowed for the new contract or retained indefinitely.
        current_ticker = str(book.get("ticker") or "")
        held_tickers = {str(mapping(p).get("ticker")) for p in positions.values()}
        self._last_quote = {k: v for k, v in self._last_quote.items() if k == current_ticker or k in held_tickers}

    @staticmethod
    def _chart(rows: Sequence[Mapping], snapshot: Mapping | None, now: float) -> tuple[list, list, dict]:
        candles: dict[int, dict] = {}
        emas: dict[int, dict] = {}
        snapshot = mapping(snapshot)
        for source in snapshot.get("candles") or ():
            source = mapping(source)
            ts = number(source.get("time"))
            values = [number(source.get(k)) for k in ("open", "high", "low", "close")]
            if ts is None or ts % 60 != 0 or any(v is None or v <= 0 for v in values):
                continue
            o, h, low, c = values
            if low > min(o, c) or h < max(o, c) or low > h:
                continue
            candles[int(ts)] = {**dict(source), "time": int(ts), "open": o, "high": h, "low": low, "close": c}
            if number(source.get("e9")) is not None or number(source.get("e30")) is not None:
                emas[int(ts)] = {"time": int(ts), "e9": number(source.get("e9")), "e30": number(source.get("e30"))}
        sampled: dict[int, dict] = {}
        for raw in rows:
            row = mapping(raw)
            ts, price = number(row.get("epoch_ms")), number(row.get("btc_price"))
            if ts is None or price is None or price <= 0 or ts / 1000 > now + 2:
                continue
            minute = int(ts / 60000) * 60
            bar = sampled.setdefault(minute, {"time": minute, "open": price, "high": price, "low": price,
                "close": price, "quality": "sampled", "complete": False, "source": "OBSERVED_PHYSICAL_SAMPLES",
                "first_observed_in_scan": ts / 1000, "known_at": ts / 1000, "sample_count": 0})
            bar["high"], bar["low"], bar["close"] = max(bar["high"], price), min(bar["low"], price), price
            bar["sample_count"] += 1
            bar["known_at"] = ts / 1000
            e9, e30 = number(row.get("ema9")), number(row.get("ema30"))
            if e9 is not None or e30 is not None:
                emas[minute] = {"time": minute, "e9": e9, "e30": e30}
        for minute, bar in sampled.items():
            if minute not in candles:
                candles[minute] = bar
        bars = sorted(candles.values(), key=lambda item: item["time"])[-1440:]
        ema_rows = sorted(emas.values(), key=lambda item: item["time"])[-1440:]
        history = dict(mapping(snapshot.get("history")))
        history.setdefault("requested_minutes", 45)
        history.setdefault("completed_minutes", sum(b.get("complete") is True for b in bars))
        history.setdefault("status", "SAMPLED_ONLY" if bars else "WARMING")
        history.setdefault("developing_status", "SAMPLED" if bars else "UNAVAILABLE")
        history.setdefault("developing_note", "Forward sampled bars contain observed prices only; missing trade extremes are not invented.")
        return bars, ema_rows, history

    def project(self, status: Mapping[str, Any], geometry_rows: Sequence[Mapping] = (),
                chart_data: Mapping | None = None, *, now_ts: float | None = None) -> dict:
        self.observe(status)
        now = time.time() if now_ts is None else float(now_ts)
        mono = time.monotonic()
        clock_continuous = self._clock_sample is None or abs((now - self._clock_sample[0]) - (mono - self._clock_sample[1])) <= 2.0
        self._clock_sample = (now, mono)
        updated = number(status.get("updated_at"))
        stopped = status.get("state") == "STOPPED"
        fresh = bool(updated is not None and 0 <= now - updated <= 5 and not stopped)
        source, physical, rack = (mapping(status.get(k)) for k in ("source_status", "physical", "rack"))
        book, market, latest = (mapping(status.get(k)) for k in ("book", "market", "latest_geometry"))
        quote = quote_view(book, now, running=fresh)
        last_quote = self._last_quote.get(str(book.get("ticker") or ""))
        if last_quote:
            quote["last_verified"] = last_quote
            quote["last_verified_age_seconds"] = now - last_quote["verified_at"]
        qtime = number(latest.get("epoch_ms"))
        qtime = qtime / 1000 if qtime is not None else None
        btc_fresh = bool(fresh and source.get("btc_current") is True and qtime is not None and -2 <= now-qtime <= 3)
        close = number(market.get("close_ts"))
        target = number(market.get("target"))
        if target is None or target <= 0 or market.get("target_source") != "KALSHI_MARKET_FLOOR_STRIKE":
            target = None
        market_view = {"ticker": market.get("ticker"), "time": qtime, "btc": number(latest.get("btc_price")),
                       "e9": number(latest.get("ema9")), "e30": number(latest.get("ema30")),
                       "target": target, "close_ts": close, "fresh": btc_fresh}
        position_reviews = {str(row.get("position_id")): mapping(mapping(row.get("decision")).get("intent"))
                            for row in (mapping(value) for value in status.get("decisions") or ())
                            if row.get("scope") == "POSITION" and row.get("position_id") is not None}
        positions = []
        for pid, raw in mapping(status.get("positions")).items():
            p = mapping(raw)
            key = self._trade_key(p)
            trade = self._trades.get(key, {})
            review = position_reviews.get(str(pid), {})
            policy = mapping(mapping(review.get("metadata")).get("floor_policy"))
            manager = review.get("tool") or p.get("tool")
            entry, qty = number(p.get("entry_price")), number(p.get("qty"))
            exact = p.get("ticker") == quote.get("ticker")
            side = str(p.get("side"))
            top_bid = quote.get(side.lower() + "_bid") if exact else None
            usage = self._sell_usage.get((book.get("ticker"), book.get("quote_id"), side), {})
            bid = full_lot_bid(book, side, qty, usage) if top_bid is not None and not usage.get("invalid") else None
            valid = bool(quote["fresh"] and bid is not None and entry is not None and entry > 0 and qty is not None)
            held_close = number(p.get("close_ts"))
            expired = held_close is not None and now >= held_close
            floor = number(p.get("floor_bid"))
            record = dict(self._protection.get(key) or {})
            record.update(armed=floor is not None, peak_bid=number(p.get("peak_bid")), stop_bid=floor,
                          protected_peak_bid=number(p.get("protected_peak_bid")),
                          bid=bid if valid else None, fresh=fresh and not expired,
                          reason=p.get("exit_reason") or ("ARMED_FLOOR_PERSISTED" if floor is not None else "FLOOR_NOT_ARMED"))
            mark = self._marks.get(key) or {}
            # A quote for a previously larger lot cannot be reused as a current
            # P&L number after a partial exit. Keep it only if quantity matches.
            mark = mark if mark.get("qty") == qty else {}
            card = {**trade, "key": key, "trade_id": str(pid), "position_id": str(pid), "ticker": p.get("ticker"),
                    "side": p.get("side"), "tool": p.get("tool"), "role": p.get("tool"),
                    "position_role": position_role(p) or trade.get("position_role"),
                    "mission": position_mission_view(mapping(p.get("entry_metadata")).get("mission")),
                    "collection_review": collection_review_view(
                        mapping(review.get("metadata")).get("mission_collection")
                        or mapping(policy.get("management_evidence")).get("mission_collection")),
                    "tactical_economics": tactical_economics_view(mapping(p.get("entry_metadata")).get("tactical_economics")),
                    "entry_tool": trade.get("tool") or p.get("tool"), "manager": manager,
                    "profit_protection_state": policy.get("profit_protection_state"),
                    "management_reason": _display_text(review.get("reason")),
                    "management_current": bool(review and fresh and physical.get("physical_current") is True),
                    "territory_id": p.get("territory_id"), "entry_ts": number(p.get("entry_time")),
                    "entry_ask": entry, "qty": qty, "remaining_qty": qty,
                    "original_qty": trade.get("original_qty", qty), "cost": number(p.get("cost")),
                    "entry_reason": p.get("entry_reason"), "evidence": trade.get("evidence", []),
                    "inventory_verified": True, "mark_valid": valid, "current_bid": bid if valid else None,
                    "native_top_bid": top_bid, "mark_basis": "FULL_REMAINING_LOT_CONSERVATIVE_NATIVE_DEPTH_BEFORE_EXIT_FEES",
                    "open_pnl": (bid-entry)*qty if valid else None,
                    "open_roi": (bid/entry-1)*100 if valid else None,
                    "valid_until": quote.get("valid_until") if valid else None,
                    "last_verified_mark": mark, "mark_age_seconds": now-mark["verified_at"] if mark else None,
                    "mark_reason": "FULL_REMAINING_LOT_NATIVE_DEPTH" if valid else "INSUFFICIENT_FULL_LOT_NATIVE_DEPTH" if top_bid is not None else quote.get("reason") if exact else "EXACT_HELD_CONTRACT_QUOTE_UNAVAILABLE",
                    "state": "UNRESOLVED AT STOP" if stopped else "AWAITING OFFICIAL RESULT" if expired else
                    "EXIT PENDING" if p.get("exit_required") else "LAZARUS CUSTODY" if p.get("custody_state") == "LAZARUS" else
                    "FLOOR ARMED" if floor is not None else "NORMAL CUSTODY RESTORED" if p.get("custody_state") == "RECOVERED_NORMAL" else "TOOL CUSTODY",
                    "custody": manager, "custody_state": p.get("custody_state") or "NORMAL",
                    "custody_metadata": dict(mapping(p.get("custody_metadata"))), "protection": record}
            positions.append({k: v for k, v in card.items() if not k.startswith("_")})
        entries = [mapping(row) for row in status.get("decisions") or () if mapping(row).get("scope") == "ENTRY"]
        decision = mapping(entries[-1].get("decision")) if entries else {}
        primary = mapping((rack.get("primary_intents") or [{}])[0])
        briefings = [mapping(row) for row in rack.get("briefings") or ()]
        current_briefing = briefings[0] if briefings else {}
        all_intents = list(rack.get("intents") or ())
        trades = [{k: v for k, v in row.items() if not k.startswith("_")} for row in self._trades.values()]
        closed = [t for t in trades if t["exit_ts"] is not None]
        issues = list(self._issues)
        issues.extend(str(source[k]) for k in ("source_error", "discovery_error", "rest_diagnostic_error") if source.get(k))
        if self._history_truncated:
            issues.append("Viewer trade history is bounded; session accounting still comes directly from the committed ledger.")
        bars, emas, history = self._chart(geometry_rows, chart_data, now)
        physical_fresh = fresh and physical.get("physical_current") is True
        mission_context = mission_context_view(status.get("mission_context"), fresh=fresh,
            physical_current=physical_fresh, now=now, updated=updated)
        health = {"engine": {"status": "STOPPED" if stopped else "CURRENT" if fresh else "STALE", "updated": updated,
                             "reason": status.get("state")},
                  "price": {"status": "CURRENT" if btc_fresh else "WARMING" if qtime is None else "STALE", "updated": qtime,
                            "reason": source.get("source_error") or "DIRECT_COINBASE_PUBLIC_TRADES"},
                  "quotes": {"status": "CURRENT" if quote["fresh"] else "UNAVAILABLE", "updated": quote.get("observed_wall"),
                             "reason": quote["reason"]},
                  "physical": {"status": "CURRENT" if physical_fresh else "WARMING", "updated": updated,
                               "reason": "REACQUISITION_REQUIRED" if status.get("awaiting_physical_reacquisition") else "DIRECT_CAUSAL_PHYSICAL_SOURCE"},
                  "commander": {"status": "STOPPED" if stopped else "CURRENT" if fresh else "STALE", "updated": updated,
                                "reason": decision.get("reason")},
                  "candles": {"status": "READY" if bars else "WARMING", "updated": bars[-1]["time"] if bars else None,
                              "reason": history.get("status")}}
        clock_valid = bool(fresh and clock_continuous and close is not None and now < close <= now+905)
        targets = list(self._targets.values())
        looking_glass = self._looking_glass_view(
            {**market_view, "fresh": bool(btc_fresh and clock_valid)},
            bars, emas, targets, quote, now,
            looking_glass_pattern_context(status, market_view, current=bool(physical_fresh and clock_valid)))
        result = {"version": VERSION, "server_now": now, "mode": "PAPER_ONLY", "readonly": True,
            "run": {"name": status.get("run_id"), "run_id": status.get("run_id"), "session_id": status.get("run_id"),
                    "version": status.get("runtime_revision"), "build": VERSION, "path": None, "pid": None,
                    "stopped": stopped, "review": False, "fresh": fresh, "updated": updated,
                    "status": status.get("state"), "pointer_changed": False},
            "market": market_view, "quote": quote, "candles": bars, "emas": emas, "targets": targets,
            "looking_glass": looking_glass,
            "mission_context": mission_context,
            "candidate_review": candidate_review_view(status.get("candidate_review")),
            "quotes": list(self._quotes), "trades": trades, "positions": positions,
            "contract_exposure": contract_exposure(positions),
            "accounting": {"realized": number(status.get("realized_gross")), "realized_net": number(status.get("realized_net")),
                           "fees_paid": number(status.get("fees_paid")), "cash": number(status.get("cash")),
                           "closed": len(closed), "wins": sum(t["net_pnl"] is not None and t["net_pnl"] > 0 for t in closed),
                           "realized_stale": not fresh, "inventory_verified": True,
                           "runtime_reports_no_positions": not positions, "issues": list(self._issues),
                           "projection_status": "COMMITTED_ENGINE_SNAPSHOT", "ledger_seq": status.get("ledger_seq"),
                           "open_pnl": sum(p["open_pnl"] for p in positions) if all(p["open_pnl"] is not None for p in positions) else None,
                           "basis": "PAPER LEDGER: net includes allocated entry and exit model fees; open marks use conservative full-remaining-lot native depth before exit fees. Simulated fills are not venue fills."},
            "tool_rack": {**dict(rack), "commander_action": decision.get("action"), "commander_reason": decision.get("reason"),
                          "physical_current": physical_fresh, "observed_at": updated, "timeline": list(self._timeline)},
            "interpretation": {"time": updated, "pilot": dict(decision), "physical": dict(physical),
                "tool_intents": all_intents, "development": dict(rack.get("release_diagnostics") or {}),
                "battle_plan": {"current_leg": label(rack.get("owned_territory")),
                    "recent_comparison": label(rack.get("ownership_reason")),
                    "expected_next": label(primary.get("expires_when"), "Only observed tool conditions are displayed"),
                    "entry_plan": (f"{label(current_briefing.get('state'))} {current_briefing.get('side') or ''} "
                                   f"<= {number(current_briefing.get('max_price')):.3f}"
                                   if current_briefing and number(current_briefing.get('max_price')) is not None
                                   else label(current_briefing.get("reason") or primary.get("reason") or "Await positive briefing")),
                    "change_condition": label(rack.get("release_boundary_name"), "No confirmed transfer boundary"), "source_ts": updated},
                "navigator": {}, "observer42": {}, "shadow_ai": {},
                "shadow_ai_status": {"status": "NOT_RUNNING", "execution_authority": False,
                    "reason": "Optional AI commentary is not attached. This feed reports the actual Tool Rack, Commander and committed PAPER ledger."}},
            "feed": list(self._feed), "commands": list(self._commands), "health": health, "history": history,
            "clock": {"verified": clock_valid, "close_ts": close, "valid_until": min(updated+5,close) if clock_valid else None,
                      "status": "OBSERVED_CONTRACT_LOCAL_CLOCK" if clock_valid else "UNAVAILABLE_OR_CLOSED",
                      "clock": {"continuous": clock_continuous, "absolute_exchange_offset_measured": False}},
            "diagnostics": {"issues": sorted(set(issues)), "readers": {},
                "sampled_candles": sum(b.get("quality") == "sampled" for b in bars),
                "complete_candles": sum(b.get("complete") is True for b in bars),
                "candle_note": "Seed history and forward trade candles retain their source labels; dashed sampled candles may omit extremes. Missing intervals remain gaps.",
                "ema_note": "EMA values are received from the current engine/feed; visible-window calculations never replace strategy EMAs.",
                "command_window": "Bounded session projection of real Commander decisions and committed PAPER events; browser reload preserves the feed. Full audit remains in decisions.jsonl and paper_journal.",
                "freshness_check": {"published_at": now, "engine_observed_at": updated,
                                    "quote_observed_at": quote.get("observed_wall"), "restamping_native_quote": False},
                "authority": "DISPLAY_ONLY", "legacy_r22_loaded": False}}
        return deepcopy(result)
