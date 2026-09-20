# Entry Authority Router V2 — Path / Recognition Replay

Purpose: measure the movie, especially the time between first directional evidence, first structural validity, actual entry, and later arc resolution.

Rows: 188
Current-engine realized P&L represented: $-74.00

## Prevalidation delay bins

- 3_6S: N=14 P&L=$-13.57 settlement=8/14
- 6_9S: N=3 P&L=$-5.54 settlement=1/3
- 9_15S: N=11 P&L=$-37.42 settlement=6/10
- GE15S: N=86 P&L=$-86.51 settlement=52/84
- LT3S: N=74 P&L=$+69.03 settlement=47/73

## Repricing from first directional evidence

- 0_3C: N=12 P&L=$-22.98 settlement=7/12
- 3_6C: N=24 P&L=$-15.98 settlement=14/24
- 6_9C: N=20 P&L=$-22.25 settlement=11/20
- 9_15C: N=25 P&L=$-19.20 settlement=15/25
- GE15C: N=28 P&L=$-33.70 settlement=21/27
- LE0C: N=79 P&L=$+40.09 settlement=46/76

## Initial router state

- HINGE_WAIT: N=43 P&L=$+11.43 settlement=28/43
- MID_PLAY_CLOSED: N=19 P&L=$+1.56 settlement=9/18
- PULLBACK_WAIT: N=40 P&L=$-29.00 settlement=27/39
- TACTICAL_COUNTERWAVE_ONLY: N=11 P&L=$+9.43 settlement=6/11
- UNCLASSIFIED_ENTRY: N=28 P&L=$-16.96 settlement=17/28
- UNRESOLVED_STORM: N=47 P&L=$-50.46 settlement=27/45

## Which release appeared first after entry

- NO_RELEASE_SEEN: N=11 P&L=$+19.45 settlement=9/10
- OPPOSITE_RELEASE_FIRST: N=40 P&L=$-46.25 settlement=18/39
- SAME_SIDE_RELEASE_FIRST: N=137 P&L=$-47.21 settlement=87/135

## Legacy lateness class

- CHASE: N=5 P&L=$+4.48 settlement=3/5
- FAIR: N=66 P&L=$-78.38 settlement=40/63
- LATE: N=7 P&L=$+5.21 settlement=6/7
- VALUE: N=110 P&L=$-5.31 settlement=65/109

## Interpretation discipline

- Prevalidation delay begins at first directional evidence, not at first structural approval.
- Repricing from first directional evidence measures how much Kalshi moved while Tachys was deciding.
- Later release ordering is descriptive. It does not prove a hypothetical entry would have filled or been managed identically.
- No threshold in this report is paper authority.

The next step is to inspect the high-loss combinations, then write a governor rule only if the same structural pattern repeats across independent runs.
