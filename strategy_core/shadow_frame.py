from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from strategy_core.router import PhysicalEvidence
from strategy_core.types import MarketSnapshot, Side


def _side(value: str | None) -> Side | None:
    if value is None:
        return None
    return Side(str(value).upper())


@dataclass(frozen=True)
class ShadowFrame:
    evidence: PhysicalEvidence
    snapshot: MarketSnapshot

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
    ) -> "ShadowFrame":
        market = raw["market"]
        physical = raw["physical"]
        return cls(
            evidence=PhysicalEvidence(
                ema9_direction=_side(
                    physical.get("ema9_direction")
                ),
                ema30_direction=_side(
                    physical.get("ema30_direction")
                ),
                ema_pair_parallel=bool(
                    physical.get(
                        "ema_pair_parallel",
                        False,
                    )
                ),
                directional_residence=bool(
                    physical.get(
                        "directional_residence",
                        False,
                    )
                ),
                rolling_mountain_repetitions=int(
                    physical.get(
                        "rolling_mountain_repetitions",
                        0,
                    )
                ),
                contracts_persistent=float(
                    physical.get(
                        "contracts_persistent",
                        0.0,
                    )
                ),
                alternating_mountain=bool(
                    physical.get(
                        "alternating_mountain",
                        False,
                    )
                ),
                rolling_mountain=bool(
                    physical.get(
                        "rolling_mountain",
                        False,
                    )
                ),
                qualified_heist=bool(
                    physical.get(
                        "qualified_heist",
                        False,
                    )
                ),
                compression_unresolved=bool(
                    physical.get(
                        "compression_unresolved",
                        False,
                    )
                ),
                release_handoff_confirmed=bool(
                    physical.get(
                        "release_handoff_confirmed",
                        False,
                    )
                ),
                release_side=_side(
                    physical.get("release_side")
                ),
                heist_takeover_confirmed=bool(
                    physical.get(
                        "heist_takeover_confirmed",
                        False,
                    )
                ),
            ),
            snapshot=MarketSnapshot(
                now_ts=float(market["now_ts"]),
                ticker=str(market["ticker"]),
                contract_age_s=float(
                    market["contract_age_s"]
                ),
                yes_ask=(
                    None
                    if market.get("yes_ask") is None
                    else float(market["yes_ask"])
                ),
                no_ask=(
                    None
                    if market.get("no_ask") is None
                    else float(market["no_ask"])
                ),
                quote_current=bool(
                    market.get(
                        "quote_current",
                        True,
                    )
                ),
                depth_available=bool(
                    market.get(
                        "depth_available",
                        True,
                    )
                ),
                metadata=market.get(
                    "metadata",
                    {},
                ),
            ),
        )
