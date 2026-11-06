# Opportunity-First Commander — implementation and evidence

2026-11-06 · PAPER only · user-facing times: America/New_York

## Release authority and readiness

This implements the user-approved Opportunity-First Commander contract after the complete PID3904 archive was restored. Read `NEXT_RUN_STATUS.json` and the **new** `OPPORTUNITY_FIRST_VALIDATION.json` for readiness. The builder cannot publish a runnable archive unless the current-source chronological admission audit, full modified-engine Construct and extracted engineering gates pass. Earlier validation reports remain historical records; they are not evidence that this release passed.

The delivered program retains one Commander, two independent positive briefing lanes, EMA9 parent authority, EMA30 as context, whole-position execution, committed profit floors, the existing 45-minute PAPER launcher and held-position drain. This work grants no venue-order authority. Account settings, fees, native-depth execution model, credentials, installer dependencies, market discovery, source freshness implementation and Looking Glass assets are unchanged.

## Why the change was needed

PID3904 contains **eight** completed positions. Starting cash was $1,000; final cash was $933.0906. Gross realized result was −$54.6094, total fees were $12.30, and net result was −$66.9094. The previous six-trade count was incorrect. `PID3904_TRADE_AUDIT.json` reconciles all entries, exits and fees, and `PID3904_FORENSICS.md` explains the source evidence.

The two cheap NO Mountains were admitted against the same still-expanding YES parent and the same child arc. The original shortcut treated child age, a new extreme timestamp and a short opposite wobble as stronger evidence than they were. A second order followed shortly after the first loss without a distinct physical excursion. Several Heist candidates came from wide envelopes containing too few real bilateral visits. Their apparent boxes included directional market motion.

There was also an independent custody defect. Structural collection combined ownership from the MAIN mission parent with a terminal flag from a smaller local child. Rail position #6 consequently closed after 9.073 seconds while its authenticated YES parent was still developing; the flat-price round trip lost $2.98 in fees. Position #4 also mixed scales, but its parent was turning/spent and its entry was weak, so it is not presented as a healthy runner or a hypothetical winner.

The audit does not establish a large supply of cheap missed late aligned winners. Actual same-parent, same-target asks during observed ages450–780s were expensive in the three covered contracts. A descriptive `STARTING_LEG_FAVORED` label could also disagree with the numeric BTC/target relationship. Opportunity review therefore measures actual target side and distance instead of treating that label as a settlement claim.

## One positive admission contract

`strategy_core/opportunity_first.py` is an internal evidence/state component called by `OneCommander`. It has no account, executor or independent trading authority. Both native proposals and authorized specialist proposals pass its source-current physical-quality contract before the Commander's other objective and custody checks.

Every admitted intent carries `commander_opportunity`: species, current source timestamp/generation, ticker, actual parent and child identities, contract age, numeric target, required move, quote/depth context, price limit, tier, physical opportunity identity and the qualifying reason. The existing executioner remains responsible for actual modeled book/depth fills. Admission and booking are recorded separately.

| Species | Positive evidence required |
|---|---|
| MOUNTAIN_RETURN | A current terminal arc with independent comparable maturity, a current defended-level rejection, or a specifically validated smaller terminal return; current return/target runway must also be demonstrated. Cheapness and an isolated microstall do not supply maturity. |
| REAL_HEIST_RETURN | Current bounded numeric walls, repeated distinct observations at both walls and center traversals, coherent source/connection identity, actual outer location or a current measured inner return, and no current directional breakout. A wide one-pass envelope is insufficient. |
| MAIN_EMA9_REJOIN | An authenticated current EMA9 parent and a located observed parent start or actual pullback/rejoin, current directional support, value within existing limits, and numeric full-target/time feasibility. Normal MAIN begins after300s. |
| RELEASE_HANDOFF | Current measured boundary break and directional expansion with residence or failed old-owner extension, coherent confirmed transfer and sufficient target runway. A watcher label alone is not a handoff. |
| ALREADY_AUTHORIZED_ROLLOVER | The actual current opening factory must reproduce the same bounded inherited, terminal or causal pre-open opportunity. A spent old leg cannot acquire permission from its old gap label. |

Unknown or inconsistent physical source, stale proposals, unresolved TP/EMA junctions, inadequate target/runway and missing positive species remain WAIT. Advisers may observe or PREPARE without an executable order. A pending Release watch cannot veto an independently earned MAIN rejoin; a confirmed opposite transfer remains different evidence.

## Causal watch memory and contract cadence

Pronounced observed excursions create PREPARE watches with ticker, generation, parent identity, outgoing/return side, actual extreme and source time. Repeated book callbacks do not become additional physical observations. Same-child re-extension refreshes/cancels the old return thesis without manufacturing a new paid opportunity. A filled excursion remains consumed. A later physically completed retreat followed by a genuinely new observed child may form a distinct excursion under the same parent.

MAIN separately remembers observed price retreat and rejoin under the actual living parent. When the old outward high is recovered, an unused dip is spent: a later cheap mid-leg quote cannot revive it. Continuity or parent changes invalidate prior state. Fill consumption follows a BOOKED receipt, not merely an admitted intent.

The first minute remains observation except for the already-authorized earned opening species. Ages60–300s allow independently earned genuine extremes and transfers, while normal MAIN observes. After300s it actively seeks current-parent value. Ages450–780s receive explicit alignment review. The last120s require feasible economics and available time; no timer forces an order. WAIT across a whole contract is valid.

Current-source review records qualified-but-unbooked opportunities and the precise final no-entry reason, including inventory, price or execution rejection. Runtime diagnostics require an evaluation on this exact frame and matching ticker, source timestamp and continuity generation. An unrelated skipped callback cannot relabel the prior review as current. Diagnostic objects are detached and strict-JSON-safe.

## Local returns are bounded TACTICAL missions

A smaller earned return may have enough observed path and pace to reach current EMA9 without proving that the contract can win settlement. Such admission is explicitly bound to a frozen EMA9 target in a TACTICAL return mission before booking. The proof records its source and generation and says that it makes no settlement-ownership claim. It receives no increase in price cap, tier or floor privilege.

Commander consumes that mission directly during custody. Collection requires the existing authenticated postentry path and an observed end of the incoming return, or observed exhaustion at the reached frozen destination, together with a current executable full remaining lot with positive proceeds after fees. A reached but advancing target remains HOLD. Missing, stale, foreign or mixed-generation evidence cannot fall back to an unrelated child terminal. Objective floors, stops, recovery, earned promotion and tactical finality retain their earlier priority. This is exercised for native Commander lots as well as adviser-originated local returns.

Promotion requires separate current continuation/parent evidence with measured full-target runway, or a current confirmed Release. Merely retaining a historical gap label cannot silently graduate the local renter into MAIN settlement custody. Genuine real-Heist, Mountain and Release species retain their distinct existing management rules.

## Parent-scale structural collection

For MAIN Rail/Release/parent-contract positions, structural terminal collection now reads the authenticated **parent's own geometry**. Current physical status, supported parent, mission/parent/geometry source and generation, current BTC/EMA9/EMA30 measurements and parent identity must agree. A terminal edge must belong to that parent, have a finite corresponding extreme timestamp, occur after entry and not after the current source.

Missing or stale MAIN parent proof yields an explicit unverified collection HOLD, rather than falling back to a local child terminal. Genuine local positions retain local-leg evidence. A true newly observed parent terminal still permits collection. Objective floors, latched exits, manual stop, finality and prior recovery/adverse handling keep their existing ordering. `paper_execution.py` is byte-identical to PID3904.

The new exact-source custody tests use the original positions from the journal immediately before the original faulty transition. They do not erase an already-latched exit from a later position record. Separate explicitly synthetic perturbations test a genuine parent terminal, mismatched source/measurements, missing/future/wrong-parent extremes and objective floor priority.

## Historical controls and transparent test migration

The initial full-suite migration exposed legacy tests that supplied bare terminal/box labels or partial historical wrappers to exercise unrelated mechanics. Those premises no longer establish complete admission. Tests now distinguish exact source frames, causal physical-prefix reconstructions, lower-level adviser predicates and explicitly authored synthetic premises. No raw archived fixture was rewritten to make a control pass, and no test is silently skipped to obtain a green release.

The earlier PID17588 test file is retained verbatim as `pid17588_pre_opportunity_behavior_test.py.txt` and checked against its historical manifest hash. Its current trajectory assertions retain the original actions while naming the new precise WAIT reasons. The PID252 floor/transition test bodies remain pinned individually to the captured baseline; the entry-premise updates no longer masquerade as an unchanged whole test file. Historical approval and raw fixture hashes remain intact.

The full PID18244 original was recovered from its eight previously uploaded parts and independently checksum-verified. Actual #6 entry is source sequence8122, before the geometry timestamp used by the old partial wrapper. Its exact current metadata, original proposal and quote qualify as MOUNTAIN_RETURN without relaxing the new rules. The 67-row causal window is preserved in `pid18244_opportunity_source_sequence.json.gz`; no future outcome is an input.

Other actual-source positives include confirmed Release and inherited/pre-open continuation, current parent value/rejoin and the specifically earned small lower return. PID14156's one-visit lower return is classified by its real smaller terminal/rebound evidence, not renamed as repeated Heist. A still-falling earlier observation remains WAIT. Existing exact protections, capacities, fees and whole-lot floor controls remain separate from admission quality.

Several old expectations are deliberately superseded. PID3904's cheap counter-parent Mountains and one-pass wide boxes fail quality even when one original trade happened to profit. PID23160's late cheap microstall and PID15184's unconfirmed microturn, TP junction and inadequate late runway do not become positives through the older labels. In the PID23072 physical-prefix reconstruction, positives1/3/5 remain;9/10 retain their old factory classifications but fail independent terminal/maturity proof at the shared boundary. The test comments and source fixtures identify these distinctions.

The available PID15740 ULTRA export is sampled and omits raw physical history. Its retained partial wrapper remains a lower-level opening-species/value control, not a fabricated source-complete original entry. Source-complete opening controls from other recorded runs separately exercise integrated admission.

## Validation scope and limits

The delivery includes a baseline-versus-candidate chronological Commander audit over all6,963 original decisions. It uses the original recorded metadata, adviser proposals and original inventory/fill observations; therefore it is an admission comparison, not a fresh whole-engine execution.

A separate full modified-engine Construct verifies all6,965 original calls against the captured baseline, then sends unchanged decoded feed/book inputs into a fresh candidate engine with fresh inventory. Its explicitly authored per-call clock is based on the original first clock reading with10microseconds per internal read. Changed code paths read the clock differently, so this is **not exact original Windows replay**. Semantic checks include source/frame/geometry/market/book identity, nonempty valid admissions and modeled custody/exits, whole lots, prohibited original routes and no venue-fill claim. No modeled alternate profit is presented as realized performance.

The final builder requires source-matching receipts and performs the full check on the actual extracted standalone archive: current tests, historical Constructs, capture/export modules, actual JavaScript Looking Glass and fresh synthetic three-way recorder/replay integrity. It then rechecks final status/report/manifest bytes and ZIP integrity. The final validation JSON records actual counts and transcript; this document does not invent a pass in advance.

The original capture used Windows11/CPython3.14.7. Native Windows execution remains unverified in this Linux workspace. The next45-minute PAPER field run is still required to assess behavior, opportunity quality, alignment, fees and realized P&L. A passed engineering gate is not a profitability claim.

## Exact code scope

Relative to the untouched PID3904 source, only `commander.py`, `custody_evidence.py` and `paper_runtime.py` change; `opportunity_first.py` is added. `commander_candidates.py` and all other existing strategy/config/UI source files remain byte-identical. The source inventory has68 sealed files, with all prior approval chains preserved through `PID3904_SOURCE_SHA256.json` and `PID3904_APPROVAL.json`. Check/build scripts, tests, fixtures and documentation are separately included in the package manifest.
