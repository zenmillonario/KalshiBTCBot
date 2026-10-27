# Tachyos Tool Rack v1 — Phase 2 Shadow Architecture Status

**Branch:** `tachyos-tool-rack-v1`  
**Base:** preserved PID21520 positive R22 branch.  
**Main branch:** untouched.  
**Mode:** strategy SHADOW / READ ONLY.  
**Tool Rack PAPER execution authority:** **NONE**.  
**Venue-order / real-money authorization:** **NONE**.

## Phase 2 milestone

The new strategy core is no longer dependent on legacy R22 strategy permission
routes for its primary physical territories.

Tool Rack now supports a complete shadow lifecycle:

```
raw EMA/price geometry
        |
        v
tool-specific physical detectors
        |
        v
Territory Router
        |
        v
primary territory tool + ReleaseWatcher overlay
        |
        v
deterministic LaneResolver
        |
        v
ONE Commander
        |
        v
objective safety
        |
        v
SHADOW intent only
```

## Tool-specific physical detectors

### Rail

`strategy_core/detectors/rail_geometry.py`

- current EMA9 direction from 3m/6m/9m structural slopes;
- EMA30 direction independently measured;
- current directional price/EMA residence is time-local to the latest
  contract-scale window;
- 1–2 contract persistence uses tolerant alignment/residence fractions, so
  shallow fakeouts do not erase an established Rail;
- old opposite-direction history does not dilute a full new Rail chapter;
- short opposite escapes do not instantly become a new Rail.

All thresholds live in `strategy_core/config/rail.json`.

### Alternating Mountain

`strategy_core/detectors/mountain_geometry.py`

Preserves PID19420 Clean Mountain Hard Relay:

- reconstruct living EMA9 arc episodes;
- compare current leg age against recent same-side completed arcs;
- protected middle remains WAIT;
- strict owner-side BTC extreme;
- several-beat edge window;
- stall / hesitation / failed re-extension / meaningful retreat;
- source-native `EXPANDING` remains active-release deferment;
- mirrored crest/trough behavior.

All detector thresholds live in `strategy_core/config/mountain.json`.

### Market Heist

`strategy_core/detectors/heist_geometry.py`

- repeated bounded sideways/compression box;
- repeated lower + upper outer-edge visits;
- center traversal required to establish repeatability;
- middle remains non-entry territory;
- bounded EMA drift distinguishes Heist from Rail/trend;
- EMA lean is measured inside the box;
- physical edge visit identity remains stable while box-bound estimates drift.

All detector thresholds live in `strategy_core/config/heist.json`.

### Release

`strategy_core/detectors/release_geometry.py`

Release is interpreted **against the Tool Rack's actual current owner**.

- first slowdown is WATCH, never automatic reversal;
- owner boundary must physically break;
- new direction must expand;
- plus old-owner failed re-extension OR accepted new-side residence;
- Heist release uses the preserved qualified-box boundary;
- Rail/Mountain transfer uses the old owner's physical EMA relationship;
- legacy R22 release labels have zero Tool Rack authority.

All detector thresholds live in `strategy_core/config/release.json`.

## RELEASE_TRANSITION custody

A confirmed physical release ends the outgoing tool's entry authority
**independently of whether the release entry fills**.

Example:

```
DOWN_RAIL owns
        |
physical UP release confirmed
        |
YES is too expensive -> ReleaseWatcher WAIT
        |
old NO Rail is STILL OFF
        |
RELEASE_TRANSITION owns
        |
new UP territory becomes physically established
        |
UP_RAIL tool activates
```

This prevents the old territory from resurrecting while the release side is
temporarily expensive.

## Live shadow source

`R22RunShadowSource` reads only:

- `tachys_runtime_hf2.json`
- `tachys_ema_geometry_v9_4i.csv`

No engine import. No strategy hook. No PAPER-run mutation.

The source now detects live:

- Rail;
- Alternating Mountain;
- Market Heist;
- release probe / handoff evidence.

Legacy R22 route permission, Heist ownership, and release labels remain
non-authoritative telemetry.

## Shadow sidecar

`START_TOOL_RACK_SHADOW.cmd`

Default input root:

`E:\TachyosR22IndependentPaperExperiments`

Default output:

`E:\TachyosToolRackShadow\<PAPER_RUN_NAME>\`

Outputs:

- `TOOL_RACK_SHADOW_STATUS.json`
- `TOOL_RACK_SHADOW_TIMELINE.json`
- `tool_rack_shadow.jsonl`
- `tool_rack_events.jsonl`

The timeline is deduplicated. It records meaningful territory, handoff, and
intent/block changes rather than one event per polling beat.

## Nautilus vNext

The visual work remains read-only and separate from strategy.

Base vNext patch:

`nautilus_vnext/APPLY_NAUTILUS_VNEXT.py`

Timeline extension:

`nautilus_vnext/APPLY_TOOL_RACK_TIMELINE.py`

Current visual doctrine:

- approximately 31% feed / 47% chart / 22% right rail;
- candle pane 83% of chart height;
- wider feed, larger feed type;
- compact scrollable current-position rectangle;
- restored `MAX @ $1` potential ROI + gross PAPER dollars;
- Tool Rack strip with territory / primary / overlay / intent / exact reason;
- accepted ask vs tool price ceiling;
- 45-minute shadow territory ribbon;
- shadow ENTER marker = dot;
- shadow RELAY/HANDOFF marker = diamond;
- actual PAPER entry = triangle;
- actual PAPER exit = circle.

This lets the operator visually compare the cleaned Tool Rack strategy against
the legacy R22 PAPER behavior without granting Nautilus any strategy authority.

## Exact branch acceptance

Latest completed acceptance at this freeze:

- GitHub Actions workflow: **Tool Rack v1 Acceptance**
- run: **#86**
- commit: `f48b7548fafaab5d252901070ee11ebc05f3e1ec`
- result: **92 / 92 PASS**
- failures: **0**
- errors: **0**
- log: `Ran 88 tests ... OK`

The suite includes:

- Rail $.30 opening entry and value ratchet;
- same-Rail profit-exit/re-entry;
- ticker rollover economic slice;
- Rail shallow-fakeout persistence;
- old-history isolation on new Rail acquisition;
- Mountain middle WAIT / mature crest+trough relay;
- raw Mountain edge detector;
- Heist box / lean / visit identity / release;
- raw Heist detector;
- owner-aware release geometry;
- confirmed-release old-lane suppression even on expensive release price;
- RELEASE_TRANSITION custody independent of fill;
- live run-file Rail/Mountain/Heist paths;
- live physical Rail release-transition fixture;
- legacy R22 authority isolation;
- per-tool external configuration;
- shadow event deduplication;
- Nautilus vNext layout/read-only patch;
- Nautilus territory ribbon;
- shadow-vs-PAPER ribbon markers;
- post-run shadow-vs-PAPER delay/chase/opposite/miss comparator;
- whitelist-only shadow bundle packaging that excludes legacy engine/execution files.

## Explicitly NOT promoted yet

- Tool Rack does not book PAPER trades.
- Tool Rack does not write the R22 journal/account.
- Tool Rack is not merged into `main`.
- No venue order path is connected.
- No real-money authorization exists.
- Shadow performance has not yet been supervised on a fresh long live run.
- Nautilus vNext still needs operator visual acceptance on Windows.

## Shadow-validation bundle

The CI workflow now builds an exact whitelisted ZIP after the acceptance suite
passes. The bundle manifest asserts:

- read-only strategy = true;
- PAPER execution authority = NONE;
- venue-order authority = NONE;
- legacy R22 engine included = false.

The extracted bundle includes one-click offline check, live shadow launcher,
post-run comparator, Tool Rack configs/tests/docs, and the Nautilus vNext
read-only patch layers.

## Next acceptance phase

1. Run the CI-built Tool Rack bundle beside a fresh R22 PAPER session in shadow.
2. Observe at least:
   - one Rail opening;
   - one Rail re-entry after profit/protection exit if naturally encountered;
   - one Mountain mature edge;
   - one Heist edge cycle if naturally encountered;
   - one territory release/handoff if naturally encountered.
3. Compare shadow ribbon and actual PAPER markers.
4. Forensically review any divergence.
5. Only after shadow behavior is accepted, design a guarded **INTERNAL PAPER**
   execution adapter for Tool Rack.
6. Keep venue/live-order integration out of scope.

**Migration rule:** never solve a Tool Rack miss by restoring the old R22
strategy-permission maze.
