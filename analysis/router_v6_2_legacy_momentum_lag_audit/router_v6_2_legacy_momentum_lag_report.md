# Router V6.2 — Legacy 90/75/60 Momentum Lag Audit

Purpose: isolate the frozen Core detector from downstream paper authority.

For each Hand/Boundary transfer epoch, this replay reconstructs the legacy evaluate_strategy() inputs from archived YES/NO ask telemetry and asks:
1. Would the frozen 90/75/60 detector qualify the transfer side at the transfer moment?
2. If not, when is the first moment it would qualify before the next transfer or contract close?

Rules reproduced exactly:
- ask must be 0.40–0.80
- current ask must exceed both 75s and 60s reference asks
- EARLY: 90→75 >= 1c and 90→60 >= 3c
- CONFIRMED: ask >= 0.50, 90→75 >= 2c, 90→60 >= 5c
- archived reference quote must be within 3s of its requested lookback, matching get_price_at()

Transfer epochs audited: 10
Legacy Core already qualified at transfer: 1/10
Legacy Core qualified at any point in transfer epoch: 3/10
Clean/no-path-interference epochs qualified at any point: 1/4
Settlement correctness at first reconstructed legacy qualification: 3/3
$10 hold sum from first reconstructed legacy qualification: +18.56

## Legacy state exactly at transfer

- ASK_ABOVE_80C: N=1 transfer-side-settlement=1/1
- ASK_BELOW_40C: N=2 transfer-side-settlement=1/2
- MOMENTUM_TOO_WEAK: N=3 transfer-side-settlement=3/3
- NO_90_75_60_HISTORY: N=2 transfer-side-settlement=1/2
- NO_CONTINUATION: N=1 transfer-side-settlement=1/1
- QUALIFIED_CONFIRMED: N=1 transfer-side-settlement=1/1

## Per epoch

- tachys_v9_5a_price_freshness_active_treasury #6 KXBTC15M-26SEP181145-45 SAME_SIDE_CONTINUATION_RESET HAND_AUTHORITY_TRANSFER -> NO | ask=0.932 | atTransfer=ASK_ABOVE_80C | firstLegacy=NONEs ask=NA grade=NA | pathInterference=1 loggedCore=0 preentry=1 finalAttempt=0 | settle=NO hold$10=NA
- tachys_v9_5a_price_freshness_active_treasury #41 KXBTC15M-26SEP181645-45 SAME_SIDE_CONTINUATION_RESET BOUNDARY_RELEASE -> NO | ask=0.006 | atTransfer=NO_90_75_60_HISTORY | firstLegacy=NONEs ask=NA grade=NA | pathInterference=0 loggedCore=0 preentry=0 finalAttempt=0 | settle=YES hold$10=NA
- tachys_v9_5a_price_freshness_active_treasury #44 KXBTC15M-26SEP190345-45 SAME_SIDE_CONTINUATION_RESET HAND_AUTHORITY_TRANSFER -> NO | ask=0.62 | atTransfer=QUALIFIED_CONFIRMED | firstLegacy=5.319s ask=0.62 grade=CONFIRMED | pathInterference=1 loggedCore=1 preentry=1 finalAttempt=0 | settle=NO hold$10=6.129
- tachys_v9_5a_price_freshness_active_treasury #68 KXBTC15M-26SEP190815-15 OPPOSITE_SIDE_REVERSAL_RESET BOUNDARY_RELEASE -> YES | ask=0.75 | atTransfer=NO_90_75_60_HISTORY | firstLegacy=NONEs ask=NA grade=NA | pathInterference=0 loggedCore=0 preentry=0 finalAttempt=0 | settle=YES hold$10=NA
- 2026-09-19_v9_5a_late_mature_shadow_5h #1 KXBTC15M-26SEP191245-45 SAME_SIDE_CONTINUATION_RESET BOUNDARY_RELEASE -> YES | ask=0.54 | atTransfer=MOMENTUM_TOO_WEAK | firstLegacy=NONEs ask=NA grade=NA | pathInterference=0 loggedCore=0 preentry=0 finalAttempt=0 | settle=YES hold$10=NA
- 2026-09-19_v9_5a_late_mature_shadow_5h #11 KXBTC15M-26SEP191415-15 OPPOSITE_SIDE_REVERSAL_RESET BOUNDARY_RELEASE -> NO | ask=0.37 | atTransfer=ASK_BELOW_40C | firstLegacy=216.979s ask=0.51 grade=EARLY | pathInterference=0 loggedCore=1 preentry=1 finalAttempt=1 | settle=NO hold$10=9.6078
- 2026-09-19_v9_5a_late_mature_shadow_5h #13 KXBTC15M-26SEP191415-15 SAME_SIDE_CONTINUATION_RESET BOUNDARY_RELEASE -> NO | ask=0.69 | atTransfer=MOMENTUM_TOO_WEAK | firstLegacy=NONEs ask=NA grade=NA | pathInterference=1 loggedCore=0 preentry=0 finalAttempt=0 | settle=NO hold$10=NA
- 2026-09-19_v9_5a_late_mature_shadow_5h #15 KXBTC15M-26SEP191430-30 OPPOSITE_SIDE_REVERSAL_RESET BOUNDARY_RELEASE -> NO | ask=0.047 | atTransfer=ASK_BELOW_40C | firstLegacy=NONEs ask=NA grade=NA | pathInterference=1 loggedCore=0 preentry=0 finalAttempt=0 | settle=YES hold$10=NA
- 2026-09-19_v9_5a_late_mature_shadow_5h #19 KXBTC15M-26SEP191515-15 SAME_SIDE_CONTINUATION_RESET BOUNDARY_RELEASE -> NO | ask=0.79 | atTransfer=NO_CONTINUATION | firstLegacy=NONEs ask=NA grade=NA | pathInterference=1 loggedCore=0 preentry=0 finalAttempt=0 | settle=NO hold$10=NA
- 2026-09-20_v9_5a_swirl_orbit_long_01 #18 KXBTC15M-26SEP192115-15 SAME_SIDE_CONTINUATION_RESET HAND_AUTHORITY_TRANSFER -> NO | ask=0.76 | atTransfer=MOMENTUM_TOO_WEAK | firstLegacy=3.341s ask=0.78 grade=EARLY | pathInterference=1 loggedCore=1 preentry=1 finalAttempt=0 | settle=NO hold$10=2.8205

## Discipline

- This is an audit of the existing legacy detector, not a new entry detector.
- Reconstructed qualification means only evaluate_strategy() would have passed; downstream phase, arc, structural, mutex, cooldown, and paper gates are intentionally excluded.
- If profitable transfer epochs remain invisible to this reconstructed detector, that is direct evidence that the 90/75/60 proposal generator can lag the battlefield reset.
- If it qualifies quickly but no logged CORE signal/final attempt appears, the loss occurs downstream in the permission path instead.
- No V9.5A authority changes.
