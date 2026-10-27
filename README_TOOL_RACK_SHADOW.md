# Tachyos Tool Rack v1 — Shadow Validation Bundle

**Mode:** READ ONLY strategy shadow.  
**Tool Rack PAPER execution authority:** NONE.  
**Venue-order / real-money authority:** NONE.

This bundle is intentionally separate from R22. It contains no legacy R22
engine/execution files.

## Recommended order

### 1. Offline acceptance check

Double-click:

`00_CHECK_TOOL_RACK_SHADOW.cmd`

Do not trust the sidecar if this check fails.

### 2. Start/keep an ordinary R22 PAPER run

The existing R22 session remains the only PAPER engine. Tool Rack will only
observe its read-only runtime/EMA files.

### 3. Start Tool Rack shadow

Double-click:

`START_TOOL_RACK_SHADOW.cmd`

Default source root:

`E:\TachyosR22IndependentPaperExperiments`

Default Tool Rack output:

`E:\TachyosToolRackShadow\<PAPER_RUN_NAME>\`

The sidecar reads only:

- `tachys_runtime_hf2.json`
- `tachys_ema_geometry_v9_4i.csv`

It does not import or call the R22 engine.

### 4. Optional Nautilus vNext preview

The bundle includes:

- `nautilus_vnext/APPLY_NAUTILUS_VNEXT.py`
- `nautilus_vnext/APPLY_TOOL_RACK_TIMELINE.py`

They are read-only UI patches. The base patch verifies known HF15 Nautilus
source hashes by default and refuses unexpected source drift.

Nautilus vNext adds:

- narrower/taller TradingView-like chart proportions;
- wider feed with larger text;
- compact current-position panel;
- `MAX @ $1` potential ROI + gross PAPER dollars;
- Tool Rack status strip;
- 45-minute Tool Rack territory ribbon;
- shadow ENTER/RELAY/HANDOFF markers;
- actual PAPER ENTRY/EXIT markers for visual comparison.

### 5. Compare Tool Rack shadow with legacy PAPER

After enough evidence accumulates, double-click:

`02_COMPARE_SHADOW_TO_PAPER.cmd`

It writes:

- `TOOL_RACK_SHADOW_VS_PAPER.json`
- `TOOL_RACK_SHADOW_VS_PAPER.md`

under the same Tool Rack shadow run folder.

The report highlights:

- same-side matches;
- delay from Tool Rack intent to legacy PAPER entry;
- actual entry price minus Tool Rack observed price;
- opposite-side PAPER entries near a Tool Rack intent;
- missed Tool Rack opportunities;
- PAPER-only entries against a Tool Rack Rail/release.

## Files written by Tool Rack

Only the separate shadow root is mutated:

- `TOOL_RACK_SHADOW_STATUS.json`
- `TOOL_RACK_SHADOW_TIMELINE.json`
- `tool_rack_shadow.jsonl`
- `tool_rack_events.jsonl`
- optional comparison reports

No R22 journal/account/custody file is changed.

## Strategy snapshot

- Rail: MAIN direction, $25 structural tier, opening value hunt, repeated
  same-Rail re-entry after profit/protection exit, release ends cycle.
- Alternating Mountain: mature physical edge only, never middle.
- Market Heist: repeatable sideways/compression outer edges; EMA lean favors
  release side.
- ReleaseWatcher: universal overlay; first slowdown is WATCH; affirmative
  physical handoff produces RELEASE_TRANSITION and removes old-tool authority.

See `docs/TOOL_RACK_PHASE2_STATUS.md` for the exact architecture and current
acceptance evidence.
