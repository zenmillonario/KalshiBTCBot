# Nautilus 1.3.0-R7 — reproducible reliability repair

This additive source kit targets the **integrated Nautilus 1.2.0-R7**, not the older 1.1 UI in the root of this Git branch. No existing repository engine, observer, launcher, or dashboard file is changed by this kit.

The deliverable is a separate read-only viewer with time-window candle backfill, an optional small session-bound cache, a verified countdown independent of chart-price age, and six independently visible component-health indicators. The existing Bridge layout remains intact. No snapshot writer or strategy changes are included.

## Why an overlay kit

The actual R7 package is a separately distributed, hash-verified release. `BASELINE_PROVENANCE.json` pins every original R7 UI input. `overlay/` contains the new source and tests. `source_edits.json` contains exact, context-checked edits to existing R7 UI files. `RELEASE_FILES.json` pins the complete resulting release, including the untouched R7 adapter.

This avoids silently taking the older R6/1.1 source in this branch as the baseline. The builder reads the original R7 ZIP or extracted package; it does not import its Python or mutate it. Rebuilding was verified byte-for-byte against the tested complete release.

```text
python -B nautilus_r7_reliability/build_release.py --baseline TACHYS_R7_4H.zip --out NEW_RELEASE_DIRECTORY
python -B nautilus_r7_reliability/build_one_click.py --source NEW_RELEASE_DIRECTORY --cmd INSTALL_NAUTILUS_R7_RELIABILITY.cmd --zip The_Nautilus_R7_Reliability_1_3_0.zip
```

Users should use the supplied self-contained CMD rather than building it. It verifies the payload, installs a separate `C:\KalshiBTCBot_666Lab\nautilus_r7_reliability_1_3_0` directory, and starts only the viewer. The original R7 engine launcher still selects its bundled 1.2 UI until a later engine release deliberately integrates this repair.

## Verification and limits

90 Python tests, 15 Node rule checks and 28 offline Chromium component checks passed. The real R7 archived accounting still yields 34 closed, 24 wins and +$54.814 paper gross. The full 8.88 GB original snapshot remains on the user's E: drive; performance and first backfill there are pending. The browser screenshot uses recorded data, not an on-host live attachment.

R7 did not export an explicit developing candle in the audited stream. This viewer supports that field when genuinely present and otherwise labels sampled/unavailable forming data; it does not invent full-feed highs/lows. Observer failure is surfaced, not repaired or restarted. No full exchange-feed parity, execution guarantee or actual browser uptime is claimed.

See `overlay/README_START_HERE.md` and `overlay/VALIDATION.md` for complete source, cache, installation and test scope. No raw run archives, snapshots, account keys or credentials are included.
