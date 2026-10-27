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
    qualified_heist: bool = False
    compression_unresolved: bool = False
    release_handoff_confirmed: bool = False
    release_side: Side | None = None
    heist_takeover_confirmed: bool = False


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

        aligned = (
            e.ema9_direction is not None
            and e.ema9_direction is e.ema30_direction
        )
        rail_persistence = (
            e.contracts_persistent >= 1.0
            or e.rolling_mountain_repetitions >= 2
        )
        if (
            aligned
            and e.ema_pair_parallel
            and e.directional_residence
            and rail_persistence
        ):
            territory = (
                Territory.UP_RAIL
                if e.ema9_direction is Side.YES
                else Territory.DOWN_RAIL
            )
            return TerritoryDecision(
                territory,
                e.ema9_direction,
                "PARALLEL_EMAS_WITH_PERSISTENT_SAME_DIRECTION_ROLLING_STRUCTURE",
            )

        if e.rolling_mountain:
            return TerritoryDecision(
                Territory.ROLLING_MOUNTAIN,
                e.ema9_direction,
                "SAME_DIRECTION_MOUNTAIN_NOT_YET_RAIL",
            )

        if e.alternating_mountain:
            return TerritoryDecision(
                Territory.ALTERNATING_MOUNTAIN,
                e.ema9_direction,
                "ALTERNATING_EMA9_MOUNTAIN",
            )

        return TerritoryDecision(
            Territory.UNKNOWN,
            e.ema9_direction,
            "NO_TOOL_TERRITORY",
        )
