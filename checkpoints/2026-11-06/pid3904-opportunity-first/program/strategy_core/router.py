from __future__ import annotations

from dataclasses import dataclass

from strategy_core.types import Side, Territory


@dataclass(frozen=True)
class PhysicalEvidence:
    """Strategy-facing physical evidence, not trade permission.

    The measurement layer may evolve independently. The router consumes only
    explicit physical facts and returns the territory that best describes the
    current market.
    """

    ema9_direction: Side | None = None
    ema30_direction: Side | None = None
    ema_pair_parallel: bool = False
    directional_residence: bool = False
    rolling_mountain_repetitions: int = 0
    contracts_persistent: float = 0.0
    alternating_mountain: bool = False
    rolling_mountain: bool = False
    # The current causal EMA9 arc is Mountain's compass. Rail's longer-horizon
    # agreement remains a separate measurement and cannot erase a real turn.
    mountain_direction: Side | None = None
    qualified_heist: bool = False
    compression_unresolved: bool = False
    heist_takeover_confirmed: bool = False
    # Explicit parent-scale governance. Rail can own only when the larger EMA9
    # parent/rail evidence says so; ordinary child Mountains cannot promote it.
    rail_launch_qualified: bool = False
    rail_launch_side: Side | None = None
    parent_extended: bool = False
    parent_slow_rolling: bool = False
    parent_terminal_ready: bool = False

    # Clean Tool Rack release measurements. These are physical observations,
    # not permission labels.
    release_candidate_side: Side | None = None
    release_boundary_break: bool = False
    release_directional_expansion: bool = False
    release_old_owner_failed_reextension: bool = False
    release_new_side_residence: bool = False
    release_first_slowdown_only: bool = False

    # Legacy R22 release labels are retained only as migration telemetry.
    # ReleaseWatcher does not accept these alone as authority.
    release_handoff_confirmed: bool = False
    release_side: Side | None = None


@dataclass(frozen=True)
class TerritoryDecision:
    territory: Territory
    side: Side | None
    reason: str


class TerritoryRouter:
    """Classifies physical territory. It never issues trade intents."""

    def classify(self, e: PhysicalEvidence) -> TerritoryDecision:
        if e.compression_unresolved and not e.qualified_heist:
            return TerritoryDecision(
                Territory.COMPRESSION_UNRESOLVED,
                None,
                "COMPRESSION_NOT_YET_REPEATABLE",
            )

        if e.qualified_heist:
            # A real bounded box remains Heist even when the EMAs lean. The
            # lean is a bias inside the Heist tool, not automatic Rail.
            return TerritoryDecision(
                Territory.MARKET_HEIST,
                e.ema9_direction,
                "QUALIFIED_REPEATABLE_SIDEWAYS_BOX",
            )

        if e.rail_launch_qualified and e.rail_launch_side is not None:
            territory = (
                Territory.UP_RAIL
                if e.rail_launch_side is Side.YES
                else Territory.DOWN_RAIL
            )
            return TerritoryDecision(
                territory,
                e.rail_launch_side,
                "EMA9_PARENT_RAIL_LAUNCH_OR_SLOW_ROLLING_PARENT",
            )

        # EMA30 alignment/residence is descriptive only.  It can never promote
        # Rail by itself; only the explicit parent-scale rail_launch_qualified
        # path above has trading authority.

        if e.alternating_mountain:
            return TerritoryDecision(
                Territory.ALTERNATING_MOUNTAIN,
                e.mountain_direction,
                "ALTERNATING_EMA9_MOUNTAIN",
            )

        if e.rolling_mountain:
            return TerritoryDecision(
                Territory.ROLLING_MOUNTAIN,
                e.mountain_direction,
                "SAME_DIRECTION_MOUNTAIN_NOT_YET_RAIL",
            )

        return TerritoryDecision(
            Territory.UNKNOWN,
            e.ema9_direction,
            "NO_TOOL_TERRITORY",
        )
