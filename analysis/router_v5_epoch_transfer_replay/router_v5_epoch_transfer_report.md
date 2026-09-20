# Entry Authority Router V5 — Epoch Transfer Replay

Scope: all stale >=9s PULLBACK_WAIT historical entries.

Epoch-reset-capable evidence is intentionally narrow:
- HAND_AUTHORITY_TRANSFER
- directional BOUNDARY_RELEASE

Failed-Regeneration, Crest, and War Council remain evidence, but they are not treated here as sufficient by themselves to reset opportunity ancestry.

Stale pullback cases: 28
Epoch transfers found before contract close: 10
Transfer quotes reconstructed: 10/10

Counterfactual economics: buy the transfer side at the reconstructed ask and hold to settlement with a $10 stake. This does not model fills, fees, Treasury, exits, or management.

## By transfer relation

- NO_TRANSFER: N=18 transfers=0 quotes=0 settlement=0/0 askAvg=NA leftAvg=NA $10HoldSum=+0.00
- OPPOSITE_SIDE_REVERSAL_RESET: N=3 transfers=3 quotes=3 settlement=2/3 askAvg=0.389 leftAvg=516.2s $10HoldSum=+10.36
- SAME_SIDE_CONTINUATION_RESET: N=7 transfers=7 quotes=7 settlement=6/7 askAvg=0.620 leftAvg=299.8s $10HoldSum=+15.69

## By transfer source

- (blank): N=18 transfers=0 quotes=0 settlement=0/0 askAvg=NA leftAvg=NA $10HoldSum=+0.00
- BOUNDARY_RELEASE: N=7 transfers=7 quotes=7 settlement=5/7 askAvg=0.456 leftAvg=348.0s $10HoldSum=+16.03
- HAND_AUTHORITY_TRANSFER: N=3 transfers=3 quotes=3 settlement=3/3 askAvg=0.771 leftAvg=403.8s $10HoldSum=+10.02

## By existing 80c price cap

- 0: N=19 transfers=1 quotes=1 settlement=1/1 askAvg=0.932 leftAvg=225.6s $10HoldSum=+0.73
- 1: N=9 transfers=9 quotes=9 settlement=7/9 askAvg=0.508 leftAvg=380.2s $10HoldSum=+25.32

## By transfer price

- 40_55C: N=1 transfers=1 quotes=1 settlement=1/1 askAvg=0.540 leftAvg=270.8s $10HoldSum=+8.52
- 55_70C: N=2 transfers=2 quotes=2 settlement=2/2 askAvg=0.655 leftAvg=379.7s $10HoldSum=+10.62
- 70_80C: N=3 transfers=3 quotes=3 settlement=3/3 askAvg=0.767 leftAvg=425.7s $10HoldSum=+9.15
- GT80C: N=1 transfers=1 quotes=1 settlement=1/1 askAvg=0.932 leftAvg=225.6s $10HoldSum=+0.73
- LT40C: N=3 transfers=3 quotes=3 settlement=1/3 askAvg=0.141 leftAvg=371.5s $10HoldSum=-2.97
- NO_QUOTE: N=18 transfers=0 quotes=0 settlement=0/0 askAvg=NA leftAvg=NA $10HoldSum=+0.00

## By time remaining

- 180_300S: N=4 transfers=4 quotes=4 settlement=4/4 askAvg=0.738 leftAvg=257.1s $10HoldSum=+16.40
- 60_180S: N=1 transfers=1 quotes=1 settlement=0/1 askAvg=0.006 leftAvg=84.5s $10HoldSum=-10.00
- GE300S: N=5 transfers=5 quotes=5 settlement=4/5 askAvg=0.509 leftAvg=506.9s $10HoldSum=+19.65
- UNKNOWN: N=18 transfers=0 quotes=0 settlement=0/0 askAvg=NA leftAvg=NA $10HoldSum=+0.00

## By transfer delay from stale historical entry

- 30_90S: N=3 transfers=3 quotes=3 settlement=3/3 askAvg=0.617 leftAvg=378.0s $10HoldSum=+24.18
- 90_180S: N=1 transfers=1 quotes=1 settlement=0/1 askAvg=0.047 leftAvg=428.0s $10HoldSum=-10.00
- GT180S: N=5 transfers=5 quotes=5 settlement=4/5 askAvg=0.570 leftAvg=323.4s $10HoldSum=+8.71
- LE9S: N=1 transfers=1 quotes=1 settlement=1/1 askAvg=0.760 leftAvg=468.4s $10HoldSum=+3.16
- NO_TRANSFER: N=18 transfers=0 quotes=0 settlement=0/0 askAvg=NA leftAvg=NA $10HoldSum=+0.00

## Interpretation discipline

- The historical stale signal is not revived. A qualifying transfer starts a candidate new opportunity epoch.
- SAME_SIDE_CONTINUATION_RESET means battlefield authority reasserted the stale side after the old window had expired.
- OPPOSITE_SIDE_REVERSAL_RESET means authority transferred to the opposite side; this is a new reversal chapter, not a flip of the old signal.
- The existing 0.80 max-entry cap is reported because it predates this replay; it is not a post-hoc V5 threshold.
- Small samples remain research evidence only. No V9.5A authority changes.
