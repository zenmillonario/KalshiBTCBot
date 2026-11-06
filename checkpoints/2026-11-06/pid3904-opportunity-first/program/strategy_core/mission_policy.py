"""Causal purpose admission and exact-contract tactical return scenarios.

The physical context selects a mission. This module never derives an edge
from a cheap quote, changes an existing lot's role, or promises a future fill.
Observed native bid response supplies an explicitly uncalibrated scenario;
the passive writer still rechecks the actual current price and consumed depth.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from decimal import Decimal
import json
import math
from pathlib import Path
from statistics import median
from typing import Any, Mapping

from strategy_core.mission_scopes import PARENT_MISSION_PURPOSES, qualified_full_arc_candidate
from strategy_core.paper_execution import PriceLevel, _sweep, nominal_taker_fee
from strategy_core.source_freshness import current_source_is_fresh, current_source_receipt
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


VERSION = "PID10092_PERSISTENT_MISSIONS_V1"
TACTICAL_COLLECTION_POLICY = "TACTICAL_OBSERVED_RETURN_V2"


def _map(value: Any) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _levels(raw: Any) -> tuple[PriceLevel, ...]:
    result = []
    if not isinstance(raw, (tuple, list)):
        return ()
    for row in raw:
        if isinstance(row, Mapping):
            p, q = _num(row.get("price")), _num(row.get("quantity"))
        elif isinstance(row, (tuple, list)) and len(row) == 2:
            p, q = _num(row[0]), _num(row[1])
        else:
            return ()
        if p is None or q is None or not 0 < p < 1 or q <= 0:
            return ()
        result.append(PriceLevel(p, q))
    return tuple(result)


def _heist_return_destination(snapshot: MarketSnapshot, side: str,
                              context: Mapping, box: Mapping) -> tuple[dict, dict, str | None]:
    """Freeze the physical return actually being bought at this box edge.

    Against an actively advancing parent, the internal pullback first returns
    to its entry-time EMA9. An old box's distant opposite wall must not inflate
    that small swing's prospective return. A witnessed neutral box retains its
    opposite wall. These are tactical classifications, never full-arc vetoes.
    """
    source = _num(context.get("source_ms"))
    geometry = _map(snapshot.metadata.get("current_geometry"))
    mountain = _map(snapshot.metadata.get("mountain"))
    parent = _map(context.get("parent"))
    contract = _map(context.get("contract"))
    e9, btc = _num(geometry.get("ema9")), _num(geometry.get("btc_price"))
    lower, upper = _num(box.get("lower")), _num(box.get("upper"))
    evidence: dict[str, Any] = {"version": "TACTICAL_FROZEN_DESTINATION_V2",
        "source_ms": source, "parent_leg_id": parent.get("id"),
        "parent_side": parent.get("side"), "entry_ema9": e9,
        "entry_btc": btc, "current_ema9_horizons": {}, "basis": "UNRESOLVED"}
    unavailable = "TACTICAL_CURRENT_RETURN_DESTINATION_UNRESOLVED"
    if (source is None or _num(geometry.get("epoch_ms")) != source
            or snapshot.metadata.get("physical_current") is not True
            or contract.get("ticker") != snapshot.ticker
            or _num(mountain.get("source_ms")) != source
            or e9 is None or btc is None or lower is None or upper is None or upper <= lower):
        return {}, evidence, unavailable
    signs = []
    for h in (6, 30, 60):
        motion = _map(_map(mountain.get("current_motion")).get(str(h)))
        start = _num(motion.get("start_source_ms"))
        first_e9 = _num(motion.get("first_ema9"))
        if (motion.get("covered") is not True or motion.get("source_continuous") is not True
                or motion.get("endpoints_are_actual_observations") is not True
                or _num(motion.get("source_ms")) != source
                or _num(motion.get("current_ema9")) != e9
                or start is None or not 0 < start < source or first_e9 is None):
            return {}, evidence, unavailable
        duration = (source - start) / 1000.
        resolution = .08 * (upper - lower) * duration / max(150., duration)
        change = e9 - first_e9
        signs.append(1 if change > resolution else -1 if change < -resolution else 0)
        evidence["current_ema9_horizons"][str(h)] = {"start_source_ms": start,
            "source_ms": source, "ema9_change": change, "resolution": resolution,
            "covered": True}
    direction = "YES" if all(s == 1 for s in signs) else "NO" if all(s == -1 for s in signs) else None
    neutral = all(s == 0 for s in signs)
    evidence["current_ema9_side"] = direction
    if direction:
        known = _num(parent.get("known_ms"))
        if (parent.get("status") != "ACTIVE" or parent.get("supported") is not True
                or parent.get("invalidated") is True or not parent.get("id")
                or parent.get("side") != direction
                or _num(parent.get("source_ms")) != source
                or parent.get("continuity_generation") != context.get("continuity_generation")
                or known is None or not 0 < known <= source):
            return {}, evidence, "TACTICAL_CURRENT_PARENT_AND_EMA9_DIRECTION_UNRESOLVED"
        if side != direction:
            tolerance = _num(mountain.get("contact_width"))
            if tolerance is None or tolerance < 0:
                return {}, evidence, unavailable
            evidence["basis"] = "COUNTER_PARENT_FIRST_EMA9_RETURN"
            return {"kind": "EMA9_RETURN", "btc": e9, "tolerance": tolerance,
                "reference_source_ms": source, "box_id": box.get("box_id"),
                "frozen_at_entry": True}, evidence, None
        evidence["basis"] = "CURRENT_PARENT_ALIGNED_BOX_RETURN"
    elif neutral:
        evidence["basis"] = "OBSERVED_NEUTRAL_BOX_OPPOSITE_WALL"
    else:
        return {}, evidence, "TACTICAL_CURRENT_EMA9_DIRECTION_MIXED"
    return {"kind": "BOX_EDGE", "btc": upper if side == "YES" else lower,
        "tolerance": box.get("edge_tolerance"), "reference_source_ms": source,
        "box_id": box.get("box_id"), "frozen_at_entry": True}, evidence, None




def _strict_heist_outer_wall(snapshot: MarketSnapshot, side: str, box: Mapping, source: float | None) -> bool:
    """A detector-qualified repeatable Heist wall is not a generic parent fade.

    The live PID19792 miss proved that a genuine repeated tight/compressed box
    can temporarily disagree with the local parent direction.  Once the box
    itself is current, repeatable and at the exact wall being bought, that wall
    is the physical mission.  This never licenses an unqualified tactical fade.
    """
    if source is None or side not in ("YES", "NO"):
        return False
    proof = _map(box.get("repeatability_proof"))
    lower, upper = _num(box.get("lower")), _num(box.get("upper"))
    correct_edge = box.get("at_lower_edge" if side == "YES" else "at_upper_edge") is True
    wrong_edge = box.get("at_upper_edge" if side == "YES" else "at_lower_edge") is True
    return bool(
        snapshot.metadata.get("physical_current") is True
        and box.get("qualified_box") is True
        and box.get("release_confirmed") is not True
        and bool(box.get("box_id"))
        and lower is not None and upper is not None and upper > lower
        and _num(proof.get("lower")) in (None, lower) and _num(proof.get("upper")) in (None, upper)
        and correct_edge and not wrong_edge
        and proof.get("source") == "OBSERVED_HEIST_REPEATABILITY_V1"
        and proof.get("tight_box") is True
        and proof.get("heist_environment") is True
        and (proof.get("compression") is True or proof.get("parallel_emas") is True)
        and _num(proof.get("window_end_ms")) == source
        and (_num(proof.get("lower_visits")) or 0) >= 2
        and (_num(proof.get("upper_visits")) or 0) >= 2
        and (_num(proof.get("center_traversals")) or 0) >= 1
    )


def _strict_rail_child_arc_value(intent: ToolIntent, snapshot: MarketSnapshot) -> bool:
    """Revalidate the narrow cheap child-arc rider inside an established Rail.

    This does not transfer Rail ownership.  It permits one local opposite leg
    only when the current child arc itself is mature, slow enough to be real,
    non-release, very cheap, and still has more than five minutes to work.
    """
    proof = _map(intent.metadata.get("rail_child_arc_value"))
    if not proof or intent.side is None or intent.tool not in ("ALTERNATING_MOUNTAIN", "ROLLING_MOUNTAIN"):
        return False
    mountain = _map(snapshot.metadata.get("mountain"))
    diagnostics = _map(mountain.get("diagnostics"))
    source = _num(mountain.get("source_ms"))
    geometry_source = _num(snapshot.metadata.get("geometry_last_epoch_ms"))
    rail_side = str(proof.get("rail_side") or "")
    owner_side = str(mountain.get("owner_side") or "")
    child_arc = str(mountain.get("current_arc_id") or "")
    ask = _num(snapshot.ask_for(intent.side))
    terminal_cue = bool(
        mountain.get("stall") is True or mountain.get("hesitation") is True
        or mountain.get("failed_reextension") is True or mountain.get("meaningful_retreat") is True
        or mountain.get("comparable_slow_edge") is True
        or _map(mountain.get("paired_gap_evidence")).get("eligible") is True
    )
    return bool(
        snapshot.metadata.get("physical_current") is True
        and source is not None and geometry_source == source
        and _num(proof.get("source_ms")) == source
        and child_arc and proof.get("child_arc_id") == child_arc
        and rail_side in ("YES", "NO") and owner_side == rail_side
        and intent.side.value != rail_side
        and mountain.get("mature_edge") is True and terminal_cue
        and mountain.get("strong_active_release") is not True
        and mountain.get("spent_edge") is not True
        and (_num(diagnostics.get("current_age_s")) or 0) >= 120.0
        and (900.0 - snapshot.contract_age_s) > 300.0
        and ask is not None and 0 < ask <= 0.16
        and _num(proof.get("max_ask")) == 0.16
    )


@dataclass(frozen=True)
class MissionPolicyConfig:
    minimum_gross_roi: float = .40
    quote_response_window_s: float = 180.
    minimum_response_pairs: int = 3

    def __post_init__(self) -> None:
        if (not math.isfinite(self.minimum_gross_roi) or not 0 <= self.minimum_gross_roi <= 20
                or not math.isfinite(self.quote_response_window_s) or self.quote_response_window_s <= 0
                or type(self.minimum_response_pairs) is not int or self.minimum_response_pairs < 2):
            raise ValueError("INVALID_MISSION_POLICY_CONFIG")

    @classmethod
    def load(cls) -> "MissionPolicyConfig":
        return cls(**json.loads((Path(__file__).with_name("config") / "mission.json").read_text(encoding="utf-8")))


class MissionPolicy:
    def __init__(self, config: MissionPolicyConfig | None = None) -> None:
        self.config = config or MissionPolicyConfig.load()
        self._quotes: deque[dict] = deque(maxlen=2048)
        self._quote_identity: tuple | None = None
        self._ticker = ""
        self._generation: int | None = None
        self._paid_main: set[tuple[str, str, str]] = set()
        # One non-neutral counterfade per observed parent/side.  A new quote,
        # child arc id, tool label or contract rollover does not manufacture a
        # second paid attempt against the same living parent.  Genuine neutral
        # Heist edge visits keep their own repeatable box identities.
        self._paid_tactical_parent: set[tuple[str, str]] = set()
        self.reviews: list[dict] = []

    def observe(self, snapshot: MarketSnapshot) -> None:
        md = snapshot.metadata
        generation = md.get("geometry_continuity_generation")
        if snapshot.ticker != self._ticker or generation != self._generation:
            self._quotes.clear()
            self._quote_identity = None
            self._ticker, self._generation = snapshot.ticker, generation
        self.reviews = []
        while self._quotes and self._quotes[0]["time"] < snapshot.now_ts - self.config.quote_response_window_s:
            self._quotes.popleft()
        geometry = _map(md.get("current_geometry"))
        source, quote_time = _num(geometry.get("epoch_ms")), _num(md.get("quote_observed_ts"))
        btc = _num(geometry.get("btc_price"))
        if (not snapshot.quote_current or not snapshot.entry_allowed or md.get("physical_current") is not True
                or source is None or quote_time is None or btc is None
                or not current_source_is_fresh(snapshot, source, max_age_seconds=3.)
                or not 0 <= snapshot.now_ts - quote_time <= 3):
            return
        identity = (snapshot.ticker, md.get("quote_id"))
        if identity == self._quote_identity or not identity[1]:
            return
        native = _map(md.get("native_depth"))
        if native.get("ticker") != snapshot.ticker or native.get("quote_id") != identity[1]:
            return
        self._quote_identity = identity
        self._quotes.append({"time": snapshot.now_ts, "quote_time": quote_time,
            "source_ms": source, "quote_id": identity[1], "btc": btc,
            "YES": _levels(native.get("yes_bids")), "NO": _levels(native.get("no_bids"))})
        while self._quotes and self._quotes[0]["time"] < snapshot.now_ts - self.config.quote_response_window_s:
            self._quotes.popleft()


    def quote_wave_briefing(self, snapshot: MarketSnapshot, *, lookback_s: float = 60.0) -> dict:
        """Advisory exact-contract quote oscillation briefing. Never creates direction.

        Asks are reconstructed from the complementary native binary bid book,
        preserving the same exact-contract executable source used by PAPER.
        """
        cutoff = snapshot.now_ts - max(1.0, float(lookback_s))
        points = [p for p in self._quotes if p.get("time", 0) >= cutoff]
        result: dict[str, Any] = {"version": "QUOTE_WAVE_BRIEFING_V1",
            "ticker": snapshot.ticker, "lookback_s": lookback_s,
            "observed_points": len(points), "sides": {}}
        for side in (Side.YES, Side.NO):
            opposite = Side.NO if side is Side.YES else Side.YES
            series = []
            for point in points:
                own = point.get(side.value) or ()
                opp = point.get(opposite.value) or ()
                if not own or not opp:
                    continue
                best_bid = max((float(lv.price) for lv in own), default=None)
                opp_bid = max((float(lv.price) for lv in opp), default=None)
                if best_bid is None or opp_bid is None:
                    continue
                ask = 1.0 - opp_bid
                if 0 < ask < 1 and 0 < best_bid < 1:
                    series.append({"time": float(point["time"]), "ask": ask, "bid": best_bid,
                        "quote_id": point.get("quote_id"), "btc": point.get("btc")})
            if not series:
                result["sides"][side.value] = {"available": False}
                continue
            asks = [x["ask"] for x in series]
            # Revisit/cycle counts are descriptive summaries only; Commander
            # applies the separately authorized cheap/reprice thresholds.
            result["sides"][side.value] = {"available": True,
                "samples": len(series), "current_ask": series[-1]["ask"],
                "current_bid": series[-1]["bid"], "low_ask": min(asks),
                "high_ask": max(asks), "ask_range": max(asks)-min(asks),
                "series": series[-64:]}
        return result

    def tactical_economics(self, intent: ToolIntent, snapshot: MarketSnapshot,
                           destination: Mapping) -> dict:
        side = intent.side
        result: dict[str, Any] = {"status": "UNASSESSED", "minimum_gross_roi": self.config.minimum_gross_roi,
            "entry_ask": None, "best_ask": snapshot.ask_for(side) if side else None,
            "required_exit_bid": None, "estimated_exit_bid": None, "gross_roi": None,
            "net_after_fees": None, "quantity": None, "future_exit_depth_proven": False,
            "entry_depth_proven": False, "automatic_take_profit": False,
            "estimate_method": "EXACT_CONTRACT_OBSERVED_FULL_LOT_BID_RESPONSE_SCENARIO",
            "uncertainty": "Uncalibrated conditional response; future price, duration and liquidity can differ.",
            "fee_model": "NOMINAL_0.07_CEIL_CENT_PAPER_ASSUMPTION",
            "reason": "TACTICAL_RETURN_SCENARIO_UNAVAILABLE"}
        if side is None or not self._quotes or not snapshot.quote_current or not snapshot.entry_allowed:
            return result
        current = self._quotes[-1]
        if (current["quote_id"] != snapshot.metadata.get("quote_id") or self._ticker != snapshot.ticker
                or not 0 <= snapshot.now_ts - current["time"] <= 3):
            return result
        budget, limit = _num(intent.size_tier), _num(intent.max_price)
        if budget is None or budget <= 0 or limit is None or not 0 < limit < 1:
            return result
        cash = _num(snapshot.metadata.get("available_paper_cash"))
        budget = min(budget, cash) if cash is not None else budget
        opposite = Side.NO if side is Side.YES else Side.YES
        asks = tuple(PriceLevel(float(Decimal(1) - Decimal(str(lv.price))), lv.quantity)
                     for lv in current[opposite.value])
        if not asks or not current[side.value]:
            return result
        low, high, purchase = 1, min(sum(int(lv.quantity) for lv in asks if lv.price <= limit), 100000), None
        while low <= high:
            qty = (low + high) // 2
            trial = _sweep(asks, qty, buy=True, limit=Decimal(str(limit)))
            if (trial and trial["qty"] == qty and trial["amount"]
                    + nominal_taker_fee(qty, trial["price"]) <= Decimal(str(budget))):
                purchase, low = trial, qty + 1
            else:
                high = qty - 1
        if purchase is None:
            result["reason"] = "TACTICAL_ENTRY_DEPTH_OR_AFFORDABLE_LOT_UNAVAILABLE"
            return result
        quantity = purchase["qty"]
        entry = float(purchase["price"])
        current_bid = _sweep(current[side.value], quantity, buy=False)
        result.update(quantity=quantity, entry_ask=entry, entry_depth_proven=True,
            required_exit_bid=float(purchase["price"] * (1 + Decimal(str(self.config.minimum_gross_roi)))))
        if not current_bid or not current_bid["full_quantity_visible"]:
            result["reason"] = "TACTICAL_CURRENT_FULL_LOT_BID_UNAVAILABLE"
            return result
        target = _num(destination.get("btc"))
        tolerance = _num(destination.get("tolerance"))
        sign = 1 if side is Side.YES else -1
        if (destination.get("kind") not in ("EMA9_RETURN", "BOX_EDGE")
                or target is None or tolerance is None or tolerance < 0):
            result["reason"] = "TACTICAL_PHYSICAL_DESTINATION_NOT_VERIFIED"
            return result
        # The held-mission manager may collect at the near edge of this
        # frozen destination band. Do not sell the entry on economics from
        # the farther center of that band: that untraded tail is not part of
        # the minimum prospective return. This also excludes a new return
        # whose collection band already contains the current physical price.
        boundary = target - sign * tolerance
        nominal_distance = (target - current["btc"]) * sign
        distance = (boundary - current["btc"]) * sign
        result.update(destination=dict(destination), destination_tolerance=tolerance,
            nominal_destination_distance=nominal_distance,
            collection_boundary_btc=boundary, physical_distance=distance,
            projection_destination_basis="EARLIEST_COLLECTIBLE_DESTINATION_BOUNDARY")
        if distance <= 0:
            result["reason"] = "TACTICAL_PHYSICAL_COLLECTION_BAND_ALREADY_REACHED"
            return result
        # Pair samples over an actually observed movement, using the existing
        # physical contact width to avoid dividing by quote/price twitch noise.
        mountain = _map(snapshot.metadata.get("mountain"))
        width = max(.01, _num(mountain.get("contact_width")) or 3.)
        pairs, anchors = [], []
        for point in self._quotes:
            sale = _sweep(point[side.value], quantity, buy=False)
            if not sale or not sale["full_quantity_visible"]:
                continue
            p = {**point, "bid": float(sale["price"])}
            if not anchors:
                anchors.append(p)
                continue
            previous = anchors[-1]
            physical_move = sign * (p["btc"] - previous["btc"])
            dt = p["time"] - previous["time"]
            if abs(physical_move) < width or dt <= 0:
                continue
            # Negative response pairs are retained; filtering only profitable
            # responses would bias the admission estimate upward.
            pairs.append({"slope": (p["bid"] - previous["bid"]) / physical_move,
                "speed": abs(physical_move) / dt, "move": abs(physical_move),
                "start_quote_id": previous["quote_id"], "end_quote_id": p["quote_id"],
                "start_ts": previous["time"], "end_ts": p["time"]})
            anchors.append(p)
        result.update(response_pair_count=len(pairs), physical_distance=distance,
            response_window_seconds=self.config.quote_response_window_s,
            observed_history_start=self._quotes[0]["time"], observed_history_end=current["time"],
            current_full_lot_bid=float(current_bid["price"]), destination=dict(destination))
        if len(pairs) < self.config.minimum_response_pairs:
            result["reason"] = "TACTICAL_INSUFFICIENT_EXACT_CONTRACT_PRICE_RESPONSE"
            return result
        slopes = sorted(p["slope"] for p in pairs)
        response = slopes[(len(slopes) - 1) // 4]
        speed = median(p["speed"] for p in pairs)
        observed_range = max(p["btc"] for p in anchors) - min(p["btc"] for p in anchors)
        supported_distance = min(distance, observed_range)
        close_ts = _num(_map(snapshot.metadata.get("contract_value_context")).get("close_ts"))
        remaining = close_ts - snapshot.now_ts if close_ts is not None else 900 - snapshot.contract_age_s
        seconds = distance / speed if speed > 0 else None
        result.update(bid_response_per_btc=response, response_quantile=.25,
            supported_projection_distance=supported_distance, scenario_duration_seconds=seconds,
            remaining_seconds=remaining, response_evidence=pairs[-4:])
        if response <= 0 or supported_distance <= 0 or seconds is None or seconds >= remaining:
            result["reason"] = "TACTICAL_RESPONSE_OR_REMAINING_TIME_INSUFFICIENT"
            return result
        estimated = min(.9999, float(current_bid["price"]) + response * supported_distance)
        # Round the prospective sale down, preserving the writer's adverse
        # direction. The projected depth is explicitly not proven future depth.
        estimated = math.floor(estimated * 10000 + 1e-9) / 10000
        gross = (estimated - entry) / entry
        fees = nominal_taker_fee(quantity, purchase["price"]) + nominal_taker_fee(quantity, estimated)
        net = Decimal(str(estimated)) * quantity - purchase["amount"] - fees
        passed = gross + 1e-12 >= self.config.minimum_gross_roi and net > 0
        result.update(status="SCENARIO_PASSES" if passed else "BELOW_THRESHOLD",
            estimated_exit_bid=estimated, gross_roi=gross, net_after_fees=float(net),
            estimated_round_trip_fees=float(fees),
            reason="TACTICAL_SUBSTANTIAL_RETURN_SCENARIO" if passed else "TACTICAL_SWING_BELOW_GROSS_OR_NET_HURDLE")
        return result

    def review(self, intent: ToolIntent, snapshot: MarketSnapshot) -> ToolIntent:
        if intent.action not in (Action.ENTER, Action.RELAY) or intent.side is None:
            return intent
        if intent.tool in ("ALTERNATING_MOUNTAIN", "ROLLING_MOUNTAIN"):
            terminal_direct = bool(
                intent.reason in ("MOUNTAIN_TERMINAL_EMA9_EDGE_RELAY",
                                  "MOUNTAIN_TERMINAL_EDGE_SUB20_VALUE_RELAY")
                and _map(intent.metadata.get("terminal_evidence")).get("qualified") is True)
            cheap_hover_direct = bool(
                intent.reason == "MOUNTAIN_CHEAP_HOVER_EDGE_RELAY"
                and intent.metadata.get("cheap_hover_edge") is True)
            small_fast_direct = bool(
                intent.reason == "MOUNTAIN_SMALL_FAST_ARC_EDGE_RELAY"
                and intent.metadata.get("small_fast_arc_edge") is True)
            armed_value_direct = bool(
                intent.reason in ("MOUNTAIN_ARMED_EDGE_SUB20_VALUE_ENTRY",
                                  "MOUNTAIN_WIDE_TOP_PATIENT_VALUE_ENTRY",
                                  "MOUNTAIN_LOW_WIDE_SIDEWAYS_VALUE_ENTRY")
                and _map(intent.metadata.get("armed_edge_value")).get("edge_id"))
            fast_bridge_direct = bool(
                intent.reason == "MOUNTAIN_FAST_NARROW_EDGE_PREENTRY_BRIDGE"
                and _map(intent.metadata.get("fast_handoff_bridge")).get("outgoing_position_id")
                and _map(intent.metadata.get("terminal_evidence")).get("qualified") is True)
            rollover_value_direct = bool(
                intent.reason == "MOUNTAIN_INHERITED_EDGE_CHEAP_ROLLOVER_ENTRY"
                and _map(intent.metadata.get("rollover_inherited_edge")).get("edge_id"))
            if (terminal_direct or cheap_hover_direct or small_fast_direct
                    or armed_value_direct or rollover_value_direct or fast_bridge_direct):
                # The Mountain tool has already earned this mission from current
                # EMA9 geometry.  A terminal edge may be filled immediately or
                # remain armed while the native binary pulls back to its terrain-specific value window;
                # the latter must not be forced to reproduce the original crest
                # on the fill tick.  Rollover value is likewise inherited from
                # the exact skipped edge. Contract thesis/history and EMA30 are
                # telemetry, never a second strategy veto.
                authority = ("MOUNTAIN_FAST_PREENTRY_BRIDGE_DIRECT_AUTHORITY" if fast_bridge_direct
                    else "MOUNTAIN_ARMED_VALUE_DIRECT_AUTHORITY" if armed_value_direct
                    else "MOUNTAIN_ROLLOVER_VALUE_DIRECT_AUTHORITY" if rollover_value_direct
                    else "MOUNTAIN_CHEAP_HOVER_DIRECT_AUTHORITY" if cheap_hover_direct
                    else "MOUNTAIN_SMALL_FAST_ARC_DIRECT_AUTHORITY" if small_fast_direct
                    else "MOUNTAIN_TERMINAL_EDGE_DIRECT_AUTHORITY")
                advice = {"tool": intent.tool, "side": intent.side.value,
                    "purpose": "EMA9_EDGE_VALUE", "classification": "MOUNTAIN_EDGE",
                    "decision": "ELIGIBLE", "reason": authority,
                    "parent_leg_id": None,
                    "swing_id": (intent.metadata.get("edge_id")
                        or _map(intent.metadata.get("armed_edge_value")).get("edge_id")
                        or _map(intent.metadata.get("rollover_inherited_edge")).get("edge_id")),
                    "economics": None, "authority": "ADVISORY_ONLY"}
                self.reviews.append(advice)
                role = intent.metadata.get("position_role") if fast_bridge_direct else "PRIMARY"
                return replace(intent,
                    metadata={**intent.metadata, "position_role": role,
                              "mission_policy_advice": advice})
        context = _map(snapshot.metadata.get("mission_context"))
        if (intent.tool == "RAIL"
                and intent.reason in {"RAIL_MAIN_VALUE", "RAIL_EMA9_DIP_VALUE"}
                and intent.metadata.get("parent_scale_rail_authority") is True):
            # Parent-scale Rail may outrank advisory thesis only when the
            # physical chapter also has complete causal target/history
            # provenance.  A local Rail label must never bootstrap a paid
            # entry from missing or future-known context.
            contract0 = _map(context.get("contract"))
            reference0 = _map(contract0.get("reference_window"))
            provenance_ready = bool(
                contract0.get("target") is not None
                and contract0.get("history_status") == "READY"
                and (_num(reference0.get("completed_prior_contracts")) or 0) >= 2
            )
            if provenance_ready:
                advice = {"tool": intent.tool, "side": intent.side.value,
                    "purpose": ("PARENT_SCALE_RAIL_EMA9_DIP_VALUE" if intent.reason == "RAIL_EMA9_DIP_VALUE"
                                else "PARENT_SCALE_RAIL_VALUE"),
                    "classification": ("RAIL_EMA9_DIP_VALUE" if intent.reason == "RAIL_EMA9_DIP_VALUE"
                                       else "RAIL_PARENT_VALUE"),
                    "decision": "ELIGIBLE", "reason": "PARENT_SCALE_RAIL_DIRECT_AUTHORITY",
                    "parent_leg_id": None, "swing_id": intent.opportunity_id,
                    "economics": None, "authority": "ADVISORY_ONLY"}
                self.reviews.append(advice)
                return replace(intent,
                    metadata={**intent.metadata, "position_role": "PRIMARY",
                              "mission_policy_advice": advice})
        # Legacy isolated tool fixtures can still exercise the tool itself.
        # Production explicitly supplies a versioned context, including an
        # unavailable context; missing production context never grants entry.
        if not context and snapshot.metadata.get("source") != "DIRECT_BTC_AND_NATIVE_KALSHI":
            return intent
        side = intent.side.value
        candidate = _map(_map(context.get("candidates")).get(side))
        parent = _map(context.get("parent"))
        contract = _map(context.get("contract"))
        classification = candidate.get("classification", "UNRESOLVED")
        source = _num(context.get("source_ms"))
        qualified = candidate.get("qualified_edge") is True
        wants_arc = classification == "PARENT_EDGE_RETURN"
        arc_return = qualified_full_arc_candidate(context, side, source)
        arc_ask = _num(snapshot.ask_for(intent.side)) if arc_return else None
        thesis_main = contract.get("thesis_side") == side and classification == "MAIN_CONTINUATION"
        physical_parent_side = parent.get("side") if parent.get("side") in ("YES", "NO") else None
        reference_window = _map(contract.get("reference_window"))
        rail_provenance_ready = bool(
            contract.get("target") is not None
            and contract.get("history_status") == "READY"
            and (_num(reference_window.get("completed_prior_contracts")) or 0) >= 2
        )
        physical_rail_main = bool(
            intent.tool == "RAIL"
            and classification == "MAIN_CONTINUATION"
            and physical_parent_side == side
            and candidate.get("continuation_supported") is True
            and candidate.get("entry_location_qualified") is True
            and rail_provenance_ready
        )
        # Conditional/history thesis is advisory once the current Rail has
        # complete causal provenance.  A fresh process with missing history or
        # exact target may not bootstrap permission from a raw Rail label.
        main = thesis_main or physical_rail_main
        parent_mission = main or arc_return
        box = _map(snapshot.metadata.get("heist"))
        box_proof = _map(box.get("repeatability_proof"))
        box_current = (intent.tool == "MARKET_HEIST" and box.get("qualified_box") is True
            and box.get("release_confirmed") is not True and bool(box.get("box_id"))
            and intent.metadata.get("box_id") == box.get("box_id")
            and box.get("at_lower_edge" if side == "YES" else "at_upper_edge") is True
            and box.get("at_upper_edge" if side == "YES" else "at_lower_edge") is not True
            and source is not None and _num(box_proof.get("window_end_ms")) == source)
        strict_heist_wall = bool(box_current and _strict_heist_outer_wall(snapshot, side, box, source))
        heist_diag = _map(box.get("diagnostics"))
        parallel_return_proof = _map(intent.metadata.get("parallel_return_evidence"))
        parallel_heist_return = bool(
            intent.tool == "MARKET_HEIST"
            and intent.metadata.get("parallel_return_entry") is True
            and parallel_return_proof.get("parallel_environment") is True
            and parallel_return_proof.get("return_confirmed") is True
            and heist_diag.get("heist_environment") is True
            and heist_diag.get("parallel_emas") is True
            and box.get("release_confirmed") is not True
            and snapshot.metadata.get("release_in_progress") is not True
            and source is not None
            and _num(parallel_return_proof.get("source_ms")) == source
            and intent.metadata.get("box_id") == box.get("box_id")
            and _num(box.get("lower")) is not None
            and _num(box.get("upper")) is not None
            and _num(box.get("upper")) > _num(box.get("lower"))
            and ((side == "NO" and parallel_return_proof.get("armed_zone") == "UPPER")
                 or (side == "YES" and parallel_return_proof.get("armed_zone") == "LOWER"))
        )
        rail_child_value = _strict_rail_child_arc_value(intent, snapshot)
        if box_current:
            qualified = True
            if not parent_mission and not wants_arc:
                classification = "BOX_RETURN"
        if parallel_heist_return:
            qualified = True
            if not parent_mission and not wants_arc:
                classification = "PARALLEL_HEIST_RETURN"
        if rail_child_value:
            qualified = True
            classification = "RAIL_CHILD_ARC_VALUE"
        purpose = "ARC_RETURN" if wants_arc else "MAIN_CONTRACT" if main else "TACTICAL_RETURN"
        reason = None
        if (context.get("current") is not True or source is None
                or not current_source_is_fresh(snapshot, source, max_age_seconds=3.)
                or wants_arc and snapshot.metadata.get("physical_current") is not True):
            reason = "MISSION_CURRENT_PHYSICAL_CONTEXT_REQUIRED"
        elif wants_arc and not arc_return:
            reason = "ARC_RETURN_REQUIRES_CURRENT_PARENT_EDGE"
        elif arc_return and (arc_ask is None or not 0 < arc_ask < 1):
            reason = "ARC_RETURN_CURRENT_ASK_REQUIRED"
        elif classification == "UNRESOLVED":
            reason = "MISSION_PHYSICAL_PURPOSE_UNRESOLVED"
        # A local box edge cannot grant a parent-leg MAIN entry zone.
        elif main and candidate.get("entry_location_qualified") is not True:
            reason = "MAIN_ENTRY_REQUIRES_CURRENT_PHYSICAL_VALUE_LOCATION"
        elif not parent_mission and not qualified:
            reason = "MISSION_LOCAL_TURN_REQUIRES_QUALIFIED_SWING_EDGE"
        elif intent.tool == "RAIL" and (not main or candidate.get("continuation_supported") is not True):
            reason = "RAIL_FRESH_ENTRY_REQUIRES_CURRENT_CONTINUATION_THESIS"
        parent_id = candidate.get("parent_leg_id") or parent.get("id")
        local = _map(context.get("local"))
        swing_id = str(candidate.get("swing_id")
                       or local.get("arc_id") or intent.opportunity_id)
        destination = dict(_map(candidate.get("destination")))
        destination_evidence = None
        if intent.tool == "MARKET_HEIST" and not parent_mission:
            if parallel_heist_return:
                destination = {"kind": "BOX_EDGE",
                    "btc": _num(box.get("upper")) if side == "YES" else _num(box.get("lower")),
                    "tolerance": _num(box.get("edge_tolerance")),
                    "reference_source_ms": source, "box_id": box.get("box_id"),
                    "frozen_at_entry": True}
                destination_evidence = {"version": "PARALLEL_HEIST_RETURN_V1",
                    "basis": "OBSERVED_PARALLEL_EXCURSION_RETURN_TO_OPPOSITE_WALL",
                    "source_ms": source, "box_id": box.get("box_id"),
                    "return_evidence": dict(parallel_return_proof)}
            elif strict_heist_wall:
                destination = {"kind": "BOX_EDGE",
                    "btc": _num(box.get("upper")) if side == "YES" else _num(box.get("lower")),
                    "tolerance": _num(box.get("edge_tolerance")),
                    "reference_source_ms": source, "box_id": box.get("box_id"),
                    "frozen_at_entry": True}
                destination_evidence = {"version": "STRICT_HEIST_WALL_V1",
                    "basis": "OBSERVED_STRICT_REPEATABLE_HEIST_OPPOSITE_WALL",
                    "source_ms": source, "box_id": box.get("box_id"),
                    "repeatability_proof": dict(box_proof)}
            else:
                destination, destination_evidence, destination_reason = _heist_return_destination(
                    snapshot, side, context, box)
                reason = reason or destination_reason
        neutral_heist = bool(strict_heist_wall or parallel_heist_return or destination_evidence
            and destination_evidence.get("basis") == "OBSERVED_NEUTRAL_BOX_OPPOSITE_WALL")
        mountain_now = _map(snapshot.metadata.get("mountain"))
        parent_side = parent.get("side") if parent.get("side") in ("YES", "NO") else None
        counter_parent = bool(not parent_mission and parent_id and parent_side and side != parent_side
                              and not neutral_heist)
        mission = {"version": VERSION, "purpose": purpose, "side": side,
            "parent_leg_id": parent_id, "swing_id": swing_id,
            "source_ms": source, "continuity_generation": context.get("continuity_generation"),
            "classification": classification,
            "target_kind": "PARENT_TERMINAL" if parent_mission else "SWING_DESTINATION",
            "destination": {"kind": "PARENT_TERMINAL"} if parent_mission else destination,
            "contract_thesis_at_entry": contract.get("thesis_side"),
            "contract_thesis_reason": contract.get("reason"),
            "scope_status_at_entry": candidate.get("scope_status", parent.get("status")),
            "neutral_heist_repeatable": neutral_heist,
            "strict_heist_outer_wall": strict_heist_wall,
            "parallel_heist_return": parallel_heist_return,
            "rail_child_arc_value": rail_child_value,
            "counter_parent_fade": counter_parent}
        source_receipt = current_source_receipt(snapshot, source, max_age_seconds=3.)
        if source_receipt is not None:
            mission["source_receipt"] = source_receipt
        if parent_mission:
            mission["collection_policy"] = "THIRD_DISTINCT_WEAKNESS_V1"
        else:
            # Only future entries receive this collection contract. Restored
            # historical lots retain the immutable policy in their ledger.
            mission["collection_policy"] = TACTICAL_COLLECTION_POLICY
            if destination_evidence is not None:
                mission["destination_evidence"] = destination_evidence
        main_key = (snapshot.ticker, str(parent_id), side)
        if parent_mission and (not parent_id or main_key in self._paid_main):
            prefix = "ARC" if arc_return else "MAIN"
            reason = f"{prefix}_PHYSICAL_LEG_SLICE_ALREADY_PAID" if parent_id else f"{prefix}_PARENT_ID_REQUIRED"
        economics = None
        if reason is None and not parent_mission:
            if counter_parent and not rail_child_value:
                # Corrective governance: ordinary counter-parent fades are
                # completely paused. Strict Heist walls and the narrowly
                # revalidated Rail child-arc value rider are explicit physical
                # missions, not generic fades.
                reason = "TACTICAL_FADES_PAUSED"
            elif strict_heist_wall or parallel_heist_return or rail_child_value:
                # These current physical setups are already fully bounded by
                # their detector proof and native entry price. Historical
                # tactical-return response estimates must not veto them.
                economics = None
            else:
                economics = self.tactical_economics(intent, snapshot, destination)
                if economics["status"] != "SCENARIO_PASSES":
                    reason = economics["reason"]
        meta = {**intent.metadata, "position_role": "PRIMARY" if parent_mission else "TACTICAL", "mission": mission}
        if source_receipt is not None:
            meta["entry_source_receipt"] = source_receipt
        if parent_mission and parent_id:
            meta["physical_mission_id"] = f"{'ARC' if arc_return else 'MAIN'}:{parent_id}:{side}"
            handoff = _map(meta.get("mountain_handoff"))
            if handoff:
                # Preserve edge, source and exact outgoing-lot proof while
                # binding Commander to the same reviewed incoming mission.
                meta["mountain_handoff"] = {**handoff,
                    "physical_mission_id": meta["physical_mission_id"]}
        if economics is not None:
            meta["tactical_economics"] = economics
        elif arc_return:
            # This purpose buys the next whole leg. Do not leave a prior
            # local-pullback estimate attached after a re-reviewed handoff.
            meta.pop("tactical_economics", None)
            mission["entry_policy"] = "BLIND_FULL_ARC_EDGE_V1"
            mission["ema_direction_veto"] = False
            mission["tactical_roi_required"] = False
        review = {"tool": intent.tool, "side": side, "purpose": purpose,
            "classification": classification, "decision": "WAIT" if reason else "ELIGIBLE",
            "reason": reason or ("ARC_RETURN_PHYSICAL_EDGE_QUALIFIED" if arc_return
                                 else "STRICT_HEIST_OUTER_WALL_QUALIFIED" if strict_heist_wall
                                 else "RAIL_CHILD_ARC_VALUE_QUALIFIED" if rail_child_value
                                 else "MISSION_PURPOSE_AND_CURRENT_ECONOMICS_QUALIFIED"),
            "parent_leg_id": parent_id, "swing_id": swing_id, "economics": economics}
        review["authority"] = "ADVISORY_ONLY"
        self.reviews.append(review)
        # MissionPolicy may classify, estimate economics, and describe why it
        # would prefer WAIT, but it cannot mutate the adviser's proposed
        # action, lane, or executable price before OneCommander reviews it.
        # Preserve mission identity/provenance in metadata for Commander,
        # anti-spray, and later forensic analysis.
        meta["mission_policy_advice"] = dict(review)
        # An unassessed scenario deliberately has no prospective exit price.
        # Keep its diagnostic reason without manufacturing a numeric ceiling
        # or carrying a suggestion from an earlier review of this intent.
        meta.pop("mission_policy_suggested_max_price", None)
        if economics is not None:
            estimated_exit_bid = _num(economics.get("estimated_exit_bid"))
            if estimated_exit_bid is not None:
                meta["mission_policy_suggested_max_price"] = (
                    estimated_exit_bid / (1 + self.config.minimum_gross_roi)
                )
        elif arc_return and arc_ask is not None:
            meta["mission_policy_suggested_max_price"] = arc_ask
        return replace(intent, metadata=meta)

    def committed(self, intent: ToolIntent, ticker: str) -> None:
        mission = _map(intent.metadata.get("mission"))
        if mission.get("purpose") in PARENT_MISSION_PURPOSES and intent.side is not None:
            self._paid_main.add((ticker, str(mission.get("parent_leg_id")), intent.side.value))
        elif (mission.get("purpose") == "TACTICAL_RETURN" and intent.side is not None
              and mission.get("counter_parent_fade") is True
              and mission.get("neutral_heist_repeatable") is not True
              and mission.get("parent_leg_id")):
            self._paid_tactical_parent.add((str(mission.get("parent_leg_id")), intent.side.value))

    def carry_paid_holding_links(self, context: Mapping[str, Any], ticker: str) -> None:
        """A holding bridge carries an existing paid latch; it creates none."""
        if context.get("current") is not True:
            return
        source = _num(context.get("source_ms"))
        parents = _map(context.get("parents_by_id"))
        for raw in _map(context.get("reacquisition_review")).get("links_created") or ():
            link = _map(raw)
            previous, target, side = link.get("from_id"), link.get("to_id"), link.get("side")
            node, next_node = _map(parents.get(previous)), _map(parents.get(target))
            known = _num(link.get("known_ms"))
            valid_link = bool(side in ("YES", "NO") and isinstance(target, str) and target and target != previous
                    and node.get("reacquired_by_parent_id") == target
                    and node.get("side") == next_node.get("side") == side
                    and next_node.get("id") == target
                    and link.get("renews_entry_permission") is False
                    and link.get("creates_terminal") is False
                    and source is not None and known is not None and 0 < known <= source
                    and _num(link.get("source_ms")) == known)
            if valid_link and (ticker, previous, side) in self._paid_main:
                self._paid_main.add((ticker, target, side))
            if valid_link:
                for tactical_side in ("YES", "NO"):
                    if (str(previous), tactical_side) in self._paid_tactical_parent:
                        self._paid_tactical_parent.add((target, tactical_side))
