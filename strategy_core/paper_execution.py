"""Passive, durable Tool Rack PAPER execution mechanics.

Only an explicit CommanderDecision can buy or sell. This module never chooses
terrain, direction, a recovery sanctuary, or an alternate strategy. It has no
network clients and cannot submit an exchange order. Prices and fees below are
a declared counterfactual immediate-taker model, never evidence of venue fills.

The integer depth walk follows HF15 r21_native_depth_sweep; conservative VWAP
rounding and the nominal fee model follow one_command_boundary_r2. Floor
observations retain R5's monotone protection invariant, while all initial
arming thresholds and trail widths are explicit instructions from Commander.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field, fields, is_dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, Mapping, TYPE_CHECKING
import uuid

from strategy_core.types import Action, Lane, Side, ToolIntent

if TYPE_CHECKING:
    from strategy_core.commander import CommanderDecision


SCHEMA = "TACHYOS_TOOL_RACK_PAPER_LEDGER_V1"
ZERO = Decimal("0")
ONE = Decimal("1")


class PaperExecutionError(RuntimeError):
    """Integrity/startup failure; caller must stop this PAPER writer."""


def _d(value: Any) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError("FINITE_NUMBER_REQUIRED")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("FINITE_NUMBER_REQUIRED")
    return result


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        # Feed provenance may be immutable MappingProxyType; asdict's deep
        # copy cannot handle it, whereas this explicit traversal can.
        return {f.name: _jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    return value


def _canonical(value: Any) -> bytes:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class PriceLevel:
    price: float
    quantity: float


@dataclass(frozen=True)
class PaperBook:
    ticker: str
    quote_id: str
    observed_ts: float
    exchange_ts: float | None
    yes_bids: tuple[PriceLevel, ...]
    no_bids: tuple[PriceLevel, ...]
    close_ts: float
    current: bool = True
    entry_allowed: bool = True
    yes_sell_allowed: bool = True
    no_sell_allowed: bool = True
    source: str = "WS_SEQUENCE_CHECKED_BOOK"
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def bids(self, side: Side) -> tuple[PriceLevel, ...]:
        return self.yes_bids if side is Side.YES else self.no_bids

    def asks(self, side: Side) -> tuple[PriceLevel, ...]:
        # Kalshi binary asks are exactly the complementary resting bids.
        opposite = self.no_bids if side is Side.YES else self.yes_bids
        return tuple(PriceLevel(float(ONE - _d(p.price)), p.quantity) for p in opposite)

    def can_sell(self, side: Side) -> bool:
        return self.yes_sell_allowed if side is Side.YES else self.no_sell_allowed


@dataclass(frozen=True)
class OfficialResult:
    ticker: str
    result_id: str
    result: Side
    close_ts: float
    observed_ts: float
    source: str
    final: bool = True
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FloorPolicy:
    """Commander-supplied mechanical settings; no tool defaults live here."""
    arm_roi: float
    trail_fraction: float
    min_age_seconds: float = 0.0
    immediate_arm_roi: float | None = None


@dataclass(frozen=True)
class FloorObservation:
    position_id: str
    ticker: str
    side: Side
    quote_id: str
    bid: float | None
    peak_bid: float | None
    floor_bid: float | None
    armed: bool
    breached: bool
    reason: str
    full_quantity_visible: bool


@dataclass(frozen=True)
class PaperPosition:
    position_id: str
    ticker: str
    side: Side
    qty: int
    entry_price: float
    cost: float
    entry_fee_remaining: float
    entry_time: float
    close_ts: float
    tool: str
    territory_id: str
    opportunity_id: str
    lane: Lane
    entry_quote_id: str
    entry_reason: str
    entry_metadata: Mapping[str, Any]
    peak_bid: float | None
    floor_bid: float | None
    trail_fraction: float | None
    exit_required: bool
    exit_reason: str | None

    @property
    def entry_ask(self) -> float:
        return self.entry_price


@dataclass(frozen=True)
class ExecutionReceipt:
    status: str
    reason: str
    command_id: str | None = None
    position_id: str | None = None
    event: Mapping[str, Any] | None = None
    journal_seq: int | None = None


def nominal_taker_fee(quantity: int, price: Decimal | float) -> Decimal:
    """HF15 nominal model only, not an authoritative current venue fee."""
    if type(quantity) is not int or quantity < 1:
        raise ValueError("POSITIVE_INTEGER_QUANTITY_REQUIRED")
    p = _d(price)
    if not ZERO <= p <= ONE:
        raise ValueError("BINARY_PRICE_REQUIRED")
    return (Decimal("0.07") * quantity * p * (ONE - p)).quantize(
        Decimal("0.01"), rounding=ROUND_CEILING)


def _validate_levels(levels: tuple[PriceLevel, ...]) -> None:
    previous = ONE
    for level in levels:
        price, quantity = _d(level.price), _d(level.quantity)
        if not ZERO < price < ONE or quantity <= ZERO or price >= previous:
            raise ValueError("INVALID_OR_NON_DESCENDING_NATIVE_BID_LEVELS")
        previous = price


def _sweep(levels: tuple[PriceLevel, ...], quantity: int, *, buy: bool,
           used: Mapping[str, int] | None = None, limit: Decimal | None = None) -> dict | None:
    """Floor each displayed level separately; never invent fractional fills."""
    remaining, total, taken_levels = quantity, ZERO, []
    previous = ZERO if buy else ONE
    for lv in levels:
        price, depth = _d(lv.price), _d(lv.quantity)
        if not ZERO < price < ONE or depth <= ZERO:
            raise ValueError("INVALID_SWEEP_LEVEL")
        if (buy and price < previous) or (not buy and price > previous):
            raise ValueError("INVALID_SWEEP_LEVEL_ORDER")
        previous = price
        if limit is not None and buy and price > limit:
            break
        amount = max(0, int(depth.to_integral_value(rounding=ROUND_FLOOR))
                     - int((used or {}).get(str(price), 0)))
        amount = min(remaining, amount)
        if amount:
            total += amount * price
            taken_levels.append((str(price), amount))
            remaining -= amount
        if remaining == 0:
            break
    taken = quantity - remaining
    if not taken:
        return None
    raw = total / taken
    price = raw.quantize(Decimal("0.0001"), rounding=ROUND_CEILING if buy else ROUND_FLOOR)
    return {"qty": taken, "remaining_qty": remaining, "price": price,
            "raw_vwap": str(raw), "levels": taken_levels, "amount": price * taken,
            "displayed_amount": str(total), "full_quantity_visible": remaining == 0}


class PaperExecutioner:
    """One passive PAPER writer with atomic, hash-linked complete-state commits.

    New runs start at $1,000. Existing ledgers are never silently replaced or
    resumed. Explicit resume is allowed only after a verified flat boundary;
    an interrupted run with inventory requires an explicit recovery workflow.
    A stale writer lock is not automatically deleted. The runtime also owns a
    global engine lock so different run directories cannot launch two engines.
    """

    def __init__(self, run_dir: str | Path, *, starting_cash: float = 1000.0,
                 resume: bool = False, max_receive_age: float = 3.0,
                 max_exchange_age: float = 15.0, future_tolerance: float = 2.0,
                 max_positions_per_ticker: int = 1) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.journal_dir = self.run_dir / "paper_journal"
        self.journal_dir.mkdir(exist_ok=True)
        self.lock_path = self.run_dir / "paper_writer.lock"
        self._token = uuid.uuid4().hex
        self._closed = False
        self._halted: str | None = None
        self._seq = 0
        self._last_hash = "0" * 64
        self._seen_books: OrderedDict[str, str] = OrderedDict()
        self._last_floor_quotes: dict[str, tuple[str, float, float | None]] = {}
        self.max_receive_age = float(_d(max_receive_age))
        self.max_exchange_age = float(_d(max_exchange_age))
        self.future_tolerance = float(_d(future_tolerance))
        if self.max_receive_age <= 0 or self.max_exchange_age <= 0 or self.future_tolerance < 0:
            raise ValueError("INVALID_FRESHNESS_LIMITS")
        if type(max_positions_per_ticker) is not int or max_positions_per_ticker < 1:
            raise ValueError("INVALID_POSITION_CAPACITY")
        self.max_positions_per_ticker = max_positions_per_ticker
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise PaperExecutionError("PAPER_WRITER_LOCK_EXISTS_REVIEW_BEFORE_RESTART") from exc
        with os.fdopen(fd, "wb") as handle:
            handle.write(_canonical({"pid": os.getpid(), "token": self._token,
                                     "created_ts": time.time(), "mode": "PAPER"}))
            handle.flush()
            os.fsync(handle.fileno())
        try:
            previous = self.inspect_journal(self.run_dir)
            if previous["records"]:
                if not resume:
                    raise PaperExecutionError("EXISTING_PAPER_LEDGER_EXPLICIT_REVIEW_REQUIRED")
                self._state = previous["state"]
                if self._state["positions"]:
                    raise PaperExecutionError("OPEN_INVENTORY_REQUIRES_EXPLICIT_RECOVERY_NOT_BLIND_RESUME")
                self._seq, self._last_hash = previous["seq"], previous["sha256"]
            else:
                cash = _d(starting_cash)
                if cash != Decimal("1000"):
                    raise ValueError("PAPER_V1_FRESH_LEDGER_REQUIRES_1000_USD")
                self._state = {"schema": SCHEMA, "mode": "PAPER", "starting_cash": str(cash),
                               "cash": str(cash), "realized_gross": "0", "realized_net": "0",
                               "fees_paid": "0", "positions": {}, "closed_positions": {},
                               "events": [], "commands": {}, "consumed_opportunities": [],
                               "book_usage": {}, "settled_results": {}, "next_position_id": 1}
                self._commit(self._state, "BASELINE", None)
            self._reconcile(self._state)
        except BaseException:
            self.close()
            raise

    @staticmethod
    def inspect_journal(run_dir: str | Path) -> dict:
        """Read-only verification; usable even when an interrupted lock exists."""
        journal = Path(run_dir) / "paper_journal"
        files = sorted(journal.glob("*.json")) if journal.exists() else []
        previous = "0" * 64
        state = None
        for sequence, path in enumerate(files, 1):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                digest = record.pop("sha256")
                if (path.name != f"{sequence:08d}.json" or record["seq"] != sequence
                        or record["previous_sha256"] != previous or record["schema"] != SCHEMA
                        or record["status"] != "COMMITTED" or _sha(record) != digest):
                    raise ValueError("HASH_SEQUENCE_OR_BOUNDARY_MISMATCH")
                PaperExecutioner._reconcile(record["state"])
            except (ValueError, KeyError, TypeError) as exc:
                raise PaperExecutionError("PAPER_JOURNAL_INTEGRITY_FAILURE:" + path.name) from exc
            previous, state = digest, record["state"]
        return {"records": len(files), "seq": len(files), "sha256": previous, "state": state,
                "committed_boundary": True,
                "uncommitted_temporary_files": [p.name for p in journal.glob("*.tmp")]}

    @staticmethod
    def _reconcile(state: dict) -> None:
        if state.get("schema") != SCHEMA or state.get("mode") != "PAPER":
            raise ValueError("WRONG_LEDGER_SCHEMA_OR_MODE")
        cash = _d(state["starting_cash"]) + sum((_d(e["cash_delta"]) for e in state["events"]), ZERO)
        gross = sum((_d(e["gross_pnl"]) for e in state["events"]), ZERO)
        net = sum((_d(e["net_pnl"]) for e in state["events"]), ZERO)
        fees = sum((_d(e["fees"]) for e in state["events"]), ZERO)
        if (cash < ZERO or cash != _d(state["cash"]) or gross != _d(state["realized_gross"])
                or abs(net - _d(state["realized_net"])) > Decimal("0.000000000001")
                or fees != _d(state["fees_paid"])):
            raise ValueError("PAPER_TREASURY_RECONCILIATION_FAILED")
        keys = set()
        for pid, position in state["positions"].items():
            if (pid != position["position_id"] or type(position["qty"]) is not int
                    or position["qty"] < 1 or _d(position["cost"]) != _d(position["entry_price"]) * position["qty"]):
                raise ValueError("PAPER_POSITION_RECONCILIATION_FAILED")
            key = position["ticker"], position["side"]
            if key in keys:
                raise ValueError("DUPLICATE_SAME_TICKER_SIDE_POSITION")
            keys.add(key)
        # Net cash + carried basis/entry fees equals start + realized net.
        carried = sum((_d(p["cost"]) + _d(p["entry_fee_remaining"]) for p in state["positions"].values()), ZERO)
        if abs(cash + carried - _d(state["starting_cash"]) - net) > Decimal("0.000000000001"):
            raise ValueError("PAPER_CASH_POSITION_BASIS_MISMATCH")

    def _commit(self, state: dict, kind: str, event: dict | None) -> None:
        self._assert_open()
        self._reconcile(state)
        seq = self._seq + 1
        record = {"schema": SCHEMA, "seq": seq, "status": "COMMITTED", "kind": kind,
                  "previous_sha256": self._last_hash, "event": event, "state": state}
        digest = _sha(record)
        record["sha256"] = digest
        destination = self.journal_dir / f"{seq:08d}.json"
        temporary = self.journal_dir / f".{seq:08d}.{self._token}.tmp"
        try:
            if destination.exists():
                raise PaperExecutionError("PAPER_JOURNAL_SEQUENCE_ALREADY_EXISTS")
            with temporary.open("xb") as handle:
                handle.write(_canonical(record))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            if os.name != "nt":
                fd = os.open(self.journal_dir, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        except BaseException as exc:
            self._halted = "PAPER_COMMIT_FAILED_REVIEW_COMMITTED_BOUNDARY"
            raise PaperExecutionError(self._halted) from exc
        self._state, self._seq, self._last_hash = state, seq, digest

    def _assert_open(self) -> None:
        if self._closed or self._halted:
            raise PaperExecutionError(self._halted or "PAPER_WRITER_CLOSED")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            owner = json.loads(self.lock_path.read_text(encoding="utf-8"))
            if owner.get("token") == self._token:
                self.lock_path.unlink()
        except FileNotFoundError:
            pass

    def __enter__(self) -> "PaperExecutioner":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @property
    def cash(self) -> float:
        return float(self._state["cash"])

    @property
    def events(self) -> list[dict]:
        return deepcopy(self._state["events"])

    @property
    def positions(self) -> dict[str, PaperPosition]:
        positions = {}
        for pid, p in self._state["positions"].items():
            values = deepcopy(p)
            for key in ("entry_price", "cost", "entry_fee_remaining", "peak_bid", "floor_bid", "trail_fraction"):
                values[key] = None if values[key] is None else float(values[key])
            values["side"], values["lane"] = Side(values["side"]), Lane(values["lane"])
            positions[pid] = PaperPosition(**values)
        return positions

    def snapshot(self) -> dict:
        return {**deepcopy(self._state), "journal_seq": self._seq,
                "journal_sha256": self._last_hash, "committed_boundary": True,
                "venue_fill_claim": False, "fee_model": "HF15_NOMINAL_0.07_CEIL_CENT"}

    def _book_digest(self, book: PaperBook) -> str:
        return _sha({"ticker": book.ticker, "quote_id": book.quote_id,
                     "exchange_ts": book.exchange_ts, "yes_bids": book.yes_bids,
                     "no_bids": book.no_bids, "close_ts": book.close_ts, "source": book.source})

    def _book_denial(self, book: PaperBook, now_ts: float, *, allow_closed: bool = False) -> str | None:
        try:
            now = float(_d(now_ts))
            received, close = float(_d(book.observed_ts)), float(_d(book.close_ts))
            if any(type(getattr(book, key)) is not bool for key in
                   ("current", "entry_allowed", "yes_sell_allowed", "no_sell_allowed")):
                return "OBJECTIVE_BOOK_FLAGS_REQUIRE_BOOLEAN_PROOF"
            _validate_levels(book.yes_bids)
            _validate_levels(book.no_bids)
            if (book.yes_bids and book.no_bids
                    and _d(book.yes_bids[0].price) + _d(book.no_bids[0].price) > ONE):
                return "OBJECTIVE_CONFLICTING_CROSSED_BINARY_BOOK"
            if not book.ticker or not book.quote_id or not book.source:
                return "OBJECTIVE_BOOK_IDENTITY_MISSING"
            if not book.current or not 0 <= now - received <= self.max_receive_age:
                return "OBJECTIVE_NATIVE_RECEIVE_STALE"
            if book.exchange_ts is None:
                required = ("sequence_checked", "snapshot_verified", "monotonic_receive_fresh")
                if book.source != "WS_SEQUENCE_CHECKED_BOOK" or not all(book.provenance.get(k) is True for k in required):
                    return "OBJECTIVE_UNKNOWN_EXCHANGE_TIME_WITHOUT_NATIVE_SEQUENCE_PROOF"
            elif not -self.future_tolerance <= now - float(_d(book.exchange_ts)) <= self.max_exchange_age:
                return "OBJECTIVE_EXCHANGE_TIME_STALE_OR_FUTURE"
            if now >= close and not allow_closed:
                return "OBJECTIVE_CONTRACT_CLOSED"
            digest = self._book_digest(book)
            key = book.ticker + ":" + book.quote_id
            previous = self._seen_books.get(key)
            if previous is not None and previous != digest:
                self._halted = "SAME_QUOTE_ID_NATIVE_DEPTH_CHANGED"
                raise PaperExecutionError(self._halted)
            self._seen_books[key] = digest
            self._seen_books.move_to_end(key)
            while len(self._seen_books) > 2048:
                self._seen_books.popitem(last=False)
        except (ValueError, TypeError, AttributeError, ArithmeticError):
            return "OBJECTIVE_MALFORMED_NATIVE_BOOK"
        return None

    @staticmethod
    def _resource(side: Side, buy: bool) -> str:
        return (Side.NO if side is Side.YES else Side.YES).value if buy else side.value

    def _used_levels(self, state: dict, book: PaperBook, side: Side, buy: bool) -> dict[str, int]:
        row = state["book_usage"].get(book.ticker + ":" + book.quote_id, {})
        used = row.get("levels", {}).get(self._resource(side, buy), {})
        return {str(ONE - _d(p)) if buy else p: q for p, q in used.items()}

    def _consume_levels(self, state: dict, book: PaperBook, side: Side, buy: bool, sweep: dict, now_ts: float) -> None:
        # Old quotes cannot execute again; retain only fresh liquidity accounting.
        state["book_usage"] = {k: v for k, v in state["book_usage"].items()
                               if now_ts - v["observed_ts"] <= self.max_receive_age + self.future_tolerance}
        key = book.ticker + ":" + book.quote_id
        row = state["book_usage"].setdefault(key, {"observed_ts": book.observed_ts,
                                                 "digest": self._book_digest(book), "levels": {}})
        if row["digest"] != self._book_digest(book):
            raise PaperExecutionError("CONSUMED_NATIVE_BOOK_CHANGED")
        used = row["levels"].setdefault(self._resource(side, buy), {})
        for price, qty in sweep["levels"]:
            key = str(ONE - _d(price)) if buy else price
            used[key] = used.get(key, 0) + qty

    def observe_floors(self, book: PaperBook, *, now_ts: float,
                       policies: Mapping[str, FloorPolicy]) -> tuple[FloorObservation, ...]:
        """Observe explicit floor instructions; never issue or execute an exit."""
        self._assert_open()
        denial = self._book_denial(book, now_ts)
        state, changed, results = deepcopy(self._state), False, []
        for pid, p in state["positions"].items():
            if p["ticker"] != book.ticker:
                continue
            side, bid, full, reason = Side(p["side"]), None, False, denial
            if reason is None and not book.can_sell(side):
                reason = "OBJECTIVE_HELD_SIDE_SELL_UNAVAILABLE"
            if reason is None:
                prior = self._last_floor_quotes.get(pid)
                source = book.exchange_ts
                if (book.observed_ts < p["entry_time"] - self.future_tolerance
                        or (source is not None and source < p["entry_time"] - self.future_tolerance)
                        or (prior is not None and (book.observed_ts < prior[1]
                            or source is not None and prior[2] is not None and source < prior[2]))):
                    reason = "OBJECTIVE_QUOTE_PRECEDES_POSITION_OR_REGRESSES"
                else:
                    sweep = _sweep(book.bids(side), p["qty"], buy=False,
                                   used=self._used_levels(state, book, side, False))
                    if sweep:
                        bid, full = sweep["price"], sweep["full_quantity_visible"]
                    if sweep and p["floor_bid"] is not None and bid <= _d(p["floor_bid"]):
                        if not p["exit_required"]:
                            p["exit_required"], p["exit_reason"] = True, "ALREADY_ARMED_EXECUTABLE_BID_FLOOR"
                            changed = True
                    policy = policies.get(pid)
                    if (policy is None and p["floor_bid"] is not None
                            and p["trail_fraction"] is not None):
                        # Once Commander has armed a trailing instruction, its
                        # existing mechanics continue even when no new tool
                        # policy is available. This cannot create a first arm.
                        policy = FloorPolicy(0.0, float(p["trail_fraction"]))
                    is_new = prior is None or prior[0] != book.quote_id
                    if is_new:
                        self._last_floor_quotes[pid] = (book.quote_id, book.observed_ts, source)
                    if full and is_new:
                        peak = max(_d(p["peak_bid"]) if p["peak_bid"] is not None else ZERO, bid)
                        if p["peak_bid"] is None or peak != _d(p["peak_bid"]):
                            p["peak_bid"], changed = str(peak), True
                        if policy is not None:
                            arm, band, age = _d(policy.arm_roi), _d(policy.trail_fraction), _d(policy.min_age_seconds)
                            immediate = _d(policy.immediate_arm_roi) if policy.immediate_arm_roi is not None else None
                            if (arm < ZERO or not ZERO < band < ONE or age < ZERO
                                    or immediate is not None and immediate < ZERO):
                                raise ValueError("INVALID_EXPLICIT_FLOOR_POLICY")
                            roi = peak / _d(p["entry_price"]) - ONE
                            armed = p["floor_bid"] is not None
                            if (armed or roi >= arm and _d(now_ts - p["entry_time"]) >= age
                                    or immediate is not None and roi >= immediate):
                                prior_band = _d(p["trail_fraction"]) if p["trail_fraction"] is not None else band
                                band = min(prior_band, band)
                                floor = max(_d(p["floor_bid"]) if armed else ZERO, peak * (ONE - band))
                                if p["floor_bid"] != str(floor) or p["trail_fraction"] != str(band):
                                    p["floor_bid"], p["trail_fraction"], changed = str(floor), str(band), True
                                if bid <= floor and not p["exit_required"]:
                                    p["exit_required"], p["exit_reason"], changed = True, "ALREADY_ARMED_EXECUTABLE_BID_FLOOR", True
                    reason = ("ALREADY_ARMED_EXECUTABLE_BID_FLOOR" if p["exit_required"] else
                              "FLOOR_OBSERVED" if full else "NO_FULL_LOT_PEAK_FROM_THIN_BOOK")
            results.append(FloorObservation(pid, p["ticker"], side, book.quote_id,
                float(bid) if bid is not None else None,
                float(p["peak_bid"]) if p["peak_bid"] is not None else None,
                float(p["floor_bid"]) if p["floor_bid"] is not None else None,
                p["floor_bid"] is not None, bool(p["exit_required"]), reason or "NO_UPDATE", full))
        if changed:
            self._commit(state, "FLOOR_OBSERVATION", {"quote": _jsonable(book), "observations": _jsonable(results)})
        return tuple(results)

    def execute(self, decision: "CommanderDecision", book: PaperBook, *, now_ts: float,
                command_id: str, position_id: str | None = None,
                quantity: int | None = None) -> ExecutionReceipt:
        self._assert_open()
        if not command_id or not isinstance(command_id, str):
            raise ValueError("EXPLICIT_COMMAND_ID_REQUIRED")
        action, intent = decision.action, decision.intent
        if not isinstance(action, Action):
            raise ValueError("COMMANDER_ACTION_REQUIRED")
        fingerprint = _sha({"decision": decision, "book": self._book_digest(book),
                            "position_id": position_id, "quantity": quantity})
        previous = self._state["commands"].get(command_id)
        if previous:
            if previous["fingerprint"] != fingerprint:
                raise PaperExecutionError("COMMAND_ID_REUSED_WITH_DIFFERENT_INPUT")
            return ExecutionReceipt("DUPLICATE", "COMMAND_ALREADY_COMMITTED", command_id,
                                    previous["position_id"], deepcopy(previous["event"]), previous["seq"])
        denial = self._book_denial(book, now_ts)
        if denial:
            return ExecutionReceipt("REJECTED", denial, command_id, position_id)
        # Recheck already armed floors even if caller omitted observe_floors.
        self.observe_floors(book, now_ts=now_ts, policies={})
        outstanding = [p for p in self._state["positions"].values()
                       if p["ticker"] == book.ticker and p["exit_required"]]
        if outstanding and (action is not Action.EXIT or position_id not in {p["position_id"] for p in outstanding}):
            return ExecutionReceipt("REJECTED", "MANDATORY_EXIT_REQUIRES_COMMANDER_EXIT", command_id, position_id)
        if action in (Action.WAIT, Action.HOLD):
            return ExecutionReceipt("NO_ACTION", decision.reason, command_id, position_id)
        if (not isinstance(intent, ToolIntent) or intent.action is not action
                or not isinstance(intent.side, Side) or not isinstance(intent.lane, Lane)):
            return ExecutionReceipt("REJECTED", "EXPLICIT_IDENTICAL_TOOL_INTENT_REQUIRED", command_id, position_id)
        if intent.metadata.get("ticker", book.ticker) != book.ticker:
            return ExecutionReceipt("REJECTED", "COMMAND_TICKER_MISMATCH", command_id, position_id)
        if not 0 <= now_ts - float(_d(intent.source_time)) <= self.max_receive_age:
            return ExecutionReceipt("REJECTED", "COMMAND_PHYSICAL_SOURCE_STALE_OR_FUTURE", command_id, position_id)
        state = deepcopy(self._state)
        if action in (Action.ENTER, Action.RELAY):
            if not book.entry_allowed:
                return ExecutionReceipt("REJECTED", "OBJECTIVE_ENTRY_BOOK_NOT_PERMITTED", command_id)
            if not intent.opportunity_id or intent.size_tier is None or intent.max_price is None:
                return ExecutionReceipt("REJECTED", "ENTRY_ID_BUDGET_AND_PRICE_LIMIT_REQUIRED", command_id)
            opportunity = book.ticker + ":" + intent.opportunity_id
            if opportunity in state["consumed_opportunities"]:
                return ExecutionReceipt("REJECTED", "OPPORTUNITY_ALREADY_BOOKED", command_id)
            held = [p for p in state["positions"].values() if p["ticker"] == book.ticker]
            if any(p["side"] == intent.side.value for p in held):
                return ExecutionReceipt("REJECTED", "SAME_TICKER_SIDE_POSITION_ALREADY_OPEN", command_id)
            if len(held) >= self.max_positions_per_ticker:
                return ExecutionReceipt("REJECTED", "TICKER_POSITION_CAPACITY_EXIT_BEFORE_RELAY", command_id)
            budget, limit = min(_d(intent.size_tier), _d(state["cash"])), _d(intent.max_price)
            if budget <= ZERO or not ZERO < limit < ONE:
                return ExecutionReceipt("REJECTED", "INVALID_OR_UNFUNDED_ENTRY_BUDGET", command_id)
            asks, used = book.asks(intent.side), self._used_levels(state, book, intent.side, True)
            available = sum(max(0, int(_d(l.quantity).to_integral_value(rounding=ROUND_FLOOR))
                                - used.get(str(_d(l.price)), 0)) for l in asks if _d(l.price) <= limit)
            low, high, sweep = 1, min(available, 100000), None
            while low <= high:
                qty = (low + high) // 2
                trial = _sweep(asks, qty, buy=True, used=used, limit=limit)
                if trial and trial["qty"] == qty and trial["amount"] + nominal_taker_fee(qty, trial["price"]) <= budget:
                    sweep, low = trial, qty + 1
                else:
                    high = qty - 1
            if sweep is None:
                return ExecutionReceipt("REJECTED", "NO_AFFORDABLE_INTEGER_LOT_WITHIN_TOOL_LIMIT", command_id)
            pid = str(state["next_position_id"])
            state["next_position_id"] += 1
            fee = nominal_taker_fee(sweep["qty"], sweep["price"])
            p = {"position_id": pid, "ticker": book.ticker, "side": intent.side.value,
                 "qty": sweep["qty"], "entry_price": str(sweep["price"]), "cost": str(sweep["amount"]),
                 "entry_fee_remaining": str(fee), "entry_time": now_ts, "close_ts": book.close_ts,
                 "tool": intent.tool, "territory_id": intent.territory_id, "opportunity_id": intent.opportunity_id,
                 "lane": intent.lane.value, "entry_quote_id": book.quote_id, "entry_reason": intent.reason,
                 "entry_metadata": _jsonable(intent.metadata), "peak_bid": None, "floor_bid": None,
                 "trail_fraction": None, "exit_required": False, "exit_reason": None}
            state["positions"][pid] = p
            state["consumed_opportunities"].append(opportunity)
            event = self._event(p, "ENTRY", command_id, intent.reason, now_ts, sweep, fee,
                                -(sweep["amount"] + fee), ZERO, ZERO, book)
            status = "BOOKED"
            self._consume_levels(state, book, intent.side, True, sweep, now_ts)
        elif action is Action.EXIT:
            pid = str(position_id) if position_id is not None else ""
            p = state["positions"].get(pid)
            if p is None or p["ticker"] != book.ticker or p["side"] != intent.side.value:
                return ExecutionReceipt("REJECTED", "EXACT_HELD_POSITION_TICKER_SIDE_REQUIRED", command_id, position_id)
            if not book.can_sell(intent.side):
                return ExecutionReceipt("REJECTED", "OBJECTIVE_HELD_SIDE_SELL_UNAVAILABLE", command_id, pid)
            requested = p["qty"] if quantity is None else quantity
            if type(requested) is not int or not 1 <= requested <= p["qty"]:
                return ExecutionReceipt("REJECTED", "INVALID_EXPLICIT_EXIT_QUANTITY", command_id, pid)
            sweep = _sweep(book.bids(intent.side), requested, buy=False,
                           used=self._used_levels(state, book, intent.side, False))
            if sweep is None:
                return ExecutionReceipt("REJECTED", "NO_INTEGER_EXECUTABLE_HELD_BID", command_id, pid)
            fee = nominal_taker_fee(sweep["qty"], sweep["price"])
            basis = _d(p["entry_price"]) * sweep["qty"]
            allocated = (_d(p["entry_fee_remaining"]) if sweep["qty"] == p["qty"] else
                         _d(p["entry_fee_remaining"]) * sweep["qty"] / p["qty"])
            gross, net = sweep["amount"] - basis, sweep["amount"] - basis - allocated - fee
            complete = sweep["qty"] == p["qty"]
            event = self._event(p, "EXIT" if complete else "PARTIAL_EXIT", command_id,
                                intent.reason, now_ts, sweep, fee, sweep["amount"] - fee, gross, net, book)
            self._consume_levels(state, book, intent.side, False, sweep, now_ts)
            if complete:
                state["closed_positions"][pid] = deepcopy(p)
                del state["positions"][pid]
            else:
                p["qty"] -= sweep["qty"]
                p["cost"] = str(_d(p["entry_price"]) * p["qty"])
                p["entry_fee_remaining"] = str(_d(p["entry_fee_remaining"]) - allocated)
                p["exit_required"], p["exit_reason"] = True, "CONTINUE_EXPLICIT_COMMANDER_EXIT"
            status = "EXITED" if complete else "PARTIAL_EXIT"
        else:
            return ExecutionReceipt("REJECTED", "UNSUPPORTED_COMMANDER_ACTION", command_id, position_id)
        self._account_event(state, event)
        state["commands"][command_id] = {"fingerprint": fingerprint, "position_id": pid,
                                        "event": event, "seq": self._seq + 1}
        self._commit(state, event["event"], event)
        return ExecutionReceipt(status, "SIMULATED_PAPER_COMMITTED", command_id, pid, deepcopy(event), self._seq)

    @staticmethod
    def _event(p: dict, kind: str, command_id: str, reason: str, now_ts: float,
               sweep: dict, fee: Decimal, cash_delta: Decimal, gross: Decimal,
               net: Decimal, book: PaperBook | None) -> dict:
        return {"schema": SCHEMA, "mode": "PAPER", "event": kind, "timestamp": now_ts,
                "trade_id": p["position_id"], "position_id": p["position_id"],
                "ticker": p["ticker"], "side": p["side"], "tool": p["tool"],
                "territory_id": p["territory_id"], "opportunity_id": p["opportunity_id"],
                "command_id": command_id, "reason": reason, "qty": sweep["qty"],
                "price": str(sweep["price"]), "entry_ask": p["entry_price"],
                "position_qty_after": (sweep["qty"] if kind == "ENTRY" else p["qty"] - sweep["qty"]),
                "bid": None if kind == "ENTRY" else str(sweep["price"]),
                "cost": str(_d(p["entry_price"]) * sweep["qty"]), "fees": str(fee),
                "gross_pnl": str(gross), "net_pnl": str(net), "cash_delta": str(cash_delta),
                "quote_id": book.quote_id if book else None, "quote_provenance": _jsonable(book) if book else None,
                "depth_sweep": _jsonable(sweep), "venue_fill_claim": False,
                "price_basis": "CONSERVATIVE_INTEGER_NATIVE_DEPTH_PAPER_MODEL" if book else "OFFICIAL_RESULT_SIMULATED"}

    @staticmethod
    def _account_event(state: dict, event: dict) -> None:
        state["events"].append(event)
        for key, field_name in (("cash", "cash_delta"), ("realized_gross", "gross_pnl"),
                                ("realized_net", "net_pnl"), ("fees_paid", "fees")):
            state[key] = str(_d(state[key]) + _d(event[field_name]))
        event["realized_gross"] = state["realized_gross"]
        event["realized_net"] = state["realized_net"]
        event["cash_after"] = state["cash"]

    def settle(self, result: OfficialResult) -> tuple[ExecutionReceipt, ...]:
        """Apply an exact official final result, never BTC/clock inference."""
        self._assert_open()
        if (not isinstance(result, OfficialResult) or result.final is not True or not result.result_id
                or not isinstance(result.result, Side) or not result.ticker
                or result.source not in ("KALSHI_PUBLIC_TLS_GET", "KALSHI_AUTHENTICATED_GET")
                or _d(result.observed_ts) < _d(result.close_ts)):
            raise ValueError("VERIFIED_FINAL_OFFICIAL_RESULT_REQUIRED")
        existing = self._state["settled_results"].get(result.ticker)
        identity = _sha({"ticker": result.ticker, "result": result.result, "close_ts": result.close_ts})
        if existing:
            if existing["identity"] != identity:
                raise PaperExecutionError("CONFLICTING_OFFICIAL_RESULT")
            return (ExecutionReceipt("DUPLICATE", "OFFICIAL_RESULT_ALREADY_COMMITTED"),)
        held = [p for p in self._state["positions"].values() if p["ticker"] == result.ticker]
        if not held:
            return ()
        if any(abs(p["close_ts"] - result.close_ts) > 0.001 for p in held):
            raise ValueError("OFFICIAL_RESULT_CLOSE_DOES_NOT_MATCH_PINNED_POSITION")
        state, events = deepcopy(self._state), []
        for old in held:
            p = state["positions"][old["position_id"]]
            price = ONE if p["side"] == result.result.value else ZERO
            amount = price * p["qty"]
            gross = amount - _d(p["cost"])
            net = gross - _d(p["entry_fee_remaining"])
            sweep = {"qty": p["qty"], "price": price, "amount": amount,
                     "remaining_qty": 0, "levels": [], "full_quantity_visible": False}
            event = self._event(p, "SETTLEMENT", "RESULT:" + result.result_id + ":" + p["position_id"],
                                "OFFICIAL_FINAL_RESULT_PAPER_SETTLEMENT", result.observed_ts,
                                sweep, ZERO, amount, gross, net, None)
            event["official_result"] = _jsonable(result)
            self._account_event(state, event)
            state["closed_positions"][p["position_id"]] = deepcopy(p)
            del state["positions"][p["position_id"]]
            events.append(event)
        state["settled_results"][result.ticker] = {"identity": identity, "result": _jsonable(result)}
        self._commit(state, "OFFICIAL_SETTLEMENT", {"events": events, "official_result": _jsonable(result)})
        return tuple(ExecutionReceipt("SETTLED", "OFFICIAL_RESULT_SIMULATED", e["command_id"],
                                       e["position_id"], deepcopy(e), self._seq) for e in events)
