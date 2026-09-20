# Entry Authority Router V4 — Hard Release Economics

Scope: only stale >=9s PULLBACK_WAIT historical entries whose first hard release after entry was same-side.

Cases: 11
Release quotes reconstructed within ±9s: 11/11

The settlement-hold calculation is counterfactual and deliberately simple: enter at the reconstructed release ask and hold to settlement. It does not simulate Treasury, stops, fills, slippage, or management.

## By release timing

- 30_90S: N=4 quotes=4 settlement=3/4 releaseAskAvg=0.740 delayAvg=67.1s $10HoldSum=-2.85
- GT180S: N=6 quotes=6 settlement=4/6 releaseAskAvg=0.663 delayAvg=451.9s $10HoldSum=-4.26
- LE9S: N=1 quotes=1 settlement=1/1 releaseAskAvg=0.760 delayAvg=0.5s $10HoldSum=+3.16

## By hard-release provenance

- BOUNDARY_RELEASE: N=3 quotes=3 settlement=3/3 releaseAskAvg=0.673 delayAvg=190.9s $10HoldSum=+15.67
- CREST_RELEASE_CONFIRMED: N=1 quotes=1 settlement=0/1 releaseAskAvg=0.920 delayAvg=653.2s $10HoldSum=-10.00
- FAILED_REGEN_CONFIRMED: N=2 quotes=2 settlement=1/2 releaseAskAvg=0.722 delayAvg=248.2s $10HoldSum=-9.64
- HAND_AUTHORITY_TRANSFER: N=3 quotes=3 settlement=3/3 releaseAskAvg=0.771 delayAvg=227.5s $10HoldSum=+10.02
- WAR_COUNCIL_RELEASE: N=2 quotes=2 settlement=1/2 releaseAskAvg=0.500 delayAvg=287.9s $10HoldSum=-10.00

## By release price

- 40_55C: N=2 quotes=2 settlement=1/2 releaseAskAvg=0.510 delayAvg=235.7s $10HoldSum=-1.48
- 55_70C: N=2 quotes=2 settlement=2/2 releaseAskAvg=0.655 delayAvg=158.4s $10HoldSum=+10.62
- 70_80C: N=2 quotes=2 settlement=2/2 releaseAskAvg=0.775 delayAvg=31.9s $10HoldSum=+5.82
- GE80C: N=4 quotes=4 settlement=3/4 releaseAskAvg=0.954 delayAvg=408.9s $10HoldSum=-8.91
- LT40C: N=1 quotes=1 settlement=0/1 releaseAskAvg=0.001 delayAvg=492.8s $10HoldSum=-10.00

## Discipline

- Hard release is a possible new chapter, not retroactive validation of the stale historical entry.
- A release that arrives with poor economics can still be directionally right and economically untradable.
- A release quote reconstructed from another telemetry tape is accepted only within the stated time window and its source is retained.
- No result here changes V9.5A authority.
