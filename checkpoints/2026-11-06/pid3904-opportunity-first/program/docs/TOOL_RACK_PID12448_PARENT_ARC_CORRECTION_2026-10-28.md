# PID12448 — entry, full-arc and contract-collection correction

**Release:** `TOOL_RACK_PID12448_ARC_CONTRACT_PAPER_20261028`  
**Dashboard:** `TOOL_RACK_NAUTILUS_TV_V10_ARC_CONTRACT`  
**Date:** 28 October 2026. Recorded market times in this report are America/New_York.

**Status: REVIEW REQUIRED before another market-fed run.** The corrected candidate now takes the large missed peak and preserves specific holding rules, but the complete recording exposes remaining entry and management limits. The standalone Windows package and Nautilus are prepared for review. No new market-fed session has been started, and this report does not clear the next 90-minute run.

## Recorded result

The final frozen-source replay processed all **20,535 original observations**, starting from an empty $1,000 PAPER portfolio. It committed **seven entries and three complete exits**, leaving **four unresolved or still-open positions** at the recorded horizon. The three closed positions produced **+$4.470 net**: +$7.020 gross less $2.55 of their allocated entry and exit fees. Total fees paid, including entry fees on open positions, were **$4.32**. Remaining cash was **$965.080**; cash alone is not portfolio profit because four lots remain purchased.

The original run finished flat at −$24.432 net. The corrected replay has a different, incomplete settlement state, so those two realized figures are **not a complete performance comparison**. The named entry and exit behavior below is the useful result.

| Replay trade | Entry, ET | Purpose | Actual close | Realized net |
|---|---|---|---|---:|
| #1 — 19 YES | 02:15:54 at $0.500 | MAIN_CONTRACT | 02:20:42 exit at $0.860 | +$6.330 |
| #2 — 67 NO | 02:20:42 at $0.140 | ARC_RETURN | No recorded close | Unrealized |
| #3 — 45 YES | 02:39:16 at $0.210 | TACTICAL_RETURN | 02:41:29 exit at $0.370 | +$5.930 |
| #4 — 19 YES | 02:43:18 at $0.500 | MAIN_CONTRACT | No recorded close | Unrealized |
| #5 — 28 YES | 02:47:11 at $0.330 | ARC_RETURN | No recorded close | Unrealized |
| #6 — 135 NO | 03:08:57 at $0.069 | TACTICAL_RETURN | 03:10:54 exit at $0.017 | −$7.790 |
| #7 — 25 YES | 03:15:20 at $0.380 | ARC_RETURN | No recorded close | Unrealized |

| Still-held replay lot | Contract close, ET | Last whole-lot bid | Time observed, ET | Hypothetical net at that bid |
|---|---|---:|---|---:|
| #2 — 67 NO | 02:30:00 | $0.999 | 02:29:59 | +$56.973 |
| #4 — 19 YES | 02:45:00 | $0.001 | 02:44:41 | −$9.831 |
| #5 — 28 YES | 03:00:00 | $0.001 | 02:59:11 | −$9.662 |
| #7 — 25 YES | 03:30:00 | $0.975 | 03:28:41 | +$14.405 |

An unsold bid is not realized profit or an official settlement. Marks for different contracts were observed at different times and must not be added into a portfolio profit figure. The only official results available to this replay are those actually captured in the original archive. A counterfactual holding in another contract remains unresolved when that contract's official result is absent.

### The large upper arc

At **02:20:42.648 ET**, the corrected pipeline closed its **19 YES at $0.860** for **+$6.33 net**, then purchased **67 NO at $0.140** for the full return. This was a real paper-ledger handoff through the tool, mission policy, Commander and writer. The observed whole-parent peak region qualified before the eventual maximum at 02:22:32.230; the detector did not require the outgoing EMA9 to turn first or a 40% tactical projection.

The later $0.110 NO ask was not known at entry. This establishes an entry within the broad upper region, not capture of the future cheapest quote. The NO holding survived the outgoing-leg release that had wrongly closed it in a superseded candidate. Its later last executable full-lot bid was $0.999, corresponding to **+$56.973 hypothetical net after modeled fees**. That was an unsold quote observation: no 02:30 official result was present in the archive, so this replay leaves the lot unresolved and books none of that amount.

![Actual recorded upper arc, committed orders and exact-contract quotes](figures/pid12448_0230_final_replay.png)

The figure uses recorded BTC/EMA observations and the exact 02:30 contract's native book. Gaps remain gaps. Filled markers identify actual replay orders; a hollow final-bid marker is an unsold observation. The later absolute cheapest ask and highest sale bid were not inputs to the strategy.

### Remaining opportunities and limits

1. **Earlier upside participation remains incomplete.** The original two early NO entries are prevented. That does not prove the intended cheaper YES entry was captured; no replacement YES trade occurred in those original entry regions. At the two old entry frames the current YES asks were already $0.54 and $0.75, so the finding is a missed earlier opportunity, not an instruction to buy those expensive quotes.

2. **The $0.21 YES return is now managed as the small swing it actually qualified for.** Replay #3 holds at the original premature-sale frame despite reaching EMA9. It sells its complete 45 contracts at $0.37 only after the admitted incoming local leg travels $24.66 and retreats $6.77 with covered current rejection. The holding lasts 132.13 seconds, about one minute longer than the original, and still realizes +$5.93 net. Its highest executable bid while actually held was $0.48, supporting a hypothetical +$10.83 net. The later $0.59 quote occurred after the position closed; the local-end proof does not establish that the whole later upswing was captured.

3. **A later MAIN entry still deserves correction or a clearer rule.** Replay #4 buys 19 YES at $0.50 with only 101.86 seconds until expiry. It has an observed early upward parent and conditional YES contract scenarios, rather than the removed EMA-contact shortcut. However, source qualification alone does not establish a good early, cheap entry. Its highest executable $0.59 bid supported only +$1.04 net on this 19-contract lot; its last bid was $0.001. The current MAIN path does not require observed completion/runway evidence, and its conditional forecast is not a promised settlement. This remains an entry-quality and contract-fit review item.

4. **Another full-return holding lacks verified ownership after interruption.** Replay #5 buys 28 YES at $0.33. Its anticipated parent invalidates, and later current YES geometry does not have the same-side rack reacquisition evidence required to adopt it: the rack still owns a NO rail. The held scope remains UNKNOWN for 915 pre-expiry reviews and cannot use ordinary held-parent completion. A $0.47 full-lot bid offered a hypothetical +$2.99 net while management remained unverified; its last bid was $0.001. This is distinct from the earlier bug that ignored an explicit valid same-side reacquisition. The generic feed phrase `MOUNTAIN_CARRY_LIVING_LEG` is misleading in that unknown-scope state. This continuity and ownership limitation remains open; a missing source cannot be filled with invented custody.

5. **The later tactical fade still loses.** Replay #6 buys 135 NO at $0.069 against the upward parent as an explicit small `TACTICAL_RETURN`. Its conditional quote model clears the 40% admission screen, but the anticipated drop fails. The observed upward arc breaks its frozen entry boundary persistently; it exits the full lot at $0.017 after 117.01 seconds for **−$7.79 net**. Its highest held full-lot bid, $0.08, offered only +$0.175 net after both fees. This is a structural entry-failure sale, not first-slowdown profit taking, a fabricated third weakness or a timer exit. Correct rule execution does not prove a good reversal forecast.

6. **The later upper plateau is still unused for a full return.** In the 03:08–03:13 region, the saved trace contains 823 physically current observations: **zero full-ARC NO qualifications**, 11 local-return classifications and 812 unresolved classifications. The later $80,826.74 BTC high first appears at 03:10:54, when #6 is sold, and recurs through 03:12:07. At the first observation of that higher plateau, both independent full-leg maturity checks were false. No full-parent entry route qualifies anywhere in the reviewed region. After the tactical sale the tool also reports a consumed attempt. The original earlier local NO entry cannot be counted as successfully detecting and entering this higher peak. The detailed observation is retained in the evidence bundle as `UPPER_0310_REVIEW`.

The profitable contract-interruption exception is supported by the separately authored fresh-entry controls. It must not be credited with a historical exit unless the final replay actually commits that authority. Earlier original lots are not retroactively granted the new immutable entry provenance.

**Advice before the next run:** correct full-leg recognition at the later upper plateau, resolve the late MAIN entry policy and the unknown-held-parent management path, then check those exact recorded regions. Preserve the verified large-peak handoff and early-weakness holds. Do not interpret the positive closed-trade subtotal or nineteen passing synthetic cases as clearance for another market-fed experiment. The broader loser-to-settlement redesign remains deferred as requested.

These results establish specific recognition, entry and management behavior on this recording. They do not establish that every visual arc is recognized, that every qualifying entry is profitable, or that the bot knows the future cheapest quote. A source-level denial is reported separately from a trade merely being blocked by existing inventory.

## What was wrong and what changed

| Finding | Correction |
|---|---|
| The full parent existed, but its compatible completed history did not reach the turn detector. A younger local child could dominate the decision. | Preserve completed received-parent history and a separate completed-minute comparison family. Pass the exact current parent geometry through Mountain, mission policy and Commander. |
| EMA9 proximity could authorize a new MAIN trade after a substantial return had already begun. | Require an observed early parent, independently qualified release, earned rollover continuation or a separately qualified Rail value location. EMA contact, empty inventory and a new ticker do not create an entry. |
| A paired-gap fallback stayed eligible after price had moved well away from the peak or valley. | Apply the same current parent-scale extreme region to every full-parent entry route, including both retest routes. Keep collection/end evidence available after new entry becomes too late. |
| One matching old peak-gap pair and a short flat print could label a small internal swing a full ARC. | Require independent current received-parent maturity or completed-minute maturity for the paired-gap full-ARC alternative. Otherwise retain LOCAL_RETURN and its own tactical rules. |
| The outgoing leg's release could cancel a newly purchased full return. | An opposing-release exit must prove completion of the exact held return. A real failure of its frozen boundary remains a separate persistent structural exit. |
| A purchased return could lose usable management after its anticipated scope was invalidated and observations were interrupted. | Permit a causal holding-only link to a genuinely observed return. Preserve the original invalidation, entry, quantity, fees and frozen boundary. Carry the paid opportunity forward so an ID change cannot authorize another purchase. |
| A small counter-swing could use the wrong direction label and a distant box destination. | Use covered current EMA9 motion for Heist alignment. Freeze the relevant first EMA9 destination for an internal counter-swing; preserve the opposite wall for a genuinely neutral box. |
| A tactical position could sell at first EMA contact while its purchased return was still advancing. | Require observed favorable travel and evidence that the purchased return is ending, with a profitable complete-lot sale at remaining native depth. The 40% rule remains admission economics. |
| A profitable full return could exhaust its contract before its ordinary third-weakness collection. | Add a separately named profitable contract interruption with current weakness, actual bid giveback, frozen comparable timing and a positive full-lot execution check. It does not fabricate a terminal or third weakness. |

The governing rules are recorded in [Strategy Backbone version 2026-10-28.6](../TACHYOS_STRATEGY_BACKBONE_V1.md). This remains the standalone Tool Rack, with one Commander and one passive PAPER ledger. R22 is a historical forensic reference, not a runtime dependency.

## Entry rules retained

At an earned full mountain peak, the return side is NO; at an earned valley, it is YES. A full `ARC_RETURN` does not need agreement with the outgoing EMA9, a contract-winner forecast, a projected quote response or the small-swing 40% screen. Current executable subcent asks remain permitted within the existing price, budget and depth constraints.

This is an entry around an observed broad extreme, not a promise to know its eventual absolute minimum. The current price must remain in that parent's extreme region. A recent gap match cannot keep an old entry alive after a material return. A continuing breakout or heavy directional release remains distinct from an observed turn.

The scale correction adds no fixed ten-minute leg, eleven-candle template or opening timer. At the disputed 03:03:22 entry, short duration alone was not the defect: the recent local comparisons really included one- to two-minute swings. The defect was that **both independent current maturity checks failed**, yet the paired-gap family label bypassed the tactical screen. A small swing can still trade when its own observed opportunity and economics qualify.

For tactical entries, 40% is gross return from entry ask to an estimated sale bid, with positive modeled net dollars and the appropriate physical destination. It is not an automatic take-profit order. First EMA contact cannot collect a still-advancing tactical return merely because the destination was touched.

## Holding and profit collection

| Situation | Governing behavior |
|---|---|
| First or second distinct weakness in a living full leg | HOLD under the ordinary full-leg policy. Repeated observations of the same pause do not add weaknesses. |
| Three weaknesses, but the same parent remains alive | HOLD. Count alone does not declare the leg spent. |
| Third distinct weakness with current spent-parent evidence | Ordinary collection may qualify, subject to current execution conditions. |
| Independently proved complete smooth arc and qualified opposite full return | The existing full-arc handoff can collect and enter the return without inventing three pullbacks. |
| Exact held parent genuinely completed | Its own completion supplies the existing structural collection path. An outgoing or smaller child's terminal cannot substitute. |
| Profitable ARC with insufficient comparable contract runway, current weakness and actual bid giveback | The new `ARC_PROFITABLE_CONTRACT_INTERRUPTION` may collect the complete remaining lot. |
| Entry candle has not ended in observed source data | No new ordinary strategy sale. Existing committed floors, accepted residual exits, manual stop and official finality retain their separate paths. |

Ordinary collection and first floor arming use the same permission. Otherwise, a displayed HOLD could silently arm a floor on the first slowdown and sell immediately. Previously committed protection remains binding.

### The contract exception is bounded

The position must be a normally held full ARC with an ACTIVE, current parent and an observed origin. Its entry metadata must identify the comparison family that actually earned full-leg scale. The family is fixed at entry. Eligible timing history freezes when the incoming parent first becomes observed ACTIVE. A later valid holding adoption reuses that observed parent snapshot without enriching it with later references. Received-parent and completed-minute references remain separate. Missing or insufficient history, a future reference, an unknown origin or a continuity gap leaves this exception unavailable.

The timing comparison is:

`exact contract close < observed parent origin + shortest eligible completed same-family duration`

This is a comparison with observed history, not mathematical proof of how long the current leg must last. The reference family is not selected later to obtain a convenient result.

The current parent must have a genuine active post-entry weakness. Covered current movement must show that the purchased leg has not already resumed advancing beyond that episode's frozen threshold. Its executable full-lot bid must have given back from a bid already observed for that position. A high percentage gain, clock pressure or quote wiggle alone is insufficient.

The passive writer then independently rechecks the exact position, ticker, quote, quantity, fees and unconsumed depth. The entire remaining lot must still produce strictly positive net profit. A partial sale, break-even result, loss, stale proof or unavailable depth is rejected under this authority. Rejection does not create a pending exit, a new floor, an EXIT_PENDING custody latch or a released paid opportunity that could later produce a loss sale or duplicate entry.

MAIN positions, ordinary holdings with adequate runway, structural exits, existing floors, Lazarus and the deferred loser-to-settlement redesign retain their existing rules. The new authority does not rewrite a historical entry's purpose or add missing scale provenance to an old lot.

## What the original five trades showed

The original PID12448 run closed five positions for **−$24.432 net**, comprising **−$20.482 gross** and **$3.95 fees**. Its ending cash was **$975.568** from $1,000. The original 56 exported hashes matched, and its journal reconciled. These figures are the original ledger, not the corrected replay. See the [original recorded forensic report](TOOL_RACK_PID12448_RECORDED_FORENSICS_2026-10-28.md) and [underlying evidence](pid12448_recorded_forensics.json).

| Original trade | Entry, ET | Recorded close | Net | Finding |
|---|---|---|---:|---|
| #1 | 02:06:29 — 20 NO at $0.470 | $0.330 after 32.21 seconds | −$3.46 | Late MAIN entry after a $12.70 return from the low, beyond its $10.158 parent boundary. |
| #2 | 02:08:37 — 54 NO at $0.260 | Official YES result; NO paid $0 | −$14.77 | Counter-swing mislabeled aligned; its far box destination failed to describe the purchased opportunity. |
| #3 | 02:39:17 — 45 YES at $0.210 | $0.370 after 72.12 seconds | +$5.93 | First EMA9 contact collected an advancing local return. |
| #4 | 03:08:46 — 158 NO at $0.059 | Official YES result; NO paid $0 | −$9.942 | Effective collection boundary was almost a strike crossing before rollover. |
| #5 | 03:19:01 — 19 NO at $0.500 | $0.420 after 239.55 seconds | −$2.19 | Another late MAIN entry: a $12.81 return versus a $10.5708 parent boundary. |

For #2, a later valid whole-lot $0.45 bid would have supported **+$8.59 net**. For #3, a later valid $0.59 bid would have supported **+$15.80 net**, $9.87 above its booked gain. For #4, the best observed complete-lot $0.080 bid supported approximately **+$1.878 net**; the effective lower box boundary was $80,747.15 against a $80,747.65 target. These are observed counterfactual opportunities, not claimed executions or requirements to capture the future maximum.

The highest recorded BTC observation was **$80,895.16 at 02:22:32.230**. The declared broad upper region, 02:20:34–02:22:36.999, contained **263 fresh-entry captures** with NO ask at or below $0.15, representing **41 distinct physical observations**. NO was offered at $0.110 in that region. The later source gap did not explain the earlier missed region.

## Validation and source binding

| Evidence | Verified result | What it establishes |
|---|---|---|
| Entire original recording | 20,535 executed and durable frames; 83 sealed chunks; every original capture hash checked | Complete recorded-input and decision coverage, including source interruptions. |
| Financial journal | 191 records verified against events and the ending ledger | The seven entries, three exits, fees, cash and remaining lots are committed paper results. |
| Source parity | All 20,535 frames match archived price, EMA9, EMA30, last source time, continuity and currentness | Recomputed strategy decisions use the actual available observations rather than supplied peaks or old intents. |
| ARC Construct | 7 of 7 cases pass | Level/sloping/mirrored peaks and valleys; acceleration/quiet controls; cheap quotes including actual $0.005 paper entries. |
| Ordinary holding Construct | 6 of 6 cases pass | Hold first two weaknesses, repeated patches and three pauses in a still-living leg; proper bounded collection and handoff. |
| Contract-interruption Construct | 6 of 6 cases pass | Fresh-entry positive mirrors collect full profitable lots with insufficient runway; sufficient-runway and quote-only controls hold. |
| Focused adversarial checks | Entry family, timing snapshots, scope adoption, remaining depth, fees, stale/foreign proof and pending-exit checks pass | The new authority cannot fabricate provenance, spend the same visible depth twice or turn a missed profitable sale into a pending loss sale. |
| Actual contract-interruption sales in this recording | **0** | This recording supplies no positive execution example for that exception; its positive execution evidence is the separate Construct controls. |

The frozen production tree contains **57 Python/JSON files**, with canonical hash `a892f7c356f27b3ca055c54a599402f780e1a3fb8a3498420a7e3a4b77d2e2df`. The standalone delivery includes the exact matching **50 runtime/configuration files** and deliberately excludes seven historical R22/shadow files. Its **seven frontend assets** have separate verified hashes; UI assets are not claimed as replayed strategy code. The Nautilus DOM check also covers the new collection label without fabricating a third weakness.

The recorded acceptance has **no failed declared mechanical or integrity check**, but it retains trade-quality reviews and does not certify every intended leg or peak. The separate nineteen-case Construct gate is complete. The broader readiness verdict remains **REVIEW REQUIRED** for the concrete findings above. Archive publication separately requires the actual extracted standalone CHECK to pass.

The actual recorded replay starts with an empty $1,000 PAPER portfolio and recomputes source geometry, parent context, tools, mission policy, Commander and execution. It imports no original positions, strategy intents, detected peaks or weakness labels. The original book observations, source interruptions, completed-history knowledge times and recorded official finality remain intact. Network access is blocked.

Every executed frame must also exist in durable evidence and match its original capture hash. A superseded candidate processed all inputs but saved only 8,328 frame records; it failed acceptance. The sealed-chunk recorder verifies each closed part and rechecks the complete trace against all original captures after the writer closes. The final delivered production files must match the exact frozen replay source, not merely share a Git branch or release name.

Construct scenarios exercise authored geometry and quote conditions through the actual entry and ledger path. They do not inject positions, recognized peaks, weakness counts or timing references. The ordinary incoming holding controls cover 264 seconds after the handoff, including 18 seconds beyond EMA9 contact; they do not establish completion of an entire second leg or settlement. The six contract controls separately exercise early profitable collection, adequate-runway holding and quote-only giveback without physical weakness.

Independent verification covered all 3,483 final-written scored Construct frames and 1,671 journal records, with matching ending ledgers and modeled fill fees. Nine optional append-only decision logs contained only valid prefixes; they are explicitly excluded from full-coverage claims. The complete final-written frame arrays and verified financial journals are the retained controlled evidence. The final recorded-market replay uses the separately verified sealed-chunk trace described above.

The delivered Construct runners also tolerate missing Git metadata or an absent Git executable. That reporting-only portability fix was made after the simulations. The evidence therefore records both the exact executed harness hashes and the delivered reporting revisions; production and fixtures were unchanged, and the simulations were not rerun merely for that metadata change.

Focused component tests provide the adversarial cases for exact-zero net, shared-quote depth consumption, stale source, missing family provenance, future references, partial quantity, re-entry and pending-exit behavior. A historical held-position probe is explicitly separate from fresh admission. The old YES45 lot does not receive invented scale provenance simply to make a new exit rule apply.

The older PID7516 test fixtures likewise no longer force invalid historical entries into current MAIN positions. Current source-to-writer tests assert their proper entry denial, while separately named original-lot tests retain the first-breath and high-ROI floor regressions. The mandatory package gate includes both kinds of evidence.

The first extracted-package check exposed three stale test premises: two PID7516 assertions assumed a particular ordering of independent entry denials, and a PID10092 test attempted to bind historical #8 to a MAIN scope that current source does not earn. The corrected tests retain both spatial and scale rejection evidence and the actual no-entry writer result. PID10092 #8 explicitly rejects a forged MAIN identity; #14 retains its actually earned MAIN holding regression. These are test-premise corrections, not changes to the frozen trading source or evidence that the historical #8 now rides a full leg successfully.

### Practical limits

- Original accepted raw public trades and the original seed response are absent. The replay uses actual archived BTC/EMA observations; it does not independently rebuild those EMAs from raw exchange trades.
- Native depth is a PAPER execution model, not a venue fill guarantee. Queue position, real order latency and market impact are not simulated. Counterfactual paper trades cannot alter later recorded quotes.
- The inherited fee model is `ceil_to_cent(0.07 × quantity × price × (1 − price))`. It is an explicit model assumption, not a newly verified official fee schedule.
- The original decision time is fixed within each replay dispatch. Live within-frame processing delay is not reproduced; the executor still contains its normal source/book age checks.
- Only actually captured official outcomes are supplied. A last bid or the displayed BTC-to-target distance does not substitute for an official exact-contract result.
- This preparation does not establish Windows live-feed performance or strategy profitability. No market-fed run has been started.

## Nautilus and the delivery

Nautilus TV v10 remains bundled with the standalone engine. The narrow feed, larger TV text, enlarged positions, simplified BID/ASK cards, trade net percentages, Looking Glass and separately labelled Hurricane scenarios remain present. The separate bottom protection panel remains removed.

The new contract collection is displayed as **“Profitable return · contract closing”**, with the actual weakness count and live parent retained. It is not displayed as an invented third weakness or spent leg. The UI remains read-only.

The builder creates a per-file SHA-256 manifest, extracts the actual ZIP into a separate directory, removes checkout dependencies from its import path, and runs the mandatory CHECK there. It publishes a delivery archive only after that extracted check succeeds. The original R22 adapters and shadow runtime are excluded; the import-closure audit prevents a hidden dependency on them.

On Windows, extract the entire ZIP into a fresh writable folder and run `02_CHECK_TOOL_RACK_PAPER.cmd`. `01_START_TOOL_RACK_PAPER_90M.cmd` is the normal operator launcher. If the prior-run unresolved-inventory error appears, use `05_RECONCILE_PREVIOUS_TOOL_RACK_RUN.cmd`; it preserves the original journal and appends only verified exact-contract official settlement. Do not erase prior inventory to obtain a fresh balance.

The complete bounded evidence, declarations, source hashes, trade results and control summaries accompany this report in [pid12448_parent_arc_correction.json](pid12448_parent_arc_correction.json).
