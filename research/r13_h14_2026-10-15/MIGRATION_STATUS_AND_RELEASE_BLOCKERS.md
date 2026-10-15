# Tachyos R13-H14 migration checkpoint — 2026-10-15 (EDT)

**STATUS: BLOCKED. PAPER-ONLY RESEARCH. DO NOT RUN H14 AGAIN until the crash and premature entry regression are repaired.**
This is an archival Git checkpoint on a new branch, NOT a complete deployment, profitable-trading validation, or authorization for real-money trading. Existing `main`, R11 and other baselines remain unchanged.

## Provenance
- Repo: `zenmillonario/KalshiBTCBot` (private).
- Archive parent: `8e7d923bdf436f31e44f2e42493eb930f510043e` (Phase13/14 WIP handoff).
- Latest local full runnable H14 Windows release ZIP SHA256 `39e4021ff6aa4d2f2b632c45e1b19d3b4a07190faf0a012a983fa00f06966b9b` (2,560,985 bytes). **Binary release ZIP is not yet committed on this branch**; retrieve from the original ChatGPT conversation or companion migration bundle; check SHA256.
- Historical H11 zero-entry source archives: PID30928, Oct 14 22:22:52–23:22:53 EDT. H11: 0 entries, 0 exits, 60 minutes. R13 Heist latched to old WIDE while physical Mountain/EMA30 domains evolved. Research documentation committed separately.
- Actual H14 run: PID30336, directory `666_lab_20261015_023320_103645_PID30336`, **02:33:20–02:50:12 EDT, Oct 15 2026**. Intended 60 minutes; stopped after ~16m52s via `UnboundLocalError` at `tachys_r15_command.py:832`. It did NOT complete the hour.
- Audit ZIP SHA256 `6f78ee95044a92eee39c6e8abb18f2be85db4aefadd6632795e709380a41251c` (43,119,853 bytes).
- Exact-session combined engine+Observer42+Navigator ZIP SHA256 `7b37ea5148aa2bed1450136c0eface4b4dd044976fa801ac31467afb0d0fb263` (62,005,969 bytes).
- Separate extracted Navigator 10-file ZIP SHA256 `4c0c88726a1764bb9151ad648e9356c0aac74eecca9156772c640d47d8fe1cd4` (157,070 bytes).
- Separate Observer42 10-file ZIP SHA256 `baf1a4e8f7452a48af482b010c61e470c0993934fc821522713eb9ae62857fdb` (18,671,271 bytes).
- Complete separate causal H14 trade report SHA256 `7930be10e2022f675c4b75d6ca013d5a3c35f6d3e311c12bf6e421c617bddeea`.
- H13 soft-force offline ZIP SHA256 `55ff33d9a619f56921cfef4f1f798106bff6687f27800f5b1540b5ab8222b40b`; H12 overlapping Heist research ZIP SHA256 `75d70e6b86f4dc76d37d61b0a9066ab40dc1a263c66c6a3e42d25bb3a10f8cbf`.

## H14 actual PAPER ledger (NOT hypothetical)
- #1 YES bought 14 @ $0.70 at 02:34:40, sold @ $0.82 at 02:44:05: +$1.68 gross, +17.14%. Source MFE held bid $0.995 (+42.14%). At 02:43:38 Sentinel repeatedly recommended COLLECT_NOW at executable full-lot bid $0.993 but Command vetoed/held; fast quote drop later tripped hard executable-bid trailing stop, **actual sale only $0.82**. Marking $0.993 would have yielded ~$4.102 gross before fees/unknown slippage; not a fill guarantee. This is an exit management defect, NOT justification to lower 35% ENTRY capacity universally.
- #2 NO bought 59 @ $0.23 at 02:37:15, sold @ $0.10 at 02:41:16 by `R15_COMMAND_EMERGENCY_60_OUTSIDE_CUSTODY`: **−$7.67 gross / −56.52%**. Peak bid $0.29 (+26.09%) before loss. **This contract later SETTLED YES**, so holding original NO to expiry would have lost all principal. A *distinct later* cheap NO tactical mission appeared: NO ask $0.061 at 02:42:09, $0.056 02:42:11, $0.016 02:42:30; WAIT/ARM from `EMA9_COUNTER_CANDIDATE_HAS_UNRESOLVED_OPPOSITION`, `CURRENT_ARC_SLOWDOWN_NEXT_LEG`, and READY revocations. Brief late NO bids $0.47 with large bid depth at 02:44:26, then $0.65 with only ~12.75 bid depth at 02:44:35, before returning near zero and settling YES. Do not assume 59 lots could exit at $0.65; late strike must harvest quickly if legitimately entered.
- Rollover 02:45:09: new ticker `KXBTC15M-26OCT150300-00`, separate PT and quotes; first fresh NO ask $0.48, then $0.47–$0.49 through 02:45:35. Command rejected `FIRST_MINUTE_PRICE_DISCOVERY`, `TACTICAL_FULL_NATIVE_BID_RANGE_NOT_OBSERVED`, `TACTICAL_OBSERVED_SWING_BELOW_REQUIRED_ROOM` and `ONE_COMMAND_SIDE_MISMATCH_WAIT`. The previous physical EMA9 leg crosses rollover, but no same-ticker completed 50–60% swing should be prerequisite for first-leg inherited entry. Later same-ticker NO bid reached $0.86 by 02:49:50; retrospective potential, not an executable fill.
- #3 YES bought 38 @ $0.26 at 02:48:19 on H13 generic `SOFT_FORCE_EARNED_ENTRY`; engine crashed with it **OPEN / UNRESOLVED**. At entry current EMA9 leg was still DOWN, age ~299s; last three 1m candles had two strong red bodies (~$151.71 combined BTC) and one tiny green body (~$8.66); BTC ~$62 below EMA9, `NO_TERMINAL_CAP`. The strict H14 structural rule returned **NOT QUALIFIED**, but generic H13 soft force was allowed through on `fresh_velocity_weakening=True` with no actual observed retreat. Last executable held bid ~$0.13 is unrealized, not booked exit. This is premature counterleg entry: wait for later new downside excursion extreme plus genuine weakening/cap or independently valid H14 third-arc/first-rebound location.
- Two CLOSED trades: aggregate **−$5.99 PAPER gross**. #3 unresolved; never count it as a closed trade.

## Priority crash fix
Frozen `tachys_r15_command.py:498–501` imports `corner_handoff_review` inside `if r13_manage_physical is not None`, but `manage_quote` at ~line 832 calls it unconditionally. If geometry is missing with a position open, `UnboundLocalError`. Move helper imports to unconditional scope; keep hard floors/safety active even when research geometry is missing. Add test `r13_manage_physical=None` while PAPER position held and valid, stale, and revalidated quotes; no crashes/no bypass.

## Other release blockers
1. #1 collection: Commander-owned terminal sale with fresh full-lot executable bid near ceiling and objective evidence of terminal stall/opposite release; preserve hard bid floor, which triggers but cannot guarantee stop-price fill. Sentinel is advisory; it cannot execute a sale by itself.
2. #2 fresh mission after prior emergency: independent cheap NO only on a new physical turn/extreme with fresh source-native quotes, depth, fee room, and quick collection; no late settlement hold by default.
3. Rollover: inherit continuous BTC EMA9 physical structure, but refresh contract ticker/PT/fees/native quote and allow first-minute exceptional continuity only when truly earned; don't require earlier same-contract profit swing.
4. #3 generic soft-force: reject one tiny counter candle + local speed lull against a strong intact leg. Keep true structural third rolling arc and first major post-crash rebound early entry.
5. Replay actual recorded native book, position inventory, and exit manager chronologically; validate winning AND false-turn controls before new supervised 1h PAPER launch. No H14 deployment just because unit tests pass. Same-side twin PAPER booking remains shadow-only until independent lots are safe.
6. One engine only, three read-only same-PID/source companions; no restart to repair attachment. Run on E: drive, collect engine+Observer42+Navigator+Nautilus evidence. Nautilus accounting may say unverified until first canonical trade ledger exists.

## Strategy doctrine to preserve
- NAEVYR=EMA9 **fast sovereign arc**, THAERYON=EMA30 slow structural spine. Physical EMA9 Zigzag arc/wall history survives 15-minute contract rollover, but quotes/fees/PT/inventory are per-contract.
- Four physical territories: Directional Dragon/Dorsal, overlapping Market Heist, alternating Mountains, and Transfer/Release. Do not create more commanders or generic independent veto blocks.
- Enter at an anticipated *corner*, not after confirmed new leg: last 2–3 arc shapes, age, average excursion, repeated resistance/support, mature ~2.5–3 arc, or first substantial rebound crest after major DOWN wall (mirror for UP). Retire fresh Heist on genuine EMA9/price expansion even if still same side of EMA30; ambiguous terrain wide/slower Heist WATCH, not automatic trade.
- Third rolling downside arc ~10:30 PM Oct14 YES, first post-crash rebound crest ~11:00 NO: no additional reversal candle or EMA crossover for physical permission; execution safety still binding.
- Fresh entries: usual ask ≤$0.50, prefer ≤$0.30; exceptional $0.50–$0.70 only verified large drop/breakout; first-minute WAIT default with rare earned inherited continuation. Sub-$0.20 allowed only when genuinely qualified, not because cheap; no arbitrary per-contract count cap. Goal at least 1 justified trade per contract, NEVER force unsafe trade.
- At true leg corners, review outgoing full-lot collection and next incoming entry independently, potentially near-simultaneous if PT/clock/economics permit. Two small opposite 1m candles do NOT overturn intact leg; can be discounted pullback.
- Losers only enter Lazarus custody. Same-side distinct-generation reentry wanted; twin within $0.05 discount or better is still SHADOW ONLY until multi-lot accounting supports both.
- Hard executable-bid peak protection rolling 5–10% on large winners, NEVER override. ~150%+ runner may expand but cash out on confirmed 6–9-second fresh quote weakness or evidenced sustained ~30-second stall, using past 12 closed gainers as context. Full-lot depth and fees matter; terminal near-$0.99 quotes merit decisive collection when no genuine expansion.
- NAVIGATOR/Observer42 shadow only; Nautilus read-only. Sentinel **light advisor only**.

## Next chat task
First audit source and reproduce UnboundLocalError with real held position; patch and negative-test. Then correct #3 H13 soft-force priority, #1 terminal sale, #2 distinct cheap NO and rollover. Reconcile true book and inventory replay, create a NEW release with new hashes only after negative controls pass. Preserve the source/branch/run ZIP hashes above. DO NOT rerun H14.
