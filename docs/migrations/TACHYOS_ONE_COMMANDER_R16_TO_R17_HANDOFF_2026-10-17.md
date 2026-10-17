# TACHYOS — ONE COMMANDER R16 → R17 MIGRATION HANDOFF
**Frozen checkpoint:** 2026-10-17 (work begun October 16, US Eastern)
**Repository:** zenmillonario/KalshiBTCBot (PRIVATE)
**Document status:** Continuity and engineering handoff; **NOT a trading release**
**Mode:** PAPER research only. NO live-money authorization. NO running engine authorized.
**Source of truth:** Exact user/session-produced R16 ZIP, not the GitHub main branch and not a hypothetical new implementation.

## START HERE / DECISION
Resume **One Commander Restoration R17** from the frozen R16 package. Do **not** redesign the strategy or add independent commanders, veto committees, recorders, or arbitrary trading rules. Do **not** issue a Windows trading launcher until the outstanding runtime gates pass. This branch contains the migration documentation, **not the 31 MB R16 source archive**; request the ZIP as an attachment in the new chat and verify its SHA-256 before making changes.

### R16 archive identity
- Filename: TACHYOS_ONE_COMMANDER_RESTORATION_R16_LIFECYCLE_OFFLINE_2026-10-17.zip
- ZIP SHA-256: **f41df389f39e897c64e92c2857aadfd16983ce69cf667654becfd561f27356f4**
- Root folder: TACHYOS_ONE_COMMANDER_RESTORATION_R16_LIFECYCLE_OFFLINE_2026-10-17
- Offline verifier inside archive: CHECK_R16_OFFLINE.py; inventory: R16_PACKAGE_MANIFEST.json; report: R16_LIFECYCLE_RISK_AND_FINALITY_REPORT.md.
- Independently reverified from clean extraction in this migration chat: **342 SHA-256-pinned files; 310 staged source-native tests PASS + 64 inherited Commander tests PASS; exactly 2 of 91 engine .py modules changed relative to R15; no Windows CMD/BAT/PS1 launcher**.
- Important: No live Windows R16 session occurred. Offline tests and synthetic fixtures are not a chronological profit simulation.

## 1. Architectural doctrine (user's original intent; NON-NEGOTIABLE)
Tachyos is **a cockpit of parallel specialist processes providing observations and overridable advice**, not a committee with independent entry/exit powers. Analogy from user: **"Never give the wheel to the speedometer."**
- NAEVYR = **EMA9**: sovereign living parent arc/mountain and its leg/phase, retained across 15-minute contract rollovers. THAERYON = **EMA30**: longer spine and context.
- Specialists: Market Heist, Candlestick Commander, King's Navigator, Arc Echo, Leg Atlas, value/entry-price desk, Settlement Sentinel, Observer42, other existing modules. They may keep history, measure, report, and recommend. They **must not book, liquidate, mutate roles/custody, or veto strategy**.
- **ONE Commander** synthesizes all evidence, records a coherent decision (ENTER, WAIT, HOLD, EXIT, REENTER) with quote-bound reasons. **ONE guarded PAPER executioner** alone modifies positions, cash, and realized P&L. There may be independent non-overridable, objective safety constraints: stale/contradictory data, insufficient cash or executable depth, verified settlement/emergency state, and hard executable-bid floors **already armed**.
- An inactive Sentinel report is never an active emergency. In H25, bool(nonempty_dictionary) erroneously overrode a Mountain hold; the exact boolean must be used.
- Preserve existing Kalshi quote provenance and full native order-book walking; never call an ask with fractional top-level size a full-lot fill. Exchange YES/NO in the same market **nets**, so do not simulate freely coexisting opposite holdings as real independent inventory.

## 2. Trading doctrine to preserve — no new strategy redesign
- **Mountain Dance:** EMA9 parent arcs/legs set MAIN ownership; child price legs and individual candle reversals are subordinate. Ride the meaningful leg, favor collection at true terminal exhaustion or contract settlement when justified. Trade **quality and location matter more than a low entry count**; the user does NOT oppose frequency when positions actually travel with their legs.
- **Market Heist remains intact** and fully tactical in small confined/overlapping arcs and brief wide wiggles between larger mountains. It can operate as a background observer during long rolling mountains and recommend genuinely independently monetizable short legs, but may not seize the MAIN steering wheel.
- **Entry price:** Under $0.30 is a strong *preference for attractive edge location*, not a hard automatic ban above $0.30. A $0.74 early-contract commitment demands exceptional structural/value evidence, not simply 35% theoretical payout capacity. Cheapness alone never authorizes a countertrend entry.
- **Entry anticipation:** In a mature mountain, slowdown/failure to extend can justify ARM and value hunting before EMA9 fully reverses. Use Arc Echo ancestry (compare prior 2–3 comparable arcs/third-cycle fatigue), while distinguishing "three contracts of duration" from "third repeated cycle." Neither is an automatic reversal veto.
- **Candlestick Commander:** completed vs forming 1-minute bodies, residence above/below/straddling EMA9/EMA30, wick-only rejection vs completed body cross/acceptance, burst size, terminal wicks, and relationship to parent arc. A counter candle does not alone end MAIN. Watch each significant 2–3+ consecutive large-candle push for a potentially large pullback, but never automatically fade a strong healthy mountain.
- **Hold/exit:** 120-second initial discretionary Mountain patience, possibly 180 seconds while healthy, is an *experiment*, **not a forced sale or unconditional lock**. Genuine structural break, urgent settlement, data/inventory emergency and armed hard profit floor can end a trade immediately. Once large gains occur, preserve rolling 5–10% executable peak-bid protection; do not surrender +100%/+150%/+169% winners. Never let Heist scalp a healthy MAIN position by itself.
- **Startup:** historical REST candle seed provides EMA context only. Require fresh *post-engine-launch* causal market evidence (R11 introduced a 90-second observation window, newly completed minute and distinct source observations) for discretionary entries; do not bypass via Heist at contract opening. Contract first-minute WAIT remains default, with rare documented inherited continuation exceptions.
- **PAPER only**; no change to user live trading or account without explicit permission. Avoid adding contradictory sensors or new generalized blockers.

## 3. Concrete real-run regressions that define success
- **H22 #2 YES:** entry $0.42, exit $0.52 after ~23.8% gross despite intact rising parent arc; later same-contract valid YES bids $0.83/$0.88. Early ordinary profit floor/scalp activation and wrong owner caused premature collection.
- **H22 #6 YES:** YES $0.74 around 4:05 ET on mature/spent UP parent arc. Source frame reported spent_capacity=True, terminal_candidate=True, decreasing upward extensions and developing bearish candle. NO ~0.27 then valid NO bid around 0.54 shortly afterward; opportunity is a historical counterfactual, not a fill. Do not mistake a child YES leg for renewal of an exhausted parent.
- **User manual NO at 4:50 AM ET:** cost $24.28, closing proceeds $51.88, +$27.60 (+113.67%) by 4:54. H22 bot had STOPPED from MemoryError before 4:50, so not a live bot veto; demonstrates possible profit on partial retracement without BTC reaching target.
- **H23 microtrades:** 14 closed, gross +$13.09, one unresolved; 12/14 closed under 120 sec. Heist collection terminated numerous Mountain entries in 28–89 sec despite intact parent arcs. Fixed hold times are not magic: 180s mark-to-bid would have worsened aggregate of four example trades (original +$12.04 vs fixed-180 +$8.66). Structural exits/hard floors must remain.
- **H24 immediate startup entry:** 74 YES at $0.19, gross loss ~-$8.07; 1.06 sec after historical candle bootstrap. Local Heist detector said NO_OBSERVED_BOUNDARIES_YET; a very wide historical extreme + unfinished bullish candle was wrongly promoted to live reversal authority. Startup evidence must be earned, not inferred from history.
- **H25 #1 (decisive original architecture failure):** purchased 13 NO at $0.74 at 9:32:00 ET, same market NO ask $0.66 only ~12 sec later; exited at $0.79 at 9:34:19 (gross +$0.65/6.76%) via H187_HEIST_OPPOSITE_EDGE_COLLECT_NOW although purchased physical owner was DOWN MOUNTAIN_DANCE arc A00001, still intact. Later bids $0.84/$0.86. Entry price desk graded $0.74 F without affecting authorization. An inactive Sentinel dictionary evaluated truthy and bypassed the Mountain HOLD guard. These prove advisers usurped strategy authority. H25 4 closed trades +$12.53 gross paper; this positive total does NOT excuse invalid decisions.

## 4. Restoration stage genealogy — R0 through R16
- **R0/R1:** source-backed authority maps and H25 concrete reproduction of Sentinel truthiness bypass; inert One Commander controls.
- **R2:** immutable adviser observation / explicit objective safety / one Commander-issued decision / one-use PAPER executor boundary.
- **R3:** source-native Kalshi book mapping and recovered H25 eight quote-ID-matched books; entry/exit test control.
- **R4:** connection to actual H25 PAPER booking/finalization, direct old discretionary calls rejected; inventory writers still needed audit.
- **R5:** guarded position store, fee-aware cash journal, independent executable-bid hard-floor arming and enforcement.
- **R6:** guarded pending custody/settlement path tested using fixtures; finality not production verified.
- **R7:** retired legacy direct inventory/P&L writers, retaining observers; no independent old path to trade.
- **R8:** single serialized streaming dispatcher; normal full quote callback and fast 100 ms risk-only callback; no duplicate entries.
- **R9:** original R13 physical and candle sensors feed cockpit as **passive** quote-bound evidence, not decision writers.
- **R10:** central interpretation of arc maturity, body/wick residence, third-cycle fatigue, price value and confined Heist; no adviser votes.
- **R11:** central EXIT evidence fusion and postlaunch entry-readiness gate; preserves mandatory floor and confirmed structural exit.
- **R12:** durable decision/evidence journal, replay fidelity/source-bound booking timestamp, incomplete-commit quarantine.
- **R13:** optional standalone 3-minute public REST recording; user successfully recorded 34/34 cycles Oct 16 ~10:08–10:11 PM ET with integrity chain. Helpful API/recording check; **not** continuous WS replay and does not need repeating. User was frustrated by unnecessary detour.
- **R14:** existing native Kalshi WS quote-identity correction (same unmodified book must keep quote ID; actual sequenced depth change gets new ID); offline handoff tests.
- **R15:** pinned HF2 quote runtime callback-to-Commander bridge; still not installed/tested in actual Windows engine; settlement/restart risks remain.
- **R16 (current):** held-side one-sided bid can trigger mandatory armed-floor **RISK_ONLY** review through ONE executor without ever authorizing ENTRY; 100 ms duplicate review paths made mutually exclusive; isolated public official Kalshi finality parser with injected fake HTTPS replies; journal replay/accounting test. This is **OFFLINE ONLY**.

## 5. Exact R16 source and verification scope
R16 derives from exact source-pinned R15, **not main**.
- Engine files modified versus R15: cutover_engine_stage/tachys_666_runtime_hf2.py and cutover_engine_stage/tachys_r15_command.py only (of 91 engine modules).
- Added: r16_sell_side_native.py, r16_public_finality_source.py, tests/test_r16_one_sided_risk.py, tests/test_r16_public_finality_source.py, tests/test_r16_chronological_one_side_replay.py, and manifest/report/checker.
- Offline full one-sided quote tests prove: a verified and deep enough sell-only bid can trigger armed-floor EXIT of an existing lot; missing/wrong-side/thin/stale/contradictory book fails closed; partial book NEVER permits entry; no duplicate cash or exit.
- Finality tests prove fixture parsing only: "closed" is not "finalized", "determined" is not enough for payout, only correct official result/ticker/time allows final-result fixture. **No real exchange settlement or account reconciliation was attempted**.
- Strict clean-extracted CHECK_R16_OFFLINE.py PASSED: 342 pinned file digests; 310+64 tests; NO-GO for live settlement, restart, Windows bootstrap and full replay. No Windows engine, no GitHub source mutations, no account orders.

## 6. OPEN NO-GO gates — what R17 MUST work on, without adding strategy features
1. **Production Windows bootstrap:** safely install one R15/R16 bridge into actual existing HF2 live stream in a controlled non-booking/read-only rehearsal. Confirm one callback owner, startup postlaunch causal evidence, real quote identity/depth, no late wrappers/legacy bypasses, and separation of normal vs 100ms risk path.
2. **Authentic finality & custody:** verify real public Kalshi finalized-result source against exact contract ticker and chronology; reconcile positions/cash/pending with independent actual venue/account truth when available, PAPER only. Fixture acceptance is not production evidence.
3. **Crash/restart:** reconcile durable PAPER cash, positions, used decision IDs, floors and pending custody before any resumed decision. Uncertain states quarantine; no auto duplicate booking.
4. **True continuous market-data replay:** the H25 native depth gzip lacks a valid end trailer; 1,563 top-quote summaries (763 valid, ~83s gap) and R13 5-second REST polling cannot certify complete changed-inventory P&L. Need source-sequenced WS evidence across a continuous usable window. Do not turn only eight recovered H25 books or synthetic bid movements into profit claims.
5. **One-sided mandatory protection in actual runtime:** observe valid sell-only risk path, duplicates, terminal windows and source outages with existing PAPER positions; hard floor cannot pretend to sell more than available depth.
6. **Release gate:** strict source hashes, real life-cycle integration, no double writes, all hard-floor/settlement invariants; only when all pass consider a short **20-minute supervised PAPER pilot**, never a live-money run by default.

## 7. Developer conduct and user workflow
- The user is tired of successive patch stacks and many tiny R releases. Restore the original cockpit design and **finish one coherent integration**. Do not promise the pilot prematurely or make user operate another recorder unless strictly necessary.
- Produce succinct progress with concrete verified findings. If a blocker persists, say precisely what it is; do not fake a GREEN release by weakening checks.
- Do not create new command classes, contradictory vetoes, blanket entry/exit blocks or backfill market conditions from future quotes. Keep no side-effecting adviser.
- Preserve frozen R16 ZIP; stage R17 in a new path and do not modify R16 files or GitHub main/revival-lab trading code.
- The GitHub handoff branch is a **docs-only migration pointer**, not a source replacement. In the next chat, attach the exact R16 ZIP and optionally R16 report for code work.

## 8. Paste-ready next-chat instruction
"Continue Tachyos One Commander Restoration from R16, not from GitHub main. Read the private GitHub handoff docs on branch handoff/one-commander-r16-2026-10-17 and inspect the attached exact R16 ZIP (SHA-256 f41df389f39e897c64e92c2857aadfd16983ce69cf667654becfd561f27356f4). All specialist processes are advisers; only one Commander decides and one executioner writes PAPER inventory. R16 passed 310 + 64 offline tests but is **NO-GO for trading**. Proceed with R17 Windows bootstrap/non-booking integration, authentic settlement and durable restart reconciliation, then continuous source replay. No redesign, no independent vetoes/commanders, no live money, no new recorder detours. Do not claim pilot readiness until all runtime gates are verified. Keep R16 frozen and report concrete source-backed findings."