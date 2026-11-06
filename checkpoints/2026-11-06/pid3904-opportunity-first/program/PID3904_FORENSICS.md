# PID3904 — source-time forensic findings

## Result and scope

The original PAPER ledger contains **eight completed whole-lot trades**, not six. Independently recomputing every trade and both fees produces **gross −$54.6094, fees $12.30, net −$66.9094**, and final cash **$933.0906** from $1,000. All eight positions are closed. The earlier six-trade account omitted trade #1 (Heist NO) and trade #5 (Heist YES). The two Mountain NOs are actual ledger IDs **2 and 3**, the two Rail YESs IDs **4 and 6**, and the two late losing Heist YESs IDs **7 and 8**.

This report diagnoses original source-time admissions and exits. It does not assert that the proposed engine made trades, saved these losses, earned alternate profit, or would have filled at an observed price. The original records identify their execution model as `CONSERVATIVE_INTEGER_NATIVE_DEPTH_PAPER_MODEL` and explicitly set `venue_fill_claim=false`.

Sources: `original/TOOL_RACK_PAPER_20261106T121055Z_PID3904/PAPER_LEDGER.json`, `CAPTURE_STATUS.json`, `decisions.jsonl`, plus the supplied `program/strategy_core` source. Exact hashes and calculations are in `PID3904_TRADE_AUDIT.json` and `PID3904_SOURCE_ANCHORS.json`.

## Independent trade and fee reconciliation

All times below are America/New_York, 2026-11-06 (UTC−05:00). Prices are dollars per contract. Exit prices are modeled executable full-lot averages, including the weighted #5 exit, rather than promised prices or historic high watermarks.

| ID | Side / tool | Entry ET | Exit ET | Qty | Entry → exit | Entry + exit fees | Gross | Net | Entry / exit source sequence |
|---:|---|---|---|---:|---|---|---:|---:|---|
| 1 | NO Heist | 07:15:32.618 | 07:21:40.488 | 25 | 0.3800 → 0.1300 | 0.42 + 0.20 | -6.2500 | -6.8700 | 1082 / 2504 |
| 2 | NO Mountain native | 07:23:37.174 | 07:24:39.914 | 668 | 0.0350 → 0.0120 | 1.58 + 0.56 | -15.3640 | -17.5040 | 2932 / 3142 |
| 3 | NO Mountain native | 07:24:56.041 | 07:27:56.311 | 2337 | 0.0100 → 0.0020 | 1.62 + 0.33 | -18.6960 | -20.6460 | 3192 / 3723 |
| 4 | YES Rail | 07:30:52.817 | 07:31:57.564 | 61 | 0.3900 → 0.3400 | 1.02 + 0.96 | -3.0500 | -5.0300 | 4291 / 4428 |
| 5 | YES Heist | 07:35:25.820 | 07:36:49.835 | 148 | 0.0630 → 0.0827 | 0.62 + 0.79 | 2.9156 | 1.5056 | 4928 / 5085 |
| 6 | YES Rail | 07:40:20.549 | 07:40:29.622 | 235 | 0.1000 → 0.1000 | 1.49 + 1.49 | 0.0000 | -2.9800 | 5508 / 5522 |
| 7 | YES Heist | 07:47:42.236 | 07:49:34.279 | 23 | 0.4000 → 0.1500 | 0.39 + 0.21 | -5.7500 | -6.3500 | 6295 / 6446 |
| 8 | YES Heist | 07:49:48.568 | 07:54:36.617 | 55 | 0.1700 → 0.0170 | 0.55 + 0.07 | -8.4150 | -9.0350 | 6466 / 6840 |

The independent arithmetic is `qty × (exit_price − entry_price) − entry_fee − exit_fee`. Each of the **16** individual recorded fees also matches `ceil_cent(0.07 × qty × price × (1 − price))`. The sum of all net results equals final cash minus starting cash. These are Decimal calculations, without float-rounding substitutions.

Exit reasons:

- #1, #2, #7, #8: `LAZARUS_HARD_ADVERSE_STRUCTURE`.
- #3: `COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT`.
- #4, #6: `COMMANDER_MOUNTAIN_ONLY_HELD_LEG_TERMINAL_EDGE`.
- #5: `ALREADY_ARMED_EXECUTABLE_BID_FLOOR`.

#5 had a recorded peak bid of 0.089 and committed floor 0.086330, but its actual modeled full-lot exit was 0.0827. Treating the floor as a guaranteed 0.086330 sale would be invented execution. The other seven positions had no committed floor. A favorable peak alone does not prove an authorized floor should have armed, or that the full lot could have exited there.

## Capture completeness and what was preserved

Capture status reports **6,965 accepted, 6,965 written, zero dropped, complete and replay ready**, ending `PAPER_ENTRY_WINDOW_COMPLETE_FLAT`. The decision journal has **6,963 decisions**, from 07:10:58.012 to 07:55:58.035 ET. Tape calls and journal decision counts are distinct quantities; the two-count difference alone is not evidence of dropped capture.

Original archive SHA256: `ef711c357a903e0c39d20b2b9179d8c8b7aa00a2ba8febb8f89ed716261d78b6`.

Decision journal SHA256: `da03d3ff02f8d718670212d93606df39a126f70a65b96d26a360776c108e4506`.

Exact event-linked source frames precede ledger events by approximately 0.02–0.59 seconds. The fixtures retain original timestamps, row hashes, complete physical metadata, native depth, source-current receipts, mission context, parent identities, target context, and original decisions. Outcomes belong in the separate audit, not in admission inputs.

## Chronological diagnosis

### 07:15:32 — #1 is a real repeated box with a weak trigger

Source sequence **1082** is different from the late wide-only Heist cases. Repeatability proof says **classic=true, wide=false, lower visits 2, upper visits 3, center traversals 4**, over 179.43 seconds. The box was 75987.33–76030.39. This is useful positive evidence for preserving genuine Heist geometry.

It is not a blanket positive entry fixture. Entry occurred **32.60 seconds into the contract**, and the current return was only **BTC6 −0.01, EMA9_6 −0.002**; BTC9 was +5.39 and BTC30 +27.39. A minuscule sign change at a real wall can satisfy the current return predicate. Opening authority and a current, meaningful return still require separate examination. This trade lost $6.87, but that outcome is not the reason to question the trigger.

### 07:20:00 — an aligned opportunity review exists before the expensive late window

Sequence **2121** is an explicit review point: YES ask **0.62**, UP descriptive parent **E000A000004** age **291.43 seconds**, `parent_turning_or_flat=false`, `parent_terminal_ready=false`, logical parent **P000L000002 YES**, and BTC **76048.93** versus target **76015.35**. TP context says `STARTING_LEG_FAVORED YES`. No original candidate is recorded on that frame.

This supports adding a positive MAIN opportunity review at current physical opportunities. It does **not** by itself prove a qualified missed fill. The engine still has to establish the specific pullback/value-join or Release shape, admissible price tier, risk/custody capacity, and executable full-lot economics. In particular, MAIN must not buy simply because it agrees with a direction label. The earlier cheapest aligned YES observation, sequence1577 at07:17:39, costs0.52 but has target ownership unresolved and a turning parent; it is less decisive.

### 07:23:37 and 07:24:56 — #2 and #3 are local counterturns against one living UP parent

The native Commander route created both entries as `COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN`. At the two entry frames:

| Evidence | #2 / seq2932 | #3 / seq3192 |
|---|---:|---:|
| NO ask | 0.035 | 0.010 |
| Seconds remaining | 382.95 | 304.10 |
| BTC | 76131.47 | 76208.85 |
| Target | 76015.35 | 76015.35 |
| BTC travel back to target | 116.12 | 193.50 |
| Current child | G000A000015 UP | G000A000015 UP |
| Current child age | 80.14 s | 159.13 s |
| Current child EMA9 amplitude | 28.15 | 61.66 |
| Parent | E000A000004 YES UP | E000A000004 YES UP |
| Parent phase / age | EXPANDING / 508.44 s | EXPANDING / 587.44 s |
| Parent terminal / turning | false / false | false / false |
| Blocks child reversal | true | true |
| BTC6 / BTC30 / BTC60 | −6.86 / +19.61 / +26.39 | −1.42 / +24.64 / +39.99 |
| EMA9_6 / EMA9_30 / EMA9_60 | −1.372 / +3.922 / +15.592 | −0.284 / +4.928 / +25.630 |
| Gap lifecycle | SPROUT | SPROUT |
| TP ownership | STARTING_LEG_FAVORED YES | STARTING_LEG_FAVORED YES |

For both, local `mature_edge`, `edge_window_active`, `terminal_evidence_qualified`, `primary_collection_terminal_qualified`, `stall`, `hesitation`, `failed_reextension`, and `meaningful_retreat` are false. The emitted intent’s `full_leg_scale_evidence` and `completed_minute_parent_reference` dictionaries are empty. The logical parent is **P000L000002 YES ACTIVE** throughout.

This is sufficient source-time reason to reject ordinary parent-scale Mountain reversal admission. A cheap NO and a brief negative six-second move do not show that the continuing UP parent has completed.

#3 occurs only **16.127 seconds after #2’s exit**. It retains the same parent and child IDs but uses a newer extreme timestamp, producing a new physical mission/opportunity ID. New local extrema must not automatically grant a fresh independent opposite mission within the same continuing parent.

### 07:30:52 and 07:31:57 — #4 combines a questionable opening join and local-edge exit

Rail #4 entered YES at0.39 in the first52.72seconds. The inherited UP parent was approximately943.7seconds old and already `CREST_FORMING` / turning, although its parent-terminal flag was false. BTC was **34.65 below the new target**, BTC30 was−22.46, and BTC60 was−27.26. That makes admission itself a useful inherited-opening/actual-retreat review; do not describe the trade as unquestionably healthy Rail custody.

At exit sequence4428, a child edge born after the entry satisfies held-leg terminal collection while the descriptive parent remains `parent_terminal_ready=false`. The parent is crest-forming and turning at age1008.63seconds. The exit at0.34 loses$5.03 net. This demonstrates the need to distinguish local collection from actual parent termination, but the source does not prove that holding this trade would have earned a profit.

### 07:35:25 and 07:36:49 — #5 is a profitable negative-quality control

Heist #5 entered YES at0.063 and exited through its already committed floor at modeled0.0827. It earned$1.5056 net. Yet its box proof is **classic=false / wide=true**, with only **one lower visit, one upper visit, two center traversals**. Its profitability cannot be used to endorse the wide-only entry predicate. Keep its actual execution/floor behavior as a separate preservation case.

### 07:40:20 and 07:40:29 — #6 is the clearest premature local-terminal collection

Rail #6 entered YES at0.10 and exited at0.10 after **9.073 seconds**, paying$2.98 in round-trip fees. At exit sequence5522:

- The living UP parent E000A000008 remains **BUILDING**, age54.52seconds, EMA9 amplitude12.06.
- `parent_terminal_ready=false` and `parent_turning_or_flat=false`.
- A new child edge produces `held_leg_terminal=true` in custody evidence.
- The recorded comparable-development ratios are below maturity; opposing Release is not present.
- There is no committed floor, current gross profit is zero, and modeled fee-adjusted collection is negative.

A new child-edge timestamp can therefore strip the aligned lot even while its parent evidence remains developing. This is the focused custody regression: a local edge alone must not authorize collection of a Rail/Release owner. Existing floor, genuine hard adverse structure, target/finality, and actual parent termination remain independent authorities.

Admission and custody remain separate questions. This Rail label was attached to a young45.93second parent at entry, with BTC84.20 below target and279.73seconds left. Preventing the local-edge exit does not establish that the initial acquisition was already a fully qualified mature Rail or that settlement would favor YES.

### 07:47:42 and 07:49:48 — #7 and #8 are wide-only pseudo-range entries

Both Heist YESs are taken against logical parent **P000L000008 NO** and descriptive parent **E000A000011 DOWN / EXPANDING**, with parent terminal and turning flags false.

| Evidence | #7 / seq6295 | #8 / seq6466 |
|---|---:|---:|
| YES ask | 0.40 | 0.17 |
| Parent age | 101.29 s | 227.34 s |
| Parent EMA9 amplitude | 19.32 | 60.73 |
| Classic / wide proof | false / true | false / true |
| Lower / upper / center counts | 2 / 1 / 3 | 2 / 1 / 3 |
| Proof span | 539.06 s | 1799.19 s |
| Box lower → upper | 76039.12 → 76173.88 | 75971.33 → 76256.44 |
| BTC6 / BTC60 | +13.49 / −7.01 | +1.36 / −24.10 |
| EMA9_6 / EMA9_60 | +2.698 / −5.024 | +0.272 / −19.521 |
| BTC below target | 41.38 | 110.64 |

The long window and broadening bounds combine directional swings into a box. One upper visit is not repeated two-wall behavior. #7 has **local Mountain terminal/maturity flags true**, but parent-scale terminal remains false; this is precisely why scales must be kept distinct. #8 has no local maturity/terminal proof either.

#8 is entered14.288seconds after #7 closes. The second return is only a tiny positive six-second movement amid continuing negative60second movement. Neither an updated lower excursion ID nor the cheaper quote supplies parent reversal proof.

## Exact weak predicates in the supplied baseline

These anchors refer to the original extracted `program/strategy_core` tree; hashes are supplied so comparisons are unambiguous.

| Source / function | Source-time failure mechanism | Required distinction |
|---|---|---|
| `commander_candidates.py::_physical_entry_candidates`, extended Mountain branch (near observed_parent_scale) | Current child age≥45s and extreme age≥15s, matching child identity and fresh source, are ORed into `current_parent_scale`. The current child can therefore stand in for parent-scale maturity. | Require an actual parent-scale extreme/comparison or genuine Release proof; a child’s elapsed seconds do not complete its parent. |
| `commander_candidates.py::_first_counterfade_has_reversal_proof` | Positive/negative sign of short6/9second BTC plus EMA9 passes independently of true terminal proof. | Meaningful current counterturn at the correct scale/location; short signs can support timing after positive setup qualification. |
| `commander_candidates.py::_counter_parent_return_briefing_ready` | ReturnsTrue before the developed-parent checks when the gap stage isSPROUT. Both #2/#3 have that stage despite clear currentUPparent andTPsupport. | Current living-parent quality cannot depend only on the gap’s age label. |
| `commander_candidates.py::_late_counter_return_has_runway` | ReturnsTrue whenever more than120seconds remain. Both return targets are already116–193BTC dollars away. | Time remaining and actual target displacement/travel capacity need joint review; price is not runway. |
| `commander_candidates.py::positive_candidate_matches_continuation` | Opposite entry can qualify via `(extended and ask<=0.05)` before observed weakness. | Cheapness must not replace parent terminal/release proof. |
| Extended Mountain emitted metadata | Writes `return_runway.fast_return_override=true` with basis `OPERATOR_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20`, rather than recording measured attainable target travel. | Do not treat a self-authored exception flag as physical proof. |
| `detectors/heist_geometry.py`, wide qualification | `tight_box` is true in that branch; wall count can be1/1 and motion calmness can be met relative to a very broad full range. | Require repeated two-wall structure and distinguish a sideways range from multiple directional parent legs. |
| `tools/heist.py`, parallel return | Uses briefBTC6+EMA9_6 signs; parallel environment can create return eligibility outside strict classic qualification. A stalled wide edge can also qualify after enough history. | Environment, repeated wall proof, current excursion and actual return must all be positive. |
| `mission_policy.py`, `parallel_heist_return` | Promotes mission classification to qualified from parallel flags, current source, matchingbox, and nonemptybounds, without rebuilding repeated-wall proof. | The central Commander must apply one physical quality standard to both native and specialist routes. |
| `commander.py::_later_tactical_heist_pause_exemption` | A calibrated tactical flag, current qualifiedbox and matchingvisit can exempt a later Heist from the oldpause; does not distinguish classic vswide-only proof. | A repeat exception cannot confer physical quality that the current source lacks. |
| `custody_evidence.py`, `held_terminal` and final COLLECT branch | A postentry localMountain terminal matchingheldside can trigger collection before the comparable-developing HOLD branch, includingRAIL. | Distinguish local pullback/harvest from termination of the actual parent owner; preserve committed floors. |
| `tp_geometry.py::build_tp_geometry` | `shape_progress<1` assigns `STARTING_LEG_FAVORED` toparent before testing actualBTC/target side. | This is descriptive evidence, not proof that target is already on that side. Review actual targetdistance. |

Read-only predicate checks on original #2/#3 input frames confirm `_first_counterfade_has_reversal_proof`, `_counter_parent_return_briefing_ready`, `_late_counter_return_has_runway`, and `_established_parent_transfer_ready` all returnTrue, and `physical_entry_candidates` emits the sameNO entryreason. At the same time `ema9_continuation_precedent` is qualifiedYES on `FRESH_SAME_SIDE_EMA9_SPROUT`. This is a reproducible contradictory admission path. The checks invoke pure baseline functions only and are **not an exact engine replay**.

## What the tape can and cannot establish about missed EMA9 alignment

The exhaustive screen below covers every original journal row with `physical_current=true` and contract age450–780seconds. It uses actual BTC versus target separately from parent direction. It is a necessary-condition screen, not a setup classifier, calibrated forecast, or fill simulation. The0800 contract is observed only through07:55:58, so its late window is censored by run end.

| Contract | Parent side | BTC on that side of target? | Source rows | Cheapest observed aligned ask | Sequence at minimum |
|---|---|---|---:|---:|---:|
| 0730 | YES | yes | 1041 | 0.850 | 2693 |
| 0745 | NO | yes | 196 | 0.906 | 5169 |
| 0745 | YES | no | 421 | 0.012 | 5785 |
| 0800 | NO | yes | 290 | 0.938 | 6712 |

The favorable-parent/favorable-target side was expensive in these later windows. The proposal explicitly rejects buying0.80–0.95 merely to ensure aligned exposure. Therefore these observations do not support a claim that the engine missed a large set of affordable late aligned winners.

The0.012YES quote in0745 is cheap because BTC remains107.09below target with120.60seconds left. Its TP label still says `STARTING_LEG_FAVORED YES` through the immature comparable-shape branch. This is a negative control for target-label overreach, not a cheap positive entry.

Potential earlier review points are preserved in separate source frames:

- **seq2121**,07:20:00,YES0.62: currentUPparent and actualBTC/target alignment, no originalcandidate. Best explicit MAIN review point in this scan; qualification still needs the entry shape, economics and capacity.
- **seq1577**,07:17:39,YES0.52: parent turning andTP unresolved; no automatic positive expectation.
- **seq6155**,07:46:13.319,YES0.53: currentUPparent but only73seconds into a newcontract; earlyentry/release proof needed.
- **seq6156**,07:46:13.869,NO0.48: `current_geometry.parent_direction=DOWN` while the Mountain and logicalparent remainYES, BTC only1.19belowtarget. This is a parent-identity conflict to reconcile, not a provenNO join.
- **seq4644/5093**,NO0.79/0.88 in0745, and **seq6482**,NO0.85 in0800: price/runway must remain decisive; direction agreement alone is insufficient.

A reliable qualified-alignment participation metric needs the revised positive quality decision and precise no-entryreason logged at every physical opportunity. Retrospective price minima and eventual outcome cannot supply that missing classifier. No alternate fills or profit are calculated here.

## Fixture handoff and validation boundaries

Recommended compact inputs are **`PID3904_CASE_INPUTS.json.gz`**,27 original sourceframes without outcome labels, and **`PID3904_CASE_ANNOTATIONS.json`**, which supplies expected semantic distinctions and compact scalar evidence. Use every relevant originalmetadata field when reconstructing `MarketSnapshot`; do not replace contradictory metadata with idealized test values.

Also provided:

- `pid3904_entry_exit_frames.json.gz`:16 exact event-linked originalframes plus eventmapping.
- `pid3904_alignment_review_frames.json.gz`:11 exact opportunity/price reviewframes.
- `pid3904_source_frames.json.gz`:1841 periodic and event-adjacent originalframes, including every originaldecision within±25seconds of entries/exits.
- `pid3904_compact_sequence.json.gz`:all6963 chronological decision summaries.
- `pid3904_recorded_candidates.json.gz`:332proposal-bearing source rows.
- `PID3904_TRADE_AUDIT.json`:independent trade arithmetic and16feechecks.
- `PID3904_BASELINE_PREDICATE_CHECKS.json`:read-only baseline predicate results.
- `PID3904_ALIGNMENT_SCREEN.json`:all-row directional/target economics screen.
- `rail_exit_frames.json`:the two detailed Rail exitframes and intents.

The selected frames are sparse evidence cases, not a substitute for replaying full chronological engineinput in a matching environment. A passing negative-case gate only establishes source-bound selectivity on that input. It does not prove new candidate coverage, sequence memory, profitable custody, or successful fill behavior over the full run. The original source tree was not edited by this forensic task.
