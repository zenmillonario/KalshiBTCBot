# Tool Rack + Nautilus — PID16280 correction handoff

Release identifier: `TOOL_RACK_PID16280_CORRECTIONS_NAUTILUS_TV_V3_20261027`  
Runtime revision: `TOOL_RACK_PAPER_PID16280_CORRECTIONS_20261027`  
Nautilus revision: `TOOL_RACK_NAUTILUS_TV_V3`  
Isolated source branch: `tachyos-tool-rack-pid16280-corrections-20261027`  
Mode: **PAPER only**, with one Tool Rack, one Commander and one passive journal writer.

This prepares the next operator-run session with the approved corrections and The Nautilus together. It supersedes the initial protection values and automatic-stop behavior in the [historical v1 handoff](TOOL_RACK_PAPER_HANDOFF_2026-10-27.md). The user-facing startup instructions are in the [current README](../README_TOOL_RACK_PAPER.md). No live market session is started by preparation or by the offline acceptance commands.

The package also preserves the exact authoritative archive copy of [Strategy Backbone v2026-10-26.6](../TACHYOS_STRATEGY_BACKBONE_V1.md) as its physical-doctrine reference. The [Tool Rack architecture reference](TACHYOS_TOOL_RACK_STRATEGY_CORE_V1.md) and this current release handoff identify the named authority homes and implemented port behavior. The backbone's historical R22 implementation labels and migration notes do not import an R22 engine or create legacy runtime permissions. Its bytes and the current documentation are covered by the same delivery manifest as the executable files.

## TV readability v3 display update

The follow-up request changes presentation only: desktop/TV feed width is reduced from roughly 31% to 22%, its type is approximately doubled, and the right positions column grows to roughly 27%. Current Positions uses larger text and more vertical space. The separate bottom protection panel is removed; per-position floor/peak details remain visible. YES and NO cards use distinct BID/ASK values and concise freshness status, with technical provenance available in tooltips and Sources.

All strategy, execution, recovery, feed, runtime and session-management code/configuration remains identical to approved strategy commit `4153789`; only the dashboard revision identifier changes in the Python projection. This package is for the next normal launch. An active dashboard retains the assets loaded at its startup, so do not stop a market session merely to refresh the display. The same 90-minute entry window and normal held-position drain continue.

The revised actual-browser fixture passed at the supplied 1884×1050 desktop size and exercised 1440×900, 1280×800 and 390×844 layouts. Visual inspection confirmed the enlarged feed/position typography and compact quote header. The existing feed filters, pause/reload, trade review, position accounting, DRAINING, Lazarus, stale-data ageing and chart controls continued to pass, with no browser errors, CSP violations or external requests. A direct comparison verified 39 core/config files against `4153789`, allowing only the dashboard revision string, plus an unchanged run launcher. The delivered extraction must pass the same 273-test package gate.

## Corrections carried into the run

| Area | Corrected behavior | Source and focused evidence |
| --- | --- | --- |
| Mountain maturity | Sparse phase labels no longer substitute for causal shape and duration. The independent paired-gap route supports a qualified pre-curl edge. Actual equal-duration acceleration and spent-return location are measured. | `detectors/mountain_geometry.py`, `physical_source.py`, `test_pid16280_mountain_corrections.py` and its compact recorded fixture |
| Failed Mountain chapter | A failed physical chapter retires across ticker rollover and requires genuine physical rearm. Persistent source-bound failed-thesis management retains ordinary breathing; valid terminal, adverse release and armed-floor exits remain available. | `tools/mountain.py`, `config/mountain.json`, Mountain correction tests |
| Late Release custody | A late purchase needs qualified current Release evidence. A latched ownership label alone cannot supply acquisition authority. Adoption of an existing aligned lot consumes the Release opportunity identity, preventing a second purchase after that lot exits. | `tool_rack.py`, `tools/release.py`, `test_pid16280_release_custody.py` and its compact recorded fixture |
| Profit protection | MAIN baseline is 10%, tactical 5%, true Heist 3%. Earned +50% protection may defer its first arming below +100% with either current healthy continuation or an observed advancing return. +100% arms immediately at any age. Weak/spent +100% uses at most 5%; +150% or an armed verified terminal uses at most 3%; +600% uses at most 2%. | Explicit policy in tool configuration/management and executor; `test_profit_protection_corrections.py` |
| Lazarus | A source-bound custody state can retain the same inventory after an ordinary thesis fails when current recovery evidence qualifies. Loss alone is insufficient. Detachment, supported restoration and required exit are explicit. Already-armed floors and hard adverse facts retain precedence. | `recovery.py`, runtime/controller/executor custody records; `test_recovery_custody.py` |
| Timed session end | `--minutes` limits new entries. Existing positions continue their normal strategy, protection and exact-contract finality until flat, with a fixed bounded drain deadline. Manual Ctrl+C remains an explicit flatten request. | `TOOL_RACK_PAPER.py`, `paper_runtime.py`, `test_entry_window_draining.py`, `test_session_draining_launcher.py` |
| Nautilus | The same launch starts the local Nautilus Bridge and actual Engine feed. DRAINING, Lazarus custody, protection, exact inventory, gross/net/fees, and quote/source freshness remain visible. | `nautilus_projection.py`, `paper_dashboard.py`, `nautilus/`, projection/dashboard/browser tests |

The package introduces no target-price veto. A displayed venue target is informational; it does not replace physical strategy evidence or official settlement authority. Historical chart candles remain separate from forward physical qualification.

The two Mountain entry routes remain independent. Shape/duration uses actually observed comparable predecessors. The paired-gap route uses EMA9–EMA30 and BTC–EMA9 gaps from the same historical peak observations, plus covered current slowdown; it does not add a shape or age requirement. Missing steepness coverage remains Unknown under backbone §0C, while observed steep motion can defer that route. The inherited 18% gap, 20% height and 0.25 normalized-shape resolutions are explicit provisional PAPER measurements, not fitted profitability thresholds.

## Session lifecycle

Double-click `01_START_TOOL_RACK_PAPER_90M.cmd` from the fully extracted package. Its preflight verifies the strict file boundary and dependency APIs, then starts one PAPER process and opens The Nautilus. The launcher does not install packages. The normal browser address is local port 8580 with the existing bounded fallback ports.

The 90-minute entry clock starts after the direct source startup completes. Its cutoff is checked again after each source await, so an awaited frame cannot cross the deadline and still receive new-entry authority. At cutoff, the runtime enters **DRAINING** and emits `PAPER_ENTRY_WINDOW_CLOSED_DRAINING` for new entries. Held-position strategy reviews, armed-floor enforcement and official-finality checks continue.

The automatic drain deadline is frozen at the latest held contract's close plus `--finality-buffer-seconds`, normally 120 seconds and bounded to 0–300. Its wait uses a monotonic deadline, so repeated polling or missing settlement cannot extend it. If positions close normally or settle officially, the final reason is `PAPER_ENTRY_WINDOW_COMPLETE_FLAT`. If the deadline arrives with unresolved inventory, the final reason is `PAPER_ENTRY_WINDOW_FINALITY_TIMEOUT_UNRESOLVED`, the original ledger remains non-flat, and the process returns code 2. No timer-generated sale or guessed settlement is recorded.

Manual **Ctrl+C once** is different: it requests Commander-led flattening at current held-side depth and uses `--stop-grace-seconds`, normally 120 seconds. It still works as a first orderly request while the automatic drain is active. A second Ctrl+C stops immediately; when received during a source await, the launcher checks it before another engine dispatch. A manual grace timeout preserves inventory with `OPERATOR_STOP_GRACE_EXPIRED_UNRESOLVED`. Code 0 means the stopped ledger is flat; code 2 means unresolved inventory; code 1 reports a runtime failure.

After stopping, `04_EXPORT_LAST_TOOL_RACK_RUN.cmd` verifies the committed journal and creates diagnostics. Existing global lease, single-writer lock, prior-run integrity and prior-inventory checks remain. A new simulated balance cannot hide known unresolved prior positions.

## Protection and custody remain distinct

ROI thresholds use executable held-side contract bids. Peak qualification requires the full remaining integer lot's current native depth. Trailing percentages apply to the earned peak bid; they are not ROI percentage-point stops. Once protection arms, its absolute floor and band can only tighten. A native-depth gap cannot earn a new peak, and an unavailable bid leaves exit intent pending.

Lazarus changes custody, not economics. The original position ID, ticker, side, quantity, cost, allocated fees, opportunity, entry metadata, and armed floor continue. The public state exposes `custody_state` as `NORMAL`, `LAZARUS`, `RECOVERED_NORMAL` or `EXIT_PENDING`, with recorded review metadata. Nautilus displays these records and emits custody transitions in its Engine feed without creating an entry or exit row. The UI has no authority to detach, restore, resize, waive a floor, or execute.

Admission requires developed loss, at least 60 seconds of position age and 45 seconds of continuously observed underwater custody, failed ordinary reclaim, and recent demonstrated recovery terrain. A stale or partial mark breaks that continuous evidence. One qualified detached lot can coexist with one genuinely renewed physical mission; the exact detached identity and current mission proof are checked by Commander and again by execution. Restoring the old lot keeps both lots separate and cannot admit a third lot. Loss of a classification label alone does not liquidate approved custody; affirmative adverse replacement, hard release, armed protection, manual stop and official finality remain binding.

Actual fills remain conservative PAPER simulations against recorded depth. They are not venue-fill evidence. The mechanical fee assumption remains separately labelled in the README; no profitability claim or current official fee-rate claim is made by these fixtures.

## Verification and delivery boundary

The package is built from an exact whitelist in `CHECK_TOOL_RACK_PAPER.py`, including the correction modules, selected tests, compact recorded fixtures, all Nautilus assets, four current Windows launchers, and this handoff. It excludes the legacy R22 engine, legacy Commander, shadow runtime, old Nautilus backend and external credentials.

The builder records the release ID, dashboard revision, default entry-window/drain policy and per-file SHA-256 hashes. It checks ZIP integrity, extracts the archive, removes inherited checkout `PYTHONPATH`, and runs the mandatory standalone check from that actual extraction. The root integration/build receipt is the authority for the final whole-package test count and archive hash; scoped checks are not substituted for that gate.

Focused launcher tests cover a cutoff crossed during a source await, normal held exit, verified finality, bounded unresolved timeout, first manual Ctrl+C during automatic drain, second Ctrl+C before another dispatch, and one engine/Nautilus lifecycle. Projection tests cover DRAINING freshness and custody display without duplicate fills or accounting reset. The existing real-browser fixture uses the actual local HTTP/assets and real offline executor/projection fixtures to check the Engine feed, positions, protection, trade review, source freshness, persistent chart controls, responsive layouts, DRAINING and Lazarus labels, and browser errors. It makes no exchange requests and requires no new dependency installation.

Scoped integration receipts completed during preparation:

| Check | Observed result |
| --- | --- |
| Nautilus projection and automatic/manual session lifecycle | 16 tests passed |
| Launcher cleanup, prior-inventory guard and diagnostic export | 6 tests passed |
| Existing Chromium Nautilus fixture, including DRAINING and Lazarus displays | Passed; no browser errors, CSP errors or external requests |
| Whitespace/diff check for the launcher, projection, package and workflow edits | Passed |
| Final frozen source checkout: strict package and execution CHECK | 273 tests passed in 31 explicitly selected modules; Python 3.12.14, websockets 16.0 and cryptography 50.0.2 |

The final source check includes the integrated strategy, custody, accounting and loopback dashboard tests. The delivery builder independently repeats those 273 mandatory tests from the actual extracted ZIP and publishes no archive unless that check succeeds. The delivered manifest records every exact source/file hash. The final delivery message supplies the archive hash and extracted-check result. No remote CI result is claimed.

This correction build still requires its first operator-side Windows launch and authenticated market session. Preparation validates the packaged behavior; the next run's diagnostic export provides the evidence for evaluating actual session behavior.
