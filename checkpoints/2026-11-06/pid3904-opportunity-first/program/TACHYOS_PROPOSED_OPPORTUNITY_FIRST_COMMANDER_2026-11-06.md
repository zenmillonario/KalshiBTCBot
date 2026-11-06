# TACHYOS — Proposed Opportunity-First Commander Contract

**Draft specification · 2026-11-06 · Not implemented · PAPER only**

## Source and intent
This proposal reconciles the user's current instruction with the existing TACHYOS strategy backbone: One Commander, independent MAIN and TACTICAL positive-briefing lanes, EMA9/NAEVYR authority, EMA30/THAERYON context only, true mature Mountain edges anticipated before a cosmetic EMA9 curl, strict Heist bounded oscillation, release/rail continuation, whole-lot custody and committed floors. The backbone's 2026-11-04 dual-lane delta authorizes MAIN parent-direction value opportunities after 300 seconds (five minutes), with previously authorized opening continuation exceptions; this proposal emphasizes systematic evaluation in the second half rather than requiring a trade every contract.

**Core problem:** Commander-native shortcuts and wide-Heist candidate routes have admitted speculative mid-leg counter-parent entries, while qualified with-EMA9 directional opportunities have sometimes remained at WAIT. Passing isolated tests has not prevented this full-sequence behavioral failure.

## Entry-state machine under ONE Commander

### WAIT (default, NO executable candidate)
- Current territory unknown/unclear, insufficient source history, EMA9–EMA30 junction or TP between EMAs, middle of living parent leg, first opposite wobble, expired/stale quote, or insufficient return/settlement runway.
- Do not allow a cheap opposite quote or contract-age urgency to become entry authority. WAIT in some or all contracts is normal.
- A detector may advise PREPARE/FISH, but advisers neither place orders nor veto an independently earned candidate.

### PREPARE (observed physical edge, not an order)
- Each **new pronounced** upper or lower BTC/EMA9 excursion starts or refreshes an identified *watch* (parent arc ID and contract/ticker, price extreme, parent trend/age, last 2–3 comparable parent arcs, recent defended levels, repeated wall visits, current quote samples, target/TP distance, time remaining).
- A watch must distinguish *same parent re-extension* from a new physically distinct excursion. New book callbacks at the same level do not create new watches or new trade opportunities.
- Watch direction: at upper mature edge, possible NO return; at lower mature edge, possible YES return. Watch is not automatic ENTER. If old leg expands again / genuine directional breakout, cancel opposing watch and prioritize with-parent Release/Rail.

### ENTER (positive Commander admission + economic feasibility)
Eligible **only** through an evidence-rich species:
1. **MOUNTAIN_RETURN:** parent-scale mature arc or validated smaller terminal arc, at genuine upper/lower extreme; anticipation allowed before EMA9 curl upon observed hesitation, failed re-extension, matching recent resistance/support, or measurable retreat. First microstall under expanding parent is insufficient.
2. **REAL_HEIST_RETURN:** repeated meaningful outer-wall visits and bounded center traversals in true compression/parallel slow zone; recent directional 6/9/30/60-second momentum may have low weight because oscillation is defining geometry; nevertheless avoid invented one-visit wide boxes, new Releases, and broken/obsolete boundaries.
3. **MAIN_EMA9_REJOIN:** current observed parent history in EMA9 direction + current continuation or real pullback/rejoin/value opportunity + target/TP and physically attainable runway; not generic mid-leg premium chase.
4. **RELEASE_HANDOFF:** current physically confirmed transfer, potentially before EMA9/EMA30 cosmetic cross; with-direction entry and higher structural hold custody.
5. **ALREADY_AUTHORIZED_ROLLOVER:** proven inherited continuation, genuine parent-scale terminal extreme carried into new contract, or current causal pre-open BTC + fresh EMA9 support, according to existing bounded opening price and source rules. A spent old parent cannot gain authority simply from the old EMA9–EMA30 gap.

Every admission includes a timestamp/source generation, candidate species, actual parent vs child identity, actual location in parent arc, TP/target distance, amount of contract time left, current executable bid/ask/depth, price tier, invalidation evidence and Commander-issued reason. Commander-created candidates MUST meet the same positive physical quality standard as specialist candidates. Legacy lane fallbacks may remain diagnostic, not executable authority.

## Per-contract operating cadence (not compulsory trading)
- **00:00–01:00**: normal WAIT; only already-authorized earned rollover/exceptional opening modes. No automatic acquisition.
- **01:00–05:00**: identify parent and compare arcs, observe Heist walls and potential early genuine extremes; enter only when a real extreme/release is earned (not because the clock advances).
- **05:00–07:30**: MAIN actively searches same-parent EMA9 pullback/value joins and new Releases, also keeps genuine TACTICAL Heist watches independent.
- **07:30–13:00**: a **positive review at every physical opportunity** asks: Which EMA9 parent side has settlement ownership? Is TP/target convincingly on that side? Is a value join or held aligned lot available? Is price economically worth the remaining runway? With clear parent and qualified entry, prioritize MAIN holding the contract-winning side. Do not chase 0.80–0.95 asks just to force an aligned position.
- **13:00–15:00**: remaining time and target displacement dominate. Protect existing whole-lot winners and settlement/finality; no cheap counter-parent buys without the previously approved true fast Heist/settlement and executable-runway proof. WAIT / flat is a valid outcome.

**Goal and metric:** A higher *qualified alignment participation rate* on sufficiently clear, economically accessible, late-contract EMA9 opportunities; never a guaranteed position in every 15-minute contract, nor a promised contract win. Log each qualified but missed opportunity and its precise no-entry reason.

## Quote-value watch and exits
- Once a positive edge qualifies, a *bounded* short ask-value observation may improve cost while rechecking the same ticker, signal and current geometry. Price timing cannot create an entry signal; exceptional cheap entry and genuinely fast Release must not be delayed into a miss.
- Nonrunning stalled mature excursion: collect at **current executable full-lot bid** when net of modelled fees is positive, high watermark is nearby and repeated extension has failed; first ordinary slowdown is not enough.
- Genuine advancing Rail/Release/large Rolling Mountain: do not strip earned custody on the first routine pause; committed profit floors remain irreversible; distinguish harvest from structure termination. No partial lots.

## Historical positive/negative source-bound examples
| Case | Desired use, not alternate P&L |
|---|---|
| PID18244 #6 NO ~$0.088 upper extreme -> $0.35 | Positive: historical top level, real fast downward rejection, cheap price, all-in/out floor |
| PID14048 #2 04:40 NO Release | Positive: genuine early DOWN handoff while EMA9 gap had not yet crossed; examine mature resistance scans at 04:32/04:36 and runner exit separately |
| PID14156 19:50:11 YES ~$0.13 proposal | Positive entry opportunity review after actual lower-box return; 19:50:01 still-falling YES is WAIT |
| PID23160 00:21:01 NO ~$0.29 | Positive: with-EMA9 DOWN parent value rejoin candidate, subject to true target/runway/depth |
| PID10760 21:45:30 YES ~$0.53 | Positive: causal pre-open BTC and fresh EMA9 opening exception; 21:45:21/25 weak are WAIT |
| PID19616 #3, #7 and PID14156 #1/#2 | Negative: stale/broken level, cheap microstall, immature short Mountain, strong contrary EMA9 |
| PID23160 #2–#5 | Negative: wide-only pseudo-Heist with 1–2 wall visits and strong directional market |
| PID3860 02:45:05 YES | Negative: bought spent inherited UP direction during substantial actual price retreat across mature rollover |
| PID14048 #3 YES high watermark 0.63 then floor never armed | Protect: fee-positive matured hover after, not exact peak/stall simultaneity; do not invent sale at historic peak |

## Validation standard before implementation or next PAPER delivery
1. Source-time snapshots: current candle/quote/EMA parent and target ONLY, no outcome leakage. Replay positive and negative source-bound frames from every case above.
2. **Full sequence behavior**: same ticker, actual chronological candidate proposals, repeated-wobble memory, WATCH/ENTER/WAIT transitions, aligned-entry opportunities, custody/exit and price/time economics across multiple contracts. A one-frame PASS cannot substitute for sequence-level selectivity.
3. Compare old and proposed engine candidate streams over recorded tape; if matching native Python/Windows environment is unavailable, state that an integrity/read-only Construct is NOT an exact engine replay. Never assert modified-run profit or hypothetical fills without an actual tested execution model.
4. Preserve historical Constructs (PID4596 genuine slow Heist, PID17588 true inherited opening, PID18244 #6, PID14048 Release and floors, recovery identity/locked floor, Looking Glass), plus full extracted-package source seals, capture/export, Windows launcher, JavaScript and synthetic recorder/replay integrity.
5. New field PAPER trial required; actual long-run behavior, trade/WAIT count, quality/parent alignment and fee-adjusted realized P&L are the final behavioral test. No real-money launch authority.

**Status:** Design proposal recorded for approval and implementation; no source files, runtime settings, risk budgets, account connections or orders were changed by this document.
