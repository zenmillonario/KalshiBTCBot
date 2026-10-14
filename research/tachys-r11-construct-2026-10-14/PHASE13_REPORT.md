# Tachys · Construct Phase 13 — Rolling Arc Echo + 2–3 Repetition

**Status:** COMPLETE as an **offline, causal, source-backed research module**. **NOT an R12 release.** No original engine source, entry permission, quote safety, protection, position custody, or launcher was changed. The existing frozen offline Phase11 Command candidate was re-tested separately and is **not** represented as having absorbed Phase13 trading logic.

## Why this phase

The physical EMA9 (NAEVYR) arc continuously evolves over an EMA30 (THAERYON) spine across Kalshi 15-minute contract boundaries. The user's traditional Arc Echo principle is **two or three similar arcs and then watch for a possible change of character**; it is not an automatic third-arc reversal command.

Original archived R9/R11 `tachys_ema_geometry_v9_4i.csv` already publishes `previous_same_arc_id`, `previous_same_amplitude`, `amplitude_ratio`, `crest_progression`, and `sequence_count`. So ancestry existed. The missing parts were an explicit comparison of the **shape** of the previous 2–3 completed comparable arcs, an **as-of equal-age** comparison of the still-growing arc, and **distinct turn-attempt generations** inside an individual long mountain.

## Data provenance, scope and fidelity

R9 original source SHA256 `bc7da97fe3c275db16028f42734c79f2c44510f6d165d15aee56f91bb68f4163`.
R11 original source SHA256 `3266d0fb6d4e13239df60aa28bcf5c6fac975a5a0dafe2de1f8a313fafddd09b`.

The two sources provide **49 named EMA9 arcs**, of which **13 span more than one economic contract**, and **two** end at the run boundary and are explicitly right-censored. **39/49** have no internal data gap greater than 30 seconds; other curves are flagged rather than pretending missing shape was observed.

At every as-of snapshot, the research draws exclusively from current/past source rows and **completed** previous arcs in the *same* R9 or R11 run. It retains the original ticker for economic identity, but never resets physical arc identity at rollover. The source-derived arc amplitude, orbit and EMA lines are **not actual independently constructed candles or guaranteed native quotes**. No future result column appears in a causal output.

## Implemented research, not another authority machine

`build_phase13.py` constructs these reproducible outputs:

1. `PHASE13_COMPLETED_ARC_SHAPE_ATLAS.csv` — completed arcs: duration, source amplitude, BTC/EMA9 signed-orbit extrema, directional EMA9 movement, fraction of observations on the relevant side of EMA30, multi-contract continuity and source-gap quality. A final right-censored arc cannot become a prior completed analogy.
2. `PHASE13_CAUSAL_ARC_ECHO_SNAPSHOTS.csv` — records current partial arc shape, newest **up to three** completed same-direction ancestors and recent opposite arcs; preserves source repetition fields; computes the **shape distance at a common, observed elapsed age**, as well as completed-predecessor relative shape and current-to-ancestor amplitude. The current arc's future length/peak is **never** used as input.
3. `PHASE13_CAUSAL_TURN_ATTEMPT_GENERATIONS.csv` — within the same physical arc, distinguishes fresh peak/trough renewal, retreat, recovery and **observed failed re-extension**. A newly observed physical extension retires a previously armed turn attempt; gaps and duplicate observations cannot reauthorize old evidence. These states are *diagnostics*, not trading commands.
4. `PHASE13_ENTRY_ANCHOR_ARC_ECHO.csv` — exact native-source snapshots as-of **eight** historical R9/R11 entry anchors (R9 #6/#10/#20, R11 #9/#10/#11/#14/#15), using Phase12's verified backward source-time join. Outcomes and stale quote assumptions do not enter.
5. `PHASE13_THIRD_REPEAT_EVALUATION_ONLY.csv` — historical later arc amplitudes are kept **strictly separate for evaluation**. This does not establish conditional probabilities of profitable YES/NO trades.

A comparison uses direction-normalized EMA9 travel and BTC-to-EMA9 orbit at seven interpolated points. It refuses interpolation across a source gap over 30 seconds. The shape distance is an **untrained research descriptor** (lower means more geometrically similar), not a validated reversal probability or admission threshold. Early partial arcs are compared with predecessors at **the same observed physical age**, rather than falsely calling an unfinished arc 'small' just because its completed predecessors are taller.

The initial offline TurnAttempt uses a $5 physical sampling resolution and a relative range threshold for descriptive transitions. These are **not trading thresholds**, and are not authorized to block or place orders.

## Concrete R9 vs R11 physical controls

### R11 — repeated modest UP arcs, followed by decisive DOWN expansion

`A00003 UP` max source amplitude **$21.70**; `A00005 UP` **$16.39**; `A00007 UP` **$19.57**. The next observed DOWN arc `A00008` reached **$280.02**, lasted approximately **25 minutes**, and spanned **three contracts**. That is a compelling *historical* BASE/HEIST→TRANSFER→DOWN DRAGON research example. It does **not** prove, by itself, that the next arc was predictable or that the third UP crest was an executable NO.

When #9Y entered, `A00008` had been observed for approximately **211 seconds**; at #10Y approximately **546 seconds**; at #11Y approximately **1,449 seconds**. They all inherited the same three completed DOWN ancestors (`A00006`, `A00004`, `A00002`), but the current arc's partial amplitude and last renewed extreme were very different. At #10Y the arc was **making a new recorded DOWN extreme**. A completed upper-side rebound analogy therefore must not independently authorize an opposing YES. At #11Y the mountain was far older; that fact alone also does **not** authorize the original YES. The subsequently successful rebound and stale original .54 native quote remain governed by the strict Phase8/9 temporal and HF2 evidence.

### R9 — repeated DOWN arcs without a mandatory third-arc switch

`A00004 DOWN` max source amplitude **$29.74**, `A00006 DOWN` **$33.67**, `A00008 DOWN` **$45.70**; a further DOWN arc `A00010` had **$34.11**. Those arcs did **not** comply with a mechanical 'third repeat, then switch and stop the DOWN thesis' rule. Asymmetric alternating opportunities remained possible while the broader terrain continued evolving.

At R9 #10 NO entry, the active `A00011 UP` was only about **37 seconds** old, with the price still above EMA9 and the source marking upward strength. At R9 #20 NO, `A00019 UP` had already been observed for **~672 seconds**, and its historical first failed re-extension was very old. A remaining `CREST_FORMING` label alone does not distinguish their outcomes. A shape/attempt chronology is useful, but neither future gain establishes entry-time permission.

## Research sample counts and causal qualification

See `PHASE13_METRICS.json` for exact recomputed counts. The 2–3 repetition review contains **41** third-or-later same-direction physical arcs with two prior completed same-direction arcs available. In **12** such instances, those two predecessor amplitudes were within a descriptive factor of about 1.5. Some subsequent same-side arcs became stronger, others weaker; there is no reliable 'switch on the third arc' empirical law from these two runs alone. These are correlated run-specific patterns, not population frequencies.

## Validation and remaining release blockers

The Phase13 source-backed tests verify: exact original hashes, completed-only ancestry, causally truncated-replay invariance, no next-arc leakage, long-gap refusal, mirrored UP/DOWN shape normalization, within-arc attempt retirement, deduplicated physical state transitions, contract-rollover continuity, eight anchored entries, and separation of hindsight-only future results. Phase13 **24/24** tests PASS.

Unmodified Phase11 baseline tests executed in **five separate Python processes**: source/sequence 19, actual offline PAPER Command 9, chronological Command 6, winner floor 3, mirrored/anticipatory Command 15: **52/52 PASS**, independently. **These baseline results do NOT mean Phase13 has been wired into Command**; the unchanged Phase11 research candidate was merely checked for continuity.

Still required before R12: integrate Arc Echo's proven physical attributes **into the existing One Command** as nonautonomous inputs, investigate the three unfinished early-turn positives (R9 #6N, R9 #10N and R11 #11Y) against independent false positives, enforce original strict HF2 exchange+receive source ages, run chronological **candidate-owned** native-book/position lifecycle with whole-position hard executable-bid floor/Lazarus, terminal settlement/rollover and the unresolved quote-data safety halt, and audit sub-$0.20 observer-only execution. Current archives are insufficient to claim a candidate alternative P&L or real fills.

**Authority invariant:** previous 2–3 arc shapes create *anticipation context*. A **fresh** turn attempt plus current physical structure and economically valid contract quotes may eventually earn execution through **One Command**. No 'third arc must reverse,' no stale completed arc as live permission, no EMA30-only tactical override, no new independent entry veto.