# Tachys R11 Construct — research handoff for next chat (2026-10-14)

**RESEARCH ONLY.** This Git branch is not an R12 deployment, not a PAPER engine release, and not evidence of alternative P&L. Phase 14 is IN PROGRESS, not tested or signed off. Do not install the branch as a runnable trading engine, start a bot, create a launcher, or change trade permissions until a separate validation and user approval.

## Where we left off

Latest **completed/verified** step: Construct **Phase 13 Rolling Arc Echo + turn-attempt generations**, based on archived R9/R11 original EMA geometry. 49 named physical EMA9 arcs, 13 cross-contract, 2 right-censored; 538 causal Arc Echo snapshots, 486 distinct physical event beats; 24/24 new causal tests and 52/52 separately isolated inherited Command/protection checks passed. The inherited Command did **not** yet consume Phase 13 authority. Phase 13 original portable evidence bundle: `TACHYS_R11_CONSTRUCT_PHASE13_ARC_ECHO_OFFLINE.zip`, 720,578 bytes, SHA256 `16c756ef04f76e7fdff85c64582c6cfe0b1fb2cbcc6cac27491d52fa780835bc`; find in conversation/file library. Original bundle contains **build_phase13.py** (19,612 bytes), **test_phase13.py** (10,345 bytes), input native R9/R11 geometry, logs, manifest, six derived output files. The code and complete zip are NOT yet included in this Git commit; recover them from the original verified bundle before attempting reproduction.

Latest **in progress** step: Phase 14. A local preparation directory `/mnt/data/tachys_construct_phase14` was populated with copies of Phase7/9/10/11 evidence and frozen inventory/command records. Work proposed an **incremental, as-of Arc Echo perception integration into existing One Command**, not hindsight-reading Phase 13 CSV into live runtime. **No completed Phase 14 source patch, tests, or release artifact were evidenced when this chat ended.** Do not claim Phase 14 complete.

## Canonical invariant — strategy

**NAEVYR=EMA9, THAERYON=EMA30.** EMA9 arc/mountain phase is tactical authority, EMA30 the contextual spine. The four physical territories are BASE (recurring arcs), DRAGON/DORSAL-VENTRAL (one-sided long mountains), MARKET HEIST (tangled/boxed, meaningful edges), TRANSFER (progressively one-sided repeated arcs and failed opposite reclaim). Territory and physical arc persist across Kalshi 15-minute contract rollovers. The contract price target, remaining time, quotes, fees, position and settlement identity are separate temporary economic slices. Never splice quotes/prices between tickers/sides; BTC physical history carries across.

**Sequence:** recognize territory → read two/three recent comparable completed arc SHAPES (not just amplitude) → observe current unfinished arc at common age → track newest physical extreme / retreat / attempted return / failed re-extension (new real extreme RETIRES older turn attempt) → anticipate fresh qualified crest/trough with native same-ticker executable quote and >=~35% monetizable capacity → enter selectively via ONE Command → keep measuring the living leg to stretch winners through harmless pullbacks, preserve hard executable-bid winner floors, mature Lazarus loss custody and legitimate settlement reviews → prepare successor leg and roll history into the next ticker without copying economic permission.

Two or three repeats are a **decision point, not an automatic reverse**. Old completed arcs and stale crest/turn labels are CONTEXT, never eternal executable entry permission. No new independent commander or blanket opposite-side ban. First-minute WAIT default, exceptions for genuinely exceptional inherited continuation. Sub-$0.20 entries observer-only absent later explicit approval. PAPER only, no live funds.

## R11 exact forensic priorities and hard lessons

R11 paper closed 17/18 entries, 10 wins/7 losses, gross **-$24.86**; #18 NO unresolved when `DATA_INVALID_30S_OPEN_POSITIONS_UNRESOLVED` halted. Earlier authority paths admitted #9Y/#10Y during strong A00008 DOWN across rollover; #15N immediate same-side center-of-Heist premium rebuy following #14N protected collection (measured interval 0.364379 sec); #16Y/#17Y unearned NEXT promotion. #14 hard-floor collection was legitimate and must stay binding. #11Y .50 original entry was unqualified while physical DOWN EXTENSION, but a subsequent genuine YES leg developed; first .54 archival publication was **exchange-stale** (>3s), not safely executable. Quoted YES .71 at first later dual-age-fresh research checkpoint offered ~40.85% maximum theoretical settlement ROI, not proof of fill. R9 #6 NO and #10 NO were valuable earlier counterlegs; losing R9 #20 NO superficially looked MORE crest-like, so a single wick/weakening label is not a permission.

Phase 7 shared EMA9 physical authority across PRIMARY/NEXT routes fixes repeated #9/#10 chronological admission and keeps #14 Mountain / #18 Heist edge positives. Phase 9 and 11 added non-executing physical handoff/turn observers; Phase 13 added explicit 2–3 predecessor shape, within-arc turn-attempt research. **Three future early-anticipation cases R9 #6 NO, R9 #10 NO, R11 #11 YES remained unresolved**. No complete candidate-owned original order-book, quotes, fills, inventory, exits/settlement replay has passed. Do not claim improved P&L.

## Phase 14 next actionable work

1. Recover the original Phase13 builder/tests and frozen Phase7/9/11 source from named source archives in Files/Library; do not infer source code from README or the repo’s older Construct v1 branch.
2. Implement an **incremental causal Arc Echo input** from actual physical samples Command already received (up to 3 predecessor completed same-side arcs, shape & duration, EMA30 residence; current arc at common age; arc continuity over rollover; distinguish summary-only when history, stable arc IDs, or sampling are incomplete; no >30-second interpolation gaps).
3. Unify PRIMARY/NEXT/Heist response to current **fresh turn-attempt generation**, but do not grant automatic entry authority from Phase13 researched outcomes. Study matched R9 #6/#10 vs #20 and R11 #11 vs #9/#10 with native independently fresh quote source time.
4. Run chronological stateful PAPER Command **entry+hold+exit+re-entry+settlement**, with all historical hard floor / Lazarus / first-minute / Heist-edge / HF2 quote safety checks and test-harness hook isolation. Include the unresolved R11 #18 safety halt and sub20 no-trade rule. Isolate tests if inherited global logger hooks conflict; fix that before release.
5. Keep R12 release **BLOCKED** until evidence supports the full lifecycle. Do not silently turn failed anticipated-entry tests green by hindsight-tuned thresholds or remove hard winner protection.

## Evidence committed in this directory

`PHASE13_REPORT.md`, complete individual Phase13 causal CSV output tables (including explicit evaluation-only table), and forensic reports from Phases 7,9,10,11,12. They are research artifacts, not loaded trading modules. Uncommitted original source archives remain accessible in the conversation/file library under the exact names given above.

Git branch intentionally based on existing `tachys-construct-v1-offline` source tree; it is NOT the R11 Windows runtime snapshot. The branch is a continuity/evidence checkpoint. No bot files in the parent tree were modified by this research commit.
