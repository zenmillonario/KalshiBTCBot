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

## Rule

**No new tactical metaphor is needed.**

The next code revision implements Leg Geometry, Target Height, Time Capacity, Rollover Continuity, dual-side authority and centralized Whole-Leg Exit Authority directly.
