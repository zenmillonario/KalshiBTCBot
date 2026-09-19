# COMMANDERS LOG

## READ THIS FIRST
This is the canonical continuity document for Tachyos/Tachys. A future chat or coding session should read this file before proposing architecture changes.

Current frozen paper baseline:
- Version: V9.5A
- File: `tachys_v9_5a_price_freshness_active_treasury.py`
- Frozen run commit: `ee2db0c70ef0adeea173138a9e8c6c273cb7652a`
- Mode: PAPER ONLY

## Constitution
1. Before Tachyos asks whether to trade, it must know what shape it is inside.
2. Terrain first. Events second.
3. Micro Arc -> Leg -> Mountain -> Snake.
4. Macro context informs; it does not veto. A local structure can contradict and overturn the larger terrain when evidence is strong enough.
5. Anticipate early, or confirm late and buy the pullback. Never chase the middle.
6. A dead position may be abandoned. The battlefield is never abandoned.
7. Looking Glass is not a signal generator. It is Tachyos's temporal memory of the battlefield and the bridge from one terrain to the next.
8. The Emperor teaches the campaign. Tachy must eventually fight it alone.
9. Poetry can suggest the question; math must answer it.
10. No new detector should be added until the existing intelligence stack has been audited for the same information.

## Battlefield geometry
### Micro Arc -> Leg -> Mountain -> Snake
- A micro arc is the smallest EMA9/price curve.
- Several compatible micro arcs form a leg.
- Several legs form a mountain: ascent, crest/knitting, descent.
- Larger mountains across contracts form a snake/voyage around a slower center of gravity such as EMA30 or the settlement target.
- A micro-arc reset must not automatically reset parent-leg or campaign age.

### EMA30 terrain
EMA30 is a larger terrain reference. Across several contracts it can form shelves, steps, staircases, broad mountains, and rollover hinges. EMA9 creates smaller mountains around that terrain.

Repeated EMA30 approaches carry memory. A third or fourth failed reclaim is not equivalent to the first. The system must preserve gate history, gate fatigue, reclaim quality, and whether separation after each test is strengthening or deteriorating.

### Rail / Swirl / Dance of Dragons
When EMA9 and EMA30 are close, nearly parallel, and price alternates around them with repeated small mountains, Tachyos is in a different species of market than a clean campaign.

A Dance of Dragons can be:
- neutral compression,
- transitional entanglement while a larger EMA30 step turns,
- or an inclined directional rail when the EMAs stay separated enough and price rides the fast EMA.

Before calling a local swirl neutral, zoom out and inspect macro EMA30 curvature and target placement.

## Entry doctrine
Every entry must declare one of two doors:
- ANTICIPATION: enter before the obvious EMA30 event because the structure offers asymmetric price and a defined invalidation.
- RETEST: if the early entry was missed, wait for a genuine cross/reclaim/hold/separation and buy the pullback or retest.

Do not chase a mature middle/release merely because direction is correct.

## Permanent Commanders
Permanent Commanders remain on deck continuously. They do not compete for existence; they contribute simultaneous context.

### EMA Command
Owns:
- EMA9/EMA30 slope, gap, curvature, compression, separation
- ancestry across contracts
- EMA30 reclaim/rejection history
- rail/swirl state
- macro EMA30 shelves/steps
- gate fatigue and failed reclaim history

Existing intelligence includes `ema9_ancestry_state`, `v83_rejection_quality`, regime/handshake logic, EMA geometry, and orbital-clock telemetry.

### Arc Detective
Owns:
- current micro arc
- parent leg
- mountain phase
- arc/leg count and scale
- remaining capacity
- deterioration
- crest/trough progression
- weak regeneration and failed regeneration

Existing intelligence includes V9.3A geometry, V9.3B failed regeneration, V9.4I crest/fakeout, and V9.4J Price-Arc Phase.

### Looking Glass
Owns continuity through time:
- how the market arrived here
- transitions between terrains
- repeated gate tests
- prior failed attempts
- arc voyage / snake continuity
- whether a new event is a new chapter or merely a repetition of the old one

Looking Glass should consume Commander history, not compete with it.

### Orbit / Higher-Scale Geometry
Owns:
- tactical vs campaign EMA orbit
- higher-scale cycle age
- boss/theater persistence
- center drift
- local structure inside the larger snake

### Target / Settlement Command
Owns:
- target gravity
- target location relative to EMA/orbit center
- target migration
- rollover target dislocation
- remaining time
- settlement regime
- binary settlement asymmetry

The target is not just a horizontal line. A target placed at an extreme edge of the current orbit can create a settlement advantage even when local EMA geometry is balanced.

## Merit Officers / Specialists
Specialists earn the floor when the battlefield makes them relevant:
- Master of Borders / churn locator
- Dragon Dance
- Formation / handoff
- Bombe / thesis integrity
- Campaign Ledger / chapter identity
- Field Medic / rescue capacity
- Treasury
- King's Guard
- Second Spear / re-entry
- Twin Gate / repeated geometry
- Elasticity
- Chop Resolution
- Settlement proxy
- Reentry Watch

A specialist may become loud, but may not erase permanent Commander context.

## Execution engines
### Campaign Engine
Main autonomous directional engine. It can WAIT. It should not manufacture a campaign inside tangled terrain.

### Raid / Sniper Engine
Operates inside contested/tangled terrain only when a short-lived asymmetric attack exists. A raid is not a campaign and should have faster objectives and tighter invalidation.

### Settlement Engine
Takes priority late when target placement and binary settlement probability matter more than broader directional geometry.

Rule: tangled market + no exceptional raid = silence.

## Human Emperor
The Emperor Tape is training/forensic ground truth, not a permanent dependency.

The human strength observed in the 2026-09-18/19 session:
- contextual, multiscale geometry
- terrain continuity
- recognizing leg maturity
- seeing target placement relative to orbit gravity
- recognizing repeated EMA30 gate tests

The human weakness to guard against:
- overtrading when forcing examples
- attachment to a strong thesis
- using visual conviction without machine-only quote/elasticity evidence

Tachyos should add memory, measurement, vigilance, and dissent rather than simply imitate.

## Current audit headline
The V9.5A run indicates that Tachyos already possesses much of the missing intelligence. The primary issue is command/authority integration, not a shortage of detectors.

Examples:
- observer layers classified contested terrain and WAIT conditions while frozen execution still entered
- mission logic sometimes produced profitable harvest advice that had no management authority
- rollover/target context was observed but could remain subordinate to inherited direction
- micro-arc events can still reset the effective structural clock too aggressively

See `TACHYOS_PROCESS_AUDIT.md` for evidence and `EMPEROR_TAPE_2026-09-18_19.md` for the manual benchmark.

## Change-control rule
No new paper authority should be promoted without:
1. a frozen baseline,
2. explicit counterfactual logging,
3. evidence across more than one local example,
4. a clear owner in the Commander / Specialist / Engine hierarchy,
5. a documented contradiction policy.
