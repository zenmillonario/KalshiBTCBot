# PID12448: actual-run forensics and candidate rejection

**Date:** October 28, 2026. All times below are Eastern Daylight Time.

**Decision:** Do not start the previously delivered blind-arc/holding candidate as the next validation run. Its recorded-data replay reproduces the early wrong entries and misses the largest peak.

**Scope:** Review of the uploaded PID12448 archive, plus a bounded replay through the prepared candidate. No live feed, venue order, replacement run, original ledger edit, or production strategy change was made.

## Findings that determine the decision

The user's central observation is supported: the bot bought late continuations and small returns while leaving the large, inexpensive upper turn unused. The intended peak/valley strategy was not consistently governing actual entry selection.

The latest candidate's successful synthetic Construct cases did not establish that the real observation pipeline would qualify these full arcs. In the recorded replay, its new full-return route remained unavailable at the disputed largest peak. The separate MAIN and Heist paths still produced the earlier failures. This is a validation gap in the delivered candidate; the synthetic test counts do not override the recorded failure.

The five actual positions closed for **−$24.432 net**: **−$20.482 gross**, **$3.95 fees**, and **$975.568 ending paper cash** from $1,000. No inventory remains unresolved. All **56 exported file hashes** match, and the **47-record journal** verifies and reconciles. The runtime and strategy/configuration source match the earlier missions build at `4100b41`; the prepared candidate replay uses frozen `ea1b2cd` code.

![Actual recorded BTC, EMAs, entries, quotes and rollovers](figures/pid12448_actual_peak_audit.png)

## Actual trades

| Trade | Entry ET | Side and ask | Exit or settlement | Net result | What selected it |
|---|---|---|---|---:|---|
| #1 | 02:06:29 | NO, 20 at $0.470 | Sold $0.330 at 02:07:01; held 32.21 seconds | −$3.46 | MAIN continuation near EMA9 |
| #2 | 02:08:37 | NO, 54 at $0.260 | Official YES settlement at 02:15:07; NO paid $0 | −$14.77 | Heist return to a frozen box boundary |
| #3 | 02:39:17 | YES, 45 at $0.210 | Sold $0.370 at 02:40:29; held 72.12 seconds | +$5.93 | Local tactical return to EMA9 |
| #4 | 03:08:46 | NO, 158 at $0.059 | Official YES settlement at 03:15:10; NO paid $0 | −$9.942 | Heist return to a frozen box boundary |
| #5 | 03:19:01 | NO, 19 at $0.500 | Sold $0.420 at 03:23:00; held 239.55 seconds | −$2.19 | MAIN continuation near EMA9 |

### #1 and #5: a late EMA contact was enough to enter the old direction

Both entries used `MOUNTAIN_PARENT_LEG_VALUE_ACQUISITION`, with `MAIN_CONTINUATION` purpose. Their own recorded entry evidence said:

- `near_living_ema9=True`;
- `observed_early_parent=False`;
- no comparable full-parent duration references.

For **#1**, the DOWN parent began at 02:02:03 and was recognized at 02:04:01. Its low was **$80,781.61 at 02:05:04**. By entry, BTC was **$80,794.31**, already **$12.70 above that low**. This exceeded its recorded parent transition distance of **$10.158**. Nevertheless, the parent remained nonterminal, and nearness to EMA9 plus brief downward micro motion authorized a new MAIN NO.

For **#5**, the DOWN parent began at 03:12:00 and was recognized at 03:14:29. Its low was **$80,782.98 at 03:15:25**. Entry came at **$80,795.79**, already **$12.81 above the low**, exceeding its **$10.5708** transition distance. The same entry predicate admitted NO.

At #5, EMA9 was **$80,798.697**, above EMA30 at **$80,794.048**. The last upward cross occurred at **03:08:40.584**, about ten minutes twenty seconds before the entry. Short-term EMA9 changes at the entry were downward. The chart therefore contains both facts: the broader post-cross YES context and a local downward section. The policy promoted the late local direction into a fresh main position without establishing the requested edge location.

The current candidate still contains the continuation predicate that permits proximity to EMA9 by itself. Its recorded replay repeats #1's NO entry at $0.47 and its sale approximately 32 seconds later. The third-weakness holding changes cannot repair the location of that entry. Its exit used a separately confirmed parent end, not ordinary first-weakness profit collection.

### #2: incorrect lean label, then an exit destination that did not match the available swing

At entry, the native arc, persistent parent, contract thesis and current EMA9 movement were all UP/YES. The Heist detector nevertheless reported NO lean because it averaged historical EMA9 drift **+1.606** with EMA30 drift **−7.921**. The resulting **−3.158** average was used to call the NO entry aligned with the EMA lean.

A legitimate full-peak NO remains allowed while EMA9 is rising. The problem here is the justification: this was a small box return labeled aligned with the main direction, not an independently qualified full-arc peak.

The trade later had a **current, full 54-contract bid of $0.45 at 02:12:42.305**. Under the run's paper fee model, selling the entire lot at that recorded quote would have yielded **+$8.59 net**. The bot held with `HEIST_CARRY_TO_OPPOSITE_BOX_EDGE`. Its frozen destination was **$80,779.47 ± $3.8376**, while BTC at that quote was **$80,798.15**. The first profit floor was still disabled. The actual bid swing was available, but the required far box boundary never arrived before expiry.

That maximum is hindsight evidence of a missed collection opportunity. It does not mean the engine could know in advance that $0.45 would be the best bid.

### #3: profit was taken at local EMA9 contact

#3's purpose was `TACTICAL_RETURN`, with a frozen `EMA9_RETURN` destination of **$80,801.1477 ± $3**. At the exit, BTC was **$80,799.20**, which satisfied that destination. The tool sold at $0.37 even while the preceding 30 seconds showed **+$19.30** of BTC progress.

A later current full-lot bid reached **$0.59 at 02:43:25.206**. For the same 45 contracts, that quote would have supported **+$15.80 net**, or **$9.87 more** than the booked gain. This is a hindsight comparison, not a promise to capture the later maximum.

The prepared candidate's full-parent holding rule does not automatically affect this trade: it still classifies the purchase as a small tactical return whose destination is EMA9. To hold a complete return leg, the engine must first purchase and manage that complete leg.

### #4: the far boundary required almost a strike crossing before rollover

#4 entered with **6 minutes 14 seconds** remaining. BTC was **$80,805.85** and the price to beat was **$80,747.65**. Its frozen lower box destination was **$80,738.03**, with **$9.12** tolerance. The effective collection boundary, **$80,747.15**, was only **$0.50 below the strike**.

Its admission model projected a **74.10-second** return and a **$0.1192** exit bid. The required return did not occur. The best recorded current bid for all **158 contracts** was **$0.080 at 03:09:16.685**, which would have supported approximately **+$1.878 net**. The position remained open for the far box edge and settled at zero.

The **$0.0826** figure in its economics was the 40% entry-screen threshold, not a submitted take-profit order. The actual best sampled bid was below that threshold. This supports the user's runway observation and exposes the need to distinguish a brief native bid swing from an attempt to reach the opposite physical boundary before contract close.

## The highest peak was available and unused

The highest recorded BTC observation was **$80,895.16 at 02:22:32.230**. At that point EMA9 was **$80,862.84** and EMA30 **$80,832.46**.

In the exact **02:30 contract**:

- NO ask was **$0.110 at 02:22:21.812**, original decision **5568**, with current physical source and entry permission. Visible ask capacity at that price was **10,852.73 contracts**.
- Decision **5607**, ten seconds later, still offered **$0.110**, with **8,651.87 contracts** available.
- Across **02:20:34–02:22:36**, there were **263 fresh-entry captures at NO ask ≤$0.15**, covering **41 distinct physical source samples**. Availability was intermittent, but this was not one isolated tick.
- Before that same contract closed, its NO bid reached **$0.999 at 02:29:34.428**, decision **7259**, with selling permitted.

These are observed quotes and capacity. They establish a real missed swing; they do not establish a hypothetical exact-minimum entry, maximum exit, or venue fill.

### Why both the original run and the candidate missed it

The original run first demanded more completed references, then rejected the latest local swing as immature, and later considered the return already at or through EMA9.

The candidate replay gives a more precise explanation at frame **5607**:

| Scope | What the candidate knew |
|---|---|
| Full parent | YES parent from 02:14:05.105, age **505.825 seconds**, EMA9 excursion **$62.965**, with three native children retained |
| Full-parent comparison history | **No comparable durations** |
| Full-parent entry edge | **False** |
| Anticipated NO return parent | **Absent** |
| Latest native child | Only **54.611 seconds** old, compared with a **415.125-second** reference |
| Result | Wait for a comparable terminal edge; no NO full-return entry |

The system preserved the larger leg's identity, but its full-leg comparison history was disconnected from the completed history. `MissionContext._parent_terminal()` invokes the mountain detector on `_parent_rows` without supplying a separately retained historical full-parent reference archive. Resets clear those rows. The lower-level physical geometry retains native/envelope references, but that archive does not supply the full-parent detector.

Completed historical minute candles feed Looking Glass, initial direction context and prior-contract range measurements. They do not supply parent shape/gap/duration comparisons. The as-of history available near the peak had **38 completed-bar records**; one was explicitly not a full minute. That is available historical information, but it must be validated into a suitable comparison family. It is not evidence that two valid comparable full legs can simply be assumed.

The 02:24 source gap happened **after** the favorable peak window. It does not explain away this miss.

## Source health and rollover limits

The source was marked noncurrent in **4,996 of 20,535 decision captures**, or **24.33% of captures**. This is a capture count, not a time-weighted outage percentage. Three disconnect/reconnect sequences and one separate observation gap produced seven continuity-generation changes. The disputed entries and cited quote opportunities nevertheless include current source observations.

The deepest recorded low, **$80,734.83 at 02:59:45**, crossed a contract rollover. The expiring 03:00 contract's very cheap YES asks cannot be paired with the next contract's later winning bids. The new 03:15 contract's lowest observed YES ask around 03:00–03:03 was **$0.51**, not the expiring contract's $0.002. Every opportunity comparison in this report stays within its exact ticker.

For the 03:30 contract, YES was offered at **$0.35 at 03:15:31** and later bid **$0.978 at 03:28:40**. This supports examining earlier YES participation around the preceding lower region; it is not a claim that an EMA cross alone guarantees that outcome.

## Corrections required before another candidate

1. **Fresh-entry location must be proved separately from holding an existing leg.** Nearness to EMA9 cannot alone authorize a new position in a mature outgoing parent. #1 and #5 must cease to enter through that shortcut, while the appropriate return-side opportunity remains evaluated.
2. **Full-arc detection must use the actual larger leg and compatible past legs.** Retain completed full-parent references, and consider a separately labeled, causally valid completed-minute comparison family. Preserve observation/knowledge times and missing coverage. Do not inflate the reference count with child swings or simply lower the required count until this run passes.
3. **Heist direction must describe the current structure accurately.** A slow EMA30 drift cannot make an opposite trade “aligned” with a clearly rising EMA9/YES parent. Independent full returns and qualifying smaller swings remain separate valid possibilities.
4. **Collection must match the purchased swing and the exact contract's remaining opportunity.** A frozen far box edge cannot remain the sole destination when the actual bid swing is shorter and the strike/rollover makes that boundary a different trade. #2 and #4 are concrete controls. This does not require redesigning the deferred loser-to-settlement strategy.
5. **Preserve the operator's full-arc rules.** Peak→NO and valley→YES remain blind physical-edge entries: no outgoing-EMA agreement veto, no 40% tactical hurdle, no fixed four-minute opening rule, and no fixed eleven-candle requirement. Full legs retain the intended breathing/third-distinct-weakness policy and separately proved complete-arc handoff.

Acceptance must demonstrate both participation and restraint: a causally justified NO entry in the broad highest-peak region, removal of the wrong late entries, suitable handling of the actual tactical swings, and preservation of the existing quiet-market, ongoing-breakout, subcent-entry and full-leg holding controls. A lower loss caused solely by refusing all entries would not satisfy the strategy.

## Replay scope and reproducibility

The actual archive audit covers all **20,535 decisions** and all five trades. The current-candidate replay completed **14,801 captures through 03:02:12.930 ET**, then was stopped after it reproduced decisive entry, exit and missed-peak failures. All replayed BTC/EMA9/EMA30 values, native arc identities and sides, continuity generations and source-currentness states matched their original captures. The first three trades had the same six economic events as the original. There were **zero full ARC_RETURN candidate reviews** and **zero qualified full-parent entry-edge frames** in that replayed interval. Its separate **26-record journal** verifies. Candidate behavior at #4 and #5 was not replayed, and no full 90-minute candidate P&L is claimed.

The replay freezes candidate source, uses the original capture's BTC/EMA observation prefix, exact native book and as-of historical-candle digest, and recomputes detectors, mission selection, tools, Commander and paper execution. It does not inject original positions, intents, peak labels or weakness counts. Official outcomes are supplied only after they were recorded as known. Network access is blocked.

The original raw accepted public trades are absent, so the replay consumes archived actual BTC/EMA observations rather than independently rebuilding the EMAs. Original within-frame processing latency is omitted; actions are compared by source frame and economics, not claimed as byte-identical dispatch timestamps. Recorded native depth remains paper feasibility evidence rather than proof of an exchange fill.

Detailed machine-readable evidence, original decision numbers, source verification and the final bounded replay checkpoint are in [pid12448_recorded_forensics.json](pid12448_recorded_forensics.json).

A reusable offline harness is retained at `scripts/replay_pid12448_recorded.py`. It accepts the extracted diagnostics directory, source repository/revision, an output directory and an optional frame limit. Its path arguments were made portable after the recorded run; that small CLI change was syntax/help checked, without repeating the engine replay. The evidence file retains the exact executed script hash separately.
