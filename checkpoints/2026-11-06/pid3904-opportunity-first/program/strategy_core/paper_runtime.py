"""Standalone Tool Rack PAPER coordinator: one source, Commander and writer.

No R22 runtime, permission route, shadow comparison or legacy Commander is
imported. Read-only source workers keep receiving while this coordinator owns
all tool state and executes explicit decisions in one thread.
"""
from __future__ import annotations

from collections import Counter, deque
from contextlib import ExitStack
from dataclasses import fields, is_dataclass, replace
from decimal import Decimal
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Any, Mapping

from strategy_core.commander import CommanderDecision, OneCommander
from strategy_core.commander_candidates import ema9_continuation_precedent
from strategy_core.dual_lane import _current_mission_parent
from strategy_core.paper_execution import FloorPolicy, PaperBook, PaperExecutioner
from strategy_core.physical_source import DirectPhysicalSource
from strategy_core.source_freshness import RECEIPT_KEY, capture_source_receipt, current_source_is_fresh
from strategy_core.tool_rack import ToolRackController
from strategy_core.tp_geometry import build_tp_geometry
from strategy_core.counter_observers import build_counter_evidence
from strategy_core.leg_ledger import LegPerformanceLedger
from strategy_core.tools.release import ReleaseEvidence
from strategy_core.tools.management import (
    ARC_CONTRACT_PROFIT_REASON, THIRD_WEAKNESS_COLLECTION_POLICY,
    entry_candle_evidence, mission_collection_evidence,
    number as number_finite,
)
from strategy_core.types import Action, MarketSnapshot, Side, Territory
from strategy_core.recovery import RecoveryTracker


RUNTIME_REVISION = "TOOL_RACK_PAPER_OPPORTUNITY_FIRST_COMMANDER_45M_20261106"
_projection_warnings: set[str] = set()


def plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, deque)):
        return [plain(item) for item in value]
    return value


def opportunity_audit(commander: OneCommander, snapshot: MarketSnapshot,
                      decision: CommanderDecision, receipt: Any = None, *,
                      evaluated: bool = False) -> dict[str, Any]:
    """Record the current Commander's review and the actual admission outcome.

    Entry-window, continuity and inventory paths may return without evaluating
    candidates. Never display a retained review from another source frame as
    a new opportunity. This record is telemetry, not another decision maker.
    """
    review = getattr(commander, "opportunity_review", None)
    geometry = snapshot.metadata.get("current_geometry")
    geometry = geometry if isinstance(geometry, Mapping) else {}
    source_ms = geometry.get("epoch_ms")
    generation = snapshot.metadata.get("geometry_continuity_generation")
    current = bool(evaluated and isinstance(review, Mapping)
        and review.get("ticker") == snapshot.ticker
        and source_ms is not None
        and review.get("source_ms") == source_ms
        and review.get("continuity_generation") == generation)
    result = plain(review) if current else {
        "revision": "OPPORTUNITY_FIRST_COMMANDER_V1",
        "ticker": snapshot.ticker,
        "source_ms": source_ms,
        "continuity_generation": generation,
        "watch_state": "NOT_EVALUATED_THIS_FRAME",
    }
    result.update(evaluated_current_frame=current, final_action=decision.action.value,
                  final_reason=decision.reason, execution_authority=False)
    if receipt is not None:
        result["receipt_status"] = receipt.status
        result["receipt_reason"] = receipt.reason
    return result


def atomic_json(path: Path, payload: Any, *, required: bool = True) -> bool:
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(plain(payload), handle, sort_keys=True, ensure_ascii=True, allow_nan=False)
            handle.write("\n")
        for attempt in range(3):
            try:
                os.replace(temporary, path)
                _projection_warnings.discard(str(path))
                return True
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.02)
    except OSError as exc:
        if required:
            raise
        if str(path) not in _projection_warnings:
            print(f"READ_ONLY_PROJECTION_DELAYED {path.name} {type(exc).__name__}; durable ledger retained", flush=True)
            _projection_warnings.add(str(path))
        return False
    return False


class GlobalPaperLease:
    """OS-released exclusive lease shared by every Tool Rack run directory."""
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle = None

    def __enter__(self) -> "GlobalPaperLease":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b" ")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise RuntimeError("ANOTHER_TOOL_RACK_PAPER_ENGINE_IS_RUNNING") from None
        self.handle = handle
        return self

    def __exit__(self, *args: Any) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None


def source_manifest(root: Path) -> dict[str, Any]:
    files = [p for p in (root / "strategy_core").rglob("*")
             if p.is_file() and p.suffix in (".py", ".json", ".html", ".css", ".js")]
    files += [p for p in root.glob("*TOOL_RACK_PAPER*") if p.is_file() and p.suffix != ".zip"]
    files += [root / name for name in ("TOOL_RACK_RECONCILE.py", "05_RECONCILE_PREVIOUS_TOOL_RACK_RUN.cmd")
              if (root / name).is_file()]
    hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    content = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return {"files": hashes, "source_and_config_sha256": hashlib.sha256(content).hexdigest()}


def snapshot_from_book(book: PaperBook | None, *, now_ts: float,
                       metadata: Mapping[str, Any], ticker: str = "",
                       close_ts: float | None = None) -> MarketSnapshot:
    if book is None:
        return MarketSnapshot(now_ts, ticker, 900.0 if close_ts is None else
                              max(0.0, min(900.0, now_ts - close_ts + 900.0)),
                              None, None, False, False, metadata)
    def best(levels: Any) -> float | None:
        return float(levels[0].price) if levels else None
    receive_age = now_ts - book.observed_ts
    exchange_age = None if book.exchange_ts is None else now_ts - book.exchange_ts
    fresh = bool(book.current and 0 <= receive_age <= 3.0 and now_ts < book.close_ts
                 and (exchange_age is None or -2.0 <= exchange_age <= 15.0))
    return MarketSnapshot(now_ts=now_ts, ticker=book.ticker,
        contract_age_s=max(0.0, min(900.0, now_ts - book.close_ts + 900.0)),
        yes_ask=best(book.asks(Side.YES)), no_ask=best(book.asks(Side.NO)),
        quote_current=fresh,
        depth_available=bool(book.yes_bids and book.no_bids),
        metadata={**metadata, "quote_id": book.quote_id, "quote_observed_ts": book.observed_ts,
                  "quote_exchange_ts": book.exchange_ts,
                  "native_depth": {"ticker": book.ticker, "quote_id": book.quote_id,
                      "yes_bids": tuple((p.price, p.quantity) for p in book.yes_bids),
                      "no_bids": tuple((p.price, p.quantity) for p in book.no_bids)}},
        yes_bid=best(book.yes_bids), no_bid=best(book.no_bids),
        entry_allowed=book.entry_allowed, yes_sell_allowed=book.yes_sell_allowed,
        no_sell_allowed=book.no_sell_allowed)


def current_release_reacquisition(result: Any, snapshot: MarketSnapshot) -> bool:
    """A retained owner may reacquire from current affirmative transfer proof.

    Ownership's historical latch is not entry evidence. Conversely, a fresh
    revalidation of that same transfer is not made stale by its owner's label.
    The source timestamp and detector evidence both belong to this capture.
    """
    if (not result.handoff_confirmed or result.owned_territory is not Territory.RELEASE_TRANSITION
            or result.release_boundary_name != "RELEASE_TRANSITION_LATCHED"
            or snapshot.metadata.get("physical_current") is not True):
        return False
    evidence = result.release_diagnostics.get("entry_evidence")
    if (not isinstance(evidence, ReleaseEvidence) or not evidence.confirmed
            or evidence.candidate_side is not result.owned_side):
        return False
    try:
        observed = float(snapshot.metadata["geometry_last_epoch_ms"]) / 1000.0
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(observed) and 0 <= snapshot.now_ts - observed <= 3.0


def current_primary_reacquisition(result: Any) -> bool:
    if result.active_tool is None:
        return False
    raw, owned = result.raw_decision, result.owned_territory
    mountains = (Territory.ALTERNATING_MOUNTAIN, Territory.ROLLING_MOUNTAIN)
    same_family = raw.territory in mountains and owned in mountains and raw.side is not None
    return (raw.territory is owned or same_family) and raw.side is result.owned_side


class ToolRackPaperEngine:
    """Synchronous decision core; network and UI remain outside the boundary."""
    def __init__(self, run_dir: Path, *, source_root: Path | None = None) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.physical = DirectPhysicalSource()
        self.rack = ToolRackController(configs=self.physical.configs)
        self.commander = OneCommander()
        self.recovery = RecoveryTracker()
        self.leg_ledger = LegPerformanceLedger(self.run_dir / "leg_performance.jsonl")
        self._seq = 0
        self._previous_hash = "0" * 64
        self._last_entry_block_quote: dict[str, str] = {}
        self._pending_tool_exits: dict[str, Any] = {}
        self._reason_counts: Counter[str] = Counter()
        self._last_console_reason: tuple[Any, ...] | None = None
        self._last_rack = None
        self._last_journal_seq = -1
        self._source_continuity_generation = 0
        self._awaiting_reacquisition = False
        self._mission_history_digest: str | None = None
        self._last_quote_echo_id: tuple[str, str] | None = None
        self.latest_status: dict[str, Any] = {}
        self.started_at = time.time()
        root = source_root or Path(__file__).resolve().parent.parent
        with ExitStack() as startup:
            self.executor = startup.enter_context(PaperExecutioner(self.run_dir))
            self.audit = startup.enter_context((self.run_dir / "decisions.jsonl").open(
                "a", encoding="utf-8", newline="\n"))
            self.geometry_log = startup.enter_context((self.run_dir / "physical_geometry.jsonl").open(
                "a", encoding="utf-8", newline="\n"))
            self.mission_history_log = startup.enter_context((self.run_dir / "mission_history.jsonl").open(
                "a", encoding="utf-8", newline="\n"))
            self.quote_echo_log = startup.enter_context((self.run_dir / "quote_echo_shadow.jsonl").open(
                "a", encoding="utf-8", newline="\n"))
            atomic_json(self.run_dir / "RUN_MANIFEST.json", {
                "mode": "PAPER", "runtime_revision": RUNTIME_REVISION, "run_id": self.run_dir.name,
                "started_at": self.started_at, "strategy_authority": "TOOL_RACK_ONE_COMMANDER",
                "r22_process_required": False, "legacy_policy_imported": False,
                "account_or_order_api_available": False, "starting_cash": 1000.0,
                "fee_model": "NOMINAL_0.07_CEIL_CENT_PAPER_ASSUMPTION",
                "paper_execution_is_not_venue_fill_evidence": True,
                **source_manifest(root)})
            startup.pop_all()

    def _contract_house_state(self, ticker: str) -> Mapping[str, Any]:
        """Contract-local realized-win state for the operator's protect-the-house rule.

        One profitable close enters CAUTION. Two profitable closes, or one
        completed position at >= +100% gross ROI, enters PROTECTED. The state
        is derived only from committed PAPER events for the current ticker and
        resets automatically on the next ticker. Market Heist remains the
        explicit exception; Commander also permits an A+/easy current Mountain
        terminal at <=20c rather than blocking a great low-risk setup solely
        because the house is protected.
        """
        if not ticker:
            return {"mode": "OPEN", "wins": 0, "best_gross_roi": None}
        groups: dict[str, dict[str, Any]] = {}
        for event in self.executor.events:
            if event.get("ticker") != ticker or event.get("event") not in {
                    "PARTIAL_EXIT", "EXIT", "SETTLEMENT"}:
                continue
            pid = str(event.get("position_id") or event.get("trade_id") or "")
            if not pid:
                continue
            g = groups.setdefault(pid, {"gross": 0.0, "cost": 0.0, "complete": False})
            try:
                g["gross"] += float(event.get("gross_pnl") or 0.0)
                g["cost"] += float(event.get("cost") or 0.0)
            except (TypeError, ValueError):
                pass
            if event.get("event") in {"EXIT", "SETTLEMENT"}:
                g["complete"] = True
        completed = []
        for pid, g in groups.items():
            if not g["complete"] or g["cost"] <= 0:
                continue
            roi = g["gross"] / g["cost"]
            completed.append({"position_id": pid, "gross_pnl": g["gross"],
                              "cost": g["cost"], "gross_roi": roi})
        wins = [row for row in completed if row["gross_pnl"] > 0]
        best = max((row["gross_roi"] for row in wins), default=None)
        if len(wins) >= 2 or (best is not None and best >= 1.0):
            mode = "PROTECTED"
        elif wins:
            mode = "CAUTION"
        else:
            mode = "OPEN"
        return {
            "revision": "OPERATOR_AUTHORIZED_CONTRACT_HOUSE_PROTECTION_V1",
            "ticker": ticker,
            "mode": mode,
            "wins": len(wins),
            "best_gross_roi": best,
            "completed_positions": completed,
            "rule": "ONE_WIN_CAUTION_TWO_WINS_OR_100PCT_PROTECTED_HEIST_PLUS_SUB20_TRUE_EDGE_EXCEPTION",
        }

    @staticmethod
    def _floor_policy(intents: Any, position: Any, snapshot: MarketSnapshot | None = None) -> FloorPolicy | None:
        policy = next((intent.metadata.get("floor_policy") for intent in intents
                       if intent.metadata.get("floor_policy")), None)
        policy = policy or position.entry_metadata.get("floor_policy")
        if not isinstance(policy, Mapping):
            return None
        arguments = {"arm_roi": float(policy["arm_roi"]),
                     "trail_fraction": float(policy["trail_fraction"]),
                     "min_age_seconds": float(policy.get("min_age_s", 0.0))}
        if policy.get("immediate_arm_roi") is not None:
            arguments["immediate_arm_roi"] = float(policy["immediate_arm_roi"])
        arguments["first_arm_allowed"] = policy.get("first_arm_allowed", True)
        arguments["first_arm_from_current_bid"] = policy.get("first_arm_from_current_bid", False)
        arguments["roi_trail_tiers"] = tuple(tuple(float(value) for value in tier)
                                             for tier in policy.get("roi_trail_tiers", ()))
        if policy.get("tighten_armed_to") is not None:
            arguments["tighten_armed_to"] = float(policy["tighten_armed_to"])
        held = plain(position)
        mission = (held.get("entry_metadata") or {}).get("mission") or {}
        strict_parent = (mission.get("purpose") in ("MAIN_CONTRACT", "ARC_RETURN")
                         and mission.get("collection_policy") == THIRD_WEAKNESS_COLLECTION_POLICY)
        if strict_parent and held.get("floor_bid") is None:
            collection = mission_collection_evidence(held, snapshot) if snapshot is not None else {}
            collectible = bool(collection.get("collection_qualified")
                and collection.get("collection_authority") != ARC_CONTRACT_PROFIT_REASON)
            if not collectible:
                # The held-parent guard still prevents ordinary +50% arming and
                # terminal tightening without physical collection proof. It must
                # not suppress the separately earned +100%/+150% executable-bid
                # peak lock approved for living MAIN/ARC_RETURN positions.
                arguments["first_arm_allowed"] = False
                arguments.pop("tighten_armed_to", None)
        # PID252 operator-authorized leg-aligned winner extension.  A +100%
        # threshold protects a winner; it must not mechanically collect a
        # position while the same living EMA9 leg is still expanding.  Before
        # the first floor is armed, postpone the ordinary +100% arm to +200%
        # while current owner/Release remains the held side and there is no
        # terminal/stall evidence.  As soon as the leg stalls/turns, the normal
        # policy becomes eligible again from the current executable bid.
        if snapshot is not None and held.get("floor_bid") is None:
            held_side = str(held.get("side") or "").upper()
            strategy = snapshot.metadata.get("commander_strategy")
            strategy = strategy if isinstance(strategy, Mapping) else {}
            mountain = snapshot.metadata.get("mountain")
            mountain = mountain if isinstance(mountain, Mapping) else {}
            mission_ctx = snapshot.metadata.get("mission_context")
            mission_ctx = mission_ctx if isinstance(mission_ctx, Mapping) else {}
            parent = mission_ctx.get("parent")
            parent = parent if isinstance(parent, Mapping) else {}
            parent_status = str(parent.get("status") or "").upper()
            structure = mountain.get("parent_structure")
            structure = structure if isinstance(structure, Mapping) else {}
            physical_owner = (str(parent.get("side") or "").upper()
                              if parent_status not in {"COMPLETED", "INVALIDATED"} else "")
            if physical_owner not in {"YES", "NO"} and structure.get("parent_terminal_ready") is not True:
                physical_owner = str(structure.get("parent_side") or "").upper()
            if physical_owner not in {"YES", "NO"}:
                physical_owner = str(strategy.get("owned_side") or mountain.get("owner_side") or "").upper()
            release_side = str(snapshot.metadata.get("release_candidate_side") or "").upper()
            release_same = bool(snapshot.metadata.get("release_in_progress") is True
                                and release_side == held_side and held_side in {"YES", "NO"})
            continuation = ema9_continuation_precedent(snapshot)
            continuation_same = bool(continuation.get("qualified") is True
                                     and continuation.get("side") == held_side)
            current_parent = _current_mission_parent(snapshot)
            current_parent_opposes = bool(current_parent
                and held_side in {"YES", "NO"}
                and current_parent["side"] != held_side)
            current_release_same = bool(release_same
                or snapshot.metadata.get("release_confirmed_current") is True
                    and release_side == held_side and held_side in {"YES", "NO"})
            # A local continuation briefing cannot independently grant the
            # living-parent +200% first-arm exception against a verified
            # current parent. Keep current Release transfers and the existing
            # unknown/stale-parent fallbacks; do not rewrite the briefing or
            # any already armed protection.
            if current_parent_opposes and not current_release_same:
                continuation_same = False
            owner_same = physical_owner == held_side
            terminal = bool(mountain.get("terminal_evidence_qualified") is True
                            and mountain.get("mature_edge") is True
                            and mountain.get("edge_window_active") is True)
            stalled = bool(mountain.get("stall") is True or mountain.get("hesitation") is True)
            entry_md = held.get("entry_metadata") if isinstance(held.get("entry_metadata"), Mapping) else {}
            seed_family = str(entry_md.get("commander_candidate_family") or "").upper()
            heist_seed = bool(str(held.get("tool") or "").upper() == "MARKET_HEIST"
                              or seed_family in {"QUOTE_WAVE_SCALP", "EDGE_HEIST",
                                                 "HISTORICAL_EXTREME_RELEASE_PREP"})
            promoted_main = str(held.get("custody_state") or "").upper() == "PROMOTED_MAIN"
            entry_reason = str(held.get("entry_reason") or "").upper()
            seconds_left = max(0.0, float(held.get("close_ts") or snapshot.now_ts) - snapshot.now_ts)
            late_release_protection = bool(
                entry_reason == "RELEASE_CONFIRMED_LEVIATHAN_HANDOFF"
                and seconds_left <= 300.0
            )
            aligned_runner = bool((owner_same or release_same or continuation_same)
                                  and not terminal and not stalled
                                  and not late_release_protection
                                  and (str(held.get("lane") or "MAIN").upper() == "MAIN"
                                       or heist_seed or promoted_main))
            if (not aligned_runner and heist_seed and not promoted_main
                    and str(held.get("lane") or "").upper() == "TACTICAL"
                    and owner_same is False and physical_owner in {"YES", "NO"}):
                # Counterwind tactical renter: full-lot, positive-net quick
                # harvest after +30%, not PRIMARY runner custody.  This arms
                # a 5% trail; it cannot guarantee an exit at the observed peak.
                arguments["arm_roi"] = min(float(arguments["arm_roi"]), 0.30)
                arguments["trail_fraction"] = min(float(arguments["trail_fraction"]), 0.05)
                arguments["first_arm_from_current_bid"] = True
                arguments["min_age_seconds"] = 0.0
            if not aligned_runner and held.get("peak_bid") is not None:
                entry_price = number_finite(held.get("entry_price"))
                peak = number_finite(held.get("peak_bid"))
                if (entry_price is not None and entry_price > 0 and peak is not None
                        and peak / entry_price >= 2.0 and (terminal or stalled)):
                    # Earned +100% and current stall: tighten an already armed
                    # floor without retroactively claiming the prior top bid.
                    arguments["arm_roi"] = min(float(arguments["arm_roi"]), 1.0)
                    arguments["trail_fraction"] = min(float(arguments["trail_fraction"]), 0.035)
                    arguments["tighten_armed_to"] = min(
                        float(arguments.get("tighten_armed_to", 1.0)), 0.035)
            # PID18244 #4: the source-owned EMA9 PARENT (not the momentary
            # local arc, rack's child label, or tool's healthy-breath flag)
            # decides whether a TACTICAL counterwind renter may borrow MAIN
            # runner breathing. A real counter-parent Heist renter retains its
            # *original entry* quick-profit arm and peak trail after its first
            # candle. This changes no entry authority and cannot undo floors.
            # Fresh native parent identification is required; unknown or
            # stale history never creates new floor permission.
            native_geo = snapshot.metadata.get("current_geometry")
            native_geo = native_geo if isinstance(native_geo, Mapping) else {}
            parent_dir = str(native_geo.get("parent_direction") or "").upper()
            native_parent_side = ("YES" if parent_dir == "UP" else "NO"
                                  if parent_dir == "DOWN" else "")
            source_ms = native_geo.get("epoch_ms")
            native_parent_current = bool(snapshot.metadata.get("physical_current") is True
                and current_source_is_fresh(snapshot, source_ms, max_age_seconds=3.0))
            original_floor = entry_md.get("floor_policy")
            original_floor = original_floor if isinstance(original_floor, Mapping) else {}
            original_arm = number_finite(original_floor.get("arm_roi"))
            original_trail = number_finite(original_floor.get("trail_fraction"))
            original_immediate = number_finite(original_floor.get("immediate_arm_roi"))
            tactical_counterparent = bool(
                held.get("floor_bid") is None
                and str(held.get("lane") or "").upper() == "TACTICAL"
                and str(held.get("custody_state") or "NORMAL").upper() not in
                    {"PROMOTED_MAIN", "LAZARUS"}
                and heist_seed
                and native_parent_current and native_parent_side in {"YES", "NO"}
                and native_parent_side != held_side
                and not current_release_same
                and entry_candle_evidence(held, snapshot)["entry_candle_complete"]
                and original_arm is not None and 0 < original_arm <= 0.40
                and original_immediate is not None and 0 < original_immediate <= 0.40
                and original_trail is not None and 0 < original_trail <= 0.05
            )
            if tactical_counterparent:
                arguments["arm_roi"] = min(float(arguments["arm_roi"]), original_arm)
                arguments["immediate_arm_roi"] = min(
                    float(arguments.get("immediate_arm_roi", original_immediate)),
                    original_immediate)
                arguments["trail_fraction"] = min(
                    float(arguments["trail_fraction"]), original_trail)
                arguments["first_arm_from_current_bid"] = True
                arguments["min_age_seconds"] = min(float(arguments["min_age_seconds"]),
                                                     float(original_floor.get("min_age_s", 0.0)))
                arguments["first_arm_allowed"] = True
            if aligned_runner and not tactical_counterparent:
                arguments["arm_roi"] = max(float(arguments["arm_roi"]), 2.0)
                if arguments.get("immediate_arm_roi") is not None:
                    arguments["immediate_arm_roi"] = max(float(arguments["immediate_arm_roi"]), 2.0)
                # Keep a real protective floor once +200% is earned, but do
                # not choke the live leg with the quick-renter band.
                arguments["trail_fraction"] = max(float(arguments["trail_fraction"]), 0.05)

            # PID8552 #5: the 3%-at-150% return policy was cutting the ENTIRE
            # NO lot at 61c while BTC/EMA9 were still accelerating DOWN inside
            # a wide, separated NO gap.  A living sloped Rail/Rolling flow is
            # not a sideways Mountain scalp. Do not make an irreversible *first*
            # floor while the held-side physical corridor still expands with
            # meaningful settlement runway. Ordinary opposite wicks may cause
            # large binary-price repricing without ending the BTC/EMA9 leg.
            # Never undo an already-committed floor or objective exit.
            geo = snapshot.metadata.get("current_geometry")
            geo = geo if isinstance(geo, Mapping) else {}
            gap_context = snapshot.metadata.get("ema9_ema30_cross_context")
            gap_context = gap_context if isinstance(gap_context, Mapping) else {}
            lifecycle = gap_context.get("gap_lifecycle")
            lifecycle = lifecycle if isinstance(lifecycle, Mapping) else {}
            slope_sign = 1.0 if held_side == "YES" else -1.0 if held_side == "NO" else 0.0
            signed_gap = number_finite(geo.get("ema_gap"))
            gap_abs = abs(signed_gap) if signed_gap is not None else 0.0
            range180 = number_finite(geo.get("range180"))
            ema30_move = number_finite(geo.get("ema9_change30"))
            ema60_move = number_finite(geo.get("ema9_change60"))
            btc30_move = number_finite(geo.get("btc_change30"))
            btc60_move = number_finite(geo.get("btc_change60"))
            stage = str(lifecycle.get("stage") or "").upper()
            parent_turn = bool(structure.get("parent_terminal_ready") is True
                               or structure.get("parent_turning_or_flat") is True)
            confirmed_opposite = bool(snapshot.metadata.get("release_confirmed_current") is True
                and str(snapshot.metadata.get("release_candidate_side") or "").upper() not in {"", held_side})
            # True physical slope proof, not a fleeting territory label.  Both
            # 30/60s EMA9 and BTC agree with the held side, and EMA9 is well
            # separated from EMA30 on that side.  Unknown samples never qualify.
            slope_flow_live = bool(
                snapshot.metadata.get("physical_current") is True
                and slope_sign != 0 and signed_gap is not None
                and slope_sign * signed_gap >= max(25.0, 0.18 * (range180 or 0.0))
                and stage in {"MATURE", "ROLLING", "INHERITED_OR_UNOBSERVED_CROSS"}
                and all(v is not None for v in (ema30_move, ema60_move, btc30_move, btc60_move))
                and slope_sign * ema30_move > 0.01 and slope_sign * ema60_move > 0.01
                and slope_sign * btc30_move > 0.01 and slope_sign * btc60_move > 0.01
                and not terminal and not stalled and not parent_turn and not confirmed_opposite
            )
            # The family is deliberately not restricted to a narrow RAIL label:
            # a smooth Rolling Mountain may show the same slope/wick anatomy.
            # Do not apply to countertrend renters or a spent/sideways arc.
            if (slope_flow_live and seconds_left > 120.0
                    and str(held.get("lane") or "MAIN").upper() == "MAIN"
                    and not (heist_seed and not promoted_main)
                    and not tactical_counterparent):
                arguments["arm_roi"] = 999.0
                arguments["immediate_arm_roi"] = None
                arguments["first_arm_allowed"] = False
                arguments["roi_trail_tiers"] = ()
                arguments["tighten_armed_to"] = None

        if snapshot is not None and not entry_candle_evidence(held, snapshot)["entry_candle_complete"]:
            # The fallback entry policy cannot turn a 30s timer into a new
            # observed candle, even when current structural custody is absent.
            # Immediate earned protection and existing armed mechanics remain.
            arguments["first_arm_allowed"] = False
            arguments.pop("tighten_armed_to", None)
            # A same-entry-candle +100% executable gain is exceptional earned
            # profit and remains eligible for the irreversible peak lock.
        return FloorPolicy(**arguments)

    def _closed(self, position: Any, *, release_handoff: bool = False) -> None:
        self.rack.mark_position_closed(ticker=position.ticker, territory_id=position.territory_id,
                                      opportunity_id=position.opportunity_id, release_handoff=release_handoff,
                                      position_id=position.position_id)
        self._pending_tool_exits.pop(position.position_id, None)
        self.recovery.forget(position.position_id)

    def settle(self, result: Any) -> tuple[Any, ...]:
        held = dict(self.executor.positions)
        receipts = self.executor.settle(result)
        for receipt in receipts:
            if receipt.status == "SETTLED" and receipt.position_id in held:
                self._closed(held[receipt.position_id])
                self._print_receipt(receipt)
        return receipts

    @staticmethod
    def _print_receipt(receipt: Any) -> None:
        if receipt.event:
            event = receipt.event
            print(f"PAPER {event['event']} {event['ticker']} {event['side']} "
                  f"qty={event['qty']} @ {event['price']} | {event['tool']} | {event['reason']}", flush=True)

    def process(self, feed: Any, *, now_ts: float | None = None,
                held_books: Mapping[str, PaperBook] | None = None,
                stop_requested: bool = False,
                entry_window_closed: bool = False,
                historical_candles=()) -> dict[str, Any]:
        now = time.time() if now_ts is None else float(now_ts)
        dispatch_clock = (lambda: time.time()) if now_ts is None else (lambda: now)
        self._seq += 1
        if not feed.geometry_rows and feed.source_status.get("btc_current") is False:
            self.physical.invalidate(str(feed.source_status.get("source_error") or "BTC_SOURCE_NOT_CURRENT"))
        physical = self.physical.observe(feed.geometry_rows, now_ts=now)
        physical_current = physical.current and feed.source_status.get("btc_current", True) is True
        metadata = {**physical.metadata, "physical_current": physical_current,
                    "source_generation": feed.generation}
        # Preserve the feed's already captured monotonic receipt evidence.
        # Source time can lead local time; a current native quote cannot prove
        # that the independent BTC frame was received recently.
        source_receipt = capture_source_receipt(metadata, feed.source_status,
            captured_at=feed.observed_ts, source_generation=feed.generation)
        if source_receipt is not None:
            metadata[RECEIPT_KEY] = source_receipt
        continuity = int(metadata.get("geometry_continuity_generation", 0))
        if continuity != self._source_continuity_generation:
            self._awaiting_reacquisition = self._last_rack is not None
            self._source_continuity_generation = continuity
        for row in physical.new_rows:
            self.geometry_log.write(json.dumps(plain(row), allow_nan=False) + "\n")
        self.geometry_log.flush()
        market = feed.market
        book = feed.book
        # Immutable exact-lot context makes role occupancy visible to tools;
        # Commander and the writer still revalidate the current ledger.
        metadata["position_inventory"] = tuple(plain(p) for p in self.executor.positions.values())
        metadata["available_paper_cash"] = self.executor.cash
        metadata["contract_house_state"] = self._contract_house_state(
            market.ticker if market is not None else "")
        if market is not None:
            metadata["contract_value_context"] = {
                "ticker": market.ticker, "close_ts": market.close_ts,
                "target": getattr(market, "target", None),
                "target_source": getattr(market, "target_source", None),
                "observed_ts": now,
            }
        if market is not None and book is not None and book.ticker != market.ticker:
            raise RuntimeError("COHERENT_CAPTURE_MARKET_BOOK_MISMATCH")
        snapshot = snapshot_from_book(book, now_ts=now, metadata=metadata,
            ticker=market.ticker if market else "", close_ts=market.close_ts if market else None)
        # Observed quote changes are shadow research ONLY.  Retain both
        # market sides with available size and time, including sub-minute
        # quote oscillations that a 10-second forensic projection would miss.
        # No action, threshold, or trading permission is derived here.
        quote_key = (snapshot.ticker, str(snapshot.metadata.get("quote_id") or ""))
        if (book is not None and quote_key != self._last_quote_echo_id
                and quote_key[1] and snapshot.quote_current):
            self._last_quote_echo_id = quote_key
            self.quote_echo_log.write(json.dumps({
                "version":"QUOTE_ECHO_SHADOW_V1", "time":now,
                "ticker":snapshot.ticker, "quote_id":quote_key[1],
                "observed_ts":book.observed_ts, "exchange_ts":book.exchange_ts,
                "btc_current":physical_current,
                "btc":number_finite(metadata.get("current_geometry",{}).get("btc_price"))
                    if isinstance(metadata.get("current_geometry"), Mapping) else None,
                "yes_ask":snapshot.yes_ask,"yes_bid":snapshot.yes_bid,
                "no_ask":snapshot.no_ask,"no_bid":snapshot.no_bid,
                "yes_bid_qty":book.yes_bids[0].quantity if book.yes_bids else None,
                "no_bid_qty":book.no_bids[0].quantity if book.no_bids else None,
                "mode":"SHADOW_ONLY","execution_authority":False,
            }, allow_nan=False)+"\n")
            self.quote_echo_log.flush()
        if market is not None:
            # Completed past OHLC/EMA data is context only. The source model
            # validates completeness/known-at time and never inserts it into
            # the forward intraminute detector path.
            history = tuple(row for row in historical_candles if isinstance(row, Mapping)
                and number_finite(row.get("time")) is not None
                # Minute bars are timestamped at OPEN; the preceding bar's
                # close supplies the older contract's opening observation.
                # Completed current-contract bars also supply the current
                # EMA path, while all future/incomplete bars stay excluded.
                and market.close_ts - 2760 <= float(row["time"])
                and float(row["time"]) + 60 <= now
                and row.get("complete") is True)
            history_bytes = json.dumps(plain(history), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            history_digest = hashlib.sha256(history_bytes).hexdigest()
            if history_digest != self._mission_history_digest:
                self.mission_history_log.write(json.dumps({"known_at": now, "ticker": market.ticker,
                    "sha256": history_digest, "candles": plain(history)}, allow_nan=False) + "\n")
                self.mission_history_log.flush()
                self._mission_history_digest = history_digest
            metadata["mission_history_reference"] = history_digest
            snapshot = replace(snapshot, metadata={**snapshot.metadata, "mission_history_reference": history_digest})
            snapshot = self.rack.prepare_snapshot(snapshot, rows=physical.new_rows,
                historical_candles=history)
            metadata["mission_context"] = snapshot.metadata["mission_context"]
        result = None
        if physical_current and market is not None:
            result = self.rack.observe(physical.evidence, snapshot)
            metadata["mission_context"] = self.rack.last_mission_context
            metadata["candidate_review"] = plain(self.rack.mission_policy.reviews)
            metadata["quote_wave"] = plain(self.rack.mission_policy.quote_wave_briefing(snapshot))
            strategy_context = {
                "owned_territory": result.owned_territory.value,
                "owned_side": result.owned_side.value if result.owned_side is not None else None,
                "active_tool": result.active_tool,
                "active_overlays": list(result.active_overlays),
                "handoff_confirmed": result.handoff_confirmed,
                "release_boundary_name": result.release_boundary_name,
            }
            metadata["commander_strategy"] = strategy_context
            metadata["release_in_progress"] = result.release_in_progress
            metadata["release_candidate_side"] = (
                result.release_candidate_side.value if result.release_candidate_side is not None else None
            )
            snapshot = replace(snapshot, metadata={**snapshot.metadata,
                "mission_context": self.rack.last_mission_context,
                "commander_strategy": strategy_context,
                "release_in_progress": result.release_in_progress,
                "release_candidate_side": (
                    result.release_candidate_side.value if result.release_candidate_side is not None else None
                )})
            tp_geometry = build_tp_geometry(snapshot)
            metadata["tp_geometry"] = tp_geometry
            snapshot = replace(snapshot, metadata={**snapshot.metadata, "tp_geometry": tp_geometry})
            leg_echo = self.leg_ledger.observe(snapshot)
            metadata["leg_echo"] = leg_echo
            snapshot = replace(snapshot, metadata={**snapshot.metadata, "leg_echo": leg_echo})
            counter = build_counter_evidence(snapshot, rows=feed.geometry_rows, historical_candles=history)
            metadata.update(counter)
            snapshot = replace(snapshot, metadata={**snapshot.metadata, **counter})
            self._last_rack = result
            fresh_handoff = (result.handoff_confirmed and
                             result.release_boundary_name != "RELEASE_TRANSITION_LATCHED")
            release_reacquired = current_release_reacquisition(result, snapshot)
            primary_reacquired = current_primary_reacquisition(result)
            if fresh_handoff or release_reacquired or primary_reacquired:
                self._awaiting_reacquisition = False
                basis = ("FRESH_CONFIRMED_HANDOFF" if fresh_handoff else
                    "CURRENT_RELEASE_REACQUISITION" if release_reacquired else
                    "CURRENT_PRIMARY_REACQUISITION")
                snapshot = self.rack.record_scope_reacquisition(snapshot,
                    side=result.owned_side, basis=basis)
                metadata["mission_context"] = snapshot.metadata["mission_context"]
        decisions: list[dict[str, Any]] = []
        receipts: list[Any] = []
        books = dict(held_books or {})
        if book is not None:
            books[book.ticker] = book
        closed_this_beat = False
        completed_handoffs: list[tuple[Any, Mapping[str, Any], Any]] = []
        for position_id, old_position in list(self.executor.positions.items()):
            held_book = books.get(old_position.ticker)
            held_snapshot = snapshot_from_book(held_book, now_ts=now, metadata=metadata,
                ticker=old_position.ticker, close_ts=old_position.close_ts)
            if held_book is not None:
                exit_mark = self.executor.remaining_exit_mark(held_book,
                    position_id=position_id, now_ts=now)
                held_snapshot = replace(held_snapshot, metadata={**held_snapshot.metadata,
                    "paper_exit_mark": exit_mark,
                    "paper_execution_state": {"journal_seq": exit_mark["journal_seq"],
                        "journal_sha256": exit_mark["journal_sha256"]}})
            expired = dispatch_clock() >= old_position.close_ts
            proposed = self.rack.manage_position(plain(old_position), held_snapshot) if physical_current and not expired else ()
            # Previously accepted exits remain pending through missing
            # liquidity. A proposal deferred by Commander does not become an
            # exit obligation merely because a tool reported it this beat.
            structural_exit = next((intent for intent in proposed if intent.action is Action.EXIT
                and intent.reason != ARC_CONTRACT_PROFIT_REASON), None)
            pending = self._pending_tool_exits.get(position_id)
            if pending is not None and pending.reason == ARC_CONTRACT_PROFIT_REASON:
                # Quote-dependent profitable collection never survives as an
                # unconditional obligation or gets a refreshed source time.
                self._pending_tool_exits.pop(position_id, None)
                pending = None
            if pending is not None:
                proposed = (replace(pending, source_time=now),)
                held_snapshot = replace(held_snapshot, metadata={**held_snapshot.metadata,
                    "pending_exit_was_previously_observed": True})
            policy = self._floor_policy(proposed, old_position, held_snapshot)
            floors = self.executor.observe_floors(held_book, now_ts=dispatch_clock(),
                policies={position_id: policy} if policy is not None else {},
                position_ids=(position_id,)) if held_book is not None and not expired else ()
            position = self.executor.positions[position_id]
            breached = any(floor.position_id == position_id and floor.breached for floor in floors)
            mark = next((floor for floor in floors if floor.position_id == position_id), None)
            slot_available = not any(other.position_id != position_id and other.ticker == position.ticker
                                     and other.custody_state == "LAZARUS"
                                     for other in self.executor.positions.values())
            recovery_review = self.recovery.review(plain(position), held_snapshot, proposed, mark,
                                                   detached_slot_available=slot_available)
            decision = self.commander.decide_position(proposed, held_snapshot, plain(position),
                floor_breached=breached, stop_requested=stop_requested, recovery_review=recovery_review)
            transitioned = self.executor.record_custody(decision, position_id=position_id, now_ts=dispatch_clock())
            if transitioned:
                position = self.executor.positions[position_id]
                if position.custody_state == "LAZARUS":
                    self._pending_tool_exits.pop(position_id, None)
                    self.rack.mark_position_recovery_detached(plain(position))
                elif position.custody_state == "RECOVERED_NORMAL":
                    self._pending_tool_exits.pop(position_id, None)
                    self.rack.mark_position_recovery_restored(plain(position))
            if structural_exit is not None and (decision.action is Action.EXIT or position.exit_required):
                self._pending_tool_exits[position_id] = structural_exit
            row = {"position_id": position_id, "scope": "POSITION", "decision": plain(decision),
                   "tool_intents": plain(proposed), "floors": plain(floors)}
            self._reason_counts[decision.reason] += 1
            if decision.action is Action.EXIT and held_book is not None:
                # Ask the owning tool while its exact outgoing lot still
                # exists. This is a fresh proposal, never a cached mandate.
                # Every partial-sale beat repeats current physical validation.
                handoff = (self.rack.handoff_intent(plain(position), held_snapshot)
                    if physical_current and not expired and not stop_requested and not entry_window_closed
                    and decision.intent is not None and decision.intent.reason != ARC_CONTRACT_PROFIT_REASON
                    and market is not None and position.ticker == market.ticker else None)
                if handoff is not None:
                    row["mountain_handoff_candidate"] = plain(handoff)
                receipt = self.executor.execute(decision, held_book, now_ts=dispatch_clock(),
                    command_id=f"{self.run_dir.name}:{self._seq}:EXIT:{position_id}", position_id=position_id)
                row["receipt"] = plain(receipt)
                receipts.append(receipt)
                if receipt.status == "EXITED":
                    opposing_handoff = bool(result and result.handoff_confirmed and any(
                        intent.side is not None and intent.side is not position.side
                        for intent in result.overlay_intents))
                    self._closed(position, release_handoff=opposing_handoff)
                    self._last_entry_block_quote[position.ticker] = held_book.quote_id
                    closed_this_beat = True
                    if handoff is not None:
                        completed_handoffs.append((handoff, plain(position), receipt))
                self._print_receipt(receipt)
            decisions.append(row)
        opportunity_evaluated = False
        if stop_requested:
            entry = CommanderDecision(Action.WAIT, None, "PAPER_STOP_NO_NEW_ENTRY")
        elif entry_window_closed:
            entry = CommanderDecision(Action.WAIT, None, "PAPER_ENTRY_WINDOW_CLOSED_DRAINING")
        elif not physical_current:
            entry = CommanderDecision(Action.WAIT, None, "DIRECT_PHYSICAL_SOURCE_WARMING_OR_STALE")
        elif book is None or market is None:
            entry = CommanderDecision(Action.WAIT, None, "NATIVE_CURRENT_MARKET_BOOK_UNAVAILABLE")
        elif self._awaiting_reacquisition:
            entry = CommanderDecision(Action.WAIT, None, "PHYSICAL_CONTINUITY_RESET_AWAIT_TOOL_REACQUISITION")
        elif completed_handoffs:
            if len(completed_handoffs) != 1:
                entry = CommanderDecision(Action.WAIT, None, "CONFLICTING_COMPLETED_MOUNTAIN_HANDOFFS")
            else:
                handoff, outgoing, exit_receipt = completed_handoffs[0]
                handoff = replace(handoff, metadata={**handoff.metadata,
                    "entry_geometry": plain(metadata.get("current_geometry") or {})})
                # Preserve the captured book, but recheck its age/expiry and
                # the proposal's source age after the outgoing commit.
                entry_snapshot = snapshot_from_book(book, now_ts=dispatch_clock(), metadata=metadata,
                    ticker=market.ticker, close_ts=market.close_ts)
                entry = self.commander.decide_handoff_entry(handoff, entry_snapshot,
                    self.executor.positions, outgoing=outgoing, exit_receipt=plain(exit_receipt))
                opportunity_evaluated = True
        elif closed_this_beat or self._last_entry_block_quote.get(book.ticker) == book.quote_id:
            entry = CommanderDecision(Action.WAIT, None, "EXIT_COMMITTED_WAIT_FOR_NEXT_NATIVE_QUOTE")
        elif result is None:
            entry = CommanderDecision(Action.WAIT, None, "PHYSICAL_TOOL_RESULT_UNAVAILABLE")
        else:
            # The one Commander receives the complete reviewed adviser set.
            # `result.intents` remains the legacy lane-resolved shadow for
            # diagnostics, but it no longer gets to starve strategy before the
            # Commander can compare physical candidates.
            # One-Commander constitution: specialist WAIT/HOLD/EXIT entry-lane
            # opinions remain in ToolRackShadowResult for telemetry, but entry
            # admission sees only actionable adviser candidates. A tool WAIT
            # can never become a second strategic veto. Position management is
            # handled separately by decide_position().
            adviser_candidates = tuple(intent for intent in (result.commander_intents or result.intents)
                if intent.action in (Action.ENTER, Action.RELAY))
            commander_primary = self.commander.physical_entry_candidates(snapshot)
            commander_candidates = commander_primary + adviser_candidates
            proposed_entries = tuple(self.rack.qualify_independent_role_mission(
                self.rack.qualify_independent_recovery_mission(intent, snapshot, self.executor.positions),
                snapshot, self.executor.positions) for intent in commander_candidates)
            # Commander-owned entries and non-owner tactical observations share
            # the same first-counterfade memory; a second callback of the same
            # swing cannot be treated as a distinct later opportunity.
            proposed_entries = self.rack.filter_independent_lane_candidates(
                proposed_entries, snapshot)
            # Pin current physical entry evidence for later developed-loss
            # review. This is provenance only; it grants no extra entry route.
            proposed_entries = tuple(replace(intent, metadata={**intent.metadata,
                "entry_geometry": plain(metadata.get("current_geometry") or {})})
                if intent.action in (Action.ENTER, Action.RELAY) else intent
                for intent in proposed_entries)
            entry = self.commander.decide_entry(proposed_entries, snapshot, self.executor.positions)
            opportunity_evaluated = True
        entry_row = {"scope": "ENTRY", "decision": plain(entry)}
        self._reason_counts[entry.reason] += 1
        if entry.action in (Action.ENTER, Action.RELAY) and book is not None:
            receipt = self.executor.execute(entry, book, now_ts=dispatch_clock(),
                command_id=f"{self.run_dir.name}:{self._seq}:ENTRY")
            entry_row["receipt"] = plain(receipt)
            receipts.append(receipt)
            if receipt.status == "BOOKED":
                self.rack.commit_accepted_intent(entry.intent, snapshot, position_id=receipt.position_id)
                self.commander.mark_entry_filled(entry.intent, ticker=snapshot.ticker)
            self._print_receipt(receipt)
        opportunity_review = opportunity_audit(self.commander, snapshot, entry,
            receipt if "receipt" in entry_row else None, evaluated=opportunity_evaluated)
        entry_row["opportunity_review"] = opportunity_review
        decisions.append(entry_row)
        state = self.executor.snapshot()
        audit = {"sequence": self._seq, "now_ts": now, "source_generation": feed.generation,
                 "source_status": plain(feed.source_status), "market": plain(market),
                 "native_book": plain(book), "physical": plain(physical.evidence),
                 "physical_metadata": plain(metadata), "rack": plain(result), "decisions": decisions,
                 "ledger_seq": state["journal_seq"], "ledger_sha256": state["journal_sha256"],
                 "previous_sha256": self._previous_hash}
        canonical = json.dumps(audit, sort_keys=True, separators=(",", ":"), allow_nan=False)
        self._previous_hash = hashlib.sha256(canonical.encode()).hexdigest()
        self.audit.write(json.dumps({**audit, "sha256": self._previous_hash}, allow_nan=False) + "\n")
        self.audit.flush()
        status = {"mode": "PAPER", "runtime_revision": RUNTIME_REVISION, "run_id": self.run_dir.name,
                  "started_at": self.started_at, "updated_at": now,
                  "state": "STOPPING" if stop_requested else "DRAINING" if entry_window_closed else "RUNNING",
                  "entry_window_closed": bool(entry_window_closed),
                  "authority": "TOOL_RACK_ONE_COMMANDER", "sequence": self._seq,
                  "source_status": plain(feed.source_status), "market": plain(market), "book": plain(book),
                  "awaiting_physical_reacquisition": self._awaiting_reacquisition,
                  "latest_geometry": plain(physical.latest_row), "physical": plain(metadata),
                  "mission_context": plain(metadata.get("mission_context") or {}),
                  "candidate_review": plain(self.rack.mission_policy.reviews),
                  "opportunity_review": opportunity_review,
                  "rack": plain(result or self._last_rack), "decisions": decisions,
                  "reason_counts": dict(self._reason_counts),
                  "cash": state["cash"], "realized_gross": state["realized_gross"],
                  "realized_net": state["realized_net"], "fees_paid": state["fees_paid"],
                  "positions": plain(self.executor.positions), "events": state["events"][-100:],
                  "ledger_seq": state["journal_seq"], "ledger_sha256": state["journal_sha256"],
                  "r22_process_required": False, "venue_fill_claim": False}
        self.latest_status = status
        atomic_json(self.run_dir / "STATUS.json", status, required=False)
        if state["journal_seq"] != self._last_journal_seq:
            if atomic_json(self.run_dir / "PAPER_LEDGER.json", state, required=False):
                self._last_journal_seq = state["journal_seq"]
        console_key = (market.ticker if market else None, result.active_tool if result else None, entry.reason)
        if console_key != self._last_console_reason:
            tool = result.active_tool if result else "SOURCE_WARMUP"
            print(f"PAPER {snapshot.ticker or 'DISCOVERY'} | {tool} | {entry.reason}", flush=True)
            self._last_console_reason = console_key
        return {"status": status, "receipts": tuple(receipts), "decisions": decisions}

    def close(self, *, reason: str = "OPERATOR_STOP") -> None:
        state = self.executor.snapshot()
        final = {**self.latest_status, "state": "STOPPED", "stop_reason": reason,
                 "updated_at": time.time(), "positions": plain(self.executor.positions),
                 "cash": state["cash"], "realized_net": state["realized_net"],
                 "realized_gross": state["realized_gross"], "fees_paid": state["fees_paid"],
                 "events": state["events"][-100:],
                 "unresolved_inventory_count": len(self.executor.positions),
                 "final_ledger_seq": state["journal_seq"], "final_ledger_sha256": state["journal_sha256"]}
        self.latest_status = final
        try:
            atomic_json(self.run_dir / "STATUS.json", final, required=False)
            atomic_json(self.run_dir / "PAPER_LEDGER.json", state, required=False)
            atomic_json(self.run_dir / "RUN_SUMMARY.json", final, required=False)
        finally:
            self.leg_ledger.finalize(reason=reason)
            try:
                self.audit.close()
            finally:
                try:
                    self.geometry_log.close()
                finally:
                    try:
                        try:
                            self.mission_history_log.close()
                        finally:
                            self.quote_echo_log.close()
                    finally:
                        self.executor.close()
