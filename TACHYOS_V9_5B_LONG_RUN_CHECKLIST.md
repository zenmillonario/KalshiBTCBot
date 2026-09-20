# TACHYOS V9.5B LONG-RUN CHECKLIST

Branch: `tachys-v9-5b-battle-council`  
Base: `3821fdb`  
Mode: PAPER ONLY

## Before launch

1. Put `tachys_v9_5b_level2_intermission_thesis_shield.py` in the repo root.
2. Confirm the working tree is clean except for the intended V9.5B file if it has not yet been committed.
3. Confirm the existing Kalshi credentials / environment used by V9.5A are unchanged.
4. Do not delete or rename inherited telemetry CSVs.

## Launch

Open two terminals:

- Engine: `START_TACHYOS_V9_5B.bat`
- Read-only Deck: `START_TACHYOS_COMMAND_DECK_V2.bat`

The engine should print V9.5B, PAPER ONLY, the 3/6/9 council doctrine, Thesis Shield, and the four new telemetry logs.

## New feeds expected

- `tachys_level2_battle_council_v9_5b.csv`
- `tachys_thesis_shield_v9_5b.csv`
- `tachys_latency_accounting_v9_5b.csv`
- `tachys_rollover_memory_v9_5b.csv`
- `tachys_run_manifest_v9_5b.csv`

The inherited RS1/RS2, Price Freshness, Formation, Structural, Reentry, Invalidation, Catastrophic Risk, Looking Glass and paper-trade feeds must continue to populate.

## What to watch — do not intervene merely because it looks strange

For the first long run, preserve the experiment. Observe:

- Parent state versus tactical intermission state.
- ARMED -> DECISIVE_3S / STANDARD_6S -> ENTERED or STAND_DOWN.
- Observer-first ask versus arm ask versus actual entry ask.
- Whether no-chase protects against price inflation.
- Whether Formation failure memory survives repaint and rollover.
- Whether sovereignty transfer resolves obsolete tactical memory.
- Whether the Thesis Shield prevents 5–40 second exits without trapping genuine catastrophic failures.
- Whether Reentry Watch keeps the battlefield alive after a local position exits.

## Stop / archive

Stop with Ctrl+C. Archive the complete run folder / CSV set before changing thresholds.

Forensics comes before tuning. Do not promote a new observer or threshold from one attractive screenshot.
