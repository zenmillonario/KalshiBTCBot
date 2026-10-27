# Tachyos Tool Rack — Port Manifest

**Branch:** `tachyos-tool-rack-v1`

This document prevents the legacy R22 strategy-permission maze from being
silently imported into the new Tool Rack core.

## Mechanical systems allowed to be ported

These systems may be brought forward from the latest verified R22 lineage,
provided their strategy-neutral behavior is preserved:

- production Kalshi read-only market data transport;
- native ticker-safe bid/ask/depth handling;
- reconnect / source freshness infrastructure;
- PAPER account and finite-liquidity mechanics;
- one guarded executioner;
- durable journal / projection;
- exact-contract inventory and custody;
- hard executable winner floors;
- verified finality / settlement handling;
- Observer42 / Navigator / Nautilus read-only plumbing;
- compact diagnostic collection;
- exact source/hash pinning and startup integrity.

## Strategy authority that must NOT be ported automatically

Do not import these merely because they existed in R22:

- global campaign permission;
- global consumed-generation permission;
- parent/wall labels with standing veto power;
- advisor score/vote/committee routing;
- Wide authority;
- a global hard-edge law outside a territory tool;
- opportunity normalization that can merge one tool's state into another;
- first-minute blanket waits that override a tool's explicit opening rule;
- PT/target strategy vetoes;
- rollover-as-physical-reset logic;
- strategy gates owned by Navigator, Observer, Looking Glass, Arc Echo,
  Candlestick, or any other specialist.

Any legacy rule must have a named home in a Tool Rack tool, Router, Commander
objective-safety boundary, or execution/custody layer. Otherwise it stays off
the new ship.

## Clean authority boundary

```
physical measurements
        |
        v
Territory Router
        |
        v
territory tools + compatible overlays
        |
        v
standardized intents
        |
        v
ONE Commander
        |
        v
objective safety only
        |
        v
ONE executioner
```

## Acceptance rule

A release is not accepted because test count is large. The simple behavior of
each tool must pass from physical evidence through Router, tool, Commander, and
execution seam.

Rail remains the first required proof:

```
DOWN Rail already owns
new contract opens
NO ask .30
fresh quote / sufficient depth
=> $25 NO ENTER
```

If this case fails, the Tool Rack build fails.
