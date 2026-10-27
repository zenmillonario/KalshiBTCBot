# Tachyos Tool Rack v1 — Phase 1 Status

**Branch:** `tachyos-tool-rack-v1`  
**Isolation:** branched from preserved PID21520 positive base; not merged to `main`.  
**Authority:** Tool Rack remains SHADOW / read-only. No PAPER or venue execution authority has been connected.

## Architecture now present

```
physical evidence
      |
      v
Territory Router
      |
      v
primary territory tool + compatible ReleaseWatcher overlay
      |
      v
deterministic LaneResolver
      |
      v
ONE Commander
      |
      v
objective safety boundary
      |
      v
execution seam (test/future integration only)
```

Primary tools implemented:

- `RailTool`
- `AlternatingMountainTool`
- `MarketHeistTool`

Compatible universal overlay:

- `ReleaseWatcher`

All tool tuning is externalized under `strategy_core/config/`.

## Rail controls locked

- UP Rail -> MAIN YES.
- DOWN Rail -> MAIN NO.
- Confirmed Rail MAIN entries use $25 PAPER structural tier.
- New contract creates a fresh economic slice of the same physical Rail.
- Opening value ladder: <=.40 first 60s, <=.42 60-120s, <=.44 120-240s, <=.50 later qualified value.
- Expensive WAIT does not consume the opportunity.
- Profit/protection exit does not end Rail. If Rail remains intact, same-ticker value re-entry rearms immediately.
- Rollover does not end Rail.
- Ordinary opposite fade authority is absent.
- Release/territory transfer ends the Rail cycle.

## Alternating Mountain controls locked

Preserves PID19420 Clean Mountain Hard Relay doctrine:

- wait for the mature physical edge;
- never enter the middle merely because price is cheap;
- price may discover the larger extreme first, while EMA9 owns the physical leg;
- mature edge + stall/hesitation/failed re-extension/meaningful retreat can relay before perfect EMA9 curl;
- strong active breakout/release defers the fade;
- edge window may span several native beats/candles;
- after relay, the Mountain territory persists across successive EMA9 legs.

## Market Heist controls locked

- unresolved compression = WAIT;
- real bounded/revisited box = Heist;
- lower outer edge -> YES renter;
- upper outer edge -> NO renter;
- repeat visits remain independent opportunities;
- EMA lean favors the aligned box side without turning EMA30 into sovereign authority;
- confirmed breakout/drop stops fading the box and transfers to ReleaseWatcher.

## Release controls locked

ReleaseWatcher is an overlay, not a reversal hunter.

First slowdown alone is WATCH.

Affirmative handoff requires:

- candidate side;
- physical boundary break;
- directional expansion;
- and old-owner failed re-extension OR accepted new-side residence.

A confirmed HANDOFF relay has deterministic lane priority over stale outgoing entry intents. Accepted release intent is marked Leviathan custody.

## Legacy R22 isolation

The R22 migration bridge deliberately ignores strategy authority from:

- legacy `routes`;
- `rail_flow_entry.eligible`;
- legacy Heist ownership labels;
- legacy Heist takeover labels;
- legacy release/handoff permission labels.

Useful physical measurements may be adapted; old permissions cannot authorize or starve Tool Rack.

## Live shadow sidecar

`START_TOOL_RACK_SHADOW.cmd` / `TOOL_RACK_ATTACH_R22_SHADOW.py`

Reads only an existing R22 PAPER run's:

- `tachys_runtime_hf2.json`
- `tachys_ema_geometry_v9_4i.csv`

Writes only to:

`E:\TachyosToolRackShadow\<PAPER_RUN_NAME>\`

The source currently proves live Rail geometry independently. Clean live Mountain/Heist/Release physical detectors remain follow-up work; legacy strategy labels will not be substituted.

## Nautilus vNext

A known-base visual/read-only patch lives under `nautilus_vnext/`.

Locked changes:

- Bridge proportions approximately 31% feed / 47% chart / 22% right rail.
- Candle-price pane ratio 75% -> 83%.
- Wider feed and larger feed type.
- Compact scrollable current-position panel (~190px cap).
- Restore `MAX @ $1`: potential ROI percent + potential gross PAPER dollars from existing `payoff_capacity` data.
- Add Tool Rack strip: territory, primary tool, overlay, intent, observed ask vs tool ceiling, exact Commander/block reason.
- Tool Rack status is displayed only when read-only/no-authority and exact-run identity checks pass.
- Saved/custom chart zoom remains untouched; normal ~3-contract / 45-minute view remains the default behavior.

## Exact branch acceptance

Latest branch workflow:

- GitHub Actions: `Tool Rack v1 Acceptance`
- Run: #18
- Result: **52 tests PASS / 0 failures / 0 errors**
- Log: `Ran 52 tests ... OK`

This includes strategy-core, live-run source, legacy-authority isolation, release/lane behavior, and focused Nautilus vNext patch tests.

## Next ordered work

1. Build clean live Alternating-Mountain physical detector from raw geometry/edge behavior.
2. Build clean live Market-Heist box detector from raw compression/revisit evidence.
3. Build clean live ReleaseWatcher evidence producer from physical boundary/expansion/acceptance facts.
4. Run Tool Rack beside R22 PAPER and compare shadow decisions visually in Nautilus.
5. Only after shadow evidence is satisfactory, design guarded PAPER execution integration.
6. Do not merge to `main` before the simple Tool Rack acceptance cases and supervised shadow review remain stable.

**Migration rule:** never replace this tool architecture with the legacy R22 permission maze merely to reuse old code.
