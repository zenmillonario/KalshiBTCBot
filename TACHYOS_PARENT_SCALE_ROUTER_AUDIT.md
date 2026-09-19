# TACHYOS PARENT-SCALE ROUTER AUDIT

## Status

OFFLINE / SHADOW RESEARCH ONLY.

Frozen paper authority remains V9.5A.

This audit does **not** change:
- entry authority,
- exit authority,
- sizing,
- settlement handling,
- active Treasury,
- Price Freshness,
- or any live/paper trading behavior.

New analysis tool:
- \`analysis/replay_battlefield_router_parent_scale.py\`

The purpose is to test two unresolved Router questions using existing telemetry only:

1. What counts as a real same-contract Campaign reset?
2. When is a local structural break corroborated at parent scale?

No new detector is introduced.

---

# 1. Campaign reset audit

The frozen V9.5A run contains:
- 68 trades
- 29 same-contract re-entries

The existing Campaign Ledger often calls a re-entry:
- FRESH_CHAPTER,
- PARTIAL_RESET,
- or SAME_CHAPTER

but those labels can be driven by:
- new micro arc,
- arc-direction change,
- phase change,
- battlefield label change,
- cage change,
- dragon change,
- target-side crossing.

Those events are useful.
They are not automatically a new Campaign.

## Stricter shadow reset categories

The parent-scale replay separates four higher-level evidence categories:

1. **AUTHORITY_TRANSFER**
   - Boss and/or Hand actually changes to the proposed trade side.

2. **PARENT_EMA_TRANSFER**
   - parent EMA/arc ancestry changes to the proposed side.

3. **BORDER_RELEASE**
   - Borders releases to the proposed side, or a sustained-clear/action combination supports it.

4. **LOOKING_GLASS_LAUNCH**
   - Looking Glass / Arc Voyage is in a new launch phase on the proposed side.

These are evidence categories only.
They do not grant authority.

## V9.5A result

Across the 29 same-contract re-entries:

- **24 = NO_CAMPAIGN_RESET**
- **5 = SINGLE_CATEGORY_ONLY**
- **0 = MULTI_CATEGORY_RESET_REVIEW**

This is a strong result.

The four legacy same-contract entries that were immediately labeled CAMPAIGN were:

- #14
- #17
- #18
- #58

Combined:
- 4 trades
- 1 settlement-correct / 3 settlement-wrong
- **-$26.27**
- **0 / 4 had multi-category Campaign-reset evidence**

### Interpretation

The rule should remain narrow:

> Same-contract re-entry is allowed.  
> Same-contract Campaign identity is not automatically renewed.

This does **not** imply one trade per contract.

In fact, many same-contract re-entries without Campaign reset were still directionally useful.

The Router distinction is:

- re-entry may be RAID,
- re-entry may be ATTACK,
- re-entry may be TRANSITION_SCOUT,
- re-entry may be CAMPAIGN_CANDIDATE,

but full Campaign persistence requires independent evidence that the battlefield itself reset.

---

# 2. Structural-loss family remains the main management problem

The four audited structural exit families produced:

- 23 exits
- **-$60.28 realized P&L**
- 16 / 23 later matched the eventual settlement side

Breakdown:

## ANTICIPATION_FAST_FAIL
- 4 exits
- 3 settlement-correct
- -$4.71

## EMA9_ARC_BROKEN
- 12 exits
- 7 settlement-correct
- -$24.54

## LATE_TARGET_INVALIDATION
- 5 exits
- 4 settlement-correct
- -$23.20

## V92_STRUCTURE_BROKEN
- 2 exits
- 2 settlement-correct
- -$7.83

This confirms the earlier audit:

> A local structural break is not the same thing as parent-thesis death.

---

# 3. Anticipation is where scale matters most

Anticipation trades inside the structural-loss family:

- 15 trades
- 10 / 15 settlement-correct
- **-$35.28 realized**

First Anticipation per contract inside that family:

- 8 trades
- 4 / 8 settlement-correct
- **-$19.28 realized**

The first-entry sample is especially useful because it removes most duplicate-entry inflation.

---

# 4. Why Boss + Hand cannot become a stop rule

Among the eight first-entry Anticipation structural exits:

- all 8 had Boss + Hand opposing the Anticipation side at exit,
- 4 eventually settled on the Anticipation side,
- 4 eventually settled against it.

Therefore:

> Boss + Hand opposition is context, not parent invalidation.

The same overlap appears in other fields:

- parent EMA opposition occurs in both correct and wrong Anticipations,
- target hostility occurs in both correct and wrong Anticipations,
- current local arc support occurs in both correct and wrong Anticipations.

No single existing field safely separates parent death from transition lag.

That is exactly why the Router must aggregate scale-aware evidence rather than promote another veto.

---

# 5. High-opposition falsification flag

A deliberately conservative shadow heuristic was added:

A structural Anticipation is marked:

\`HIGH_OPPOSITION_PARENT_BREAK_CANDIDATE\`

only when:

1. at least three independent parent/terrain opposition categories agree, and
2. no transition-support category remains.

Opposition categories:
- Boss + Hand both against,
- parent EMA against,
- clear territory against,
- War action against.

Transition-support categories:
- parent EMA already supports the new side,
- Borders is resolving/releasing,
- battlefield is TRANSITION_RELEASE,
- the old opposite Arc Voyage is mature,
- target position currently supports the trade side.

## V9.5A result

The heuristic flags only:

- #24
- #40

Both eventually settled against the original Anticipation side.

So in this frozen run:
- 2 candidates
- 0 settlement-correct
- -$4.52 realized

This is interesting.

It is **not enough evidence to promote the heuristic**.

The sample is only two trades and must be falsified on future/more compatible frozen runs.

---

# 6. Important non-result

The parent-scale audit does **not** produce a universal replacement for:

- EMA9_ARC_BROKEN,
- ANTICIPATION_FAST_FAIL,
- V92_STRUCTURE_BROKEN,
- LATE_TARGET_INVALIDATION.

That is a useful result.

A blanket "hold Anticipation longer" rule was already disproved by the first-entry control.

The architecture therefore remains:

\`\`\`
local break
    |
    v
scale review
    |
    +-- tactical provenance -> existing tactical manager
    |
    +-- Anticipation -> parent evidence review
    |
    +-- late target -> Settlement-scale review
    |
    +-- Campaign -> parent/campaign invalidation review
\`\`\`

A local break may still be a valid exit.
It simply needs to be named at the correct scale.

---

# 7. Campaign reset vs parent invalidation

These are different problems.

## Campaign reset
The evidence is currently relatively clean:

> micro chapter change is insufficient for a new Campaign.

## Parent invalidation
The evidence is more difficult:

> old authority can oppose a transition that later proves correct.

Therefore the next Router should be stricter about **granting Campaign rights** than it is about **allowing tactical entries**.

That preserves the central doctrine:

> A dead position may be abandoned. The battlefield is never abandoned.

---

# 8. Current shadow fields

The new replay writes, among others:

## Campaign reset
- reset_status
- reset_major_count
- reset_authority_transfer_to_side
- reset_authority_transfer_against
- reset_parent_ema_transfer_to_side
- reset_boundary_release_to_side
- reset_looking_glass_launch_to_side
- reset_evidence_categories

## Exit-scale evidence
- exit_authority_against
- exit_parent_ema_against
- exit_border_resolving
- exit_border_clear_against
- exit_war_action_against
- exit_target_favorable_margin
- exit_old_voyage_mature_against
- exit_battlefield_transition
- exit_failed_local_thesis
- exit_parent_opposition_count
- exit_transition_support_count
- exit_high_opposition_parent_break_candidate

Again:
these are observer fields only.

---

# 9. Next test

Run the new offline replay on the frozen V9.5A directory and save:

- \`analysis/router_parent_scale_replay.csv\`
- \`analysis/router_parent_scale_summary.json\`

Then inspect:
- #24
- #29
- #40
- #47
- #50
- #54–#59
- #62
- #66

against the Emperor Tape and existing continuity documents.

Only after that should we decide whether any parent-scale rule deserves broader cross-run testing.

No V9.5B paper authority is authorized by this audit.
