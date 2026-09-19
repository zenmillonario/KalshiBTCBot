# EMPEROR REPLAY AUDIT — V9.5A

## Scope
This replay compares the manual Emperor Tape from the overnight 2026-09-18/19 session with the frozen V9.5A telemetry.

Frozen baseline:
- V9.5A run commit: `ee2db0c70ef0adeea173138a9e8c6c273cb7652a`
- paper only

This is not an attempt to prove the human or Tachyos "right." The purpose is to identify:
- shared perception,
- temporal lead/lag,
- command contradictions,
- horizon confusion,
- overtrading,
- and machine-only strengths.

## High-level replay result
A heuristic nearest-entry match was run against the manual ENTER/ADD markers.

Caution: these are not statistically independent because a human ADD can map to the same Tachy trade and some manual campaigns span multiple bot entries.

Within 5 minutes:
- 15 manual markers had a nearby Tachy trade
- 13 were the same side
- 2 were opposite

Within 10 minutes:
- 21 had a nearby Tachy trade
- 18 were the same side
- 3 were opposite
- 2 had no nearby Tachy entry

The central message is therefore NOT "Tachy cannot see direction."

It is:
**Tachy often sees the same direction, but does not preserve the same campaign identity, timing horizon, or terrain memory.**

## Replay Case 1 — 11:42 PM to 11:55 PM: transition lag
Emperor:
- 11:42 YES
- 11:47 NO after failed EMA30 break / weak greens
- 11:52 ADD NO
- NO campaign later explicitly confirmed a win

Tachyos:
- #24 YES at 11:47:18, about five minutes after the Emperor's YES and almost exactly when the Emperor had already flipped to NO
- #24 lost -$0.32 via `EMA9_ARC_BROKEN`
- #25 NO at 11:51:04, about four minutes after the Emperor's NO
- #25 lost -$8.00 via `LATE_TARGET_INVALIDATION`

Entry-timing shadow on #24 already said:
- `LOW_REMAINING_CAPACITY_SHADOW`
- phase = PEAK_TROUGH_BUILD
- mission = SCOUT / UNRESOLVED_MANDATE

Interpretation:
The bot was late to both sides of the transition. The human read the turn while Tachy was still executing the prior leg. This is a temporal-continuity / transition problem, not simply a direction detector problem.

## Replay Case 2 — 12:47 AM onward: one human campaign, multiple bot attempts
Emperor:
- 12:47 YES from a knitted bottom
- held through return toward EMA30 and target noise

Tachyos:
- #29 YES at 12:51:01, lost -$0.90 after 7 seconds
- #30 YES at 12:53:25, lost -$0.54
- #31 YES at 12:55:31, later settled +$6.069

The first two bot entries were classified as:
- COMPRESSION_STORM
- RAID / CONTESTED_TERRITORY
- `WAIT_EMA9_REACTION_SHADOW`

Interpretation:
The human expressed one larger thesis. Tachy expressed the same broad directional idea as a series of short-lived independent attempts. This is the first clear sign that micro invalidation is repeatedly killing a parent thesis that later proves viable.

## Replay Case 3 — 1:02 AM: battlefield continuity after profit
Emperor:
- 1:02 YES
- continued to hold
- 1:14 YES WIN

Tachyos:
- had already completed a profitable YES #31 at 1:00
- did not establish the comparable 1:02 continuation campaign

Interpretation:
This supports the charter:
**A position may end; the battlefield does not.**
A profitable exit should not erase the parent leg / mountain / campaign state.

## Replay Case 4 — 2:17 AM: micro signal overruled both larger commanders
Emperor:
- 2:10 NO
- 2:17 ADD/HOLD NO as EMA separation resumed down

Tachyos:
- #40 entered YES at 2:17:06
- lost -$4.20 via `EMA9_ARC_BROKEN`

At Tachy's entry, Looking Glass / entry timing reported:
- Boss = NO
- Hand = NO
- mission = RAID / CONTESTED_TERRITORY
- battlefield = TRANSITION_RELEASE

The legacy entry reason was:
- `FADE_WEAK_DOWN_REJECTION_TO_UP`
- `V83_CONTEXT_CONTINUATION`

Interpretation:
A local "fade weak rejection" event was allowed to override both persistent larger commanders. This is a direct example of:
**micro event > terrain**, when the intended architecture should normally be terrain first with explicit contradiction handling.

## Replay Case 5 — 4:48 to 4:56 AM: rail vs local rollover
Emperor:
- 4:48 YES on an inclined directional rail
- 4:54 EXIT YES when the rail was compromised
- immediately recognized Dance of Dragons / entanglement rather than automatically flipping NO

Tachyos:
- #47 entered NO at 4:55:24
- lost -$4.84 via `LATE_TARGET_INVALIDATION`

Entry timing showed:
- Boss = YES
- Hand = YES
- mission = RAID / CONTESTED_TERRITORY
- bot trigger = `EMA9_ROLLOVER_TO_DOWN`

Interpretation:
Again, a local rollover signal fired opposite the larger persistent commanders. The human response to rail failure was "terrain changed; reassess," while execution translated the event too directly into the opposite trade.

## Replay Case 6 — 5:30 AM: apparent disagreement that is actually horizon separation
Emperor:
- 5:30 NO
- thesis: repeated EMA30 tests, gate fatigue, new down leg / terrain break

Tachyos:
- #51 entered YES at 5:30:30
- strategy = `EXHAUSTION_HANDOFF_FLIP`
- mission = RAID / CONTESTED_TERRITORY
- exited 33 seconds later for +$1.24

This should NOT be labeled simply "Tachy wrong / Emperor right."

Interpretation:
The bot found a short-lived YES raid while the human was describing a larger NO campaign. Both can coexist at different horizons. The future architecture must attach a mission and time horizon to every thesis so a successful raid is not confused with the campaign direction.

## Replay Case 7 — 6:15 to 6:35 AM: the clearest overtrading / campaign-memory failure
Emperor:
- 6:19 ENTER YES because the short down leg looked mature
- held through normal oscillation / target swirl
- YES settled as a win
- 6:31 ENTER NO on persistent multi-contract failed EMA30 reclaim

Tachyos fired six trades through this transition:

1. #54 YES 6:15:19 — -$4.59
2. #55 YES 6:20:15 — -$1.35
3. #56 YES 6:22:15 — -$3.24
4. #57 YES 6:26:10 — -$2.53
5. #58 NO 6:27:51 — -$6.08
6. #59 NO 6:30:21 — +$7.25

Net across the sequence: **-$10.54**

The four YES attempts were four separate executions of what the Emperor treated as one larger anticipation thesis.

#55:
- mission = RAID / CONTESTED_TERRITORY
- exited after ~20s via `ANTICIPATION_FAST_FAIL`

#56:
- mission = RAID / CONTESTED_TERRITORY
- exited via `V92_STRUCTURE_BROKEN`

#57:
- another YES anticipation
- exited via `LATE_TARGET_INVALIDATION`

#58:
- flipped NO late in the old contract at .77
- labeled CAMPAIGN / AUTHORITY_ALIGNED
- reached roughly +19% MFE but then lost -$6.08
- Treasury's 20% "proven" threshold was narrowly missed

#59:
- next-contract NO at .58
- CONTINUATION_HANDOFF / ARC_RIDER
- won +$7.25

Interpretation:
This is the strongest evidence in the run for:
1. parent-thesis memory,
2. anti-repeat / chapter authority,
3. different management for ANTICIPATION,
4. separation of RAID from CAMPAIGN,
5. rollover reset without battlefield amnesia.

The bot essentially paid several times to discover the same transition.

## Replay Case 8 — 6:31 AM: strong human/machine alignment
Emperor:
- 6:31 NO
- EMA9 below EMA30 for several contracts
- repeated approaches failed to reclaim
- both EMAs separating down

Tachyos:
- #59 NO at 6:30:21
- CONTINUATION_HANDOFF / ARC_RIDER
- reason included `ANCESTRY_DOWN, PRICE_BELOW_E9, TARGET_NEAR`
- +$7.25 / +50%

Interpretation:
This is an important positive control. Tachy is capable of reading persistent terrain when ancestry and handoff align. The redesign should preserve this strength.

## Replay Case 9 — 6:52 AM: machine can lead the human
Emperor:
- 6:52 YES as EMA9 moved over EMA30 and separated
- exited 6:57 on weakness

Tachyos:
- #60 YES at 6:45:11, +$3.64
- #61 YES at 6:46:38, +$2.38

Interpretation:
The human is not always earlier. Tachy can identify a viable move first. The objective is not imitation; it is synthesis and disciplined dissent.

## Replay Case 10 — 7:00 AM rollover target dislocation
Emperor:
- 7:00 YES from downside overextension
- recognized that rollover occurred inside the lower extension
- therefore the new target was near the lower edge of the wider orbit and materially below EMA gravity
- later observed price >$100 above target and believed the YES settled successfully

War Council at the 7:00 rollover still carried the old terrain:
- DOWN_DECAY
- NO authority
- CHOP_QUARANTINE
- falling-channel / macro DOWN

At rollover the new target remapped to about 81192.74 while BTC was around 81195.19.

By ~7:14 AM, the same War Council had moved to:
- UP_FORMING
- YES authority
- target accepted YES
- failed-regeneration release side YES
- price roughly $87 above that target

Then:
- #62 entered NO at 7:17
- entry timing showed Boss = YES and Hand = YES
- local trigger was `EMA9_ROLLOVER_TO_DOWN`
- trade lost -$4.96 via `EMA9_ARC_BROKEN`

Interpretation:
This is the cleanest late-session example of two problems at once:
1. Target/Settlement Command adapted to rollover too slowly.
2. Once the larger commanders had switched YES, a local EMA9 rollover still had enough authority to create an opposite NO.

## Whole-run timing telemetry
Entry Timing Shadow versus actual paper results:

| Entry timing label | Trades | W-L | Net P&L | PF |
|---|---:|---:|---:|---:|
| TIMING_OK_SHADOW | 31 | 15-16 | -$24.26 | 0.639 |
| WAIT_NEW_ARC_SHADOW | 16 | 10-6 | +$14.92 | 2.370 |
| WAIT_EMA9_REACTION_SHADOW | 9 | 2-7 | -$12.80 | 0.219 |
| LOW_REMAINING_CAPACITY_SHADOW | 8 | 5-3 | +$14.764 | 6.722 |
| EARLY_COUNTERARC_SHADOW | 2 | 1-1 | -$1.26 | 0.000 |
| ELITE_RAID_ONLY_SHADOW | 2 | 1-1 | -$1.07 | 0.412 |

Important:
These labels should NOT simply become vetoes.
For example, WAIT_NEW_ARC entries were profitable in this one run, while TIMING_OK was negative. The labels contain information, but their semantics must be conditioned on mission and horizon.

## Price-Arc Phase versus actual results
| Price-Arc Phase | Trades | W-L | Net P&L | PF |
|---|---:|---:|---:|---:|
| CROSS_RESET | 16 | 10-6 | +$14.92 | 2.370 |
| PEAK_TROUGH_BUILD | 14 | 7-7 | +$2.154 | 1.111 |
| EXTENSION | 26 | 14-12 | -$13.78 | 0.735 |
| RETURN_TO_EMA9 | 11 | 3-8 | -$11.74 | 0.291 |
| EXTENSION_SLOW | 1 | 0-1 | -$1.26 | 0.000 |

This supports the emerging doctrine:
- mid/extension chasing is dangerous,
- return-to-EMA9 needs reaction/retest logic,
- transition/reset areas can be valuable when entered with the correct mission and invalidation.

## Phase 2 conclusions
### 1. Direction is not the primary deficit
Human and machine frequently chose the same side within a few minutes.

### 2. Campaign identity is the primary deficit
Tachy repeatedly treats each micro signal as a new independent trade.

### 3. Local events have too much unilateral authority
EMA9 rollover / weak-rejection fades can override persistent Boss/Hand/terrain without an explicit contradiction vote.

### 4. Horizon is not explicit enough
A RAID and a CAMPAIGN can legitimately point in opposite directions. They need different objectives, stops, and time budgets.

### 5. ANTICIPATION is managed too much like confirmation
The 6:19 YES example shows an anticipation thesis can require surviving ordinary counter-candles and target swirl. Fast-fail logic should invalidate structure, not merely discomfort.

### 6. Target/Settlement needs first-class rollover authority
A target created at an extreme excursion can instantly change binary settlement asymmetry even when macro direction remains unchanged.

### 7. Tachy must preserve battlefield memory after exits
An exit should end a position, not erase the parent leg, gate history, or campaign.

## Next audit step
Before writing a new trading version:
- define one canonical Battlefield State object,
- map every existing observer into it,
- specify who owns each field,
- specify contradiction rules,
- specify which execution engine may act in each terrain,
- then replay the same Emperor Tape through that proposed decision hierarchy on paper before granting authority.


# Phase 3 — signal quality versus management quality

The contract settlement log allows a second question:

**Was the entry direction wrong, or did management lose a directionally correct trade before settlement?**

Across all 68 V9.5A trades:
- 47 / 68 entry sides matched the eventual contract settlement = **69.1% directional settlement accuracy**
- actual profitable trades = 34 / 68 = **50.0%**
- **21 trades were directionally correct at settlement but still lost money under active management**
- 8 trades were on the wrong eventual settlement side but still made money through tactical exits

This is the strongest evidence yet that mission-specific management matters.

## Hold-to-settlement counterfactual — diagnostic only
If every historical paper entry is independently marked to binary settlement:
- actual V9.5A net: **-$9.706**
- independent hold-to-settlement counterfactual: **+$83.27**

This number is NOT an executable portfolio result because it double-counts repeated entries and ignores capital occupancy / reentry constraints.

Its value is diagnostic:
the entry engine often identified the eventual settlement side, while the management engine failed to convert that information into realized profit.

## First-entry-per-contract control
A more conservative diagnostic keeps only the first Tachy entry in each traded contract.

39 contracts had at least one trade.

First entry per contract:
- 22 wins / 17 losses under actual management
- **+$14.831 actual P&L**
- PF **1.312**
- 27 / 39 first entries matched settlement = **69.2%**
- if only those first entries were independently held to settlement: **+$48.05**

All later same-contract entries:
- 29 trades
- 12 wins / 17 losses
- **-$24.537**
- PF **0.533**

Therefore the full run moved from a profitable first-entry set to a losing overall run primarily through same-contract re-entry churn.

This is a major architecture finding:

> **The first battlefield read often had edge. Re-declaring the battlefield repeatedly destroyed it.**

Do NOT translate this into a crude "one trade per contract" rule. Some re-entries were useful.

Instead:
- preserve campaign/chapter identity after exit,
- require a genuine new structural chapter before declaring a new CAMPAIGN,
- otherwise any re-entry must remain a tactical RAID.

## Mission of same-contract re-entries
Among the 29 subsequent entries in already-traded contracts:

- RAID: 22 trades, **+$6.063**, PF 1.276
- CAMPAIGN: 4 trades, **-$26.27**, 0 wins / 4 losses
- SCOUT: 2 trades, **-$3.79**
- ATTACK: 1 trade, **-$0.54**

The four repeated entries that were reclassified as CAMPAIGN were trades:
- #14
- #17
- #18
- #58

All four lost.

This directly supports the Campaign Ledger doctrine:

> A repeated signal is not a new campaign. A new campaign requires a new chapter.

Repeated same-contract opportunities can still be profitable as raids, but the system should not silently reset campaign identity.

## Intent-specific management result

### ANTICIPATION
- 42 trades
- settlement-direction correct: **33 / 42 = 78.6%**
- actual P&L: **-$19.383**
- 15 trades were correct at settlement but lost under management

Independent hold diagnostic: +$113.91, inflated by repeated entries and therefore NOT a deployable return estimate.

Interpretation:
ANTICIPATION is primarily suffering from management/horizon mismatch, not lack of directional information.

The current fast-fail / structural-break machinery appears too eager for a thesis whose purpose is explicitly to enter before confirmation.

### ARC_RIDER
- 12 trades
- settlement-direction correct: 66.7%
- actual P&L: **+$17.84**
- independent hold diagnostic: +$16.80

Interpretation:
Current active management is broadly adding appropriate value here. Arc Rider is already behaving much more like a properly defined mission.

### EARLY_IMPULSE
- 9 trades
- settlement-direction correct: 55.6%
- actual P&L: **+$3.647**
- independent hold diagnostic: **-$8.29**

Interpretation:
Early Impulse specifically BENEFITS from active tactical management. It should not inherit Anticipation's future hold logic.

### EXHAUSTION_FLIP
Only one example in this run:
- wrong eventual settlement side
- still made +$1.24 tactically

Interpretation:
This is exactly a RAID-like species. A profitable short counter-move does not imply campaign direction.

## Trigger families: direction versus realized management

### EMA9_ROLLOVER anticipation
- 23 examples
- 19 / 23 = **82.6%** matched eventual settlement
- actual P&L only +$2.123
- 10 directionally correct examples still lost under management

Therefore EMA9 rollover should NOT be broadly disabled. The issue is often what Tachy does after the entry.

### PRE_CROSS anticipation
- 11 examples
- 81.8% settlement-direction correct
- actual P&L: -$0.86

Again: useful directional information, weak conversion to realized profit.

### FADE_WEAK anticipation
- 7 examples
- 71.4% settlement-direction correct
- actual P&L: **-$10.68**

This is another warning against evaluating a signal only by managed-trade outcome.
The signal often pointed to the eventual settlement side, but current management rarely monetized it.

### CROSS_RESET anticipation
- 12 examples
- 11 / 12 = **91.7%** settlement-direction correct
- actual P&L: +$7.87

This is especially important because the existing Entry Timing shadow often says `WAIT_NEW_ARC_SHADOW` at CROSS_RESET.

The replay says CROSS_RESET is not automatically a bad place to act. For an anticipation mission it may be precisely where cheap asymmetry exists.

### RETURN_TO_EMA9 anticipation
- 7 examples
- 71.4% settlement-direction correct
- actual P&L: **-$9.59**

This remains the strongest candidate for a reaction/retest rule rather than immediate execution.

## Updated primary diagnosis
The audit now separates three problems that had previously been mixed together:

1. **Signal direction**
   - substantially better than the final P&L suggests

2. **Campaign memory / re-entry**
   - clearly destructive when repeated entries are mistaken for new campaigns

3. **Mission-specific management**
   - Anticipation is being managed too tactically
   - Arc Rider management is comparatively effective
   - Early Impulse needs tactical exits
   - Exhaustion Flip is a raid, not a settlement thesis

This means the next architecture should NOT simply "hold everything longer."

It should make management conditional on:
- mission,
- entry mode,
- parent campaign,
- target geometry,
- and explicit structural invalidation.


# Phase 4 — Campaign Ledger audit

V9.4M already contains the exact kind of chapter memory we thought we might need to invent.

Current-run REAL_ENTRY labels:
- FIRST_CHAPTER: 39 trades, +$14.831
- PARTIAL_RESET: 10 trades, -$3.830
- FRESH_CHAPTER: 14 trades, -$18.501
- SAME_CHAPTER: 5 trades, -$2.206

All 29 non-first same-contract entries were therefore negative in aggregate regardless of chapter label.

More importantly, crossing chapter label with Trade Mission reveals what actually matters:

### Re-entry as RAID
- FRESH_CHAPTER + RAID: 10 trades, 7-3, +$1.069
- SAME_CHAPTER + RAID: 4 trades, 2-2, +$2.204
- PARTIAL_RESET + RAID: 8 trades, 3-5, +$2.790
- combined RAID re-entries: **+$6.063**

### Re-entry as CAMPAIGN
- FRESH_CHAPTER + CAMPAIGN: 2 trades, 0-2, -$15.780
- SAME_CHAPTER + CAMPAIGN: 1 trade, 0-1, -$4.410
- PARTIAL_RESET + CAMPAIGN: 1 trade, 0-1, -$6.080
- combined CAMPAIGN re-entries: **0-4, -$26.270**

This means the existing Chapter classifier is not strong enough to declare a new campaign by itself.

A label such as FRESH_CHAPTER can still represent only a tactical opportunity.

Updated doctrine:

> **Chapter identity and mission identity are separate questions.**
>
> A changed chapter may permit a new RAID.
> A new CAMPAIGN requires a stricter campaign-level authority transfer.

This further supports keeping the existing Campaign Ledger but changing its role in the next architecture:
- Looking Glass uses it as temporal evidence,
- Mission Selector decides whether the new chapter is merely tactical or campaign-grade,
- execution may not promote a repeated same-contract signal into CAMPAIGN without explicit campaign-reset evidence.
