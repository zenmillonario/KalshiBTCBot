# TACHYOS — new 45-minute PAPER run screenshots, trades #1–#3 (Nov 5 2026 ET)

**Forensic intake only.** User screenshots of Nautilus Looking Glass; full run archive, run/PID, entry source, and decision/quote trace not yet provided for this run. NOT full-run forensics, NOT hypothetical profit/fill evidence. Do not conflate these trade IDs with previous PID14156 or PID18244.

## User observation
- "**2 would have won, 3 is like it tried to get the worst entry location**."
- Wants to **hold valid directional moves longer** while avoiding buying **wrong-side, expensive, mid-child-leg counters**. Preserve one Commander, EMA9 main direction, independent MAIN/TACTICAL, floor/risk controls and PAPER-only architecture.

## On-screen realized data (trade review)
| Trade | Side | Role | Entry ET | Exit ET | Contracts | Entry → exit | Net PAPER | Peak bid | Engine floor |
|--|--|--|--|--|--|--|--|--|--|
| #1 | NO | PRIMARY | 21:49:45 | 21:53:57 | 131 | $0.180 → $0.140 | −$7.71 (−30.91%) | $0.230 | Not armed |
| #2 | NO | TACTICAL | 22:01:09 | 22:04:10 | 27 | $0.350 → $0.290 | −$2.44 (−24.70%) | $0.410 | Not armed |
| #3 | YES | PRIMARY | 22:20:57 | 22:22:45 | 30 | $0.310 → $0.150 | −$5.52 (−56.62%) | $0.300 | Not armed |

**#2 NO — strong hold/exit forensic candidate:**
- The #2 NO entry appears during upper-side testing near ~22:01, with larger BTC DOWN movement **later in the same 22:00–22:15 contract**, clearly visible around ~22:09–22:12.
- Actual held only **181 seconds**; a TACTICAL 180-second max-hold closure is a high-priority **hypothesis**, NOT a proven exit reason without the Commander event/close record.
- Looking Glass mission: TACTICAL `EMA9 RETURN` to BTC `$76,097.37 ± $9.49`; parent leg `P000L000005`, local `G000A000027`; entry mission source 22:01:08 ET. NO entry $0.35 (not cheap by A+ tier), screen peak bid $0.41, exit $0.29, no floor armed.
- User judges it **could have won with longer custody**. Investigate whether no physical parent termination had occurred at exit; whether TACTICAL→MAIN promotion was warranted upon later DOWN EMA9 ownership; and actual available NO bid/ask with time left before close. The screenshot's later favorable movement is **not proof of a specific hypothetical executable fill or guaranteed settlement**.
- Avoid unlimited 3-minute rule extension without stage/parent/contract-runway proof; preserve short tactical exits that protect against genuine reversals. Compare original PID18244 #3 wrong-side promotion negative control and #6 positive MAIN extreme.

**#3 YES — wrong-location, against DOWN EMA9:**
- A PRIMARY YES purchased at **$0.310** at ~22:20:57 during a strong BTC DOWN phase, after a small countertrend upward correction. The chart shows EMA9 falling **below** EMA30 (at review snapshot EMA9 ~$75,936.83, EMA30 ~$76,003.68), with lower highs/lows and immediate resumed selling; no mature bottom/physical YES parent handoff obvious at purchase.
- Trade exits at 22:22:45 for $0.15 with peak bid $0.30 (not above entry) and no floor armed. Position provenance in Looking Glass shows `Purpose unavailable` because PRIMARY can be Commander-native; investigate actual Commander's entry reason, TP/level-match authority, parent/emerging leg, quote value, and whether current physical edge location and runway were ever earned.
- User calls it among the worst entry locations. Candidate **negative** regression: expensive/late YES against demonstrably expanding DOWN EMA9, on a mid-child bounce rather than a matured lower edge; no blanket ban on properly proven lower-edge returns.

**#1 NO context:**
- PRIMARY NO $0.18 entered ~21:49:45 on/near sharp rise after initial up impulse; closed ~21:53:57 at $0.14, −$7.71. Peak bid $0.23, floor not armed. Inspect independently for premature or bad location; avoid claiming effect of later **different contract** drop.

## Next-forensic tasks
1. Verify actual run ID, source release/SEALED hashes, complete original six/other numbered-part transport manifest, and exact ledger.
2. #2 obtain exact `exit_reason`, role/timeouts, EMA9 parent at original exit, position-development and custody handoff eligibility, quote bids after exit until 22:15; check source-bound tests of valid directional extension.
3. #3 obtain actual native EMA9 gap/slope, BTC 6/9/30/60s, true lower edge maturity, admission category and quote depth; compare fixed PID19616 false level-match and PID14156 late counterparent YES negative controls.
4. Preserve original PID18244 #6 great NO Mountain-entry positive and PID21672 #4 full-lot protection; no new source changes or hypothetical P&L based solely on screenshots.
