# Tool Rack live-shadow sidecar

## What it does

`START_TOOL_RACK_SHADOW.cmd` launches the isolated Tool Rack against the newest
qualifying R22 PAPER run under:

`E:\TachyosR22IndependentPaperExperiments`

It reads only:

- `tachys_runtime_hf2.json`
- `tachys_ema_geometry_v9_4i.csv`

It does **not** import the R22 engine, call an executioner, mutate the PAPER
journal, or place venue orders.

## Output

Default output root:

`E:\TachyosToolRackShadow\<PAPER_RUN_NAME>\`

Files:

- `TOOL_RACK_SHADOW_STATUS.json` — current auditable status for Nautilus vNext.
- `tool_rack_shadow.jsonl` — append-only shadow history for later forensics.

The status includes territory, primary tool, overlays, resolved intent,
Commander reason, accepted side, observed ask, and tool price ceiling.

## Safety boundary

The sidecar explicitly publishes:

- `read_only: true`
- `execution_authority: NONE`

Nautilus vNext withholds Tool Rack status unless those facts and the exact run
identity match.

## Current detector scope

The run-file source currently proves Rail from physical EMA geometry without
using legacy R22 strategy routes. Mountain/Heist/Release tools exist and are
fully unit-tested in the Tool Rack core, but their dedicated clean live
run-file detectors are still being wired. Legacy R22 Heist/release authority
labels are deliberately ignored.
