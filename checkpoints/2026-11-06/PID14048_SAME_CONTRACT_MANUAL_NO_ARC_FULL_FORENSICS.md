# PID14048 — Verified same-contract manual DOWN / PAPER NO comparison (Nov 6, 2026)

**Forensics only — no strategy patch or next PAPER ZIP issued.** One Commander, independent MAIN/TACTICAL, EMA9 authority, EMA30 spine, existing whole-lot floors and Lazarus, PAPER-only bot. The user's manually profitable real Kalshi DOWN trade is **not** included in the bot's PAPER ledger.

## Original immutable source
- Run: `TOOL_RACK_PAPER_20261106T091604Z_PID14048` (04:16–05:03 ET).
- All 7 original transport pieces independently SHA-256 checked and reconstructed. Source ZIP **572,452,852 bytes**, SHA **`31eea05ad08bae678bae1efaa5eb24053dc513f6d7987049d7a10aa7c2b97c05`**, 434 ZIP members, CRC PASS.
- 67/67 captured sealed source hashes match both archived program and verified `TACHYOS_PID3860_MATURE_ARC_STALL_HARVEST_45M_PAPER_20261106.zip`. No older source relapse.
- 8,181/8,181 captured calls, 0 dropped, 8,179 Commander decision rows; previous SHA-pointer chain PASS; no original/modified engine replay.
- PAPER: three closed trades, cash **$1,000→$1,024.1875**, gross **+$31.4475**, fees **$7.26**, net **+$24.1875**; no unresolved position, no venue orders.

## Same-contract evidence — user manual trade
User TradingView screenshot highlights the mature upper arc and repeated failed high tests ~04:30–04:45 ET. User Kalshi screenshot shows **DOWN** on **BTC 15 min target $76,042.80**, closed ~04:44, displayed cost **$50**, payout **$197.17** (implied +$147.17 / +294.34% before fees not shown). Manual entry time/price unknown. These are *manual trade* records, not simulated TACHYOS profits.

**PAPER trade #2 is the SAME target/ticker `KXBTC15M-26NOV060445-45`**: NO 91 contracts bought **04:40:00 at $0.26**, sold **04:41:27 at $0.54**, **+$22.66 net PAPER**. Entry reason `RELEASE_CONFIRMED_LEVIATHAN_HANDOFF`, MAIN/PRIMARY custody `LEVIATHAN_RELEASE`, despite old positive EMA9–EMA30 gap +$53.75. The bot **correctly anticipated NO release before EMA9/EMA30 crossed (~04:46)**, so preserve this as a positive entry control.

The entry/execution evidence shows an important **hold-policy conflict**: executor peak bid **$0.58**, armed floor **$0.5626** (3% trailing), exit $0.54. At 04:41:27, BTC9 **−$30.31**, BTC30 **−$48.97**, EMA9_6 **−$6.06**, and native EMA9 parent was **NO**, with no mature terminal DOWN edge. It protected +$22.66 correctly, but the confirmed Release was still moving; ask whether the same tight protection should govern a structural Leviathan. Do not retroactively widen an armed floor or claim an alternative fill. **Later, recorded same-contract NO bids: $0.69 at 04:42, $0.922 at 04:43:30, $0.959 at 04:44 and $0.998 at 04:44:30, with displayed depth >=91 at last two times**; source observations, not hypothetical executions.

Parent-scale reference had captured upper high **$76,167.11 ~04:26**, a failed retest **$76,159.68 ~04:32**, and lower high **~$76,121.57 ~04:36**. New-contract NO asks ~$0.19 at 04:32 and ~$0.17 at 04:36:30 but the Commander WAITed until confirmed 04:40 release at $0.26. These are *candidate earlier upper-edge windows only*; do not assume a qualified fill from hindsight. The **previous-contract** #1 cheap NO scout at 04:26:25 $0.015→$0.0255 at 04:27:55 (+$7.2175 PAPER) was a separate 04:15–04:30 contract; do not transfer its quotes.

## Independent later risk — #3 YES and lower-profit stalled collection
#3 **05:00:32 YES $0.43 x55**, parent/EMA gap UP +$15.76 but BTC30 −$12.32 and BTC60 −$19.92; exceptional `COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION`. At **05:01:50** recorded YES bid reached **$0.63** (full displayed depth). At **05:01:55–05:02:10** a mature UP arc stalled; current bid had receded to **$0.60–$0.57**. Floor never armed; sold **05:03:32 $0.36, −$5.69 net** under `COMMANDER_MOUNTAIN_ONLY_HELD_LEG_TERMINAL_EDGE`. The newly introduced fee-positive harvest in `strategy_core/custody_evidence.py` ~lines 162–223 requires an exact high-water *current* full-lot bid and specific failed-reextension/repeated-Heist proof at same time: bid peak and physical stall do **not** necessarily coincide. Test near-peak profitable hover **prospectively**, with current executable bid, fees and genuine maturity; preserve first-slowdown breathing for live runners and all historic floor positives.

## Read-only Construct and next gates
- Original source/ZIP/67-file seal, six-part original verification, 8,179-row previous-hash chain and observed trade/quote controls PASS. **Behavioral Release hold and non-Release hover remain REVIEW_NEEDED**; no patched source was run and no modified-engine profit claimed.
- Required next acceptance controls: preserve positive trade #2 anticipatory NO release and PID18244 #6 exceptional edge; test if parent-scale repeated resistance at 04:32–04:36 should merit earlier scouting; test healthy release hold versus protected peak floor; test #3 05:01:50 peak → later stalled positive quote without demanding exact simultaneity; preserve real Heist/whole-lot protection and patient WAIT controls.
- Next release would require explicit authorized changes, exact source-bound controls, full chronological Construct, historical suite, extracted ZIP preflight/Windows capture/export, Looking Glass JS and integrity, plus new PAPER observations. No code modified here.

Conversation artifacts: `PID14048_MANUAL_ARC_AND_FULL_RUN_FORENSICS_2026-11-06.md`, `PID14048_SOURCE_BOUND_MANUAL_COMPARISON_2026-11-06.json`, `PID14048_READONLY_ARC_COMPARISON_CONSTRUCT.py`, `PID14048_ARC_COMPARISON_CONSTRUCT_RESULTS.json`. 
