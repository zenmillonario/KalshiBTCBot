# TACHYOS LEG GEOMETRY — CANONICAL DOCTRINE

Status: CANONICAL  
Applies forward from V9.5B forensic review  
Purpose: eliminate competing metaphors and define the tactical object once.

## The object

**LEG GEOMETRY** is the primary tactical shape model.

A leg is NOT a single EMA9 arc or mountain.

A complete leg is:

`OLD-SIDE RETURN SLOPE -> EMA30 APPROACH -> EMA30 TRANSFER -> OPPOSITE-SIDE BUILD -> EXPANSION / MATURITY`

The return slope on the old side and the new build on the opposite side are **one continuous leg**.

The EMA9/EMA30 cross is not the beginning of the leg. It is the transfer zone near the middle of the leg.

## Canonical vocabulary

Only these terms should be used as primary architecture names:

- **Spine** = EMA30
- **Leg** = the full EMA9 transition from one side of EMA30 into the opposite-side build
- **Return Slope** = EMA9 bending back toward EMA30 from the old side
- **Transfer** = EMA9 touch/cross/hand-off around EMA30
- **Build** = opposite-side EMA9 arc forming away from EMA30
- **Expansion** = the new side gaining amplitude / separation
- **Maturity** = the leg has substantially completed its expected geometry
- **Target Height** = BTC distance above/below the Kalshi target
- **Time Capacity** = estimated leg time remaining versus contract seconds remaining
- **Rollover Continuity** = whether the same leg should continue through the contract boundary

Legacy labels such as mountain, swirl, dragon dance, orbit, snake, crest, etc. may remain in old telemetry or observer modules, but they are descriptive sublabels only. They must not create new architectural objects.

## Tactical law

**EMA30 is the spine. EMA9 draws the legs around it.**

The actionable information begins on the RETURN SLOPE, before the cross.

Do not wait for the opposite-side build to become obvious before recognizing the new leg.

## Leg state machine

`LEG_START`
-> `RETURN_SLOPE`
-> `EMA30_APPROACH`
-> `TRANSFER`
-> `OPPOSITE_BUILD`
-> `EXPANSION`
-> `MATURE`
-> next `RETURN_SLOPE`

The end of one leg becomes the beginning of the next.

## Required leg coordinates

Every live leg should carry at least:

- leg_id
- leg_side
- leg_state
- leg_start_ts
- leg_age_sec
- EMA9 slope
- EMA9 curvature
- EMA9-to-EMA30 distance
- EMA30 slope fast / medium / slow
- transfer timestamp
- build amplitude
- current / peak amplitude
- prior-leg amplitude
- target_height = BTC - Kalshi target
- target_height at return slope
- target_height at transfer
- target_height during build
- seconds_left
- estimated_leg_seconds_remaining
- time_capacity_ratio
- rollover_state
- next_target if known
- inherited_leg_id across rollover

## Exit law

Position management must use the **whole leg**, not an isolated EMA9 sub-arc.

A local EMA9 arc break is NOT automatically a leg invalidation.

In particular:

- `EMA9_ARC_BROKEN` may describe the RETURN SLOPE or TRANSFER portion of an intact larger leg.
- a local swirl / snipe take-profit must not automatically flatten the entire tactical thesis while the leg remains valid.
- profit MFE / giveback is secondary to Leg Geometry, Target Height and Time Capacity.
- the position may be reduced, protected or re-entered later, but the battlefield thesis remains alive until the **whole leg** is invalidated or matured.
- if a position is closed while the leg remains valid, the active leg must remain eligible for immediate reacquisition without waiting for a new strategic parent.

A whole leg is invalidated only when the geometry materially fails, for example:

- the expected RETURN SLOPE fails and regenerates strongly back into the prior side;
- TRANSFER attempts fail repeatedly and the old-side build re-expands;
- the new opposite-side BUILD fails and price/EMA9 reclaim the spine against the intended leg;
- Target Height moves decisively against the leg with insufficient Time Capacity to recover;
- a genuine new opposite leg begins.

**Do not confuse a sub-arc ending with the leg ending.**

**Do not confuse taking profit on one position with abandoning the active leg.**

## Target Height

Target Height is part of the geometry, not a separate afterthought.

The same EMA9 leg means something different when BTC is far above target, far below target, approaching target, crossing target, reclaiming target, or sitting directly on target.

Target relationship must be evaluated continuously through the whole leg.

## Time Capacity

A leg must be judged against the 15-minute contract clock.

Do not label a leg failed merely because the contract ends before the leg finishes.

Example:

- estimated leg time remaining: 85s
- contract seconds left: 35s

Interpretation:

`LEG_INCOMPLETE -> EXPECT_ROLLOVER_CONTINUATION`

The geometry is continuous even when the Kalshi contract is not.

## Rollover Continuity

A contract boundary is a fencepost, not a market reset.

At rollover:

1. preserve the active leg and its state;
2. preserve EMA9 / EMA30 geometry;
3. carry the leg_id or explicit parent_leg_id;
4. acquire the new Kalshi target;
5. recompute Target Height against the new target;
6. recompute Time Capacity;
7. decide whether the inherited leg is still valid, transformed, mature, or reversing.

A fresh contract label must never erase an unfinished leg.

## Tactical priority

For 15-minute contracts, tactical priority is:

1. Leg Geometry
2. Target Height
3. Time Capacity / seconds left
4. Rollover Continuity
5. Fast displacement / volume / candle texture
6. Strategic parent / MTF context

Boss / Hand / MTF remain strategic context. They do not redefine the current leg.

## Parent and leg are different

Examples:

- Parent YES / current tactical leg NO
- Parent YES / current tactical leg YES
- Parent NO / current tactical leg YES
- Parent NO / current tactical leg NO

The current leg can agree with or oppose the strategic parent.

Level 2 must evaluate both YES and NO possibilities. It must not define the tactical candidate only as the opposite of the parent.

## Enough time?

This question becomes explicit:

`Does the current contract have enough time for the active leg to complete?`

Use:

- current leg age
- recent comparable leg durations
- current return/transfer/build speed
- target height
- current seconds left
- next target if available

Outputs should include:

- `ENOUGH_TIME_THIS_CONTRACT`
- `MARGINAL_TIME`
- `LEG_INCOMPLETE_EXPECT_ROLLOVER`
- `ROLLOVER_CONTINUATION_ACTIVE`


## Hardcoded authority laws

These are engine rules, not observer suggestions.

### Dual-side tactical evaluation

Level 2 must evaluate **YES and NO on every tactical cycle**.

It is forbidden to define the candidate side merely as `opposite(parent)`.

A tactical leg may be:

- parent-aligned continuation / reclaim;
- parent-opposed intermission / reversal;
- rollover continuation;
- post-exit reacquisition of the still-valid leg.

### Mature-leg continuation disarm

A mature leg loses same-side continuation authority when a credible RETURN SLOPE begins.

The old side may not re-enter by default merely because it was the previous successful direction.

Same-side authority is restored only by **regeneration**:

`RETURN_SLOPE_FAILS -> EMA9 TURNS BACK AWAY FROM SPINE -> OLD-SIDE AMPLITUDE RE-EXPANDS -> REGENERATION_CONFIRMED`

Without confirmed regeneration, old-side continuation is stale ancestry.

### Parent-aligned reclaim

When the strategic parent and current emerging leg agree, Level 2 may arm the aligned side early.

Do not require the legacy Early Impulse displacement gate to be satisfied first.

A valid parent-aligned reclaim may be recognized from:

- old opposite leg reaching maturity;
- RETURN SLOPE toward EMA30;
- target reclaim / favorable Target Height;
- EMA9 slope and curvature turning;
- fast candle / volume confirmation;
- sufficient Time Capacity.

### Rollover pre-arm

Before contract rollover, if the active leg is mature/extended and a RETURN SLOPE is emerging, Tachyos must evaluate the likely next leg before the fencepost.

At T-30 / T-9 / T-3, log and maintain:

- current leg side/state;
- next-leg candidate;
- Target Height to the current target;
- projected Target Height to the next target when available;
- upper/lower wick rejection;
- EMA9 slope and distance to EMA30;
- estimated leg time remaining;
- contract seconds remaining.

If the next leg is coherent, the next contract may open **PRE_ARMED**.

### Target and time authority near expiry

As time decays, Target Height gains tactical authority and strategic parent weight falls.

A target cross/reclaim in the final minute cannot remain observer-only by design.

Late-contract tactical evaluation must explicitly consider:

- target side;
- target distance;
- target hold / reclaim;
- 3/6/9 displacement;
- direction efficiency;
- price of the corresponding Kalshi side;
- seconds remaining.

The engine must not print `NO NEW TRADE` merely because a fixed cushion threshold missed by a few dollars while the settlement relationship is rapidly becoming decisive.

### Universal whole-leg exit gate

**Every non-emergency exit must pass one centralized Whole-Leg Exit Authority gate.**

No module may flatten a paper position directly because of a local sub-arc, profit lock, Treasury recommendation, or target wobble without this gate.

The following become advisory until the Whole-Leg Exit Authority approves:

- `V95A_ACTIVE_TREASURY_DEFEND`
- `EMA9_ARC_BROKEN`
- `CORE_SWIRL_SNIP_TP_22_5`
- `CORE_SWIRL_PROFIT_LOCK`
- `V92_STRUCTURE_BROKEN`
- `V92_PROTECT_WINNER_DIVERGENCE`
- ordinary MFE / giveback / trailing exits
- `LATE_TARGET_INVALIDATION`

The gate asks:

1. Is the whole leg still developing?
2. Has the whole leg matured?
3. Has the whole leg been materially invalidated?
4. Has a genuine opposite leg begun?
5. Does Target Height plus remaining Time Capacity make recovery implausible?

Hard bypasses may remain only for:

- contract close / settlement;
- unrecoverable market-data failure;
- explicit catastrophic opposite-leg confirmation;
- truly terminal expiry conditions;
- any separate paper-risk emergency stop intentionally retained for experiment safety.

### Position death is not leg death

If a position exits while its leg remains valid:

- preserve the active leg;
- preserve its leg_id / lineage;
- allow immediate reacquisition subject to price sanity;
- do not require Boss/Hand to rediscover the thesis;
- do not require a fresh opposite-parent event.

### Authority routing

If multiple observers already agree on a tactical side, the problem is authority, not perception.

Existing witnesses such as Looking Glass, Flexible Cage, War Council, Structural Events, Flash, Formation, Reentry Watch and Leg Geometry must be routed into the same dual-side tactical adjudication layer.

Do not create another named observer to solve an authority problem.

## Canonical doctrine

**The slope returning from one side of EMA30 and the build on the other side are one leg.**

**EMA30 is the spine.**

**Target Height tells us where that leg sits relative to settlement.**

**Time Capacity tells us whether the leg can finish before expiry.**

**Rollover does not reset the leg; it only changes the target against which the same geometry is judged.**

This doctrine supersedes treating individual EMA9 mountains/arcs as independent tactical objects.
