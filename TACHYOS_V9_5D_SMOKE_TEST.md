# TACHYOS V9.5D — SMOKE TEST BEFORE LONG RUN

Branch: `tachys-v9-5d-campaign-authority`  
Mode: PAPER ONLY

## Launch

1. Pull the V9.5D branch.
2. Run `START_TACHYOS_V9_5D.bat`.
3. It must pass `py_compile`.
4. Confirm banner shows:
   - Campaign Authority
   - Pre-Arm TTL 60s
   - Winner Harvest
   - Exit Court
   - Parallel Transition
   - Next Leg Prep
5. Run `START_TACHYOS_COMMAND_DECK_V3_2.bat`.

## Mandatory smoke checks

### A. Campaign persistence

Watch at least one contract through EMA9/EMA30 interaction.

Expected:
- Campaign Side does NOT alternate on every local leg wiggle.
- Candidate side may arm.
- transfer requires about 6s persistence.
- after a confirmed transfer, 9s hysteresis is visible.
- repeated micro-crosses do not create rapid YES/NO ping-pong.

FAIL if:
- 3+ alternating entries occur inside ~2 minutes without a clear EMA30 escape.

### B. Rollover Pre-Arm lifecycle

Expected:
- PREARM_FRESH appears after rollover only when preparation existed.
- age counts upward.
- first successful pre-arm entry changes state to PREARM_USED.
- unused pre-arm expires by 60s.
- no ROLLOVER_PREARM entry may occur after 60s.

FAIL immediately if:
- PREARM remains fresh beyond 60s.
- a second entry uses the same pre-arm.
- a trade several minutes into a contract says ROLLOVER_PREARM.

### C. Winner Harvest

For a trade that reaches +50% MFE:

Expected:
- fresh highs keep state WINNER_EXPANDING.
- +75% does NOT automatically exit.
- every meaningful new high resets plateau timing.
- when highs stop and strength decays, Winner Harvest may collect after roughly 9s of plateau evidence.

Positive control concept:
- #120 behavior: +75% -> +100% with repeated strength must be held.

Negative control concept:
- #112 behavior: +85.7% MFE must not be donated into a routine loss.

### D. Exit Court

Expected:
- ordinary local opposite-leg signals do not directly flatten.
- legacy exits are suppressed while Exit Court says HOLD.
- V9.5D exits should be labeled:
  - V95D_WINNER_HARVEST_EXIT
  - V95D_CAMPAIGN_TRANSFER_EXIT
  - V95D_TERMINAL_TARGET_EXIT
  - emergency inherited reasons only for true emergency cases.

FAIL if:
- V95C_EXIT_OPPOSITE_LEG_CONFIRMED directly closes ordinary trades.
- EMA9_ARC_BROKEN / Bird / Swirl / King Guard directly close ordinary positions.

### E. Parallel transition

If a campaign truly transfers while the old side remains open:

Expected:
- one opposite-side position may open before old side exits.
- never more than one active position per side.
- both positions have separate trade IDs.

## New telemetry

- `tachys_campaign_authority_v9_5d.csv`
- `tachys_winner_harvest_v9_5d.csv`
- `tachys_exit_court_v9_5d.csv`
- `tachys_prearm_lifecycle_v9_5d.csv`
- `tachys_run_manifest_v9_5d.csv`

## Initial smoke duration

Run for 1–2 contracts first.

Do NOT leave V9.5D unattended until:
- no traceback;
- pre-arm expiry is confirmed;
- campaign persistence is visibly working;
- Exit Court is sovereign;
- Winner Harvest does not cut an expanding winner.

After a clean smoke, archive before any threshold changes.
