"""Nautilus read-only R5/R6 telemetry adapter. No trading imports or writes.

Canonical UTC trade events own accounting. Legacy rows only enrich explanations.
The adapter never reconstructs a missing quote, protection policy or decision.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any

VERSION = "1.0.0"
csv.field_size_limit(8_000_000)
STOPPED = {"STOPPED", "FAILED", "ENDED", "COMPLETED"}


def number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def epoch(value: Any) -> float | None:
    n = number(value)
    if n is not None:
        return n / 1000 if n > 100_000_000_000 else n
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        # A timezone must be explicit. Legacy local timestamps are not guessed.
        return d.timestamp() if d.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def truth(value: Any) -> bool:
    return value is True or str(value).lower() in {"true", "1"}


def json_file(path: Path, limit: int = 4_000_000) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as f:
        raw = f.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"{path.name}: exceeds read limit")
    result = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(result, dict):
        raise ValueError(f"{path.name}: expected an object")
    return result


def key(row: dict) -> str:
    return "|".join(str(row.get(k, "")) for k in ("ticker", "trade_id", "side"))


def basename(path: str) -> str:
    return PureWindowsPath(path).name if "\\" in path else Path(path).name


def resolve_run(lab: Path, build: str, explicit: Path | None, review: bool):
    """Pin one run at launch. No newest-directory guessing or automatic rebinding."""
    pointer = None
    if explicit:
        run = explicit.resolve()
    else:
        pointer = lab / f"LATEST_TACHYS_REASSEMBLED_{build}_RUN.json"
        data = json_file(pointer, 100_000)
        if not data.get("run_directory"):
            raise ValueError(f"No exact {build} pointer: {pointer}")
        run = Path(data["run_directory"]).resolve()
        if run.parent != (lab / "runs").resolve() or not run.name.startswith("666_lab_"):
            raise ValueError("Run pointer is outside this lab's runs directory")
    manifest = json_file(run / "launcher_manifest.json", 1_000_000)
    if manifest.get("mode") != "PAPER_ONLY":
        raise ValueError("Nautilus v1 requires an explicit PAPER_ONLY manifest")
    match = re.fullmatch(r"V9\.5D-666-REASSEMBLED-(R\d+)", str(manifest.get("version", "")))
    if not match:
        raise ValueError("Unsupported run identity; expected a Reassembled PAPER run")
    actual = match.group(1)
    if not review and actual != build:
        raise ValueError(f"Refusing {actual}; this launcher is pinned to {build}")
    if manifest.get("hotfix_id") != f"666-ROOT-AUDIT-REASSEMBLED-{actual}":
        raise ValueError("Manifest hotfix/build identity disagreement")
    if manifest.get("reconciliation_build") != f"ROOT-AUDIT-REASSEMBLED-{actual}":
        raise ValueError("Manifest reconciliation identity disagreement")
    original = str(manifest.get("run_directory", ""))
    if not review and Path(original).resolve() != run:
        raise ValueError("Manifest run path does not match the selected directory")
    return run, manifest, pointer


class Tail:
    """Incremental UTF-8 complete-record reader with bounded catch-up and memory.

    The engine's CSV/JSONL telemetry writes one physical line per event. Header
    schema is checked by consumers. Truncated or rotating files reset explicitly.
    """
    def __init__(self, path: Path, initial_bytes: int = 4_000_000, batch: int = 4_000_000):
        self.path, self.initial_bytes, self.batch = path, initial_bytes, batch
        self.offset = 0
        self.identity = None
        self.header: list[str] = []
        self.partial = b""
        self.generation = 0
        self.trimmed = False
        self.lag_bytes = 0
        self.bad_rows = 0

    def lines(self, is_csv: bool = False):
        if not self.path.is_file():
            return []
        stat = self.path.stat()
        identity = (stat.st_dev, stat.st_ino)
        reset = identity != self.identity or stat.st_size < self.offset
        with self.path.open("rb") as f:
            if reset:
                self.generation += 1
                self.identity, self.partial = identity, b""
                self.offset = 0
                if is_csv:
                    raw_header = f.readline(200_000)
                    if not raw_header.endswith(b"\n"):
                        self.identity = None
                        return []
                    self.header = next(csv.reader([raw_header.decode("utf-8-sig").strip()]))
                    self.offset = f.tell()
                if stat.st_size - self.offset > self.initial_bytes:
                    f.seek(stat.st_size - self.initial_bytes)
                    f.readline()  # discard the initial incomplete record
                    self.offset = f.tell()
                    self.trimmed = True
            f.seek(self.offset)
            raw = f.read(self.batch)
        start_offset = self.offset - len(self.partial)
        self.offset += len(raw)
        self.lag_bytes = max(0, stat.st_size - self.offset)
        data = self.partial + raw
        parts = data.split(b"\n")
        self.partial = parts.pop()
        if len(self.partial) > 8_000_000:
            self.partial = b""  # refuse unbounded/malformed records
            raise ValueError(f"{self.path.name}: record exceeds 8 MB")
        result = []
        for p in parts:
            line_offset = start_offset
            start_offset += len(p) + 1
            result.append((f"{self.generation}:{line_offset}", p.rstrip(b"\r").decode("utf-8-sig", errors="replace")))
        return result

    def rows(self):
        result = []
        for seq, line in self.lines(True):
            if not line:
                continue
            try:
                values = next(csv.reader([line], strict=True))
                if len(values) != len(self.header):
                    self.bad_rows += 1
                    continue
                row = dict(zip(self.header, values))
                row["_seq"] = seq
                result.append(row)
            except csv.Error:
                self.bad_rows += 1
                continue
        return result


def complete_csv(path: Path, max_bytes: int = 16_000_000):
    """Accounting is never a tail. Refuse oversized, malformed or missing ledgers."""
    if not path.is_file():
        raise ValueError(f"Missing canonical accounting ledger: {path.name}")
    with path.open("rb") as f:
        raw = f.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("Complete ledger exceeds 16 MB; totals withheld, not truncated")
    if not raw:
        raise ValueError("Canonical ledger has no header yet")
    if not raw.endswith(b"\n"):
        raw = raw[:raw.rfind(b"\n") + 1]
    rd = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), strict=True)
    required = {"timestamp", "event", "trade_id", "ticker", "side"}
    if not required.issubset(rd.fieldnames or []):
        raise ValueError("Canonical ledger identity columns are missing")
    rows = list(rd)
    if any(None in r or any(r.get(k) is None for k in required) for r in rows):
        raise ValueError("Malformed canonical ledger; totals withheld")
    return rows


def assemble_trades(rows: list[dict], run_id: str | None, session_id: str | None):
    trades, issues = {}, []
    for r in rows:
        if (run_id and r.get("run_id") != run_id) or (session_id and r.get("session_id") != session_id):
            issues.append("Canonical ledger contains a different run/session")
            continue
        event = r.get("event", "").upper()
        if event not in {"ENTRY", "EXIT", "MILESTONE"}:
            continue
        k, ts = key(r), epoch(r.get("timestamp"))
        if ts is None or not r.get("ticker") or not r.get("trade_id") or r.get("side") not in {"YES", "NO"}:
            issues.append("Invalid canonical event identity/time")
            continue
        if event == "ENTRY":
            if k in trades:
                issues.append("Duplicate canonical entry identity")
                continue
            ask, qty, cost = number(r.get("entry_ask")), number(r.get("qty")), number(r.get("cost"))
            if ask is None or not 0 < ask <= 1 or qty is None or qty <= 0 or cost is None or cost <= 0:
                issues.append("Invalid entry basis/quantity/cost")
            trades[k] = dict(key=k, trade_id=r["trade_id"], ticker=r["ticker"], side=r["side"],
                             role=r.get("role") or "Not recorded", entry_ts=ts, entry_ask=ask,
                             qty=qty, cost=cost, exit_ts=None, exit_bid=None, pnl=None, roi=None,
                             entry_reason=r.get("reason") or "Not recorded", exit_reason="Not recorded",
                             mfe=number(r.get("mfe_pct")), mae=number(r.get("mae_pct")), evidence=[])
        elif k not in trades:
            issues.append("Canonical event has no corresponding entry")
        elif event == "EXIT":
            t = trades[k]
            if t["exit_ts"] is not None:
                issues.append("Duplicate canonical exit identity")
                continue
            pnl, bid = number(r.get("pnl")), number(r.get("bid"))
            if pnl is None or bid is None or not 0 <= bid <= 1 or ts < t["entry_ts"]:
                issues.append("Invalid canonical exit price/P&L/time")
            t.update(exit_ts=ts, exit_bid=bid, pnl=pnl,
                     roi=100 * pnl / t["cost"] if pnl is not None and t["cost"] else None,
                     exit_reason=r.get("reason") or "Not recorded",
                     mfe=number(r.get("mfe_pct")), mae=number(r.get("mae_pct")))
        else:
            for out, field in (("mfe", "mfe_pct"), ("mae", "mae_pct")):
                if number(r.get(field)) is not None:
                    trades[k][out] = number(r[field])
    closed = [t for t in trades.values() if t["exit_ts"] is not None]
    total = sum(t["pnl"] for t in closed if t["pnl"] is not None) if not issues else None
    return list(trades.values()), total, sorted(set(issues))


def mark_position(trade: dict, detail: dict, state: dict, now: float, stopped: bool):
    """A native, held-side bid with exact quote identity is required for a mark."""
    out = dict(trade)
    q = state.get("quote") or {}
    updated = number(state.get("updated_wall"))
    age = number(q.get("receive_age_sec"))
    sd = trade["side"].lower()
    native, candidate = number(q.get(sd + "_bid")), number(detail.get("current_bid"))
    allowed = q.get(sd + "_sell_allowed", q.get("valid"))
    valid = (not stopped and updated is not None and 0 <= now - updated <= 5
             and age is not None and 0 <= age + now - updated <= 3
             and truth(allowed) and detail.get("mark_valid") is True
             and q.get("ticker") == trade["ticker"]
             and bool(q.get("quote_id")) and detail.get("quote_id") == q.get("quote_id")
             and candidate is not None and native is not None and 0 <= native <= 1
             and abs(native - candidate) < 1e-9)
    out.update(current_bid=candidate if valid else None,
               open_pnl=number(detail.get("open_pnl")) if valid else None,
               mark_valid=bool(valid), valid_until=updated + 3 - age if valid else None, role=detail.get("role") or trade["role"],
               state="UNRESOLVED AT STOP" if stopped else "OPEN" if valid else "MARK UNAVAILABLE",
               last_verified_mark=detail.get("last_verified_mark"),
               mark_reason=detail.get("mark_reason") or q.get("reason"),
               custody=detail.get("state"), protection=None)
    for field, source in (("mfe", "mfe_pct"), ("mae", "mae_pct")):
        v = number(detail.get(source))
        if v is not None:
            out[field] = v
    return out


ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SECRET = re.compile(r"(?i)((?:api[_ -]?key|authorization|password|secret|access[_ -]?token)\s*[:=]\s*)(?:Bearer\s+)?(\S+)")


def feed_line(seq: str, line: str):
    text = SECRET.sub(r"\1[REDACTED]", ANSI.sub("", line))[:6000]
    upper = text.upper()
    category = "info"
    if any(w in upper for w in ("ERROR", "TRACEBACK", "EMERGENCY", "DISAGREEMENT", "PAUSED", "STALE", "FAILED")):
        category = "warning"
    elif any(w in upper for w in ("PROTECTION", "TRAIL", "STOP_BID", "GIVEBACK", "HARVEST", "TROPHY")):
        category = "protection"
    elif any(w in upper for w in ("ENTRY", "EXIT", "PAPER BUY", "PAPER SELL", "LAZARUS")):
        category = "trade"
    elif any(w in upper for w in ("CAUTION", "CHOP", "WAIT", "HEIST", "ARM", "PLAN")):
        category = "watch"
    return {"id": seq, "text": text, "category": category}


class Adapter:
    def __init__(self, run: Path, manifest: dict, lab: Path | None = None,
                 pointer: Path | None = None, review: bool = False):
        self.run, self.manifest, self.lab, self.pointer = run, manifest, lab, pointer
        self.review = review
        self.candles: dict[int, dict] = {}
        self.emas: dict[int, dict] = {}
        self.targets: dict[str, dict] = {}
        self.quotes = deque(maxlen=40_000)
        self.feed = deque(maxlen=1000)
        self.commands = deque(maxlen=1500)
        self.protection: dict[str, dict] = {}
        self.latest_market: dict = {}
        self.last_snapshot: dict = {}
        self.seed_loaded = False
        self.trade_cache = (None, [])
        self.errors: list[str] = []
        self.feeds = {
            "market": Tail(run / "tachys_price_arc_phase_v9_4j.csv", 24_000_000, 24_000_000),
            "quotes": Tail(run / "tachys_canonical_quotes_hf2.csv", 24_000_000, 24_000_000),
            "command": Tail(run / "tachys_r15_command.csv", 4_000_000),
            "console": Tail(run / "console.log", 200_000, 400_000),
            "snapshots": Tail(run / "hf21_decision_snapshots.jsonl", 8_000_000, 8_000_000),
        }

    def safe_json(self, name: str, limit: int = 4_000_000):
        try:
            return json_file(self.run / name, limit)
        except (OSError, ValueError, TypeError) as exc:
            self.errors.append(str(exc)[:240])
            return {}

    def candle(self, row: dict, source: str, known_at: float | None = None):
        ts = epoch(row.get("minute", row.get("time")))
        values = [number(row.get(k)) for k in ("open", "high", "low", "close")]
        if ts is None or ts % 60 or any(v is None or v <= 0 for v in values):
            return
        o, h, low, c = values
        if low > min(o, c) or h < max(o, c) or low > h:
            return
        if known_at is not None and ts + 60 > known_at:
            return
        self.candles[int(ts)] = dict(time=int(ts), open=o, high=h, low=low, close=c,
                                    quality=source, known_at=known_at)

    def seed(self):
        if self.seed_loaded:
            return
        data = self.safe_json("tachys_r15_history_seed.json")
        rows = sorted(data.get("candles") or [], key=lambda r: number(r.get("minute")) or 0)
        if not rows:
            return
        closes, e9, e30 = [], None, None
        for r in rows:
            self.candle(r, "engine-seed", epoch((data.get("status") or {}).get("observed_at")))
            ts, close = epoch(r.get("minute")), number(r.get("close"))
            if ts is None or close is None:
                continue
            closes.append(close)
            i = len(closes)
            if i == 9:
                e9 = sum(closes[:9]) / 9
            elif i > 9:
                e9 += (close - e9) * .2
            if i == 30:
                e30 = sum(closes[:30]) / 30
            elif i > 30:
                e30 += (close - e30) * 2 / 31
            if e9 is not None and e30 is not None:
                self.emas[int(ts)] = dict(time=int(ts), e9=e9, e30=e30, source="full-seed reconstruction")
        self.seed_loaded = True

    def ingest_market(self, r: dict):
        ts, btc = epoch(r.get("timestamp")), number(r.get("btc_price"))
        if ts is None or btc is None or btc <= 0:
            return
        minute = int(ts // 60 * 60)
        old = self.candles.get(minute)
        # Sampled bars never overwrite a known, complete engine candle.
        if old is None or old["quality"] == "sampled":
            if old is None:
                old = dict(time=minute, open=btc, high=btc, low=btc, close=btc,
                           quality="sampled", first_sample=ts, last_sample=ts)
                self.candles[minute] = old
            old.update(high=max(old["high"], btc), low=min(old["low"], btc))
            if ts >= old.get("last_sample", 0):
                old.update(close=btc, last_sample=ts)
        e9, e30 = number(r.get("ema9")), number(r.get("ema30"))
        if e9 is not None and e30 is not None and min(e9, e30) > 0:
            self.emas[minute] = dict(time=minute, e9=e9, e30=e30, source="engine telemetry", observed_at=ts)
        ticker, target, left = r.get("ticker"), number(r.get("target")), number(r.get("seconds_left"))
        close = round((ts + left) / 60) * 60 if left is not None else None
        if ticker and target is not None and target > 0:
            self.targets[ticker] = dict(ticker=ticker, target=target, close_ts=close,
                                       start_ts=close - 900 if close is not None else ts, observed_at=ts)
        if ts >= self.latest_market.get("time", 0):
            self.latest_market = dict(time=ts, btc=btc, e9=e9, e30=e30, ticker=ticker,
                                      target=target, close_ts=close, phase=r.get("price_arc_phase"),
                                      arc_direction=r.get("arc_direction"), terrain=r.get("battlefield_class"))

    def ingest_quote(self, r: dict):
        ts = epoch(r.get("timestamp"))
        if ts is None or not r.get("ticker"):
            return
        out = dict(time=ts, ticker=r["ticker"], quote_id=r.get("quote_id"), close_ts=number(r.get("close_ts")))
        age = number(r.get("receive_age_sec"))
        for sd in ("yes", "no"):
            bv = truth(r.get(sd + "_sell_allowed", r.get("valid")))
            av = truth(r.get("entry_allowed", r.get("valid")))
            for field, valid in ((sd + "_bid", bv), (sd + "_ask", av)):
                value = number(r.get(field))
                out[field] = value if valid and age is not None and 0 <= age <= 3 and value is not None and 0 <= value <= 1 else None
        self.quotes.append(out)

    def ingest_command(self, r: dict):
        ts = epoch(r.get("timestamp"))
        if ts is None:
            return
        brief = {k: r.get(k) for k in ("event", "trade_id", "ticker", "side", "action", "reason", "custody")}
        brief.update(time=ts, id=r.get("_seq"), key=key(r))
        for field in ("bid", "ask", "roi_pct", "mfe_pct", "peak_bid", "stop_bid", "trail_pct"):
            brief[field] = number(r.get(field))
        self.commands.append(brief)
        if r.get("trade_id") and r.get("event") == "POSITION":
            self.protection[key(r)] = brief

    def ingest_snapshot(self, obj: dict):
        ts = epoch(obj.get("captured_at_epoch", obj.get("captured_at_utc")))
        frame = obj.get("frame") or {}
        if ts is None or not isinstance(frame, dict):
            return
        for row in frame.get("box_candles") or []:
            if isinstance(row, dict):
                self.candle(row, "engine-completed", ts)
        # Optional explicit export; never synthesize a developing high or low.
        current = frame.get("current_candle")
        if isinstance(current, dict):
            self.candle(current, "engine-developing")
        if ts >= self.last_snapshot.get("time", 0):
            self.last_snapshot = dict(time=ts, frame=frame, decision=obj.get("decision"), identity=obj.get("identity"))

    def poll(self, now: float | None = None):
        now = time.time() if now is None else now
        self.errors = []
        self.seed()
        for kind, consume in (("market", self.ingest_market), ("quotes", self.ingest_quote), ("command", self.ingest_command)):
            try:
                for row in self.feeds[kind].rows():
                    consume(row)
            except (OSError, ValueError, csv.Error) as exc:
                self.errors.append(f"{kind}: {exc}")
        for name in ("snapshots", "console"):
            try:
                for seq, line in self.feeds[name].lines():
                    if name == "console":
                        if line.strip():
                            self.feed.append(feed_line(seq, line))
                    elif line:
                        try:
                            self.ingest_snapshot(json.loads(line))
                        except (ValueError, TypeError, KeyError):
                            self.errors.append("Malformed optional decision snapshot skipped")
            except (OSError, ValueError) as exc:
                self.errors.append(f"{name}: {exc}")
        # Bound session memory. Older history stays in the original files.
        if len(self.candles) > 1440:
            cutoff = sorted(self.candles)[-1440]
            self.candles = {k: v for k, v in self.candles.items() if k >= cutoff}
            self.emas = {k: v for k, v in self.emas.items() if k >= cutoff}
        manifest = self.safe_json("launcher_manifest.json", 1_000_000) or self.manifest
        state = self.safe_json("tachys_runtime_hf2.json")
        planner = self.safe_json("tachys_r15_planner_state.json")
        stopped = self.review or manifest.get("status") in STOPPED or state.get("status") in STOPPED
        updated = number(state.get("updated_wall"))
        runtime_fresh = not stopped and updated is not None and 0 <= now - updated <= 5
        source_run = state.get("run_id")
        source_session = state.get("session_id")
        identity_ok = bool(source_run and source_session)
        for field in ("version", "hotfix_id", "reconciliation_build", "source_commit", "pid", "run_directory", "mode"):
            if manifest.get(field) != self.manifest.get(field):
                identity_ok = False
                self.errors.append("Pinned manifest identity changed; current marks withheld")
                break
        if manifest.get("pid") is not None and state.get("pid") != manifest["pid"]:
            identity_ok = False
            self.errors.append("Runtime process identity does not match launcher manifest")
        if not identity_ok:
            runtime_fresh = False
            self.errors.append("Runtime identity unavailable; live marks withheld")
        trades, realized, accounting_issues = [], None, []
        try:
            path = self.run / "tachys_canonical_trade_events_hf2.csv"
            stat = path.stat()
            sig = (stat.st_size, stat.st_mtime_ns)
            if sig != self.trade_cache[0]:
                self.trade_cache = (sig, complete_csv(path))
            trades, realized, accounting_issues = assemble_trades(self.trade_cache[1], source_run, source_session)
            if not identity_ok:
                accounting_issues.append("Runtime identity missing; accounting identity cannot be confirmed")
                realized = None
        except (OSError, ValueError, csv.Error) as exc:
            accounting_issues.append(str(exc))
        # Legacy context is enrichment only and never replaces canonical UTC timing.
        try:
            path = self.run / "tachys_paper_trades_v9_2_6.csv"
            if path.is_file() and path.stat().st_size < 8_000_000:
                legacy = {(key(r), r.get("event")): r for r in complete_csv(path)}
                for t in trades:
                    entry = legacy.get((t["key"], "ENTRY"), {})
                    t.update(strategy=entry.get("strategy") or "Not recorded", intent=entry.get("trade_intent"),
                             target=number(entry.get("target_price")), btc_at_entry=number(entry.get("btc_price")))
                    if t["entry_reason"] == "Not recorded" and entry.get("reason"):
                        t["entry_reason"] = entry["reason"]
        except (OSError, ValueError, csv.Error) as exc:
            self.errors.append("Optional legacy context: " + str(exc))
        for t in trades:
            t["evidence"] = [c for c in self.commands if c["key"] == t["key"]][-35:]
        mapping = {key(p): p for p in state.get("positions", []) if isinstance(p, dict)}
        open_trades = [t for t in trades if t["exit_ts"] is None]
        if runtime_fresh and set(mapping) != {t["key"] for t in open_trades}:
            accounting_issues.append("Ledger/runtime position mismatch; waiting for consistent writes")
        positions = []
        for t in open_trades:
            card = mark_position(t, mapping.get(t["key"], {}), state, now,
                                 stopped or not identity_ok or bool(accounting_issues))
            recorded = self.protection.get(t["key"])
            if recorded:
                card["protection"] = dict(recorded, fresh=runtime_fresh and 0 <= now - recorded["time"] <= 10)
            positions.append(card)
        closed = [t for t in trades if t["exit_ts"] is not None]
        open_pnl = sum(p["open_pnl"] for p in positions) if all(p["mark_valid"] and p["open_pnl"] is not None for p in positions) and not accounting_issues else None
        if accounting_issues:
            realized = None
        q = state.get("quote") or {}
        market = dict(self.latest_market)
        market_age = now - market["time"] if market.get("time") else None
        market["fresh"] = bool(runtime_fresh and market_age is not None and 0 <= market_age <= 5)
        market["age"] = market_age
        # A target from the preceding contract must never be displayed as current.
        same_contract = bool(market.get("ticker") and market.get("ticker") == q.get("ticker"))
        if not same_contract and runtime_fresh:
            market.update(target=None, close_ts=number(q.get("close_ts")), ticker=q.get("ticker"), fresh=False)
        elif same_contract and number(q.get("close_ts")) is not None:
            market["close_ts"] = number(q["close_ts"])
        qout = dict(ticker=q.get("ticker"), source=q.get("source"), reason=q.get("reason"), time=updated,
                    quote_id=q.get("quote_id"), fresh=False)
        age = number(q.get("receive_age_sec"))
        timely = bool(runtime_fresh and age is not None and 0 <= age + now - updated <= 3)
        qout["valid_until"] = updated + 3 - age if timely else None
        for sd in ("yes", "no"):
            for suffix, permission in (("bid", q.get(sd + "_sell_allowed", q.get("valid"))),
                                       ("ask", q.get("entry_allowed", q.get("valid")))):
                value = number(q.get(sd + "_" + suffix))
                valid = timely and truth(permission) and value is not None and 0 <= value <= 1
                qout[sd + "_" + suffix] = value if valid else None
                qout["fresh"] = qout["fresh"] or valid
        pointer_changed = False
        if self.pointer:
            try:
                pointed = json_file(self.pointer, 100_000).get("run_directory")
                pointer_changed = bool(pointed and Path(pointed).resolve() != self.run)
            except (OSError, ValueError):
                self.errors.append("Run pointer temporarily unreadable; attachment remains pinned")
        if pointer_changed:
            self.errors.append("Run pointer changed. Nautilus remains on the original run; restart to attach a new run.")
        navigator = {}
        if self.lab:
            try:
                nav = json_file(self.lab / "LATEST_KINGS_NAVIGATOR_STATUS.json")
                # Build matching alone is not proof of session identity.
                nav_run = nav.get("run_directory") or nav.get("engine_run_directory") or nav.get("source_run_directory")
                nav_identity = nav_run and basename(str(nav_run)) == basename(str(manifest.get("run_directory", "")))
                if nav and nav_identity and nav.get("engine_version") == manifest.get("version"):
                    navigator = {k: nav.get(k) for k in ("timestamp_utc", "updated_utc", "uranus_radar", "naevyr_residence", "return_clock", "dragon_backbone_warning")}
                elif nav:
                    self.errors.append("Navigator session identity not confirmed; its panel is withheld")
            except (OSError, ValueError):
                self.errors.append("Navigator optional snapshot temporarily unavailable")
        candles = sorted(self.candles.values(), key=lambda c: c["time"])
        sample_count = sum(c["quality"] == "sampled" for c in candles)
        return dict(version=VERSION, server_now=now, mode="PAPER_ONLY", readonly=True,
                    run=dict(name=basename(str(manifest.get("run_directory", self.run.name))), path=str(self.run),
                             version=manifest.get("version"), build=manifest.get("reconciliation_build"),
                             source_commit=manifest.get("source_commit"), run_id=source_run, session_id=source_session,
                             pid=manifest.get("pid"), status=manifest.get("status"), stopped=stopped,
                             review=self.review, fresh=runtime_fresh, updated=updated, pointer_changed=pointer_changed),
                    market=market, quote=qout, candles=candles, emas=sorted(self.emas.values(), key=lambda e: e["time"]),
                    targets=list(self.targets.values()), quotes=list(self.quotes), trades=trades, positions=positions,
                    accounting=dict(realized=realized, open_pnl=open_pnl, closed=len(closed),
                                    wins=sum((t["pnl"] or 0) > 0 for t in closed), issues=accounting_issues,
                                    basis="PAPER GROSS — before fees; displayed quotes are not guaranteed fills"),
                    interpretation=dict(time=number(planner.get("source_ts")),
                                        pilot=planner.get("command_pilot") or {},
                                        development=planner.get("development") or {},
                                        plans=[{k: p.get(k) for k in ("plan_id", "side", "state", "reason", "mission", "first_ask", "entry_limit", "source_ts")} for p in (planner.get("plans") or [])[-8:]],
                                        navigator=navigator),
                    feed=list(self.feed), commands=list(self.commands),
                    diagnostics=dict(issues=sorted(set(self.errors + accounting_issues)),
                                     sampled_candles=sample_count, complete_candles=len(candles) - sample_count,
                                     candle_note="Dashed-outline bars are sampled telemetry OHLC, not full exchange candles. Solid bars are exported engine candles.",
                                     ema_note="Live values are engine telemetry; pre-run warmup uses the complete exported SMA-seeded history, never the visible window.",
                                     command_window="Recent bounded command window; missing historical explanations are not invented.",
                                     readers={n: {"file": f.path.name, "tail_limited": f.trimmed, "lag_bytes": f.lag_bytes, "present": f.path.is_file(), "malformed_rows_skipped": f.bad_rows} for n, f in self.feeds.items()}))
