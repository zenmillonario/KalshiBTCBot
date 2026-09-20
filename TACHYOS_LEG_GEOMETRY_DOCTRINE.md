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

## Canonical doctrine

**The slope returning from one side of EMA30 and the build on the other side are one leg.**

**EMA30 is the spine.**

**Target Height tells us where that leg sits relative to settlement.**

**Time Capacity tells us whether the leg can finish before expiry.**

**Rollover does not reset the leg; it only changes the target against which the same geometry is judged.**

This doctrine supersedes treating individual EMA9 mountains/arcs as independent tactical objects.
