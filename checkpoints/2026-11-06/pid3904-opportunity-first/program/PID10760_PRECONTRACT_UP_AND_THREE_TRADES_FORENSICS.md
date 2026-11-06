# TACHYOS PID10760 — verified pre-contract UP inheritance and trade review

**Forensic assessment · November 5, 2026, Eastern Time · PAPER only**

## Source integrity and limits

- Original run: `TOOL_RACK_PAPER_20261106T024325Z_PID10760`.
- All seven `archive_chunk.bin` payloads matched their transfer-manifest SHA-256 checks. Reconstructed original: **601,531,000 bytes**, SHA-256 `f676cdc8b44688f92382972c489dbb2eb745096ab1f8a6216493e7b00a61a0ff`, **399 ZIP members**, CRC verified.
- **67/67 sealed program source hashes matched**. The actual release is `TACHYOS_PID14156_HEIST_HANDOFF_PATIENT_MOUNTAIN_45M_PAPER_20261105`, determined from `NEXT_RUN_STATUS.json`, `APPROVED_STRATEGY_CHANGES.json`, and matching `commander.py`/`commander_candidates.py` hashes. The older embedded `runtime_revision` text refers to an unchanged PAPER runtime and does **not** imply the old trading Commander was running.
- Capture **7,607 attempted, 7,607 written, zero drops**, complete and replay-ready. The original full-engine replay **was not performed**.
- Recorded PAPER cash **$1,000.00 → $984.33**, net **−$15.67**, gross **−$11.66**, fees **$4.01**, **three closed positions**, zero open. No venue fills or live orders.

## New priority: missed UP leg already developing before 21:45 rollover

The chart observation is supported by the recorder as a **developing BTC UP movement** before the new 21:45 contract. The live observation history begins at approximately **21:43:28**, so it cannot prove a fully established inherited EMA9 parent prior to that startup.

| ET | Physical and execution evidence |
|---|---|
| **21:44:58** (expiring contract) | BTC ~$75,998, BTC +$14 over 9s, EMA9 still below EMA30, no formally established UP parent. This is a developing pre-rollover push, not a validated historical UP rail. |
| **21:45:00–21:45:17** | Six market-discovery queries returned **`NO_CURRENT_OPEN_KXBTC15M_MARKET`**. The engine continued referencing the expired ticker. |
| **21:45:20.531** | First discovery of new `KXBTC15M-26NOV052200-00` contract, approximately **20.5 seconds after open**; `MARKET_ROLLOVER` recorded at 21:45:20.669. |
| **21:45:21** | New-contract YES ask **$0.49**; physical parent still `NONE`, current UP arc ~14.9s vs ~21.1s contract age. A purchase is **not automatically qualified** by quote alone. |
| **21:45:30** | YES ask **$0.53**, BTC ~$76,019, BTC 60s +~$25.2, EMA9 60s +~$5.4. Physical parent still `NONE`. Current arc ~15.6s old while contract already ~30s old. TP indicated YES `STARTING_LEG_FAVORED`. |
| **21:45:45** | YES ask **$0.56**, BTC 60s +~$49.9, EMA9 60s +~$10.4; gap still ~−$6.47. The quote already exceeds the exceptional ≤$0.55 inherited-continuation cap. |
| **21:46:00** | BTC 60s +~$58.5; EMA9 60s +~$12.1; gap crossing near zero; new contract YES ask ~$0.61. |
| **21:46:27.335** | Native parent first recorded as **UP**; YES ask ~$0.62, outside the regular and exceptional opening value limits. |
| **21:49:45**, #1 | BTC ~$76,174, 60s BTC +$64.10, EMA9 gap **+$42.01**, parent UP; YES ask ~$0.83. Commander bought **NO $0.18**, not with-parent YES. |

**Concrete admission failure.** In the new contract's opening five minutes, **no eligible aligned MAIN YES proposal** was recorded. The primary proposal repeatedly returned `MOUNTAIN_EDGE_ONLY_NO_MIDLEG_ALIGNED_ENTRY`, and the rack used Mountain edge-WAIT responses, even as EMA9 direction became UP and YES prices climbed. The existing exceptional opening route in `strategy_core/commander_candidates.py` lines ~1619–1659 requires an observed historically qualified directional parent and, among other criteria, **the current arc age to exceed the new contract's age by >1 second**. At 21:45:30 and 21:45:45 the **current child arc was ~14 seconds younger than the new contract** despite the developing pre-rollover BTC push. The route thus did not have the required inherited-parent provenance. Its ≤$0.55 exceptional quote window also disappeared as evidence grew.

This is a **rollover source/discovery plus missing positive continuation admission** case, not merely a poorly timed individual trade. It does **not** justify blindly buying the first $0.49 ask: the true parent had not yet been physically confirmed. It warrants constructing a *source-causal inherited EMA9 parent/child-arc lineage* positive briefing test that can survive a local arc reset, together with independent strong-moving and weak-opening negative controls. No guessed fill, gain or alternate ledger.

## Trade-by-trade causal findings

| Trade, ET | Actual PAPER | Recorded source cause | Forensic implication |
|---|---|---|---|
| **#1 NO** 21:49:45→21:53:57 | 131 NO, $0.18→$0.14, **−$7.71 net** | Commander `COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN` bought NO with parent **UP**. At entry EMA9 gap **+$42.01**, BTC 60s **+$64.10**, 9s **+$11.29**, 30s +$17.53; parent not terminal-ready. Exit later `COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT`; peak NO bid $0.23, no armed floor. | Positive earlier YES continuation absent; later cheap NO level-match was admitted against a living expanding parent. Examine actual upper rejection quality/current parent terminal proof without blanket-banning true #6 extreme returns. |
| **#2 NO** 22:01:09→22:04:10 | 27 NO, $0.35→$0.29, **−$2.44 net** | MARKET_HEIST TACTICAL upper return; at entry parent UP, gap **+$24.28**, BTC 30s +$75.18. At exit parent still UP, gap **+$36.92**. Exact exit `TACTICAL_MAX_HOLD_EXIT`, age ~181s, peak NO bid $0.41, no floor. | Later same-ticker NO bid became **$0.78 around 22:12** and **$0.999 near 22:14**, with source top size >27. A genuine large DOWN excursion subsequently emerged, but not yet earned at 22:04. Compare transition/re-entry timing with guarded custody extension rather than unconditional hold. No alternate fill claimed. |
| **#3 YES** 22:20:57→22:22:45 | 30 YES, $0.31→$0.15, **−$5.52 net** | Commander `COMMANDER_MOUNTAIN_BOUNCE_OWNS_CONTRACT` entered when native EMA9 parent DOWN, gap **−$63.55**, 9s BTC **−$10.91** and current DOWN arc ~14s old. TP tagged `BOUNCE_FAVORED YES` despite required move to target **$66.11** vs comparable parent amplitude **$37.04**, and target lying in EMA junction. Exit `LAZARUS_HARD_ADVERSE_STRUCTURE`, no floor. | Weak bounce/terminal localization and unsupported winning-leg classification allowed expensive opposite-parent YES at a developing DOWN leg. Future negative control should distinguish genuine mature lower edge from this child-scale bounce. |

## Next controlled engineering tests — recommendations only, NOT implemented

1. **Pre-contract inherited UP / first-minute positive test:** preserve last 2–3 minutes of current observed EMA9 parent geometry across contract rollover, including verified origin/continuity and partial child-arc reset; admit a positively briefed same-parent YES only when both current physical progress and target/runway prove it, with existing exceptional price/tier and one-Commander limits. Negative controls: cold start/unobserved origin, price already above cap, unproven current parent, first-minute weak cross, stale book or no active new market.
2. **Timely ticker discovery:** source logged six `NO_CURRENT_OPEN_KXBTC15M_MARKET` responses until +20.5s. Review market-list timing and early future-market selection without assuming Kalshi exposed a currently open book before it did.
3. **#1 counter-UP top:** a cheap level match alone must not usurp a strong living UP parent. Preserve historical PID18244 #6 NO $0.0877→$0.35 winner and all mature-arc exceptions.
4. **#2 Rail–Heist→Release custody:** inspect actual handoff after the 22:04 timeout, and evidence for a later NO entry. Keep a defended three-minute timeout for genuinely unsupported counterpositions; do not use hindsight bids as an execution claim.
5. **#3 expensive wrong-location bounce:** require meaningful lower parent-edge maturity and credible target-side runway before MAIN classifies a small child counter-bounce as `BOUNCE_FAVORED`. Preserve established leg pullbacks, whole-lot profit floors, Lazarus, one Commander, MAIN/TACTICAL and Nautilus.

**No strategy source changes, no new executable package, no exact original-run replay, and no hypothetical trades or returns** in this forensic review. Source-bound machine-readable evidence is supplied alongside this document.
