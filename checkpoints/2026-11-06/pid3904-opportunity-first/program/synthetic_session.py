"""Deterministic synthetic inputs for the unchanged PID15740 engine boundary.

This is an offline engineering fixture, not recorded market history or evidence
of strategy profitability.  It yields inputs only: no engine construction,
decision injection, state mutation, network worker, or trading launcher.

The raw-row, book, market, and historical-candle builders are adapted from
``tests/tool_rack/test_direct_paper_runtime.py`` in the supplied frozen archive
``TACHYOS_PID15740_INHERITED_PARENT_DUAL_LANE_6H_PAPER_2026-11-04.zip``.
Their original source-schema labels are retained for interface compatibility;
explicit synthetic provenance distinguishes them from venue observations.
Each feed includes the entire rolling observation window, matching
``DirectPaperFeed._capture``.  Only the original physical-source consumer
deduplicates previously observed rows; other consumers receive their full
recent history.

The schedule exercises a Rail entry, earned floor and whole-position exit,
another entry at rollover, a held position through expiry, settlement, and
draining across two rollovers.  TACTICAL-to-MAIN promotion and parent handoff
are intentionally unexercised; no strategy decision is forced to claim them.

``calls()`` yields ``(method, arguments, clock_base)``.  The external harness
owns constructor/close operations and records the original runtime's clock
reads.  In particular, process arguments omit ``now_ts`` so the unchanged
engine follows its default per-dispatch clock path.
"""
from __future__ import annotations

from collections import deque
from dataclasses import replace
from typing import Any, Iterator

from strategy_core.marketdata.kalshi_public import MarketInfo
from strategy_core.paper_execution import OfficialResult, PaperBook, PriceLevel
from strategy_core.paper_feed import (
    FeedSnapshot, GEOMETRY_HISTORY_LIMIT, _ChartHistory, freeze_data,
)
from strategy_core.types import Side


BASE = 1_800_000_000.0
RUN_ID = "TACHYOS_SYNTHETIC_SESSION"

_OFFSETS = tuple(sorted(set(
    list(range(1200, 2702, 5))
    + [1201, 1202, 1799, 1800, 1801, 1802, 2699, 2700, 2701, 2702]
)))


def fixture_metadata() -> dict[str, Any]:
    """Describe the input scope without implying real-market acceptance."""
    return {
        "kind": "SYNTHETIC_ENGINE_BOUNDARY_SESSION",
        "synthetic": True,
        "not_venue_evidence": True,
        "run_id": RUN_ID,
        "base_ts": BASE,
        "first_process_ts": BASE + _OFFSETS[0],
        "last_process_ts": BASE + _OFFSETS[-1],
        "process_calls": len(_OFFSETS),
        "settle_calls": 2,
        "contract_rollovers": 2,
        "initial_geometry_rows": 1201,
        "geometry_snapshot": "FULL_ROLLING_WINDOW_MATCHING_DIRECT_PAPER_FEED",
        "geometry_history_limit": GEOMETRY_HISTORY_LIMIT,
        "geometry_sample_interval_seconds": 1,
        "routine_process_interval_seconds": 5,
        "clock_policy": "ORIGINAL_DEFAULT_CLOCK_PATH_WITH_EXTERNAL_RECORDED_READS",
        "builder_attribution": "frozen PID15740 tests/tool_rack/test_direct_paper_runtime.py",
        "source_label_policy": "SOURCE_SCHEMA_COMPATIBILITY_ONLY; ALL_INPUTS_SYNTHETIC",
        "intended_lifecycle": [
            "RAIL_ENTRY_A",
            "EARNED_FLOOR_A",
            "WHOLE_POSITION_EXIT_A",
            "STALE_QUOTE_INPUT",
            "ROLLOVER_ENTRY_B",
            "DRAINING_AT_SECOND_ROLLOVER",
            "HELD_EXPIRY_AND_SETTLEMENT_B",
        ],
        "unexercised": [
            "TACTICAL_TO_MAIN_PROMOTION",
            "PARENT_HANDOFF",
            "NATIVE_RECEIVER_OR_TRANSPORT_REPLAY",
            "SOURCE_DISCONNECT_AND_REACQUISITION",
            "HELD_BOOK_REFRESH",
            "RESTART_WITH_OPEN_INVENTORY",
            "INTERRUPTED_PROCESS_RECOVERY",
            "REAL_CAPTURED_MARKET_HISTORY",
        ],
        "stale_quote_limit": "Stale input occurs without a viable fresh entry; no threatened-order rejection is claimed.",
    }


def _raw_rows(stop: int, *, start: int = 0) -> tuple[dict[str, Any], ...]:
    # Adapted from the original direct-runtime fixture.  The price remains
    # inside the observed three-dollar EMA9 contact band on a DOWN parent.
    return tuple({
        "epoch_ms": (BASE + second) * 1000,
        "btc_price": 79998 - second * .10,
        "ema9": 80000 - second * .10,
        "ema30": 80015 - second * .10,
        "connection_epoch": 1,
        "sequence_num": second,
    } for second in range(start, stop + 1))


def _historical_candles(offset: int) -> list[dict[str, Any]]:
    # The original _ChartHistory validates this same causal source schema.
    # These generated minute bars never become forward geometry observations.
    bars = []
    for opened in range(-2700, int(offset // 60) * 60, 60):
        first = 79998 - opened * .10
        last = 79998 - (opened + 60) * .10
        bars.append({
            "time": BASE + opened,
            "open": first,
            "high": first,
            "low": last,
            "close": last,
            "e9": 80000 - (opened + 60) * .10,
            "e30": 80015 - (opened + 60) * .10,
            "known_at": BASE + opened + 60,
            "complete": True,
            "full_minute": True,
            "connection_epoch": 1,
            "source": "COINBASE_VALIDATED_HISTORY",
            "historical_seed_is_not_forward_observation": True,
            "synthetic": True,
            "not_venue_evidence": True,
        })
    chart = _ChartHistory()
    chart.seed(bars, 1)
    return chart.snapshot()["candles"]


def _capture(offset: int, geometry_rows=None) -> FeedSnapshot:
    if offset < 1800:
        ticker, close = "KXBTC15M-FIXTURE-A", 1800
    elif offset < 2700:
        ticker, close = "KXBTC15M-FIXTURE-B", 2700
    else:
        ticker, close = "KXBTC15M-FIXTURE-C", 3600

    no_bid, no_ask = .08, .10
    if offset == 1201:
        no_bid, no_ask = .44, .46
    elif 1202 <= offset < 1800:
        no_bid, no_ask = .38, .40

    timestamp = BASE + offset
    book = PaperBook(
        ticker, f"NATIVE:{offset}", timestamp, timestamp,
        (PriceLevel(round(1 - no_ask, 8), 1000),),
        (PriceLevel(no_bid, 1000),), BASE + close,
        provenance=freeze_data({
            "sequence_checked": True,
            "snapshot_verified": True,
            "monotonic_receive_fresh": True,
            "fixture": True,
            "synthetic": True,
            "not_venue_evidence": True,
        }),
    )
    if offset == 1600:
        book = replace(book, observed_ts=timestamp - 8)
    market = MarketInfo(
        ticker, BASE + close - 900, BASE + close, "active",
        target=79998 - (close - 900) * .10,
        target_source="KALSHI_MARKET_FLOOR_STRIKE",
    )
    return FeedSnapshot(
        offset, timestamp, market, book,
        (freeze_data(_raw_rows(offset, start=max(0, offset - GEOMETRY_HISTORY_LIMIT + 1)))
         if geometry_rows is None else geometry_rows),
        freeze_data({
            "btc_current": True,
            "book_current": True,
            "synthetic": True,
            "not_venue_evidence": True,
        }),
    )


def calls() -> Iterator[tuple[str, dict[str, Any], float]]:
    """Yield all 309 process calls and two interleaved settlement attempts.

    A is already closed when its settlement result arrives.  B remains held
    through its close and settles after the second rollover.  Input timestamps
    are nondecreasing, and no missing seconds are interpolated during replay:
    every synthetic forward observation is generated explicitly here.
    """
    # Match native ownership as well as values: each immutable row is frozen
    # once, retained in the rolling deque and shared by consecutive snapshots.
    # No input values or call chronology differ from the original fixture.
    rolling = deque(maxlen=GEOMETRY_HISTORY_LIMIT)
    last_offset = -1
    for offset in _OFFSETS:
        rolling.extend(freeze_data(row) for row in _raw_rows(offset, start=last_offset + 1))
        last_offset = offset
        frame = _capture(offset, tuple(rolling))
        yield "process", {
            "feed": frame,
            "historical_candles": _historical_candles(offset),
            "entry_window_closed": offset >= 2700,
        }, BASE + offset
        if offset in (1801, 2701):
            suffix, close = ("A", 1800) if offset == 1801 else ("B", 2700)
            result = OfficialResult(
                f"KXBTC15M-FIXTURE-{suffix}",
                f"SYNTHETIC_FINAL_{suffix}",
                Side.NO, BASE + close, BASE + offset,
                "KALSHI_PUBLIC_TLS_GET",
                provenance=freeze_data({
                    "synthetic": True,
                    "not_venue_evidence": True,
                    "fixture": RUN_ID,
                }),
            )
            yield "settle", {"result": result}, BASE + offset
