from __future__ import annotations

from strategy_core.source_freshness import current_source_is_fresh

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from strategy_core.tools.base import StrategyTool
from strategy_core.commander_candidates import settlement_runway_for_side
from strategy_core.tools.management import (
    as_side, floor_policy, opposing_transfer, ordinary_profit_hold_reason, position_intent, rack_context,
    mission_collection_evidence, mapping, number,
)
from strategy_core.types import (
    Action,
    Lane,
    MarketSnapshot,
    Side,
    ToolIntent,
)


def _side(value: Any) -> Side | None:
    if isinstance(value, Side):
        return value
    if value is None:
        return None
    text = str(value).upper()
    if text == "YES":
        return Side.YES
    if text == "NO":
        return Side.NO
    return None


@dataclass(frozen=True)
class HeistConfig:
    regular_size: float = 10.0
    lean_favored_size: float = 15.0
    soft_max_price: float = 0.30
    wide_normal_max_price: float = 0.30
    wide_exceptional_max_price: float = 0.35
    release_ends_box_immediately: bool = True
    parallel_profit_arm_roi: float = 0.40
    parallel_profit_trail_fraction: float = 0.03
    late_counter_window_s: float = 60.0
    late_counter_max_ask: float = 0.01
    floor_arm_roi: float = 0.40
    floor_trail_fraction: float = 0.03
    floor_min_age_s: float = 30.0
    floor_immediate_arm_roi: float | None = None


class MarketHeistTool(StrategyTool):
    """Repeated edge-to-edge business inside a genuine compression box."""

    name = "MARKET_HEIST"

    def __init__(
        self,
        *,
        territory_id: str,
        config: HeistConfig | None = None,
    ) -> None:
        self.territory_id = territory_id
        self.config = config or HeistConfig()
        self._active = True
        self._current_ticker: str | None = None
        self._open_tickers: set[str] = set()
        self._filled_opportunities: set[tuple[str, str]] = set()
        self._visit_side: Side | None = None
        self._visit_id: str | None = None
        self._center_since_visit = True
        self._exit_latches: dict[str, str] = {}
        self._parallel_return_arm: dict[str, Any] | None = None

    @property
    def active(self) -> bool:
        return self._active

    @property
    def parallel_return_armed(self) -> bool:
        return self._parallel_return_arm is not None

    def _details(
        self,
        snapshot: MarketSnapshot,
    ) -> Mapping[str, Any]:
        raw = snapshot.metadata.get(
            "heist",
            {},
        )
        return (
            raw
            if isinstance(raw, Mapping)
            else {}
        )

    def _wait(
        self,
        snapshot: MarketSnapshot,
        reason: str,
        *,
        side: Side | None = None,
        opportunity_id: str | None = None,
    ) -> ToolIntent:
        return ToolIntent(
            tool=self.name,
            territory_id=self.territory_id,
            lane=Lane.TACTICAL,
            side=side,
            action=Action.WAIT,
            opportunity_id=opportunity_id,
            max_price=self.config.soft_max_price,
            size_tier=None,
            reason=reason,
            source_time=snapshot.now_ts,
        )

    def on_activate(
        self,
        snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        return self.on_market_event(
            snapshot
        )

    def on_market_event(
        self,
        snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        if not self._active:
            return []
        if self._current_ticker is not None and self._current_ticker != snapshot.ticker:
            self._parallel_return_arm = None
        self._current_ticker = snapshot.ticker
        self._filled_opportunities = {
            key for key in self._filled_opportunities
            if key[0] == snapshot.ticker or key[0] in self._open_tickers
        }

        details = self._details(snapshot)
        current_zone = str(details.get("current_zone") or "")
        if current_zone == "CENTER":
            self._center_since_visit = True
            self._parallel_return_arm = None
        if not details:
            return [self._wait(snapshot, "HEIST_EVIDENCE_UNAVAILABLE")]

        if (self.config.release_ends_box_immediately
                and snapshot.metadata.get("release_in_progress") is True):
            self._parallel_return_arm = None
            return [self._wait(
                snapshot, "HEIST_RELEASE_RUNWAY_ACTIVE_STOP_FADING_BOX",
                side=_side(snapshot.metadata.get("release_candidate_side")))]

        if self.config.release_ends_box_immediately and details.get("release_confirmed") is True:
            self._parallel_return_arm = None
            return [self._wait(
                snapshot, "HEIST_RELEASE_CONFIRMED_STOP_FADING_BOX",
                side=_side(details.get("release_side")))]

        if snapshot.ticker in self._open_tickers:
            return [self._wait(snapshot, "HEIST_POSITION_ALREADY_OPEN")]

        heist_diag = mapping(details.get("diagnostics"))
        parallel_environment = bool(
            heist_diag.get("heist_environment") is True
            and heist_diag.get("parallel_emas") is True
        )
        at_lower = details.get("at_lower_edge") is True
        at_upper = details.get("at_upper_edge") is True

        # Operator-authorized 2026-11-01 parallel Heist rule: a quiet/parallel
        # excursion arms the *return*; it never fades the still-extending push.
        # The visit may be a fully qualified box edge or the first unresolved
        # parallel excursion.  BTC and EMA9 must both start returning before
        # the entry becomes actionable.
        if parallel_environment and at_lower != at_upper:
            arm_side = Side.YES if at_lower else Side.NO
            arm_visit = str(details.get("visit_id") or f"{current_zone}:{snapshot.now_ts:.3f}")
            if (self._parallel_return_arm is None
                    or self._parallel_return_arm.get("ticker") != snapshot.ticker
                    or self._parallel_return_arm.get("side") != arm_side.value
                    or self._parallel_return_arm.get("visit_id") != arm_visit):
                self._parallel_return_arm = {
                    "ticker": snapshot.ticker,
                    "side": arm_side.value,
                    "visit_id": arm_visit,
                    "box_id": str(details.get("box_id") or "PARALLEL"),
                    "armed_at": snapshot.now_ts,
                    "armed_zone": current_zone,
                }

        parallel_return = False
        side: Side | None = None
        visit_id: str | None = None
        box_id = str(details.get("box_id") or "BOX")
        return_geometry: dict[str, Any] = {}
        arm = self._parallel_return_arm
        if parallel_environment and isinstance(arm, Mapping) and arm.get("ticker") == snapshot.ticker:
            side = _side(arm.get("side"))
            visit_id = str(arm.get("visit_id") or "PARALLEL")
            box_id = str(arm.get("box_id") or box_id)
            geometry = mapping(snapshot.metadata.get("current_geometry"))
            btc6 = number(geometry.get("btc_change6"))
            ema6 = number(geometry.get("ema9_change6"))
            if side is Side.YES:
                returning = bool(btc6 is not None and ema6 is not None and btc6 > 0 and ema6 >= 0)
                zone_ok = current_zone in ("LOWER", "INNER")
            elif side is Side.NO:
                returning = bool(btc6 is not None and ema6 is not None and btc6 < 0 and ema6 <= 0)
                zone_ok = current_zone in ("UPPER", "INNER")
            else:
                returning = False
                zone_ok = False
            parallel_return = bool(returning and zone_ok)
            return_geometry = {
                "parallel_environment": True,
                "source_ms": number(geometry.get("epoch_ms")),
                "armed_at": arm.get("armed_at"),
                "armed_zone": arm.get("armed_zone"),
                "current_zone": current_zone,
                "btc_change6": btc6,
                "ema9_change6": ema6,
                "return_confirmed": parallel_return,
            }

        qualified_box = details.get("qualified_box") is True
        geometry_now = mapping(snapshot.metadata.get("current_geometry"))
        observed_history_s = number(geometry_now.get("observed_history_seconds")) or 0.0
        stalled_parallel_edge = bool(
            qualified_box and parallel_environment and isinstance(arm, Mapping)
            and observed_history_s >= 600.0
            and current_zone in ("UPPER", "LOWER")
            and side is not None
        )
        if stalled_parallel_edge and not parallel_return:
            parallel_return = True
            return_geometry = {**return_geometry,
                "return_confirmed": False,
                "stalled_parallel_edge_override": True,
                "observed_history_seconds": observed_history_s,
            }

        if not qualified_box and not parallel_return:
            reason = ("HEIST_PARALLEL_EXCURSION_ARMED_AWAIT_RETURN"
                      if parallel_environment and self._parallel_return_arm is not None
                      else "HEIST_COMPRESSION_UNRESOLVED_WAIT")
            return [self._wait(snapshot, reason, side=side)]
        if parallel_environment and not parallel_return:
            return [self._wait(snapshot, "HEIST_PARALLEL_EXCURSION_ARMED_AWAIT_RETURN", side=side)]

        # A proven non-parallel box retains its existing immediate outer-edge
        # behavior.  Parallel boxes obey the newly authorized return-only rule.
        if not parallel_return:
            if at_lower == at_upper:
                return [self._wait(snapshot, "HEIST_WAIT_FOR_REAL_OUTER_EDGE")]
            side = Side.YES if at_lower else Side.NO
            visit_id = str(details.get("visit_id") or f"{snapshot.now_ts:.3f}")
            if current_zone in ("UPPER", "LOWER"):
                if (self._visit_id is None or side is not self._visit_side
                        or self._center_since_visit):
                    self._visit_id = visit_id
                    self._visit_side = side
                    self._center_since_visit = False
                else:
                    visit_id = self._visit_id
        assert side is not None
        visit_id = visit_id or str(details.get("visit_id") or f"{snapshot.now_ts:.3f}")

        opportunity_id = (
            f"{self.territory_id}:"
            f"{'HEIST_PARALLEL_RETURN' if parallel_return else 'HEIST_VISIT'}:{visit_id}:{side.value}"
        )
        if (snapshot.ticker, opportunity_id) in self._filled_opportunities:
            return [self._wait(
                snapshot, "HEIST_EDGE_VISIT_ALREADY_FILLED",
                side=side, opportunity_id=opportunity_id)]

        seconds_left = max(0.0, 900.0 - snapshot.contract_age_s)
        late_runway: dict[str, Any] | None = None
        if seconds_left <= 240.0:
            runway_ok, runway_evidence = settlement_runway_for_side(snapshot, side)
            late_runway = runway_evidence
            if not runway_ok:
                return [self._wait(
                    snapshot, "HEIST_LATE_DYNAMIC_TP_RUNWAY_BLOCK",
                    side=side, opportunity_id=opportunity_id)]

        geometry = mapping(snapshot.metadata.get("current_geometry"))
        ema_gap = abs(number(geometry.get("ema_gap")) or 0.0)
        range180 = max(1.0, number(geometry.get("range180")) or 1.0)
        ema30_slope = abs(number(geometry.get("ema30_slope3m")) or 0.0)
        if ema_gap > 0.40 * range180 and ema30_slope > 0.12 * range180:
            return [self._wait(
                snapshot, "HEIST_BLOCKED_WIDE_DIRECTIONAL_EMA_TERRAIN",
                side=side, opportunity_id=opportunity_id)]

        ask = snapshot.ask_for(side)
        if ask is None:
            return [self._wait(
                snapshot, "HEIST_EDGE_ASK_UNAVAILABLE",
                side=side, opportunity_id=opportunity_id)]
        if (900.0 - snapshot.contract_age_s <= self.config.late_counter_window_s
                and ask <= self.config.late_counter_max_ask):
            return [self._wait(
                snapshot, "LATE_COUNTER_PENNY_REQUIRES_CONFIRMED_TRANSFER",
                side=side, opportunity_id=opportunity_id)]

        # 2026-11-02 operator-authorized wider Heist economics. Repeated broad
        # alternation may use <=30c normally. 31-35c is exceptional and only
        # after current BTC+EMA9 have actually begun returning from the outer
        # wall; >35c remains WAIT. Price never creates the Heist opportunity.
        geometry_now = mapping(snapshot.metadata.get("current_geometry"))
        btc6_now = number(geometry_now.get("btc_change6"))
        ema6_now = number(geometry_now.get("ema9_change6"))
        outer_return_confirmed = bool(
            side is Side.YES and btc6_now is not None and ema6_now is not None
                and btc6_now > 0 and ema6_now >= 0
            or side is Side.NO and btc6_now is not None and ema6_now is not None
                and btc6_now < 0 and ema6_now <= 0
        )
        premium_ok = bool(details.get("premium_value_qualified") is True)
        stalled_edge_max_price = 0.40
        if (ask > self.config.wide_exceptional_max_price and not premium_ok
                and not (stalled_parallel_edge and ask <= stalled_edge_max_price)):
            return [self._wait(snapshot, "HEIST_EDGE_PRICE_ABOVE_EXCEPTIONAL_VALUE",
                side=side, opportunity_id=opportunity_id)]
        if (ask > self.config.wide_normal_max_price and not premium_ok
                and not outer_return_confirmed and not stalled_parallel_edge):
            return [self._wait(snapshot, "HEIST_31_35_REQUIRES_CONFIRMED_OUTER_RETURN",
                side=side, opportunity_id=opportunity_id)]

        lean = _side(details.get("lean_side"))
        lean_proof = mapping(details.get("lean_evidence"))
        if snapshot.metadata.get("source") == "DIRECT_BTC_AND_NATIVE_KALSHI":
            geometry = mapping(snapshot.metadata.get("current_geometry"))
            source = number(geometry.get("epoch_ms"))
            if not (lean_proof.get("version") == "CURRENT_EMA9_LEG_LEAN_V2"
                    and lean_proof.get("status") == "DIRECTIONAL"
                    and lean_proof.get("side") == (lean.value if lean else None)
                    and source is not None and number(lean_proof.get("source_ms")) == source
                    and current_source_is_fresh(snapshot, source, max_age_seconds=3.)
                    and all(mapping(mapping(lean_proof.get("horizons")).get(str(h))).get(
                        "single_connection_epoch") is True for h in (6, 30, 60))):
                lean = None
        aligned = lean is not None and lean is side
        repeatability = mapping(details.get("repeatability_proof"))
        observed_span_s = number(repeatability.get("observed_span_s")) or 0.0
        lower = number(details.get("lower"))
        upper = number(details.get("upper"))
        minimum_box_range = number(heist_diag.get("minimum_box_range")) or 0.0
        box_range = (upper - lower) if lower is not None and upper is not None else 0.0
        parallel_profit_mode = bool(heist_diag.get("parallel_emas") is True
            and observed_span_s >= 360.0
            and minimum_box_range > 0.0
            and box_range >= 1.5 * minimum_box_range)
        size = self.config.lean_favored_size if aligned else self.config.regular_size
        if parallel_return:
            reason = ("HEIST_PARALLEL_STALLED_EDGE_RETURN"
                      if stalled_parallel_edge and not outer_return_confirmed
                      else "HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED")
        else:
            reason = ("HEIST_OUTER_EDGE_ALIGNED_WITH_EMA_LEAN"
                      if aligned else "HEIST_OUTER_EDGE_TACTICAL_RENTER")

        return [ToolIntent(
            tool=self.name,
            territory_id=self.territory_id,
            lane=Lane.TACTICAL,
            side=side,
            action=Action.ENTER,
            opportunity_id=opportunity_id,
            max_price=(None if premium_ok else
                       stalled_edge_max_price if stalled_parallel_edge
                       else self.config.wide_exceptional_max_price if (ask > self.config.wide_normal_max_price and outer_return_confirmed)
                       else self.config.wide_normal_max_price),
            size_tier=size,
            reason=reason,
            source_time=snapshot.now_ts,
            expires_when="BOX_EDGE_LEAVES_OR_RELEASE_CONFIRMS",
            metadata={
                "box_id": box_id,
                "visit_id": visit_id,
                "lean_side": lean.value if lean else None,
                "lean_aligned": aligned,
                "lean_evidence": dict(lean_proof),
                "parallel_profit_mode": parallel_profit_mode,
                "parallel_return_entry": parallel_return,
                "parallel_return_evidence": return_geometry,
                "late_dynamic_runway": late_runway,
                "heist_cycle_context": dict(mapping(snapshot.metadata.get("heist_cycle_context"))),
                "observed_ask": ask,
                "wide_heist_price_policy": {
                    "normal_max": self.config.wide_normal_max_price,
                    "exceptional_max": self.config.wide_exceptional_max_price,
                    "outer_return_confirmed": outer_return_confirmed,
                },
                "entry_box_lower": details.get("lower"),
                "entry_box_upper": details.get("upper"),
                "entry_edge_tolerance": details.get("edge_tolerance"),
                # Operator-authorized quick-arc custody: small Heist returns
                # are harvested, not managed as monster runners.  Once the
                # executable full-lot bid reaches about +40% ROI, immediately
                # arm a tight 3% peak-bid trail.
                "floor_policy": {
                    "arm_roi": 0.40,
                    "trail_fraction": 0.03,
                    "min_age_s": 0.0,
                    "immediate_arm_roi": 0.40,
                    "first_arm_allowed": True,
                    "first_arm_from_current_bid": True,
                    "roi_trail_tiers": [],
                    "profit_policy_revision": "OPERATOR_AUTHORIZED_QUICK_HEIST_40_ARM_3_TRAIL_V1",
                },
            },
        )]

    def mark_entry_filled(
        self,
        opportunity_id: str,
        *, ticker: str | None = None,
    ) -> None:
        ticker = ticker or self._current_ticker
        if ticker is not None:
            self._filled_opportunities.add((ticker, opportunity_id))
            self._open_tickers.add(ticker)
            self._exit_latches.pop(ticker, None)
            self._parallel_return_arm = None

    def mark_position_closed(
        self,
        *, ticker: str | None = None, release_handoff: bool = False,
        opportunity_id: str | None = None,
    ) -> None:
        ticker = ticker or self._current_ticker
        if ticker is not None:
            self._open_tickers.discard(ticker)
            self._exit_latches.pop(ticker, None)
            if opportunity_id is not None:
                self._exit_latches.pop(opportunity_id, None)

    def manage_position(
        self, position: Mapping[str, Any], snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        details = self._details(snapshot)
        ticker = str(position.get("ticker") or "")
        latch_key = str(position.get("opportunity_id") or ticker)
        if not position.get("exit_required"):
            # An unaccepted collection must remain physically current. A
            # same-candle pause cannot turn into a phantom next-candle exit.
            self._exit_latches.pop(latch_key, None)
        side = as_side(position.get("side"))
        scoped = mission_collection_evidence(position, snapshot)
        release_side = as_side(rack_context(snapshot).get("confirmed_release_side"))
        parallel_release_side = as_side(snapshot.metadata.get("parallel_release_side"))
        action, reason = Action.HOLD, "HEIST_CARRY_TO_OPPOSITE_BOX_EDGE"
        if position.get("ticker") != snapshot.ticker:
            reason = "HEIST_AWAIT_EXACT_CONTRACT_CUSTODY"
        elif parallel_release_side is not None and parallel_release_side is not side:
            action, reason = Action.EXIT, "HEIST_PARALLEL_RELEASE_OPPOSES_HELD_SIDE"
        elif parallel_release_side is side and side is not None:
            reason = "HEIST_ALIGNED_PARALLEL_RELEASE_TRANSFERS_TO_RAIL_CUSTODY"
        elif opposing_transfer(position, snapshot):
            action, reason = Action.EXIT, "HEIST_CONFIRMED_OPPOSING_RELEASE"
        elif release_side is side and side is not None:
            reason = "HEIST_ALIGNED_RELEASE_TRANSFERS_HIGHER_CUSTODY"
        elif scoped["scope_enforced"] and scoped["collection_qualified"]:
            action, reason = Action.EXIT, "HELD_MISSION_PHYSICAL_DESTINATION"
        elif not scoped["scope_enforced"] and details.get("qualified_box") is True and (
            (side is Side.YES and details.get("at_upper_edge") is True)
            or (side is Side.NO and details.get("at_lower_edge") is True)
        ):
            action, reason = Action.EXIT, "HEIST_OPPOSITE_PHYSICAL_BOX_EDGE"
        deferred = ordinary_profit_hold_reason(position, snapshot, reason) if action is Action.EXIT else None
        if deferred:
            action, reason = Action.HOLD, deferred
        if action is Action.EXIT:
            self._exit_latches[latch_key] = reason
        if latch_key in self._exit_latches:
            action, reason = Action.EXIT, self._exit_latches[latch_key]
        return [position_intent(
            tool=self.name, territory_id=self.territory_id, lane=Lane.TACTICAL,
            position=position, snapshot=snapshot, action=action, reason=reason,
            config=self.config,
        )]

    def on_deactivate(
        self,
        snapshot: MarketSnapshot,
        reason: str,
    ) -> Iterable[ToolIntent]:
        self._active = False
        return [
            self._wait(
                snapshot,
                f"HEIST_DEACTIVATED:{reason}",
            )
        ]
