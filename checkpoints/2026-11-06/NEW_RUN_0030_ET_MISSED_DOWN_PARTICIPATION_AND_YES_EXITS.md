# TACHYOS — early November 6, 2026, 00:30 ET, ongoing new PAPER run screenshot

**Evidence class: user Nautilus screenshot observation only; full run export not supplied.** Do not identify unknown run PID from this crop; do not infer completed run, actual post-exit fills, causal Commander reasons or hypothetical profits. No strategy changes authorized from this screenshot. Earlier PID10760 release is verified offline but this screenshot does not establish which deployment is active.

## Observed screenshot
- Looking Glass chart spans ~23:55 to 00:30 ET. Multiple descending waves and lower recoveries into ~00:30; EMA9 (NAEVYR) **$75,443.43**, EMA30 (THAERYON) **$75,506.46**, so fast gap **−$63.03** at screenshot. Target marked around **$75,489.05**. This is a **current** snapshot; do not back-project the exact indicator value to earlier trades.
- Trades ledger shows only two completed YES trades; **no NO entries displayed** despite substantial downward BTC movement in the viewed interval.
  - **#1 YES 00:09** entry **$0.076**, exit **$0.001**, net **−$24.65**, −98.88% net as displayed. Chart marker at/near lower leg; possible counter-DOWN bottom attempt. Need actual signal and role/venue/quote traces.
  - **#2 YES 00:24** entry **$0.190**, exit **$0.240**, net **+$1.29**, +13.11% net as displayed. User says '**missed opportunities and early exit**.' The observed lower-edge rebound may have allowed a larger excursion; chart subsequently rolled over, so no profitable longer exit is assumed. Need exact exit/peak bid/EMA structure/floor and quote ladder.
  - Screenshot realized subtotal of two trades = **−$23.36 net PAPER**; not necessarily final run result.
- At screenshot the Looking Glass announces `Current physical observations are unavailable or stale`, no open positions and `NO_TOOL_INTENT`. This may be a current-source telemetry limitation, not yet proven causal for earlier missed entries.

## Forensic goals
1. **Positive with-EMA9 admission:** Trace why Commander/MAIN did not join NO in a sustained descending Mountain/Rail or rolling DOWN parent across ~00:00–00:30. Map 9EMA parent ancestry, rotations, early rollover, price/cap, quote source freshness, time-to-contract-close, and exact candidate reasons. This aligns with prior PID14156/PID10760 direction-starvation findings.
2. **#1 false bottom:** Determine if YES was entered in the middle of an active DOWN leg or at a genuinely mature lower edge, and whether the physical return/runway proof supported a $0.076 counter-parent entry. Do not ban well-proven Heist returns by category.
3. **#2 custody/early exit:** Establish exact exit reason, floor arming, high-water executable YES bids, tactical vs MAIN intent, physical parent at exit, and whether a longer hold would have been structurally justified at that time. Do not assert counterfactual profit from future candles alone.
4. **Observability:** Investigate if `Current physical observations are unavailable or stale` correlates with `NO_TOOL_INTENT` or happens only in review view.
5. **Regression controls:** Preserve PID18244 #6 cheap NO mountain-edge win and executable whole-position protection, valid Heist tactical rotations, PID10760 pre-open continuation, independent MAIN/TACTICAL under ONE Commander, EMA9 authority, price discipline and PAPER only.

## Next step
Await the completed first-review ZIP, ALL numbered run ZIP parts, transfer manifest, READ_ME_FIRST and Windows completion status; verify archive identity/hash and original decision stream. This note records observations, **not changes**.


## Subsequent Looking Glass trade-review screenshots: #3 YES and #4 NO
**Source:** Two additional user screenshots of the *same ongoing PAPER run* around 00:35–00:39 ET. Do not infer PID, engine reason, or final run result. These are separate from earlier historical runs and from the previously recorded #1/#2 entries.

| # | Side | Visible role | Entry → exit | Quantity | PAPER net | Gross P&L | Entry mission source / target |
|---|---|---|---|---:|---:|---:|---|
| **#3** | YES | TACTICAL | **$0.270 → $0.380** | 35 | **+$2.78 (+27.97%)** | +$3.85 | **00:30:33 ET**, EMA9 RETURN `BTC $75,434.97 ± $11.60` |
| **#4** | NO | TACTICAL | **$0.400 → $0.240** | 23 | **−$4.37 (−45.57%)** | −$3.68 | **00:35:11 ET**, BOX EDGE `BTC $75,242.55 ± $26.77` |

- #3 mission parent `P000L000009`, local swing `G000A000024`; #4 mission parent `P000L000011`, local `G000A000029`. Screenshot clock labels give missions' source time, not necessarily executed fill seconds; actual exit timestamps and bid peaks require the ledger and event records.
- **#3 potential positive lower-edge return:** Chart shows a deep BTC lower excursion toward roughly $75,250 around 00:30 followed by multiple upward candles and rising EMA9, so a well-priced YES tactical rebound is consistent with a physically earned lower-edge entry. The $0.38 exit was profitable, but chart subsequently rose farther: investigate whether an already-armed floor, early profit collection, or tactical custody timer caused the exit. Do **not** assume a hypothetical later fill, or call exit wrong without exact executable bid and active parent at exit.
- **#4 candidate premature NO fade of recovering YES child leg:** NO entered near ~00:35 after several strong green rebound candles; local EMA9 was rising toward/through the EMA30 region and no confirmed terminal upper rejection is apparent at the entry marker. Chart later pushes up toward ~$75,550 before NO closed lower. The purported BOX EDGE destination ~$75,242.55 sits near the *prior low*, far below the ~00:35 trade area; check genuine bounded-repeat evidence, actual top maturity, return-distance/runway and whether the bot was demanding a full revisit of an obsolete low while the rebound gained strength.
- On these screenshots EMA9 displayed ~$75,409.92 vs EMA30 $75,468.25 for #3 review, and EMA9 ~$75,467.93 vs EMA30 $75,479.09 for #4 review, but they are **review-time values**, not authoritative entry-sample values. Read the contemporaneous recorded decisions before assigning native parent direction at trade entry.
- Earlier #1 and #2 were both YES despite a larger DOWN market, and missed NO continuation remains the chief observed imbalance. Adding #4 NO **does not** establish that the bot correctly joined a physically qualified DOWN rail; it may have been an opposite-side fade of the local rebound.
- **Next forensic controls:** Verify exact #3/#4 entry time, Commander proposal/admission reason, owner territory and parent, EMA9 6s/9s/30s dynamics, Heist box boundaries/repeated rotations, Native quote health and price, executable peak bid and initial floor states, prior low ages and estimated BTC return/runway; compare #3 with genuine Heist lower-edge positives, and #4 with prematurely faded sprouts. Preserve prior PID18244 #6 exceptional cheap upper-edge NO and all positive whole-lot floor examples.
- Observed first-four-trade net subtotal: −$24.65 + $1.29 + $2.78 − $4.37 = **−$24.95 PAPER**, not necessarily final run net. No strategy code modification or runtime restart.
