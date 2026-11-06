from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from strategy_core.tools.base import StrategyTool
from strategy_core.tools.management import (
    floor_policy, opposing_transfer, position_intent, strategy_exit_hold_reason, mission_collection_evidence,
    runner_harvest_update,
)
from strategy_core.types import (
    Action,
    Lane,
    MarketSnapshot,
    Side,
    ToolIntent,
)


@dataclass(frozen=True)
class ReleaseConfig:
    structural_size: float = 25.0
    soft_max_price: float = 0.20
    first_slowdown_confirms_release: bool = False
    requires_boundary_break: bool = True
    requires_directional_expansion: bool = True
    floor_arm_roi: float = 0.5
    floor_trail_fraction: float = 0.10
    floor_min_age_s: float = 30.0
    floor_immediate_arm_roi: float | None = None


@dataclass(frozen=True)
class ReleaseEvidence:
    candidate_side: Side | None = None
    boundary_break: bool = False
    directional_expansion: bool = False
    old_owner_failed_reextension: bool = False
    new_side_residence: bool = False
    first_slowdown_only: bool = False

    @property
    def confirmed(self) -> bool:
        return bool(
            not self.first_slowdown_only
            and self.candidate_side is not None
            and self.boundary_break
            and self.directional_expansion
            and (self.old_owner_failed_reextension or self.new_side_residence)
        )


class ReleaseWatcher(StrategyTool):
    """Universal territory-ending overlay.

    ReleaseWatcher never performs ordinary fades. It observes beside the
    primary tool and emits a HANDOFF relay only when physical transfer evidence
    is affirmative. A legacy release label is not sufficient.
    """

    name = "RELEASE_WATCHER"

    def __init__(
        self,
        *,
        territory_id: str,
        owner_side: Side | None,
        config: ReleaseConfig | None = None,
    ) -> None:
        self.territory_id = territory_id
        self.owner_side = owner_side
        self.config = config or ReleaseConfig()
        self._active = True
        self._evidence = ReleaseEvidence()
        self._entry_evidence = ReleaseEvidence()
        self._entry_diagnostics: dict[str, Any] = {}
        self._current_ticker: str | None = None
        self._open_tickers: set[str] = set()
        self._filled_opportunities: set[tuple[str, str]] = set()
        self._exit_latches: dict[str, str] = {}
        self._runner_harvest: dict[str, dict[str, Any]] = {}

    @property
    def active(self) -> bool:
        return self._active

    @property
    def confirmed(self) -> bool:
        return self._confirmed()

    @property
    def evidence(self) -> ReleaseEvidence:
        return self._evidence

    def update_owner_side(
        self,
        side: Side | None,
    ) -> None:
        if side is not None:
            self.owner_side = side

    def update_evidence(
        self,
        evidence: ReleaseEvidence,
        *,
        entry_evidence: ReleaseEvidence | None = None,
        entry_diagnostics: Mapping[str, Any] | None = None,
    ) -> None:
        # Ownership may remain latched through ordinary weakness. A new
        # purchase must separately qualify against the current physical probe.
        self._evidence = evidence
        self._entry_evidence = evidence if entry_evidence is None else entry_evidence
        self._entry_diagnostics = dict(entry_diagnostics or {})

    def opportunity_id(self, ticker: str) -> str:
        side = self._evidence.candidate_side
        if side is None:
            raise ValueError("RELEASE_MISSION_REQUIRES_CONFIRMED_SIDE")
        return f"{self.territory_id}:RELEASE:{side.value}:{ticker}"

    def physical_mission_id(self) -> str:
        side = self._evidence.candidate_side
        return f"{self.territory_id}:RELEASE:{side.value if side else 'UNKNOWN'}"

    def adopt_position(self, *, ticker: str) -> str:
        """Existing inventory consumes the release mission it now expresses."""
        opportunity_id = self.opportunity_id(ticker)
        self.mark_entry_filled(opportunity_id, ticker=ticker)
        return opportunity_id

    def _evidence_confirmed(self, evidence: ReleaseEvidence) -> bool:
        if evidence.candidate_side is None:
            return False
        if evidence.first_slowdown_only and not self.config.first_slowdown_confirms_release:
            return False
        if self.config.requires_boundary_break and not evidence.boundary_break:
            return False
        if self.config.requires_directional_expansion and not evidence.directional_expansion:
            return False
        return bool(evidence.old_owner_failed_reextension or evidence.new_side_residence)

    def _confirmed(self) -> bool:
        return self._evidence_confirmed(self._evidence)

    def _wait(
        self,
        snapshot: MarketSnapshot,
        reason: str,
    ) -> ToolIntent:
        return ToolIntent(
            tool=self.name,
            territory_id=self.territory_id,
            lane=Lane.HANDOFF,
            side=self._evidence.candidate_side,
            action=Action.WAIT,
            opportunity_id=None,
            max_price=self.config.soft_max_price,
            size_tier=None,
            reason=reason,
            source_time=snapshot.now_ts,
            metadata={"release_entry_proof": self._entry_diagnostics},
        )

    def on_activate(
        self,
        snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        return self.on_market_event(snapshot)

    def on_market_event(
        self,
        snapshot: MarketSnapshot,
    ) -> Iterable[ToolIntent]:
        if not self._active:
            return []
        self._current_ticker = snapshot.ticker

        e = self._evidence
        if e.first_slowdown_only and not self.config.first_slowdown_confirms_release:
            return [
                self._wait(
                    snapshot,
                    "RELEASE_FIRST_SLOWDOWN_IS_WATCH_NOT_HANDOFF",
                )
            ]

        if not self._confirmed():
            return [
                self._wait(
                    snapshot,
                    "RELEASE_WATCHING_FOR_AFFIRMATIVE_TRANSFER",
                )
            ]

        side = e.candidate_side
        assert side is not None
        opportunity_id = self.opportunity_id(snapshot.ticker)
        if snapshot.ticker in self._open_tickers:
            return [self._wait(snapshot, "RELEASE_POSITION_ALREADY_OPEN")]
        if (snapshot.ticker, opportunity_id) in self._filled_opportunities:
            return [self._wait(snapshot, "RELEASE_OPPORTUNITY_ALREADY_FILLED")]
        if not self._evidence_confirmed(self._entry_evidence) or self._entry_evidence.candidate_side is not side:
            return [self._wait(snapshot, "RELEASE_OWNER_RETAINED_NEW_ENTRY_PROOF_NOT_CURRENT")]
        ask = snapshot.ask_for(side)
        if ask is None:
            return [
                self._wait(
                    snapshot,
                    "RELEASE_SIDE_ASK_UNAVAILABLE",
                )
            ]

        if ask > self.config.soft_max_price:
            return [
                self._wait(
                    snapshot,
                    "RELEASE_CONFIRMED_BUT_PRICE_ABOVE_SOFT_VALUE",
                )
            ]

        release_floor = dict(floor_policy(self.config))
        seconds_left = max(0.0, 900.0 - float(snapshot.contract_age_s))
        if seconds_left <= 300.0:
            # PID14312 #9: a late confirmed Release from 11c reached 20c and
            # round-tripped because living-leg runner logic postponed all
            # protection.  Late Release still gets runway, but after 30s a
            # +60% full-lot gain earns a 5% trail; an exceptional +150% pop may
            # arm immediately (preserving PID14312 #4's fast harvest).
            release_floor.update({
                "arm_roi": 0.60,
                "trail_fraction": 0.05,
                "min_age_s": 30.0,
                "immediate_arm_roi": 1.50,
                "first_arm_allowed": True,
                "first_arm_from_current_bid": True,
                "roi_trail_tiers": [[1.0, 0.05], [1.5, 0.03], [6.0, 0.02]],
                "profit_policy_revision": "PID14312_LATE_RELEASE_60_5_150_IMMEDIATE",
            })

        return [
            ToolIntent(
                tool=self.name,
                territory_id=self.territory_id,
                lane=Lane.HANDOFF,
                side=side,
                action=Action.RELAY,
                opportunity_id=opportunity_id,
                max_price=self.config.soft_max_price,
                size_tier=self.config.structural_size,
                reason="RELEASE_CONFIRMED_LEVIATHAN_HANDOFF",
                source_time=snapshot.now_ts,
                expires_when="RELEASE_INVALIDATES_OR_NEXT_TERRITORY_OWNS",
                metadata={
                    "custody": "LEVIATHAN_RELEASE",
                    "old_owner_side": (
                        self.owner_side.value
                        if self.owner_side
                        else None
                    ),
                    "boundary_break": e.boundary_break,
                    "directional_expansion": e.directional_expansion,
                    "old_owner_failed_reextension": (
                        e.old_owner_failed_reextension
                    ),
                    "new_side_residence": e.new_side_residence,
                    "floor_policy": release_floor,
                    "physical_mission_id": self.physical_mission_id(),
                    "physical_renewal": {
                        "independent": self._entry_diagnostics.get("fresh_transfer") is True,
                        "renewal_kind": "CONFIRMED_RELEASE_TRANSFER",
                        "observed_at": self._entry_diagnostics.get("observed_at", snapshot.now_ts),
                    },
                    "release_entry_proof": self._entry_diagnostics,
                    "heist_cycle_context": dict(snapshot.metadata.get("heist_cycle_context") or {}),
                },
            )
        ]

    def mark_entry_filled(
        self, opportunity_id: str, *, ticker: str | None = None,
    ) -> None:
        ticker = ticker or self._current_ticker
        if ticker is not None:
            self._filled_opportunities.add((ticker, opportunity_id))
            self._open_tickers.add(ticker)
            self._exit_latches.pop(ticker, None)

    def mark_position_closed(
        self, *, ticker: str | None = None, release_handoff: bool = False,
        opportunity_id: str | None = None,
    ) -> None:
        ticker = ticker or self._current_ticker
        if ticker is not None:
            self._open_tickers.discard(ticker)
            self._exit_latches.pop(ticker, None)
            if opportunity_id is not None:
                self._exit_latches.pop(opportunity_id, None)
            # Runner state is keyed by position/opportunity and is harmless to
            # retain if the exact position id is unavailable; a new position
            # receives a distinct key.

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
            label="RELEASE_RUNNER")
        if opposing_transfer(position, snapshot):
            proposed = "RELEASE_CONFIRMED_OPPOSING_TRANSFER"
        elif runner.get("exit_now") is True:
            proposed = str(runner.get("exit_reason") or "RELEASE_RUNNER_SECOND_SLOWDOWN_UPTICK_PEAK_HARVEST")
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
                reason = "RELEASE_RUNNER_SECOND_SLOWDOWN_HARVEST_ARMED_AWAIT_UPTICK_PEAK"
            elif runner.get("slowdown_count") == 1:
                reason = "RELEASE_RUNNER_FIRST_SLOWDOWN_HOLD_FOR_RESUME"
            else:
                reason = "RELEASE_RUNNER_STRUCTURAL_RUNWAY"
        else:
            reason = self._exit_latches.get(latch_key, deferred or "RELEASE_STRUCTURAL_CUSTODY_INTACT")
        return [position_intent(
            tool=self.name, territory_id=self.territory_id, lane=Lane.HANDOFF,
            position=position, snapshot=snapshot, action=action, reason=reason,
            config=self.config, metadata={"custody": "LEVIATHAN_RELEASE",
                                          "runner_harvest": runner},
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
                f"RELEASE_WATCHER_DEACTIVATED:{reason}",
            )
        ]
