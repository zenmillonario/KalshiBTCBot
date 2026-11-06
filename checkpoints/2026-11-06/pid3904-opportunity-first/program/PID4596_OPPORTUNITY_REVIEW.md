# PID4596: entry coverage and opportunity review

## Finding

**The completed recording contains no approved entry and no failed execution of an approved entry.** Every one of its 4,259 completed decisions ended in `WAIT`. The run remained at $1,000 with no positions or realized gain/loss. The crash is a separate reliability defect; loosening entry rules is not required to repair it.

The run did contain substantial same-contract price moves with enough displayed depth for whole lots. Those are useful research leads. They do not establish that the current strategy earned an order at the selected low or could have collected the later high.

**The new opening rail dip/rejoin watch never armed.** This run therefore cannot demonstrate whether that change improved or worsened the expensive early entry from the preceding run.

Scope: all completed decisions from **November 4, 2026, 8:16:06.641–8:35:42.587 p.m. Eastern**. This is a roughly 19-minute completed prefix, ending at the runtime exception. It is not the intended full 45-minute run and says nothing about opportunities after the crash. No strategy, thresholds, original records, or captured source were changed by this review.

## What stopped entries

| Final entry result | Completed callbacks | Interpretation |
|---|---:|---|
| `NO_TOOL_INTENT` | 3,621 | No candidate remained for entry admission. This includes 11 callbacks observing the first NO counter-swing. |
| `COMMANDER_TACTICAL_FADES_PAUSED` | 539 | A Heist NO proposal opposed the current YES mission parent without the permitted neutral/strict/parallel/calibrated exception. |
| `COMMANDER_LEGACY_MOUNTAIN_SPECIALIST_ENTRY_PAUSED_USE_PRIMARY` | 86 | The older Mountain adviser proposed YES, but the captured strategy deliberately permits only Commander-owned Mountain entry routes. |
| `DIRECT_PHYSICAL_SOURCE_WARMING_OR_STALE` | 13 | The direct physical source was warming or temporarily not current. |
| **Total** | **4,259** | **No `ENTER`, `RELAY`, or executor entry receipt.** |

These are callback counts, not distinct trade opportunities. Repeated quotes from one armed setup can create many callbacks.

The actual advisory record contains **86 Mountain YES proposals** between sequence 1280 and sequence 1506, at 8:21:35–8:22:35 p.m. Their asks ranged from **3.5 to 5.9 cents**. The advisory label `ELIGIBLE` referred to the older specialist's armed-value assessment; it was not Commander permission. All 86 reached the explicit legacy-Mountain pause.

There were **550 Heist NO proposals**, beginning at sequence 3579, 8:32:08 p.m. Exactly 539 reached the final tactical-fade pause. Sequences **3970–3980** returned no intent while the first counter-swing was being observed. All 550 recorded Heist missions had `counter_parent_fade=true`, with `neutral_heist_repeatable`, `strict_heist_outer_wall`, and `parallel_heist_return` false. None carried the later-calibrated exception flag. Removing their pause would change the current strategy's permission rules.

The candidate-review telemetry also recorded 3,150 Mountain proposals as **not offered**, with `MOUNTAIN_EDGE_ONLY_NO_MIDLEG_ALIGNED_ENTRY`. Those advisory records should not be counted as approved orders waiting for an execution fix.

Sources: original `decisions.jsonl`, every completed sequence; `opportunity_component_scan.json`, recorded positive adviser stages; captured `commander.py` and `tool_rack.py`.

## What the bot actually recognized

The active tool was Rolling Mountain for **3,150** callbacks, Market Heist for **789**, and none for **320**. Rail was never the active tool, and the low-level detector never reported a qualified rail launch. Terrain labels alone are not enough to establish a valid opening watch, so its actual physical conditions were also examined.

The recorded mission parent progressed through these chapters:

| Eastern time | Decision sequences | Mission parent |
|---|---|---|
| 8:16:07–8:23:59 p.m. | 4–1824 | `P000L000001`, NO |
| 8:23:59–8:29:02 p.m. | 1825–2906 | `P000L000002`, YES |
| 8:29:03–8:30:51 p.m. | 2907–3313 | `P000L000003`, NO |
| 8:30:51–8:35:42 p.m. | 3314–4259 | `P000L000004`, YES |

The contract changed after sequence 3147. Prices from the 8:30 p.m. contract and the 8:45 p.m. contract were kept separate throughout this audit.

The longer-duration EMA9/EMA30 gap evidence is a different scale from these mission-parent chapters. The captured `directional_parent_evidence` function first qualified a long-lived **NO** gap at sequence **3373**, 8:31:08.072 p.m. It remained qualified through **3547**, 8:31:58.672 p.m. By then the current mission parent was already **YES**. The gap subsequently became too small for that historical qualification, then crossed into a new YES sprout at sequence **3939**, 8:33:58.739 p.m.

Consequently the inherited gap side, live mission parent, current source identity, and opening continuation conditions never combined into a valid opening rail context. The captured watch code was stepped in order through the completed physically current snapshots; **qualified opening contexts: 0; armed watch rows: 0**. No watch was consumed, because there were no fills.

### Release did confirm, but the price was above its limit

There is an important distinction between the low-level `physical.release_handoff_confirmed` flag and the independently computed ReleaseWatcher result. The former remained false, while the rack recorded **54 confirmed handoff/value-wait callbacks**:

| ReleaseWatcher desired side | Eastern time | Sequences | Desired-side ask | Captured value limit |
|---|---|---|---:|---:|
| NO | 8:30:21.798–8:30:22.839 p.m. | 3202–3206 | 59–60¢ | 30¢ |
| YES | 8:31:53.732–8:32:07.930 p.m. | 3530–3578 | 76–80¢ | 30¢ |

These callbacks reported `RELEASE_CONFIRMED_BUT_PRICE_ABOVE_SOFT_VALUE`. They were not failed fills. On the first callback of each transition, `owned_side` still names the outgoing owner; the desired side above comes from the ReleaseWatcher briefing and release candidate, not that lagging owner field.

Sources: original decisions at the cited sequences; captured `directional_parent.py`, `commander_candidates.py`, and `tool_rack.py`.

## Same-contract moves worth studying

The following quotes are from the original native books, with both endpoints current. Each pair uses the **same ticker and side**. The quantity column is a whole-lot displayed-depth probe. It uses the actual adviser budget when there was a proposal, or an explicitly illustrative budget when there was none. The calculation floors displayed size per level and uses the captured program's nominal entry fee to determine affordability.

The selected later bid is a hindsight research endpoint. No exit policy, latency, queue position, market impact, or alternate trade path was simulated, and these are not claims of realized or achievable profit.

| Research lead | Eastern entry quote → later bid | Sequences | Whole-lot probe | Why no approved entry was established |
|---|---|---|---|---|
| Early YES rebound, 8:30 contract | 8:18:38.311: **16¢** → 8:18:52.831: **22¢** | 594 → 651 | 88 contracts, illustrative $15 budget; full-lot VWAP 16¢ → 22¢ | No positive entry proposal at the selected first quote; short motion was still DOWN. |
| First actual legacy YES proposal, 8:30 contract | 8:21:35.557: **5.6¢** → 8:25:11.303: **29¢** | 1280 → 2091 | 251 contracts, actual $15 adviser budget; full-lot VWAP 5.6¢ → 29¢ | Deliberately paused legacy route. Before the later peak, the bid fell to **3.4¢**, about **39.3% below the first entry ask**, before fees. |
| Later cheapest legacy YES quote, same 8:30 contract | 8:22:34.492: **3.5¢** → 8:25:11.303: **29¢** | 1504 → 2091 | 401 contracts, actual $15 adviser budget; full-lot VWAP 3.5¢ → 29¢ | Selecting this later low instead of the first proposal is hindsight. The captured Commander produced no qualifying Mountain candidate. |
| New-contract YES continuation, 8:45 contract | 8:30:11.082: **39¢** → 8:34:23.087: **87¢** | 3161 → 4016 | 61 contracts, illustrative $25 budget; full-lot VWAP 39¢ → 87¢ | No Commander candidate. Active Mountain rollover edge was fishing at ≤20¢; Release used ≤30¢ and Heist ≤35¢. The inherited opening exception did not qualify. |
| Late Heist NO rebound, 8:45 contract | 8:34:23.087: **13¢** → 8:35:29.136: **19¢** | 4016 → 4218 | 72 contracts, actual $10 adviser budget; full-lot VWAP 13¢ → 19¢ | The proposal remained an unqualified counter-parent fade. At the 13¢ quote the current native motion and 6/9-second BTC changes were still UP. |

At sequence 1504, the current Mountain record had no mature edge, terminal evidence, stall, failed re-extension, or meaningful retreat, and target ownership remained NO. The old specialist's armed state and the newer current physical quality rules therefore describe different things. A cheap quote plus a later rally does not prove that the newer route malfunctioned.

At sequence 4016 there was local terminal/stall evidence, but no retreat or failed re-extension, and current BTC/EMA9 motion still favored YES. The 13¢ NO quote is a legitimate case to study for future tactical coverage; it does not establish that a permitted later-calibrated Heist entry was lost.

Endpoint native depth is ample for each displayed probe. For example, the 3.5¢ YES entry side showed 1,865.67 contracts and the later 29¢ bid showed 9,310.87; the full 401-contract probe fits both after flooring. The 39¢ YES entry showed 10,734.19 and its later 87¢ bid 8,031.06; the full 61-contract probe fits both. These observations establish displayed depth at the two recorded instants, not order execution.

Sources: original `decisions.jsonl` at the cited pairs; detailed book levels, hashes, offsets, affordability calculations, and intermediate low bids are retained in `opportunity_audit.json`.

## Freshness behavior

The prior freshness repair was active in this run:

- **4,246** completed decisions had current physical evidence. Of these, **4,174** had a bounded negative source age supported by current local receipt evidence. Current geometry ages ranged from approximately **−1.642 to +1.458 seconds**.
- Quote-wave briefings existed on all **4,246** physically current callbacks. On all **3,992** callbacks that also had an entry-available two-sided book, both current asks and both current bids matched the corresponding native quotes exactly, and the latest quote-wave point had the current callback's timestamp.
- There were **zero wrong-ticker quote-wave briefings**. The new ticker began with zero observations while its book was unavailable, then collected its own quotes.
- There were 217 retained-wave/current-book differences at sequences **2896–3112**. Those books were one-sided and `entry_quote_available=false`; these were not missed actionable two-sided quotes. There were also 31 zero-observation briefings, all while entry quotes were unavailable.

This supports the narrow conclusion that the recorded fresh quote stream was advancing correctly. It does not establish the profitability of any candidate.

## Prior leg-ledger repair: no observed regression

The original `LEG_PERFORMANCE_LEDGER_V2` contains eight records. Its **18 per-ticker/side opportunity records** were checked against the original decision quotes: all **15 non-null later-bid endpoints** match the correct ticker, side, timestamp, and price; the other three correctly retain null later bids and null returns. No return combines a cheap quote from an expired contract with a bid from the next contract.

The decisive rollover case is **`E000A000007`**, 8:29:03–8:30:51 p.m. It remains one physical NO leg across two contracts and **34 terrain segments**. It keeps separate opportunities for the 8:30 and 8:45 tickers and leaves the combined top-level return unavailable. The old contract's 0.1¢ YES ask has no invented later bid; the new contract's YES 39¢→62¢ pair is separate. Its 37 noncurrent quote callbacks are excluded from the contract opportunity samples, matching the captured quote-current rules.

The final **`E000A000008`** stays one YES observation across **72 terrain segments**. Its ending is correctly labeled `OBSERVATION_SEGMENT`, `RUNTIME_ERROR_TypeError`, with no observed physical end boundary and `comparable_eligible=false`. The crash did not fabricate a completed leg. The first partial-start record is also excluded from completed comparable evidence.

All seven earlier record endings are `PHYSICAL_LEG_CHANGED`; there are **zero terrain-only leg endings** and **zero mixed-ticker aggregate returns**. This directly exercises both parts of the prior repair. The ledger remains top-of-book research evidence, so the whole-lot depth checks above are separate.

Source: original `leg_performance.jsonl`; checks and exact sequence mappings in `leg_ledger_v2_audit.json`, also incorporated into `opportunity_audit.json`.

## Verification method and limits

The parent's index verifies the canonical SHA chain for all 4,259 decisions and preserves each original byte offset and length. This audit read that index and the matching original rows. It used only the captured program, with bytecode writing disabled.

Every physically current saved snapshot was passed through the captured Commander candidate functions. The historical-extreme/level-match cache was reconstructed with the captured helper from the **exact `mission_history_reference` digest** on each decision, after verifying that history was known by that decision time. No future candles or invented cache were added. The raw physical path, current parent-quality path, historical-extreme path, and edge-Heist path all produced **zero candidates** across those 4,246 snapshots.

This is component inspection plus an unconsumed opening-watch sequence, not a full stateful replay of the engine. The captured runtime records the quote-wave diagnostic but does not copy that field onto its Commander snapshot; ToolRack advisers receive it internally. A separate probe supplied the recorded briefing to the quote-wave candidate function and still produced **zero candidates** on this run. Thus that wiring observation establishes no missed quote-wave entry here and was not changed during this audit.

The failed process call is outside the completed decision prefix. The crash-repair and capture-boundary reports own that reconstruction. Nothing in this audit treats the incomplete capture as a completed exact replay.

## Next step

Finish and validate the narrow missing-number crash repair, keep the captured entry policy intact, and collect a clean PAPER run. Judge the opening rail change when an eligible inherited parent actually supplies a dip and a subsequent cheaper rejoin.

If strategy coverage is revisited later, use the legacy YES window, new-contract YES continuation, and late NO rebound as separate research cases. Compare the full causal path, including earlier adverse movement and the existing exit rules, before changing any permission or price limit. The clean distinction for this run is: **a repairable crash, no approved entry failures, an unexercised rail-watch change, and specific price/coverage leads for later investigation.**
