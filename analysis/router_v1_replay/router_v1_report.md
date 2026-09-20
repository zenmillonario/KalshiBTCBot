# Entry Authority Router V1 — Replay Feature Report

This report is a structural replay, not a claim that the V1 states are ready for live authority.
Joins use timestamp+ticker+side+ask rather than trade_id alone.

Rows: 188
Current-engine realized P&L represented: $-74.00

## By run

- 2026-09-19_v9_5a_late_mature_shadow_5h: N=28 P&L=$-3.03
- 2026-09-20_v9_5a_swirl_orbit_long_01: N=41 P&L=$-34.08
- tachys_v9_5a_price_freshness_active_treasury: N=119 P&L=$-36.90

## Router replay states

- ENTRY_WINDOW_CANDIDATE: N=41 current-engine P&L=$-42.55 settlement=23/40
- HINGE_WAIT: N=32 current-engine P&L=$-1.86 settlement=20/32
- MID_PLAY_CLOSED: N=19 current-engine P&L=$+1.56 settlement=9/18
- NO_TRADE: N=34 current-engine P&L=$-24.87 settlement=21/33
- PULLBACK_WAIT: N=40 current-engine P&L=$-29.00 settlement=27/39
- RELEASE_ARMED: N=11 current-engine P&L=$+13.29 settlement=8/11
- TACTICAL_COUNTERWAVE_ONLY: N=11 current-engine P&L=$+9.43 settlement=6/11

## Action buckets

- ALLOW_CANDIDATE: N=41 current-engine P&L=$-42.55
- BLOCK: N=19 current-engine P&L=$+1.56
- TACTICAL_ONLY: N=11 current-engine P&L=$+9.43
- WAIT: N=117 current-engine P&L=$-42.45

## Important limitation

Subtracting the P&L of WAIT/BLOCK rows is only a deletion diagnostic. It is not a valid strategy backtest because waiting can create a later entry at a different price, and blocking one trade can change re-entry state and subsequent trades.

The next replay step is path-aware: follow each WAIT candidate until release, pullback, invalidation, or contract close and compare the later opportunity with the original entry.
