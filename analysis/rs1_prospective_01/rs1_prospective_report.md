# RS1 Prospective Entry-Authority Run — First Forensic Pass

Run folder: runs\2026-09-20_v9_5a_rs1_entry_authority_router_shadow_01

## Run headline

- RS1 event rows: 603
- RS1 prospective window: 2026-09-20T06:59:25.911868+00:00 -> 2026-09-20T14:14:57.944597+00:00
- Archived pre-RS1 paper entries excluded as carryover: 41
- Paper entries inside RS1 window: 40
- Matched to RS1 legacy proposals: 40/40
- Realized paper P&L: $-17.60
- Paper wins/losses: 18/22
- Settled contracts recorded: 57

## RS1 event counts

- FIRST_DIRECTIONAL_SHADOW: 198
- LEGACY_PROPOSAL_SHADOW: 187
- TRANSFER_ACCEPTED_SHADOW: 14
- TRANSFER_ARMED_SHADOW: 23
- WINDOW_EXPIRED_SHADOW: 181

## Opportunity age at actual paper entries

- Young (<9s research clock): N=19 actualPnL=$-16.77
- Expired (>=9s research clock): N=21 actualPnL=$-0.83

## Paper entries by battlefield class

- CLEAN_TERRITORY: N=4 actualPnL=$-7.46 wins=1/4 settlement=3/4
- COMPRESSION_STORM: N=13 actualPnL=$+2.52 wins=7/13 settlement=7/13
- LOCAL_FOG: N=2 actualPnL=$-7.68 wins=0/2 settlement=1/2
- METRONOME_STORM: N=2 actualPnL=$+6.77 wins=2/2 settlement=2/2
- MIXED_STORM: N=15 actualPnL=$+7.42 wins=8/15 settlement=13/15
- QUIET_TERRITORY: N=3 actualPnL=$-19.01 wins=0/3 settlement=1/3
- TRANSITION_RELEASE: N=1 actualPnL=$-0.16 wins=0/1 settlement=0/1

## Paper entries by churn type

- COMPRESSION_CHURN: N=13 actualPnL=$+3.32 wins=7/13 settlement=7/13
- METRONOME_CHURN: N=3 actualPnL=$+6.42 wins=2/3 settlement=3/3
- MIXED_CHURN: N=15 actualPnL=$+6.81 wins=8/15 settlement=12/15
- NONE: N=9 actualPnL=$-34.15 wins=1/9 settlement=5/9

## Paper entries by dragon state

- DRAGONS_ENTANGLED: N=16 actualPnL=$-8.33 wins=8/16 settlement=9/16
- DRAGONS_SEPARATED: N=2 actualPnL=$+0.47 wins=1/2 settlement=2/2
- DRAGONS_SWIRLING: N=13 actualPnL=$-3.50 wins=5/13 settlement=10/13
- DRAGONS_UNCLEAR: N=9 actualPnL=$-6.24 wins=4/9 settlement=6/9

## Prospective structural transfers

- TRANSFER_ARMED: 23
- Transfer side later/at-once accepted in existing 20c–80c band: 14/23
- Transfer epoch later received a legacy proposal: 6/23
- Accepted transfer epoch later received a legacy proposal: 6/14
- Raw transfer-side settlement correctness: 11/23
- Accepted transfer-side settlement correctness: 5/14

### By transfer source

- BOUNDARY_RELEASE: N=13 accepted=10 proposals=4 settlement=3/13
- HAND_AUTHORITY_TRANSFER: N=10 accepted=4 proposals=2 settlement=8/10

## Observed compression contract: KXBTC15M-26SEP200315-15

- Trade #1 NO @ 0.6 actual=$-9.50 exit=EMERGENCY_STOP_60 MFE=0.0 MAE=-63.33333333333333 battlefield=QUIET_TERRITORY churn=NONE dragon=DRAGONS_UNCLEAR age=0.015 expired9=0 settle=YES holdToSettle=-15.0
- Trade #2 YES @ 0.75 actual=$-1.40 exit=ANTICIPATION_FAST_FAIL MFE=6.666666666666667 MAE=-9.333333333333323 battlefield=COMPRESSION_STORM churn=MIXED_CHURN dragon=DRAGONS_SWIRLING age=55.91 expired9=1 settle=YES holdToSettle=5.0
- Trade #3 YES @ 0.8 actual=$-3.96 exit=ANTICIPATION_FAST_FAIL MFE=0.0 MAE=-27.500000000000007 battlefield=CLEAN_TERRITORY churn=NONE dragon=DRAGONS_SWIRLING age=149.46 expired9=1 settle=YES holdToSettle=3.6
- Trade #4 YES @ 0.77 actual=$+3.57 exit=CORE_LATE_TP_22_5 MFE=24.415584415584394 MAE=0.0 battlefield=MIXED_STORM churn=MIXED_CHURN dragon=DRAGONS_UNCLEAR age=112.693 expired9=1 settle=YES holdToSettle=4.37

## Interpretation discipline

- RS1 was prospective and shadow-only; V9.5A paper authority remained unchanged.
- The 9-second boundary is still a research clock, not promoted authority.
- Transfer and 20c–80c acceptance are context, not an entry rule.
- Settlement-hold counterfactuals ignore Treasury, fills, fees, and active management.
- The next pass should specifically test the observed PT/EMA/price compression -> snake -> mountain/leg sequence, including rollover continuity, without inventing a new detector before existing telemetry is exhausted.
