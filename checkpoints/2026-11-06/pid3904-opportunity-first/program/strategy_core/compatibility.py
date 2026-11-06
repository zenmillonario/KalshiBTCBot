from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ToolName(str, Enum):
    RAIL = "RAIL"
    ALTERNATING_MOUNTAIN = "ALTERNATING_MOUNTAIN"
    ROLLING_MOUNTAIN = "ROLLING_MOUNTAIN"
    MARKET_HEIST = "MARKET_HEIST"
    RELEASE_WATCHER = "RELEASE_WATCHER"
    OPPOSITE_FADE = "OPPOSITE_FADE"


@dataclass(frozen=True)
class CompatibilityRule:
    primary: ToolName
    secondary: ToolName
    allowed: bool
    reason: str


_RULES = {
    (ToolName.RAIL, ToolName.RELEASE_WATCHER): CompatibilityRule(
        ToolName.RAIL,
        ToolName.RELEASE_WATCHER,
        True,
        "Release watcher may observe/hand off without fading the live Rail.",
    ),
    (
        ToolName.ALTERNATING_MOUNTAIN,
        ToolName.RELEASE_WATCHER,
    ): CompatibilityRule(
        ToolName.ALTERNATING_MOUNTAIN,
        ToolName.RELEASE_WATCHER,
        True,
        "Release watcher prepares for the Mountain terminal transfer.",
    ),
    (
        ToolName.MARKET_HEIST,
        ToolName.RELEASE_WATCHER,
    ): CompatibilityRule(
        ToolName.MARKET_HEIST,
        ToolName.RELEASE_WATCHER,
        True,
        "Release watcher prepares for the box breakout/drop.",
    ),
    (ToolName.ROLLING_MOUNTAIN, ToolName.RELEASE_WATCHER): CompatibilityRule(
        ToolName.ROLLING_MOUNTAIN,
        ToolName.RELEASE_WATCHER,
        True,
        "Release watcher observes alongside causal Mountain terminal relays.",
    ),
    (ToolName.RAIL, ToolName.OPPOSITE_FADE): CompatibilityRule(
        ToolName.RAIL,
        ToolName.OPPOSITE_FADE,
        True,
        "A separately qualified tactical edge may coexist with Rail when target or opening-value context permits; it does not transfer Rail ownership.",
    ),
    (ToolName.RAIL, ToolName.MARKET_HEIST): CompatibilityRule(
        ToolName.RAIL, ToolName.MARKET_HEIST, True,
        "A genuinely qualified bounded box may supply an independent tactical edge under the same Rail value conditions."),
    (ToolName.ALTERNATING_MOUNTAIN, ToolName.MARKET_HEIST): CompatibilityRule(
        ToolName.ALTERNATING_MOUNTAIN, ToolName.MARKET_HEIST, True,
        "Qualified tactical box entries preserve the living Mountain primary."),
    (ToolName.ROLLING_MOUNTAIN, ToolName.MARKET_HEIST): CompatibilityRule(
        ToolName.ROLLING_MOUNTAIN, ToolName.MARKET_HEIST, True,
        "Qualified tactical box entries preserve the living Mountain primary."),
}


def compatibility(
    primary: ToolName,
    secondary: ToolName,
) -> CompatibilityRule:
    return _RULES.get(
        (primary, secondary),
        CompatibilityRule(
            primary,
            secondary,
            False,
            "No compatibility is granted unless explicitly declared.",
        ),
    )
