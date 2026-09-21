# TACHYOS V9.5C — HARDCODED CHANGESET

Status: REQUIRED NEXT IMPLEMENTATION  
No mythology names. Plain architecture only.

## Confirmed V9.5B defects from live run

1. Tactical candidate is constrained to the side opposite the strategic parent.
2. Parent-aligned reclaim / continuation has no equivalent fast authority path.
3. Mature legs can keep re-entering the old side unless slower logic eventually changes.
4. Final-minute target crosses are often observer-only or blocked by rigid cushion thresholds.
5. V9.5B Thesis Shield is path-specific, not universal.
6. V9.5A Active Treasury can exit before V9.5B Thesis Shield gets control.
7. `EMA9_ARC_BROKEN` can flatten a position even when the whole leg is still valid.
8. `LATE_TARGET_INVALIDATION` is outside the current 120s Thesis Shield.
9. Local profit / giveback rules can kill a position while the leg continues.
10. Multiple observers may already agree on YES/NO while execution authority remains blocked.
11. Contract rollover can erase tactical urgency even though BTC geometry is continuous.

## Required hardcoded changes

### A. Leg Geometry becomes primary tactical state

Implement one canonical live state machine:

`LEG_START -> RETURN_SLOPE -> EMA30_APPROACH -> TRANSFER -> OPPOSITE_BUILD -> EXPANSION -> MATURE -> RETURN_SLOPE`

EMA30 = Spine.  
EMA9 = leg geometry.

### B. Evaluate both sides continuously

Every tactical cycle must compute a YES case and a NO case.

Do not use:

`candidate = opposite(parent)`

as the tactical architecture.

Parent becomes context only.

### C. Mature-leg disarm

Once a credible RETURN SLOPE begins, same-side continuation is disarmed.

Same-side re-entry requires explicit `REGENERATION_CONFIRMED`.

### D. Parent-aligned early reclaim

Allow a fast aligned entry when:

- prior opposite leg matured;
- return slope / transfer supports the parent side;
- Target Height is favorable or being reclaimed;
- fast EMA9 geometry confirms;
- there is enough Time Capacity.

Do not wait for legacy 30s impulse displacement if the leg geometry is already coherent.

### E. Target Height is always inside the leg model

Track target height at:

- leg start;
- return slope;
- EMA30 transfer;
- build;
- expansion;
- maturity;
- rollover remap.

### F. Time Capacity is explicit

For each leg estimate:

- leg age;
- expected remaining leg time;
- seconds left in contract;
- time capacity ratio.

Required labels:

- `ENOUGH_TIME_THIS_CONTRACT`
- `MARGINAL_TIME`
- `LEG_INCOMPLETE_EXPECT_ROLLOVER`
- `ROLLOVER_CONTINUATION_ACTIVE`

### G. Rollover pre-arm

At T-30 / T-9 / T-3:

- preserve current leg;
- determine maturity / extension;
- detect return slope;
- evaluate next-leg side;
- include wick rejection and fast displacement;
- compare with next target if available;
- allow next contract to open `PRE_ARMED_YES` or `PRE_ARMED_NO`.

### H. Expiry target-first authority

Inside the final 60 seconds, Target Height and seconds left outrank strategic parent.

Target cross/reclaim/acceptance plus fast directional evidence must be able to arm/authorize a trade.

Do not require a fixed $25 cushion as the only path to expiry authority.

### I. Centralized Whole-Leg Exit Authority

All non-emergency exits must call one gate before changing `paper_positions`.

The gate returns one of:

- `HOLD_LEG_DEVELOPING`
- `HOLD_RETURN_SLOPE_EXPECTED`
- `REDUCE_OPTIONAL`
- `EXIT_LEG_MATURE`
- `EXIT_LEG_INVALIDATED`
- `EXIT_OPPOSITE_LEG_CONFIRMED`
- `EXIT_TIME_TARGET_TERMINAL`
- `EMERGENCY_BYPASS`

No active module may bypass this gate except the explicit hard bypass list.

### J. Demote old exit reasons to proposals

These may propose an exit but not execute it directly:

- Active Treasury defend
- EMA9 arc broken
- swirl/snipe profit target
- swirl profit lock
- structural broken
- winner divergence
- ordinary giveback/trailing
- late target invalidation

### K. Leg survives position exit

A closed position does not clear active leg memory.

If the leg remains valid, Level 2 may reacquire immediately at sane price.

### L. Authority must use existing witnesses

When Looking Glass / Flexible Cage / War Council / Structure / Flash / Formation / Reentry / Leg Geometry already agree, route that agreement to tactical authority.

Do not solve this with another observer name.


### M. Failed-break / fakeout reversal authority

A target break that fails and is reclaimed must be treated as a first-class tactical reversal event.

Required behavior:

- if a NO leg is entered on a downside break and BTC reclaims the target quickly, NO continuation authority is disarmed;
- if the reclaim is accompanied by improving EMA9 slope / return geometry, YES may be armed immediately;
- the engine must not wait for `EMERGENCY_STOP_60` to discover the NO thesis was wrong;
- likewise, a failed upside break followed by target loss must be able to disarm YES and arm NO;
- a fakeout reversal may reuse the still-live opposite leg lineage instead of waiting for a fresh strategic-parent signal.

Required labels:

- `TARGET_BREAK_FAILED`
- `TARGET_RECLAIM_REVERSAL`
- `WRONG_SIDE_LEG_DISARMED`
- `OPPOSITE_LEG_REARMED`

This is especially important late in the contract, where a target reclaim can dominate lagging EMA30 / Boss context.



### N. Final-minute target fakeout authority

The last 60 seconds are a separate tactical regime. Settlement-control processes move to the front.

A brief cross of the Kalshi target is **not automatically a true directional transfer**.

The engine must distinguish:

- \`TARGET_TOUCH\`
- \`TARGET_CROSS_UNCONFIRMED\`
- \`TARGET_FAKEOUT_RECLAIM\`
- \`TARGET_ACCEPTED\`
- \`TARGET_TERMINAL_CONTROL\`

Final-minute adjudication must weight, in this order:

1. seconds remaining;
2. Target Height and which side currently owns the settlement line;
3. reclaim speed after the cross;
4. hold time on the new side;
5. current Whole-Leg Geometry state;
6. 3/6/9-second displacement and efficiency;
7. wick rejection / candle texture;
8. Kalshi price and available value;
9. strategic parent only as context.

A fast cross followed by an immediate reclaim, especially when the active leg never truly transferred, is a **fakeout**, not automatic confirmation of the crossed side.

Required labels:

- \`FINAL_MINUTE_MODE\`
- \`TARGET_CROSS_UNCONFIRMED\`
- \`TARGET_FAKEOUT_RECLAIM\`
- \`SETTLEMENT_SIDE_RESTORED\`
- \`TARGET_TERMINAL_CONTROL\`

### O. Parallel opposite-position transition

Entry authority and exit authority are independent.

In PAPER mode, a newly confirmed opposite leg may open an opposite-side position **before the existing position is formally closed**.

Do not force:

\`OLD POSITION EXIT -> WAIT -> OPPOSITE ENTRY\`

when the market has already transferred.

Allow:

\`OLD POSITION STILL OPEN + OPPOSITE LEG CONFIRMED -> OPEN OPPOSITE PAPER POSITION -> MANAGE BOTH INDEPENDENTLY -> OLD POSITION EXIT WHEN ITS GATE RULES\`

Requirements:

- parallel positions must have separate trade IDs, leg IDs, entry reasons and exit gates;
- the new opposite position must earn normal tactical authority; it is not an automatic hedge;
- no unlimited pyramiding: one active position per side per tactical transition unless a later experiment explicitly changes this;
- existing-position loss must not suppress a valid opposite entry;
- an opposite entry must not automatically liquidate the old side;
- logs must mark \`PARALLEL_TRANSITION_ACTIVE\`, \`OLD_LEG_POSITION\`, and \`NEW_LEG_POSITION\`;
- P/L and risk accounting must remain separate for both positions;
- this rule is PAPER ONLY until separately validated.



### P. Winner Harvest — let expansion run, harvest the stall

This supersedes the earlier fixed profit-floor interpretation.

A trade reaching +50% to +75% MFE is **not** an automatic exit and does **not** create a rigid trailing floor by itself.

The correct question is:

**Is the winner still expanding, or has it stopped paying?**

#### HOLD / LET IT BREATHE

Continue holding a large winner when the move is still visibly alive, for example:

- fresh MFE highs are still being made;
- current ROI is still advancing rather than hovering;
- 3/6/9-second displacement remains favorable;
- EMA9 Leg Geometry remains in BUILD / EXPANSION;
- Target Height continues improving for the held side;
- price/quote velocity remains healthy;
- the opposite leg has not begun a credible RETURN SLOPE / transfer.

There is **no profit cap**. A +50%, +75%, or larger winner may continue running.

#### HARVEST / TAKE IT

Once a trade is already in the +50% to +75% winner zone, become increasingly willing to take the profit when the move stalls.

A winner is a harvest candidate when several of these agree:

- no fresh MFE high for a short 3/6/9-style observation window;
- current ROI repeatedly hovers in a narrow band;
- quote velocity slows materially;
- 3/6/9 displacement loses directional force;
- EMA9 expansion flattens;
- Leg Geometry reaches MATURE / RETURN_SLOPE;
- target progress stops improving;
- repeated upper/lower rejection appears against the held side;
- the opposite tactical score begins building.

Initial paper behavior:

- at **+50% MFE**, arm \`WINNER_HARVEST_WATCH\`;
- while expansion continues, keep holding;
- if the winner stalls/plateaus for roughly **9 seconds** without a meaningful new high, allow harvest;
- at **+75% MFE or higher**, the same principle applies, but plateau/slowdown evidence receives greater weight;
- a fresh breakout/new MFE cancels the harvest timer and returns to \`WINNER_EXPANDING\`.

Required labels:

- \`WINNER_EXPANDING\`
- \`WINNER_HARVEST_WATCH\`
- \`WINNER_PLATEAU_9S\`
- \`WINNER_HARVEST_EXIT\`
- \`WINNER_BREAKOUT_CONTINUE\`

**Training law:**  
**Do not cut a winner because it became large. Cut it when it stops behaving like a winner.**



### Q. EMA30 Transfer-Zone Hysteresis — stop spine ping-pong

When price/EMA9 hover around the EMA30 Spine, repeated tiny crosses are **not separate legs**.

The engine must enter a neutral transfer state instead of alternating YES/NO entries.

Required state:

- \`TRANSFER_ZONE_UNRESOLVED\`

Enter this state when several of these agree:

- EMA9-to-EMA30 distance is small relative to recent BTC range;
- EMA9 repeatedly crosses/touches EMA30 inside a short window;
- price repeatedly crosses EMA9/EMA30 without directional separation;
- candles are small and alternating;
- 3/6/9-second displacement lacks consistent direction;
- Target Height is near the settlement line and repeatedly changes sign;
- YES/NO tactical scores alternate without a sustained score lead.

While \`TRANSFER_ZONE_UNRESOLVED\`:

- do not open a fresh YES or NO position merely because one tactical score temporarily leads;
- do not declare a new opposite leg from a single cross;
- preserve the existing leg lineage as unresolved;
- an existing position may still be managed by Whole-Leg Exit Authority;
- parallel opposite-position authority is suspended until a genuine transfer/escape is confirmed.

A new side may earn authority only after **escape from the transfer zone**.

Initial paper escape test:

1. directional separation from EMA30 / Spine is increasing;
2. 3/6/9-second displacement agrees with the same side;
3. the directional lead persists for at least **6 seconds**;
4. either Target Height confirms the side or Leg Geometry reaches OPPOSITE_BUILD / EXPANSION;
5. no immediate recross back through the Spine.

If the move recrosses before the escape test completes, reset to \`TRANSFER_ZONE_UNRESOLVED\`.

Add hysteresis:

- after a confirmed side transfer, do not flip the leg side again for ordinary evidence inside the next **9 seconds**;
- an earlier flip is allowed only for a strong target fakeout/reclaim or catastrophic opposite displacement;
- a prior side may regenerate only after \`REGENERATION_CONFIRMED\`, not from micro-cross chatter.

Required labels:

- \`TRANSFER_ZONE_UNRESOLVED\`
- \`TRANSFER_ESCAPE_ARMED\`
- \`TRANSFER_ESCAPE_CONFIRMED\`
- \`TRANSFER_ESCAPE_FAILED_RECROSS\`
- \`SIDE_FLIP_HYSTERESIS_ACTIVE\`

**Training law:**  
**A cross is a transfer attempt. Separation is the transfer.**


## Required audit fields

Every entry and exit decision must record:

- leg_id
- leg_side
- leg_state
- parent_side
- target_height
- target_event
- seconds_left
- estimated_leg_seconds_remaining
- time_capacity_ratio
- rollover_state
- EMA9 slope / curvature
- EMA9-to-EMA30 distance
- EMA30 slope fast / medium / slow
- current / prior leg amplitude
- regeneration state
- YES tactical score
- NO tactical score
- proposed exit reason
- centralized exit-gate ruling
- final action

## Non-negotiable implementation test cases

Replay / inspect these live-run failure classes:

- early parent-aligned YES missed while parent remained YES;
- late target cross below target with ~11s remaining but `NO NEW TRADE`;
- stale NO re-entry while next YES leg was already forming;
- observers signaling YES while execution remained NO/none;
- #7/#8 style early exits where sub-arc ended but whole leg continued;
- V95A Treasury exit occurring before Thesis Shield authority;
- `LATE_TARGET_INVALIDATION` inside a still-developing leg;
- rollover with mature/extended leg and next-leg warning visible before fencepost.
- #18/#19 case: YES impulse was defended out, NO entered on a fake breakdown, target was reclaimed, contract finished YES; system must either preserve the valid YES leg or immediately re-arm YES on failed-break reclaim instead of waiting for emergency stop.

- final-minute fakeout case: BTC briefly crosses PT inside the last 60 seconds, then quickly reclaims it while the larger leg remains intact; settlement-control logic must recognize the fakeout instead of treating the first cross as final truth.
- parallel-transition case: if the opposite leg earns authority before the existing position's exit gate releases, paper trading must be able to open the opposite side immediately and manage both positions independently.

- winner-harvest case: a trade reaches +50% to +75% MFE; if it continues making fresh highs / expanding, Tachyos must let it run, but if it plateaus or slows for a short confirmation window, Tachyos should harvest rather than donate the mature gain.

- spine-ping-pong case: price and EMA9 hover around EMA30 with small alternating candles and repeated micro-crosses; Tachyos must remain TRANSFER_ZONE_UNRESOLVED and must not rapid-fire YES/NO until directional separation persists.

## Rule

**No new tactical metaphor is needed.**

The next code revision implements Leg Geometry, Target Height, Time Capacity, Rollover Continuity, dual-side authority and centralized Whole-Leg Exit Authority directly.
