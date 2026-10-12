# Nautilus R7 — local candle coverage checker 1.0.0-R7

## Purpose

This is a **diagnostic tool**, not a Nautilus UI release. It targets the R7 run's
`HF21_SNAPSHOT_V1` records and the integrated **Nautilus 1.2.0-R7** data format.
It does not install the older standalone 1.1 UI or modify any existing program.
The snapshot writer, engine, strategies, sidecars and data files remain unchanged.

The supplied statistics report 63,814 enqueued/serialized/written records, zero
reported drops/errors, and a drained shutdown. Those are writer counters, not
proof of complete OHLC coverage. This tool checks the missing evidence locally.

## Use

The generated **CHECK_NAUTILUS_R7_CANDLES.cmd** is self-contained: it embeds the
exact Python source, verifies its SHA-256 before executing it, and uses the
existing `C:\KalshiBTCBot\.venv\Scripts\python.exe`. No new Python packages,
Git checkout, network connection, account keys or engine restart are required.
The temporary Python file is about 30 KB and is deleted after normal completion.

Save the CMD file in Downloads, then run:

```bat
call "%USERPROFILE%\Downloads\CHECK_NAUTILUS_R7_CANDLES.cmd"
```

Defaults are intentionally pinned to the already stopped, reviewed R7 run:

```
E:\TACHYS_DATA\runs\666_lab_20261012_033042_556731_PID28648
```

Reports go to **E:\TACHYS_DATA\diagnostics**, in a new uniquely named folder plus a
ZIP with exactly **REPORT.md**, **coverage.json**, and **minutes.csv**. Upload only
that ZIP. The large JSONL stays in place; it is read once, never copied or uploaded.

Direct source use or a different explicitly chosen run:

```bat
"C:\KalshiBTCBot\.venv\Scripts\python.exe" -B -u candle_coverage.py --run "E:\TACHYS_DATA\runs\EXACT_RUN" --out-root "E:\TACHYS_DATA\diagnostics"
```

By default a running session is refused. `--allow-live` explicitly permits a
fixed-starting-size partial scan but never gives a stopped-run coverage verdict.
The tool is bounded to seven days of run minutes and 16 MB per parsed record.
Invalid or oversized records are counted, not hidden. Runtime and manifest must
agree on PID; verified candles also require exact snapshot run AND session IDs.

## Report interpretation

- `COMPLETED_CANDLE_COVERAGE_PRESENT`: each fully contained run minute has a valid,
  session-matched completed OHLC observation in a stable full scan.
- `COMPLETED_CANDLE_GAPS`: some fully contained minutes have no such observation.
- `INCOMPLETE_OR_IDENTITY_INTEGRITY_UNVERIFIED`: a live/changing file, foreign or
  missing snapshot identity, unknown schema, malformed record or another explicit
  integrity limitation prevents an unqualified coverage conclusion.

A minute counts once regardless of how often `frame.box_candles` repeats it.
`frame.current_candle` observations are tracked separately. Completed candles
must finish by snapshot capture time. The report records earliest availability
lag and subsequent OHLC changes. Start/end partial minutes are displayed but not
counted as missing full run minutes. Price-sample bars never fill completed-bar gaps.

The R7 Nautilus adapter initially tails **8,000,000 bytes**, not eight MiB, of the
snapshot stream. The report compares the minutes in that tail with full-file
availability. This is an initial-read model, **not observed browser delivery**.
A later completed bar does not retroactively establish live candle availability.
Neither a successful writer nor complete engine OHLC proves TradingView parity.

No raw decision text, quote payloads, account credentials or snapshot lines are
included in the reports. Error examples contain bounded line numbers/reasons only.

## Validation scope

Run `python -B -m unittest discover -s nautilus/tests -p test_candle_coverage.py -v`.
35 synthetic tests passed at build time, covering complete/missing/foreign candles,
partial minutes, invalid values, repeated histories, revisions, sample distinctions,
reader limits, file changes, source hashing, no source writes, and compact ZIP output.
The checker was also exercised as a command-line program on synthetic fixtures.

**The user's complete R7 JSONL is not in the supplied archive**. The actual
coverage result and on-host Windows CMD execution remain unverified until this
checker runs on E:. No count is invented to fill that gap.

To rebuild the self-contained CMD from the source:
`python -B nautilus/tools/build_coverage_runner.py CHECK_NAUTILUS_R7_CANDLES.cmd`

The countdown-price coupling and independent component-health UI improvements
are not implemented by this diagnostic-only tool. Keep the current R7 UI intact.
