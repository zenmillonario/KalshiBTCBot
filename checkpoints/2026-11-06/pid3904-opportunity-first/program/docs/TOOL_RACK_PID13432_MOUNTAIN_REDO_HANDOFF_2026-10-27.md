# Tool Rack + Nautilus: PID13432 Mountain correction

Release: `TOOL_RACK_PID13432_MOUNTAIN_REDO_NAUTILUS_TV_V3_20261027`  
Runtime: `TOOL_RACK_PAPER_PID13432_MOUNTAIN_REDO_20261027`  
Dashboard: `TOOL_RACK_NAUTILUS_TV_V3`  
Source branch: `tachyos-tool-rack-pid13432-mountain-redo-20261027`  
Mode: **PAPER**, one Tool Rack, one Commander, one passive economic writer.

This is the replacement candidate prepared after the operator's zero-entry PID13432 run. It combines the corrected strategy and execution paths with the already approved Nautilus TV layout. The [forensic report](TOOL_RACK_PID13432_FORENSIC_REPORT_2026-10-27.md) describes the original run; this document describes the correction. [Startup instructions](../README_TOOL_RACK_PAPER.md) apply to the fully extracted replacement package.

## What the original run established

The original run lasted 51 minutes 21.185 seconds, from 16:28:42.261 to 17:20:03.446 ET on 27 October 2026, and ended with `OPERATOR_STOP`. All 12,004 entry decisions were WAIT. The verified journal remained at its initial $1,000, with no positions, trades or fees. All 56 recorded delivered-file hashes match the actual predecessor ZIP, and the decision/journal chains verified.

The clearest causal blocker was at sequence 11,090, 17:16:06.360 ET. A current Release proposal sought NO at the recorded $0.44 ask with 4,161.31 contracts visible and more than 13 minutes remaining. The current physical transfer had revalidated, but the runtime's old continuity latch refused admission. The same unfilled mission generated 44 such proposal evaluations; these were not 44 independent trades.

Mountain had separate defects: ordinary Rolling Mountain was recognized without a primary tool, Mountain direction borrowed Rail's longer-horizon unanimity, an unconfirmed Release WATCH froze the controller's Mountain direction, and completed comparison history was discarded at two real reconnects. Both old maturity routes remained false throughout the recorded run. The full baseline counts and durations are in the report and `pid13432_forensic_summary.json`.

## Mountain behavior implemented in this candidate

A qualified lower edge can release the outgoing NO and acquire YES for the rising leg. A qualified upper edge can release the outgoing YES and acquire NO for the return. The purchased position follows the living EMA9 leg through ordinary pauses and pullbacks. Its next genuine terminal edge, hard structural invalidation, earned protection or finality can end custody.

The paired-gap route may act before the visible EMA9 curl. It uses two genuine completed same-direction references, both current signed gaps matching one actual historical BTC/EMA9/EMA30 snapshot, and current measured slowdown. Whole-Mountain shape agreement, another stall/retreat flag, a Heist box, or an old whole-arc price-extreme timer is not an additional prerequisite for this independently sufficient route. Observed current steepness, spent return location, paid-opportunity identity, current sources and native execution economics still apply.

The contract target remains briefing context. It is not a requirement that BTC cross the price-to-beat before a held contract can collect an earned bid improvement. The existing protection, fee-positive physical completion and healthy-leg holding rules remain in place; no fixed take-profit quota was added.

## Corrections and authority homes

| Area | Corrected behavior | Implementation and evidence |
|---|---|---|
| Ordinary Mountain activation | `ROLLING_MOUNTAIN` activates a named Mountain tool with the same causal terminal-edge discipline. It need not become Rail. | `router.py`, `tool_rack.py`, `tools/mountain.py`; recorded routing controls and qualified synthetic peak/valley controls |
| Current Mountain direction | `mountain_direction` comes from the current causal Mountain arc. Rail's available 3/6/9-minute agreement stays specific to Rail. Unknown Mountain direction remains unknown. | `physical_source.py`, `router.py`; recorded sequence 3,931 |
| Mountain ownership during WATCH | Only a confirmed Release retains outgoing ancestry for transfer. An unconfirmed watch cannot freeze a genuine new Mountain direction. Release evidence is recomputed against a changed owner from the same frozen observation. | `tool_rack.py`; real-probe watch and confirmed-transfer controls |
| Reference history | Completed, continuously observed references can survive a reconnect within the existing bounded history. Cold-origin, interrupted, future and zero-duration arcs cannot be manufactured into complete comparables. | `physical_source.py`, `detectors/mountain_geometry.py`; recorded source-prefix and continuity controls |
| Smaller EMA9 references | Meaningful completed native EMA9 arcs supply descriptive paired-peak history. They do not change sovereign mission IDs or renew paid attempts. Larger whole-Mountain references retain their own family. | `detectors/mountain_geometry.py`; native-history and prior PID16280 controls |
| Sufficient paired-gap route | Current paired match plus measured slowdown reaches the actual tool and coordinated handoff without an extra terminal flag or old whole-arc extreme-age gate. | `tools/mountain.py`, `detectors/mountain_geometry.py`; detector-to-runtime pre-curl control |
| Release reacquisition | A retained Release owner can reacquire on affirmative, current, same-side transfer proof. An old latch or merely a fresh quote remains insufficient. | `paper_runtime.py`; exact original sequence 11,090 and stale/mismatched-proof negatives |
| Coordinated ordinary handoff | Review the incoming mission while the outgoing lot exists. Commit the complete authorized exit first, then review the incoming purchase on the same captured book using remaining depth and updated cash. | `tool_rack.py`, `commander.py`, `paper_runtime.py`, `paper_execution.py`; full/partial/exhausted-book and expiry controls |

The larger and smaller peak families each use a bounded recent reference set. Duplicate descriptions of the same observed turning point cannot supply two references. The selected matching peak is deterministic and current steepness is evaluated against that selection; renaming a family cannot bypass observed steepness. Whole-Mountain shape/duration comparisons remain separate. The existing provisional 18% gap, 20% height and 0.25 normalized-shape measurements are not claimed to be calibrated profitable thresholds.

## Complete territory coverage

The operator requested an explicit check of every territory, including acquisition after a transition. The exhaustive coverage test enumerates the complete `Territory` enum; adding a future state without updating its expected behavior fails that check.

| Territory | Tool or intended behavior |
|---|---|
| `UP_RAIL` | `RAIL`, YES direction |
| `DOWN_RAIL` | `RAIL`, NO direction |
| `ALTERNATING_MOUNTAIN` | `ALTERNATING_MOUNTAIN`, qualified upper/lower edge relays |
| `ROLLING_MOUNTAIN` | `ROLLING_MOUNTAIN`, qualified upper/lower edge relays without Rail prerequisites |
| `MARKET_HEIST` | `MARKET_HEIST`, qualified repeatable box edges |
| `RELEASE_TRANSITION` | The confirmed `RELEASE_WATCHER` remains attached while the next genuine primary qualifies |
| `COMPRESSION_UNRESOLVED` | Intentional WAIT; an unresolved squeeze has no trading tool permission |
| `UNKNOWN` | Intentional WAIT until affirmative physical territory is observed |

The audit also exposed a neutral-Heist transition gap. A genuinely new bounded box can have no directional side; requiring Rail direction would leave it stuck behind Release. The corrected acquisition requires current, measured repeatability earned after the transfer: actual required lower/upper/center visits and traversals, with source times and bounded EMA behavior. A renamed old box or old pre-transfer visits cannot restore defeated ownership. Rail can likewise yield to a genuinely measured new Heist box once its defining current Rail qualification is gone. A confirmed opposing Release retains priority.

## Profit-taking and the operator's holding clarification

**Ordinary profit collection waits until a later observed one-minute candle than the entry candle.** The existing 30-second minimum remains where applicable; it is not treated as a substitute for a candle change. The check uses the committed fill time, the recorded entry source candle and a fresh current physical source candle. Wall-clock time advancing while the source is frozen does not establish a new candle.

The guard runs before Mountain or Heist can create an ordinary exit latch. A blocked terminal/box-edge proposal must qualify again later. If the edge disappears, the next candle holds; it does not inherit a deferred phantom sale. Previously accepted exits and partial remainders retain their obligations.

The first ordinary pullback, slowdown or weak patch does not by itself end a supported living leg. Current medium structure can preserve a Mountain/Rail breath when the shorter interval weakens, provided there is no deep adverse break, verified terminal or hard opposing transfer. Release custody can likewise breathe through an initial pullback using its current held-side transfer and actual held-direction progress. A green quote or an old ownership label supplies no such proof.

EMA9 can continue through EMA30 as part of the same living leg. `ema9_ema30_cross_context` records the current and prior actually observed crossings, their known times and continuous source coverage. A touch, future observation or missing interval cannot manufacture a previous crossing. Repeated crossing history is current path context; it neither renews a paid opportunity nor creates a sell by itself. Tests cover the first ordinary pullback at a second observed crossing and a subsequently failed cross with genuine opposing release.

The candle and breathing rules govern ordinary collection. Already-armed floors, immediate earned +100% protection, verified physical failure/opposing Release, manual stop, official finality and an already accepted partial exit retain their priority. The original protection levels remain; no floor is loosened to grant breathing room.

## Coordinated execution details

The tool supplies an exact handoff proposal tied to the outgoing position ID, opportunity, ticker, incoming physical mission, physical edge, source timestamp and continuity generation. Commander authorizes the outgoing sale under the normal position rules. The writer records that sale before Commander can authorize the opposite entry.

The special same-book path requires the old lot to be completely closed and the current contract flat. Partial sales preserve their remaining whole-lot EXIT obligation. Each later beat recomputes the incoming opportunity; a stale or already-spent return cannot be purchased from cached intent. A retained Lazarus companion remains subject to the existing independent-mission rules.

Selling YES and buying NO consume the same native YES bid resource; the reverse direction shares NO bids. The writer retains its per-level usage ledger, preventing double use of liquidity. It rechecks the exact committed sale, current source/quote age, expiry, side, integer quantity, price ceiling, fee-inclusive budget and available cash. If entry cannot execute, the completed sale remains truthfully recorded and the contract stays flat.

An armed floor retains its exit authority. The 90-minute entry cutoff and manual stop still prohibit a new handoff purchase. Ordinary Rail profit exit/re-entry retains its next-native-quote rule.

## Preserved behavior

- The paid physical attempt remains consumed through quote, ticker and Mountain-family changes. A source reset alone cannot revive the paid attempt under a new cold arc ID. Genuine new observed arcs or the existing observed retreat/retest/rejection renewal are required where appropriate.
- Lazarus custody, detachment/restoration, original identity/basis/fees, bounded independent new missions and sovereign floors remain in place. `recovery.py` is unchanged.
- Existing profit protection levels remain: MAIN 10%, tactical 5%, true Heist 3%; healthy first-arm breathing below +100%; immediate +100% protection; weak/spent +100% at most 5%; +150% or armed terminal at most 3%; +600% at most 2%. The new entry-candle and supported-pullback guards clarify ordinary timing. An armed floor cannot loosen.
- The normal 90-minute entry window is followed by normal held-position draining. It is not a timer-generated liquidation. Exact-contract official finality remains the settlement authority.
- Nautilus TV v3 assets are unchanged: narrower feed with larger type, enlarged Current Positions, simplified BID/ASK cards and per-position protection detail. The separate bottom protection panel stays removed.
- The exact archived backbone remains unchanged. Historical R22 implementation references do not import an R22 runtime, Commander, sidecar or order path.

## Validation and interpretation

The replacement ZIP is published only after the builder's actual extraction passes `CHECK_TOOL_RACK_PAPER.py --require-manifest`. That check runs the explicit standalone regression list, verifies the exact delivered file hashes, audits import boundaries and checks Windows text encoding. The new modules are `test_pid13432_mountain_routing`, `test_pid13432_mountain_redo`, `test_pid13432_runtime_reacquisition`, `test_mountain_handoff_execution`, `test_territory_tool_coverage` and `test_ordinary_profit_breathing`.

The exact frozen sequence 11,090 control exercises the corrected runtime gate with its original recorded physical/rack outputs and full native book, then uses the real Commander and PAPER writer. It admits one 54-contract NO lot at $0.44 under the inherited fee assumption. Repeated reviews do not add another lot. This isolates the original runtime defect; it is not a claim of a historical venue fill or corrected-run profit.

The coordinated-handoff control uses a causal synthetic source path through the actual detector, tool, rack, Commander and writer. It exits YES and buys NO on the same captured quote while EMA9 is still rising. Partial-fill, exhausted-depth, cash/fee, stale-source, changed generation, expiry, draining and armed-floor cases exercise the negative boundaries. The zero-position original run cannot itself validate held-position handoffs.

All earlier PID16280 entry and paid-attempt regression cases remain required, including its recorded pre-curl positive, the nine middle-entry negatives and the 18 retry pairs. Its old synthetic two-second ordinary terminal-sale expectation was updated to the operator's new candle rule; the separate immediate adverse-release control remains. A lower trade count alone is not evidence that a strategy is correct, and a larger trade count is not the acceptance goal.

### What remains unproven

The corrected causal replay of PID13432's actual 1,833 physical samples does **not** justify claiming that every visual peak or valley qualified for a Mountain purchase. The preserved comparison routes still produce no eligible Mountain edge on that recorded source sequence. The positively demonstrated original admission defect is the Release continuity gate; the Mountain routing and independent-route defects are demonstrated separately by recorded inputs and causal controls.

Original canonical arc recognition also lagged some observed native turns. A newly assigned arc ID is not by itself a safe fresh-entry signal: several original recognitions arrived after substantial travel or with adverse current motion. This release does not resegment sovereign arcs or promote every small descriptive EMA9 reversal into a new paid mission. The earlier observed turn at 16:39:23 ET remains a concrete item for further physical-generation review, not a fabricated completed trade.

The new candidate needs a supervised PAPER observation to establish its frequency and location under fresh market data. It has not been launched on the operator's Windows machine or authenticated live markets during preparation. No profitable outcome, complete peak capture, or venue-fill realism is claimed by the offline tests.

## Next operator run

Extract the complete new ZIP into a new folder, run `02_CHECK_TOOL_RACK_PAPER.cmd`, then start `01_START_TOOL_RACK_PAPER_90M.cmd`. The same launch opens Nautilus and the actual engine feed. Run the explicit dependency installer only if CHECK reports it is needed. Preserve the old run. After normal completion, use `04_EXPORT_LAST_TOOL_RACK_RUN.cmd` for the next forensic comparison.

The review criteria are physical entry location, current admission reason, paid-attempt identity, hold duration relative to the living leg, terminal handoff, actual native liquidity, protection and Lazarus behavior. A WAIT should identify unavailable comparable evidence, active steep expansion, a spent return, value or source conditions accurately; it should not conceal an unsupported primary or a permanently stuck reacquisition latch.
