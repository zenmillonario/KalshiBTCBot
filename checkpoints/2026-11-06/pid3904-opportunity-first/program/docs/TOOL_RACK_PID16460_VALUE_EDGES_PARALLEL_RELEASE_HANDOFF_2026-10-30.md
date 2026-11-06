# PID16460 Value Edges + Parallel Release Handoff — 2026-10-30

Release: `TOOL_RACK_VALUE_EDGES_PARALLEL_RELEASE_PAPER_20261030`  
Runtime: `TOOL_RACK_PAPER_VALUE_EDGES_PARALLEL_RELEASE_20261030`

This is a PAPER-only tuning release. It preserves the parent-scale Mountain/Rail architecture and keeps generic fades disabled.

## Governing changes

1. Ordinary qualified Mountain edge above 20c arms the next-leg side and waits for <=20c instead of paying immediately. The armed mission survives the first pullback without requiring the original terminal flag to remain current.
2. Very small terminal Mountains (<=180s) may still relay immediately up to 50c using $10.
3. Normal Mountain <=20c value uses $15. Mature 11c-16c hover with >=5 minutes, non-extended parent and no unfinished gap expansion uses $25.
4. No fresh Mountain entries in the final 240s. The exact earned side may carry to the next ticker for <=240s and requires <=20c.
5. Strict parallel Market Heist trades its actual box edges with $10/$15 sizing and may arm +65% executable profit protection with a 5% trail.
6. Same-parent breakout from a qualified parallel box transfers immediately to Rail; it is never faded. Parent-aligned Rail uses $25 and may accept up to 50c on this release transition.
7. Existing Mountain/Rail +100% 5% peak-lock and +150% 3% tightening remain.
8. EMA30 remains spine/context only. It cannot choose YES/NO or activate Rail without EMA9 parent evidence.
9. Generic tactical/counter-parent fades remain OFF.

## Recorded run controls

PID16460: an early otherwise-valid 52c edge must arm/wait; 11c-16c mature hover with >5m is exceptional value; $10/$15/$25 tiers are explicit; and a ~3m-to-close penny edge is deferred. PID5452 remains the parent/child long-Mountain control.
