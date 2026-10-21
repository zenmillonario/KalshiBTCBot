# Nautilus 1.3.0-R7 — executed validation

## Passed in this build environment

- **90 Python tests**: 37 inherited adapter/HTTP/Bridge tests with obsolete R6/1.1
  fixture metadata updated for the actual R7 baseline, plus 45 new history/clock/
  health tests and 8 isolated-installer tests. No production rule was weakened to
  make an old fixture pass.
- **15 Node tests** of the pure browser timer/health predicates.
- **28 Chromium component checks**: six independent health badges, real archived
  R7 Observer failure visible, canonical +$54.81 unchanged, TV feed/trades/chart
  within 1664×806, no horizontal overflow on 1024 and 420 widths, pan/zoom retained,
  requested time range transmitted, feed pause/resume, trade review, stale BTC with
  running verified timer, verification/disconnection pause, no JavaScript errors.
- JavaScript syntax checks for all four local script assets.
- Real archived R7 adapter comparison: 34 closed, 24 winners, +$54.814 gross,
  zero unresolved positions and no canonical accounting issues. The archive lacks
  the intentionally omitted snapshot stream, so the recorded screenshot honestly
  reports missing detailed candle history instead of showing fabricated bars.
- A **61,153,752-byte synthetic** repeated-history stream loaded the 45-minute view
  plus 15-minute buffer. In this container it took about 0.11 seconds, peaked at
  about 2.45 MB Python-tracked allocations, and produced a 12,218-byte candle cache.
  A verified cache reopening required zero backward source bytes. These figures
  are fixture measurements, NOT performance measurements of the user's E: drive
  or the real 8.88 GB R7 snapshot.
- Source-byte checks verify the retained `adapter.py` equals the integrated
  1.2.0-R7 package. Tests confirm the separate installer and derived cache do not
  alter original engine/run files, and mismatched payloads/targets are refused.

The managed Chromium environment blocks navigation to localhost/test-host URLs.
Browser components were exercised offline with exact local assets and a supplied
recorded state; live/failure cases were explicitly synthetic. Loopback HTTP,
same-origin/token checks and rejection of write endpoints were tested separately.
This is not claimed as an end-to-end Windows browser attachment.

## Remaining on-host checks

- First backfill, cache reuse and measured speed against the actual R7 JSONL on E:.
- Windows CMD/PowerShell installation and the exact running host's browser display.
- Complete developing OHLC: R7 did not export `frame.current_candle`; the new path
  supports it when genuinely present and otherwise explicitly labels sampled data.
- Actual Observer42 recovery: this UI surfaces its failure but does not fix/restart it.
- Integration into the next engine release's automatic UI selection. The frozen R7
  launcher is intentionally not modified.
- Absolute exchange clock offset, complete market-feed parity, real execution or
  fee-adjusted profitability are outside this display repair.

## Reproduce

```text
python -B -m unittest discover -s nautilus/tests -p "test_*.py" -v
node nautilus/tests/test_timer_ui.js
```

The real archived engine data and the multi-gigabyte source are not included in this
software package. No run logs, raw decisions, account keys or personal records are
committed to Git with the release.
