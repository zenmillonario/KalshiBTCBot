# TACHYOS — PID18244 complete-recording forensic review

**Review date:** 2026-11-05  
**Run:** `TOOL_RACK_PAPER_20261105T201055Z_PID18244`  
**Status:** Post-run forensic findings only; **NO strategy-code or Windows-run changes made**. Existing verified PID21672 45-minute PAPER baseline is intact. No live orders and no exact engine replay in this review.

## 1. Recording provenance and run reconciliation

- Received `TRANSFER_MANIFEST(8).json`, `00_SEND_FIRST_REVIEW(8).zip`, all **8** numbered parts, `READ_ME_FIRST(8).txt`.
- Reassembled *raw `archive_chunk.bin` payloads*, not the surrounding ZIP files; every part matched its declared size and SHA-256. Rebuilt original ZIP **678,087,269 bytes**, SHA-256 **`2600a6273a54ee1831f6ba40aced24b998cbd6c1f3b142dfd495ac8804bb9b12`**; archive has **492 members**.
- The `00_SEND_FIRST_REVIEW` preview deliberately included 122 of 137 complete journal members, with exclusions declared in `REVIEW_SCOPE.json`; full numbered transfer restores the original, without losing the omitted 15.
- Capture reports **8,245 attempted / 8,245 written / 0 dropped** engine calls, capture `complete=true`, `replay_ready=true`. This is recorder readiness, **not** proof that exact replay has run; the operator's export states replay `NOT_REQUESTED`.
- Run state `STOPPED`, reason `PAPER_ENTRY_WINDOW_COMPLETE_FLAT`, **0 unresolved positions**, modeled PAPER account **$1,000 → $1,069.7041**. Realized gross **+$80.6841**, modeled fees **$10.98**, realized net **+$69.7041**, six complete whole-lot positions. Paper quote/fill model is not venue execution evidence.

## 2. Exact executed PAPER trade ledger

| # | Entry → close (ET) | Held | Side, price, qty | Realized PAPER net | Observed intraposition best NO/YES bid | Recorded exit reason |
|---|---|---:|---|---:|---|---|
| 1 | 15:30:49 → 15:33:31 | 162.0s | YES $0.370 → $0.620, 25 | **$+5.42** | $0.660 at 15:33:24 | `ALREADY_ARMED_EXECUTABLE_BID_FLOOR` |
| 2 | 15:34:13 → 15:35:54 | 101.1s | NO $0.190 → $0.360, 49 | **$+7.00** | $0.380 at 15:35:52 | `ALREADY_ARMED_EXECUTABLE_BID_FLOOR` |
| 3 | 15:40:52 → 15:45:08 | 255.7s | NO $0.055 → $0.000, 170 | **$-9.97** | $0.100 at 15:42:33 | `OFFICIAL_FINAL_RESULT_PAPER_SETTLEMENT` |
| 4 | 15:47:30 → 15:50:31 | 180.5s | NO $0.260 → $0.280, 36 | **$-0.28** | $0.510 at 15:49:36 | `TACTICAL_MAX_HOLD_EXIT` |
| 5 | 15:52:35 → 15:53:42 | 67.8s | NO $0.100 → $0.150, 94 | **$+3.26** | $0.180 at 15:53:06 | `ALREADY_ARMED_EXECUTABLE_BID_FLOOR` |
| 6 | 15:54:42 → 15:55:21 | 39.1s | NO $0.0877 → $0.350, 267 | **$+64.2741** | $0.370 at 15:55:17 | `ALREADY_ARMED_EXECUTABLE_BID_FLOOR` |

**Caution:** `quote_echo_shadow.jsonl` is sampled native quote evidence with `execution_authority=false`. The observed peak bids are not alternate fills or profit claims. They help diagnose the controller's response to quotes that were present during the original run.

## 3. Trade #1 YES — good entry; floor collected before later extension

- Entered **15:30:49 at $0.37** via `HEIST_PARALLEL_STALLED_EDGE_RETURN`, TACTICAL role; initially physical EMA9 parent DOWN and YES was an anticipatory opposite-side purchase.
- Promoted to `PROMOTED_MAIN` at **15:33:09** under `COMMANDER_HEIST_SEED_PROMOTED_TO_RELEASE_CUSTODY`. An *in-progress* Release is not the same as a fully confirmed new parent.
- Intraposition YES bid peaked **$0.66 at 15:33:24**, with a committed bid floor of **$0.6208**. Whole-lot exit **$0.62 at 15:33:31**, **+$5.42 net**. The floor behaved as configured (`ALREADY_ARMED_EXECUTABLE_BID_FLOOR`), not as an unexplained timeout.
- After exit, same-contract YES bid first observed **$0.81 at 15:34:12**, 40.9 seconds later; the run contains even higher later bid samples. This supports operator's **early-exit concern**, *not* proof that a particular alternative hold or fill would have succeeded.
- **Decision for next development:** study when a *physically earned*, same-side fresh Release should have appropriately different floor/breathing behavior **before** a tight floor becomes committed. Never retrospectively loosen an already-armed floor; preserve the prior PID21672 #4 successful positive-protection control.

## 4. Trade #2 NO — positive, short tactical upper-edge return

- Entered **15:34:13 NO $0.19**, 49 contracts, through `HEIST_OUTER_EDGE_TACTICAL_RENTER`; short-term EMA9 parent was UP and BTC was extended above EMA9. The downward tactical swing was physically present and quickly repriced NO.
- Peak sampled NO bid **$0.38 at 15:35:52**; already-armed bid floor exited at **$0.36 at 15:35:54**; **+$7.00 net**. This is a positive Heist **upper-edge excursion** control despite counter-parent orientation.
- **Do not confuse this new-run #2** with the earlier PID21672 #2 negative control, which was a premature middle-of-tiny-leg purchase; the two IDs refer to different runs.

## 5. Trade #3 NO — sprout fade amplified by invalid MAIN promotion

- Entered **15:40:52 NO $0.055** / 170 contracts via `HEIST_PARALLEL_STALLED_EDGE_RETURN` TACTICAL, with **parent UP, current EMA9 gap +$17.77 and EMA9 6-second change +$5.99**, after the new YES-side EMA9 cross. This is a **SPROUT-side counterfade** rather than an earned opposite parent.
- **15:41:24:** `COMMANDER_HEIST_SEED_PROMOTED_TO_LIVING_EMA9_CUSTODY` moved NO into `PROMOTED_MAIN` even though the recorded Commander rack owner was **YES**, EMA9 gap side was **YES**, Release was not confirmed, and `continuation_precedent.current_motion_supports=false`. The prior-cross `ema9_continuation_precedent` reported an older NO historical precedent; that was enough for the current Commander promotion at `strategy_core/commander.py` lines ~918–928 and 983–1003.
- **15:41:59:** custody changed to Lazarus; **15:42:07–15:42:08:** recovered to NORMAL, then was promoted into MAIN again. This custody oscillation is material.
- The original TACTICAL entry policy was **+40% first arm / 3% trail**. Promotion substituted **+200% first arm / 5% trail** (`HEIST_SEED_TO_LIVING_LEG_RUNNER_V2`). The recorded NO bid reached **$0.10 at 15:42:33** (+81.8% gross versus entry), but never reached +200% and **no floor was recorded**. Official settlement at **15:45:08**: NO worthless, **−$9.97 net**.
- **Candidate narrow repair/test:** historical continuation may contribute evidence but cannot independently grant MAIN custody to a NO Heist seed opposing a demonstrably living YES parent without current matching EMA9/Release proof. Preserve earned anticipatory *TACTICAL* entry and make any true promotion a separate positive, source-timed determination. Do not claim that an earlier sale would certainly have filled or earned hypothetical profit.

## 6. Trade #4 NO — counter-sprout plus unprotected near-doubling

- Entered **15:47:30 NO $0.26** / 36 contracts via `HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED`, while **EMA9–EMA30 gap was +$56.18**, 30-second EMA9 change was **+$14.93**, and current parent was **UP** (although immediate native direction was DOWN). This was a tactical counter-sprout trial, not independent evidence of a durable NO parent.
- The move nonetheless became **genuinely profitable intraposition**: NO bid peaked **$0.51 at 15:49:36**, ~**+96.15% gross**, with displayed top bid depth >9,000 versus 36 contracts. At that moment, the rack still had **owned_side=YES**, but floor-management evidence briefly used **owner_side=NO** from the local counter-swing.
- The effective policy read `LIVING_LEG_BREATHING_WITH_100_PERCENT_PEAK_LOCK`: `first_arm_allowed=false`, `immediate_arm_roi=1.0` (+100%), despite the entry's 40% tactical arm policy. Since $0.51/$0.26−1 = **96.15%**, the first floor never armed. The quote then fell, and the universal three-minute TACTICAL timeout exited at **15:50:31 for $0.28**, net **−$0.28** after fees (gross +$0.72, fees $1.00).
- This is a **concrete protection-classification problem**, not simply an unprofitable entry. The delegated dynamic management in `strategy_core/tools/management.py` lines ~1311–1342 and `strategy_core/paper_runtime.py` lines ~327–416 should not give long-runner first-arm deferral to a tactical child moving *against* the actual EMA9 parent. Preserve valid MAIN living-leg breathing, the irreversible-floor rule, and full-lot collection.

## 7. Trade #5 NO — positive bounded Heist scalp

- Entered **15:52:35 NO $0.10**, 94 contracts TACTICAL, current EMA9 parent UP, via `HEIST_PARALLEL_STALLED_EDGE_RETURN`; sampled peak **$0.18 at 15:53:06**.
- Already-armed floor sold entire lot at **$0.15 at 15:53:42**, **+$3.26 net**. Preserve as a positive small tactical excursion and management control. It does not by itself prove a DOWN parent Release.

## 8. Trade #6 NO — protected first-class Mountain-edge positive control

- Entered **15:54:42 NO at modeled VWAP $0.0877** (display rounded $0.088), **267 contracts**, approx **$23.42 exposure**, PRIMARY / MAIN / `ONE_COMMANDER_PRIMARY` through `COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN` (not a generic TACTICAL Heist entry). $25 exceptional tier, $0.20 cap.
- `commander_physical_evidence` explicitly records **`RECENT_LEVEL_MATCH_RETURN`**, historical upper anchor **$76,197.03** approximately **401.83 seconds** old, current BTC **$76,201.96**, only **$4.93** from anchor, **BTC 6s −$9.10; BTC 9s −$22.31; EMA9 6s −$1.82**, and `rejection_proven=true`. The wider EMA9 parent was still UP, but the bearish *local level rejection* was source-supported; do not relabel this as a confirmed DOWN Rail.
- At **15:55:17**, sampled NO bid hit **$0.37**. Already-armed whole-position floor exited at **15:55:21 for $0.35** after **39.1 seconds**: **+$70.0341 gross, −$5.76 fees, +$64.2741 net (+257.96% of the stated net-return basis)**.
- Screenshot's “purpose unavailable” for #6 does **not** imply an anonymous engine entry. The ledger has Commander source, arc, price cap, physical evidence and level identity; it lacks the *mission-style* fields expected by the Looking Glass TACTICAL review. Add a Commander-primary display fallback in a future separately authorized UI patch.
- **Freeze this positive control** for any future sprout-fade restriction or first-floor fix. Rejecting all counter-UP NO entries would regress the successful #2, #5, and #6 opportunities.

## 9. Proposed regression matrix; NOT implemented

1. **Negative** `PID18244_3_OPPOSING_SPROUT_NO_NOT_PROMOTED`: NO seed + YES gap parent + no confirmed NO Release + `current_motion_supports=false` cannot change to MAIN on a historical NO precedent alone. Existing authorized TACTICAL rules remain independent of adviser vetoes. Check no false floor escalation to +200%.
2. **Negative/positive pair** `PID18244_4_TACTICAL_COUNTERWIND_PROTECTION`: while rack/physical EMA9 parent YES, a short NO counter-swing cannot borrow living-MAIN runner floor deferral; test explicit available +40% protective mechanism and whole-lot management without retroactive peak fills.
3. **Positive** `PID18244_6_LEVEL_MATCH_NO_PRIMARY`: preserve real-time early turn + historical level match + $0.0877 NO + exceptional MAIN tier + whole-lot protected exit.
4. **Positive** `PID18244_2_5_HEIST_OUTER_RETURNS`: preserve independent bounded tactical NO captures where there is real top/box evidence, even if broader UP parent persists; do not globally ban counter-parent trades.
5. **Dual exit controls** `PID18244_1_RELEASE_RUNWAY_VS_ARMED_FLOOR` and prior-run `PID21672_4_PROFIT_FLOOR`: study premature collection without permitting already-committed whole-lot floor reversals or weakening a proven positive.
6. **Historical baseline guards** PID17588 inherited continuation and PID21672 conflicting-old-parent trade #2 remain mandatory. Keep ONE Commander, MAIN/TACTICAL independent, EMA9 authority, EMA30 reference only, PAPER-only, loss-only Lazarus and zero partial exits.
7. **UI-only** primary Commander entry evidence display, sourced from `commander_physical_evidence`; do not invent TACTICAL mission metadata.

## 10. Scope and next actions

- **Validated:** transport hash, final modeled-paper ledger, capture completion, actual events and captured source quote chronology, selected full decisions, custody transitions, effective floor policies, associated source-code paths/branches.
- **Not done:** exact recorder-driven engine replay, counterfactual re-execution or alternative fills/ROI, fresh Windows build or changed trading settings. No evidence from hypothetical returns has been used as achieved P&L.
- **Recommended next authorized engineering step:** create targeted positive and negative tests from the immutable PID18244 event/source windows first, then narrow down (A) incorrect #3 MAIN promotion and (B) #4 tactical floor deferral, preserving the #6 winner and the existing floor and inherited-continuation controls. Validate full extracted Windows PAPER package before another 45-minute run. Avoid altering the currently frozen release until explicit user authorization.
