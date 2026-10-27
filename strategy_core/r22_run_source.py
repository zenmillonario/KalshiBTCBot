from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from strategy_core.detectors.heist_geometry import (
    HeistGeometryDetection,
    detect_heist_geometry,
)
from strategy_core.detectors.mountain_geometry import detect_mountain_geometry
from strategy_core.detectors.release_geometry import build_release_probe
from strategy_core.config_loader import (
    ToolConfigBundle,
    load_default_tool_configs,
)
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

    def __init__(
        self,
        run_dir: str | Path,
        configs: ToolConfigBundle | None = None,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.configs = configs or load_default_tool_configs()
        self.runtime_path = self.run_dir / "tachys_runtime_hf2.json"
        self.geometry_path = self.run_dir / "tachys_ema_geometry_v9_4i.csv"
        self._last_qualified_heist: HeistGeometryDetection | None = None

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

        # Directional residence is measured from raw geometry. Rail persistence
        # deliberately tolerates shallow pullbacks/fakeouts instead of requiring
        # every callback to remain perfectly aligned.
        last_ms = _num(last.get("epoch_ms"))
        if last_ms is not None:
            current_residence_cutoff = last_ms - 900_000.0
            recent = [
                row
                for row in rows
                if (
                    (_num(row.get("epoch_ms")) or -1.0)
                    >= current_residence_cutoff
                )
            ]
        else:
            recent = rows[-90:]
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

        residence_fraction = (
            residence_votes / residence_total
            if residence_total
            else 0.0
        )
        directional_residence = bool(
            residence_total >= 8
            and residence_fraction >= 0.62
        )

        aligned_now = bool(
            ema9_side is not None
            and ema9_side is ema30_side
            and directional_residence
        )

        rail_persistence_seconds = 0.0
        rail_alignment_fraction = 0.0
        rail_residence_fraction = 0.0
        if aligned_now and last_ms is not None:
            for window_s in (1800.0, 1500.0, 1200.0, 900.0, 720.0, 600.0):
                cutoff = last_ms - window_s * 1000.0
                window_rows = [
                    row for row in rows
                    if (_num(row.get("epoch_ms")) or -1.0) >= cutoff
                ]
                if len(window_rows) < 8:
                    continue
                align = 0
                reside = 0
                usable = 0
                first_window_ms = None
                for row in window_rows:
                    ts = _num(row.get("epoch_ms"))
                    s9 = _sign_side(_num(row.get("struct_slope3m")), eps=0.02)
                    s30 = _sign_side(_num(row.get("ema30_slope3m")), eps=0.01)
                    btc = _num(row.get("btc_price"))
                    e9 = _num(row.get("ema9"))
                    e30 = _num(row.get("ema30"))
                    if (
                        ts is None
                        or btc is None
                        or e9 is None
                        or e30 is None
                    ):
                        continue
                    if first_window_ms is None:
                        first_window_ms = ts
                    usable += 1
                    if s9 is ema9_side and s30 is ema9_side:
                        align += 1
                    if (
                        (ema9_side is Side.YES and btc >= e9 >= e30)
                        or (ema9_side is Side.NO and btc <= e9 <= e30)
                    ):
                        reside += 1
                if usable < 8 or first_window_ms is None:
                    continue
                align_fraction = align / usable
                reside_fraction = reside / usable
                span_s = max(0.0, (last_ms - first_window_ms) / 1000.0)
                if align_fraction >= 0.70 and reside_fraction >= 0.60:
                    rail_persistence_seconds = span_s
                    rail_alignment_fraction = align_fraction
                    rail_residence_fraction = reside_fraction
                    break

        persistence_seconds = rail_persistence_seconds

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

        # Raw tool-specific physical detectors. Their outputs describe geometry
        # only; they do not read legacy R22 strategy routes or permissions.
        mountain = detect_mountain_geometry(
            rows,
            self.configs.mountain_detector,
        )
        heist = detect_heist_geometry(
            rows,
            self.configs.heist_detector,
        )
        if heist.qualified_box:
            self._last_qualified_heist = heist

        release_probe = build_release_probe(
            rows,
            heist=(
                self._last_qualified_heist
                if self._last_qualified_heist is not None
                else heist
            ),
            mountain=mountain,
        )

        rail_established = bool(
            aligned_now
            and persistence_seconds >= 900.0
        )

        # A true established Rail owns before a sideways-box interpretation.
        # A qualified Heist owns before Alternating Mountain. Unresolved
        # compression may only suppress UNKNOWN/generic rolling terrain, never
        # a clean already-qualified Mountain.
        qualified_heist = bool(
            heist.qualified_box
            and not rail_established
        )
        qualified_mountain = bool(
            mountain.qualified_alternating_mountain
            and not rail_established
            and not qualified_heist
        )
        unresolved_compression = bool(
            heist.compression_unresolved
            and not rail_established
            and not qualified_heist
            and not qualified_mountain
        )

        physical = PhysicalEvidence(
            ema9_direction=ema9_side,
            ema30_direction=ema30_side,
            ema_pair_parallel=aligned_now,
            directional_residence=directional_residence,
            # Live raw Rail qualification currently uses tolerant 1–2 contract
            # persistence; repeated rolling-Mountain graduation remains a core
            # capability but is not fabricated from alternating arc counts.
            rolling_mountain_repetitions=0,
            contracts_persistent=persistence_seconds / 900.0,
            alternating_mountain=qualified_mountain,
            rolling_mountain=(
                rolling
                and not qualified_mountain
                and not qualified_heist
            ),
            qualified_heist=qualified_heist,
            compression_unresolved=unresolved_compression,
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
                "rail_alignment_fraction": rail_alignment_fraction,
                "rail_residence_fraction": rail_residence_fraction,
                "recent_arcs": arcs,
                "mountain": mountain.tool_metadata(),
                "heist": heist.tool_metadata(),
                "release_probe": release_probe,
                "territory_detector_summary": {
                    "rail_established": rail_established,
                    "qualified_heist": qualified_heist,
                    "qualified_mountain": qualified_mountain,
                    "compression_unresolved": unresolved_compression,
                },
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
