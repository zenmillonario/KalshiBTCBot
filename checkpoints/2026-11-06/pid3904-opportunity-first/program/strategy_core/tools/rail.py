from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from strategy_core.tools.base import StrategyTool
from strategy_core.commander_candidates import settlement_runway_for_side
from strategy_core.tools.management import (
    floor_policy, opposing_transfer, position_intent, strategy_exit_hold_reason, mission_collection_evidence,
    runner_harvest_update,
)


@dataclass(frozen=True)
class RailConfig:
    """Rail-only knobs.

    These values deliberately live here so Rail can be tuned without editing
    Mountain, Heist, Commander, or execution code.
    """

    size_tier: float = 25.0
    first_60s_max: float = 0.35
    sec_60_120_max: float = 0.35
    sec_120_240_max: float = 0.35
    later_soft_max: float = 0.35
    hard_max_price: float = 0.399
    activation_window_s: float = 240.0
    reentry_after_exit: bool = True
    # These are strategy constitution switches, not documentation-only knobs.
    # With opposite_fades disabled, a Rail can only transfer through a
    # confirmed ReleaseWatcher handoff.
    opposite_fades: bool = False
    rollover_creates_new_slice: bool = True
    parallel_release_max_price: float = 0.35
    floor_arm_roi: float = 0.5
    floor_trail_fraction: float = 0.10
    floor_min_age_s: float = 30.0
    floor_immediate_arm_roi: float | None = None


class RailTool(StrategyTool):
    """Open-ended same-direction Rail participation.

    The primary Rail tool keeps its direction. The rack may attach a separately
    qualified tactical edge with explicit value context; that companion does
    not terminate Rail ownership. Genuine release still controls transfer.
    """

    name = "RAIL"

    def __init__(
        self,
        *,
        territory_id: str,
        side: Side,
        activated_at: float,
        config: RailConfig | None = None,
    ) -> None:
        self.territory_id = territory_id
        self.side = side
        self.activated_at = activated_at
        self.config = config or RailConfig()
        self._active = True
        self._current_ticker: str | None = None
        self._filled_opportunity_ids: set[str] = set()
        self._open_tickers: set[str] = set()
        self._rearm_generations: dict[str, int] = {}
        self._exit_latches: dict[str, str] = {}
        self._runner_harvest: dict[str, dict[str, Any]] = {}
        # Same physical Rail rolling into a new Kalshi contract may use the
        # existing Rail soft ceiling immediately. A freshly detected Rail still
        # uses the conservative 35c discovery window.
        self._inherited_rollover_tickers: set[str] = set()
        self._value_started_at: dict[str, float] = {}

    @property
    def active(self) -> bool:
        return self._active

    def _max_price(self, snapshot: MarketSnapshot) -> float:
        if snapshot.metadata.get("parallel_release_rail") is True:
            return self.config.parallel_release_max_price
        if snapshot.ticker in self._inherited_rollover_tickers:
            # An already-established Rail rolling into a fresh contract may use
            # the operator-authorized hard Rail ceiling: strictly below 40c.
            return self.config.hard_max_price
        # A newly activated Rail gets its own value-discovery window even when
        # activation happens mid-contract. Rollover gets the normal contract
        # opening ladder automatically because contract_age_s resets.
        activation_age = max(0.0, snapshot.now_ts - self.activated_at)
        age = min(snapshot.contract_age_s, activation_age)
        if age < 60:
            return self.config.first_60s_max
        if age < 120:
            return self.config.sec_60_120_max
        if age < 240:
            return self.config.sec_120_240_max
        return self.config.later_soft_max


    def _ema9_dip_value_context(self, snapshot: MarketSnapshot) -> tuple[bool, dict[str, Any]]:
        """Recognize a same-direction value pullback into the living EMA9 Rail.

        Operator-authorized PID2672 route: this is not a counter fade and not a
        clock-only permission.  A mature/rolling EMA9-EMA30 gap must still own
        the Rail direction, the current child must pull opposite the parent, and
        BTC must trade back into the corridor between EMA9 and EMA30.  That deep
        pullback may use the existing 20c Rail ceiling immediately instead of
        waiting through the 10c/15c discovery ladder.
        """
        geometry = snapshot.metadata.get("current_geometry")
        geometry = geometry if isinstance(geometry, Mapping) else {}
        mountain = snapshot.metadata.get("mountain")
        mountain = mountain if isinstance(mountain, Mapping) else {}
        parent = mountain.get("parent_structure")
        parent = parent if isinstance(parent, Mapping) else {}
        cross = snapshot.metadata.get("ema9_ema30_cross_context")
        cross = cross if isinstance(cross, Mapping) else {}
        lifecycle = cross.get("gap_lifecycle")
        lifecycle = lifecycle if isinstance(lifecycle, Mapping) else {}
        try:
            btc = float(geometry.get("btc_price"))
            ema9 = float(geometry.get("ema9"))
            ema30 = float(geometry.get("ema30"))
        except (TypeError, ValueError):
            return False, {"basis": "EMA_VALUES_UNAVAILABLE"}
        parent_side = str(parent.get("parent_side") or "").upper()
        child_direction = str(geometry.get("arc_direction") or "").upper()
        stage = str(lifecycle.get("stage") or "").upper()
        gap_side = str(lifecycle.get("current_side") or lifecycle.get("side") or "").upper()
        if not gap_side:
            gap_side = "YES" if ema9 > ema30 else "NO" if ema9 < ema30 else ""
        expected_parent = self.side.value
        opposite_child = "DOWN" if self.side is Side.YES else "UP"
        if self.side is Side.YES:
            corridor_pullback = ema30 < btc <= ema9 and ema9 > ema30
        else:
            corridor_pullback = ema9 <= btc < ema30 and ema9 < ema30
        qualified = bool(
            stage in {"MATURE", "ROLLING"}
            and parent_side == expected_parent
            and gap_side == expected_parent
            and child_direction == opposite_child
            and corridor_pullback
            and parent.get("parent_terminal_ready") is not True
        )
        return qualified, {
            "basis": "MATURE_RAIL_OPPOSITE_CHILD_PULLBACK_INTO_EMA9_EMA30_CORRIDOR" if qualified
                     else "EMA9_RAIL_DIP_NOT_QUALIFIED",
            "gap_stage": stage,
            "gap_side": gap_side or None,
            "parent_side": parent_side or None,
            "child_direction": child_direction or None,
            "btc": btc, "ema9": ema9, "ema30": ema30,
            "corridor_pullback": corridor_pullback,
            "parent_terminal_ready": parent.get("parent_terminal_ready") is True,
            "max_price": self.config.later_soft_max,
        }

    def _opportunity_id(self, snapshot: MarketSnapshot) -> str:
        return (
            f"{self.territory_id}:RAIL_VALUE:{snapshot.ticker}:"
            f"REARM{self._rearm_generations.get(snapshot.ticker, 0)}"
        )

    def _wait(
        self,
        snapshot: MarketSnapshot,
        reason: str,
        *,
        max_price: float | None = None,
    ) -> ToolIntent:
        return ToolIntent(
            tool=self.name,
            territory_id=self.territory_id,
            lane=Lane.MAIN,
            side=self.side,
            action=Action.WAIT,
            opportunity_id=self._opportunity_id(snapshot),
            max_price=max_price,
            size_tier=self.config.size_tier,
            reason=reason,
            source_time=snapshot.now_ts,
        )

    def on_activate(self, snapshot: MarketSnapshot) -> Iterable[ToolIntent]:
        self._current_ticker = snapshot.ticker
        return self.on_market_event(snapshot)

    def on_market_event(self, snapshot: MarketSnapshot) -> Iterable[ToolIntent]:
        if not self._active:
            return []

        rolled_contract = self._current_ticker is not None and self._current_ticker != snapshot.ticker
        if self._current_ticker != snapshot.ticker:
            # New Kalshi contract = fresh economic slice of the same physical
            # Rail when the configured rollover policy permits it. It is NOT a
            # new Rail territory. Preserve that inherited status so the already
            # established Rail may participate at the normal <=50c Rail ceiling
            # instead of waiting for a 35c quote that may never appear.
            if rolled_contract:
                self._inherited_rollover_tickers.add(snapshot.ticker)
            self._current_ticker = snapshot.ticker
            self._rearm_generations.setdefault(snapshot.ticker, 0)

        max_price = self._max_price(snapshot)
        if rolled_contract and not self.config.rollover_creates_new_slice:
            return [self._wait(snapshot, "RAIL_ROLLOVER_SLICE_DISABLED", max_price=max_price)]
        opportunity_id = self._opportunity_id(snapshot)
        geometry = snapshot.metadata.get("current_geometry") if isinstance(snapshot.metadata.get("current_geometry"), Mapping) else {}
        raw_parent = str(geometry.get("parent_direction") or "").upper()
        raw_parent_side = Side.YES if raw_parent == "UP" else Side.NO if raw_parent == "DOWN" else None
        if raw_parent_side is not None and raw_parent_side is not self.side:
            return [self._wait(snapshot, "RAIL_SIDE_CONFLICTS_SOVEREIGN_PARENT", max_price=max_price)]

        # Reactivated Rail is intentionally stricter than a local Rail label.
        # Production must have causal prior-contract history plus the exact
        # current target before a same-direction Rail value slice can book.
        # This preserves the pre-existing Commander audit requirement that
        # physical Rail may outrank an advisory thesis only with complete
        # target/history provenance.  Isolated unit-tool fixtures remain free
        # to exercise Rail mechanics without constructing production context.
        if snapshot.metadata.get("source") == "DIRECT_BTC_AND_NATIVE_KALSHI":
            context = snapshot.metadata.get("mission_context")
            context = context if isinstance(context, Mapping) else {}
            contract = context.get("contract")
            contract = contract if isinstance(contract, Mapping) else {}
            reference = contract.get("reference_window")
            reference = reference if isinstance(reference, Mapping) else {}
            if contract.get("target") is None:
                return [self._wait(snapshot, "RAIL_TARGET_PROVENANCE_REQUIRED", max_price=max_price)]
            try:
                completed_prior = float(reference.get("completed_prior_contracts") or 0.0)
            except (TypeError, ValueError):
                completed_prior = 0.0
            if contract.get("history_status") != "READY" or completed_prior < 2.0:
                return [self._wait(snapshot, "RAIL_CAUSAL_HISTORY_PROVENANCE_REQUIRED", max_price=max_price)]

        seconds_left = max(0.0, 900.0 - snapshot.contract_age_s)
        late_runway: dict[str, Any] | None = None
        if seconds_left <= 240.0:
            runway_ok, runway_evidence = settlement_runway_for_side(snapshot, self.side)
            late_runway = runway_evidence
            if not runway_ok:
                return [self._wait(snapshot, "RAIL_LATE_DYNAMIC_TP_RUNWAY_BLOCK", max_price=max_price)]
        started = self._value_started_at.setdefault(opportunity_id, snapshot.now_ts)
        waited = max(0.0, snapshot.now_ts - started)
        ema9_dip_value, ema9_dip_evidence = self._ema9_dip_value_context(snapshot)
        if ema9_dip_value:
            # Same-direction EMA9 Rail pullbacks are the explicit value window.
            # Operator-authorized PID1172 economics: <=35c is preferred normal
            # Rail value; 36-39.9c is reserved for this physically established
            # MATURE/ROLLING EMA9 dip (or inherited rollover), never mid-leg chase.
            max_price = self.config.hard_max_price
        # The previous 10c/15c discovery ladder is retired.  A Rail has already
        # paid for persistence before activation; once established, <=35c is the
        # normal value zone rather than a reason to starve the chapter.

        if snapshot.ticker in self._open_tickers:
            return [
                self._wait(
                    snapshot,
                    "RAIL_POSITION_ALREADY_OPEN",
                    max_price=max_price,
                )
            ]

        if opportunity_id in self._filled_opportunity_ids:
            return [
                self._wait(
                    snapshot,
                    "RAIL_VALUE_OPPORTUNITY_ALREADY_FILLED",
                    max_price=max_price,
                )
            ]

        ask = snapshot.ask_for(self.side)
        if ask is None:
            return [
                self._wait(
                    snapshot,
                    "MAIN_SIDE_ASK_UNAVAILABLE",
                    max_price=max_price,
                )
            ]

        if ask > max_price:
            # Critical doctrine: WAIT does not consume the opportunity.
            return [
                self._wait(
                    snapshot,
                    f"ASK_{ask:.3f}_ABOVE_MAX_{max_price:.3f}",
                    max_price=max_price,
                )
            ]

        return [
            ToolIntent(
                tool=self.name,
                territory_id=self.territory_id,
                lane=Lane.MAIN,
                side=self.side,
                action=Action.ENTER,
                opportunity_id=opportunity_id,
                max_price=max_price,
                size_tier=self.config.size_tier,
                reason="RAIL_EMA9_DIP_VALUE" if ema9_dip_value else "RAIL_MAIN_VALUE",
                source_time=snapshot.now_ts,
                expires_when="RAIL_HANDOFF_OR_VALUE_WINDOW_CHANGE",
                metadata={"observed_ask": ask, "floor_policy": floor_policy(self.config),
                          "late_dynamic_runway": late_runway,
                          "rail_price_policy": {"preferred_max": self.config.later_soft_max,
                                                "hard_max_strictly_below_40": self.config.hard_max_price,
                                                "uses_hard_tier": bool(ask > self.config.later_soft_max)},
                          "ema9_dip_value": ema9_dip_evidence if ema9_dip_value else None},
            )
        ]

    def mark_entry_filled(
        self, opportunity_id: str, *, ticker: str | None = None,
    ) -> None:
        self._filled_opportunity_ids.add(opportunity_id)
        ticker = ticker or self._current_ticker
        if ticker is not None:
            self._open_tickers.add(ticker)
            self._exit_latches.pop(ticker, None)

    def mark_position_closed(
        self, *, ticker: str | None = None, release_handoff: bool = False,
        opportunity_id: str | None = None,
    ) -> None:
        ticker = ticker or self._current_ticker
        if ticker is None:
            return
        self._open_tickers.discard(ticker)
        self._exit_latches.pop(ticker, None)
        if opportunity_id is not None:
            self._exit_latches.pop(opportunity_id, None)
            self._runner_harvest.pop(opportunity_id, None)
        if release_handoff:
            self._active = False
            return
        if self.config.reentry_after_exit:
            # A profit/protection exit does not end the Rail. Rearm a fresh
            # value opportunity immediately. A genuine release is what stops
            # the cycle.
            self._rearm_generations[ticker] = self._rearm_generations.get(ticker, 0) + 1

    def manage_position(
        self, position: Mapping[str, Any], snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        ticker = str(position.get("ticker") or "")
        latch_key = str(position.get("opportunity_id") or ticker)
        if not position.get("exit_required"):
            self._exit_latches.pop(latch_key, None)
        scoped = mission_collection_evidence(position, snapshot)
        runner = runner_harvest_update(
            self._runner_harvest, position, snapshot, eligible=True,
            label="RAIL_RUNNER")
        if opposing_transfer(position, snapshot):
            proposed = "RAIL_CONFIRMED_OPPOSING_RELEASE"
        elif runner.get("exit_now") is True:
            proposed = str(runner.get("exit_reason") or "RAIL_RUNNER_SECOND_SLOWDOWN_UPTICK_PEAK_HARVEST")
        elif runner.get("eligible") is True:
            proposed = None
        elif scoped["scope_enforced"] and scoped["collection_qualified"]:
            proposed = "HELD_MISSION_PHYSICAL_DESTINATION"
        else:
            proposed = None
        deferred = strategy_exit_hold_reason(position, snapshot, proposed) if proposed else None
        if proposed and not deferred:
            self._exit_latches[latch_key] = proposed
        action = Action.EXIT if latch_key in self._exit_latches else Action.HOLD
        if action is Action.HOLD and runner.get("eligible") is True:
            if runner.get("harvest_armed"):
                reason = "RAIL_RUNNER_SECOND_SLOWDOWN_HARVEST_ARMED_AWAIT_UPTICK_PEAK"
            elif runner.get("slowdown_count") == 1:
                reason = "RAIL_RUNNER_FIRST_SLOWDOWN_HOLD_FOR_RESUME"
            else:
                reason = "RAIL_RUNNER_STRUCTURAL_RUNWAY"
        else:
            reason = self._exit_latches.get(latch_key, deferred or "RAIL_STRUCTURAL_CUSTODY_INTACT")
        # Quote validity and ticker matching remain independent execution
        # constraints. A structural EXIT stays latched while its quote recovers.
        return [position_intent(
            tool=self.name, territory_id=self.territory_id, lane=Lane.MAIN,
            position=position, snapshot=snapshot, action=action, reason=reason,
            config=self.config, metadata={"runner_harvest": runner},
        )]

    def on_deactivate(
        self,
        snapshot: MarketSnapshot,
        reason: str,
    ) -> Iterable[ToolIntent]:
        self._active = False
        return [
            ToolIntent(
                tool=self.name,
                territory_id=self.territory_id,
                lane=Lane.HANDOFF,
                side=self.side,
                action=Action.WAIT,
                opportunity_id=None,
                max_price=None,
                size_tier=None,
                reason=f"RAIL_DEACTIVATED:{reason}",
                source_time=snapshot.now_ts,
            )
        ]
