from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from strategy_core.router import PhysicalEvidence
from strategy_core.shadow_frame import ShadowFrame
from strategy_core.types import MarketSnapshot, Side


def _num(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _sign_side(value: float | None, eps: float = 0.0) -> Side | None:
    if value is None:
        return None
    if value > eps:
        return Side.YES
    if value < -eps:
        return Side.NO
    return None


@dataclass(frozen=True)
class R22ShadowSourceState:
    frame: ShadowFrame
    run_id: str | None
    session_id: str | None
    source_files: dict[str, str]
    geometry_rows_used: int
    geometry_age_seconds: float | None


class R22RunShadowSource:
    """Read-only adapter from an R22 PAPER run directory.

    It never imports the engine and never writes inside the PAPER run.
    """

    def __init__(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir)
        self.runtime_path = self.run_dir / "tachys_runtime_hf2.json"
        self.geometry_path = self.run_dir / "tachys_ema_geometry_v9_4i.csv"

    def _runtime(self) -> dict[str, Any]:
        return json.loads(
            self.runtime_path.read_text(
                encoding="utf-8"
            )
        )

    def _geometry_tail(self, limit: int = 900) -> list[dict[str, str]]:
        with self.geometry_path.open(
            "r",
            encoding="utf-8",
            errors="replace",
            newline="",
        ) as handle:
            rows = list(csv.DictReader(handle))
        return rows[-limit:]

    @staticmethod
    def _unique_arcs(rows: list[dict[str, str]]) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        for row in reversed(rows):
            arc_id = str(row.get("arc_id") or "").strip()
            direction = str(row.get("arc_direction") or "").strip().upper()
            if not arc_id or arc_id in seen or direction not in ("UP", "DOWN"):
                continue
            seen.add(arc_id)
            out.append((arc_id, direction))
            if len(out) >= 6:
                break
        return list(reversed(out))

    def read(self) -> R22ShadowSourceState:
        runtime = self._runtime()
        rows = self._geometry_tail()
        if not rows:
            raise RuntimeError("R22 geometry file has no rows")

        last = rows[-1]
        now_ts = _num(runtime.get("updated_wall"))
        if now_ts is None:
            raise RuntimeError("R22 runtime updated_wall unavailable")

        quote = runtime.get("quote") or {}
        ticker = str(quote.get("ticker") or last.get("ticker") or "")
        if not ticker:
            raise RuntimeError("R22 current ticker unavailable")

        close_ts = _num(quote.get("close_ts"))
        open_ts = close_ts - 900.0 if close_ts is not None else None
        contract_age = (
            max(0.0, min(900.0, now_ts - open_ts))
            if open_ts is not None
            else max(0.0, 900.0 - (_num(last.get("seconds_left")) or 900.0))
        )

        # Use source-native structural slopes already published by the physical
        # observer. No R22 strategy permission/route fields are consulted.
        ema9_sides = [
            _sign_side(_num(last.get(name)), eps=0.02)
            for name in ("struct_slope3m", "struct_slope6m", "struct_slope9m")
        ]
        nonnull_ema9 = [side for side in ema9_sides if side is not None]
        ema9_side = (
            nonnull_ema9[0]
            if nonnull_ema9
            and all(side is nonnull_ema9[0] for side in nonnull_ema9)
            else None
        )

        ema30_side = _sign_side(
            _num(last.get("ema30_slope3m")),
            eps=0.01,
        )

        # Directional residence is measured from recent physical price/EMA
        # relationships, not from a legacy territory label.
        recent = rows[-120:]
        residence_votes = 0
        residence_total = 0
        if ema9_side is not None:
            for row in recent:
                btc = _num(row.get("btc_price"))
                e9 = _num(row.get("ema9"))
                e30 = _num(row.get("ema30"))
                if btc is None or e9 is None or e30 is None:
                    continue
                residence_total += 1
                if ema9_side is Side.YES and btc >= e9 >= e30:
                    residence_votes += 1
                elif ema9_side is Side.NO and btc <= e9 <= e30:
                    residence_votes += 1

        directional_residence = bool(
            residence_total >= 8
            and residence_votes / residence_total >= 0.62
        )

        aligned_now = bool(
            ema9_side is not None
            and ema9_side is ema30_side
            and directional_residence
        )

        # Measure how long the current aligned/parallel physical condition has
        # persisted in the geometry stream. This is descriptive persistence,
        # not a contract-count permission gate.
        persistence_start_ms: float | None = None
        if aligned_now:
            for row in reversed(rows):
                s9 = _sign_side(_num(row.get("struct_slope3m")), eps=0.02)
                s30 = _sign_side(_num(row.get("ema30_slope3m")), eps=0.01)
                btc = _num(row.get("btc_price"))
                e9 = _num(row.get("ema9"))
                e30 = _num(row.get("ema30"))
                if (
                    s9 is not ema9_side
                    or s30 is not ema9_side
                    or btc is None
                    or e9 is None
                    or e30 is None
                ):
                    break
                resident = (
                    (ema9_side is Side.YES and btc >= e9 >= e30)
                    or (ema9_side is Side.NO and btc <= e9 <= e30)
                )
                if not resident:
                    break
                persistence_start_ms = _num(row.get("epoch_ms"))

        last_ms = _num(last.get("epoch_ms"))
        persistence_seconds = (
            max(0.0, (last_ms - persistence_start_ms) / 1000.0)
            if (
                last_ms is not None
                and persistence_start_ms is not None
            )
            else 0.0
        )

        arcs = self._unique_arcs(rows)
        alternating = bool(
            len(arcs) >= 4
            and all(
                arcs[i][1] != arcs[i - 1][1]
                for i in range(1, len(arcs))
            )
        )

        parent = str(last.get("parent_direction") or "").upper()
        rolling = bool(
            ema9_side is not None
            and (
                (ema9_side is Side.YES and parent in ("UP", "YES"))
                or (ema9_side is Side.NO and parent in ("DOWN", "NO"))
            )
        )

        rolling_repetitions = 0
        if ema9_side is not None:
            target = "UP" if ema9_side is Side.YES else "DOWN"
            rolling_repetitions = sum(
                1 for _, direction in arcs[-4:]
                if direction == target
            )

        physical = PhysicalEvidence(
            ema9_direction=ema9_side,
            ema30_direction=ema30_side,
            ema_pair_parallel=aligned_now,
            directional_residence=directional_residence,
            rolling_mountain_repetitions=rolling_repetitions,
            contracts_persistent=persistence_seconds / 900.0,
            alternating_mountain=alternating and not aligned_now,
            rolling_mountain=rolling,
            # Heist and Release remain unqualified here until their clean
            # physical sidecar detectors are wired. No legacy labels used.
            qualified_heist=False,
            compression_unresolved=False,
        )

        snapshot = MarketSnapshot(
            now_ts=now_ts,
            ticker=ticker,
            contract_age_s=contract_age,
            yes_ask=_num(quote.get("yes_ask")),
            no_ask=_num(quote.get("no_ask")),
            quote_current=bool(
                quote.get("valid") is True
                and (_num(quote.get("exchange_age_sec")) or 999) <= 15.0
            ),
            depth_available=bool(
                (_num(quote.get("yes_bid_size")) or 0) > 0
                and (_num(quote.get("no_bid_size")) or 0) > 0
            ),
            metadata={
                "source": "R22_RUN_FILES_READ_ONLY",
                "geometry_last_epoch_ms": last_ms,
                "persistence_seconds": persistence_seconds,
                "recent_arcs": arcs,
                "legacy_strategy_routes_used": False,
            },
        )

        geometry_age = (
            max(0.0, now_ts - last_ms / 1000.0)
            if last_ms is not None
            else None
        )
        return R22ShadowSourceState(
            frame=ShadowFrame(
                evidence=physical,
                snapshot=snapshot,
            ),
            run_id=runtime.get("run_id"),
            session_id=runtime.get("session_id"),
            source_files={
                "runtime": str(self.runtime_path),
                "geometry": str(self.geometry_path),
            },
            geometry_rows_used=len(rows),
            geometry_age_seconds=geometry_age,
        )
