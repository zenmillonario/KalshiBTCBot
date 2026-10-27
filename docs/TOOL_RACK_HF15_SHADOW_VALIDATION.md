# Tool Rack v1 — HF15 Physical-Packet Shadow Validation

Mode: offline / read-only validation only.
No PAPER or venue execution occurred.

The Tool Rack R22 adapter was exercised against the actual HF15
build_physical_questions implementation from the HF15 automatic Rail package.

## Purpose

Prove that Tool Rack can consume R22's useful physical measurements without
inheriting R22's strategy permission routes.

## Procedure

For both DOWN and UP Rail fixtures from HF15's own automatic-Rail test:

1. generate the actual R22 source fixture;
2. call HF15 build_physical_questions;
3. deliberately overwrite the legacy rail_flow_entry eligible flag to False;
4. adapt only the physical evidence packet into Tool Rack;
5. evaluate through Tool Rack Router -> RailTool -> OneCommander.

## Result

NO  -> DOWN_RAIL -> RAIL -> ENTER NO  -> COMMANDER_ACCEPTED_TOOL_INTENT
YES -> UP_RAIL   -> RAIL -> ENTER YES -> COMMANDER_ACCEPTED_TOOL_INTENT

This is intentional. A legacy R22 route denial can no longer starve a Tool Rack
Rail entry because the new adapter ignores legacy routes.

The adapter currently treats legacy Heist ownership only as provisional SHADOW
telemetry. A clean MarketHeistTool / bounded-box detector remains future Tool
Rack work.
