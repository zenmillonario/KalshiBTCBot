# Nautilus 1.3.1-R7 — post-read clock and stop-boundary hotfix

This source patch supersedes the 1.3.0 viewer for the two defects reproduced from
the user's 20-minute PAPER UI check. It is not an engine/strategy release.

## Corrections

1. The UI adapter samples freshness after source reads instead of using poll-start
   wall time. A legitimate runtime file update during the read is no longer falsely
   future/stale. True future and expired timestamps remain invalid. Runtime TTL is
   still 5 seconds; quote TTL is still 3. No accounting or permission formula changes.
2. A live-started history worker now learns and freezes the validated final session
   end. Pending and future coverage requests/expected sets are clipped to that end.
   The final manifest is preferred; an explicit same-session stopped runtime record
   may temporarily supply a labeled provisional bound. Real internal candle gaps
   remain warnings. Chart pan and zoom are not recentered.

Health adds post-read timestamps/reasons and a bounded 32-sample diagnostic buffer.
The original R7 engine, snapshot writer, sidecars and frozen package are unchanged.
The UI copy of Adapter.poll is intentionally changed, so the previous claim that
that UI file is byte-identical to R7 is no longer applicable to the new viewer.
All other adapter function source segments are checked against their parent hashes.

## User delivery

The self-contained `UPDATE_NAUTILUS_1_3_1.cmd` installs the complete verified viewer
into `C:\KalshiBTCBot_666Lab\nautilus_r7_reliability_1_3_1` and opens it. It leaves the
old 1.3.0 folder intact and does not start another engine run. The next on-host check
uses the stopped 20-minute run; no additional PAPER run is needed for that step.
The complete source/test package supplied with the installer is:

`The_Nautilus_R7_Reliability_1_3_1.zip`

SHA-256: `518da28be8053680c1b47dc031437013e48b230fad719f11f4a8fbb1ecfd21c3`

This Git folder preserves the exact changed runtime-source recipe, its before/after
hashes, the 23 new regression tests and release verification. It is **not a standalone
installer** and is not intended to be applied in the running engine directory.
`verify_runtime.py` checks the recipe in memory against the parent and candidate ZIPs.
The complete distributed ZIP also contains updated documentation, version/provenance
assertions and a browser test harness. Its PACKAGE_MANIFEST pins every supplied file.

## Executed checks

- 113 Python tests (90 inherited with UI metadata/pin assertions updated; 23 new).
- 15 Node timer/health rules.
- 12 offline Chromium component checks; separate Python HTTP safeguards unchanged.
- Same before/after race fixture: old STALE / age -0.25s / timer false; new CURRENT /
  age +0.05s / timer true. Real future and old timestamps remain rejected.
- Same stop-boundary fixture: old 21 expected minutes; new 19. Removing a real
  in-run fixture candle still gives 18/19 GAPS, not a blanket READY.
- Isolated install/reinstall with the actual R7 baseline and byte checks; all source
  files and installer payload hashes verified. Full source patch reconstruction was
  also compared byte-for-byte with the tested release in the build container.

These are build-container/synthetic tests, not proof of live Windows uptime, actual
20-minute OHLC completeness or the cause of all 87 STALE samples in the old receipt.
Windows installation and the corrected stopped-run screen need on-host acceptance.
Observer/Navigator UNVERIFIED warnings and missing explicit forming OHLC are not
repaired or hidden by this change. Keep the original raw snapshots intact.

Run tests from the full extracted 1.3.1 release:

```
python -B -m unittest discover -s nautilus/tests -p "test_*.py" -v
node nautilus/tests/test_timer_ui.js
```

No changes are merged into trading authority by this patch.
