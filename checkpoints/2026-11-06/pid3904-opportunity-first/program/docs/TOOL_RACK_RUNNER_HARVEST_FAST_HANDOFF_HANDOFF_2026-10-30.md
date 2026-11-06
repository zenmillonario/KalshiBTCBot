# Tool Rack Runner Harvest + Fast Narrow Handoff — 2026-10-30

This PAPER release is a custody/execution refinement on top of the verified Release Runway + global 20c value-cap strategy. It does not reopen generic fades and it does not give EMA30 directional authority.

## Runner custody

Release, Rail, and physically proven extended/Slow-Rolling same-parent Mountain positions may enter RUNNER custody. A newly qualified runner does not arm the ordinary +100%/+150% percentage floor. Any protection already committed before Runner qualification remains monotone and cannot be loosened.

Runner exit sequence:

1. First distinct structural slowdown: HOLD.
2. A real resumption must occur before another slowdown counts.
3. Second distinct structural slowdown after that resumption: arm HARVEST, but do not sell weakness.
4. Wait for the next favorable full-lot bid uptick/re-extension and track the highest executable bid.
5. Collect on the first meaningful downtick (1c or more) from that fresh post-second-slowdown peak.
6. A genuine opposing physical transfer remains a hard structural exit and does not wait for harvest.

This is designed to capture more of release/breakout/long-runway winners without waiting for a complete collapse or mechanically clipping them at +100%/+150%.

## Fast narrow Mountain handoff

A non-extended, non-Slow-Rolling Mountain edge may use a brief two-role bridge when:

- the actual terminal edge is current,
- the current child arc is no older than 6 minutes,
- the terminal window is no older than 90 seconds,
- no release is in progress,
- the incoming opposite-side ask is <= $0.20,
- exactly one normal outgoing position is held.

The new side may book before the outgoing side is sold. It uses the opposite normal role slot (PRIMARY/Tactical bridge) only long enough to complete the handoff. On the next management beat the old outgoing lot is exited and custody transfers to the new side. This bridge is a terminal-edge handoff, not permission to fade an expanding parent.

## Long / wide Mountain top

Extended/Slow-Rolling/wide tops never use the overlap bridge. The earned side is preserved as a patient value window:

- first 4 minutes: hunt <= $0.15,
- after 4 minutes: may use the existing <= $0.20 global ceiling only if the same parent edge is still physically supported.

This preserves the user's ability to exploit the 4–6 candle wide top instead of chasing an early quote.

## Preserved rules

- Global fresh-entry hard cap remains $0.20.
- Generic counter-parent fades remain OFF.
- Release runway remains sovereign against opposite entries.
- EMA9/NAEVYR owns direction; EMA30/THAERYON is spine/context only.
- Strict Heist remains limited to qualified repeated compression/parallel boxes.
- $10/$15/$25 sizing and the existing cheap-hover rule remain unchanged.
- PAPER only; one Commander, one PAPER ledger.
