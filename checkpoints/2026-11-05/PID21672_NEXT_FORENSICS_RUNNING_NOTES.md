# TACHYOS — next-run forensic running notes

**Recorded:** 2026-11-05. **Status:** User observations and hypotheses for next PAPER forensic review, not implemented strategy changes or counterfactual results.

## Preserve verified release baseline
- Continue from the verified PID21672 45-minute Windows PAPER package and its documented gate. Do not restart strategy development.
- One Commander, independent MAIN and TACTICAL lanes, EMA9 authority (EMA30 as spine/reference only), existing risk discipline and whole-lot position handling.
- Preserve trade #2's narrow inherited-parent conflict correction, trade #4's successful whole-position profit protection, and Nautilus Looking Glass.
- Do not claim hypothetical trades or profit. Keep PAPER only.

## Trade #2 — negative control
- User judged #2 premature/wrong, taken in the middle of a tiny counter leg.
- Preserve rejection of early middle-of-leg purchases that conflict with the still-active supported parent; verify against recorded sequence and existing tests.

## Trade #3 NO — reevaluate as upward-test rejection / Rail–Heist transition
- User disputes the blanket conclusion that #3 was unqualified. User reports **four candles below the EMA30 with long wicks**, consistent with an **upward testing area**. This chart observation must be checked against original candle and quote timeline rather than treated as fully independently verified.
- Candidate interpretation: inherited DOWN Rail remains parent; repeated upward wicks/test attempts below EMA30 may form local upper rejection edge and emerging Heist-type bounded excursions. A well-priced NO near the upper test edge could be qualified tactically even when generic Rail-pullback-location diagnostics say false.
- The original #3 entry's MAIN `RAIL_MAIN_VALUE` intent was recorded with TACTICAL custody and a `TACTICAL_MAX_HOLD_EXIT` approximately three minutes later. User believes #3 should have stayed longer. Investigate intent-to-custody handoff, candle/wick location, actual fill and available time/runway, and whether EMA9 parent remained active during exit; do **not** assert it would have won.
- Test both potential outcomes: rejected upward test → NO excursion and possible TACTICAL-to-MAIN promotion only on earned physical continuation; accepted upward test → possible YES tactical rebound, with promotion only after a physically earned EMA9 Release. Do not buy opposite side merely because of contract age or a single cross.
- Critically, distinguish a Rail entry gate from a local Heist upper-testing-edge gate: `rail_established=false` / `entry_location_qualified=false` are Rail diagnostic failures and do not alone disprove a distinct physical Heist setup. Do not turn adviser diagnostics into Commander vetoes.

## Proposed Rail → Heist → Lean → Release watch
- After approximately **2.5+ continuous contracts** of demonstrated parent Rail ownership, increase *transition vigilance*, not automatic fading or forced Rail expiry. Rails can persist much longer.
- Look for repeated tests/wicks, EMA9 loss of expansion, meaningful bounded price swings and compression; evaluate both sideways testing and possible release bias.
- Keep MAIN aligned with inherited parent while TACTICAL independently evaluates actual Heist edges. Under one Commander, permit whole-position transfer to MAIN only once new/current EMA9 structural evidence supports ongoing custody.
- Record both old-Rail resumption and true opposite Release as possible outcomes, with post-run evidence and negative controls.
- Avoid expensive/new-contract YES assumptions; separate expiring-contract quotes from new-contract quotes.

## Incoming new run
User will add further observations while the 45-minute PAPER run proceeds. Append each observation with timing/trade ID, image or quote evidence if supplied, and whether it is provisional or validated. **No strategy code changes were authorized by this discussion.**

## New 45m PAPER run — trade #1 YES early-exit observation (2026-11-05, screen captured around 15:34:14–15:34:15 ET)
- Source: user's Nautilus screenshot from ongoing new PAPER run; screen header appears to identify `TOOL_RACK_PAPER_20261105T201005Z_PID18244`. Treat as screenshot observation pending exact export corroboration.
- Trade table: **#1 YES entry $0.370, exit $0.620, +56.11% net, +$5.42 net, +$6.25 gross**, recorded around 15:30 ET. User: **“1 out way early.”**
- At screenshot time 15:34 ET, same 15:45-settling contract showed **YES bid $0.810 / ask $0.820**, BTC current ~$76,083.29 versus target ~$75,914.65, +$168.64 above target; chart visibly shows a large green impulse and higher continuation after the entry/exit period. This is later favorable mark-to-market evidence, NOT proof that any hypothetical alternate exit would have filled or made a specific profit.
- **Next-forensics questions:** Exact #1 entry and exit timestamps; Commander exit category and structure/floor reasons; current EMA9 parent and Heist/Release watcher at exit; whether the exit fired on first slowdown / box oscillation while the new upward impulse was still expanding; how profit floor and quote-echo levels evolved, whether parent handoff to MAIN was earned before exit; whether a protective whole-lot trailing floor could avoid premature exit without sacrificing #4's proven winner-protection.
- **Scope:** Analyze as **positive entry, potential too-early exit**; do not disable protection generally, and do not assume a guaranteed alternative profit. Preserve one Commander, MAIN/TACTICAL independence, EMA9 priority and PAPER-only execution.
- Also visible #2 NO $0.190 opened around 15:34 with 49 NO contracts; **do not adjudicate #2 from a still-open screenshot**. Review eventual outcome and physical context in exported event/quote timeline.
- **Status:** Observation captured only. No new run strategy code change authorized or applied.


## New 45m PAPER run — trades #2 through #6 closed (Nautilus screenshot review, 2026-11-05)
Source: Five user-provided **Looking Glass trade-review screenshots** following the #1 snapshot, with x-axis showing approximately 15:20–16:10 ET across views. These numbers are on-screen realized PAPER ledger amounts; exact timestamps, best executable quotes, and Commander decisions require export. **Do not confuse these new-run trade IDs with the original PID21672 trades.**

| New-run trade | Role on screen | Entry → exit | Contracts | Gross P&L | Fees | PAPER net | Net % | Screen exit type |
|---|---|---|---:|---:|---:|---:|---:|---|
| **#2 NO** | TACTICAL | $0.190 → $0.360 | 49 | +$8.33 | $1.33 | **+$7.00** | +71.14% | EXIT |
| **#3 NO** | TACTICAL | $0.055 → $0.000 | 170 | −$9.35 | $0.62 | **−$9.97** | −100.00% | SETTLEMENT |
| **#4 NO** | TACTICAL | $0.260 → $0.280 | 36 | +$0.72 | $1.00 | **−$0.28** | −2.84% | EXIT |
| **#5 NO** | TACTICAL | $0.100 → $0.150 | 94 | +$4.70 | $1.44 | **+$3.26** | +32.60% | EXIT |
| **#6 NO** | PRIMARY | $0.088 → $0.350 | 267 | +$70.03 | $5.76 | **+$64.27** | +257.96% | EXIT |

New-run #2–#6 realized net subtotal **+$64.28 PAPER**; with preceding screenshot-confirmed new-run #1 +$5.42, six-trade subtotal **+$69.70 PAPER**. Not necessarily the final run total. All proceeds whole-position as presented on screen; confirm against export.

### Trade-level location and mission notes
- **#2 NO** — screen entry mission source **15:34:12 ET**; holding destination EMA9 RETURN ~$75,964.03 ±$23.81, parent leg `P002L000009`, local `G002A000030`. Apparent NO entry near a sharp small upward extension, then successful downward excursion. Candidate **positive Heist upper-edge-to-return control**. Verify entry/exit placement and whether profit was prematurely capped.
- **#3 NO** — screen entry mission source **15:40:52 ET**; holding destination EMA9 RETURN ~$75,993.18 ±$9.25, parent `P002L000013`, local `G002A000038`. Chart shows continuation UP after near-top cheap NO purchase; NO settles worthless at zero at the 15:45 contract expiry. Candidate **late cheap counter-UP fade / insufficient physical return and runway** negative control. Research candle/wick rejection quality, latest effective EMA9 parent, TP distance, clock, and whether first-minute/last-minute regulations were met; do not treat cheap quote alone as evidence that NO was favorable.
- **#4 NO** — screen entry mission source **15:47:30 ET**; BOX EDGE destination ~$76,002.03 ±$23.40, parent `P002L000013`, local `G002A000050`. Small quote gain ($0.26→$0.28) failed to cover PAPER modeled fees. **Fee-drag / micro-exit negative control**. Check whether whole-lot exit protected from a larger loss or was an over-eager take-profit; cannot decide from screenshot alone.
- **#5 NO** — screen entry mission source **15:52:34 ET**; EMA9 RETURN ~$76,132.58 ±$15.13, parent `P002L000016`, local `G002A000056`. Tactical NO upper-edge scout earned +32.60% net, followed by another top opportunity (#6). Candidate positive profitable scalp, evaluate whether exit was structurally justified rather than reflexive.
- **#6 NO** — screenshot shows **PRIMARY** position role, **purpose, destination, parent leg, local swing, and entry mission source unavailable** (instrumentation gap requiring review). Very cheap $0.088 NO purchased around a chart high and exited at $0.350 around a strong bearish candle near 15:55, with EMA9 rising but BTC retracing downward toward EMA30. **Strong positive entry/whole-lot exit example**; evaluate how the position gained PRIMARY custody and why mission parent data are unavailable. Do not assume a full new parent reversal: the visible candle alone does not prove one.

### Cross-trade forensic hypotheses
1. Why did #3's very cheap NO expire worthless during sustained UP parent movement, while #6's similarly inexpensive NO captured a rapid local downward excursion? Compare **actual top maturity, wick rejection, EMA9 parent age/slope, parent-leg runway, terminal vs mid-leg location, target and contract clock, and quote echo**; this is a higher-value test of *Heist upper edges inside directional territory* than just price caps.
2. Examine **#2 and #5 positive tactical rotations versus #4 after-fee loss**: small increments can be structurally correct but economically nonviable after spread+fees. Avoid universal fixed-profit thresholds without analyzing post-entry favorable-excursion and subsequent adverse-excursion in the full ledger.
3. Preserve **#1 premature-exit complaint**, **#6 positive large capture**, and prior-run **#4 protection positive control** when tuning hold rules. Look for when tactical returns should convert to longer MAIN custody; never transfer based only on a candle or profit size.
4. **#6 missing provenance fields** must be traced: missing mission metadata under PRIMARY is a diagnostic integrity concern, not proof the trading logic was unauthorized. Verify source lane and custody transition from events.
5. No changes authorized to existing PAPER code yet. This is forensic intake; complete source archive and event/quote/decision evidence are required before any engine correction or counterfactual performance claims.
