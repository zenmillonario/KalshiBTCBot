"""Causal rolling performance memory for physical EMA9 legs.

The ledger records every observed physical leg whether traded or not.  It has
zero trading authority.  OneCommander may use its last 3-5 comparable legs as
entry/hold/exit evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Mapping

from strategy_core.types import MarketSnapshot


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
    text = str(getattr(value, "value", value)).upper() if value is not None else ""
    return text if text in ("YES", "NO") else None


def _terrain(snapshot: MarketSnapshot) -> str:
    strategy = _map(snapshot.metadata.get("commander_strategy"))
    value = str(strategy.get("owned_territory") or "UNKNOWN")
    return value


def _current_physical(snapshot: MarketSnapshot) -> tuple[str | None, str | None, str | None]:
    mountain = _map(snapshot.metadata.get("mountain"))
    parent = _map(mountain.get("parent_structure"))
    parent_id = parent.get("parent_id")
    parent_side = _side(parent.get("parent_side"))
    child_id = mountain.get("current_arc_id")
    child_side = _side(mountain.get("owner_side"))
    if parent_id and parent_side:
        return str(parent_id), parent_side, str(child_id) if child_id else None
    if child_id and child_side:
        return str(child_id), child_side, str(child_id)
    # A territory/tool label is an observation about a physical leg, not its
    # identity.  In particular UNKNOWN/HEIST/RAIL flicker cannot manufacture
    # completed legs when no physical identity is available.
    return None, None, str(child_id) if child_id else None


def _identity_source(snapshot: MarketSnapshot) -> str:
    parent = _map(_map(snapshot.metadata.get("mountain")).get("parent_structure"))
    return "EMA9_PARENT" if parent.get("parent_id") and _side(parent.get("parent_side")) else "MOUNTAIN_CHILD"


def _comparable_record(row: Mapping[str, Any]) -> bool:
    """Only boundary-observed V2 legs are duration/amplitude comparables.

    V1 cannot distinguish label fragments from physical legs or prove ticker
    provenance.  It remains readable in its original archive, never silently
    promoted into corrected evidence.
    """
    duration = _num(row.get("duration_s"))
    return bool(row.get("version") == "LEG_PERFORMANCE_LEDGER_V2"
                and row.get("record_kind") == "PHYSICAL_LEG"
                and row.get("start_boundary_observed") is True
                and row.get("end_boundary_observed") is True
                and row.get("comparable_eligible") is True
                and duration is not None and duration > 0
                and (_num(row.get("sample_count")) or 0) >= 2)


def validated_contract_opportunities(record: Mapping[str, Any], side: str) -> list[dict[str, Any]]:
    """Read independently checkable quote excursions; never combine contracts.

    These are top-of-book observations, not proof of a full-lot fill or a new
    trading permission.  Legacy mixed-ticker scalar returns are not accepted.
    """
    if not _comparable_record(record) or side not in ("YES", "NO"):
        return []
    contracts = record.get("contract_opportunities")
    if not isinstance(contracts, (list, tuple)):
        return []
    validated = []
    seen = set()
    for contract in contracts:
        contract = _map(contract)
        ticker = contract.get("ticker")
        if not isinstance(ticker, str) or not ticker or ticker in seen:
            continue
        seen.add(ticker)
        opportunity = _map(contract.get("yes_opportunity" if side == "YES" else "no_opportunity"))
        ask, bid = _num(opportunity.get("min_ask")), _num(opportunity.get("max_bid_after_min_ask"))
        ask_ts, bid_ts = _num(opportunity.get("min_ask_ts")), _num(opportunity.get("max_bid_ts"))
        start, end = _num(contract.get("start_ts")), _num(contract.get("end_ts"))
        reported = _num(opportunity.get("potential_roi_from_best_observed_basis"))
        if (contract.get("opportunity_scope") != "EXACT_TICKER"
                or opportunity.get("opportunity_scope") != "EXACT_TICKER"
                or opportunity.get("ticker_scope_valid") is not True
                or opportunity.get("side") != side
                or any(opportunity.get(key) != ticker for key in ("ticker", "min_ask_ticker", "max_bid_ticker"))
                or ask is None or not 0 < ask < 1 or bid is None or not 0 < bid < 1
                or None in (start, end, ask_ts, bid_ts) or not start <= ask_ts <= bid_ts <= end
                or reported is None or not math.isclose(reported, (bid - ask) / ask, rel_tol=1e-12, abs_tol=1e-12)):
            continue
        validated.append({**dict(opportunity), "leg_id": record.get("leg_id")})
    return validated


@dataclass
class QuoteOpportunity:
    ticker: str
    side: str
    min_ask: float | None = None
    min_ask_ts: float | None = None
    max_bid_after_min_ask: float | None = None
    max_bid_ts: float | None = None

    def observe(self, *, ticker: str, ask: float | None, bid: float | None, now: float) -> None:
        if not self.ticker or ticker != self.ticker:
            raise ValueError("QUOTE_OPPORTUNITY_TICKER_MISMATCH")
        ask, bid = _num(ask), _num(bid)
        if ask is not None and 0 < ask < 1 and (self.min_ask is None or ask < self.min_ask):
            self.min_ask = ask
            self.min_ask_ts = now
            self.max_bid_after_min_ask = bid if bid is not None and 0 < bid < 1 else None
            self.max_bid_ts = now if self.max_bid_after_min_ask is not None else None
        elif (self.min_ask is not None and self.min_ask_ts is not None and now >= self.min_ask_ts
              and bid is not None and 0 < bid < 1
              and (self.max_bid_after_min_ask is None or bid > self.max_bid_after_min_ask)):
            self.max_bid_after_min_ask = bid
            self.max_bid_ts = now

    def payload(self) -> dict[str, Any]:
        roi = None
        time_to_mfe = None
        if self.min_ask not in (None, 0) and self.max_bid_after_min_ask is not None:
            roi = (self.max_bid_after_min_ask - self.min_ask) / self.min_ask
        if self.min_ask_ts is not None and self.max_bid_ts is not None:
            time_to_mfe = self.max_bid_ts - self.min_ask_ts
        return {
            "opportunity_scope": "EXACT_TICKER",
            "ticker": self.ticker,
            "side": self.side,
            "min_ask_ticker": self.ticker if self.min_ask is not None else None,
            "max_bid_ticker": self.ticker if self.max_bid_after_min_ask is not None else None,
            "ticker_scope_valid": roi is not None and time_to_mfe is not None and time_to_mfe >= 0,
            "quantity_basis": "TOP_OF_BOOK_ONLY",
            "execution_authority": False,
            "min_ask": self.min_ask,
            "min_ask_ts": self.min_ask_ts,
            "max_bid_after_min_ask": self.max_bid_after_min_ask,
            "max_bid_ts": self.max_bid_ts,
            "potential_roi_from_best_observed_basis": roi,
            "time_to_mfe_s": time_to_mfe,
        }


@dataclass
class ContractOpportunity:
    ticker: str
    start_ts: float
    end_ts: float
    sample_count: int = 0
    quotes_yes: QuoteOpportunity = field(init=False)
    quotes_no: QuoteOpportunity = field(init=False)

    def __post_init__(self) -> None:
        self.quotes_yes = QuoteOpportunity(self.ticker, "YES")
        self.quotes_no = QuoteOpportunity(self.ticker, "NO")

    def observe(self, snapshot: MarketSnapshot) -> None:
        if snapshot.ticker != self.ticker:
            raise ValueError("CONTRACT_OPPORTUNITY_TICKER_MISMATCH")
        self.end_ts = snapshot.now_ts
        self.quotes_yes.observe(ticker=snapshot.ticker, ask=snapshot.yes_ask,
                                bid=snapshot.yes_bid, now=snapshot.now_ts)
        self.quotes_no.observe(ticker=snapshot.ticker, ask=snapshot.no_ask,
                               bid=snapshot.no_bid, now=snapshot.now_ts)
        self.sample_count += 1

    def payload(self) -> dict[str, Any]:
        return {"ticker": self.ticker, "opportunity_scope": "EXACT_TICKER",
                "start_ts": self.start_ts, "end_ts": self.end_ts, "sample_count": self.sample_count,
                "yes_opportunity": self.quotes_yes.payload(), "no_opportunity": self.quotes_no.payload()}


@dataclass
class LiveLeg:
    leg_id: str
    side: str
    terrain: str
    start_ts: float
    first_btc: float | None
    first_ema9: float | None
    first_tp: float | None
    last_ts: float
    identity_source: str
    continuity_generation: Any
    start_reason: str
    start_boundary_observed: bool
    btc_min: float | None = None
    btc_max: float | None = None
    ema9_min: float | None = None
    ema9_max: float | None = None
    tp_last: float | None = None
    child_sequence: list[dict[str, Any]] = field(default_factory=list)
    last_child_id: str | None = None
    contract_opportunities: dict[str, ContractOpportunity] = field(default_factory=dict)
    terrain_sequence: list[dict[str, Any]] = field(default_factory=list)
    sample_count: int = 0
    contracts_seen: list[str] = field(default_factory=list)

    def observe(self, snapshot: MarketSnapshot, *, child_id: str | None) -> None:
        self.last_ts = snapshot.now_ts
        self.terrain = _terrain(snapshot)
        if not self.terrain_sequence or self.terrain_sequence[-1]["terrain"] != self.terrain:
            self.terrain_sequence.append({"terrain": self.terrain, "start_ts": snapshot.now_ts,
                                          "end_ts": snapshot.now_ts, "sample_count": 0})
        self.terrain_sequence[-1]["end_ts"] = snapshot.now_ts
        self.terrain_sequence[-1]["sample_count"] += 1
        if snapshot.ticker and snapshot.ticker not in self.contracts_seen:
            self.contracts_seen.append(snapshot.ticker)
        current = _map(snapshot.metadata.get("current_geometry"))
        mountain = _map(snapshot.metadata.get("mountain"))
        btc = _num(current.get("btc_price")) or _num(mountain.get("current_btc"))
        ema9 = _num(current.get("ema9")) or _num(mountain.get("current_ema9"))
        tp = _num(_map(snapshot.metadata.get("tp_geometry")).get("target"))
        if btc is not None:
            self.btc_min = btc if self.btc_min is None else min(self.btc_min, btc)
            self.btc_max = btc if self.btc_max is None else max(self.btc_max, btc)
        if ema9 is not None:
            self.ema9_min = ema9 if self.ema9_min is None else min(self.ema9_min, ema9)
            self.ema9_max = ema9 if self.ema9_max is None else max(self.ema9_max, ema9)
        self.tp_last = tp
        if child_id and child_id != self.last_child_id:
            # Close the previous child segment causally at the first observation
            # of the new child.  This lets Arc Echo remember actual pullback
            # depth/duration rather than only counting labels.
            if self.child_sequence:
                prior = self.child_sequence[-1]
                prior["end_ts"] = snapshot.now_ts
                prior["end_btc"] = btc
                prior["duration_s"] = max(0.0, snapshot.now_ts - float(prior["start_ts"]))
            child_side = _side(mountain.get("owner_side"))
            self.child_sequence.append({
                "id": child_id, "side": child_side, "known_at": snapshot.now_ts,
                "start_ts": snapshot.now_ts, "end_ts": snapshot.now_ts,
                "start_btc": btc, "end_btc": btc, "btc_min": btc, "btc_max": btc,
                "duration_s": 0.0,
            })
            self.last_child_id = child_id
        elif child_id and self.child_sequence:
            child = self.child_sequence[-1]
            child["end_ts"] = snapshot.now_ts
            child["end_btc"] = btc
            child["duration_s"] = max(0.0, snapshot.now_ts - float(child["start_ts"]))
            if btc is not None:
                child["btc_min"] = btc if child.get("btc_min") is None else min(float(child["btc_min"]), btc)
                child["btc_max"] = btc if child.get("btc_max") is None else max(float(child["btc_max"]), btc)
        # The physical leg lives through rollover.  Contract payoff bases do
        # not: a 0.1-cent old-contract ask may never pair with a new-contract
        # bid.  Non-current or unidentified quotes add no opportunity sample.
        if snapshot.ticker and snapshot.quote_current:
            if snapshot.ticker not in self.contract_opportunities:
                self.contract_opportunities[snapshot.ticker] = ContractOpportunity(
                    snapshot.ticker, snapshot.now_ts, snapshot.now_ts)
            self.contract_opportunities[snapshot.ticker].observe(snapshot)
        self.sample_count += 1

    def payload(self, *, end_reason: str, physical_end_observed: bool = False) -> dict[str, Any]:
        duration = max(0.0, self.last_ts - self.start_ts)
        btc_amp = (self.btc_max - self.btc_min
                   if self.btc_min is not None and self.btc_max is not None else None)
        ema9_amp = (self.ema9_max - self.ema9_min
                    if self.ema9_min is not None and self.ema9_max is not None else None)
        pullback_rows = []
        prior_owner_child = None
        for child in self.child_sequence:
            child_side = child.get("side")
            if child_side == self.side:
                prior_owner_child = child
                continue
            if child_side is None:
                continue
            lo, hi = _num(child.get("btc_min")), _num(child.get("btc_max"))
            depth = None
            reference_btc = None
            if prior_owner_child is not None:
                if self.side == "YES":
                    reference_btc = _num(prior_owner_child.get("btc_max"))
                    if reference_btc is not None and lo is not None:
                        depth = max(0.0, reference_btc - lo)
                else:
                    reference_btc = _num(prior_owner_child.get("btc_min"))
                    if reference_btc is not None and hi is not None:
                        depth = max(0.0, hi - reference_btc)
            if depth is None and lo is not None and hi is not None:
                depth = hi - lo
            pullback_rows.append({
                "id": child.get("id"), "side": child_side,
                "start_ts": child.get("start_ts"), "end_ts": child.get("end_ts"),
                "duration_s": child.get("duration_s"), "btc_depth": depth,
                "reference_btc": reference_btc,
            })
        pullbacks = len(pullback_rows)
        pushes = sum(1 for child in self.child_sequence if child.get("side") == self.side)
        contracts = [contract.payload() for contract in self.contract_opportunities.values()]
        if len(self.contracts_seen) == 1 and len(contracts) == 1:
            yes_opportunity, no_opportunity = contracts[0]["yes_opportunity"], contracts[0]["no_opportunity"]
        else:
            # Preserve the familiar keys without representing a multi-contract
            # observation as one tradable instrument.  Full data is below.
            empty = {"min_ask": None, "min_ask_ts": None, "max_bid_after_min_ask": None,
                     "max_bid_ts": None, "potential_roi_from_best_observed_basis": None,
                     "time_to_mfe_s": None, "ticker": None, "ticker_scope_valid": False,
                     "opportunity_scope": "NO_SINGLE_CONTRACT_PROJECTION", "execution_authority": False,
                     "reason": "USE_EXACT_TICKER_CONTRACT_OPPORTUNITIES"}
            yes_opportunity, no_opportunity = {**empty, "side": "YES"}, {**empty, "side": "NO"}
        return {
            "version": "LEG_PERFORMANCE_LEDGER_V2",
            "execution_authority": False,
            "record_kind": "PHYSICAL_LEG" if physical_end_observed else "OBSERVATION_SEGMENT",
            "identity_source": self.identity_source,
            "continuity_generation": self.continuity_generation,
            "start_reason": self.start_reason,
            "start_boundary_observed": self.start_boundary_observed,
            "end_boundary_observed": physical_end_observed,
            "duration_basis": "FIRST_TO_LAST_OBSERVATION",
            "comparable_eligible": bool(self.start_boundary_observed and physical_end_observed
                                         and duration > 0 and self.sample_count >= 2),
            "leg_id": self.leg_id,
            "side": self.side,
            "terrain": self.terrain,
            "terrain_sequence": [dict(row) for row in self.terrain_sequence],
            "terrain_has_boundary_authority": False,
            "start_ts": self.start_ts,
            "end_ts": self.last_ts,
            "duration_s": duration,
            "first_btc": self.first_btc,
            "btc_min": self.btc_min,
            "btc_max": self.btc_max,
            "btc_amplitude": btc_amp,
            "first_ema9": self.first_ema9,
            "ema9_min": self.ema9_min,
            "ema9_max": self.ema9_max,
            "ema9_amplitude": ema9_amp,
            "tp_start": self.first_tp,
            "tp_end": self.tp_last,
            "child_sequence": list(self.child_sequence),
            "push_count": pushes,
            "pullback_count": pullbacks,
            "pullbacks": pullback_rows,
            "yes_opportunity": yes_opportunity,
            "no_opportunity": no_opportunity,
            "contract_opportunities": contracts,
            "opportunity_scope": "EXACT_TICKER_ONLY",
            "sample_count": self.sample_count,
            "contracts_seen": list(self.contracts_seen),
            "contract_count": len(self.contracts_seen),
            "end_reason": end_reason,
        }


class LegPerformanceLedger:
    def __init__(self, path: Path | None = None, *, max_history: int = 128) -> None:
        self.path = Path(path) if path is not None else None
        self.max_history = max_history
        self.completed: list[dict[str, Any]] = []
        self.live: LiveLeg | None = None

    @staticmethod
    def _new_leg(snapshot: MarketSnapshot, leg_id: str, side: str, terrain: str,
                 *, start_reason: str, start_boundary_observed: bool = False) -> LiveLeg:
        current = _map(snapshot.metadata.get("current_geometry"))
        mountain = _map(snapshot.metadata.get("mountain"))
        btc = _num(current.get("btc_price")) or _num(mountain.get("current_btc"))
        ema9 = _num(current.get("ema9")) or _num(mountain.get("current_ema9"))
        tp = _num(_map(snapshot.metadata.get("tp_geometry")).get("target"))
        return LiveLeg(leg_id, side, terrain, snapshot.now_ts, btc, ema9, tp, snapshot.now_ts,
                       _identity_source(snapshot), snapshot.metadata.get("geometry_continuity_generation"),
                       start_reason, start_boundary_observed)

    def _append(self, record: dict[str, Any]) -> None:
        self.completed.append(record)
        if len(self.completed) > self.max_history:
            self.completed = self.completed[-self.max_history:]
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")

    def observe(self, snapshot: MarketSnapshot) -> dict[str, Any]:
        leg_id, side, child_id = _current_physical(snapshot)
        terrain = _terrain(snapshot)
        start_reason = "FIRST_OBSERVATION"
        if self.live is not None:
            break_reason = None
            if self.live.continuity_generation != snapshot.metadata.get("geometry_continuity_generation"):
                break_reason = "GEOMETRY_CONTINUITY_CHANGED"
            elif snapshot.now_ts < self.live.last_ts:
                break_reason = "OBSERVATION_TIME_REGRESSION"
            elif snapshot.metadata.get("physical_current") is False:
                break_reason = "PHYSICAL_SOURCE_NOT_CURRENT"
            elif leg_id is None or side is None:
                break_reason = "PHYSICAL_IDENTITY_UNAVAILABLE"
            elif self.live.identity_source != _identity_source(snapshot):
                break_reason = "PHYSICAL_IDENTITY_SOURCE_CHANGED"
            if break_reason:
                self._append(self.live.payload(end_reason=break_reason))
                self.live = None
                start_reason = break_reason
        if snapshot.metadata.get("physical_current") is False:
            return self.summary(snapshot)
        if leg_id is None or side is None:
            return self.summary(snapshot)
        if self.live is None:
            self.live = self._new_leg(snapshot, leg_id, side, terrain, start_reason=start_reason)
        elif self.live.leg_id != leg_id or self.live.side != side:
            self._append(self.live.payload(end_reason="PHYSICAL_LEG_CHANGED", physical_end_observed=True))
            self.live = self._new_leg(snapshot, leg_id, side, terrain,
                                      start_reason="PHYSICAL_LEG_CHANGED", start_boundary_observed=True)
        self.live.observe(snapshot, child_id=child_id)
        return self.summary(snapshot)

    def finalize(self, *, reason: str = "RUN_STOP") -> None:
        if self.live is not None:
            self._append(self.live.payload(end_reason=reason))
            self.live = None

    def comparable(self, *, terrain: str, side: str, limit: int = 5) -> list[dict[str, Any]]:
        eligible = [row for row in self.completed if _comparable_record(row)]
        exact = [row for row in eligible if row.get("terrain") == terrain and row.get("side") == side]
        if len(exact) >= 2:
            return exact[-limit:]
        same_side = [row for row in eligible if row.get("side") == side]
        return same_side[-limit:]

    def summary(self, snapshot: MarketSnapshot) -> dict[str, Any]:
        terrain = self.live.terrain if self.live else _terrain(snapshot)
        side = self.live.side if self.live else _current_physical(snapshot)[1]
        rows = self.comparable(terrain=terrain, side=side, limit=5) if side else []
        durations = [float(r["duration_s"]) for r in rows if _num(r.get("duration_s")) is not None]
        amplitudes = [float(r["btc_amplitude"]) for r in rows if _num(r.get("btc_amplitude")) is not None]
        pullbacks = [float(r["pullback_count"]) for r in rows if _num(r.get("pullback_count")) is not None]
        pullback_depths = [
            float(pb["btc_depth"]) for row in rows for pb in row.get("pullbacks", [])
            if _num(pb.get("btc_depth")) is not None
        ]
        pullback_durations = [
            float(pb["duration_s"]) for row in rows for pb in row.get("pullbacks", [])
            if _num(pb.get("duration_s")) is not None
        ]
        live_age = max(0.0, snapshot.now_ts - self.live.start_ts) if self.live else None
        live_amp = None
        if self.live and self.live.btc_min is not None and self.live.btc_max is not None:
            live_amp = self.live.btc_max - self.live.btc_min
        med_duration = median(durations) if durations else None
        med_amp = median(amplitudes) if amplitudes else None
        return {
            "version": "LEG_ECHO_V2",
            "execution_authority": False,
            "comparison_basis": "V2_BOUNDARY_OBSERVED_PHYSICAL_LEGS_ONLY",
            "excluded_record_count": sum(not _comparable_record(row) for row in self.completed),
            "legacy_record_count": sum(row.get("version") != "LEG_PERFORMANCE_LEDGER_V2" for row in self.completed),
            "terrain": terrain,
            "side": side,
            "comparison_count": len(rows),
            "comparison_quality": "STRONG" if len(rows) >= 5 else "USEFUL" if len(rows) >= 3 else "SPARSE",
            "comparable_leg_ids": [r.get("leg_id") for r in rows],
            "median_duration_s": med_duration,
            "median_btc_amplitude": med_amp,
            "median_pullback_count": median(pullbacks) if pullbacks else None,
            "median_pullback_btc": median(pullback_depths) if pullback_depths else None,
            "median_pullback_duration_s": median(pullback_durations) if pullback_durations else None,
            "live_pullback_count": sum(1 for child in self.live.child_sequence
                                       if child.get("side") not in (None, self.live.side)) if self.live else 0,
            "live_current_child": dict(self.live.child_sequence[-1]) if self.live and self.live.child_sequence else None,
            "live_age_s": live_age,
            "live_leg_id": self.live.leg_id if self.live else None,
            "live_identity_source": self.live.identity_source if self.live else None,
            "live_start_boundary_observed": self.live.start_boundary_observed if self.live else False,
            "live_btc_amplitude": live_amp,
            "live_age_ratio": live_age / med_duration if live_age is not None and med_duration not in (None, 0) else None,
            "live_amplitude_ratio": live_amp / med_amp if live_amp is not None and med_amp not in (None, 0) else None,
            "live_contracts_seen": list(self.live.contracts_seen) if self.live else [],
            "live_contract_count": len(self.live.contracts_seen) if self.live else 0,
            "completed_comparable_legs": rows,
        }
