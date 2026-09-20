# RS1 Battlefield Persistence / Reacquisition Forensics

This pass asks whether a losing position ended while the same contract-side thesis later reappeared. It uses only existing RS1 router, paper-trade, and EMA-arc telemetry. No detector or authority change is introduced.

## Correct-side losing exits

- Trades: 12
- Same-side directional recognition after exit: 12/12
- Same-side legacy proposal after exit: 9/12
- Same-side proposal was cheaper than original entry: 3/9
- Same-side proposal arrived on a new arc: 6/9
- Same-side paper re-entry occurred: 6/12
- Same-side re-entry was cheaper than original entry: 2/6
- Median delay to same-side recognition: 92.8s
- Median delay to same-side proposal: 120.6s
- Median same-side proposal price improvement: -10.0c
- First post-exit proposal relation: SAME=8, OPPOSITE=2, NONE=2

## Wrong-side losing exits

- Trades: 10
- Same-side directional recognition after exit: 6/10
- Same-side legacy proposal after exit: 3/10
- Same-side proposal was cheaper than original entry: 0/3
- Same-side proposal arrived on a new arc: 2/3
- Same-side paper re-entry occurred: 3/10
- Same-side re-entry was cheaper than original entry: 0/3
- Median delay to same-side recognition: 141.6s
- Median delay to same-side proposal: 130.4s
- Median same-side proposal price improvement: -7.0c
- First post-exit proposal relation: OPPOSITE=3, SAME=3, NONE=4

## Correct-side losing exit detail

- #2 KXBTC15M-26SEP200315-15 YES exit=ANTICIPATION_FAST_FAIL sameRec=1 recDelay=126.62098503112793 sameProp=1 propDelay=120.87296891212463 propAsk=0.8 improve=-5.000000000000004c newArc=0 seq=2 crest=LOWER firstProp=SAME reentry=1 reentryDelay=120.0 reentryAsk=0.8
- #3 KXBTC15M-26SEP200315-15 YES exit=ANTICIPATION_FAST_FAIL sameRec=1 recDelay=115.56269907951355 sameProp=1 propDelay=105.29912209510803 propAsk=0.77 improve=3.0000000000000027c newArc=1 seq=3 crest=HIGHER firstProp=SAME reentry=1 reentryDelay=105.0 reentryAsk=0.77
- #11 KXBTC15M-26SEP200430-30 NO exit=ANTICIPATION_FAST_FAIL sameRec=1 recDelay=93.79287791252136 sameProp=1 propDelay=88.43723893165588 propAsk=0.54 improve=12.99999999999999c newArc=0 seq=1 crest=NONE firstProp=SAME reentry=1 reentryDelay=88.0 reentryAsk=0.54
- #12 KXBTC15M-26SEP200430-30 NO exit=EMA9_ARC_BROKEN sameRec=1 recDelay=91.87748789787292 sameProp=1 propDelay=86.82582402229309 propAsk=0.64 improve=-9.999999999999998c newArc=1 seq=2 crest=LOWER firstProp=SAME reentry=1 reentryDelay=86.0 reentryAsk=0.64
- #15 KXBTC15M-26SEP200500-00 YES exit=EMA9_ARC_BROKEN sameRec=1 recDelay=353.8897180557251 sameProp=1 propDelay=511.2235629558563 propAsk=0.61 improve=4.0000000000000036c newArc=1 seq=1 crest=NONE firstProp=SAME reentry=0 reentryDelay=None reentryAsk=
- #20 KXBTC15M-26SEP200630-30 YES exit=EMA9_ARC_BROKEN sameRec=1 recDelay=66.64372992515564 sameProp=0 propDelay=None propAsk= improve=Nonec newArc= seq= crest= firstProp=OPPOSITE reentry=0 reentryDelay=None reentryAsk=
- #21 KXBTC15M-26SEP200645-45 NO exit=V95A_ACTIVE_TREASURY_DEFEND sameRec=1 recDelay=55.39778995513916 sameProp=1 propDelay=299.33921098709106 propAsk=0.78 improve=-38.0c newArc=1 seq=3 crest=LOWER firstProp=SAME reentry=1 reentryDelay=448.0 reentryAsk=0.69
- #26 KXBTC15M-26SEP200700-00 NO exit=V95A_ACTIVE_TREASURY_DEFEND sameRec=1 recDelay=7.263902902603149 sameProp=1 propDelay=71.12134099006653 propAsk=0.79 improve=-38.0c newArc=1 seq=5 crest=LOWER firstProp=SAME reentry=1 reentryDelay=71.0 reentryAsk=0.79
- #28 KXBTC15M-26SEP200715-15 YES exit=EMA9_ARC_BROKEN sameRec=1 recDelay=135.81949591636658 sameProp=1 propDelay=239.82988810539246 propAsk=0.75 improve=-17.000000000000004c newArc=1 seq=6 crest=LOWER firstProp=OPPOSITE reentry=0 reentryDelay=None reentryAsk=
- #33 KXBTC15M-26SEP200815-15 NO exit=V95A_ACTIVE_TREASURY_DEFEND sameRec=1 recDelay=608.6236228942871 sameProp=0 propDelay=None propAsk= improve=Nonec newArc= seq= crest= firstProp= reentry=0 reentryDelay=None reentryAsk=
- #34 KXBTC15M-26SEP200830-30 NO exit=V95A_ACTIVE_TREASURY_DEFEND sameRec=1 recDelay=0.8356719017028809 sameProp=1 propDelay=120.55346298217773 propAsk=0.56 improve=-14.000000000000007c newArc=0 seq=11 crest=LOWER firstProp=SAME reentry=0 reentryDelay=None reentryAsk=
- #38 KXBTC15M-26SEP200945-45 YES exit=V95A_ACTIVE_TREASURY_DEFEND sameRec=1 recDelay=40.97571611404419 sameProp=0 propDelay=None propAsk= improve=Nonec newArc= seq= crest= firstProp= reentry=0 reentryDelay=None reentryAsk=

## Wrong-side losing exit detail

- #1 KXBTC15M-26SEP200315-15 NO exit=EMERGENCY_STOP_60 sameRec=1 recDelay=65.3914520740509 sameProp=0 propDelay=None propAsk= improve=Nonec newArc= seq= crest= firstProp=OPPOSITE reentry=0 reentryDelay=None reentryAsk=
- #5 KXBTC15M-26SEP200330-30 NO exit=V95A_ACTIVE_TREASURY_DEFEND sameRec=0 recDelay=None sameProp=0 propDelay=None propAsk= improve=Nonec newArc= seq= crest= firstProp=OPPOSITE reentry=0 reentryDelay=None reentryAsk=
- #7 KXBTC15M-26SEP200400-00 YES exit=V92_STRUCTURE_BROKEN sameRec=1 recDelay=135.86383390426636 sameProp=1 propDelay=130.36080598831177 propAsk=0.56 improve=-11.000000000000004c newArc=1 seq=5 crest=LOWER firstProp=SAME reentry=1 reentryDelay=130.0 reentryAsk=0.56
- #8 KXBTC15M-26SEP200400-00 YES exit=V92_STRUCTURE_BROKEN sameRec=1 recDelay=198.82862210273743 sameProp=0 propDelay=None propAsk= improve=Nonec newArc= seq= crest= firstProp= reentry=0 reentryDelay=None reentryAsk=
- #17 KXBTC15M-26SEP200515-15 NO exit=EMERGENCY_STOP_60 sameRec=1 recDelay=147.3522069454193 sameProp=0 propDelay=None propAsk= improve=Nonec newArc= seq= crest= firstProp= reentry=0 reentryDelay=None reentryAsk=
- #18 KXBTC15M-26SEP200530-30 NO exit=EMERGENCY_STOP_60 sameRec=0 recDelay=None sameProp=0 propDelay=None propAsk= improve=Nonec newArc= seq= crest= firstProp= reentry=0 reentryDelay=None reentryAsk=
- #23 KXBTC15M-26SEP200700-00 YES exit=V92_STRUCTURE_BROKEN sameRec=1 recDelay=232.5754849910736 sameProp=1 propDelay=256.1197910308838 propAsk=0.54 improve=-7.000000000000006c newArc=1 seq=5 crest=HIGHER firstProp=SAME reentry=1 reentryDelay=256.0 reentryAsk=0.54
- #24 KXBTC15M-26SEP200700-00 YES exit=EMA9_ARC_BROKEN sameRec=1 recDelay=90.12302803993225 sameProp=1 propDelay=33.1395959854126 propAsk=0.54 improve=0.0c newArc=0 seq=5 crest=HIGHER firstProp=SAME reentry=1 reentryDelay=33.0 reentryAsk=0.54
- #29 KXBTC15M-26SEP200715-15 NO exit=EMERGENCY_STOP_60 sameRec=0 recDelay=None sameProp=0 propDelay=None propAsk= improve=Nonec newArc= seq= crest= firstProp=OPPOSITE reentry=0 reentryDelay=None reentryAsk=
- #35 KXBTC15M-26SEP200845-45 YES exit=LATE_TARGET_INVALIDATION sameRec=0 recDelay=None sameProp=0 propDelay=None propAsk= improve=Nonec newArc= seq= crest= firstProp= reentry=0 reentryDelay=None reentryAsk=

## Discipline

- A later same-side proposal is evidence that the proposal engine revisited the thesis; it is not proof the earlier exit was wrong.
- Cheaper reappearance is a value-reset diagnostic, not a re-entry rule.
- Wrong-side losing trades are kept as the control group so battlefield persistence cannot be mistaken for edge by itself.
- Same-contract persistence is tested first. Rollover continuity remains a separate parent-formation question.
- The architecture question is whether Tachys should preserve thesis memory after a position dies, then require fresh structure and value before any reacquisition.
