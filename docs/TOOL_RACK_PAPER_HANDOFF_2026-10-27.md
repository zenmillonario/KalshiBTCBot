# Tool Rack PAPER handoff — 27 October 2026

## Decision and scope

This delivery makes Tool Rack the strategy owner for a standalone PAPER session. It follows the user's correction that Tool Rack must actually trade PAPER and that R22 must not remain the authority. The earlier shadow-only recommendation is superseded by that instruction. The prior R22/PID12156 forensic report remains historical evidence; this build does not reinterpret shadow candidates as fills or claim a backtested return.

The delivery is isolated to branch `tachyos-tool-rack-paper-v1`. Its CI workflow runs only for that branch or pull requests targeting it, with Python 3.12 and 3.14. No main-branch merge, venue order, or live-market PAPER run is part of the implementation/packaging validation.

The operational entry point is [TOOL_RACK_PAPER.py](../TOOL_RACK_PAPER.py). The [README](../README_TOOL_RACK_PAPER.md) contains the Windows start/check/install/stop/export steps. The two direct dependency pins are verified against the locally installed environment and upstream versioned documentation: [websockets 16.0](https://websockets.readthedocs.io/en/16.0/reference/sync/client.html), [cryptography 50.0.2](https://cryptography.io/en/50.0.2/installation/). Their transitive wheel dependencies are resolved by pip only when the explicit installer is run.

## Authority map

| Component | Authorized responsibility | Boundary |
| --- | --- | --- |
| Direct market-data feed | Receive causal BTC observations and exact-ticker native bid depth; discover markets; verify official results | Public market GETs and an authenticated market-data WebSocket; no portfolio/order endpoints |
| Physical source and detectors | Derive arcs, comparable edges, ranges, persistence and release evidence from the frozen observation | Measurements do not issue execution commands |
| Rail | Value entry and sustained same-direction structural custody | No ordinary opposite fade; continuity and genuine transfer govern ownership |
| Alternating Mountain | Mature-edge entry and living-leg custody | No protected-middle chase; first/repeated edge evidence has to be physically usable |
| Market Heist | Qualified repeatable box, real edge departure and opposite-edge custody | A confirmed breakout ends box authority; losing positions are eligible for structural exit |
| Release Watcher | Observe owner termination and propose a confirmed directional handoff | First slowdown is insufficient; it remains advisory until Commander authorizes action |
| Tool Rack controller | Maintain one primary owner plus the release overlay; manage exact identities and custody adoption | Consumes an entry opportunity only after a committed `BOOKED` receipt |
| OneCommander | Sole decision authority for ordered ENTRY/HOLD/EXIT | Armed-floor and stop facts take precedence; new entries require current physical and quote evidence |
| PaperExecutioner | Apply the explicit command to the exact PAPER inventory, available depth, fees and durable ledger | No strategy selection, automatic relay close, venue order submission or guessed settlement |
| Dashboard/export | Display detached state; archive a stopped run with a verified journal | No write or trade controls; no specialist authority |

Sources: [feed](../strategy_core/paper_feed.py), [physical source](../strategy_core/physical_source.py), [tools](../strategy_core/tools/), [controller](../strategy_core/tool_rack.py), [Commander](../strategy_core/commander.py), [executor](../strategy_core/paper_execution.py), [dashboard](../strategy_core/paper_dashboard.py), [exporter](../TOOL_RACK_EXPORT.py).

## What changed because of the forensic review

The R22 review identified separate strategy, custody and observation problems. This implementation addresses concrete mechanisms; it does not claim that every previous WAIT or the whole flat interval had one cause.

| Previous failure mode or required control | Standalone implementation | Regression evidence |
| --- | --- | --- |
| A generic watch/compression state could mask established directional Rail evidence | Qualified physical ownership is resolved before incidental observer labels; Rail continuity remains independent of contract slices | `test_pid12156_physical_authority_regressions.py`, `test_router_tool_rack.py` |
| Mountain/Heist candidates could be cheap because the physical thesis was already failing | Mature Mountain windows require usable terminal cues, which may be stall, hesitation, failed reextension or retreat; Heist requires its box-edge evidence. Protected middle and late counter candidates lack ordinary entry authority | Mountain/Heist detector and controller tests; PID12156 physical-authority regressions |
| A loss could bypass ordinary physical-break review through sanctuary custody | Each held position returns through its tool manager and the sole Commander; a losing explicit EXIT can execute | `test_paper_execution.py`, tool custody regressions |
| An expanding structural move could inherit an ordinary rental-profit threshold | Tools carry explicit floor policy: Mountain 50%/5%, Heist 50%/3%, Rail and Release 100%/10%; earned 100% protection is immediate | Executor floor tests and direct-runtime Rail tests |
| Already-armed protection had to survive a structural explanation or policy change | Floor monotonicity and breach latch are executor invariants; only Commander chooses the resulting EXIT | Executor tests for nonwaivable armed floors and observation-independent enforcement |
| A current producer could advance beyond an otherwise coherent frozen frame | The direct runtime consumes immutable causal capture; actual dispatch time rechecks native age and contract close after measurement work | `test_paper_runtime_accounting.py` |
| A quote or callback from the next ticker could affect old inventory | Position IDs, entry quote, exact ticker, territory and opportunity are retained; official settlement for the old ticker cannot clear the new slice | Executor and direct-runtime rollover tests |
| A stalled or reset physical feed could preserve unjustified ownership | Source continuity reset withdraws physical entry authority; recovery must requalify; existing inventory remains separately managed | `test_source_gap_reacquisition.py` |
| A projection read lock could look like an economic failure | Hash-linked journal commit is authoritative; optional JSON projections retry briefly and report delay without undoing the trade | Accounting integration test with a simulated Windows projection lock |

The prior forensic evidence is not a performance guarantee for the new model. The old source is not imported to select entries or exits. The small vendored market-data primitives are transport/book mechanics only, with provenance recorded in [VENDOR_PROVENANCE.json](../strategy_core/marketdata/VENDOR_PROVENANCE.json).

## Causal measurement contract

BTC EMA seed values come from validated completed Coinbase minute candles. The seed does not fabricate forward intraminute arcs, range visits or comparable mountain repetitions. Live physical geometry is built only after actual observations arrive.

The new 3/6/9-minute structural slopes end at the frozen live observation and use the full corresponding elapsed horizon. This is a deliberate measurement change from the old minute-boundary endpoint behavior. It removes that endpoint lag, but it is not a bitwise port of the archived observer. Short history yields missing long-horizon measurements instead of invented values. Gaps and connection-epoch changes clear structural history; contract rollover by itself does not erase continuous physical BTC history.

Rail defaults require 900 seconds of qualified persistence/residence evidence. That is a physical qualification threshold, not a promise to trade exactly 15 minutes after startup. Mountain requires comparable completed structure and an eligible edge; Heist requires repeated bounded behavior; Release requires an existing meaningful owner/boundary and affirmative handoff evidence. A session can legitimately spend substantial time warming or waiting. [Geometry and physical configuration](../strategy_core/physical_source.py), [physical.json](../strategy_core/config/physical.json), [rail.json](../strategy_core/config/rail.json).

Native books preserve receive and exchange/source timing, sequence continuity, quote identity and exact ticker. An unchanged book is not restamped as new liquidity. Exchange timestamps may be absent in a native snapshot; that is recorded as unknown, with sequence-verified snapshot and receive-monotonic provenance required. Currentness is not inferred from the poll time alone. One-sided books remain separately eligible for a held-side sale.

## Accounting and custody contract

The starting PAPER balance is $1,000. The executor buys affordable whole contracts at visible asks within the explicit tool limit, including the modeled fee in the tool budget. Fractional quantities at distinct price levels are not combined into invented whole contracts. Sales use visible held-side bids; conservative VWAP rounding and allocated entry basis/fees keep partial exits reconciled.

The fee formula is `ceil_to_cent(0.07 × q × p × (1 − p))` per modeled purchase or sale. It is an assumption carried forward as a mechanical convention, not a claim about current official venue fees. The ledger reports gross and net separately. For example, the tested 17c, $25 fee-inclusive entry buys 138 contracts: cost $23.46 plus $1.37 modeled entry fee. This fixture verifies bookkeeping, not an obtainable live fill.

Economic events contain `qty`, `cost`, `fees`, `gross_pnl`, `net_pnl`, ticker, side, tool, territory/opportunity, quote ID/provenance, command ID and position ID. `venue_fill_claim` is false. The same native visible liquidity cannot be sold twice. Duplicate successful commands are idempotent; mutation under the same command or quote identity is rejected. Repeated same-ticker same-side stacking is prohibited.

The floor observation layer never sells by itself. An armed floor cannot move downward or be waived. A breach becomes a mandatory fact for the one Commander; the executor rejects non-exit actions while it remains breached. A full-position peak requires full-quantity executable depth. Ordinary first arming has a 30-second age condition; the explicit +100% immediate protection setting bypasses that age condition. Trail percentages apply to the executable peak bid, not percentage points of ROI.

There is no generic fixed-loss threshold added by this delivery and no losing-position sanctuary. A structurally valid Rail/Release can continue to hold; a tool's genuine invalidation or confirmed opposing transfer is reviewed even below entry. Partial or temporarily unavailable liquidity leaves an explicit pending exit. Exit and replacement entry are ordered; the same beat/native quote cannot be reused for immediate reentry.

Expired positions remain tied to their own contract. Settlement requires an official finalized binary result with pinned close/result provenance. A missing result does not become zero, and the next ticker's quote cannot settle the old ticker. Final-summary economics are refreshed from the ledger after finality, including settlement that arrives after the last ordinary decision snapshot.

Each economic mutation is committed to a separate hash-linked journal record before the public state changes. The writer lock prevents two writers for the same run; the global OS lease prevents two Tool Rack PAPER engines. Under that lease, startup checks both the global last-run pointer and the output folder's last-run pointer, verifies the prior durable journal, and requires flat inventory before allocating a fresh $1,000 ledger. A missing, unreadable, corrupt or non-flat referenced prior journal refuses startup; choosing another output folder cannot bypass the global reference. Open inventory is never blindly resumed or silently reset. A stopped run with unresolved positions requires review rather than deletion of its locks/history. Optional status projections may lag after a Windows read lock; the journal remains the accounting authority.

Sources: [executor](../strategy_core/paper_execution.py), [runtime](../strategy_core/paper_runtime.py), [executor tests](../tests/tool_rack/test_paper_execution.py), [runtime accounting tests](../tests/tool_rack/test_paper_runtime_accounting.py).

## Delivery and verification

The package boundary is the exact `PACKAGE_FILES` tuple in [CHECK_TOOL_RACK_PAPER.py](../CHECK_TOOL_RACK_PAPER.py). Broad directory prefixes are not used. It includes direct core/tool/detector/config/feed/market-data/execution/runtime/physical/dashboard files, the four current launchers, README/handoff, installer requirements, isolated CI workflow and an explicit standalone test list.

It excludes the R22 adapter, R22 run-source reader, shadow engine/frame/comparator/event timeline, old launchers and Nautilus patcher. Selected tests cannot import those omitted modules: an AST import-closure audit fails on missing local imports or undeclared third-party dependencies. A runtime loaded-module check also refuses unpackaged strategy modules. Source is parsed/compiled without starting feed constructors. Windows text I/O and launcher UTF-8/CRLF bytes are checked explicitly.

The builder hashes each whitelisted file, validates ZIP integrity, extracts the actual ZIP and runs CHECK from the extraction with inherited `PYTHONPATH` removed. The extraction must pass all selected tests with no skips, including named mandatory tests that book and close real simulated ledger positions. Only then is the archive published. A changed or incomplete extracted file fails the manifest check.

The isolated CI workflow repeats source and extracted-bundle checks on Ubuntu/Python 3.12 and Windows/Python 3.14. The workflow definition does not itself establish a successful remote run. The environment used during preparation is Python 3.12.14, websockets 16.0, cryptography 50.0.2. The full repository suite passed 209 tests during integration; that includes historical migration/shadow coverage that is deliberately not shipped. The standalone source check passed **180 tests in 23 explicit modules**, with no skips. The strict delivery whitelist contains **78 files**, plus its generated manifest. The builder repeats those 180 tests on the extracted artifact before publishing it; do not substitute the earlier shadow-suite count.

### Remaining validation limits

- No native Windows process/console/locking session has been run in this Linux preparation environment. CRLF, quoting, selection paths and UTF-8 are statically verified; the dedicated Windows machine must exercise the launchers.
- No live credential authentication, market-data session or fresh 90-minute PAPER run was started for this delivery. Offline market fixtures, cryptographic primitive tests and local loopback dashboard tests do not prove operator credentials or current venue connectivity.
- The dashboard passed local HTTP/isolation and JavaScript checks. A browser screenshot test was unavailable because the preparation environment did not have a browser binary.
- No profitability claim follows from passing tests. Cold-history qualification, source interruptions, depth, official-finality delays and actual opportunity availability can all reduce activity. Modeled depth sweeps and fees are not real venue executions.
- There is no automated recovery of open inventory after a crash and no ability to place a real venue order. Preserve the stopped journal and export it for review if an exit cannot complete.

The first operator session should be assessed by the complete decision-to-journal chain: raw physical evidence, recognized territory, tool proposal, Commander reason, quote freshness, simulated fill/exit or exact rejection, and final reconciled ledger. Count entries only from committed economic events. A quiet run needs that admission evidence before any strategy threshold is changed.
