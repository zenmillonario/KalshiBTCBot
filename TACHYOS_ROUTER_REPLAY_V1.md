# TACHYOS ROUTER REPLAY V1

## Status
OFFLINE / SHADOW RESEARCH ONLY.

Frozen baseline:
- V9.5A
- run commit: `ee2db0c70ef0adeea173138a9e8c6c273cb7652a`
- no live/paper authority changes

Replay tool:
- `analysis/replay_battlefield_router_v1.py`

The purpose of this phase is not to optimize thresholds.
It is to separate:
- direction,
- mission,
- campaign identity,
- contradiction,
- management horizon.

---

# 1. Emperor vs Tachyos — same overnight window

The Emperor Tape can now be compared against the contract settlement log.

To avoid obvious double-counting:
- the 11:52 PM NO add is not counted as a separate campaign,
- entries on a rollover boundary are assigned to the new 15-minute contract when the surrounding commentary makes that clear.

Manual campaigns from 11:42 PM through 7:00 AM:
- 22 independent directional campaigns
- 16 / 22 matched eventual settlement side
- **72.7% settlement-direction accuracy**

Of the 6 manual entries whose original direction did NOT match settlement:
- 5 were exited before settlement
- only the 4:00 AM NO was explicitly held into a losing settlement

This is not a realized-P&L calculation because exact manual fills/exits were not supplied for every campaign.

Tachyos over the comparable 11:42 PM -> 7:15 AM window:
- 38 entries
- 27 / 38 matched eventual settlement side
- **71.1% settlement-direction accuracy**
- 21 / 38 realized profitable trades
- observed paper P&L in that window: **+$14.423**

## Meaning
The human and Tachyos were remarkably similar in raw settlement direction during the tape window.

The human advantage was not obviously "better prediction."

It was more:
- fewer independent declarations,
- stronger campaign continuity,
- recognizing when geometry changed,
- exiting 5 of 6 wrong-direction manual campaigns before settlement,
- avoiding some of the bot's re-entry churn.

This is the strongest evidence so far that the primary research target is:

> **mission + continuity + management, not another direction detector.**

---

# 2. Commander contradiction is information, not a veto

The Router assigns contradiction classes.

A particularly important class is:

`C2_TACTICAL_COUNTERTREND`

Meaning:
- trade side opposed both current Boss and Hand,
- but the mission was tactical RAID / ATTACK.

V9.5A C2 trades:
- 39 trades
- 19W / 20L
- actual P&L **+$9.813**
- 74.4% matched eventual settlement side

Therefore:

> **A trade opposing both larger Commanders is not automatically bad.**

This validates the constitutional rule:
macro terrain informs; it does not veto.

---

# 3. Counterterrain behavior depends on entry species

## ARC_RIDER counterterrain raids
- 8 trades
- 6W / 2L
- **+$12.15**
- settlement-direction accuracy: 62.5%

The actual tactical manager outperformed the independent hold-to-settlement diagnostic.

Interpretation:
ARC_RIDER can be a successful tactical raid even while larger Commanders still point the other way.

Do not force it to become a settlement thesis.

## EARLY_IMPULSE counterterrain raids
- 3 trades
- 2W / 1L
- **+$3.01**
- settlement-direction accuracy: 66.7%

Again, tactical management is appropriate.

## ANTICIPATION counterterrain raids
- 27 trades
- 11W / 16L
- actual P&L **-$4.707**
- 22 / 27 matched eventual settlement side
- **81.5% settlement-direction accuracy**

Independent hold-to-settlement diagnostic: +$86.54.

That hold number is NOT a deployable return because repeated entries share contracts and capital assumptions.

But the directional result is too strong to dismiss.

### First countertrend Anticipation per contract
To reduce duplicate inflation, keep only the first such signal in each contract:

- 19 contracts
- 14 / 19 correct at settlement
- **73.7% settlement-direction accuracy**
- actual management P&L: **-$16.30**
- independent hold diagnostic: **+$32.63**

This is a major finding.

> **Counterterrain Anticipation frequently behaves like an early transition detector, but the current RAID-style manager often monetizes it poorly.**

It should not automatically receive Campaign rights.
It should receive a distinct shadow overlay:

`TRANSITION_ANTICIPATION`

That overlay is a management/research state, not a new detector.

---

# 4. Chapter behavior inside countertrend Anticipation

Among C2 Anticipation trades:

### FIRST_CHAPTER
- 13
- settlement correct 76.9%
- actual P&L -$10.69

### FRESH_CHAPTER
- 6
- settlement correct 100%
- actual P&L +$7.539

### PARTIAL_RESET
- 4
- settlement correct 100%
- actual P&L -$3.76

### SAME_CHAPTER
- 4
- settlement correct 50%
- actual P&L +$2.204

This reinforces an important distinction:

> **Chapter identity and management quality are separate.**

A PARTIAL_RESET can still point correctly to the eventual side while current management loses the trade.

A FRESH_CHAPTER does not automatically justify CAMPAIGN status either.

---

# 5. Price-Arc Phase inside transition Anticipation

C2 Anticipation by Price-Arc Phase:

### CROSS_RESET
- 5
- 100% settlement-direction correct
- actual P&L -$3.16

### RETURN_TO_EMA9
- 6
- 83.3% settlement-direction correct
- actual P&L -$0.39
- only 1 realized winner

### EXTENSION
- 9
- 88.9% settlement-direction correct
- actual P&L -$2.081

### PEAK_TROUGH_BUILD
- 7
- 57.1% settlement-direction correct
- actual P&L +$0.924

Important:
these are small samples and should not become thresholds.

But they explain why global labels such as:
- "WAIT_NEW_ARC"
- "RETURN_TO_EMA9 is bad"
- "EXTENSION is late"

are too crude.

The phase must be interpreted together with:
- mission,
- contradiction,
- campaign age,
- target gravity,
- chapter.

---

# 6. SCOUT should not be erased

Five V9.5A trades were assigned SCOUT / unresolved mandate.

Observed:
- actual P&L: **-$4.71**
- 4 / 5 matched eventual settlement direction = **80%**

The current Router replay therefore preserves these as:

`TRANSITION_SCOUT`

rather than converting them directly into WAIT.

A Scout has no normal execution authority yet.
Its job is to tell Looking Glass:

> "The local structure may be discovering the next battlefield before Boss/Hand have transferred authority."

This is particularly relevant to early reversal research.

---

# 7. Campaign promotion readiness at RAID harvest

Existing Trade Mission shadow emits:

`HARVEST_EDGE_SHADOW`

when a RAID reaches roughly +15% ROI.

The audit asked:
when should a RAID harvest, and when should it wait because the battlefield is close to promoting it into a CAMPAIGN?

A simple one-run shadow hypothesis was tested at the first harvest:

Promotion readiness = HIGH when:

1. Hand authority agrees with the trade side, AND
2. either:
   - Borders is `CHURN_RESOLVING`, `BOUNDARY_RELEASE`, or `CLEAR_TERRITORY`,
   - OR War Council has `ACT_IMMEDIATELY` / `ACT_FIRST_VALID` on the trade side.

Among 36 trades that emitted a RAID harvest:

- later-promoted correctly identified: 3 / 3
- false negatives: 0
- false positives: 1
- true low-readiness: 32

The single false positive was trade #32.
Its actual outcome happened to equal the first-harvest result, so the classification had no observed P&L cost in this run.

## Diagnostic arithmetic
If:
- LOW readiness -> take first harvest,
- HIGH readiness -> preserve the actual historical path,

then those 36 historical trades produce:
- diagnostic router arithmetic: **+$76.18**
- actual observed arithmetic: **+$64.373**
- difference: **+$11.807**

This is NOT a live backtest because changed exits alter future availability and state.

It is strong enough to justify keeping this rule in shadow.

### Doctrine
> **A Raid harvests its edge unless the battlefield is visibly earning promotion.**

---

# 8. Immediate Campaign declaration remains suspect

Legacy mission assignment says CAMPAIGN whenever:
- Hand authority matches side,
- Borders is clear/releasing.

That ignores entry species.

The six immediate CAMPAIGN assignments in V9.5A:
- 1W / 5L
- **-$29.453**

Four were same-contract re-entry campaigns:
- 0W / 4L
- **-$26.27**

By contrast, later promotions into CAMPAIGN:
- 7W / 1L
- **+$22.274**

Therefore the Router keeps:

`CAMPAIGN_CANDIDATE`

as a provisional state.

Campaign persistence is granted only after evidence develops.

---

# 9. Mission and entry provenance must remain separate

The active bot currently can overwrite `trade_intent` and promote an ANTICIPATION into ARC_RIDER.

The concept is good, but history is lost.

Future state must preserve two independent fields:

### entry_mode
Immutable origin:
- ANTICIPATION
- RETEST
- EARLY_IMPULSE
- HANDOFF
- EXHAUSTION_FLIP

### active_mission
May evolve:
- SCOUT
- RAID
- ATTACK
- CAMPAIGN_CANDIDATE
- CAMPAIGN
- SETTLEMENT

Example:

```
entry_mode = ANTICIPATION
active_mission = RAID
overlay = TRANSITION_ANTICIPATION
...
boundary releases
Hand aligns
Looking Glass confirms chapter transfer
...
active_mission = CAMPAIGN
entry_mode remains ANTICIPATION
```

This lets the manager know both:
- how much confirmation was paid for,
- what battlefield status has since been earned.

---

# 10. Router V1 research object

The offline replay now records:
- legacy mission
- router mission
- entry action
- chapter
- Boss / Hand
- Borders / War Council
- battlefield class
- Price-Arc Phase
- contradiction class
- transition-candidate overlay
- first RAID harvest
- promotion readiness
- observed campaign promotion
- active mission at exit
- exit-review class
- settlement result

The tool is:
`analysis/replay_battlefield_router_v1.py`

It does not import or modify the live bot.

---

# 11. Current interpretation

The architecture is converging toward:

```
Direction detectors
      |
BattlefieldState
      |
Permanent Commanders
      |
Contradiction Ledger
      |
Mission Selector
      |
Entry provenance + mission overlay
      |
Mission-specific manager
      |
Looking Glass continuity
```

The key idea is no longer:

"Which signal wins?"

It is:

> **What kind of idea is this, what scale does it belong to, and what evidence would actually kill it?**

---

# 12. What remains before a new paper version

Still do NOT promote this to V9.5B paper authority.

Next research tasks:
1. run the offline Router script against the frozen V9.5A directory locally,
2. save the 68-trade replay table,
3. inspect the Router's transition candidates against the Emperor Tape,
4. define parent-scale invalidation using existing Arc / Looking Glass / gate memory,
5. test the same Router logic on the earlier frozen J/K/M runs,
6. only then choose which shadow rules deserve a new paper version.

Cross-run survival is now the most important test.
