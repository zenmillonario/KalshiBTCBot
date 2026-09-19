# TACHYOS BATTLEFIELD ROUTER SHADOW SPEC

## Status
SHADOW ONLY.

This document defines the next research layer.
It does not alter V9.5A paper entries, exits, sizing, or settlement behavior.

## Why this exists
The V9.5A audit showed three separate truths:

1. Tachyos often identifies the eventual settlement side.
2. Same-contract re-entry churn destroys much of that edge.
3. Existing shadow intelligence already knows enough to distinguish RAID from CAMPAIGN and to promote a trade only after battlefield release.

The next experiment should therefore test command routing before granting any new authority.

## Router principle
The Router does not create a new signal.

It answers:

> Given everything Tachyos already knows, what kind of mission is permitted right now, and which manager would own it?

## Inputs
The Router consumes existing state from:
- EMA ancestry / rejection quality
- Price-Arc Phase
- EMA geometry / arc sequence
- Failed Regeneration
- Looking Glass / Arc Voyage
- Boss / Orbital Clock
- Regime Handshake
- Master of Borders
- Dragon Dance
- Rollover War Council
- Target Tube / Migration
- Formation Handoff
- Campaign Ledger
- Trade Mission
- Treasury / Medic
- current quote, target, time, BTC/EMA values

No new detector is required for version 1 of the Router.

## Output record
Each decision sample emits:

- timestamp
- ticker
- proposed_side
- current_position_side
- entry_mode
- current_chapter
- chapter_score
- parent_campaign_id
- battlefield_species
- boss_side
- hand_side
- ema_command_side
- arc_command_side
- looking_glass_side
- settlement_side
- commander_support_count
- commander_dissent_count
- contradiction_class
- target_gravity_state
- borders_state
- dragon_state
- price_arc_phase
- mission_candidate
- mission_status
- manager_owner
- shadow_action
- shadow_reason
- promotion_readiness
- campaign_reset_evidence
- invalidation_scale

## Entry-mode provenance
Entry mode is immutable provenance:
- ANTICIPATION
- RETEST
- IMPULSE
- HANDOFF
- EXHAUSTION_FLIP

A position may change active mission later, but its birth mode is never overwritten.

Example:
- born ANTICIPATION
- starts RAID
- later earns CAMPAIGN
- provenance remains ANTICIPATION

This prevents the current architecture from forgetting how much confirmation was paid for at entry.

## Mission states

### WAIT
Default when:
- battlefield is tangled,
- contradiction is unresolved,
- no asymmetric raid exists,
- a repeated campaign has not earned a reset.

### RAID
Default tactical mission in contested terrain.

Can be counterterrain.

Management:
- harvest edge quickly,
- micro/leg invalidation allowed,
- no heroic rescue.

### ATTACK
Short-lived release mission around rollover or boundary break.

Can promote if authority stabilizes.

### CAMPAIGN_CANDIDATE
New research state.

The market appears directional, but campaign authority has not yet been earned.

No special persistence rights yet.

### CAMPAIGN
Must be earned.

Preferred promotion evidence:
- Borders = BOUNDARY_RELEASE or clear sustained release
- Hand authority = trade side
- Looking Glass says chapter transition is genuine
- EMA Command does not show immediate failed reclaim
- parent leg is not mature/exhausted
- target geometry is not materially hostile

Exact thresholds remain shadow research.

### SETTLEMENT
Activated late when target/time geometry dominates directional terrain.

## Campaign promotion rule

V9.5A evidence:
- immediate CAMPAIGN assignments: 1-5, -$29.453
- later promotions into CAMPAIGN: 7-1, +$22.274

Therefore shadow version 1 should strongly prefer:

```
RAID / ATTACK / CAMPAIGN_CANDIDATE
        -> evidence
        -> CAMPAIGN
```

rather than declaring CAMPAIGN immediately at entry.

This is a research policy, not yet active authority.

## Re-entry policy

A position exit does not erase:
- chapter
- campaign
- parent mountain
- gate history
- target history

For a same-contract new entry:

### If no genuine campaign reset
- CAMPAIGN is not permitted
- RAID may still be permitted
- SETTLEMENT may still be permitted

### If genuine campaign reset
Campaign may be re-earned.

Campaign reset evidence should require multiple categories, not simply:
- new arc id,
- phase change,
- local EMA9 rollover.

Possible categories:
- Hand authority transfer
- Boss / theater transfer
- EMA30 gate reclaim or rejection regime change
- Borders release
- target-gravity relocation
- parent mountain / leg break
- Looking Glass chapter transition

## RAID manager

Existing shadow threshold:
- `HARVEST_EDGE_SHADOW` at +15% ROI

V9.5A diagnostic:
- non-promoted RAID harvests generally benefited from taking the first edge
- trades that later earned CAMPAIGN benefited from not harvesting too early

Shadow rule:

```
if mission == RAID and roi >= 15%:
    if promotion_readiness is LOW:
        HARVEST_EDGE_SHADOW
    else:
        HOLD_FOR_PROMOTION_SHADOW
```

No paper effect yet.

## ANTICIPATION manager

Do not use ordinary micro structure failure as sufficient invalidation.

Shadow invalidation must classify scale:

- MICRO_BROKEN
- LEG_BROKEN
- PARENT_BROKEN
- CAMPAIGN_BROKEN
- SETTLEMENT_BROKEN

ANTICIPATION should normally survive MICRO_BROKEN.

It may exit when:
- parent thesis is disproven,
- campaign authority transfers,
- settlement geometry becomes materially hostile,
- catastrophe stop is reached.

## RETEST manager

A failed retest is much more meaningful because confirmation was already paid for.

RETEST may invalidate on:
- reclaim lost,
- retest fails,
- renewed separation against,
- gate acceptance against.

## CAMPAIGN manager

Campaign manager ignores ordinary child-arc noise.

It responds to:
- parent leg failure,
- campaign authority transfer,
- target/settlement contradiction,
- proven-trade protection,
- campaign exhaustion.

## SETTLEMENT manager

Owns:
- target distance
- target-to-EMA center distance
- orbit percentile
- target dislocation
- crossing persistence
- time left
- quote elasticity
- recapture frequency

A target crossing is not automatically invalidation.

The question is whether the target has moved from edge to center/opposite gravity and whether there is enough time/volatility for recovery.

## Contradiction classes

### C0 — ALIGNED
Commanders broadly agree.

### C1 — LOCAL_DISSENT
One local observer disagrees with larger terrain.

Usually does not reverse campaign.

### C2 — TACTICAL_COUNTERTREND
RAID may oppose campaign terrain.

Must be explicitly labeled.

### C3 — AUTHORITY_TRANSFER_CANDIDATE
Multiple independent commanders disagree with old campaign.

No automatic reversal yet.

### C4 — AUTHORITY_TRANSFER_CONFIRMED
New campaign side may be earned.

Every opposite-direction CAMPAIGN entry must show the contradiction path that got it to C4.

## Shadow actions
Possible outputs:
- WAIT
- ENTER_RAID_SHADOW
- ENTER_ATTACK_SHADOW
- CAMPAIGN_CANDIDATE_SHADOW
- PROMOTE_CAMPAIGN_SHADOW
- HOLD_RAID_SHADOW
- HARVEST_RAID_SHADOW
- HOLD_CAMPAIGN_SHADOW
- INVALIDATE_MICRO_ONLY
- INVALIDATE_LEG_SHADOW
- INVALIDATE_CAMPAIGN_SHADOW
- SETTLEMENT_HOLD_SHADOW
- SETTLEMENT_EXIT_SHADOW

## Reference torture tests

The Router must explain these sessions correctly enough to be useful:

### 12:47-1:00 AM
One larger YES thesis should not become three independent campaigns merely because micro structure resets.

### 2:17 AM
A local YES fade should be explicitly counterterrain while Boss + Hand remain NO.

### 4:48-4:56 AM
Failure of a directional rail should first trigger reassessment / transition, not automatic opposite campaign.

### 5:30 AM
A short YES raid can coexist with a larger NO campaign thesis.

### 6:15-6:35 AM
Repeated YES attempts should share one parent thesis.
The later NO transition should become a new authority chapter only when evidence changes.
The same contract should not be re-declared as multiple campaigns.

### 7:00 AM rollover
Target dislocation must immediately update settlement gravity.
Old macro terrain may remain relevant, but cannot suppress the new contract's target geometry.

## Success metrics
Before any promotion to paper authority, compare shadow routing against V9.5A:

1. number of repeated same-contract CAMPAIGN declarations
2. RAID harvest value
3. correct-at-settlement trades killed by MICRO_BROKEN logic
4. number of C2 tactical trades correctly separated from campaign direction
5. time from rollover to target-gravity adaptation
6. ability to preserve profitable first-read edge
7. ability to retain known good trade #59
8. ability to avoid or relabel the 6:15-6:35 churn sequence

## Promotion standard
The Router remains shadow until:
- it survives multiple runs,
- it improves the frozen-run replay without simple memorization,
- it does not erase profitable tactical raids,
- it preserves the distinction between directional correctness and management quality,
- its rules can be stated in plain language before code.
