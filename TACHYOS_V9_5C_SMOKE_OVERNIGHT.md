# TACHYOS V9.5C — SMOKE THEN OVERNIGHT

Branch: `tachys-v9-5c-leg-geometry`  
Frozen base: pushed V9.5B archive head `bf6d6d7`  
Mode: PAPER ONLY

## Smoke test

1. Launch `START_TACHYOS_V9_5C.bat`.
2. The launcher must pass `py_compile` before starting.
3. Confirm the startup banner says:
   - V9.5C
   - EMA30 = SPINE
   - YES and NO evaluated every tactical cycle
   - Active Treasury = proposal only
   - Whole-Leg Exit Authority
4. Launch `START_TACHYOS_COMMAND_DECK_V3.bat`.
5. Confirm these feeds begin populating:
   - `tachys_leg_geometry_v9_5c.csv`
   - `tachys_dual_side_authority_v9_5c.csv`
   - `tachys_whole_leg_exit_authority_v9_5c.csv` after the first open position
   - `tachys_rollover_continuity_v9_5c.csv` after the first rollover
6. Watch at least one contract or 5–10 minutes.
7. Stop immediately if there is a traceback, repeated engine exception, or impossible rapid-fire entries.

## What must be visibly different from V9.5B

- Both YES and NO have tactical scores.
- A return slope can create the next leg before EMA9 crosses EMA30.
- The old side is blocked while the new leg is active unless regeneration is confirmed.
- Parent-aligned reclaim can enter without waiting for legacy Early Impulse.
- Target Height and Time Capacity are visible.
- Rollover keeps the leg alive and can pre-arm the next contract.
- V9.5A Treasury does not directly flatten positions.
- Old local exits are suppressed while Whole-Leg Exit Authority says HOLD.
- Failed target break/reclaim can reverse tactical authority.

## Overnight

If the smoke run is clean, restart fresh and let it run untouched.

Suggested archive folder after the overnight run:

`runs\2026-09-20_v9_5c_leg_geometry_overnight_01`

Archive all CSVs before any threshold changes.
