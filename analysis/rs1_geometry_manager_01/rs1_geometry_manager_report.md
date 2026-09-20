# RS1 Geometry + Manager Forensics

This pass tests the user's PT/EMA/price encounter idea using existing telemetry only. No new detector and no authority change.

## Direction vs management

- RS1 trades: 40
- Correct settlement side but realized loss: 12
- Aggregate counterfactual improvement if those individual trades had instead been held to settlement: $+120.79

### Correct-side losing trades by exit reason

- V95A_ACTIVE_TREASURY_DEFEND: N=5 PnL=$-4.23 settlement=5/5 correct-side-losers=5 leakageVsHold=$+64.57
- EMA9_ARC_BROKEN: N=4 PnL=$-6.97 settlement=4/4 correct-side-losers=4 leakageVsHold=$+33.24
- ANTICIPATION_FAST_FAIL: N=3 PnL=$-7.12 settlement=3/3 correct-side-losers=3 leakageVsHold=$+22.98

## PT-EMA-price geometry at entry

Normalized span tercile cut points: tight <= 0.749, middle <= 1.344, widest > 1.344

- TIGHTEST_THIRD: N=14 PnL=$-5.62 settlement=9/14 correct-side-losers=5 leakageVsHold=$+69.07
- MIDDLE_THIRD: N=13 PnL=$-19.27 settlement=7/13 correct-side-losers=3 leakageVsHold=$+20.14
- WIDEST_THIRD: N=13 PnL=$+7.29 settlement=11/13 correct-side-losers=4 leakageVsHold=$+31.58

### Exact EMA-band relationships

- target_inside_ema_band=1: N=10 PnL=$-17.11 settlement=5/10 correct-side-losers=1 leakageVsHold=$+20.65
- target_inside_ema_band=0: N=30 PnL=$-0.49 settlement=22/30 correct-side-losers=11 leakageVsHold=$+100.14
- price_inside_ema_band=1: N=15 PnL=$+0.10 settlement=11/15 correct-side-losers=5 leakageVsHold=$+51.11
- price_inside_ema_band=0: N=25 PnL=$-17.71 settlement=16/25 correct-side-losers=7 leakageVsHold=$+69.68

## Swirl/compression manager check

- battlefield:COMPRESSION_STORM: N=13 PnL=$+2.52 settlement=7/13 correct-side-losers=3 leakageVsHold=$+30.78
- churn:COMPRESSION_CHURN: N=13 PnL=$+3.32 settlement=7/13 correct-side-losers=3 leakageVsHold=$+30.58
- dragon:DRAGONS_SWIRLING: N=13 PnL=$-3.50 settlement=10/13 correct-side-losers=6 leakageVsHold=$+60.37
- dragon:DRAGONS_ENTANGLED: N=16 PnL=$-8.33 settlement=9/16 correct-side-losers=3 leakageVsHold=$+37.92

## Watched contract KXBTC15M-26SEP200315-15

- #1 NO @0.6 actual=$-9.50 settle=YES hold=$-15.00 span=63.062809386319714 norm60=1.2841134063595798 EMA-gap=44.773676261655055 PT-center=6.1159712554945145 battle=QUIET_TERRITORY churn=NONE dragon=DRAGONS_UNCLEAR exit=EMERGENCY_STOP_60
- #2 YES @0.75 actual=$-1.40 settle=YES hold=$+5.00 span=29.847209020663286 norm60=1.1216538527118614 EMA-gap=27.111683820869075 PT-center=16.291367110228748 battle=COMPRESSION_STORM churn=MIXED_CHURN dragon=DRAGONS_SWIRLING exit=ANTICIPATION_FAST_FAIL
- #3 YES @0.8 actual=$-3.96 settle=YES hold=$+3.60 span=26.30444778362289 norm60=1.6916043590751104 EMA-gap=22.711711655763793 PT-center=14.94859195574827 battle=CLEAN_TERRITORY churn=NONE dragon=DRAGONS_SWIRLING exit=ANTICIPATION_FAST_FAIL
- #4 YES @0.77 actual=$+3.57 settle=YES hold=$+4.37 span=22.41462191424216 norm60=1.48835470878125 EMA-gap=22.41462191424216 PT-center=10.21370207896689 battle=MIXED_STORM churn=MIXED_CHURN dragon=DRAGONS_UNCLEAR exit=CORE_LATE_TP_22_5

## Rollover continuity

- ROLLOVER_REMAP events in RS1 window: 29
- New PT landed inside EMA9/EMA30 band: 8/29

- CONTINUES: 20
- TRANSFORMED_SAME_PARENT: 6
- FAMILY_CONTINUES: 3

## Existing mountain/arc telemetry

- Completed EMA arcs in RS1 window: 67
- sequence_count 1: 18
- sequence_count 2: 13
- sequence_count 3: 8
- sequence_count 4+: 28

Crest progression:
- HIGHER: 22
- NONE: 18
- LOWER: 18
- EQUAL: 9

## Discipline

- Geometry terciles are descriptive rank buckets, not proposed thresholds.
- Hold-to-settlement is a manager diagnostic, not a recommendation to hold every trade.
- Rollover preserves the underlying BTC/EMA formation; this report treats the new PT as a remap, not a reset.
- Existing arc sequence_count / crest_progression telemetry is used as the first machine proxy for the 'little mountains'; no separate mountain detector is introduced here.
