# TACHYOS CROSS-RUN VALIDATION

## Purpose
Validate the V9.5A audit against earlier frozen J / K / M runs before promoting any new paper authority.

Runs compared:
- V9.4J long
- V9.4K long
- V9.4M frozen
- V9.5A frozen

This is still observational research.
No live/paper execution rules are changed here.

---

# 1. The most robust finding: RAID works

Initial Trade Mission = RAID:

| Run | Trades | P&L |
|---|---:|---:|
| J | 15 | +$5.707 |
| K | 4 | +$10.728 |
| M | 38 | +$11.685 |
| V9.5A | 56 | +$24.997 |

Aggregate:
- 113 RAID entries
- 63 realized wins / 48 losses / 2 flats
- **+$53.117**
- 74 / 113 matched eventual settlement side = **65.5%**

RAID is the only initial mission that was profitable in every run sampled.

This does not mean every trade should be a raid.
It means the existing tactical mission concept is empirically useful and should be preserved.

---

# 2. Immediate CAMPAIGN is not robust

Initial Trade Mission = CAMPAIGN:

| Run | Trades | Settlement-correct | P&L |
|---|---:|---:|---:|
| J | 2 | 2 | +$1.387 |
| K | 1 | 1 | +$3.762 |
| M | 9 | 2 | -$29.315 |
| V9.5A | 6 | 2 | -$29.453 |

Aggregate:
- 18 immediate CAMPAIGN entries
- only 7 / 18 matched settlement = **38.9%**
- **-$53.619**

The small J/K samples looked fine.
The larger M and V9.5A samples did not.

Therefore:

> **Hand alignment + clear territory is not sufficient to declare a Campaign at entry.**

The V9.5A conclusion survives cross-run validation.

---

# 3. Campaign promotion is better than Campaign declaration — but not universally

Observed shadow promotions into CAMPAIGN:

| Run | Promotions | W-L | P&L |
|---|---:|---:|---:|
| J | 0 | — | $0 |
| K | 1 | 1-0 | +$4.80 |
| M | 4 | 1-3 | -$7.50 |
| V9.5A | 8 | 7-1 | +$22.274 |

Aggregate:
- 13 promotions
- 9W / 4L
- **+$19.574**

This supports "Campaign is earned" much more than "Campaign is declared."

But M is an important warning:
boundary release + Hand alignment alone is still not a perfect promotion rule.

Promotion needs Looking Glass / parent-structure / target context as additional evidence.

---

# 4. Promotion origin matters enormously

## ATTACK -> CAMPAIGN
Across K / M / V9.5A:
- 4 promotions
- 1W / 3L
- **-$6.06**

ATTACK is a tactical species.
Cross-run evidence does not support automatically converting it into a Campaign.

## RAID -> CAMPAIGN
Across M / V9.5A:
- 9 promotions
- 7W / 1L / 1 flat
- **+$25.634**

This is a much cleaner path.

### Router implication
For the next shadow Router:

- ATTACK remains tactical.
- RAID may earn CAMPAIGN.
- Campaign promotion is not available merely because time passed or ROI rose.
- promotion must come from battlefield evidence.

---

# 5. Entry provenance must constrain promotion

## EARLY_IMPULSE across all four runs
Where settlement result was available:
- 26 trades
- 46.2% settlement-direction correct
- actual active-management P&L: **+$1.417**
- independent hold-to-settlement diagnostic: **-$53.71**

This is decisive.

> **Early Impulse is tactical.**

It benefits from active harvesting / defense and should not inherit Campaign-style persistence merely because Hand later aligns.

## ARC_RIDER across all four runs
- 30 trades
- 63.3% settlement-direction correct
- actual P&L: **+$27.892**
- independent hold diagnostic: **+$2.62**

The existing Arc Rider manager adds substantial value.

> **Do not replace Arc Rider's tactical manager with a blanket hold-to-settlement philosophy.**

Arc Rider may contribute to a future Campaign promotion, but its existing management behavior is valuable and should be preserved unless the promotion itself earns a different manager.

## ANTICIPATION across all four runs
- 74 trades with settlement data
- 54 / 74 settlement-correct = **73.0%**
- actual P&L: **+$11.319**
- independent hold diagnostic: **+$139.98**

Because repeated entries share contracts, +$139.98 is diagnostic only.

Control: first Anticipation per contract:
- 50 signals
- 35 / 50 correct = **70.0%**
- actual P&L: **+$9.302**
- independent hold diagnostic: **+$59.73**

Interpretation:
Anticipation is a strong directional / transition sensor, but its correct manager is regime-dependent.
J/K did not benefit from blind holding the way V9.5A would have.

Therefore:

> **Anticipation needs parent-scale management, not automatic settlement holding.**

---

# 6. Counterterrain RAID is a real species

Trades classified as RAID while both Boss and Hand pointed the opposite direction were examined across all four runs.

## ARC_RIDER counterterrain
Aggregate:
- 16 trades
- 11W / 5L
- **+$15.88**

Positive in K, M, and V9.5A; J had one large losing example.

This strongly supports allowing tactical Arc Rider raids against macro authority.

## EARLY_IMPULSE counterterrain
Aggregate:
- 9 trades
- 5 realized wins / 3 losses / 1 flat
- **+$7.57**

Again: tactical counterterrain is legitimate.

## ANTICIPATION counterterrain
Aggregate realized:
- 47 trades
- 21W / 26L
- **-$1.915**

Where settlement result was available:
- 46 trades
- 34 / 46 settlement-correct = **73.9%**
- actual P&L on those = +$3.835
- independent hold diagnostic = +$90.57

This is the exact reason Commander disagreement must not be a veto.

Counterterrain Anticipation often appears to be an early transition detector.
It should be tagged for transition research, not treated as a normal mature Campaign.

---

# 7. SCOUT survives cross-run validation as a transition sensor

Initial SCOUT:
- J: 1 trade, settlement correct
- K: 2 trades, both settlement correct
- M: 2 trades, 1 correct
- V9.5A: 5 trades, 4 correct

Aggregate:
- 10 Scout trades
- **8 / 10 settlement-correct = 80%**
- actual P&L: **-$1.71**

So Scout is not useless indecision.

It frequently sees direction before authority is settled, but current monetization is weak.

Router role:

`TRANSITION_SCOUT`

No normal Campaign authority.
Preserve it for Looking Glass and future transition management research.

---

# 8. Same-contract re-entry is NOT globally bad

This is an important correction to the V9.5A-only reading.

Later same-contract entries:
- J: +$12.144
- K: +$9.64
- M: -$6.598
- V9.5A: -$24.537

Therefore:

> **Do not create a one-trade-per-contract rule.**

Re-entry quality is regime- and mission-dependent.

However, same-contract re-entry specifically labeled CAMPAIGN remains weak in aggregate:

- J: +$1.387
- K: +$3.762
- M: -$12.535
- V9.5A: -$26.27

Aggregate:
- 11 re-entry CAMPAIGN declarations
- 4W / 7L
- **-$33.656**

So the correct rule is narrower:

> **Re-entry is allowed. Re-declaring a new Campaign requires much stronger evidence.**

---

# 9. The +15% RAID harvest rule needs provenance

V9.5A alone suggested:
"harvest a RAID at +15% unless promotion is becoming ready."

Cross-run replay shows that is too broad.

A simple harvest policy improved diagnostic arithmetic in:
- J overall harvest sample
- M
- V9.5A

but hurt K, where an ARC_RIDER raid ran from a +15% opportunity to a much larger realized gain.

Therefore:

- ARC_RIDER should keep its current manager.
- EARLY_IMPULSE remains tactical under its own manager.
- ANTICIPATION harvest/promotion logic stays research-only.
- a generic mission-wide +15% exit should NOT be promoted.

This is exactly why entry provenance and active mission must remain separate fields.

---

# 10. Cross-run command hierarchy

The evidence now supports a stricter hierarchy:

## Initial state
Most executable ideas begin as:
- RAID
- ATTACK
- TRANSITION_SCOUT
- CAMPAIGN_CANDIDATE

Not as full CAMPAIGN.

## Tactical species
### EARLY_IMPULSE
- tactical
- active profit-taking valuable
- campaign persistence not justified by default

### ATTACK
- tactical release
- do not auto-promote to Campaign in Router V1

### ARC_RIDER
- preserve current manager
- can oppose macro terrain
- may become promotion evidence, but do not destroy its working management

## Transition species
### ANTICIPATION
- strong directional information
- may oppose current Boss/Hand
- needs parent-scale invalidation
- may become Campaign only after release / continuity evidence

### TRANSITION_SCOUT
- research-only
- feeds Looking Glass
- often directionally early

## Campaign
Must be earned from a tactical / transition state.

Preferred source:
`RAID -> CAMPAIGN`

Not:
`ATTACK -> CAMPAIGN`

Promotion evidence should include:
- Borders release
- Hand alignment
- Looking Glass chapter transfer
- parent leg / mountain continuity
- target gravity not hostile

---

# 11. What this changes in Router research

V9.5A-only hypotheses that SURVIVED:
- immediate Campaign is dangerous
- RAID is useful
- Commander disagreement cannot be a veto
- Scout contains transition information
- Anticipation needs different management
- mission and entry provenance must remain separate

Hypotheses that were WEAKENED / corrected:
- all same-contract re-entry is bad -> FALSE
- +15% harvest should apply to every RAID -> TOO BROAD
- any boundary-release promotion is good -> FALSE
- Campaign promotion can ignore entry provenance -> FALSE

This is why the cross-run audit was required before paper authority.

---

# 12. Next shadow version

The next Router research iteration should implement these constraints:

1. no immediate full CAMPAIGN at entry
2. ATTACK cannot promote to CAMPAIGN
3. EARLY_IMPULSE remains tactical
4. ARC_RIDER keeps current management
5. SCOUT becomes TRANSITION_SCOUT
6. counterterrain ANTICIPATION gets TRANSITION_ANTICIPATION overlay
7. RAID -> CAMPAIGN is the primary promotion path
8. promotion requires Looking Glass + parent-scale + target context in addition to Borders/Hand
9. same-contract re-entry is allowed, but Campaign reset is explicit

Still SHADOW ONLY.
