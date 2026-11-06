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
from strategy_core.position_roles import normal_role_entry_denial, role_pair_proof_valid, POSITION_ROLES
from strategy_core.recovery import CUSTODY_STATES, independent_entry_denial

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
    first_arm_allowed: bool = True
    roi_trail_tiers: tuple[tuple[float, float], ...] = ()
    tighten_armed_to: float | None = None
    first_arm_from_current_bid: bool = False


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
    custody_state: str = "NORMAL"
    custody_metadata: Mapping[str, Any] = field(default_factory=dict)
    position_role: str | None = None
    protected_peak_bid: float | None = None

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
    resumed. Explicit resume is allowed only after a verified flat boundary.
    Settlement-only recovery can reopen verified existing inventory to append
    official results, but cannot buy, sell, alter custody or observe floors.
    A stale writer lock is not automatically deleted. The runtime also owns a
    global engine lock so different run directories cannot launch two engines.
    """

    def __init__(self, run_dir: str | Path, *, starting_cash: float = 1000.0,
                 resume: bool = False, max_receive_age: float = 3.0,
                 max_exchange_age: float = 15.0, future_tolerance: float = 2.0,
                 max_positions_per_ticker: int = 1,
                 settlement_only: bool = False,
                 expected_journal_sha256: str | None = None,
                 expected_journal_seq: int | None = None) -> None:
        if type(settlement_only) is not bool:
            raise ValueError("INVALID_SETTLEMENT_ONLY_MODE")
        if settlement_only and resume:
            raise ValueError("SETTLEMENT_ONLY_AND_RESUME_ARE_EXCLUSIVE")
        if not settlement_only and (expected_journal_sha256 is not None or expected_journal_seq is not None):
            raise ValueError("EXPECTED_JOURNAL_HEAD_REQUIRES_SETTLEMENT_ONLY")
        if expected_journal_sha256 is not None and (
                not isinstance(expected_journal_sha256, str) or len(expected_journal_sha256) != 64
                or any(c not in "0123456789abcdef" for c in expected_journal_sha256)):
            raise ValueError("INVALID_EXPECTED_JOURNAL_SHA256")
        if expected_journal_seq is not None and (
                type(expected_journal_seq) is not int or expected_journal_seq < 1):
            raise ValueError("INVALID_EXPECTED_JOURNAL_SEQUENCE")
        self._settlement_only = settlement_only
        self.run_dir = Path(run_dir)
        self.journal_dir = self.run_dir / "paper_journal"
        if settlement_only:
            if not self.run_dir.is_dir() or not self.journal_dir.is_dir():
                raise PaperExecutionError("SETTLEMENT_RECOVERY_REQUIRES_EXISTING_JOURNAL")
        else:
            self.run_dir.mkdir(parents=True, exist_ok=True)
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
            if settlement_only and not previous["records"]:
                raise PaperExecutionError("SETTLEMENT_RECOVERY_REQUIRES_EXISTING_JOURNAL")
            if (expected_journal_sha256 is not None and previous["sha256"] != expected_journal_sha256
                    or expected_journal_seq is not None and previous["seq"] != expected_journal_seq):
                raise PaperExecutionError("SETTLEMENT_RECOVERY_JOURNAL_HEAD_CHANGED")
            if previous["records"]:
                if not resume and not settlement_only:
                    raise PaperExecutionError("EXISTING_PAPER_LEDGER_EXPLICIT_REVIEW_REQUIRED")
                self._state = previous["state"]
                if self._state["positions"] and not settlement_only:
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
        by_ticker: dict[str, list[dict]] = {}
        for pid, position in state["positions"].items():
            if (pid != position["position_id"] or type(position["qty"]) is not int
                    or position["qty"] < 1 or _d(position["cost"]) != _d(position["entry_price"]) * position["qty"]):
                raise ValueError("PAPER_POSITION_RECONCILIATION_FAILED")
            if position.get("custody_state", "NORMAL") not in CUSTODY_STATES:
                raise ValueError("INVALID_POSITION_CUSTODY_STATE")
            by_ticker.setdefault(position["ticker"], []).append(position)
        for cohort in by_ticker.values():
            if len(cohort) > 2:
                raise ValueError("RECOVERY_COHORT_POSITION_CAPACITY_EXCEEDED")
            if len(cohort) == 2:
                # Restoration can produce two normally managed existing lots.
                # Validate the original independent booking proof, not a rule
                # forcing the recovering lot to remain a permanent loser.
                older, newer = sorted(cohort, key=lambda p: int(p["position_id"]))
                proof = newer["entry_metadata"].get("independent_recovery_mission") or {}
                original = older["entry_metadata"].get("physical_mission_id") or older["entry_metadata"].get("entry_arc_id")
                if (not role_pair_proof_valid(older, newer) and (proof.get("independently_renewed") is not True
                        or proof.get("detached_position_ids") != [older["position_id"]]
                        or not original or not proof.get("mission_id") or proof["mission_id"] == original
                        or newer["entry_metadata"].get("physical_mission_id") != proof["mission_id"])):
                    raise ValueError("MULTIPLE_LOTS_WITHOUT_INDEPENDENT_RECOVERY_MISSION")
        # Net cash + carried basis/entry fees equals start + realized net.
        carried = sum((_d(p["cost"]) + _d(p["entry_fee_remaining"]) for p in state["positions"].values()), ZERO)
        if abs(cash + carried - _d(state["starting_cash"]) - net) > Decimal("0.000000000001"):
            raise ValueError("PAPER_CASH_POSITION_BASIS_MISMATCH")

    def _commit(self, state: dict, kind: str, event: dict | None) -> None:
        self._assert_open()
        if self._settlement_only and kind != "OFFICIAL_SETTLEMENT":
            raise PaperExecutionError("SETTLEMENT_ONLY_RECOVERY_FORBIDS_NONSETTLEMENT_WRITES")
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

    def _assert_nonsettlement_allowed(self) -> None:
        self._assert_open()
        if self._settlement_only:
            raise PaperExecutionError("SETTLEMENT_ONLY_RECOVERY_FORBIDS_NONSETTLEMENT_WRITES")

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
            values["protected_peak_bid"] = (None if values.get("protected_peak_bid") is None
                                            else float(values["protected_peak_bid"]))
            values["side"], values["lane"] = Side(values["side"]), Lane(values["lane"])
            positions[pid] = PaperPosition(**values)
        return positions

    def snapshot(self) -> dict:
        return {**deepcopy(self._state), "journal_seq": self._seq,
                "journal_sha256": self._last_hash, "committed_boundary": True,
                "venue_fill_claim": False, "fee_model": "HF15_NOMINAL_0.07_CEIL_CENT"}

    def remaining_exit_mark(self, book: PaperBook, *, position_id: str,
                            now_ts: float) -> dict[str, Any]:
        """Read-only exact-lot sale mark after prior fills on this quote.

        The raw book remains immutable. This does not consume liquidity, arm
        a floor, accept an exit, or alter the quote-observation cache.
        """
        self._assert_open()
        pid = str(position_id)
        position = self._state["positions"].get(pid)
        mark: dict[str, Any] = {"version": "PAPER_REMAINING_EXIT_MARK_V1",
            "position_id": pid, "ticker": book.ticker, "quote_id": book.quote_id,
            "quote_observed_ts": book.observed_ts, "evaluated_at": now_ts,
            "journal_seq": self._seq, "journal_sha256": self._last_hash,
            "current": False, "full_quantity_visible": False,
            "full_lot_bid": None, "net_after_fees": None, "exit_fee": None,
            "used_bid_levels": {}, "remaining_depth_applied": True,
            "reason": "EXACT_HELD_POSITION_REQUIRED"}
        if position is None or position["ticker"] != book.ticker:
            return mark
        side, quantity = Side(position["side"]), position["qty"]
        mark.update(side=side.value, quantity=quantity, cost=position["cost"],
                    entry_fee_remaining=position["entry_fee_remaining"],
                    observed_peak_bid=position.get("peak_bid"),
                    peak_basis="EXECUTOR_OBSERVED_FULL_LOT_BID")
        denial = self._book_denial(book, now_ts, remember=False)
        if denial is None and (not book.can_sell(side)
                or book.close_ts != position["close_ts"]):
            denial = "OBJECTIVE_EXACT_HELD_CONTRACT_SELL_UNAVAILABLE"
        prior = self._last_floor_quotes.get(pid)
        if denial is None and (book.observed_ts < position["entry_time"] - self.future_tolerance
                or book.exchange_ts is not None
                    and book.exchange_ts < position["entry_time"] - self.future_tolerance
                or prior is not None and (book.observed_ts < prior[1]
                    or book.exchange_ts is not None and prior[2] is not None and book.exchange_ts < prior[2])):
            denial = "OBJECTIVE_QUOTE_PRECEDES_POSITION_OR_REGRESSES"
        usage = self._state["book_usage"].get(book.ticker + ":" + book.quote_id)
        if denial is None and usage and usage["digest"] != self._book_digest(book):
            denial = "OBJECTIVE_CONSUMED_NATIVE_BOOK_CHANGED"
        if denial is not None:
            mark["reason"] = denial
            return mark
        used = self._used_levels(self._state, book, side, False)
        sale = _sweep(book.bids(side), quantity, buy=False, used=used)
        mark.update(current=True, used_bid_levels=deepcopy(used),
            available_quantity=sale["qty"] if sale else 0,
            reason="NO_FULL_LOT_REMAINING_BID")
        if sale and sale["full_quantity_visible"]:
            fee = nominal_taker_fee(quantity, sale["price"])
            net = sale["amount"] - _d(position["cost"]) - _d(position["entry_fee_remaining"]) - fee
            mark.update(full_quantity_visible=True, full_lot_bid=float(sale["price"]),
                net_after_fees=float(net), exit_fee=float(fee), reason="CURRENT_FULL_LOT_REMAINING_BID")
        return mark

    def record_custody(self, decision: "CommanderDecision", *, position_id: str,
                       now_ts: float) -> bool:
        """Persist an explicit Commander transition without moving any money.

        The permitted write set is custody metadata and an explicit pending
        exit latch. Original economics, mission identity and armed protection
        are never amended by recovery.
        """
        self._assert_nonsettlement_allowed()
        from strategy_core.tools.management import ARC_CONTRACT_PROFIT_REASON
        if ((decision.intent is not None and decision.intent.reason == ARC_CONTRACT_PROFIT_REASON)
                or (decision.custody_update or {}).get("reason") == ARC_CONTRACT_PROFIT_REASON):
            # This is a quote-dependent profitable opportunity, not a
            # structural obligation to sell later at any price. The writer
            # validates it atomically with the full remaining-lot sale.
            return False
        update = decision.custody_update
        if update is None:
            return False
        p = self._state["positions"].get(str(position_id))
        if (p is None or str(update.get("position_id")) != str(position_id)
                or update.get("previous_state") != p.get("custody_state", "NORMAL")
                or update.get("state") not in CUSTODY_STATES
                or not 0 <= now_ts - float(_d(update.get("reviewed_at"))) <= self.max_receive_age):
            raise ValueError("EXACT_CURRENT_COMMANDER_CUSTODY_TRANSITION_REQUIRED")
        state_name = update["state"]
        review = update.get("review") or {}
        if state_name == "LAZARUS" and (decision.action is not Action.HOLD
                or review.get("lazarus_qualified") is not True or review.get("hard_exit") is True
                or p.get("floor_bid") is not None or p.get("exit_required")):
            raise ValueError("UNQUALIFIED_OR_PROTECTED_POSITION_CANNOT_DETACH")
        if state_name == "RECOVERED_NORMAL" and (p.get("custody_state") != "LAZARUS"
                or review.get("full_lot_current") is not True
                or not (review.get("physical") or {}).get("held_side_supported")
                or _d(review.get("current_executable_bid")) < _d(p["entry_price"])):
            raise ValueError("QUOTE_GREEN_ALONE_CANNOT_RESTORE_CUSTODY")
        state = deepcopy(self._state)
        position = state["positions"][str(position_id)]
        history = list((position.get("custody_metadata") or {}).get("transition_history") or [])
        history.append({"from": position.get("custody_state", "NORMAL"), "to": state_name,
                        "timestamp": now_ts, "reason": str(update["reason"])})
        position["custody_state"] = state_name
        position["custody_metadata"] = {"reason": str(update["reason"]), "reviewed_at": now_ts,
            "transition_history": history, "qualification": _jsonable(review)}
        if state_name == "EXIT_PENDING" and not position["exit_required"]:
            position["exit_required"], position["exit_reason"] = True, str(update["reason"])
        self._commit(state, "CUSTODY_TRANSITION", _jsonable(update))
        return True

    def _book_digest(self, book: PaperBook) -> str:
        return _sha({"ticker": book.ticker, "quote_id": book.quote_id,
                     "exchange_ts": book.exchange_ts, "yes_bids": book.yes_bids,
                     "no_bids": book.no_bids, "close_ts": book.close_ts, "source": book.source})

    def _book_denial(self, book: PaperBook, now_ts: float, *, allow_closed: bool = False,
                     remember: bool = True) -> str | None:
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
                if not remember:
                    return "SAME_QUOTE_ID_NATIVE_DEPTH_CHANGED"
                self._halted = "SAME_QUOTE_ID_NATIVE_DEPTH_CHANGED"
                raise PaperExecutionError(self._halted)
            if remember:
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
                       policies: Mapping[str, FloorPolicy],
                       position_ids: tuple[str, ...] | None = None) -> tuple[FloorObservation, ...]:
        """Observe explicit floor instructions; never issue or execute an exit."""
        self._assert_nonsettlement_allowed()
        denial = self._book_denial(book, now_ts)
        state, changed, results = deepcopy(self._state), False, []
        for pid, p in state["positions"].items():
            if p["ticker"] != book.ticker or position_ids is not None and pid not in position_ids:
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
                    if full:
                        peak = max(_d(p["peak_bid"]) if p["peak_bid"] is not None else ZERO, bid)
                        if is_new and (p["peak_bid"] is None or peak != _d(p["peak_bid"])):
                            p["peak_bid"], changed = str(peak), True
                        if policy is not None:
                            arm, band, age = _d(policy.arm_roi), _d(policy.trail_fraction), _d(policy.min_age_seconds)
                            immediate = _d(policy.immediate_arm_roi) if policy.immediate_arm_roi is not None else None
                            if (arm < ZERO or not ZERO < band < ONE or age < ZERO
                                    or type(policy.first_arm_allowed) is not bool
                                    or type(policy.first_arm_from_current_bid) is not bool
                                    or immediate is not None and immediate < ZERO):
                                raise ValueError("INVALID_EXPLICIT_FLOOR_POLICY")
                            armed = p["floor_bid"] is not None
                            # MFE remains historical display evidence. A new protection
                            # instruction cannot retroactively protect a deferred peak.
                            protected_peak = (max(_d(p.get("protected_peak_bid") or p["peak_bid"]), bid)
                                              if armed else bid if policy.first_arm_from_current_bid else peak)
                            roi = protected_peak / _d(p["entry_price"]) - ONE
                            current_net = bid * p["qty"] - nominal_taker_fee(p["qty"], bid) - _d(p["cost"]) - _d(p["entry_fee_remaining"])
                            new_arm_profitable = not policy.first_arm_from_current_bid or current_net > ZERO
                            for threshold, earned_band in policy.roi_trail_tiers:
                                threshold, earned_band = _d(threshold), _d(earned_band)
                                if threshold < ZERO or not ZERO < earned_band < ONE:
                                    raise ValueError("INVALID_EXPLICIT_FLOOR_TIER")
                                if roi >= threshold:
                                    band = min(band, earned_band)
                            if policy.tighten_armed_to is not None:
                                terminal_band = _d(policy.tighten_armed_to)
                                if not ZERO < terminal_band < ONE:
                                    raise ValueError("INVALID_EXPLICIT_ARMED_FLOOR_BAND")
                                if armed:
                                    band = min(band, terminal_band)
                            if (armed or new_arm_profitable and (
                                    policy.first_arm_allowed and roi >= arm and _d(now_ts - p["entry_time"]) >= age
                                    or immediate is not None and roi >= immediate)):
                                if p.get("protected_peak_bid") != str(protected_peak):
                                    p["protected_peak_bid"], changed = str(protected_peak), True
                                prior_band = _d(p["trail_fraction"]) if p["trail_fraction"] is not None else band
                                band = min(prior_band, band)
                                floor = max(_d(p["floor_bid"]) if armed else ZERO, protected_peak * (ONE - band))
                                if p["floor_bid"] != str(floor) or p["trail_fraction"] != str(band):
                                    p["floor_bid"], p["trail_fraction"], changed = str(floor), str(band), True
                                if bid <= floor and not p["exit_required"]:
                                    p["exit_required"], p["exit_reason"], changed = True, "ALREADY_ARMED_EXECUTABLE_BID_FLOOR", True
                    reason = (str(p["exit_reason"]) if p["exit_required"] else
                              "FLOOR_OBSERVED" if full else "NO_FULL_LOT_PEAK_FROM_THIN_BOOK")
            results.append(FloorObservation(pid, p["ticker"], side, book.quote_id,
                float(bid) if bid is not None else None,
                float(p["peak_bid"]) if p["peak_bid"] is not None else None,
                float(p["floor_bid"]) if p["floor_bid"] is not None else None,
                p["floor_bid"] is not None,
                bool(p["exit_required"] and p["exit_reason"] == "ALREADY_ARMED_EXECUTABLE_BID_FLOOR"),
                reason or "NO_UPDATE", full))
        if changed:
            self._commit(state, "FLOOR_OBSERVATION", {"quote": _jsonable(book), "observations": _jsonable(results)})
        return tuple(results)

    def _arc_contract_exit_denial(self, position: Mapping[str, Any], intent: ToolIntent,
                                  book: PaperBook, now_ts: float, requested: int,
                                  sweep: Mapping[str, Any], net: Decimal) -> str | None:
        """Recheck a conditional all-lot profit against actual remaining depth.

        A structural exit may commit a partial sale or remain pending. This
        opportunity may do neither: it must still be the exact current quote,
        normal held ARC and a strictly profitable complete sale at commit.
        """
        from strategy_core.tools.management import ARC_CONTRACT_PROFIT_REASON, ARC_CONTRACT_PROFIT_VERSION
        proof = intent.metadata.get("arc_contract_interruption")
        if not isinstance(proof, Mapping):
            return "ARC_CONTRACT_CURRENT_COLLECTION_PROOF_REQUIRED"
        mission = (position.get("entry_metadata") or {}).get("mission") or {}
        try:
            valid = (intent.reason == ARC_CONTRACT_PROFIT_REASON
                and proof.get("version") == ARC_CONTRACT_PROFIT_VERSION
                and proof.get("qualified") is True and proof.get("reason") == ARC_CONTRACT_PROFIT_REASON
                and str(proof.get("position_id")) == str(position["position_id"])
                and proof.get("ticker") == position["ticker"] == book.ticker
                and proof.get("side") == position["side"] == intent.side.value
                and type(proof.get("quantity")) is int and proof["quantity"] == position["qty"]
                and _d(proof.get("cost")) == _d(position["cost"])
                and _d(proof.get("entry_fee_remaining")) == _d(position["entry_fee_remaining"])
                and _d(proof.get("close_ts")) == _d(position["close_ts"]) == _d(book.close_ts)
                and now_ts < book.close_ts
                and mission.get("purpose") == "ARC_RETURN"
                and position.get("custody_state", "NORMAL") in ("NORMAL", "RECOVERED_NORMAL")
                and position.get("floor_bid") is None and not position.get("exit_required")
                and proof.get("quote_id") == book.quote_id
                and _d(proof.get("quote_observed_ts")) == _d(book.observed_ts)
                and _d(proof.get("evaluated_at")) == _d(intent.source_time)
                and 0 <= _d(now_ts) - _d(proof["evaluated_at"]) <= _d(self.max_receive_age)
                and _d(position["entry_time"]) * 1000 < _d(proof.get("active_weakness_source_ms"))
                <= _d(proof.get("source_ms")) <= _d(proof["evaluated_at"]) * 1000
                and int(_d(proof["source_ms"]) / 60000) > int(_d(position["entry_time"]) / 60)
                and _d(proof.get("net_after_fees")) > ZERO
                and _d(proof.get("observed_peak_bid")) == _d(position.get("peak_bid"))
                and _d(proof.get("current_full_lot_bid")) < _d(position["peak_bid"]))
        except (ValueError, TypeError, KeyError, ArithmeticError):
            valid = False
        if not valid:
            return "ARC_CONTRACT_CURRENT_EXACT_LOT_QUOTE_PROOF_REQUIRED"
        if requested != position["qty"] or sweep["qty"] != position["qty"] or not sweep["full_quantity_visible"]:
            return "ARC_CONTRACT_FULL_REMAINING_LOT_REQUIRED"
        if net <= ZERO:
            return "ARC_CONTRACT_STRICT_POSITIVE_NET_REQUIRED_AT_COMMIT"
        if _d(sweep["price"]) >= _d(position["peak_bid"]):
            return "ARC_CONTRACT_OBSERVED_BID_GIVEBACK_REQUIRED_AT_COMMIT"
        return None

    def execute(self, decision: "CommanderDecision", book: PaperBook, *, now_ts: float,
                command_id: str, position_id: str | None = None,
                quantity: int | None = None) -> ExecutionReceipt:
        self._assert_nonsettlement_allowed()
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
        if not -self.future_tolerance <= now_ts - float(_d(intent.source_time)) <= self.max_receive_age:
            return ExecutionReceipt("REJECTED", "COMMAND_PHYSICAL_SOURCE_STALE_OR_FUTURE", command_id, position_id)
        state = deepcopy(self._state)
        if action in (Action.ENTER, Action.RELAY):
            if not book.entry_allowed:
                return ExecutionReceipt("REJECTED", "OBJECTIVE_ENTRY_BOOK_NOT_PERMITTED", command_id)
            if not intent.opportunity_id or intent.size_tier is None or intent.max_price is None:
                return ExecutionReceipt("REJECTED", "ENTRY_ID_BUDGET_AND_PRICE_LIMIT_REQUIRED", command_id)
            if intent.metadata.get("position_role") is not None and intent.metadata["position_role"] not in POSITION_ROLES:
                return ExecutionReceipt("REJECTED", "INVALID_EXPLICIT_POSITION_ROLE", command_id)
            if intent.metadata.get("aligned_entry_evidence") and any(
                    p["ticker"] == book.ticker and (p.get("entry_metadata") or {}).get("physical_mission_id")
                    == intent.metadata.get("physical_mission_id")
                    for p in (*state["positions"].values(), *state["closed_positions"].values())):
                return ExecutionReceipt("REJECTED", "OBSERVED_LEG_SLICE_ALREADY_BOOKED", command_id)
            opportunity = book.ticker + ":" + intent.opportunity_id
            if opportunity in state["consumed_opportunities"]:
                return ExecutionReceipt("REJECTED", "OPPORTUNITY_ALREADY_BOOKED", command_id)
            if "mountain_handoff" in intent.metadata:
                # A receipt carried by a caller cannot manufacture a flat
                # contract. Require the exact outgoing sale in this writer's
                # committed journal before using the remaining native depth.
                from strategy_core.commander import mountain_handoff_denial
                proof = intent.metadata.get("mountain_handoff_execution")
                if not isinstance(proof, Mapping):
                    return ExecutionReceipt("REJECTED", "COMMANDER_COMPLETED_MOUNTAIN_HANDOFF_REQUIRED", command_id)
                outgoing_id = str(proof.get("outgoing_position_id"))
                outgoing = state["closed_positions"].get(outgoing_id)
                committed = state["commands"].get(proof.get("exit_command_id"))
                event = committed.get("event", {}) if committed else {}
                if (outgoing is None or event.get("event") != "EXIT"
                        or str(event.get("position_id")) != outgoing_id
                        or event.get("position_qty_after") != 0
                        or event.get("ticker") != book.ticker
                        or event.get("quote_id") != book.quote_id
                        or proof.get("quote_id") != book.quote_id
                        or proof.get("exit_journal_seq") != committed.get("seq")
                        or proof.get("exit_timestamp") != event.get("timestamp")
                        or any(p["ticker"] == book.ticker for p in state["positions"].values())):
                    return ExecutionReceipt("REJECTED", "EXACT_COMMITTED_FLAT_MOUNTAIN_HANDOFF_REQUIRED", command_id)
                denial = mountain_handoff_denial(intent, outgoing, ticker=book.ticker, now_ts=now_ts)
                if denial:
                    return ExecutionReceipt("REJECTED", denial, command_id)
            held = [p for p in state["positions"].values() if p["ticker"] == book.ticker]
            if held:
                qualified_custody = all(p.get("custody_state") == "LAZARUS" for p in held)
                if qualified_custody:
                    denial = independent_entry_denial(intent, held, now_ts=now_ts)
                elif intent.metadata.get("position_role"):
                    denial = normal_role_entry_denial(intent, held, now_ts=now_ts)
                else:
                    denial = ("SAME_TICKER_SIDE_POSITION_ALREADY_OPEN" if
                              any(p["side"] == intent.side.value for p in held) else
                              "TICKER_POSITION_CAPACITY_EXIT_BEFORE_RELAY")
                if denial:
                    return ExecutionReceipt("REJECTED", denial, command_id)
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
                 "trail_fraction": None, "exit_required": False, "exit_reason": None,
                 "custody_state": "NORMAL", "custody_metadata": {},
                 "position_role": intent.metadata.get("position_role"), "protected_peak_bid": None}
            opening = (_sweep(book.bids(intent.side), sweep["qty"], buy=False,
                              used=self._used_levels(state, book, intent.side, False))
                       if book.can_sell(intent.side) else None)
            if opening and opening["full_quantity_visible"]:
                p["entry_metadata"]["opening_executable_bid"] = float(opening["price"])
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
            from strategy_core.tools.management import ARC_CONTRACT_PROFIT_REASON
            conditional_profit = intent.reason == ARC_CONTRACT_PROFIT_REASON
            if conditional_profit:
                denial = self._arc_contract_exit_denial(p, intent, book, now_ts, requested, sweep, net)
                if denial is not None:
                    return ExecutionReceipt("REJECTED", denial, command_id, pid)
            event = self._event(p, "EXIT" if complete else "PARTIAL_EXIT", command_id,
                                intent.reason, now_ts, sweep, fee, sweep["amount"] - fee, gross, net, book)
            if conditional_profit:
                event["arc_contract_interruption"] = {**_jsonable(intent.metadata["arc_contract_interruption"]),
                    "commit_full_lot_bid": float(sweep["price"]), "commit_net_after_fees": float(net),
                    "commit_exit_fee": float(fee), "commit_quantity": sweep["qty"],
                    "commit_full_remaining_lot_verified": True}
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
                "territory_id": p["territory_id"], "opportunity_id": p["opportunity_id"], "position_role": p.get("position_role"),
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
