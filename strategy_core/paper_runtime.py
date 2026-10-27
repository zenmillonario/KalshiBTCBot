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
from strategy_core.paper_execution import FloorPolicy, PaperBook, PaperExecutioner
from strategy_core.physical_source import DirectPhysicalSource
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, MarketSnapshot, Side


RUNTIME_REVISION = "TOOL_RACK_PAPER_V1"
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
                  "quote_exchange_ts": book.exchange_ts},
        yes_bid=best(book.yes_bids), no_bid=best(book.no_bids),
        entry_allowed=book.entry_allowed, yes_sell_allowed=book.yes_sell_allowed,
        no_sell_allowed=book.no_sell_allowed)


class ToolRackPaperEngine:
    """Synchronous decision core; network and UI remain outside the boundary."""
    def __init__(self, run_dir: Path, *, source_root: Path | None = None) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.physical = DirectPhysicalSource()
        self.rack = ToolRackController(configs=self.physical.configs)
        self.commander = OneCommander()
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
        self.latest_status: dict[str, Any] = {}
        self.started_at = time.time()
        root = source_root or Path(__file__).resolve().parent.parent
        with ExitStack() as startup:
            self.executor = startup.enter_context(PaperExecutioner(self.run_dir))
            self.audit = startup.enter_context((self.run_dir / "decisions.jsonl").open(
                "a", encoding="utf-8", newline="\n"))
            self.geometry_log = startup.enter_context((self.run_dir / "physical_geometry.jsonl").open(
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

    @staticmethod
    def _floor_policy(intents: Any, position: Any) -> FloorPolicy | None:
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
        return FloorPolicy(**arguments)

    def _closed(self, position: Any, *, release_handoff: bool = False) -> None:
        self.rack.mark_position_closed(ticker=position.ticker, territory_id=position.territory_id,
                                      opportunity_id=position.opportunity_id, release_handoff=release_handoff)
        self._pending_tool_exits.pop(position.position_id, None)

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
                stop_requested: bool = False) -> dict[str, Any]:
        now = time.time() if now_ts is None else float(now_ts)
        dispatch_clock = (lambda: time.time()) if now_ts is None else (lambda: now)
        self._seq += 1
        if not feed.geometry_rows and feed.source_status.get("btc_current") is False:
            self.physical.invalidate(str(feed.source_status.get("source_error") or "BTC_SOURCE_NOT_CURRENT"))
        physical = self.physical.observe(feed.geometry_rows, now_ts=now)
        physical_current = physical.current and feed.source_status.get("btc_current", True) is True
        metadata = {**physical.metadata, "physical_current": physical_current,
                    "source_generation": feed.generation}
        continuity = int(metadata.get("geometry_continuity_generation", 0))
        if continuity != self._source_continuity_generation:
            self._awaiting_reacquisition = self._last_rack is not None
            self._source_continuity_generation = continuity
        for row in physical.new_rows:
            self.geometry_log.write(json.dumps(plain(row), allow_nan=False) + "\n")
        self.geometry_log.flush()
        market = feed.market
        book = feed.book
        if market is not None and book is not None and book.ticker != market.ticker:
            raise RuntimeError("COHERENT_CAPTURE_MARKET_BOOK_MISMATCH")
        snapshot = snapshot_from_book(book, now_ts=now, metadata=metadata,
            ticker=market.ticker if market else "", close_ts=market.close_ts if market else None)
        result = None
        if physical_current and market is not None:
            result = self.rack.observe(physical.evidence, snapshot)
            self._last_rack = result
            fresh_handoff = (result.handoff_confirmed and
                             result.release_boundary_name != "RELEASE_TRANSITION_LATCHED")
            if (fresh_handoff or result.active_tool is not None and
                    result.raw_decision.territory is result.owned_territory and
                    result.raw_decision.side is result.owned_side):
                self._awaiting_reacquisition = False
        decisions: list[dict[str, Any]] = []
        receipts: list[Any] = []
        books = dict(held_books or {})
        if book is not None:
            books[book.ticker] = book
        closed_this_beat = False
        for position_id, old_position in list(self.executor.positions.items()):
            held_book = books.get(old_position.ticker)
            held_snapshot = snapshot_from_book(held_book, now_ts=now, metadata=metadata,
                ticker=old_position.ticker, close_ts=old_position.close_ts)
            expired = dispatch_clock() >= old_position.close_ts
            proposed = self.rack.manage_position(plain(old_position), held_snapshot) if physical_current and not expired else ()
            # An accepted physical invalidation remains pending through missing
            # liquidity. A later HOLD cannot silently erase the requested exit.
            structural_exit = next((intent for intent in proposed if intent.action is Action.EXIT), None)
            if structural_exit is not None:
                self._pending_tool_exits[position_id] = structural_exit
            pending = self._pending_tool_exits.get(position_id)
            if pending is not None:
                proposed = (replace(pending, source_time=now),)
                held_snapshot = replace(held_snapshot, metadata={**held_snapshot.metadata,
                    "pending_exit_was_previously_observed": True})
            policy = self._floor_policy(proposed, old_position)
            floors = self.executor.observe_floors(held_book, now_ts=dispatch_clock(),
                policies={position_id: policy} if policy is not None else {}) if held_book is not None and not expired else ()
            position = self.executor.positions[position_id]
            breached = any(floor.position_id == position_id and floor.breached for floor in floors)
            decision = self.commander.decide_position(proposed, held_snapshot, plain(position),
                floor_breached=breached, stop_requested=stop_requested)
            row = {"position_id": position_id, "scope": "POSITION", "decision": plain(decision),
                   "tool_intents": plain(proposed), "floors": plain(floors)}
            self._reason_counts[decision.reason] += 1
            if decision.action is Action.EXIT and held_book is not None:
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
                self._print_receipt(receipt)
            decisions.append(row)
        if stop_requested:
            entry = CommanderDecision(Action.WAIT, None, "PAPER_STOP_NO_NEW_ENTRY")
        elif not physical_current:
            entry = CommanderDecision(Action.WAIT, None, "DIRECT_PHYSICAL_SOURCE_WARMING_OR_STALE")
        elif book is None or market is None:
            entry = CommanderDecision(Action.WAIT, None, "NATIVE_CURRENT_MARKET_BOOK_UNAVAILABLE")
        elif self._awaiting_reacquisition:
            entry = CommanderDecision(Action.WAIT, None, "PHYSICAL_CONTINUITY_RESET_AWAIT_TOOL_REACQUISITION")
        elif closed_this_beat or self._last_entry_block_quote.get(book.ticker) == book.quote_id:
            entry = CommanderDecision(Action.WAIT, None, "EXIT_COMMITTED_WAIT_FOR_NEXT_NATIVE_QUOTE")
        elif result is None:
            entry = CommanderDecision(Action.WAIT, None, "PHYSICAL_TOOL_RESULT_UNAVAILABLE")
        else:
            entry = self.commander.decide_entry(result.intents, snapshot, self.executor.positions)
        entry_row = {"scope": "ENTRY", "decision": plain(entry)}
        self._reason_counts[entry.reason] += 1
        if entry.action in (Action.ENTER, Action.RELAY) and book is not None:
            receipt = self.executor.execute(entry, book, now_ts=dispatch_clock(),
                command_id=f"{self.run_dir.name}:{self._seq}:ENTRY")
            entry_row["receipt"] = plain(receipt)
            receipts.append(receipt)
            if receipt.status == "BOOKED":
                self.rack.commit_accepted_intent(entry.intent, snapshot)
            self._print_receipt(receipt)
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
                  "started_at": self.started_at, "updated_at": now, "state": "STOPPING" if stop_requested else "RUNNING",
                  "authority": "TOOL_RACK_ONE_COMMANDER", "sequence": self._seq,
                  "source_status": plain(feed.source_status), "market": plain(market), "book": plain(book),
                  "awaiting_physical_reacquisition": self._awaiting_reacquisition,
                  "latest_geometry": plain(physical.latest_row), "physical": plain(metadata),
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
        try:
            atomic_json(self.run_dir / "STATUS.json", final, required=False)
            atomic_json(self.run_dir / "PAPER_LEDGER.json", state, required=False)
            atomic_json(self.run_dir / "RUN_SUMMARY.json", final, required=False)
        finally:
            try:
                self.audit.close()
            finally:
                try:
                    self.geometry_log.close()
                finally:
                    self.executor.close()
