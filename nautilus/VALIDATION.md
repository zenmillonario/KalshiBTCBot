# Nautilus v1 validation

## Executed

- 34 Python unittest checks: exact source identity, full-ledger accounting, distinct
  same-side trade generations, duplicate/orphan detection, native held-side zero bid,
  stale/wrong-identity marks, partial and rotating files, manifest/pointer changes,
  completed vs sampled candles, refusal of future completed candles, no inferred quotes,
  archive behavior, HTTP GET assets/API, token, same-origin/Host guards, gzip and refusal
  of write/order/arbitrary-file routes.
- JavaScript syntax checks for app.js and chart.js.
- 21 offline Chromium component checks using a real adapter snapshot: persistent zoom
  and pan, next-candle/rollover behavior, review selection, feed pause/resume, safe text,
  desktop/tablet/small-screen width, diagnostics and disconnected state.
- Real archived run `666_lab_20261011_190044_368345_PID31092`: canonical 26 entries,
  25 closed, 18 winners, one unresolved position; gross closed P&L +$45.703 (UI +$45.70).
  359 displayed minutes: 240 actual exported warmup candles and 119 sampled bars.
  Source is Reassembled R5, not the currently running R6 session.
- Local HTTP server was exercised separately over loopback. Browser tests used offline
  fulfilled snapshots because this environment's managed Chromium blocks navigation
  to arbitrary localhost ports; no claim of an end-to-end Windows browser attachment.
- Recent command evidence for this archive used its last approximately 4 MB, with the
  original CSV header. Canonical accounting and quote/market input were not sampled for
  this comparison. No private run archive or snapshot is committed with the software.
- Synthetic append/rollover/failure cases are tests, not additional recorded trades.

## Not yet established

- Successful attachment to the user's current Windows R6 run.
- Full R6 1-minute OHLC coverage or TradingView candle parity.
- Windows CMD/PowerShell launcher execution on the user's host.
- Live trading execution, P&L after fees, or protection execution guarantees.

The original engine/strategy/observer files are not changed. This is an additive,
read-only dashboard release. Keep the old cockpit until on-host acceptance confirms
run identity, chart coverage, live quote/price age, and console updates.
