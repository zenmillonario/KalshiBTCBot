# TACHYOS full implementation audit — 2026-10-29

## Scope

The supplied standalone Tool Rack archive was re-extracted and audited as a package rather than treating the latest symptom as a single-file bug. The audit covered Python strategy/runtime/tests, JSON strategy configuration, launch/build/check files, dashboard code/assets, documentation, fixtures and package-boundary metadata. Python files were parsed/compiled and JSON files parsed before behavioral changes were accepted.

## Root findings

### 1. Strategy authority was inverted

`OneCommander` stated that tools owned strategy and Commander did not reinterpret terrain. Actual runtime entry flow was Tool proposal -> MissionPolicy -> role selection -> LaneResolver -> Commander. Therefore a valid trade could be lost before Commander saw it. This contradicted the governing architecture: specialists are evidence/advisers, one Commander owns the trade decision, one executioner books it.

### 2. Exact recurring counter-expansion fade path existed

Mountain `_entry_intents` applied `strong_active_release` restraint only when `not full_arc`. A `full_arc` candidate therefore bypassed the restraint and could enter the opposite side while the living EMA9 parent remained in strong expansion. ToolRack additionally allowed a source-qualified full-arc counter candidate to coexist with a young expanding child.

### 3. Rail's apparent hard fade switch was dead

`strategy_core/config/rail.json` contained `"opposite_fades": false`, but the prior `RailConfig`/loader never loaded that key. It had no runtime effect. The same audit found additional strategy JSON switches that were declared but not wired into their runtime config objects.

### 4. Physical Rail MAIN could be vetoed by advisory thesis

MissionPolicy defined MAIN as `contract.thesis_side == side AND MAIN_CONTINUATION`, including Rail. Thus a currently owned physical Rail could offer a correct same-direction value entry and still be rejected because conditional/history contract thesis disagreed or was unresolved. This is a direct starvation route and violates EMA9/physical-terrain sovereignty.

### 5. Tests were locally strong but compositionally incomplete

Large portions of the suite passed even with the above behavior. Existing tests covered tools, mission rules and execution safety independently, but did not freeze the exact invariant `full_arc + strong_active_release => NO opposite entry`, nor did they require `rail.opposite_fades: false` to be live. The correction adds those exact controls and Commander-level regression tests.

## Corrections

- OneCommander is now documented and implemented as the single strategic admission boundary.
- ToolRack exposes the complete reviewed adviser candidate set as `commander_intents`; the legacy lane-resolved `intents` remains diagnostic/backward-compatible.
- PAPER runtime sends `commander_intents` to Commander.
- Commander deterministically chooses among entry candidates and independently blocks opposite entry against active EMA expansion.
- Commander independently blocks a Rail counter-fade unless a confirmed ReleaseWatcher HANDOFF transfers ownership.
- Mountain blocks `strong_active_release` before the full-arc exception can admit the opposite side.
- ToolRack does not manufacture compatible opposite tactical fades while Rail owns and `opposite_fades` is false.
- MissionPolicy accepts a current physical Rail MAIN based on current parent side + continuation + current value location + complete target/history provenance even if advisory directional thesis disagrees; missing provenance still waits.
- Previously decorative strategy JSON controls are loaded and behaviorally wired.

## Deliberately unchanged

PAPER-only execution, exact native quote/depth checks, source-current checks, immutable journal/finality mechanics, custody/Lazarus separation, existing winner management, full-parent edge/value requirements and no-middle intent remain. The correction does not claim a future win rate or profitability.

## Required next evidence

Run this build in PAPER and export the complete run. The review should answer four questions first: (1) Did an established Rail enter same-direction value near contract opening/rollover? (2) Did any opposite entry occur while `strong_active_release=true`? It must be zero unless it is a confirmed ReleaseWatcher handoff. (3) Did real full mountain peaks/valleys participate after expansion ended? (4) If a valid candidate did not trade, which exact Commander reason blocked it? The new authority path is designed so that answer is visible at one boundary rather than hidden across several veto layers.
