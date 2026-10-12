# Nautilus 1.1 Bridge validation — 2026-10-12

## Executed for this release

- 37 Python unit/integration tests passed, including GET checks for the new local
  bridge assets, UI/adapter version separation, full-ledger accounting, identity,
  stale quotes, no-write HTTP routes and source-file immutability.
- 65 offline Chromium display/interaction checks passed. These use the real archived
  R5 adapter snapshot, with clearly test-only appended lines/rollover events. Checks
  cover the 1664 × 806 screenshot viewport; 1280 × 720, 1366 × 768, 1920 × 1080 and
  3840 × 2160 layouts; tablet landscape/portrait; phone layouts; independent fullscreen
  modes and unsupported fallback; persistent chart zoom/pan; touch pinch/cancel;
  table scroll retention; feed pause; tab access and coarse-pointer tap target height.
- Phone branding/hero fit was inspected visually. Very short views use the documented
  scroll fallback instead of clipping content. User-controlled text scaling preserves
  the chart time window. Preferences were serialized/restored using a storage shim
  in the offline test page, not a claim of a physical-device browser test.
- All three JavaScript files pass `node --check`.
- Test snapshot: recorded R5 run 666_lab_20261011_190044_368345_PID31092, 26 entries,
  25 closed, one unresolved; canonical realized PAPER gross +$45.703 displayed +$45.70.
  No run archive, personal trading snapshot or screenshots are committed to Git.
- The telemetry adapter remains byte-identical to the previous version (Git blob
  049bc787fd6bf5f93c3c27ea993ff923dce451cc). Engine/strategy code is not touched.

## Boundaries

Managed Chromium blocks navigating to arbitrary local test URLs. Exact HTML/CSS/JS
assets were loaded into an offline page and provided the real recorded JSON response.
Local HTTP behavior/security was tested separately. These are not a claimed end-to-end
Windows R6 browser session. Native fullscreen buttons and emulated touch pointer input
were exercised in Chromium; iOS Safari and physical phone/tablet/TV acceptance remain
pending. No LAN/mobile device networking is enabled.

The Windows CMD installer has been inspected but not executed on the user's PC. It
exports a captured Git revision into a new versioned folder, verifies the UI version,
forwards launch arguments and leaves the old folder and running engine unchanged.

Earlier chart-data limitations still apply: sampled OHLC is not full exchange OHLC,
PAPER gross is not net profitability, and a displayed engine floor is not an execution
guarantee. This release changes display/layout behavior, not those semantics.

---

## Previous 1.0 baseline record (historical)

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
