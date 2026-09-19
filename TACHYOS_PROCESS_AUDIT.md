# TACHYOS PROCESS AUDIT

## Scope
Frozen baseline audited:
- V9.5A
- commit `ee2db0c70ef0adeea173138a9e8c6c273cb7652a`
- run id family `A20260918_193335`
- paper only

This audit asks:
- What does Tachy already know that Tachy is not using?
- What is execution doing that contradicts what its own Commanders already know?

## V9.5A run result
Actual V9.5A run only:
- 68 trades
- 34 wins / 34 losses
- net paper P&L: -$9.706
- gross wins: +$90.414
- gross losses: -$100.120
- profit factor: 0.903

### Entry families
| Family | Trades | W-L | Net P&L | PF |
|---|---:|---:|---:|---:|
| CORE | 48 | 22-26 | -$32.193 | 0.603 |
| CONTINUATION_HANDOFF | 10 | 7-3 | +$17.600 | 2.642 |
| EARLY_IMPULSE_CORE | 9 | 4-5 | +$3.647 | 1.435 |
| EXHAUSTION_HANDOFF_FLIP | 1 | 1-0 | +$1.240 | n/a |

### Trade-intent families
| Intent | Trades | W-L | Net P&L | PF |
|---|---:|---:|---:|---:|
| ANTICIPATION | 42 | 20-22 | -$19.383 | 0.711 |
| ARC_RIDER | 12 | 8-4 | +$17.840 | 2.527 |
| EARLY_IMPULSE | 9 | 4-5 | +$3.647 | 1.435 |
| CORE | 4 | 1-3 | -$13.050 | 0.000 |
| EXHAUSTION_FLIP | 1 | 1-0 | +$1.240 | n/a |

### Setup labels
The surprising result is that the legacy `CONFIRMED` setup was the worst bucket:
- CONFIRMED: 26 trades, 11-15, -$38.141, PF 0.412
- HANDOFF: 11 trades, 8-3, +$18.840, PF 2.757
- EARLY: 22 trades, 11-11, +$5.948, PF 1.367
- IMPULSE: 9 trades, 4-5, +$3.647, PF 1.435

Interpretation: "confirmed" often means later and more expensive. Directional correctness is not enough if the move has already repriced.

## V9.5A authority audit
V9.5A promoted exactly two ideas.

### 1. Price Freshness entry gate
Rule:
- aligned with current leg
- leg age >= 90s
- premium >= 9 cents
- premium >= 25% relative to leg-start bid

Run:
- 315 entry-gate evaluations
- 77 blocked
- 238 allowed
- block rate: 24.4%

Counterfactual blocked-entry markouts:
- 15s average ROI: +0.07%
- 30s average ROI: +1.46%
- 60s average ROI: +4.44%
- 120s average ROI: +5.01%

Caution: these are short-horizon counterfactual markouts, not full managed-trade P&L. Still, the gate is not a simple success. It blocked many candidates that improved over the next one to two minutes. Price Freshness should be reevaluated as a context-sensitive timing tool, not assumed to be a universal late-leg veto.

### 2. Active Treasury exit
V9.4M `DEFEND_CANDIDATE` was promoted to paper-exit authority.

Run:
- 16 Active Treasury exits
- combined P&L: +$9.17

This layer was net helpful in the run. It is not the main source of current losses.

## Main loss / gain mechanisms
Selected exit reasons in the V9.5A run:
- `V95A_ACTIVE_TREASURY_DEFEND`: 16, +$9.17
- `CORE_SWIRL_SNIP_TP_22_5`: 11, +$30.378
- `EARLY_TAKE_PROFIT_50`: 5, +$29.660
- `EMA9_ARC_BROKEN`: 12, -$24.54
- `LATE_TARGET_INVALIDATION`: 5, -$23.20
- `KING_GUARD_FAILSAFE`: 2, -$20.90
- `EMERGENCY_STOP_60`: 2, -$15.49

The dominant unresolved problem is not lack of defense. It is entry-context and authority coherence.

## Process inventory

### Base execution authority
The active execution still descends from the older paper engine embedded in V9.4I, itself carrying the frozen V9.4A paper authority plus legacy Core / Early / Handoff / management logic.

This means many later modules can describe a richer battlefield but cannot stop or reshape legacy execution.

### V9.3A EMA Geometry
Status: observer only.
Knows:
- EMA arc sequence
- parent direction
- arc phase
- 3/6/9 curvature
- crest progression
- sequence continuity

Role: Arc Detective.

### V9.3B Failed Regeneration
Status: observer only.
State machine:
TREND -> EXHAUSTION -> REVERSAL_ARMED -> REGENERATION_TEST -> FAILED_REGENERATION -> RELEASE_SEEN -> CONFIRMED_RELEASE

Knows:
- parent arm aging
- weak opposite regeneration
- EMA30 not reclaimed
- release confirmation

Role: Arc Detective / Failed-Regeneration specialist.

### V9.4A King's Guard + Orbit
Authority: King's Guard changed paper management.
Observer:
- orbit field
- target/EMA anchor geometry
- territory

Role: management specialist plus Orbit context.

### V9.4B Shadow Lab / Waypoint
Status: shadow.
Knows:
- management alternatives
- entry value/risk
- waypoint / settlement-proxy context
- edge follow-through

Role: research and Target/Settlement support.

### V9.4C Temporal Loom / Target Tube
Status: shadow.
Knows:
- target spine / target tube
- previous/active target relation
- tube escape / transit / node capture

Role: Target/Settlement Command.

### V9.4D Trade Topology / Formation Handoff
Status: shadow.
Knows:
- formation geometry
- compression / release / breakout / failure
- quote topology
- entry/profit topology
- formation continuity across rollover

Role: Formation specialist and handoff continuity.

### V9.4E King's Council
Status: shadow.
Knows:
- stable regime and handshake
- authority side
- pulse / heartbeat
- council votes and dissent
- high-confluence value / escape conditions

Role: War Council / Commander fusion.

### V9.4F Rollover War Council
Status: shadow.
Knows:
- T-30 / T-9 / T-3 rollover state
- target event
- gap motion
- formation
- failed reclaim count
- target tube
- fresh-score side
- first-price / rollover remap

Role: Target/Settlement + Rollover specialist.

### V9.4G Master of Borders / Trade Missions
Status: shadow.
Knows:
- CLEAR_TERRITORY / CHURN_ACTIVE / CHURN_RESOLVING / BOUNDARY_RELEASE
- metronome/compression/mixed churn
- box position
- RAID / SCOUT / ATTACK / CAMPAIGN mission identity
- campaign counterwave behavior

Role: terrain specialist and execution-mode selector.

### V9.4H Boss / Orbital Clock / Scorekeeper
Status: shadow.
Knows:
- persistent theater/boss above temporary Hand flips
- tactical and campaign EMA orbit
- cycle age, contracts in cycle, center drift
- rearm quality

Role: higher-scale Commander.

### V9.4I Rearm / Crest / Dual-Scale Orbit
Status: additions shadow; frozen paper engine remains authority.
Knows:
- 3-crest + fakeout pattern
- opposite release
- dual-scale orbit context
- earlier Council/Borders/Boss stack

Role: higher-scale geometry + specialist.

### V9.4J Looking Glass / Arc Voyage
Status: shadow.
Knows:
- Price-Arc Phase: LAUNCH, EXTENSION, EXTENSION_SLOW, RETURN_TO_EMA9, CROSS_RESET, PEAK_TROUGH_BUILD
- remaining-capacity estimate
- Entry Timing Shadow
- Arc Echo / Grammar
- Arc Voyage: LAUNCH -> BODY -> RELEASE
- battlefield class
- temporal scenario rehearsal

Role: permanent temporal Commander.

### V9.4K Field Medic / Flexible Cage / Dragon Dance
Status: shadow.
Knows:
- recoverable wound vs dead thesis
- flexible cage / rescue geometry
- target migration
- Dance of Dragons
- chop resolution
- tide clock
- reentry watch

Role: Medic and contested-terrain specialists.

### V9.4L Second Spear / Settlement Elasticity
Status: not imported by M or V9.5A.
Reason: old Spear v1 was too permissive and settlement-elasticity logging was too large.
Role: historical experiment only.

### V9.4M Battle Plan / Treasury
Status: shadow.
Knows:
- Treasury defense
- Bombe thesis integrity
- Campaign Ledger / chapter identity
- Medic qualifier
- Second Spear V2
- arc legs
- Twin Peak / Twin Valley -> EMA30 gate
- Elasticity Lite

Role: specialists and treasury.

### V9.5A
Authority:
- Price Freshness can block entries
- Active Treasury can close paper trades
Everything else above remains largely advisory.

## Evidence of command/authority contradiction

### Case A: 6:20 AM ET, trade #55 YES
At entry, the mission layer classified:
- mission = RAID
- mission reason = CONTESTED_TERRITORY
- Hand regime = DOWN_FORMING
- Hand authority = NO
- Borders = CHURN_ACTIVE
- churn type = COMPRESSION_CHURN
- War directive = WAIT_CONFIRMATION / NO

Frozen execution still entered YES.

This is not necessarily proof YES was wrong. It is proof the architecture allowed execution to act without resolving a direct contradiction between its own battlefield assessment and the entry engine.

### Case B: 6:22 AM ET, trade #56 YES
Mission layer again classified RAID / CONTESTED_TERRITORY with Hand authority NO.

During the trade, the mission observer saw the paper bid around +16.7% ROI and repeatedly emitted `HARVEST_EDGE_SHADOW`. The real manager did not use that advice. The position later exited at -33.3% via `V92_STRUCTURE_BROKEN`.

This is direct evidence that Tachyos already had useful management intelligence that lacked authority.

### Case C: 6:27 AM ET, trade #58 NO
The mission layer classified CAMPAIGN / AUTHORITY_ALIGNED.
The trade reached roughly +18.96% MFE, then exited about -41.56% via `KING_GUARD_FAILSAFE`.

Active Treasury requires a proven threshold at/above the configured tier; this trade stopped just below the 20% proof level and therefore fell through a threshold cliff.

Audit item: test tiered proof/defense rather than a single hard boundary. An 18% research tier is worth testing because it is close to the observed failure and also fits the project's 3/6/9 parameter preference, but it must earn promotion from data.

### Case D: 7:00 AM ET rollover
The Emperor read the new contract as YES-favorable because rollover occurred inside a deep lower extension, placing the new target near the lower edge of the wider EMA orbit.

The War Council at T-30/T-9/T-3 still carried:
- DOWN_DECAY
- NO authority
- CHOP_QUARANTINE
- falling-channel / macro DOWN
- target accepted NO

At the rollover remap, the new target moved to roughly 81192.74 while BTC was roughly 81195.19. The target relocation was recognized in telemetry, but the inherited NO battlefield still dominated.

By ~7:14 AM ET, the War Council had moved to:
- UP_FORMING
- YES authority
- target accepted YES
- whispers = FAILED_REGENERATION with release side YES
- target roughly $87 below price

This suggests the system recognized the new terrain later, but did not treat rollover target dislocation as a first-class immediate reset of settlement gravity.

### Case E: 6:31 AM ET NO
The Emperor entered NO on repeated multi-contract EMA30 failure and EMA9 remaining below EMA30.
Tachyos entered NO around 6:30:21 and harvested +50% by 6:35:50.

This is a positive alignment case. The system can trade well when the terrain, handoff, and direction are coherent.

## Core architectural finding
Tachyos is not primarily blind. It is fragmented.

The stack contains:
- terrain classification
- stable regime memory
- repeated reclaim memory
- mountain/arc geometry
- higher-scale orbit
- target tube
- rollover remap
- raid/campaign mission labels
- temporal voyage
- rescue / treasury logic

But these layers were built mostly as observers around frozen execution.

The next architecture should therefore be an authority-integration redesign, not another detector layer.

## Proposed redesign questions — not yet implementation
1. Can we create one persistent Battlefield State object consumed by every engine?
2. Can parent-leg / mountain / campaign age survive micro-arc resets?
3. Can Looking Glass become the temporal owner that reconciles prior terrain with current transition?
4. Can Trade Mission become the explicit execution-mode selector: WAIT / RAID / CAMPAIGN / SETTLEMENT?
5. Can contradictory Commander evidence require an explicit override rather than being silently ignored?
6. Can rollover target dislocation recalculate settlement gravity immediately?
7. Can management distinguish ANTICIPATION from RETEST and RAID from CAMPAIGN?
8. Can Treasury proof become tiered and structural rather than a cliff at a single ROI?
9. Can Price Freshness become a scoring/input feature rather than a blunt veto where the short-horizon counterfactual evidence does not support universal blocking?

## Audit policy
Do not build V9.5B until:
- Emperor Tape replay is completed,
- observer-vs-authority contradictions are mapped,
- missing large telemetry is requested only if a specific unresolved question needs it,
- the new command hierarchy is documented.
