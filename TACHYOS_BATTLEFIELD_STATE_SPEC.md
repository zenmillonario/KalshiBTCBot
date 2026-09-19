# TACHYOS BATTLEFIELD STATE SPEC

## Purpose
This document defines the proposed canonical state model for the next Tachyos architecture.

It is a design specification only.
It does NOT grant new paper authority.

The core goal is to stop independent observers from describing one battlefield while an older execution engine acts on a different one.

## First principle
Before Tachyos asks whether to trade, it must know:
1. what terrain species it is inside,
2. what scale it is acting on,
3. which campaign / mountain / leg / micro-arc it belongs to,
4. what the settlement target is doing,
5. what mission is permitted,
6. what contradictions exist.

## Canonical object
Every meaningful market update should produce one immutable `BattlefieldState`.

Conceptual schema:

```
BattlefieldState
  identity
  market_clock
  target_settlement
  ema_terrain
  arc_structure
  temporal_memory
  higher_scale
  contested_terrain
  commander_views
  contradiction_ledger
  mission_state
  execution_permission
  position_state
```

The state object should be passed to execution.
Execution should not independently reconstruct battlefield meaning from isolated legacy functions.

---

# 1. Identity

Fields:
- run_id
- session_id
- ticker
- contract_id
- timestamp
- contract_open_ts
- contract_close_ts
- seconds_left
- rollover_generation

Rollover rule:
- contract-specific fields reset
- BTC terrain does NOT reset
- EMA ancestry does NOT reset
- gate history does NOT reset
- Looking Glass history does NOT reset
- parent mountain / campaign does NOT reset merely because ticker changed

---

# 2. Target / Settlement Command

Owner:
**Target / Settlement Commander**

Existing sources:
- active target
- Target Tube / Spine
- target migration
- settlement proxy
- Rollover War Council
- expiry observer
- target distance / target crossings

Required fields:
- target_price
- target_distance
- target_distance_norm60
- target_to_ema9
- target_to_ema30
- target_to_ema_center
- target_orbit_percentile
- target_gravity_side
- target_dislocation_score
- target_migration_state
- target_capture_state
- seconds_left
- settlement_phase
- rollover_target_age_sec

### Target gravity
Tachyos must measure where the target sits relative to the current local orbit, not only whether price is above or below it.

Example:
If rollover occurs during an extreme lower excursion and the new target is near the lower boundary while EMA9/EMA30 gravity remains materially above it, the target can create YES settlement asymmetry even in a locally balanced Dance of Dragons.

### Immediate rollover recomputation
A new target must trigger an immediate settlement-state recomputation.

The previous contract's target narrative may inform history, but it cannot dominate the new contract's binary geometry.

---

# 3. EMA Command

Owner:
**EMA Commander**

Existing sources:
- `ema9_ancestry_state`
- `v83_rejection_quality`
- EMA9/EMA30 series
- V9.3 geometry
- regime handshake
- orbital clock
- failed reclaim counts

Required fields:
- ema9
- ema30
- ema9_slope
- ema30_slope
- ema9_curvature
- ema_gap
- ema_gap_norm60
- ema_gap_velocity
- ema_relation
- ancestry_side
- ancestry_age_sec
- gate_side
- gate_test_count
- gate_test_history
- gate_reclaim_quality
- gate_rejection_quality
- gate_fatigue_score
- ema30_macro_shape
- ema30_center_drift
- rail_state
- swirl_state

### Gate history
EMA30 is a gate with memory.

A first approach, third approach, and fifth approach are not equivalent.

Each test should preserve:
- timestamp
- side approached from
- penetration depth
- whether price crossed
- whether EMA9 crossed
- maximum separation after test
- time to rejection/reclaim
- result

### Macro EMA30 shape
Track shelves / staircase / broad crest / broad trough / rolling hinge over several contracts.

The system should be able to say:
- local EMA9 up leg inside macro EMA30 down step
- local swirl at macro EMA30 crest
- clean directional rail
- true flat neutral rail

---

# 4. Arc Detective

Owner:
**Arc Detective**

Existing sources:
- V9.3A EMA geometry
- V9.3B failed regeneration
- V9.4I crest/fakeout
- V9.4J Price-Arc Phase
- arc echo / grammar

Hierarchy:
```
micro_arc_id
  -> leg_id
      -> mountain_id
          -> campaign_id / snake_id
```

Required fields:
- micro_arc_id
- micro_arc_direction
- micro_arc_phase
- micro_arc_age
- leg_id
- leg_direction
- leg_age
- leg_progress
- mountain_id
- mountain_phase
- mountain_age
- mountain_leg_count
- mountain_deterioration
- parent_campaign_id
- parent_campaign_direction
- parent_campaign_age
- remaining_capacity_local
- remaining_capacity_parent
- crest_progression
- regeneration_state
- failed_regeneration_state

### Critical fix
A new micro arc must NOT automatically create a young parent leg.

The 2026-09-18/19 audit repeatedly showed micro resets inside mature campaigns.

Parent age survives child resets unless a structural authority transfer is confirmed.

---

# 5. Looking Glass — temporal memory

Owner:
**Looking Glass Commander**

Existing sources:
- Arc Voyage
- Arc Echo
- Arc Grammar
- campaign ledger
- boss history
- prior gate attempts
- rollover rhythm
- reentry watches

Looking Glass answers:
- How did we get here?
- Is this actually a new chapter?
- Has this exact gate already been tested?
- Did the last three attempts fail the same way?
- Is the market transitioning from terrain A to terrain B?
- Is the current signal a repetition, continuation, or genuine structural reset?

Required fields:
- previous_terrain_species
- current_terrain_species
- transition_age_sec
- transition_reason
- chapter_id
- chapter_state
- repeated_signal_count
- repeated_failure_count
- prior_gate_failures
- voyage_id
- voyage_phase
- voyage_maturity
- prior_mission
- prior_position_outcome
- time_since_last_exit
- battlefield_persistence_after_exit

### Rule
Looking Glass owns continuity through time.

It does not place orders.

It supplies the temporal context every engine must read.

---

# 6. Higher-scale Orbit / Theater

Owner:
**Orbit / Higher-Scale Commander**

Existing sources:
- Boss Columns
- Orbital Clock
- tactical/campaign orbit cycles
- center drift
- multi-timeframe observer

Required fields:
- boss_id
- boss_side
- boss_state
- tactical_orbit_id
- tactical_orbit_state
- tactical_orbit_age
- campaign_orbit_id
- campaign_orbit_state
- campaign_orbit_age
- orbit_center_drift
- 5m_regime
- 30m_regime
- macro_context_side
- macro_context_strength

Rule:
Macro context informs; it does not veto.

A local break can defeat the Boss, but it must be recorded as an authority transfer, not silently inferred from one micro event.

---

# 7. Contested Terrain / Borders

Owners:
- Master of Borders
- Dragon Dance specialist
- Formation specialist

Existing sources:
- V9.4G Master of Borders
- V9.4K Dragon Dance
- formation_state
- chop-resolution
- flexible cage

Required fields:
- terrain_species
- churn_state
- churn_type
- dragon_state
- rail_state
- box_low
- box_high
- box_location
- compression_score
- formation
- formation_maturity
- local_regime
- release_candidate_side
- release_quality

Proposed terrain species vocabulary:
- CLEAN_CAMPAIGN
- DIRECTIONAL_RAIL
- DRAGON_DANCE
- COMPRESSION_STORM
- TRANSITION_HINGE
- RELEASE
- LOCAL_FOG
- SETTLEMENT_BATTLE

These names should be calibrated from data before becoming authority.

---

# 8. Permanent Commander views

Every Commander publishes a side and confidence without directly placing a trade.

Conceptual:

```
commander_views = {
  ema:        {side, confidence, reason},
  arc:        {side, confidence, reason},
  looking:    {side, confidence, reason},
  orbit:      {side, confidence, reason},
  settlement: {side, confidence, reason}
}
```

A Commander may publish:
- YES
- NO
- NEUTRAL
- TRANSITION
- UNKNOWN

No single Commander is "priority #1" forever.

All remain present.

---

# 9. Contradiction Ledger

This is the missing constitutional layer.

Before any entry, Tachyos records:
- proposed side
- proposed mission
- which Commanders agree
- which Commanders disagree
- whether disagreement is stale or current
- whether the trade is explicitly counterterrain
- what evidence justifies the contradiction

Required fields:
- proposed_side
- supporting_commanders
- dissenting_commanders
- contradiction_count
- contradiction_weight
- override_reason
- override_owner
- override_expiry

### Rule: no silent override
A local EMA9 event may not quietly overrule both EMA terrain and Looking Glass continuity.

If it does, the trade must be explicitly labeled a counterterrain RAID with a narrow objective and invalidation.

It may not masquerade as a CAMPAIGN.

### Authority-transfer rule
To reverse campaign direction, require multiple categories of evidence, for example:
- gate reclaim/rejection change,
- parent leg break,
- Hand/regime change,
- persistent separation,
- terrain release,
- target/settlement shift.

Exact thresholds remain research questions.

---

# 10. Mission State

Owner:
**Mission Selector**

Allowed missions:
- WAIT
- SCOUT
- RAID
- CAMPAIGN
- SETTLEMENT

The mission is selected BEFORE execution.

### WAIT
No trade.
Used when:
- tangled terrain with no exceptional raid,
- unresolved contradiction,
- target battle without settlement edge,
- stale/mature entry with no retest.

### SCOUT
Research-sized concept or paper-only probe.
Not a normal production mission.

### RAID
Short-lived asymmetric attack inside contested terrain.
Characteristics:
- small time budget
- quick harvest objective
- fast structural invalidation
- may oppose macro terrain
- cannot silently become a campaign

### CAMPAIGN
Directional parent thesis.
Characteristics:
- persistent battlefield memory
- can survive ordinary counterwaves
- uses parent-leg / mountain invalidation
- exits do not erase campaign state

### SETTLEMENT
Binary target/time mission.
Characteristics:
- target gravity dominates
- time remaining is first-class
- macro trend becomes context rather than primary objective

---

# 11. Entry Mode

Independent of mission:
- ANTICIPATION
- RETEST

### ANTICIPATION
Entered before full confirmation.

Required:
- explicit structural thesis
- explicit invalidation
- parent context
- favorable price asymmetry

Management:
Normal oscillation is not enough to kill the trade.

### RETEST
Entered after:
- cross/reclaim,
- hold,
- separation,
- pullback/retest.

Management can be tighter because confirmation has already been paid for.

Rule:
**Anticipate early, or confirm late and buy the pullback. Never chase the middle.**

---

# 12. Management by mission

The same stop logic should not manage every trade.

## RAID
- quick harvest
- short leash
- no heroic recovery
- Field Medic mostly stands down

## CAMPAIGN
- counterwaves allowed
- parent structure controls invalidation
- Treasury protects proven progress
- Looking Glass remains active after exits

## ANTICIPATION
- thesis invalidation > short-term mark-to-market discomfort
- fast fail only when the anticipated structural premise is disproven

## RETEST
- failed retest can invalidate quickly

## SETTLEMENT
- target cushion
- target gravity
- time
- quote elasticity
- crossing risk
dominate management.

---

# 13. Treasury / proof

The V9.5A audit showed Active Treasury was net positive.

Keep Treasury conceptually separate from entry selection.

Current issue:
The proof threshold can create a cliff.

Example:
Trade #58 reached about +19% MFE but missed the 20% proven tier and later lost heavily.

Future research:
- tiered proof
- structural proof
- proof based on MFE + terrain quality

Possible 18% research tier may be tested because it is near the observed cliff and fits the project's 3/6/9 preference, but it must not be promoted merely for numerological elegance.

---

# 14. Price Freshness

V9.5A's hard Price Freshness gate should remain under audit.

The blocked-candidate 60s/120s counterfactuals were positive on average in this run.

Proposed role:
Price Freshness becomes an input to:
- mission selection
- chase risk
- sizing
- retest preference

It should not automatically be a universal veto until evidence supports that role.

---

# 15. State persistence rules

### A position exit does NOT reset:
- campaign_id
- mountain_id
- gate history
- Looking Glass chapter
- boss/theater
- target history

### Contract rollover does NOT reset:
- EMA ancestry
- macro EMA shape
- gate history
- voyage
- campaign state

### Contract rollover DOES reset/recompute:
- target_price
- target gravity
- target dislocation
- settlement phase
- contract-specific quote history

### Genuine authority transfer may reset:
- parent campaign direction
- boss
- chapter
- mission permissions

---

# 16. Proposed execution pipeline

```
market data
  -> observer updates
  -> BattlefieldState build
  -> Commander views
  -> contradiction ledger
  -> mission selector
  -> entry-mode selector
  -> permission gate
  -> paper execution
  -> mission-specific management
  -> outcome logging
  -> Looking Glass continuity update
```

The execution engine should receive one approved state object.

It should no longer independently call a sequence of legacy yes/no gates that can contradict the state.

---

# 17. What NOT to do next

Do not:
- add another standalone detector,
- promote all shadow warnings to vetoes,
- assume "TIMING_OK" is good because of its name,
- assume "CONFIRMED" is safer because of its name,
- use one run to optimize dozens of thresholds,
- erase profitable countertrend raids merely because macro terrain disagrees.

The audit showed that names and intended semantics are not always aligned with empirical outcomes.

---

# 18. Next implementation research

Before coding authority:
1. Build an offline BattlefieldState reconstruction for the frozen V9.5A run.
2. Populate it from existing logs.
3. Replay trades #24-#68 and the Emperor Tape.
4. Tag each historical entry with:
   - terrain species
   - parent campaign
   - mission
   - entry mode
   - commander support/dissent
   - target gravity
5. Measure which rules would have reduced repeated losses without deleting known good trades such as #59.
6. Only then write the next paper-trading version.
