# TACHYOS V9.5C — OVERNIGHT FORENSIC REVIEW

Archive:
\`runs/2026-09-21_v9_5c_leg_geometry_overnight_01\`

Frozen pushed head:
\`ce392e3eb2bc8f4a7dedb40aaf8b05cbaab6f183\`

Run:
- engine start ~2026-09-20 21:38 ET
- first paper entry 21:45:14 ET
- last archived exit 2026-09-21 08:56:24 ET
- paper only

## Executive conclusion

V9.5C proved that the Leg Geometry / dual-side architecture contains real edge, but it also exposed a severe over-segmentation problem.

The engine made money because a minority of large winners paid for a large amount of side-flip churn.

The next version should **not** replace Leg Geometry. It should stabilize it with a campaign layer, true transfer hysteresis, one-shot rollover preparation, winner-harvest state, and a real single exit choke point.

## Run statistics

| Metric | Result |
|---|---:|
| Closed trades | 281 |
| Realized P/L | +$164.67 |
| Gross profit | +$345.21 |
| Gross loss | -$180.54 |
| Profit factor | 1.91 |
| Wins | 132 |
| Losses | 133 |
| Flats | 16 |
| Win rate | 47.0% |
| Average win | +$2.615 |
| Average loss | -$1.357 |
| Median hold time | 25 sec |
| Contracts traded | 45 |

The distribution is asymmetric: the system does not need a high win rate if it preserves its large winners, but it cannot afford to donate those winners or fragment every campaign into repeated flips.

## Strategy contribution

| Strategy | Trades | P/L |
|---|---:|---:|
| V95C_LEG_GEOMETRY | 250 | +$147.568 |
| CORE | 27 | +$13.436 |
| EARLY_IMPULSE_CORE | 3 | +$4.816 |
| EXHAUSTION_HANDOFF_FLIP | 1 | -$1.150 |

The V9.5C Leg Geometry layer was the primary source of profit.

## Entry-path attribution

| Entry path | Trades | P/L | Win rate | Avg P/L |
|---|---:|---:|---:|---:|
| FAST_LEG | 104 | +$117.83 | 49.0% | +$1.133 |
| STANDARD_LEG | 18 | +$15.59 | 61.1% | +$0.866 |
| ROLLOVER_PREARM | 128 | +$14.14 | 40.6% | +$0.111 |
| Legacy/non-V95C | 31 | +$17.10 | 58.1% | +$0.552 |

### Finding

\`FAST_LEG\` is the strongest V9.5C entry path from this run.

\`ROLLOVER_PREARM\` was far too permissive. It created 128 entries but contributed only +$14.14.

Code inspection explains part of this: the pre-arm object could remain active throughout the following contract because it had no strict post-roll TTL / consume rule. Once its \`from_ticker\` differed from the new ticker, that condition remained true.

### Required repair

Rollover pre-arm should be:
- one-shot;
- short-lived after rollover;
- invalidated by target remap / failed geometry;
- consumed after its first authorized entry;
- converted to ordinary Leg Geometry authority if the new leg actually develops.

Initial paper test: approximately 36 seconds after rollover or first authorized entry, whichever comes first.

## Timing distribution

| Contract phase | Trades | P/L | Win rate |
|---|---:|---:|---:|
| First 5 min | 242 | +$142.67 | 45.0% |
| Middle 5 min | 36 | +$17.45 | 61.1% |
| Last 5 min | 3 | +$4.55 | 33.3% |

The first five minutes contained 86% of all trades. Some of the best winners also started there, so early trading itself is not the problem. The problem is repeated side declaration inside the same opening campaign.

## Campaign fragmentation

39 of 45 contracts had at least 6 trades.

Those 39 contracts contained 264 of the 281 closed trades.

Seven contracts had at least 8 trades; together they contained 63 trades but only produced +$20.68.

Worst example:
- \`KXBTC15M-26SEP210630-30\`
- 11 trades
- 7 side flips
- 5 flips occurred within 60 seconds
- median flip interval ~29 sec
- contract P/L -$8.20

Other negative high-churn examples had median side-flip intervals of 10–39 seconds.

### Trades #122–#126

In roughly the first five minutes of \`KXBTC15M-26SEP210315-15\`:

\`#122 YES -> #123 NO -> #124 YES -> #125 NO -> #126 YES\`

Approximate combined P/L:
- #122 +$3.52
- #123 -$0.54
- #124 -$3.00
- #125 +$0.78
- #126 -$0.60

Net: approximately +$0.16 from five trades.

Formation around rollover showed:
- inherited \`DESCENDING_TRIANGLE / APEX / COMPRESSION\`
- current \`ASCENDING_TRIANGLE / APEX / COMPRESSION\`
- compression 100
- no confirmed breakout
- macro remained DOWN

EMA sequence telemetry shortly afterward showed weak contracting arcs:
- UP sequence amplitude ratio ~0.095, \`CONTRACTING+LOWER+FAILED_RECOVERY_2\`
- DOWN sequence amplitude ratio ~0.311, \`CONTRACTING+EQUAL\`

Arc Voyage still held the larger voyage as DOWN and \`MATURE_WATCH\`.

This is strong evidence that #122–#126 were mostly campaign fragmentation inside compression, not five independent tactical legs.

## Leg Geometry detector

V9.5C produced:
- 1,083 unique leg IDs
- median leg lifetime ~23.5 sec
- 357 legs lasted under 15 sec
- 640 legs lasted under 30 sec
- only 185 lasted 60 sec or longer

State-row counts:
- RETURN_SLOPE: 14,315
- EXPANSION: 6,000
- OPPOSITE_BUILD: 5,452
- MATURE: 3,303
- EMA30_APPROACH: 328
- TRANSFER: 111

### Finding

The detector is still treating micro-return slopes as complete side transfers.

The canonical doctrine says the return slope + transfer + opposite build are one leg. The implementation instead frequently minted a new opposite leg during the return slope and then minted another one on the next reversal.

### Required architecture

Add a campaign layer above leg candidates:

\`CAMPAIGN_SIDE\`
-> \`RETURN_SLOPE_CANDIDATE\`
-> \`TRANSFER_ZONE\`
-> \`ESCAPE_CONFIRMED\`
-> only then change \`CAMPAIGN_SIDE\`

Do not mint a new confirmed leg ID simply because the return-slope candidate survives a few seconds.

## Dual-side evidence quality

250 V9.5C entries were matched to their dual-side evidence.

### Strong evidence families

| Evidence | Trades | P/L | Win rate | Avg P/L |
|---|---:|---:|---:|---:|
| FAST_369_3 | 110 | +$143.34 | 55.5% | +$1.303 |
| STRUCTURAL_BIAS | 119 | +$100.63 | 47.9% | +$0.846 |
| FORMATION | 63 | +$67.91 | 49.2% | +$1.078 |
| PARENT_ALIGNED | 124 | +$90.31 | 45.2% | +$0.728 |
| PARENT_OPPOSED | 126 | +$57.25 | 46.0% | +$0.454 |
| REGEN_CONFIRMED | 126 | +$89.36 | 45.2% | +$0.709 |

The strongest single composite marker in this run was full \`FAST_369_3\` alignment.

Parent-opposed trades were still profitable, validating the decision to remove strategic-parent tactical veto.

Formation and Structural Bias both added value as evidence families, but neither should independently flip campaign side.

### Weak / caution evidence

Wick-rejection entries:
- 54 trades
- +$22.09
- 37.0% win rate

Wicks are useful supporting evidence but should not be a primary authority trigger.

Target reclaim reversal had only 4 matched entries, so the sample is too small to judge independently.

## Confirmation-clock telemetry defect

All 250 \`ENTERED\` rows in \`tachys_dual_side_authority_v9_5c.csv\` recorded arm age as zero.

This does **not** prove the code skipped confirmation, because the engine clears the arm state before writing the ENTERED telemetry row. It means the current log cannot audit the true recognition -> arm -> confirmation -> entry latency.

### Required logging repair

Record before clearing:
- first recognition timestamp
- first recognition ask
- arm timestamp
- confirmation timestamp
- entry timestamp
- recognition->arm latency
- arm->confirmation latency
- confirmation->execution latency
- first recognition ask -> execution ask repricing

## Exit authority

Whole-Leg Exit Authority telemetry:
- HOLD_RETURN_SLOPE_EXPECTED: 9,433 rows
- HOLD_LEG_DEVELOPING: 15,600 rows
- EXIT_OPPOSITE_LEG_CONFIRMED: 281 rows

Proposals observed:
- Active Treasury proposal: 3,304 rows
- Opposite leg: 200
- Target reclaim reversal: 41

### Exit reason attribution

Paper exits:

| Reason | Count | P/L |
|---|---:|---:|
| V95C_EXIT_OPPOSITE_LEG_CONFIRMED | 238 | +$23.254 |
| EARLY_TAKE_PROFIT_50 | 9 | +$84.026 |
| CORE_SWIRL_PROFIT_LOCK | 7 | +$21.670 |
| EMA9_ARC_BROKEN | 7 | -$15.080 |
| CORE_SWIRL_SNIP_TP_22_5 | 4 | +$24.020 |
| other legacy protection exits | remainder | mixed |

### Finding

The "central" gate is not yet a true single execution choke point.

When the gate says HOLD, V9.5C suppresses several legacy constants before calling inherited management.

When the gate says EXIT, inherited management may still execute first and choose a legacy exit reason. This happened around #112.

The next version should not suppress old exits indirectly through temporary constant mutation. It should centralize the actual flatten operation.

## Trade #112 — negative control

#112:
- side: NO
- entry: .21 at 02:07:17 ET
- +47.6% within ~1 sec
- +76.2% at 02:07:42
- final MFE: +85.7%
- exit: .18
- realized ROI: -14.3%
- realized P/L: -$2.13

At ~02:08:42:
- gate still held
- opposite YES leg became dominant
- YES score ~22–23
- NO score -7
- ROI was briefly still about +19%

Within roughly 0.2 sec the mark collapsed to about -14% ROI.

The gate waited for its ordinary opposite-leg confirmation and exited at 02:08:45.

### Finding

This is not evidence that ordinary 3-second opposite-leg confirmation is universally too slow.

It is evidence that a trade with very large prior MFE needs a separate winner-harvest state. Once a proven winner stalls or loses strength, the engine must not wait for the same confirmation used by an ordinary young trade.

## Trade #120 — positive control

#120:
- side YES
- entry .44 at 02:45:15 ET
- +34.1% at 02:45:16
- +40.9% at 02:45:22
- +52.3% at 02:45:34
- +61.4% at 02:46:03
- +77.3% at 02:46:12
- +90.9% at 02:46:16
- +100% at 02:46:33
- MFE +106.6%
- exit .904 at 02:47:12
- realized ROI +105.45%
- P/L +$15.776

The exit gate recognized a new NO leg around 02:47:09:
- NO score ~10–11
- YES score ~2–4

After the normal confirmation, it exited at +105.45%, giving back almost none of the peak.

### Finding

This is the positive control for Winner Harvest:

\`+75% -> fresh highs -> +90 -> +100 -> keep holding\`

The trade continued to make meaningful progress, so harvesting at +75 would have been wrong.

After +100, it remained open about 39 more seconds and added only ~5.5 percentage points beyond +100. That is the zone where plateau/harvest logic should be studied—not during the +75 -> +100 expansion.

## #120 rollover preparation

Before #120, the old contract was still decisively NO.

Rollover Rhythm saw:
- LOWER_EXPANSION
- RETURN_TO_EMA9
- later LOWER_TURN
- boundary during return/build
- remaining capacity effectively exhausted

These were useful "current NO / prepare next YES" clues.

War Council at T-30 / T-9 / T-3 remained:
- YES score 0
- NO score 15
- WAIT_CONFIRMATION NO
- TARGET_ACCEPTED_NO
- macro DOWN

Whispers showed \`REVERSAL_ARMED\` but no directional release.

Formation remained a falling-channel/down structure through rollover and only later marked the current formation FAILED/REVERSAL.

### Finding

For **next-leg preparation**, promote Rollover Rhythm / Time Capacity / Leg extension evidence above old War Council and Formation directional calls.

War Council was describing the current contract correctly, but it was not a good predictor of the next leg.

## Rollover observer promotion board

### Promote / integrate

**Rollover Rhythm**
- strong timing/context value
- useful for LOWER_TURN / UPPER_TURN and return-to-spine preparation
- should feed NEXT_LEG_PREP, not direct execution

**Arc Voyage**
- valuable campaign continuity
- during #122–126 it still described the larger DOWN voyage across contracts
- should help prevent micro-leg side flipping

**EMA Sequences**
- useful for detecting tiny contracting failed-recovery arcs
- should help classify counter-arcs as weak substructure rather than new campaigns

**Formation**
- useful as compression/release/failure context
- particularly valuable as anti-churn evidence when APEX/COMPRESSION persists
- should not independently determine side

**Structural Bias**
- strong contributing evidence in matched trades
- keep active inside composites

**FAST 3/6/9 alignment**
- strongest measured evidence family in this run
- should have priority in fast authorization and escape confirmation

### Keep as context / shadow

**War Council**
- good current-contract battlefield description
- too anchored to current side for next-leg prediction
- no direct next-leg authority

**Reentry Watch**
- useful battlefield memory
- in churn it rapidly cycled TERRITORY_RECLAIMED / NEW_THESIS_CANDIDATE / RECLAMATION_STIRRING
- must not directly authorize fresh trades

**Wick rejection**
- supporting evidence only

### Repair before further authority

**Rollover Prearm**
- remove persistent execution authority
- one-shot TTL and consume semantics required

**Target reclaim reversal**
- add hysteresis / acceptance duration around the settlement line
- do not let repeated target sign changes create repeated leg IDs

**Legacy exit branches**
- no independent execution path after Whole-Leg gate is introduced

## Winner Harvest specification from this run

Do not install a rigid +50% trailing floor.

Use state:

\`WINNER_EXPANDING\`
-> \`WINNER_HARVEST_WATCH\`
-> either \`WINNER_BREAKOUT_CONTINUE\`
or \`WINNER_PLATEAU_EXIT\`

At MFE >= +50:
- arm harvest awareness
- do not exit if fresh MFE highs continue
- reset plateau timer on meaningful new high / healthy expansion

Initial paper test:
- no meaningful new high for ~9 sec
- plus weakening 3/6/9 displacement / quote velocity / target progress / leg maturity
- then authorize harvest

At >= +75:
- still allow fresh expansion
- weight plateau evidence more heavily

#120 proves expansion must be allowed.
#112 proves plateau/decay cannot be ignored.

## Final-minute settlement mode

The live review found brief target crosses inside the final minute that behaved as fakeouts.

Required distinction:
- target touch
- unconfirmed cross
- reclaim fakeout
- accepted side
- terminal settlement control

Final-minute weighting:
1. seconds left
2. Target Height
3. reclaim speed / hold time
4. active campaign/leg
5. 3/6/9 displacement
6. wick/candle rejection
7. Kalshi value
8. strategic parent as context only

## Parallel transition

Current V9.5C blocks a new entry whenever any position is already open for the ticker.

That prevents the requested behavior:

\`old position still open + new opposite leg confirmed -> open opposite position now\`

Next paper revision should permit one position per side during a confirmed transition and manage the two independently.

This is not automatic hedging; the new side must earn normal authority.

## Exact next-version build order

1. **Campaign Authority**
   - persistent campaign_id / campaign_side
   - do not change campaign on every candidate leg

2. **Leg Candidate vs Confirmed Leg**
   - return slope becomes candidate evidence
   - transfer/escape confirms new side

3. **Transfer-zone hysteresis**
   - 6-sec directional persistence + aligned 3/6/9
   - 9-sec side-flip hysteresis after confirmation
   - most-likely-side bias remains sticky until real invalidation

4. **Rollover Prearm repair**
   - one-shot
   - ~36-sec post-roll TTL for initial paper test
   - consume after first entry
   - invalidate on failed remap

5. **Next-Leg Prep state**
   - CURRENT_CONTRACT_SIDE separate from NEXT_LEG_PREP_SIDE
   - high-conviction alert before rollover

6. **Winner Harvest**
   - preserve #120-style strength
   - harvest #112-style stall/decay

7. **True central exit choke point**
   - all ordinary exit proposals route into one executor
   - legacy reasons cannot flatten independently

8. **Parallel opposite position**
   - one live position per side during confirmed transition
   - independent P/L and exit gates

9. **Telemetry repair**
   - preserve recognition/arm/confirmation timestamps before state clear
   - campaign IDs, flip counts, true-transfer flag

10. **Replay tests**
    - #112 winner donation
    - #120 +75 -> +100 strength
    - #122–126 campaign fragmentation
    - worst 11-trade contract
    - final-minute target fakeout
    - pre-roll current-side NO / next-leg YES case

## Bottom line

V9.5C should not be discarded.

It proved three important things:

1. Leg Geometry can find profitable early moves.
2. Dual-side authority works even against the strategic parent.
3. Large winners can carry a sub-50% hit rate to strong positive expectancy.

But the implementation still confuses **candidate leg motion** with **confirmed campaign transfer**.

The next revision should be less eager to rename the battlefield and more willing to stay with the most-likely campaign until real separation proves a new side.
