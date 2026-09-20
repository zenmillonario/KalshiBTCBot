# Router V6.3 — Global Hand/Boundary Transfer Acceptance Replay

Purpose: test the V5 transfer hypothesis outside the 28 stale PULLBACK_WAIT cases.

Universe:
- every true HAND authority transfer in the three archived runs;
- every directional BOUNDARY_RELEASE row whose transition_reason is CHURN_RELEASED;
- near-simultaneous same-side transfer evidence is clustered within 9s to avoid double-counting one battlefield epoch.

The acceptance band is pre-existing, not optimized here:
- V9.4G V94G_FIRST_VALID_MIN_ASK = 0.20
- V9.4G V94G_FIRST_VALID_MAX_ASK = 0.80
- legacy MAX_ENTRY_ASK = 0.80

Global clustered transfer epochs: 95
Quotes reconstructed: 95/95
Inside existing 0.20–0.80 band: 53
Accepted-band settlement correctness: 27/52
Accepted-band simple $10 hold sum: -39.65
Outside-band directional correctness (economics not endorsed): 28/42

Counterfactual economics buy the transfer side at the nearest reconstructed ask and hold to settlement. No fees, fills, Treasury, stops, or management are modeled.

## By transfer evidence

- BOUNDARY_RELEASE: N=60 quotes=60 accepted=39 settlement=18/38 askAvg=0.532 $10HoldSum=-46.93
- HAND_AUTHORITY_TRANSFER: N=35 quotes=35 accepted=14 settlement=9/14 askAvg=0.631 $10HoldSum=+7.28

## By price

- 20_40C: N=13 quotes=13 accepted=13 settlement=4/13 askAvg=0.292 $10HoldSum=-1.02
- 40_55C: N=6 quotes=6 accepted=6 settlement=2/6 askAvg=0.475 $10HoldSum=-21.87
- 55_70C: N=19 quotes=19 accepted=19 settlement=11/18 askAvg=0.617 $10HoldSum=-0.66
- 70_80C: N=15 quotes=15 accepted=15 settlement=10/15 askAvg=0.749 $10HoldSum=-16.09
- GT80C: N=29 quotes=29 accepted=0 settlement=0/0 askAvg=NA $10HoldSum=+0.00
- LT20C: N=13 quotes=13 accepted=0 settlement=0/0 askAvg=NA $10HoldSum=+0.00

## By time remaining

- 180_300S: N=10 quotes=10 accepted=4 settlement=3/4 askAvg=0.688 $10HoldSum=+5.67
- 60_180S: N=10 quotes=10 accepted=2 settlement=0/2 askAvg=0.240 $10HoldSum=-20.00
- GE300S: N=60 quotes=60 accepted=42 settlement=21/41 askAvg=0.550 $10HoldSum=-27.67
- LT60S: N=9 quotes=9 accepted=1 settlement=1/1 askAvg=0.720 $10HoldSum=+3.89
- UNKNOWN: N=6 quotes=6 accepted=4 settlement=2/4 askAvg=0.635 $10HoldSum=-1.54

## By run

- 2026-09-19_v9_5a_late_mature_shadow_5h: N=21 quotes=21 accepted=13 settlement=9/13 askAvg=0.533 $10HoldSum=+23.71
- 2026-09-20_v9_5a_swirl_orbit_long_01: N=21 quotes=21 accepted=12 settlement=4/12 askAvg=0.562 $10HoldSum=-13.86
- tachys_v9_5a_price_freshness_active_treasury: N=53 quotes=53 accepted=28 settlement=14/27 askAvg=0.568 $10HoldSum=-49.49

## Interpretation discipline

- This is the first broad test of transfer+market-acceptance outside the stale-pullback selection that generated V5.
- HAND/BOUNDARY are existing structural observers; V6.3 adds no new detector.
- The 0.20–0.80 band predates this replay and is not tuned to these outcomes.
- Multiple transfer epochs can occur in one contract; each is a new structural epoch, not a resurrection of an old signal.
- Settlement hold is intentionally crude and cannot be treated as expected live P&L.
- No V9.5A authority changes.
