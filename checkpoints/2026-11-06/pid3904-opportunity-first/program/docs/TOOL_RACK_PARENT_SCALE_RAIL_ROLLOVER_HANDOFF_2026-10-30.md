# Tool Rack Parent-Scale Rail / Rollover Handoff — 2026-10-30

Current runtime: `TOOL_RACK_PAPER_PARENT_SCALE_RAIL_ROLLOVER_20261030`.

## Governing controls

- EMA9 parent direction is sovereign; EMA30 is spine/context only.
- Normal/tight parent (<360s) Mountain terminal behavior is unchanged.
- 360–900s same-direction parent blocks child-only reversal fishing.
- >=900s parent, or an earlier parent-aligned rail-like structure with >=600s persistence, may activate Rail/Slow-Rolling custody.
- Rail direction must match the larger EMA9 parent. Generic EMA alignment alone cannot activate Rail.
- Rail opening value cap: <=0.35 through the first 240s of a contract.
- Mountain edge inside final 120s: defer to next ticker; inherited side may enter <=0.35 during first 240s.
- +100% executable peak: 5% trail. +150%: 3% trail.
- Market Heist remains strict tight compression/parallel churn. Generic fades remain paused.

## Recorded PID5452 controls

Bundled fixture: `tests/tool_rack/fixtures/pid5452_physical_geometry.jsonl.gz`.

Trade #5 remains a valid normal Mountain terminal edge. Trades #1/#3/#6/#7/#8/#9/#11 are blocked as child reversals inside extended parents. #4 demonstrates early parent-aligned Rail geometry. #10 remains same-parent UP pullback/rollover and its 0.39 YES ask is above the 0.35 opening value cap.
