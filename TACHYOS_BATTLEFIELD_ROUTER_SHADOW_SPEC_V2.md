# TACHYOS BATTLEFIELD ROUTER SHADOW SPEC V2

## Status
SHADOW ONLY.

This version supersedes the V1 Router research assumptions where the cross-run J/K/M/V9.5A audit contradicted them.

No paper entry, exit, sizing, or settlement authority is changed.

---

# 1. Cross-run foundation

The V2 Router is based on findings that survived multiple frozen runs:

- RAID was profitable in every run sampled.
- immediate CAMPAIGN was poor in aggregate.
- RAID -> CAMPAIGN promotion was materially better than ATTACK -> CAMPAIGN.
- EARLY_IMPULSE benefits from tactical management.
- ARC_RIDER benefits from its existing active management.
- ANTICIPATION contains strong directional information but needs scale-aware management.
- SCOUT is often directionally early and should be preserved as a transition sensor.
- same-contract re-entry is allowed; same-contract CAMPAIGN declaration requires explicit reset evidence.

---

# 2. Initial mission set

No trade starts with full CAMPAIGN rights.

Allowed initial Router states:

- RAID
- ATTACK
- TRANSITION_SCOUT
- CAMPAIGN_CANDIDATE

Full CAMPAIGN must be earned.

## RAID
Executable tactical mission.

## ATTACK
Executable tactical release mission.

V2 rule:
**ATTACK cannot promote directly to CAMPAIGN.**

Cross-run ATTACK -> CAMPAIGN:
- 4 examples
- 1W / 3L
- -$6.06

## TRANSITION_SCOUT
Research-only state.

No normal paper authority.

Feeds:
- Looking Glass
- transition memory
- contradiction ledger

Cross-run Scout settlement direction:
- 8 / 10 correct
- realized P&L weak

## CAMPAIGN_CANDIDATE
Directional thesis that may eventually earn persistence.

It does NOT yet receive Campaign management privileges.

---

# 3. Entry provenance is immutable

Every position retains an immutable birth mode:

- ANTICIPATION
- RETEST
- EARLY_IMPULSE
- HANDOFF / ARC_RIDER
- EXHAUSTION_FLIP
- CORE legacy

Active mission may evolve.
Entry provenance never changes.

---

# 4. Provenance-specific management

## EARLY_IMPULSE
Cross-run:
- 26 trades with settlement data
- actual active-management P&L +$1.417
- hold-to-settlement diagnostic -$53.71

V2:
- always tactical by default
- use existing Early Impulse manager
- no automatic Campaign promotion
- no settlement-hold conversion

## ARC_RIDER
Cross-run:
- 30 trades
- actual P&L +$27.892
- hold diagnostic +$2.62

V2:
- preserve current Arc Rider management
- do not auto-harvest merely because mission label is RAID
- may contribute to Campaign promotion evidence
- Campaign promotion must not erase the working Arc Rider manager until a separate campaign manager proves superior in shadow

## ANTICIPATION
Cross-run:
- 74 trades
- 73% settlement-direction correct
- first Anticipation per contract: 70% settlement-direction correct

V2:
- can be counterterrain
- receives TRANSITION_ANTICIPATION overlay when Boss/Hand disagree
- micro failure alone is insufficient to kill a parent transition thesis
- no blind hold-to-settlement
- no generic +15% harvest rule
- promotion remains possible only after release / continuity evidence

## EXHAUSTION_FLIP
Tactical reversal species.
Do not auto-promote.

---

# 5. Contradiction classes

## C0_ALIGNED
Boss + Hand agree with trade side.

This is context, not automatic Campaign permission.

## C1_SPLIT_COMMAND
One larger Commander agrees.

## C2_TACTICAL_COUNTERTREND
Boss + Hand oppose trade, but a tactical mission exists.

Cross-run:
- ARC_RIDER counterterrain: +$15.88
- EARLY_IMPULSE counterterrain: +$7.57

Therefore C2 is explicitly permitted.

## C3_AUTHORITY_TRANSFER_CANDIDATE
Local transition evidence opposes old authority but lacks transfer confirmation.

Often:
- ANTICIPATION
- TRANSITION_SCOUT

## C4_AUTHORITY_TRANSFER_CONFIRMED
Campaign-side transfer is earned.

V2 does not grant C4 from one signal.

---

# 6. Campaign promotion path

Primary V2 path:

```
RAID
  -> CAMPAIGN_CANDIDATE
  -> C4 AUTHORITY TRANSFER
  -> CAMPAIGN
```

Not:

```
ATTACK -> CAMPAIGN
```

and not:

```
Hand matches side -> CAMPAIGN
```

## Minimum promotion evidence categories

Promotion remains SHADOW unless several independent categories agree:

1. Borders / release
   - BOUNDARY_RELEASE or sustained clear release

2. Hand authority
   - aligns with trade side

3. Looking Glass
   - genuine chapter / terrain transition
   - not merely another child arc

4. Parent structure
   - parent leg / mountain supports continuation
   - not mature/exhausted

5. Target / Settlement
   - target gravity not materially hostile
   - rollover target remap incorporated

6. Gate history
   - EMA30 reclaim/rejection pattern supports transfer

V2 intentionally does NOT define a single numeric threshold yet.

The shadow replay should log each evidence category separately.

---

# 7. Same-contract re-entry

Allowed.

Do not impose one-trade-per-contract.

But full CAMPAIGN re-declaration requires explicit reset evidence.

Cross-run same-contract CAMPAIGN re-entry:
- 11 trades
- 4W / 7L
- -$33.656

Therefore a repeat entry can be:
- RAID
- ATTACK
- TRANSITION_SCOUT
- CAMPAIGN_CANDIDATE

but cannot silently become a new Campaign.

---

# 8. RAID harvest V2

The V1 idea:
"take +15% on every RAID unless promotion is ready"

was too broad.

K showed a counterexample where ARC_RIDER made much more by running.

V2 rule:

## ARC_RIDER
Ignore generic RAID harvest.
Use Arc Rider manager.

## EARLY_IMPULSE
Use Early Impulse manager.

## ANTICIPATION
+15% becomes a research event, not an exit command.

Possible shadow actions:
- HARVEST_CANDIDATE
- HOLD_FOR_PROMOTION_REVIEW
- HOLD_PARENT_THESIS
- TACTICAL_EXIT_REVIEW

## plain RAID / legacy CORE
May still use harvest research.

---

# 9. Transition overlay

A mission and a transition hypothesis are different fields.

Example:

```
entry_mode = ANTICIPATION
active_mission = RAID
contradiction = C2_TACTICAL_COUNTERTREND
overlay = TRANSITION_ANTICIPATION
```

The overlay tells management:
- this raid may be discovering the next campaign,
- do not mistake every micro failure for thesis death,
- monitor authority-transfer evidence.

It does NOT grant Campaign rights.

---

# 10. Manager routing matrix

| Entry provenance | Active mission | V2 shadow manager |
|---|---|---|
| EARLY_IMPULSE | RAID / ATTACK | EARLY_IMPULSE_MANAGER |
| ARC_RIDER | RAID | ARC_RIDER_MANAGER |
| ANTICIPATION | RAID + transition overlay | TRANSITION_ANTICIPATION_MANAGER |
| ANTICIPATION | CAMPAIGN_CANDIDATE | PARENT_THESIS_MANAGER |
| RETEST | RAID / candidate | RETEST_MANAGER |
| any | CAMPAIGN | CAMPAIGN_MANAGER |
| any | SETTLEMENT | SETTLEMENT_MANAGER |
| SCOUT | TRANSITION_SCOUT | OBSERVER_ONLY |

No new active manager is promoted yet.
These are shadow ownership labels.

---

# 11. Invalidation scale

Every structural invalidation must state its scale:

- MICRO_BROKEN
- LEG_BROKEN
- PARENT_BROKEN
- CAMPAIGN_BROKEN
- SETTLEMENT_BROKEN

V2 rule:

- tactical managers may act on MICRO / LEG break
- Transition Anticipation cannot be killed solely by MICRO_BROKEN
- Campaign cannot be killed solely by child-arc break
- Settlement manager can override campaign late when binary target geometry dominates

---

# 12. Cross-run success tests

Router V2 should be replayed on J, K, M, and V9.5A.

It must not merely improve one run.

Required reports:

1. initial mission distribution
2. immediate Campaign declarations prevented
3. RAID outcomes preserved
4. ATTACK promotions blocked
5. RAID promotion candidates
6. Scout transition accuracy
7. counterterrain Arc Rider outcomes
8. counterterrain Anticipation transition outcomes
9. same-contract Campaign resets
10. mission-specific harvest outcomes
11. correct-at-settlement trades killed by local invalidation

Only rules that survive cross-run comparison are candidates for future paper authority.

---

# 13. V2 doctrine

> Terrain first. Events second.

> Mission is not direction.

> Entry provenance is not mission.

> Commander disagreement is not a veto.

> Raid is allowed to attack the old terrain.

> Campaign is earned from continuity, not declared from alignment.

> A micro arc may die while the parent campaign remains alive.

Still SHADOW ONLY.
