# The Nautilus 1.3.0-R7 — data reliability repair

This is a UI-only repair **derived from the integrated Nautilus 1.2.0-R7**,
not a return to the old standalone R6/1.1 data adapter. `nautilus/adapter.py` is
byte-identical to the inspected R7 release. A separate `reliability.py` layer
adds chart ingestion and independent health without changing canonical accounting.
The Bridge's feed-left / chart-center / positions-right layout is preserved.

## Install and open

Use the supplied self-contained `INSTALL_NAUTILUS_R7_RELIABILITY.cmd`.
Save it, then double-click it. No Git checkout, Python package installation,
engine restart, account key or large data upload is required. Close only the
previous Nautilus terminal with Ctrl+C first to avoid two viewer windows.

The installer verifies the existing integrated R7 UI baseline and creates:

`C:\KalshiBTCBot_666Lab\nautilus_r7_reliability_1_3_0`

It never overwrites `reassembled_root_audit_r7_4h` or its package manifest.
This is deliberate: modifying files inside that frozen release would break its
hash-verified engine launcher and installer. Identical reinstallation is safe;
a different existing reliability folder is refused, not deleted or overwritten.

For subsequent openings:

```bat
call "C:\KalshiBTCBot_666Lab\nautilus_r7_reliability_1_3_0\RUN_NAUTILUS_R7_RELIABILITY.cmd"
```

**The original R7 engine one-click launcher is unchanged and still selects its
bundled 1.2.0-R7 viewer.** This repair does not silently alter startup selection.
Start the repair viewer separately after the normal engine launch, until a later
engine release deliberately integrates this UI. Do not use `git pull`, checkout,
or reset in a running engine working directory merely to launch Nautilus.

The new viewer remains pinned to the exact R7 pointer and run. A stopped run opens
as stopped/recorded data; the installer never starts a new trading run. It uses
localhost 8580 or the next free port through 8589. No LAN/mobile access is opened.

## Completed history by time, not an 8 MB cut

The history worker backfills valid `HF21_SNAPSHOT_V1` completed candles from the
original JSONL until the visible time window is covered, with a 15-minute buffer.
It runs separately from the main price/quote/accounting publisher. Inspecting
older times requests more history; newest records continue to be read in parallel.
The chart's time position and spacing are not changed by data arrival.

Only completed OHLC whose snapshot run_id AND session_id match the runtime are
accepted. Foreign identity, malformed records, impossible OHLC and a completed
candle that was still in the future at capture are rejected and counted.
Known completed bars replace sampled approximations at the same minute. Capture
timestamps and earliest observation **within scanned records** remain attached.
This is not a full-file audit of first availability and not causal tick replay.

A small, bounded **derived UI cache** (maximum 2 MiB per run) is written outside
engine telemetry, normally:

`E:\TACHYS_DATA\nautilus_cache`

The cache is session-bound and checks file identity, size and read-boundary
fingerprints before reuse. It holds OHLC, timestamps and read positions—not raw
trading decisions. A stale/invalid cache is discarded and rebuilt. Cache writes
are atomic; a permission failure is reported rather than stopping the engine.
The source stream is assumed append-only during one run; this is not a forensic
full-file hash verification on every read. Retained chart history is bounded to
1,440 minutes. Old run caches are not automatically deleted.

**First attachment can still need substantial disk reading** because the existing
R7 forensic file is verbose (the user's four-hour file was approximately 8.88 GB).
This repair does not magically compress or remove that source. Backfill progress
and coverage are visible, and repeated browser refreshes share the existing worker
and cache rather than restarting a full-file scan. Actual speed on E: is untested.

## Developing candles: no invented high/low

The audited R7 data has no explicit `frame.current_candle` export. This patch does
not edit the engine or snapshot writer to add one. It supports a timestamped
explicit export when present, but it shows **FORMING SAMPLED ONLY / UNAVAILABLE**
when that is all the source supports. `OBSERVED_TICKS_ONLY` exports remain sampled.

Solid historical candles are completed engine bars. Dashed bars are sampled-price
approximations. An explicit developing export uses a cyan outline. Completed data
can arrive late and improve historical wicks without pretending it was available
earlier. Neither mode claims TradingView or exchange-feed parity.

## Timer and independent health

The countdown uses the verified active runtime contract's close time. An old BTC
chart sample or invalid quote *values* no longer disable an otherwise trusted
contract clock. Exact runtime identity/freshness, contract close validity and local
wall-clock/monotonic continuity remain required. A detected local clock jump pauses
verification for 30 seconds; absolute exchange clock offset is **not measured**.
At close the display waits for a new verified contract; it never fabricates rollover.
Stale quotes remain blank and stale prices remain labeled last recorded.

Six always-visible health indicators separate **engine, BTC price, quotes,
Observer42, Navigator and candle history**. Source failure/read errors are red;
an engine connection is not proof the observers are healthy. Exact sidecar source
paths are checked, not just a matching folder basename. The old Observer42 error
is surfaced, **not repaired or automatically restarted** by this UI patch.

One small per-viewer health receipt is updated at most every 30 seconds, normally
under `E:\TACHYS_DATA\nautilus_health`. It records attachment, server sample/status
counts, HTTP state-request counts and observed data-volume free space. It is not
proof that a browser displayed every frame, a past C: free-space history, or an
Observer internal error audit. It is not a duplicate console/decision stream.
Use `--no-cache` to disable both derived disk cache and receipts.

## Verification and limitations

See `VALIDATION.md` and the included tests. No Windows-host performance result,
actual reading of the user's omitted 8.88 GB JSONL, developing-candle completeness,
real-money execution result or snapshot-writer repair is claimed.
No engine, strategy, Observer, Navigator, run pointer or snapshot-source file is
modified. HTTP remains read-only, same-origin and loopback-only.
