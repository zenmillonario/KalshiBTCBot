# Tachyos Tool Rack — standalone PAPER

**The Tool Rack owns PAPER strategy and custody in this build.** Four specialist tools propose actions, one `OneCommander` authorizes them, and one passive `PaperExecutioner` records simulated fills against observed native book depth. Every new approved session starts with a separate **$1,000 simulated ledger**. There is no venue order submission capability.

This package is the standalone successor to the shadow attachment. R22/PID12156 is a forensic reference; no R22 process, legacy Commander, permission route, run folder, or shadow engine is required. The strict delivery whitelist excludes those components. Implementation and test evidence are mapped in [the handoff](docs/TOOL_RACK_PAPER_HANDOFF_2026-10-27.md).

## Start on Windows

1. Extract the **whole ZIP** to a writable folder. Keep its files together.
2. Open `02_CHECK_TOOL_RACK_PAPER.cmd`. It checks the package, dependency APIs, tools, and real PAPER execution/journal tests without starting a live market session.
3. If dependencies are missing or incompatible, explicitly run `03_INSTALL_TOOL_RACK_DEPENDENCIES.cmd`, then repeat the check. The installer creates this extracted folder's `.venv`; it does not modify `C:\KalshiBTCBot\.venv`.
4. Keep the existing market-data credential settings in `C:\KalshiBTCBot`. Start `01_START_TOOL_RACK_PAPER_90M.cmd` when ready. One process receives the feeds, runs the Tool Rack, writes the PAPER ledger, and opens its read-only local dashboard.
5. Press **Ctrl+C once** for an orderly PAPER stop. The 90-minute deadline uses the same stop path: entries cease and Commander requests exits using current held-side depth. The default exit grace is up to 120 seconds. A second Ctrl+C stops immediately and preserves any unresolved PAPER inventory.
6. After the process stops, use `04_EXPORT_LAST_TOOL_RACK_RUN.cmd` to create a diagnostic ZIP. The exporter verifies the durable economic journal before archiving it.

The launchers select, in order, the bundle-local `.venv`, `C:\KalshiBTCBot\.venv`, a working `python`, or `py -3`. They quote paths, set UTF-8, and pause on completion so errors remain visible. Start/check/export do not install packages. Python 3.10+ syntax is supported; Python 3.12 and 3.14 are the validation targets. The local validation interpreter and the remote CI status are separate facts; see the handoff.

### Credentials and data

Market-data authentication reads `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH` from the environment or the existing credential directory's configuration. It reads the key to sign the **market-data WebSocket handshake**. There are no account/order API calls, account balance reads, or real-money trades. Credentials and private key files are not packaged or exported. Source: [market-data client](strategy_core/marketdata/kalshi_public.py).

The default output folder is `E:\TachyosToolRackPaper` when `E:\` exists on Windows; otherwise it is `TachyosToolRackPaper` under the current user's home directory. `TACHYOS_TOOL_RACK_PAPER_ROOT` or `--output-root` overrides it. Each session gets a dated `TOOL_RACK_PAPER_..._PID...` folder. Keep the previous run available for review before starting another session.

Advanced invocation from the extracted folder:

```bat
python TOOL_RACK_PAPER.py --minutes 90 --credential-dir "C:\KalshiBTCBot"
python TOOL_RACK_PAPER.py --minutes 90 --output-root "D:\TachyosToolRackPaper" --no-browser --dashboard-port 0
python TOOL_RACK_EXPORT.py --run "D:\TachyosToolRackPaper\TOOL_RACK_PAPER_..."
```

Use the selected environment's Python executable when it is not on `PATH`. Port `0` chooses an available loopback port. Closing the browser does not stop the PAPER engine; use its console. The dashboard has no trading controls and loads no third-party browser resources. Sources: [launcher](TOOL_RACK_PAPER.py), [dashboard](strategy_core/paper_dashboard.py).

## Four tools, one authority boundary

| Tool | Entry responsibility | Custody and termination | Default budget |
| --- | --- | --- | --- |
| **Rail** | Established same-direction EMA structure and residence; wait for a value ask. The opening/activation ask ladder is 40c, 42c, 44c, then a 50c soft maximum. | Maintain directional custody through healthy continuation. A confirmed opposing release can terminate it. After a protection exit, a fresh quote can offer a new value opportunity in the same Rail. Rollover creates a new economic slice. | $25 |
| **Alternating Mountain** | Mature edge window with adequate comparable structure and terminal cues: stall, hesitation, failed reextension or meaningful retreat. The protected middle has no entry authority. | Carry the living leg; recognize the next mature edge, invalidated entry edge, or confirmed opposing release. Healthy continuation can transfer management to a qualified structural owner. | $10 / $15 / $25 by the explicit tool tier |
| **Market Heist** | Repeated bounded range, genuine edge visits and traversals; directional lean biases the edge trade. | Carry toward the opposite box edge. A confirmed release ends box logic; a losing position receives the same explicit structural-exit review as a winner. | $10 / $15 by the explicit tool tier |
| **Release Watcher** | Advisory overlay while the current owner remains valid. Entry/handoff requires physical boundary break, directional expansion and confirmation of the new side. A first slowdown is insufficient. | Maintain confirmed release custody and report a genuine opposing transfer. It cannot independently send an execution command. | $25 |

The tool files and corresponding JSON files in `strategy_core/config/` define these policies. The router selects territory, specialists supply evidence and intents, and `OneCommander` decides. A `RELAY` intent never silently sells inventory: the runtime commits the authorized exit first and requires a subsequent fresh native quote before entry. Exact position/ticker/opportunity identities survive every callback. Sources: [Tool Rack](strategy_core/tool_rack.py), [Commander](strategy_core/commander.py), [tools](strategy_core/tools/), [runtime](strategy_core/paper_runtime.py).

## Economic and protection semantics

Entries sweep visible integer-lot ask depth within the authorized price and fee-inclusive budget. Exits sweep the **held side's bid depth**. The ledger uses exact ticker inventory and prevents duplicate command/opportunity fills and repeated same-ticker same-side stacking. Expensive WAITs do not consume opportunities. A one-sided book can disable new entries while still permitting an exit at a current held-side bid.

PAPER fills are modeled outcomes, not evidence of venue fills. Quotes can change between an observation and a real order; queue position, routing latency and actual execution are not simulated. Each economic event therefore records its native quote ID/provenance, depth sweep, quantity, cost, fees, gross P&L, net P&L, tool, territory/opportunity, command ID, and position ID. [Execution source and invariants](strategy_core/paper_execution.py).

The **fee assumption** is `ceil_to_cent(0.07 × quantity × price × (1 − price))` for modeled purchases and sales. It is inherited mechanical bookkeeping, **not a verified current official venue fee schedule**. Gross P&L excludes modeled fees; net P&L includes them. Settlement uses a verified exact-contract official binary result and no additional modeled settlement charge.

| Explicit floor policy | First ordinary arming | Trail from executable peak bid | Immediate protection |
| --- | --- | --- | --- |
| Mountain | At least +50% bid ROI, after 30 seconds | 5% | At least +100% bid ROI at any age |
| Heist | At least +50% bid ROI, after 30 seconds | 3% | At least +100% bid ROI at any age |
| Rail / Release | At least +100% bid ROI | 10% | At least +100% bid ROI at any age |

These thresholds are explicit per-tool policy, carried into Commander/execution; they are not selected by the executor. Once armed, a floor cannot be lowered, disarmed or waived by a tool. A floor breach requires Commander to exit; the executor rejects attempted non-exit actions while breached and does not invent an alternate strategy. Thin depth cannot earn a full-position peak. If current executable depth is unavailable, exit intent remains pending and the unresolved inventory remains visible.

There is **no losing-position sanctuary**. This does not create a generic fixed-loss stop: ordinary holds and structural exits remain the active tool's responsibility. An expired lot is never closed using the next ticker's book or a guessed zero. Official finality is fetched for the exact expired contract, independently of current-ticker activity.

## Reading the first session

The direct feed seeds EMA values from validated completed Coinbase minute bars. Physical arcs, edge comparisons and residence are built from actual forward observations. The 3/6/9-minute structural measurements use full elapsed horizons ending at the frozen live observation. This deliberately removes the old minute-endpoint lag; it is **not bitwise observer parity**. Cold or interrupted physical history must requalify before it grants new trading authority. Initial WAITs are expected; do not infer a failure from the trade count alone. [Physical source](strategy_core/physical_source.py).

Use these records together:

| Record | What it establishes |
| --- | --- |
| `RUN_MANIFEST.json` | Source/configuration hashes and the session's PAPER authority |
| `decisions.jsonl` | Physical evidence, owner, tool intents, Commander decisions, execution receipts and reasons |
| `physical_geometry.jsonl` | Causal geometry generated from the live physical source |
| `market_data_source.jsonl` | Feed status/provenance and continuity context |
| `paper_journal/*.json` | Hash-linked committed economic state; the durable accounting authority |
| `PAPER_LEDGER.json`, `STATUS.json` | Convenient projections; a temporary Windows read lock can delay a projection without undoing a committed trade |
| `RUN_SUMMARY.json` | Final cash, realized gross/net, modeled fees, events and unresolved inventory |
| `console.log` | Operator-visible startup, source, stop and error messages |

The session has a process-wide exclusive lease and a separate journal-writer lock. Before creating a fresh ledger, the launcher verifies that the prior journal is intact and flat, using both the global last-run pointer and the selected output folder's pointer. Changing output folders cannot hide known unresolved inventory. It does not blindly resume an open inventory ledger. Do not delete locks, journals or prior inventory to obtain a fresh balance. Export the stopped run and review any unresolved positions first.

## Validation boundary

`CHECK_TOOL_RACK_PAPER.py` uses an explicit test list. Real execution, custody, fee accounting, partial exits, already-armed protection, official settlement, restart refusal, source-gap requalification, dashboard isolation and exporter behavior are mandatory. Legacy R22 adapters, shadow comparisons, old run-source tests and Nautilus patch tests are explicitly outside this package.

`BUILD_TOOL_RACK_PAPER_BUNDLE.py` uses exact file names, audits Python import closure and UTF-8 text I/O, creates a per-file SHA-256 manifest, extracts the ZIP, and runs the same mandatory check from the extraction with the checkout removed from `PYTHONPATH`. It publishes the ZIP only after that extracted check passes.

The offline fixtures validate behavior; they do not establish trading profitability. Native Windows launch/locking behavior and an authenticated live-market PAPER session still need operator-side validation. No new market run was started while preparing this delivery. The dependency installer pins are `websockets==16.0` and `cryptography==50.0.2`; CHECK also accepts an existing environment whose required APIs pass and reports its actual versions. See the [versioned WebSocket API](https://websockets.readthedocs.io/en/16.0/reference/sync/client.html) and [cryptography installation documentation](https://cryptography.io/en/50.0.2/installation/).
