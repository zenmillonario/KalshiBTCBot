# PID13432 zero-entry run: forensic findings

## Finding

The engine remained active, but entry admission was starved by multiple concrete implementation gaps. This was not a stopped engine or a successful demonstration of selective Mountain trading. The most direct recorded defect is that the strategy produced **44 current, affordable Release RELAY proposals for one unfilled physical mission**, and the runtime rejected every one through its stale continuity-reacquisition latch. Separately, the Mountain detector never recognized a mature edge during the entire recorded run, and ordinary rolling Mountain had no supported primary route.

This report describes the original completed run and isolated admission checks. It does not claim that every chart peak should have been a trade, that 44 proposals represent 44 independent opportunities, that any counterfactual order filled, or that a corrected run would have made a profit.

## Verified run identity and outcome

- Input: `TOOL_RACK_PAPER_20261027T202810Z_PID13432.zip`.
- Input SHA-256: `0517e3e4efb2f8a48b948082fba042694a273ab08d03c34d8d2275ba8ae9d3e2`.
- Runtime: `TOOL_RACK_PAPER_PID16280_CORRECTIONS_20261027`, strategy source commit `4153789`.
- **All 56 files named in RUN_MANIFEST.json exactly match the previously delivered PID16280-corrections PAPER ZIP.** Git-source comparison alone showed expected Windows launcher newline differences and the generated bundle manifest; comparison with the actual delivery ZIP resolves all three.
- Start: **16:28:42.261 ET, 2026-10-27**. Stop: **17:20:03.446 ET**.
- Elapsed: **51 minutes 21.185 seconds**. Stop reason: **OPERATOR_STOP**; the 90-minute entry window had not expired.
- The capture spans five contract IDs, including the partial opening and ending contracts and three intervening 15-minute contract windows.
- **12,004 decision records, all ENTRY decisions WAIT. Zero ledger entries, exits, positions, fees, or realized P&L. Cash remained $1,000.**
- Every decision's SHA-256, previous-hash link, and sequence verified. The single baseline journal record and ledger hash verified; no uncommitted journal files were present.

## 1. A current Release proposal was blocked by a stale runtime latch

The first unambiguous recorded example is **sequence 11,090 at 17:16:06.360 ET**, contract `KXBTC15M-26OCT271730-30`:

| Recorded field | Value |
|---|---|
| Physical source | Current |
| Native book | Current; entry allowed |
| Remaining contract time | 833.640 seconds |
| Current desired side | NO |
| NO executable ask derived from the native book | $0.44 |
| Available quantity at that ask | 4,161.31 contracts |
| Tool maximum price | $0.50 |
| Tool intent | RELEASE_WATCHER / RELAY |
| Tool reason | RELEASE_CONFIRMED_LEVIATHAN_HANDOFF |
| Current revalidated physical proof | Qualified; observed at 17:16:06.190 ET |
| Runtime decision | WAIT / PHYSICAL_CONTINUITY_RESET_AWAIT_TOOL_REACQUISITION |

The same physical mission produced 44 RELAY evaluations in three short windows between sequences 11,090 and 11,211, ending at **17:16:37.228 ET**. They were repeated observations of an unfilled mission.

The source-level chain is explicit. A connection reset sets `_awaiting_reacquisition`. The runtime clears it only on a fresh transfer whose boundary is not `RELEASE_TRANSITION_LATCHED`, or on a primary tool whose territory and side match the raw classifier. A latched Release can separately pass **current** acquisition revalidation and produce an affordable RELAY, but that current proof does not clear the runtime latch. The runtime's earlier WAIT branch prevents Commander from reviewing it.

**Controlled admission check:** using the exact delivered baseline source, original native book timestamps/depth, recorded intents, and the flat inventory state that actually existed, Commander accepted all 44 as RELAY when called directly. This check did not call an executor, create positions, or simulate P&L. It isolates the runtime latch as an actual admission blocker, rather than inferring a missed order from the chart.

The corrective test should accept the exact current qualified proof after reacquisition, while continuing to reject stale/mismatched proof, stale physical data, stale native books, and any already-consumed physical mission.

## 2. Mountain maturity never became reachable with the available references

There were **1,833 real forward geometry samples** and eight recognized arc IDs across three connection epochs. Across all 12,004 decision records:

- `mature_edge` was false on every frame.
- Neither shape/length maturity nor the independent paired-gap maturity route ever qualified.
- Both routes require at least two completed same-direction references.
- The recorded detector had at most **one** such reference: zero on 9,095 frames, one on 2,786 frames, and no arc/reference state on 123 initial/reset frames.

Before the first reconnect, the initial source segment recognized four arcs; the second recognized two; the third recognized two. Resetting the whole geometry history prevented references from accumulating across these segments. Historical chart candles seeded EMAs and display, but were explicitly not forward native arc paths. The visible historical chart therefore did not establish that the strategy had sufficient comparable-path history.

A source-level distinction matters when repairing this. The old detector marks a sampled path complete when it observes every row from its recorded origin, but the first arc after startup or reconnect initializes from the first observed direction. It can have a **partial true physical origin** even though the old coverage flag is true. Do not preserve such an arc as a fully observed comparable merely because that flag says complete.

Two first-epoch completed arcs unquestionably began at witnessed prior extrema and have complete native paths through completion: `G000A000002` (UP, 60.222 seconds) and `G000A000003` (DOWN, 130.036 seconds). The initial `G000A000001` and reconnect-initialized `G002A000005` require the cold-origin qualification above. `G004A000007` is a zero-duration degenerate episode with no valid native outward reversal and must be excluded. Ongoing arcs at a feed gap cannot be declared completed across the gap.

The repair must preserve genuine causal evidence and provide the intended Mountain entry routes; merely removing the two-reference requirement or restoring the old elapsed-age fallback would revive unearned middle entries.

## 3. Actual routing and direction gaps compounded the detector starvation

The source recognizes `ROLLING_MOUNTAIN`, but the controller did not activate a primary tool for that territory or accept it as the next primary after a Release. In this run:

- **2,553 raw frames** were ROLLING_MOUNTAIN.
- **1,859** of those had no active primary.
- **768** had matching Rolling Mountain direction and Release-transition ownership, yet remained without a primary.

A representative frame is sequence **745 at 16:31:52.535 ET**: raw ROLLING_MOUNTAIN / NO, current physical source, current entry-enabled book, owned UNKNOWN, active tool None, Commander NO_TOOL_INTENT. Its mature-edge flag is false; this proves unsupported territory routing, not an independently qualified trade.

Mountain direction was also supplied from the Rail detector's unanimity across available 3-, 6-, and 9-minute slopes. The current Mountain owner could be known while this Rail compass was null. There were **439 raw ALTERNATING_MOUNTAIN frames with null routed side and a known Mountain owner**, of which **438** were inside a Release transition with the current Mountain owner matching the incoming side.

Sequence **3,931 at 16:45:27.014 ET** is a useful current-market example: Mountain owner YES, raw ALTERNATING_MOUNTAIN with side null, Release transition YES, no primary, valid new-contract quotes, and a Release price wait at YES ask $0.71. The Mountain owner was lost because 3-/6-minute EMA9 changes were positive while the 9-minute change remained negative. This was not a source-stale frame. Its mature-edge flag also remained false, so routing repair alone would not establish an entry.

The supported handoff should use the current causal Mountain owner; Rail-specific agreement belongs to Rail qualification.

## 4. Two real source reconnections occurred; ordinary brief staleness is different

| Event | Recorded behavior |
|---|---|
| 16:55:47.242 ET, sequence 6,349 | ConnectionClosedError invalidated geometry |
| 16:55:48.769 ET, sequence 6,355 | Connection epoch 2 resumed; reset serial became 2 |
| 17:08:53.546 ET, sequence 9,407 | NO_PUBLIC_ENVELOPE_15S invalidated geometry |
| 17:08:55.849 ET, sequence 9,416 | Connection epoch 3 resumed; reset serial became 4 |

The second incident includes an actual **18.056-second gap** between geometry samples. The reset serial increments twice per incident because explicit invalidation and subsequent epoch change are separately recorded; this is **two connection incidents, not four separate outages**.

Brief 3.5-second stale samples are not the same reset path. They retain the existing geometry rows and do not by themselves erase comparable history. Across the full run, the physical source was current on **11,355 / 12,004 frames (94.6%)**, and the native book was current on **11,687 / 12,004 (97.4%)**. The zero-entry result cannot be explained solely by general source unavailability.

## 5. Entry wait accounting

Durations below hold each recorded state until the next recorded decision timestamp. They cover 3,079.046 seconds between first and last decision, excluding startup and the final shutdown tail. Repeated 250 ms evaluations are not independent trade opportunities.

| Runtime ENTRY reason | Frames | Approximate minutes |
|---|---:|---:|
| `PHYSICAL_CONTINUITY_RESET_AWAIT_TOOL_REACQUISITION` | 4,460 | 19.11 |
| `NO_TOOL_INTENT` | 3,295 | 14.03 |
| `MOUNTAIN_WAIT_FOR_MATURE_EDGE_NEVER_MIDDLE` | 1,816 | 7.76 |
| `RELEASE_CONFIRMED_BUT_PRICE_ABOVE_SOFT_VALUE` | 1,070 | 4.60 |
| `DIRECT_PHYSICAL_SOURCE_WARMING_OR_STALE` | 649 | 2.76 |
| `MAIN_SIDE_ASK_UNAVAILABLE` | 233 | 0.99 |
| `MOUNTAIN_EDGE_DEFER_ACTIVE_RELEASE` | 183 | 0.79 |
| `RELEASE_OWNER_RETAINED_NEW_ENTRY_PROOF_NOT_CURRENT` | 143 | 0.62 |
| `RELEASE_SIDE_ASK_UNAVAILABLE` | 103 | 0.43 |
| `ASK_0.999_ABOVE_MAX_0.400` | 29 | 0.12 |
| `ASK_0.998_ABOVE_MAX_0.400` | 22 | 0.09 |
| `ASK_0.996_ABOVE_MAX_0.400` | 1 | 0.00 |

The largest single wait was the continuity-reacquisition latch: **4,460 frames / 19.11 minutes**, including the 44 affordable, current Release proposals described above.

## 6. Controller ownership chronology

This table follows actual non-null controller results. Temporary stale-source frames do not imply that latched ownership was erased.

| ET | Sequence | Owned territory | Side | Primary tool |
|---|---:|---|---|---|
| 16:28:43.418 | 2 | UNKNOWN | — | None |
| 16:43:45.466 | 3,531 | DOWN_RAIL | NO | RAIL |
| 16:45:00.633 | 3,826 | RELEASE_TRANSITION | YES | None |
| 16:47:00.712 | 4,297 | ALTERNATING_MOUNTAIN | YES | ALTERNATING_MOUNTAIN |
| 17:04:50.076 | 8,465 | RELEASE_TRANSITION | NO | None |

The original run finished flat in RELEASE_TRANSITION / NO with reacquisition still pending.

## Required correction and validation targets

1. Give ordinary Rolling Mountain a real primary path and appropriate Mountain ownership direction, while keeping Rail qualification independent.
2. Repair post-reset acquisition so current, same-side revalidated Release evidence can discharge the reacquisition wait. Require the exact current proof, not the old ownership label.
3. Repair Mountain evidence accumulation and intended edge participation without treating display candles, partial-origin arcs, missing samples, or elapsed age as completed native comparables.
4. Implement coordinated outgoing terminal exit and incoming Mountain handoff with native depth, cash, inventory, and partial-fill sequencing. This run had no positions, so that behavior needs separate positive and negative execution controls; it cannot be validated from a zero-position ledger alone.
5. Preserve the existing paid-arc/attempt consumption, genuine new-generation/retest requirements, profit floors, physical holds, and Lazarus rules. Positive admission must coexist with the earlier PID16280 anti-spray controls.

## Evidence artifacts

The delivered correction bundle includes this report, `docs/pid13432_forensic_summary.json`, and selected immutable regression inputs under `tests/tool_rack/fixtures/`. The additional full working records below are analysis intermediates, not part of the runtime package. The original uploaded ZIP remains the complete baseline evidence.

- `pid13432_forensic_summary.json`: bounded machine-readable findings and exact reference sequences.
- `pid13432_routing_frames.json`: three unmodified representative routing inputs; mature-edge flags remain false.
- `recorded_seq11090.json`: complete original first blocked Release frame with original decision hash.
- `recorded_frames.json`: neighboring/boundary original frames for regression fixtures.
- `baseline_controls.json`: isolated Commander admission results and per-epoch episode provenance.
- `audit_run.py`, `baseline_controls.py`: reproducible read-only analysis scripts.

Source references for the original implementation are `strategy_core/paper_runtime.py` (reset/reacquisition and entry ordering), `strategy_core/physical_source.py` (continuity reset, source direction, geometry production), `strategy_core/detectors/mountain_geometry.py` (reference/path qualification), `strategy_core/router.py` (territory classification), and `strategy_core/tool_rack.py` (supported territories and transitions), all compared with delivered commit 4153789. This is a baseline report; corrected behavior must be reported separately with its own test evidence.
