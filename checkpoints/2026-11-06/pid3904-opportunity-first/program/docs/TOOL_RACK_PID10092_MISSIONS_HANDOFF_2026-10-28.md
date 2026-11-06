# PID10092 correction — persistent missions PAPER candidate

Operational update: this document records the base mission candidate at commit `b310b37`. The subsequent [restart/finality fix](TOOL_RACK_RESTART_FINALITY_FIX_2026-10-28.md) adds explicit settlement of stopped expired inventory and a clearer startup message; it retains these strategy rules. Source/replay coverage and test counts below describe that base candidate.

Date: 28 October 2026. Branch: `tachyos-tool-rack-pid10092-missions-20261028`.

Release: `TOOL_RACK_PID10092_MISSIONS_PAPER_CANDIDATE_20261028`.
Runtime: `TOOL_RACK_PAPER_PID10092_MISSIONS_20261028`.
Nautilus: `TOOL_RACK_NAUTILUS_TV_V7_MISSIONS`.

**Preparation status: source accepted; PAPER candidate prepared.** All 522 selected offline Python tests pass. The builder publishes the delivery ZIP only after extracting it and passing the same gate with its file manifest verified. No new trading session has been started.

## Purpose and authority

This candidate implements the operator's entry, mission and profit-management corrections following the verified PID10092 run. It retains the standalone Tool Rack, one Commander and one passive PAPER writer. The monitor remains read only. The candidate does not import the R22 engine, start an AI adviser, place venue orders or change an already running session. A subsequent start uses a new $1,000 simulated ledger only after the existing restart checks establish that prior inventory is resolved.

The controlling sequence is: establish the current contract thesis from the physical path, preceding one or two completed contract intervals, exact current target and remaining time; evaluate an eligible main position; then evaluate independent substantial tactical swings. Purpose is assigned before inventory capacity. There is no automatic promotion from local swing to main merely because the ledger is flat.

The implementation does not claim that each visually symmetric pyramid is predictable or that every eventual quote minimum could have been bought. A current qualified edge may be anticipated before the EMA9 curls. Its actual location, source timestamp, parent/local scope and available execution price are recorded so the next run can be judged against the intended strategy.

## What changed

### Persistent parent and local geometry

`mission_context.py` maintains a larger parent leg separately from the native short arcs. Native changes and ticker rollover do not reset the parent. The transition resolution exposes its observed inputs: the parent's excursion, already completed prior-contract ranges, the existing retreat fraction and minimum-dollar resolution. References are resolved as of each received row, including when a historical prefix is supplied in one batch. Future reference ranges cannot be applied to an earlier parent transition.

A meaningful observed retreat, qualified retest/rejection or actual confirmed Release transfer can establish the new parent. A supported anticipated successor has its own ID before the full reversal is observed; the same ID is promoted when the transition actually arrives. A source gap interrupts the evidence and continuity generation. It does not manufacture a terminal or a new paid opportunity.

`parent.entry_edge` and `parent.terminal` answer different questions. Parent-scale matched gaps and slowdown may support an early incoming candidate without giving the outgoing held main position collection authority. This distinction preserves stronger anticipatory entries while avoiding collection at the first small slowdown.

Completed source candles supply contract context, not fabricated intraminute observations. The runtime retains the preceding opening-close bar needed for the older of two complete profiles and completed bars from the current contract. Missing targets/history and future-known bars cannot create a side thesis. Competing known endpoints are `MIXED`; unresolved endpoints remain `UNKNOWN`.

### Explicit main and tactical admission

`mission_policy.py` establishes the purpose of an actionable tool proposal before capacity checks. A main candidate needs a matching conditional contract thesis plus a qualified current parent value location or earned parent edge. Native recognition age is not permission. There is no fixed four-minute entry deadline or early-opening exception that supplies physical authority.

A fresh Rail acquisition must show current continuation support. Retained Rail custody alone cannot justify a new purchase while the present path deteriorates. A qualified Heist box has an independent bounded-return route; it does not need a Mountain entry classification. Compatible Mountain/Heist fades on a Rail remain possible through their own current physical evidence and return scenario.

Eligible main proposals receive selection priority. A main and a distinct opposite tactical lot can coexist under the existing exact-position protocol. One main parent slice per exact ticker is recorded only after an actual booked fill. An expensive quote, insufficient cash or missing depth does not consume it. A fresh quote, local native turn or route rename cannot repay the same parent. A new physical parent or exact contract slice is evaluated independently.

The new parent route is also adapted to the existing Lazarus coexistence protocol. It must prove an exact current supported new parent, different from the held original scope. This preserves independently earned opportunities beside qualified recovery inventory without changing the underlying recovery qualification. It does not allow a third lot or an unchanged mission renamed as new.

### Tactical return screen

The engine setting is `strategy_core/config/mission.json`:

```json
{
  "minimum_gross_roi": 0.40,
  "quote_response_window_s": 180.0,
  "minimum_response_pairs": 3
}
```

The 40% unit is gross return on entry ask: a .30 purchase requires a .42 prospective sale bid. It is neither forty cents of quote movement nor forty percent of the BTC arc. It is not an automatic take-profit order and does not impose a numeric return target on main admission.

The scenario uses the exact current ticker and continuity generation. It reproduces an affordable integer lot using current visible ask depth, the tool's budget and the existing nominal fee calculation. It measures already observed full-lot bid response over meaningful physical movements, retains negative response pairs and uses a conservative lower-quartile response estimate. At least three response pairs are required. The forecast movement is capped by the actually observed BTC range, and the estimated duration must fit the remaining contract time.

A passing scenario must meet the gross screen and have positive estimated net dollars after modeled purchase/sale fees. It carries the quote IDs, source times, response observations, proposed quantity, entry VWAP, required bid, estimated bid and uncertainty. The permitted purchase price is tightened to preserve the gross hurdle. The passive writer independently checks the actual captured book, remaining liquidity, price, cash, timestamp and fees at execution.

The response scenario is uncalibrated and does not establish future price, duration or exit depth. `future_exit_depth_proven` remains false. Missing or inadequate response evidence stays unassessed; no required-bid arithmetic is presented as a forecast. The separate `looking_glass.json` setting remains observer arithmetic. The engine's admission threshold is the one in `mission.json` and is shown explicitly with each candidate review.

### Holding and collection

Each filled position records its purpose, side, source time, continuity generation and physical scope. Main custody collects at that exact parent's qualified terminal. An outgoing peak cannot immediately collect a position bought for the anticipated incoming parent. A small native arc cannot finish a larger held leg by itself.

A tactical return freezes its EMA9 or box destination at entry. Later EMA/box estimates do not move that destination inward. Reaching the actual bounded destination remains a valid collection event even when a different larger move might later continue. The candidate does not silently convert a tactical entry into a main holding after seeing subsequent prices.

After a genuine source reset, the original entry remains unchanged. An interrupted main scope can resume collection only through a timestamped, same-side link to an actually reacquired current parent. A gap or the link itself supplies no terminal. Later gaps preserve the chain and completed terminal facts already observed. A tactical position can reach its frozen destination using a fresh post-gap BTC endpoint, but a local terminal from a different source generation cannot be imported. The real runtime test exercises a source reset, 180 seconds of new observations and an actual Rolling Mountain reacquisition without creating a trade or changing the held quantity, cost, fees or purpose.

Every new strategy sale requires a later observed entry candle. A wall-clock delay alone is insufficient. Deferred proposals leave no accepted exit latch; they must qualify again on later fresh evidence. Existing armed floors, accepted partial-exit obligations, explicit manual stop and exact official settlement retain their objective paths. The underlying Lazarus/loss predicates remain unchanged.

Affirmative prior-cross holding uses two actually witnessed EMA9/EMA30 crosses within the same continuous source segment and the position's still-living mission. It does not use a boolean flag alone, infer a cross across a gap or make every crossing an exit. The position's own terminal/destination and applicable structural invalidation remain meaningful.

Existing fee bookkeeping and earned protection are retained. Gross return alone does not arm a first floor or force collection; qualified physical collection and the applicable candle/source requirements are still needed. Once protection is committed it cannot be loosened by a new narrative or mission label.

### Feed scheduling and forensic evidence

The feed consumer yields cooperatively even when synchronous processing has already exhausted its pacing interval. Discovery and finality requests record separate request/start/completion/failure/cancellation events, with queue and execution timing. This repairs the reproduced scheduling mechanism without claiming that the old archive contained a direct event-loop trace of it.

The new `mission_history.jsonl` records exactly which completed chart context reached the engine, when it was known and its content hash. Decisions retain the history reference, mission context and candidate reviews. This closes the missing-history evidence gap found in the old export and makes the next run's thesis reconstructable.

### Nautilus

Nautilus now shows the engine's actual main-side thesis and current parent even while flat. Position cards show the recorded main/tactical purpose, holding destination and scope identifiers. Briefing shows the anticipated successor, history status and admission reviews, including required versus estimated exit bid and estimated net dollars for the proposed lot.

Looking Glass/Hurricane remain a separate scenario section with no execution controls. Unknown evidence stays unavailable. Source expiry changes the mission label to LAST RECORDED without waiting for another response. Historical trade review retains the original entry purpose/economics even after the current contract thesis changes. Existing TV typography, feed width, large position cards, simplified quotes and net percentages are preserved.

## Recorded PID10092 acceptance and its limits

The bundled fixture retains all 3,445 original geometry observations losslessly, their canonical hashes and ten original entry/exit checkpoints. The original diagnostic ZIP SHA-256 is `db1e95ae78fd89691e93aca81fca2949540dd6d385903646c8e98f1bce3365bf`.

| Recorded case | Premise and correction established |
| --- | --- |
| #4 | Original tactical Heist destination is frozen at upper 80,724.52 with tolerance 10.1244. At the old exit BTC 80,711.84 was still 2.5556 below the permitted destination band. The refreshed, inward-moving box cannot authorize that sale. |
| #8 | Under an explicitly selected MAIN purpose, a causal anticipated incoming parent is available at entry. Its old small local terminal does not collect that parent position. |
| #14 | Under MAIN purpose, the actually witnessed lower-region retest supports the anticipated scope; the old local slowdown does not collect it. |
| #16 | The genuine parent retreat/retest/rejection remains collectible. This protects against a blanket hold-every-winner rule. |
| #17 | Its original bounded NO return had reached the frozen entry EMA9 destination by the original exit. Collection remains permitted. |

The MAIN choices in #8/#14/#16 are explicit holding-test premises. They do not claim that the complete new admission and portfolio rules would buy the original quantities at the original times. #4's correction proves the old box exit was early; it does not prove that its tactical lot should remain through settlement. #17 is not forced to HOLD after its intended return is complete. These are source-prefix acceptance checks, not a sum of alternative profits.

### Full archive replay

The replay adapter processed all 15,804 verified original decision inputs and 3,445 causal geometry rows. The original-source control, pinned to Git `547315a3241050407a9a0fa1457f957c39a4f26a`, reproduced all **43 economic events exactly**, including sequence, side, ticker, quantity, price, fees and cash movement. Its 230-record journal reconciled. Exact equality applies to economic events; it is not a claim that every diagnostic field in all decisions is identical.

That control reproduced 22 entries, 21 closed positions and one unresolved position, with $933.6540 cash and −$56.3920 recognized realized net. The separate later-result calculation reproduces −$66.3460; that later result was not supplied to either replay.

The original export does not retain completed chart/seed bars. Its forward one-second observations are not relabelled as complete OHLC. Consequently the revised archive-only replay reported an UNKNOWN contract thesis on all 15,804 frames and admitted **no main contract position**. It is an incomplete reconstruction of the new strategy. Production history wiring is tested separately with the actual feed schema.

The available inputs produced five NO tactical positions:

| Replay entry ET | Entry price | Estimated gross return at admission | Actual diagnostic outcome | Net dollars |
| --- | ---: | ---: | --- | ---: |
| 21:33:22 | .3000 | 55.17% | Losing official settlement | −9.7600 |
| 21:56:28 | .2000 | 40.00% | Losing official settlement | −9.9300 |
| 22:10:41 | .2900 | 44.76% | Persistent physical failure exit | −7.0792 |
| 22:12:46 | .0390 | 213.33% | Losing official settlement | −9.9900 |
| 22:16:48 | .2600 | 48.23% | Mature physical edge exit | +6.8000 |

The revised diagnostic ended flat at $970.0408 cash: −$26.5592 gross, $3.40 fees and **−$29.9592 net**, with one winner and four losers. Its 52-record journal reconciled. Each admission used past-only response evidence, matched the actual quantity, passed the estimated gross/net screen and retained `future_exit_depth_proven = false`. Neither discretionary sale occurred in its entry candle. Four losses despite passing estimates demonstrate that the return screen is conditional and uncalibrated.

These totals are **not a full-strategy performance result, forecast or evidence of improvement** over the original run. The source used by that diagnostic was a frozen 54-file Python/configuration snapshot, aggregate SHA-256 `0d54c79a5669e01c34b44e145d279855e34a53454445a8baa0c9ed79e61d0fe0`. Later final-source changes add interrupted-main reacquisition and align the main handoff identity. The recording contains no main entries, one connection epoch and a maximum geometry gap of 11.002853 seconds, below the 15-second reset boundary; those new paths are covered by separate focused/runtime tests. This is not a claim that the final source was replayed unchanged. The archive also cannot measure the economic effect of repaired background scheduling because it lacks the repaired finality request and next-contract quotes after 22:30.

Machine-readable evidence, original source hashes, admission checks and source-coverage qualifications are retained in `pid10092_mission_replay_summary.json`.

## Validation and next session

The final source gate passed **522 tests with no skips**, using Python 3.12.14 on Linux, cryptography 50.0.2 and websockets 16.0. It completed in 67.944 seconds. The strict package whitelist contains 145 files plus the generated hash manifest. The standalone builder extracts the actual ZIP, removes external `PYTHONPATH` support and requires that extracted package to pass the same full check before publishing the archive.

The actual Nautilus renderer's mission and Looking Glass JavaScript checks passed, and JavaScript syntax checks passed. The final source coverage review also confirmed that exactly the five documented modules differ from the frozen archive replay, with no additional unreviewed change in its 54-file Python/configuration subset. `git diff --check` passed before packaging.

The selected gate covers real Commander/executor accounting, fees, exact native depth, stale/expired dispatch, role coexistence, Lazarus custody, source resets, entry-window draining, official finality, journal/export integrity, mission causality, tactical scenario economics and display projection. Existing execution tests that deliberately script detector inputs now state their mission premise explicitly. They do not pretend to reconstruct historical admissions without historical context.

The actual JavaScript renderer has offline DOM checks for engine/observer separation, exact position purpose/destination, stale expiry, historical review isolation, unavailable estimates and safe text. This revision has no new visual browser inspection. Local Python acceptance and the remote Windows CI workflow are separate facts; no remote CI success is implied.

After the delivered ZIP passes its extracted gate, extract it into a new folder, run `02_CHECK_TOOL_RACK_PAPER.cmd`, and start `01_START_TOOL_RACK_PAPER_90M.cmd` when ready. The default is a 90-minute entry window followed by normal held-position draining. Export the stopped session with `04_EXPORT_LAST_TOOL_RACK_RUN.cmd`. Verify the new runtime/display identifiers in Nautilus; refreshing an old page does not load new strategy code.

Judge the next session by whether its recorded purpose, direction, entry location, fixed destination and collection reason match the observed leg. Trade count or a favorable outcome alone is not proof of strategy compliance.
