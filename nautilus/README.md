# The Nautilus 1.1.0 — Bridge

A separate, local, **read-only PAPER dashboard** for the Tachys Reassembled lab.
The engine, existing cockpit, observers, launchers, run pointers and strategy remain unchanged.

## New in 1.1 — viewport-fit Bridge

The main screen is now **feed + Trades/Decisions on the left, chart in the center,
positions/protection on the right**. Wide screens no longer place the evidence deck
below the chart. Panel contents scroll independently instead of hiding below the page.

Use **Display** for Auto, TV/Bridge, compact Desktop, Tablet, or Phone layout, plus
standard / 115% / 130% text. Preferences are stored in the local browser, not the engine.
Auto chooses Bridge at 1400+ CSS pixels, Desktop at 1150+, Tablet at 700+, otherwise Phone.
Explicit wide-screen preferences fall back when the window is too narrow. Browser zoom
changes available CSS pixels; a 55-inch diagonal alone does not determine layout.

**Fullscreen** in the top bar expands the whole dashboard. The chart's separate icon
expands only the chart. Unsupported or rejected requests show a visible fallback;
Windows F11 also works with the viewport-fitting layout. Fullscreen is user-initiated,
not silently entered. Normal browser Escape behavior is not intercepted.

Tablet keeps a chart plus a selected dock (below in portrait). Phone has directly
accessible Chart / Positions / Feed / Trades / Decisions / Briefing tabs. Right-side
Positions / Briefing / Navigator tabs keep detailed panels accessible. Selecting a trade
opens its recorded review on the right or in the phone dock. Touch pinch zoom and +/−
buttons are available. Feed pause, chart zoom/pan and table scroll survive updates.

Very short windows, including phone heights below 680 CSS pixels, intentionally allow
page scrolling rather than cropping panels to unusable heights. This is different from
the viewport-fit wide-screen Bridge at the user's 1664 × 806 screenshot size.

**Phone/tablet are layout modes, not remote device access.** The server still binds only
to 127.0.0.1. No firewall, LAN exposure, authentication model, account access or trading
authority changes are included. Use device layouts locally for now; remote access would
need a separate secure design.

The telemetry adapter is byte-identical to 1.0.0; `adapter_version` identifies it while
`version` identifies the 1.1.0 UI. Market freshness rules, accounting, candle provenance,
strategy logic and current run attachment semantics are unchanged.

## Launch on Windows

From the exported folder, double-click `RUN_NAUTILUS.cmd`, or call it from CMD.
The launcher uses `C:\KalshiBTCBot\.venv\Scripts\python.exe` when present, otherwise `py -3`.
Python 3.10+ and a current desktop browser are recommended. No pip, Node, cloud account,
chart subscription, credentials, or external assets are required at runtime.

Default live attachment is **only** the exact R6 pointer:
`C:\KalshiBTCBot_666Lab\LATEST_TACHYS_REASSEMBLED_R6_RUN.json`.
The pointer, manifest PAPER mode, R6 build identity, PID and runtime session are checked.
It never guesses the newest folder. It remains pinned if another run starts.

```
RUN_NAUTILUS.cmd
RUN_NAUTILUS.cmd --check
RUN_NAUTILUS.cmd --lab "E:\YourLab" --build R6
RUN_NAUTILUS.cmd --review --run "E:\ExtractedArchive\666_lab_your_run"
```

The archive directory must contain `launcher_manifest.json` and the telemetry files,
not another wrapper folder. `--review` explicitly permits a relocated supported
Reassembled archive and suppresses current quotes, marks, and the running countdown.
The browser opens on localhost port 8580, or the first free port through 8589.
Ctrl+C closes only Nautilus. It never stops or restarts Tachys.

`INSTALL_NAUTILUS_FROM_GIT.cmd` in the repository root fetches the separate Nautilus
branch and uses `git archive` to export **only** `nautilus/` and `RUN_NAUTILUS.cmd` into
`C:\KalshiBTCBot_666Lab\nautilus_v1_1_0`. It does not checkout, merge, reset, or pull
into your running working tree. An existing destination is refused, not overwritten.

## What is implemented

* Design #3-inspired dark-ocean layout, oversized illuminated target/current-price/timer
  cards, explicit PAPER/read-only status and exact run identity.
* Continuous 1-minute chart, 45-minute initial viewport, persistent candle spacing,
  drag/zoom, price-axis scaling, resizable quote pane, fullscreen and return-to-live.
* Native YES/NO bid/ask history on the same time axis, with gaps between contracts,
  invalid records and missing intervals. No complementary quotes are invented.
* Canonical full-ledger accounting; all distinct position identities remain visible.
  Bid marks require exact native quote identity, freshness and held-side permission.
* Clickable entries, exits and table rows; recorded trade reasons and MFE/MAE; selected
  trade duration shading. Missing evidence stays "Not recorded".
* Visible console feed beside the trades table, importance filters, user scroll pause,
  unread-line count, and safe text rendering. Original console timestamps are preserved
  when present; missing timestamps are not manufactured.
* Engine-reported protection cards; no new stop policy or trading authority.
* Session-matched Navigator output where available; unmatched sidecars are withheld.
* Local connection-loss warnings, source diagnostics, strict file route allowlist,
  same-origin checks, per-launch read token and no HTTP write/order endpoints.

## Chart provenance and limitations

This release uses a **custom local Canvas chart**, not the TradingView application or
Lightweight Charts library. It deliberately needs no downloaded JavaScript or separate
frontend runtime. Time is stored in UTC seconds and displayed in America/New_York.

**Solid candles** are actual OHLC bars exported by the engine: its complete warmup seed
and optional `hf21_decision_snapshots.jsonl` `frame.box_candles` records. An explicit
`frame.current_candle` export is supported but is not assumed to exist.

**Dashed-outline candles** are OHLC of recorded price samples, **not complete exchange
candles**. Their missing intraminute highs/lows cannot be recovered from snapshots.
R5's archived data had a complete seed but sampled-only live prices. R6 supports an
optional decision-snapshot export; availability/coverage depends on the actual run.
The chart, hover tooltip and Health panel disclose this distinction. The software does
not claim TradingView candle parity or invent absent highs/lows. No engine exporter was
changed as part of this release.

Live EMA values come from engine telemetry. Pre-run EMAs are reconstructed only from
the *entire* exported seed using the engine's SMA-seeded EMA convention, not from the
visible 45-minute window. Read Health for source/window coverage.

The default in-memory chart ceiling is 1,440 minutes. Initial telemetry reads and the
recent decision/feed buffers are bounded. Full canonical accounting is never tailed:
missing, malformed, duplicate, mismatched, or oversized (>16 MB) accounting ledgers
withhold totals. Quotes/prices marked stale are not represented as current tradable marks.

Review selects recorded trades; it is **not** a causal tick-by-tick replay engine.
Hero instruments and console tape remain the latest recorded run snapshot while the
selected trade panel/chart inspect the chosen trade. The recent decision window may
not contain an older trade's protection sequence; absence is not proof of disabled
protection. A reported bid floor is not an execution guarantee. PAPER P&L is gross,
before fees, and does not establish live profitability.

## Source files read

`launcher_manifest.json`, `tachys_runtime_hf2.json`,
`tachys_canonical_trade_events_hf2.csv`, `tachys_canonical_quotes_hf2.csv`,
`tachys_price_arc_phase_v9_4j.csv`, `tachys_r15_history_seed.json`,
`tachys_r15_command.csv`, optional `hf21_decision_snapshots.jsonl`,
`tachys_paper_trades_v9_2_6.csv` (context only), `tachys_r15_planner_state.json`,
`console.log`, and the session-matched lab Navigator status file.

No account keys are requested. Keep this server loopback-only; it is not a public web
service. Log redaction is best-effort and not a substitute for avoiding secrets in logs.
The adapter does not write a new stream to disk or alter any run files.

## Developer checks

```
python -B -m unittest discover -s nautilus/tests -v
node --check nautilus/static/app.js
node --check nautilus/static/chart.js
```

Optional Chromium component test (developer Playwright installation only):

```
python nautilus/tests/browser_checks.py /path/to/recorded_state.json /path/to/output
```

For the new display checks: `python nautilus/tests/bridge_checks.py /path/to/recorded_state.json /path/to/output`.

See `VALIDATION.md` for what was actually tested and what still needs on-host acceptance.
