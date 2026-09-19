# TACHYOS MANAGEMENT AUDIT — V9.5A

## Scope
Frozen V9.5A baseline:
- run commit: `ee2db0c70ef0adeea173138a9e8c6c273cb7652a`
- paper only

This audit separates:
1. entry direction,
2. campaign / chapter identity,
3. position management.

## Core finding
V9.5A's realized P&L understates the directional quality of the entry engine.

Across 68 trades:
- 47 / 68 entries matched the eventual contract settlement side = 69.1%
- only 34 / 68 trades realized a profit
- 21 trades were correct at settlement but lost under active management

The management problem is therefore not a minor afterthought.

## Exit reason audit

| Exit reason | N | Net P&L | Correct at settlement | Correct-but-lost |
|---|---:|---:|---:|---:|
| EMA9_ARC_BROKEN | 12 | -$24.54 | 7 | 7 |
| LATE_TARGET_INVALIDATION | 5 | -$23.20 | 4 | 4 |
| KING_GUARD_FAILSAFE | 2 | -$20.90 | 1 | 1 |
| EMERGENCY_STOP_60 | 2 | -$15.49 | 0 | 0 |
| V92_STRUCTURE_BROKEN | 2 | -$7.83 | 2 | 2 |
| ANTICIPATION_FAST_FAIL | 4 | -$4.71 | 3 | 3 |
| V95A_ACTIVE_TREASURY_DEFEND | 16 | +$9.17 | 12 | 4 |
| EARLY_TAKE_PROFIT_50 | 5 | +$29.66 | 5 | 0 |
| CORE_SWIRL_SNIP_TP_22_5 | 11 | +$30.378 | 7 | 0 |

Interpretation:
- emergency stop appears to be doing genuine catastrophe control
- Active Treasury is net helpful
- tactical profit-taking is useful
- the largest management mismatch is in structural invalidation of trades that later settle correctly

## ANTICIPATION management

Existing V8.1 lifecycle:
- ANTICIPATION_CONFIRM_ROI = +10%
- ANTICIPATION_CONFIRM_SECONDS = 18s
- ANTICIPATION_FAST_FAIL_SECONDS = 18s
- ANTICIPATION_FAIL_ROI = -8%

Fast fail requires:
- position is anticipation
- not yet confirmed
- age <= 18s
- ROI <= -8%
- `structural_failed`

In the V9.5A run:
- 4 fast-fail exits
- 3 / 4 later settled on the original trade side

Therefore the problem is not just the -8% threshold.
The `structural_failed` concept itself is too local for an Anticipation thesis.

An Anticipation trade is entered precisely before the short-term structure has completed confirmation. It should not be invalidated by the same micro evidence used to manage a confirmed/retest trade.

### Proposed distinction
Anticipation invalidation must reference the parent thesis:
- parent leg invalidated,
- gate thesis disproven,
- target/settlement geometry materially reversed,
- authority transfer confirmed.

A temporary EMA9 wobble or local structural score failure is insufficient by itself.

## EMA9_ARC_BROKEN

Current rule requires:
- arc relation BROKEN
- persistence depending on time left
- arc-break evidence score
- same-side structural thesis no longer VALID/STRONG
- trade not already proven enough for another protection path

Run:
- 12 exits
- all 12 lost
- 7 later settled on the original side
- net -$24.54

The current arc break logic is coherent for a micro arc.
The problem is that a broken micro arc is being allowed to terminate a parent campaign thesis.

Required architecture change:
- micro arc break ends a micro arc
- it does not automatically end the parent leg / mountain / campaign
- management asks Looking Glass + Arc Detective whether this is:
  - normal counterwave,
  - child-arc reset,
  - parent-leg failure,
  - genuine campaign authority transfer

## V92_STRUCTURE_BROKEN

Current structural manager combines:
- hold authority
- structural score advantage
- target acceptance
- EMA30 acceptance

The two V9.5A exits using `V92_STRUCTURE_BROKEN` both later settled on the original entry side.

This indicates that the manager's "broken" label can still describe a local interval rather than the contract thesis.

Future state must include scale:
- MICRO_BROKEN
- LEG_BROKEN
- CAMPAIGN_BROKEN
- SETTLEMENT_BROKEN

A manager may only exit a CAMPAIGN because CAMPAIGN structure broke.
A RAID may exit on MICRO/LEG break.

## LATE_TARGET_INVALIDATION

Current rule is late-contract and requires:
- ROI sufficiently negative
- favorable cushion < 0
- weak target / EMA30 structure
- no meaningful prior MFE
- arc weak/broken or hard expiry

Run:
- 5 exits
- 4 of 5 later settled on the original side
- net -$23.20

This strongly suggests target acceptance is being treated too discretely.

Future Settlement Command should track:
- target-cross duration
- target recapture count
- orbit center relative to target
- target dislocation percentile
- remaining-time volatility budget
- whether the target is at the edge or center of the local orbit

A brief target disadvantage inside a wide orbit is not equivalent to settlement invalidation.

## KING'S GUARD

King's Guard is conceptually sound:
profit arms protection, deterioration authorizes defense.

However the failsafe can still allow very large giveback:
`max(-25%, peak_roi - 50%)`

Trade #58 is the clearest threshold problem:
- roughly +19% MFE
- missed the 20% proven tier
- later exited -$6.08

Research item:
- continuous/tiered proof rather than a sharp 20% cliff
- test an 18% observation tier
- structural proof can supplement pure ROI proof

Do not promote 18% merely because it matches 3/6/9 preferences; it must improve replay data.

## Dynamic intent promotion

The existing engine already promotes some ANTICIPATION positions to ARC_RIDER when:
- not in swirl
- EMA9 relation becomes HEALTHY
- arc stage is RELEASE / BUILDING / EXPANDING

Eight trades changed intent between entry and exit in V9.5A.

This mechanism should be preserved, but formalized in the new router:
- entry_mode remains ANTICIPATION forever as provenance
- active_mission may transition RAID -> CAMPAIGN or ANTICIPATION -> ARC_RIDER
- the original entry mode should not be overwritten

Why:
the system needs to know both:
1. how the trade was born,
2. what mission it has earned now.

## First-read versus re-entry

First entry in each traded contract:
- 39 trades
- +$14.831
- PF 1.312

All subsequent same-contract entries:
- 29 trades
- -$24.537
- PF 0.533

But this is not a one-trade-per-contract argument.

Same-contract RAID re-entries:
- +$6.063

Same-contract CAMPAIGN re-entries:
- 0-4
- -$26.27

Therefore:
- preserve re-entry capability
- require campaign-level authority transfer before declaring a new CAMPAIGN
- otherwise repeated entries remain tactical raids

## Naive router shadow counterfactual

Diagnostic only; not an executable portfolio simulation.

If we keep:
- every first entry in each contract
- all later entries classified RAID

and suppress:
- later CAMPAIGN
- later SCOUT
- later ATTACK

the observed-trade arithmetic would be:
- first-entry P&L: +$14.831
- RAID re-entry P&L: +$6.063
- total: **+$20.894**

The suppressed later non-RAID groups lost:
- CAMPAIGN: -$26.27
- SCOUT: -$3.79
- ATTACK: -$0.54

Caution:
blocking trades changes later state and opportunity availability, so +$20.894 is NOT a valid live backtest result.

It is strong enough to justify a shadow router experiment.

## Management constitution

### RAID
- tactical target
- quick harvest
- micro/leg invalidation allowed
- no heroic hold
- may oppose macro terrain

### CAMPAIGN
- parent thesis survives child-arc resets
- micro arc break is not enough
- Looking Glass + campaign authority decide invalidation
- ordinary counterwaves are expected
- re-entry requires genuine campaign reset

### ANTICIPATION entry mode
- born before confirmation
- invalidation is parent-thesis based
- short-term discomfort is expected
- may earn promotion into ARC_RIDER / CAMPAIGN

### RETEST entry mode
- confirmation has already been paid for
- failed retest may invalidate quickly

### ARC_RIDER
- current management is comparatively effective
- preserve tactical/profit protection behavior unless later evidence contradicts it

### EARLY_IMPULSE
- requires tactical exits
- hold-to-settlement was worse than actual management in V9.5A

### SETTLEMENT
- target gravity/time dominate
- macro trend is context
- target acceptance must be continuous/probabilistic rather than a single local event

## Next experiment
The next safe experiment should be SHADOW ONLY:

`Battlefield Router Shadow`

It should not change paper entries or exits.

For every legacy entry candidate and active paper position it should emit:
- terrain species
- chapter id / chapter label
- proposed mission
- entry mode provenance
- active mission
- Commander support/dissent
- parent thesis id
- target gravity state
- allowed manager
- hypothetical action: WAIT / ENTER_RAID / ENTER_CAMPAIGN / HOLD / HARVEST / INVALIDATE
- reason

Then replay the frozen V9.5A run and Emperor Tape against that output before promoting any authority.


# Phase 5 — Campaign is earned, not declared

The existing Trade Mission observer contains a promotion mechanism:

- RAID -> CAMPAIGN when Borders reaches `BOUNDARY_RELEASE` and Hand authority matches the trade side
- ATTACK -> CAMPAIGN after fresh authority confirmation

This shadow promotion was unexpectedly strong in the V9.5A run.

## Initial CAMPAIGN assignments
At entry:
- 6 trades were immediately assigned CAMPAIGN
- 1 win / 5 losses
- net **-$29.453**

## Trades promoted into CAMPAIGN later
Eight trades were promoted after entry:
- 7 wins / 1 loss
- net **+$22.274**

Some promotions happened while the trade itself was still negative.

That is important:
campaign status was earned from battlefield structure, not from ROI.

### Interpretation

> **Campaign is a status the market earns after release. It should usually not be a declaration made merely because an entry signal points in the same direction as Hand authority.**

This may be one of the cleanest architectural discoveries in the audit.

A trade can begin as a RAID or ATTACK and later earn CAMPAIGN status when:
- churn boundary releases,
- Hand authority aligns,
- Looking Glass agrees that the chapter changed,
- parent structure survives.

This is materially different from labeling a trade CAMPAIGN at entry because the current side matches the Hand.

## RAID harvest shadow

The Trade Mission observer already emits `HARVEST_EDGE_SHADOW` at:
- RAID ROI >= 15%

36 V9.5A trades emitted at least one harvest signal.

If each of those trades were hypothetically closed at the FIRST harvest:
- hypothetical P&L across those 36 trades: **+$70.708**
- actual P&L across those same trades: **+$64.373**
- difference: **+$6.335**

Again, this is a diagnostic counterfactual, not an executable backtest because altered exits change later opportunities.

### Promotion-aware split

For trades that later earned CAMPAIGN promotion:
- 3 had emitted harvest before promotion
- first-harvest hypothetical: +$5.278
- actual outcome: +$10.750
- harvesting early would have given up **$5.472**

For trades that never promoted:
- 33 trades
- first-harvest hypothetical: +$65.430
- actual outcome: +$53.623
- first harvest would have improved observed arithmetic by **$11.807**

### Doctrine

> **A Raid should harvest its tactical edge unless the battlefield is actively earning Campaign promotion.**

This gives the Mission Selector a concrete purpose:
- RAID owns quick asymmetry
- CAMPAIGN owns persistence
- the promotion boundary determines whether a +15% edge should be harvested or allowed to become a larger campaign

The current shadow brain already approximates this distinction. The next architecture should integrate it rather than invent another manager.


# Phase 6 — first-entry control corrects the Anticipation story

The earlier all-trade hold-to-settlement diagnostic was intentionally labeled non-executable because repeated entries inflate it.

A stricter first-entry-per-contract control changes the interpretation in an important way.

## First-entry intent comparison

### ANTICIPATION
- 20 first entries
- 15 / 20 settlement-direction correct = 75%
- actual P&L: **-$9.576**
- independent hold-to-settlement diagnostic: **+$38.70**

So Anticipation still contains substantial directional information.

However, looking only at the eight first-entry Anticipation trades that exited through the main structural-loss reasons:
- actual: **-$19.28**
- naive hold-to-settlement: **-$20.99**

That means a blanket rule such as "Anticipation should simply be held longer" is WRONG.

The correct conclusion is narrower:

> Anticipation needs a better parent-thesis invalidation model, not infinite patience.

Some early Anticipation losses are genuine bad theses and should still be killed.

### ARC_RIDER
- 11 first entries
- 8 / 11 settlement-direction correct
- actual: **+$18.80**
- hold diagnostic: **+$31.44**

Arc Rider remains one of the healthier species, though there is still room to improve management.

### EARLY_IMPULSE
- 7 first entries
- actual: **+$4.367**
- hold diagnostic: **-$7.21**

This again confirms Early Impulse should remain tactical.

### EXHAUSTION_FLIP
- one first-entry example
- actual: +$1.24
- hold diagnostic: -$14.88

This remains a textbook Raid species.

## Exit-family nuance

Among first entries only:

### EMA9_ARC_BROKEN
- 8 exits
- 5 eventually settled on the original side
- actual: -$19.52
- hold diagnostic: -$0.64

The arc-break manager is too aggressive in some cases, but not universally wrong.

### ANTICIPATION_FAST_FAIL
- 2 first-entry examples
- only 1 eventually settled on the original side
- actual: -$2.10
- hold diagnostic: -$4.05

This is not enough evidence to delete Fast Fail.

Instead, Fast Fail should be redefined around parent-thesis failure and tested in shadow.

### V92_STRUCTURE_BROKEN
- one first-entry example
- original side later settled
- actual -$4.59 vs hold +$12.15

Strong candidate for scale-aware invalidation.

### LATE_TARGET_INVALIDATION
- one first-entry example
- original side later settled
- actual -$4.84 vs hold +$7.48

Strong candidate for Settlement Command redesign.

## Updated management conclusion

Do NOT replace the current manager with "hold Anticipation to settlement."

Instead:

1. preserve the early-entry edge,
2. classify invalidation by scale,
3. kill genuinely broken parent theses,
4. ignore child-arc noise when parent thesis remains intact,
5. route tactical species to tactical exits,
6. route settlement species to target/time logic.

This is exactly why the next experiment must be a Battlefield Router shadow rather than a simple stop-threshold tweak.
