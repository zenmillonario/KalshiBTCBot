# TACHYOS ENTRY AUTHORITY ROUTER V1

Status: DESIGN / REPLAY FIRST  
Trading authority: NONE YET  
Control: V9.5A remains frozen  
Purpose: replace "signal qualifies -> enter" with "candidate -> battlefield state -> authority decision".

## Why this exists

V9.5A still inherits the old trading engine. The research stack can describe a candidate as:

- CROSS_RESET / WAIT_NEW_ARC
- low remaining capacity
- MIXED_STORM / COMPRESSION_STORM / METRONOME_STORM
- Boss and Hand opposed
- War Council waiting or quarantining
- Dragon swirl / entanglement
- tactical/campaign orbit context

and the legacy engine can still enter.

The repeated failure is not lack of observation. It is that the wrong layer has the keys.

V1 changes the architecture:

1. Legacy signal logic becomes a proposal generator.
2. Existing research layers become evidence providers.
3. Entry Authority Router becomes the single paper-entry governor.
4. No paper position is created unless Router returns an entry-permitted state.

## Core doctrine

A dying old leg does not imply a newborn opposite leg.

A new detector leg is not automatically a young market move.

Anticipate early, or confirm late and buy the pullback. Never chase the middle.

A tactical counterwave may exist inside an intact parent campaign.

Messy terrain suspends directional authority until the structure resolves; it does not permanently ban the contract.

## Integration point

The current proposal path ends at:

`core.print_signal(...) -> core.paper_enter(...)`

V9.5A wraps `core.paper_enter` for price freshness. V1 will install after the frozen V9.5A stack and become the final authority doorway.

The legacy engine may continue to generate candidates. The Router decides whether the candidate reaches the inherited `paper_enter`.

There must be no second path that creates a paper position.

## Existing intelligence to consume

No new detector is required for V1.

### Price/arc
From V9.4J snapshot:
- arc_id
- arc_direction
- arc_age_sec
- price_arc_phase
- remaining_capacity
- signed_sep_norm60
- sep_velocity_6s
- price_velocity_6s
- battlefield_class
- zoom_mode
- target_distance
- target_distance_norm60
- boss_side
- hand_side
- territory_state
- churn_type
- snake_phase / snake_maturity
- orbit

### War / authority
From V9.4I:
- v94e_latest_regime -> Hand authority
- v94h_boss -> Boss side/state
- v94f_latest_war -> War directive / directive_side
- v94f_latest_chop -> chop state / lean
- v94g_latest_border -> border / churn / boundary release
- failed-regeneration release
- crest release
- Scorekeeper rearm evidence

### Orbit
From v94h_orbit_state["latest"]:
- phase_deg
- unwrapped_phase_deg
- phase_delta_deg
- gap
- gap_velocity
- tactical_cycle_state / age / contracts
- campaign_cycle_state / age / contracts
- macro_cycle_state / age
- center_drift_proxy

V1 may log these immediately. They do not all need authority on day one.

### V9.5A
- existing price-freshness result
- candidate side/ask/intent
- existing active Treasury remains unchanged during entry-router research

## State machine

The Router uses market states, not only YES/NO.

### NO_TRADE
Meaning:
The battlefield is not sufficiently resolved for a directional entry.

Typical causes:
- no reliable structural context
- contradictory state with no release evidence
- explicit chop quarantine without an authorized release
- repeated candidate spraying inside unresolved terrain

Authority:
BLOCK new directional entry.

### HINGE_WAIT
Meaning:
Old geometry has broken or crossed, but a new leg has not been established.

Strong evidence:
- price_arc_phase == CROSS_RESET
- WAIT_NEW_ARC_SHADOW equivalent
- old arc died / EMA relationship reset
- radius/gap compression around the center
- Dragon swirl/entanglement
- Boss/Hand/War do not yet support the proposed side
- no boundary / failed-regen / crest / fresh-hand release for the proposed side

Authority:
BLOCK entry for now.
Continue observing the same candidate thesis.
Do not convert "old leg died" into "opposite leg born."

### RELEASE_ARMED
Meaning:
The hinge is resolving and a directional leg may be forming, but economic entry permission has not yet been earned.

Evidence can include:
- new arc begins in candidate direction
- EMA gap starts separating
- orbit phase advances coherently
- border release
- failed-regeneration release
- crest release
- Hand transfer
- repeated EMA30 rejection supports the side
- target side begins holding

Authority:
WAIT.
Candidate remains alive.
Look for either early-release qualification or pullback.

### EARLY_ENTRY_OPEN
Meaning:
A fresh release is young in trajectory terms, not merely young by detector ID.

Authority:
ALLOW inherited paper entry.

Important:
Detector leg_age alone cannot establish this state.

### PULLBACK_WAIT
Meaning:
Direction may be correct but the candidate is returning toward EMA9 / value after a confirmed release.

Evidence:
- RETURN_TO_EMA9
- direction still structurally authorized
- no parent invalidation

Authority:
WAIT for reaction / hold / rejection.
Do not buy the middle before the pullback resolves.

### PULLBACK_ENTRY_OPEN
Meaning:
Confirmed directional release has pulled back and re-established the side at improved economics.

Authority:
ALLOW inherited paper entry.

### MID_PLAY_CLOSED
Meaning:
Direction may still be correct, but the useful entry window has been substantially consumed.

Evidence:
- low remaining arc capacity
- substantial trajectory age
- expensive Kalshi repricing
- move already displaced through target/EMA geometry
- no fresh reset/release chapter

Authority:
BLOCK new entry.
Existing position management is unaffected.

### LEG_MATURE
Meaning:
Existing leg is near completion or entering a hinge.

Authority:
No new same-direction entry.
Manage existing position.
Prepare HINGE_WAIT.

### TACTICAL_COUNTERWAVE_ONLY
Meaning:
Candidate direction opposes intact parent authority but a legitimate tactical wave may be forming.

Examples:
- candidate opposes Boss/campaign
- candidate may agree with local arc / fresh release
- tactical orbit reverses while campaign orbit remains intact

Authority:
Not a campaign.
If later promoted to paper authority, must use tactical sizing/manager/expectations.
V1 replay must study this separately before live sizing changes.

## Authority hierarchy

The Router should answer questions in this order:

1. Is the battlefield understood enough to trade?
2. Is this a hinge or unresolved transition?
3. Is the proposed side a parent continuation or tactical counterwave?
4. Has a real release occurred?
5. Is the economic entry window still open?
6. Is this early release or pullback entry?
7. Which manager should own the resulting trade?

Direction is not question #1.

## Context agreement

For a candidate side S, define contextual authorities:

- Boss side
- Hand side
- War directive side

Agreement count is descriptive, not a vote-based veto by itself.

The latest run demonstrated that a candidate can be in CROSS_RESET with very low remaining capacity while all three larger authorities oppose it. That should be treated as unresolved/counterwave evidence, not automatic reversal permission.

Historical replay must use session/time-safe joins before any threshold is promoted.

## Explicitly forbidden shortcuts

V1 must NOT implement any of these as standalone rules:

- "WAIT_NEW_ARC is always bad"
- "low remaining capacity is always bad"
- "counter-leg is always bad"
- "storm is always no-trade"
- "Boss/Hand disagreement is an automatic veto"
- "leg_age == 0 means the market move is newborn"
- one-trade-per-contract
- contract rollover resets battlefield ancestry

These were contradicted by prior runs or project doctrine.

## Detector age vs trajectory age

V1 must distinguish:

- detector_leg_age: when Tachys labeled/reset the current leg object
- trajectory_age: when the actual directional displacement/release began

A freshly-created leg ID can occur late in a larger move.

Trajectory age should eventually use pre-existing telemetry such as:
- prior arc ancestry
- gap velocity and phase
- center drift
- target/EMA traversal
- prior turning point / release event
- orbit cycle continuity

Until trajectory age is reliable, a new leg ID must not automatically earn EARLY_ENTRY_OPEN.

## Entry provenance -> manager ownership

Router output must preserve provenance.

Examples:
- ARC_RIDER -> ARC_RIDER manager
- ANTICIPATION -> transition/anticipation manager
- RAID -> RAID manager
- earned CAMPAIGN -> parent/campaign manager
- TACTICAL_COUNTERWAVE_ONLY -> tactical manager

The manager must not forget why the trade was allowed.

## Logging

New log:
`tachys_entry_authority_router_v1.csv`

Minimum fields:
- timestamp
- run_id / session_id
- ticker
- candidate_id
- side
- ask
- trade_intent
- strategy
- router_state
- router_action
- reason
- price_arc_phase
- arc_direction
- detector_leg_age
- trajectory_age_estimate
- remaining_capacity
- battlefield_class
- dragon_state
- cage_state
- boss_side
- hand_side
- war_directive
- war_side
- authority_agreement_count
- territory_state
- churn_type
- target_distance
- seconds_left
- orbit_phase_deg
- orbit_unwrapped_phase_deg
- orbit_gap
- orbit_gap_velocity
- tactical_cycle_state
- campaign_cycle_state
- center_drift_proxy
- inherited_v95a_gate_action
- inherited_v95a_gate_reason
- actual_entered
- eventual_exit_reason
- eventual_pnl
- settlement_result
- settlement_correct

## Replay-first implementation plan

Phase 1 — session-safe feature reconstruction
- Join by timestamp + ticker + side + ask, not trade_id alone.
- Preserve run/session boundaries.
- Build one row per actual entry candidate.
- Attach eventual paper outcome and settlement.
- Do not double-count duplicate archives.

Phase 2 — state reconstruction
- Recreate HINGE_WAIT / RELEASE_ARMED / PULLBACK_WAIT / MID_PLAY_CLOSED / TACTICAL_COUNTERWAVE_ONLY labels from existing telemetry.
- No P&L optimization yet.

Phase 3 — counterfactual router
For each entry:
- current engine: ENTER
- router: ENTER / WAIT / BLOCK / TACTICAL_ONLY
Compare:
- trade count
- realized P&L removed/retained
- settlement correctness
- MFE/MAE
- right-thesis losses
- wrong-thesis losses
- opportunity cost of blocked entries
- later same-contract opportunities after a WAIT

Phase 4 — robustness
Run the exact same rules across independent archived runs.
No per-run retuning.

Phase 5 — paper authority
Only after replay:
- create V10 paper launcher
- import frozen V9.5A stack
- install Router last
- legacy `paper_enter` called only for Router ENTER states
- all WAIT/BLOCK candidates logged and counterfactually followed

## Initial research hypotheses

These are hypotheses, not authority rules:

H1. CROSS_RESET with weak contextual support is a HINGE, not an automatic reversal.

H2. Counterwaves that oppose intact Boss/Hand/War need explicit release evidence before entry.

H3. A low-capacity state is mostly an economic/timing warning; it becomes dangerous when combined with unresolved transition or stale/counter authority.

H4. Fresh detector leg IDs can occur late in trajectory; detector age alone creates false "young leg" permission.

H5. Some profitable counterwaves are tactical moves inside intact campaigns; blocking all counterwaves would destroy real edge.

H6. The best trade permission comes from path state (release/pullback) rather than a static signal score.

## Control discipline

V9.5A remains unchanged and archived as control.

No V9.5B entry patch.

No new Commander.

No new indicator unless replay proves an existing field is insufficient.

The purpose of V1 is governance: make existing intelligence operational.
