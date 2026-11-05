# TACHYOS — PID18244 full-run verified forensics (2026-11-05)

**Audit only.** One Commander, independent MAIN/TACTICAL, EMA9 authority, EMA30 reference only, existing risk, Lazarus and whole-position protection, Nautilus Looking Glass, Windows PAPER only. No trading-strategy code changes or hypothetical fill/profit claims. This run's trade numbers are **not** the previous PID21672 trade numbers.

## Original recording verified
- Run: `TOOL_RACK_PAPER_20261105T201055Z_PID18244`
- All 8 numbered pieces reconstructed as raw `archive_chunk.bin` streams and individually SHA-256 verified.
- Reconstructed source ZIP: **678,087,269 bytes**, **492 members**, SHA-256 `2600a6273a54ee1831f6ba40aced24b998cbd6c1f3b142dfd495ac8804bb9b12`; exact match to manifest.
- Capture status: 8,245 written / 8,245 attempted / zero drops; complete and replay-ready. **Exact engine replay NOT REQUESTED / NOT PERFORMED**. Shadow quotes are not trade fill evidence.
- Final modeled PAPER ledger: start $1,000, end **$1,069.7041**; **+$80.6841 gross**, **$10.98 modeled fees**, **+$69.7041 net**, six closed whole lots, zero unresolved inventory, `PAPER_ENTRY_WINDOW_COMPLETE_FLAT`. NO real venue orders.

## Original six-trade ledger (ET, actual modeled PAPER closes)
| # | ET open to close | Side / entry to exit, qty | PAPER net | Exit cause |
|---|---|---|---|---|
| 1 | 15:30:49→15:33:31 | YES $0.370→$0.620, 25 | +$5.42 | Already-armed bid floor |
| 2 | 15:34:13→15:35:54 | NO $0.190→$0.360, 49 | +$7.00 | Already-armed bid floor |
| 3 | 15:40:52→15:45:08 | NO $0.055→$0.000, 170 | −$9.97 | Official settlement |
| 4 | 15:47:30→15:50:31 | NO $0.260→$0.280, 36 | −$0.28 | TACTICAL_MAX_HOLD_EXIT |
| 5 | 15:52:35→15:53:42 | NO $0.100→$0.150, 94 | +$3.26 | Already-armed bid floor |
| 6 | 15:54:42→15:55:21 | NO $0.0877→$0.350, 267 | +$64.2741 | Already-armed bid floor |

## Mechanism and required next forensic controls

**#1 YES — good entry, early-exit concern.** TACTICAL Heist YES promoted to release custody at ~15:33:09. YES bid peaked $0.66 at 15:33:24; $0.6208 committed floor caused sale $0.62 at 15:33:31. Same ticker's bid later observed $0.81 at 15:34:12. The armed floor did function correctly; any future longer Release hold policy must be determined *before* committing a floor, preserve prior PID21672 #4's whole-lot floor control, and cannot retroactively claim later fills.

**#2 NO — positive Heist.** NO $0.19 entered at a meaningful upper-edge excursion around 15:34 while current EMA9 physical direction UP; returned and exited at $0.36, +$7.00 net. Do not ban all counterparent tactical entries. Old PID21672 #2 was a *different* negative-control trade.

**#3 NO — wrong-side sprout fade plus invalid MAIN promotion.** Entry 15:40:52 NO $0.055, EMA9 gap +$17.77, 6s EMA9 +$5.99 and parent YES. 15:41:24 Commander promoted NO to `PROMOTED_MAIN` via `COMMANDER_HEIST_SEED_PROMOTED_TO_LIVING_EMA9_CUSTODY` even though live rack owner/gap side YES, Release unconfirmed, and `continuation_precedent.current_motion_supports=false`. It relied on qualified historical NO cross precedent; source `strategy_core/commander.py` lines ~918–928 and 983–1003. It bounced through Lazarus ~15:41:59, recovered and re-promoted ~15:42:08. Tactical +40%/3% arm policy replaced by MAIN +200%/5% runner; NO bid peaked $0.10 at 15:42:33 (~82% gross versus purchase) but no floor; settled worthless −$9.97. **Candidate negative regression:** historical NO precedent alone must NOT upgrade NO tactical seed to MAIN opposite a current living YES parent without current physically earned NO Release/EMA9 handoff.

**#4 NO — counter-sprout and protection-classification error.** Entry NO $0.26 15:47:30 with current YES parent, EMA9–EMA30 gap +$56.18 and 30s EMA9 +$14.93. Despite user's characterization as an unsuitable sprout fade, it achieved a real temporary NO excursion: bid **$0.51 at 15:49:36** (96.15% gross against $0.26; observed top displayed quantity >9,000 versus lot 36). Rack owner at peak **YES**, but dynamic management owner evidence treated local NO downswing as `owner_side=NO` and chose `LIVING_LEG_BREATHING_WITH_100_PERCENT_PEAK_LOCK` (`first_arm_allowed=false`, `immediate_arm_roi=1.0`). It therefore did not arm its earlier tactical 40% first floor. At ~15:50:31 mandatory 180s timeout sold $0.28, −$0.28 net after fees. Relevant sealed source `strategy_core/tools/management.py` lines ~1311–1342, `strategy_core/paper_runtime.py` lines ~327–416, `paper_execution.py` ~700–755. **Candidate negative regression:** tactical NO counter to actual current UP parent cannot borrow same-side living MAIN first-arm deferral simply because its local child leg briefly turns NO. Preserve structurally earned MAIN breathing and irreversible floors.

**#5 NO — positive bounded tactical return.** Entry $0.10, in-run bid reached $0.18, whole lot out $0.15, +$3.26 net. Preserve true upper Heist excursion controls.

**#6 NO — crucial positive first-class Commander Mountain edge.** MAIN/PRIMARY `ONE_COMMANDER_PRIMARY` entered 267 NO at VWAP **$0.0877** via `COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN`, exceptional $25 tier, $0.20 cap. Current BTC $76,201.96 versus historical upper anchor $76,197.03 (difference $4.93; anchor age ~401.83s). BTC 6s −$9.10, 9s −$22.31; EMA9 6s −$1.82; physical `rejection_proven=true`. It caught a meaningful counter-UP downturn without proof of a completed DOWN parent Rail. Bid peaked $0.37 15:55:17; protected full lot sold $0.35 at 15:55:21 (39.1s held), +$64.2741 net. **Never weaken/bypass this entry or floor when fixing #3/#4.** The Nautilus review "purpose unavailable" is UI metadata mapping: Commander-specific entry provenance exists under `commander_physical_evidence`, but no TACTICAL mission record.

## Proposed tests before any authorized code change
1. #3 wrong-side history-only promotion blocked; maintain true same-side current physically proven Release/MOUNTAIN transfer and historical PID17588 earned inherited continuation.
2. #4 tactical counterwind first-floor arming not replaced by MAIN living-parent grace when actual current EMA9 parent is opposite; no retrospective peak sale.
3. #6 Commander Mountain edge + sub-$0.20 $25 cap + original whole-lot floor **positive control**.
4. #2/#5 physical Heist upper-edge countertrend **positive controls**; avoid categorical NO fade veto.
5. #1 Release early exit versus irreversible-floor protections; prior PID21672 #4 protected winner and original PID21672 #2 parent conflict **must not regress**.
6. Looking Glass Commander-primary provenance fallback separate UI-only change.

**Release status:** current Windows PAPER baseline remains unchanged; no next run package built from these hypotheses. Detailed report/evidence are conversation artifacts `PID18244_FULL_RUN_FORENSICS_2026-11-05.md` (SHA-256 `57caefb92973d95b9f204af0a476cab74993b04c745722b25d552df15cd92f4e`) and `PID18244_FORENSIC_EVIDENCE_2026-11-05.json`. Never infer counterfactual profits from sampled quotes; exact engine replay not executed.
