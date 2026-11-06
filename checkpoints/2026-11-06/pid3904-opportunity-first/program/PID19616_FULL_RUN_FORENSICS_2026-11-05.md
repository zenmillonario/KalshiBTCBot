# TACHYOS — PID19616 complete PAPER run forensics

**Date:** 2026-11-05 (ET). **Review scope:** Original recorded PAPER run, not hypothetical trades. **Strategy status:** Existing verified PID18244 program unchanged; **no new strategy patch or 45-minute release has been approved, built, or field-tested from this review.**

## Evidence and integrity

- Run ID: `TOOL_RACK_PAPER_20261105T223220Z_PID19616`.
- Original saved ZIP: `TOOL_RACK_PAPER_20261105T223220Z_PID19616_FULL_ORIGINAL_20261105T231910Z_1069d60f.zip`, **556,916,480 bytes**.
- Original SHA-256: `22028d8a01034bd76f66caf164ff622f660a0d5b7cc76dca765218d21fe117e5`, verified after lossless reconstruction from **six** individually SHA-256-verified upload payloads. Source ZIP contains 444 entries.
- `CAPTURE_STATUS.json`: completed, **8,641/8,641 captured calls**, **zero drops**. Source program was `TACHYOS_PID18244_PARENT_CUSTODY_PROTECTION_45M_PAPER_20261105`, with `strategy_core/commander.py` SHA-256 `34d93123421310b6c3cfbb4480333b33b578e105614636cd0ab884f3cc4ff6ef`, `strategy_core/paper_runtime.py` SHA-256 `c02af95418283848190a54a23c49a8dcbf984bc74324616c9208b6cc8f46a100`, `strategy_core/commander_candidates.py` SHA-256 `98b186de6845510bac7528ee7f0584b73b1157c8f943d830eaa5c9acf2243572`—the previously verified release code.
- **Exact original run engine replay was NOT requested or performed.** The complete captured inputs are replay-ready. Source-bound entry-time frames, on-ledger fills and exit causes are sufficient to attribute observed decisions, but not to assert counterfactual P&L.
- Independent check: 27 prior regression tests for PID18244 custody/floor, PID15740 inherited opening, and PID17224 parent-transfer cases passed unchanged.

## Final modeled ledger

Starting PAPER cash `$1,000.00`; ending `$959.8284`; **realized gross −$30.6016**, **fees $9.57**, **realized net −$40.1716**. Eight full positions closed; no unresolved inventory; run stop reason `PAPER_ENTRY_WINDOW_COMPLETE_FLAT`. These are **PAPER simulated executions** with native quote/depth and fees, not live venue fills.

| # | Entry → exit time ET | Side / qty | Entry → exit (USD/contract) | Net PAPER | Execution reason |
|---:|---|---|---|---:|---|
| **1** | 17:38:08 → 17:39:31 | YES / 38 | $.250 → $.057 | **−$7.9840** | `LAZARUS_HARD_ADVERSE_STRUCTURE` |
| **2** | 17:39:40 → 17:40:55 | YES / 228 | $.041 → $.0653 | **+$3.9304** | `ALREADY_ARMED_EXECUTABLE_BID_FLOOR` |
| **3** | 17:41:06 → 17:45:14 | YES / 213 | $.110 → $0.000 | **−$24.8900** | Official YES-losing settlement (NO resolved) |
| **4** | 18:01:37 → 18:02:11 | YES / 49 | $.190 → $.290 | **+$3.6600** | Armed bid floor |
| **5** | 18:05:15 → 18:07:22 | YES / 31 | $.300 → $.380 | **+$1.5000** | Armed bid floor |
| **6** | 18:08:29 → 18:09:29 | YES / 94 | $.100 → $.130 | **+$1.4700** | Armed bid floor |
| **7** | 18:10:15 → 18:12:33 | YES / 208 | $.045 → $.004 | **−$9.2180** | `LAZARUS_HARD_ADVERSE_STRUCTURE` |
| **8** | 18:15:11 → 18:18:12 | NO / 47 | $.510 → $.360 | **−$8.6400** | `COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT` |

**Four gains total +$10.5604; four losses total −$50.7320; net −$40.1716.** The independent runs PID18244 and PID19616 experienced different market conditions: the difference in realized PAPER totals is **not** a measured counterfactual regression of the source changes.

## Root-cause observations

### Priority 1 — #3 YES: oversized, loose recent-level match against continuing DOWN EMA9

At original decision sequence **2029**, native BTC `$75,742.38`, EMA9 `$75,769.35`, EMA30 `$75,824.36`, gap **−$55.01**, physical parent and current native arc both **DOWN**. The short BTC rebound was +$39.54/6s, +$44.18/9s, EMA9 +$7.91/6s, but no confirmed parent-scale YES release or YES TP ownership: target ownership **UNRESOLVED**. Commander nonetheless entered **213 YES at $.11**, the exceptional $25 tier, via `COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN`. The previous-completed-low reference was `$75,774.90`, **786.3 seconds old**, so BTC was **$32.52 BELOW that supposed support reference**. The preceding downward trend and exhausted support, plus short temporary rebound, were treated as an earned level match. Position never marked above $.12 and resolved worthless, losing **$24.89** including fees.

**Code-mechanism candidate:** `strategy_core/tool_rack.py` recent-level match recognition allows a loose tolerance of `max($12, 25% of recent 180s range)`. `strategy_core/commander_candidates.py` then treats 6/9s BTC/EMA9 positive movement as sufficient rejection proof. This allowed a wide *failed support* to count as a positive physical level return. **Suggested test, not implemented:** require a tighter contemporaneous support/rejection location before granting the expensive exceptional MAIN tier. Preserve PID18244 **#6 NO**: previous genuine upper retest within **$4.93** of the prior high and positive 6/9s downward turn, which collected **+$64.2741** in that earlier PAPER run. Also preserve PID17224 source-bound true transfer positive case (~$1.35 from anchor). Do not create a generic counter-EMA9 veto.

### Priority 2 — #7 YES: cheap fade still entered amid a pronounced DOWN parent

At decision sequence **7707** (~18:10:15), BTC `$75,157.25`, EMA9 `$75,388.92`, EMA30 `$75,536.18`, gap **−$147.27**, current parent and native child DOWN. BTC 9s **−$82.52**, 30s **−$197.59**, EMA9 30s **−$52.70**. The 6s micro-change was merely ~−$0.67, not a qualified upward parent handoff. However `HEIST_PARALLEL_STALLED_EDGE_RETURN` accepted **YES $.045** while `ROLLING_MOUNTAIN` NO owned the displayed parent. Bid peaked $.051, never reached the tactical floor; Lazarus sold at $.004, loss **$9.2180**. Low quote alone did not establish an eligible physical return. Compare positive quick YES Heist excursions #2/#4/#5/#6 before suppressing any route; blanket fade removal would regress good entries.

### Priority 3 — #8 NO: 2.85-contract inherited parent treated as fresh strong first-minute continuation at $.51

At **18:15:11** new-contract age 11.50s, sequence **8301**, `COMMANDER_OBSERVED_INHERITED_PARENT_FIRST_MINUTE_CONTINUATION` entered **47 NO contracts at $.51**, exceptional $25 tier. Historical-flow metadata: **2,564.63 seconds / 2.85 contracts** of observed same-side NO residency, EMA9–EMA30 gap **−$140.28**, with TP `STARTING_LEG_FAVORED` NO and no terminal classification. The immediate 6s BTC/EMA9 was DOWN, but physical movement over **60s was only −$1.90 BTC** (range60 ~$53.41), a near-flat older Rail, not proven *renewed acceleration*. EMA9 30s −$14.82; current arc already 101s old. The admission path checked BTC30 and EMA9 30s direction, but not meaningful BTC60s progress. Within ~3 minutes BTC adverse movement and local YES motion forced a sale at $.36; **−$8.64** net.

This is exactly a **Rail maturity/possible transition-watch** case after 2.5+ contracts, not proof that every mature NO Rail must reverse. **Suggested test, not implemented:** retain user-approved first-minute $.48–$.55 continuation only with fresh, meaningful same-direction continuation evidence beyond static historical residence and old TP ownership. Preserve historical PID15740 positive 53c opening where BTC moved ~+$52.15 over 60s on a ~$56.58 range; don't block genuine inherited launches. Normal <=$.35 value fishing remains separate.

### #1 and positive tactical controls

**#1 YES** $.25 entered an early lower Heist edge even though native parent DOWN (EMA9–EMA30 gap −$20.45). While BTC rebounded +$29.14 over 6s, 9s BTC remained −$11.65 and EMA9 30s −$10.73; the move did not mature. Peak bid $.24 was below entry; Lazarus took −$7.98. It is another negative against declaring a real Heist return from a single micro-turn.

**#2 YES** $.041 → $.0653 earned **+$3.93** on a small genuine bounce under a DOWN parent; preserve this class of cheap bounded Heist excursion. **#4 YES** entered near a very sharp flush (BTC −$151.69/6s, gap −$110.76), returned $.19→$.29, +$3.66. **#5 YES** $.30→$.38, +$1.50; **#6 YES** $.10→$.13, +$1.47. All four profits were collected through **already-armed executable-bid floors**. Thus the prior counter-parent tactical protection and whole-lot capture paths clearly remained active; none should be disabled while reducing poor entries.

**Custody observation on #5:** At ~18:07:21 a YES tactical position briefly received `COMMANDER_HEIST_SEED_PROMOTED_TO_RELEASE_CUSTODY` while the historical gap and `ROLLING_MOUNTAIN` rack owner were still NO and `handoff_confirmed=false`. The release watcher reported a developing YES release and short current EMA9 upward movement. Its previous floor then triggered sale ~1 second later; there is no observed harm here, but this is a useful **safety audit case** for physical MAIN promotion. Do not assume the earlier #3 promotion fix necessarily covers all release-watcher branches. Require actual current physical parent/transfer proof on future audit before broadening promotion eligibility.

## Decision / risk implications — proposals pending approval

1. **Level-match precision:** distinguish a genuinely defended prior low/high from a far-side overshoot/failed level plus temporary 6/9s bounce; ensure price remains near a causal completed level and parent return is physically earned before a $25 exceptional MAIN position. Negative PID19616 #3; positive PID18244 #6, PID17224 approved transfer.
2. **Age-aware opening:** after >=2.5 contracts of continuous directional residence, set *transition watch*, never a forced reverse. When paying >$.35 on the very first minute, require new 60s-style same-direction momentum evidence, not merely historical gap, same-side arc and static TP; negative #8, positive historical PID15740 @$.53.
3. **Real Heist vs directional release:** new-run #1 and #7 cannot qualify solely from cheap prices or one brief stall when EMA9 30s and parent still expanding DOWN. But preserve positive #2/#4/#5/#6 and prior-run PID18244 #2/#5 and Commander #6; investigate a physically defined micro-rejection + bounded repeat excursion / sprout-avoidance distinction before any code change.
4. **MAIN custody watch:** trace the developing YES release candidate promoting #5 while larger NO parent still owned rack; floor correctly executed, so this is a regression-test opportunity, not an observed loss.
5. **Retain hard discipline:** EMA9 leg sovereign; EMA30 reference only; one Commander; independent MAIN/TACTICAL; no mid-leg premium chasing; whole-position protection and Lazarus; first-minute default WAIT except proven earned exceptions; PAPER-only venue safety.

## Next validation / release gate

Do **not** publish a newly changed 45-minute PAPER ZIP from these observations alone. First authorise the narrow entry-quality changes; then implement them as first-class Commander positive-qualification rules (no independent adviser veto) with source-bound original cases and historical positive controls. Run all historical 46-module+ strategy tests, mandatory Constructs, capture/launcher tests, real Looking Glass JavaScript test, synthetic three-way recorder/replay, extracted ZIP/hash audit and Windows preflight before declaring a new release. Keep run PIC `PID19616` evidence and original source untouched. **No alternate-run P&L, hypothetically missed fills, or original full engine replay has been produced.**

Companion machine-readable evidence: `PID19616_SOURCE_BOUND_EVIDENCE_2026-11-05.json`. Original verified upload parts and source ZIP remain inputs, not published replacements.
