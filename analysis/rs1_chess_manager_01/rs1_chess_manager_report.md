# RS1 Chess / Arc Manager Forensics

This pass uses existing completed-arc and Orbital Clock telemetry. It adds no detector and changes no authority.

## Four-way outcome split

- RIGHT_SIDE_WIN: N=15 PnL=$+38.28 arcAligned=11/15 gapSupportExit=5/11 velSupportExit=4/9 microSupportExit=5/10 macroSupportExit=4/5 medianArcProgress=0.362
- RIGHT_SIDE_LOSS: N=12 PnL=$-18.32 arcAligned=7/12 gapSupportExit=1/6 velSupportExit=3/5 microSupportExit=1/5 macroSupportExit=0/3 medianArcProgress=0.731
- WRONG_SIDE_WIN: N=3 PnL=$+1.68 arcAligned=2/3 gapSupportExit=0/1 velSupportExit=1/1 microSupportExit=0/0 macroSupportExit=0/0 medianArcProgress=0.555
- WRONG_SIDE_LOSS: N=10 PnL=$-39.24 arcAligned=8/10 gapSupportExit=2/5 velSupportExit=1/3 microSupportExit=2/4 macroSupportExit=0/0 medianArcProgress=0.587

## Manager question: correct side, losing exit

- Correct-side losing trades: 12
- EMA gap still supported trade side at exit: 1/6
- EMA gap velocity still supported trade side at exit: 3/5
- Micro side still supported trade at exit: 1/5
- Macro side still supported trade at exit: 0/3
- Gap supported trade again 6s after exit: 2/10
- Gap supported trade again 9s after exit: 1/7
- Exit occurred before proposal arc completed: 9/12

### Correct-side losers by exit reason

- V95A_ACTIVE_TREASURY_DEFEND: N=5 PnL=$-4.23 arcAligned=3/5 gapSupportExit=1/4 velSupportExit=3/3 microSupportExit=1/3 macroSupportExit=0/1 medianArcProgress=0.728
- EMA9_ARC_BROKEN: N=4 PnL=$-6.97 arcAligned=1/4 gapSupportExit=0/0 velSupportExit=0/0 microSupportExit=0/0 macroSupportExit=0/0 medianArcProgress=0.874
- ANTICIPATION_FAST_FAIL: N=3 PnL=$-7.12 arcAligned=3/3 gapSupportExit=0/2 velSupportExit=0/2 microSupportExit=0/2 macroSupportExit=0/2 medianArcProgress=0.642

## Comparison: genuinely wrong-side losing trades

- Wrong-side losing trades: 10
- EMA gap still supported chosen trade side at exit: 2/5
- EMA gap velocity still supported chosen trade side at exit: 1/3
- Micro side still supported chosen trade at exit: 2/4
- Macro side still supported chosen trade at exit: 0/0
- Gap supported chosen side again 6s after exit: 3/8
- Gap supported chosen side again 9s after exit: 2/6
- Exit occurred before proposal arc completed: 5/10

## Existing little-mountain proxy at entry

- RIGHT_SIDE_WIN: seq=1:1, 2:5, 3:3, 4+:6 | crest=HIGHER:6, LOWER:5, EQUAL:3, NONE:1
- RIGHT_SIDE_LOSS: seq=1:2, 2:5, 3:1, 4+:4 | crest=LOWER:7, HIGHER:3, NONE:2
- WRONG_SIDE_WIN: seq=2:2, 4+:1 | crest=HIGHER:2, LOWER:1
- WRONG_SIDE_LOSS: seq=1:1, 2:2, 3:1, 4+:6 | crest=LOWER:6, HIGHER:3, NONE:1

## Twelve correct-side losers

- #2 KXBTC15M-26SEP200315-15 YES @0.75 exit=ANTICIPATION_FAST_FAIL pnl=$-1.40 arc=A00005 dir=UP seq=2 crest=LOWER progress=0.4017021432695334 gapExit=0 velExit=0 microExit=0 macroExit=0 gap6= gap9=0 beforeArcEnd=1
- #3 KXBTC15M-26SEP200315-15 YES @0.8 exit=ANTICIPATION_FAST_FAIL pnl=$-3.96 arc=A00005 dir=UP seq=2 crest=LOWER progress=0.910544946139674 gapExit=0 velExit=0 microExit=0 macroExit=0 gap6=0 gap9=0 beforeArcEnd=1
- #11 KXBTC15M-26SEP200430-30 NO @0.6699999999999999 exit=ANTICIPATION_FAST_FAIL pnl=$-1.76 arc=A00022 dir=DOWN seq=1 crest=NONE progress=0.642239657851984 gapExit= velExit= microExit= macroExit= gap6=0 gap9= beforeArcEnd=1
- #12 KXBTC15M-26SEP200430-30 NO @0.54 exit=EMA9_ARC_BROKEN pnl=$-0.72 arc=A00022 dir=DOWN seq=1 crest=NONE progress=0.9740519740066633 gapExit= velExit= microExit= macroExit= gap6=0 gap9= beforeArcEnd=0
- #15 KXBTC15M-26SEP200500-00 YES @0.65 exit=EMA9_ARC_BROKEN pnl=$-2.25 arc=A00024 dir=DOWN seq=2 crest=LOWER progress=0.7767927281946553 gapExit= velExit= microExit= macroExit= gap6=0 gap9= beforeArcEnd=1
- #20 KXBTC15M-26SEP200630-30 YES @0.72 exit=EMA9_ARC_BROKEN pnl=$-0.60 arc=A00038 dir=DOWN seq=3 crest=LOWER progress=0.9713971535541002 gapExit= velExit= microExit= macroExit= gap6=0 gap9= beforeArcEnd=0
- #21 KXBTC15M-26SEP200645-45 NO @0.4 exit=V95A_ACTIVE_TREASURY_DEFEND pnl=$-1.92 arc=A00041 dir=UP seq=2 crest=LOWER progress=0.7283846560332052 gapExit=1 velExit=1 microExit=1 macroExit= gap6=1 gap9=1 beforeArcEnd=0
- #26 KXBTC15M-26SEP200700-00 NO @0.41000000000000003 exit=V95A_ACTIVE_TREASURY_DEFEND pnl=$-1.20 arc=A00047 dir=UP seq=5 crest=HIGHER progress=0.8776170076865019 gapExit= velExit= microExit= macroExit= gap6=1 gap9= beforeArcEnd=1
- #28 KXBTC15M-26SEP200715-15 YES @0.58 exit=EMA9_ARC_BROKEN pnl=$-3.40 arc=A00048 dir=DOWN seq=5 crest=LOWER progress=0.5753140936205643 gapExit= velExit= microExit= macroExit= gap6=0 gap9=0 beforeArcEnd=1
- #33 KXBTC15M-26SEP200815-15 NO @0.64 exit=V95A_ACTIVE_TREASURY_DEFEND pnl=$-0.60 arc=A00060 dir=DOWN seq=10 crest=HIGHER progress=0.7339317879123902 gapExit=0 velExit=1 microExit= macroExit= gap6= gap9=0 beforeArcEnd=1
- #34 KXBTC15M-26SEP200830-30 NO @0.42 exit=V95A_ACTIVE_TREASURY_DEFEND pnl=$-0.35 arc=A00064 dir=DOWN seq=11 crest=LOWER progress=0.09909145794330551 gapExit=0 velExit=1 microExit=0 macroExit=0 gap6=0 gap9=0 beforeArcEnd=1
- #38 KXBTC15M-26SEP200945-45 YES @0.62 exit=V95A_ACTIVE_TREASURY_DEFEND pnl=$-0.16 arc=A00075 dir=UP seq=2 crest=HIGHER progress=0.07598406615928059 gapExit=0 velExit= microExit=0 macroExit= gap6=0 gap9=0 beforeArcEnd=1

## Watched compression contract KXBTC15M-26SEP200315-15

- #1 NO outcome=WRONG_SIDE_LOSS arc=A00004 arcDir=DOWN seq=2 crest=LOWER arcProgress=0.7528432546305225 exit=EMERGENCY_STOP_60 gapExit= velExit= microExit= macroExit=
- #2 YES outcome=RIGHT_SIDE_LOSS arc=A00005 arcDir=UP seq=2 crest=LOWER arcProgress=0.4017021432695334 exit=ANTICIPATION_FAST_FAIL gapExit=0 velExit=0 microExit=0 macroExit=0
- #3 YES outcome=RIGHT_SIDE_LOSS arc=A00005 arcDir=UP seq=2 crest=LOWER arcProgress=0.910544946139674 exit=ANTICIPATION_FAST_FAIL gapExit=0 velExit=0 microExit=0 macroExit=0
- #4 YES outcome=RIGHT_SIDE_WIN arc=A00007 arcDir=UP seq=3 crest=HIGHER arcProgress=0.3336224034234499 exit=CORE_LATE_TP_22_5 gapExit=0 velExit=1 microExit=0 macroExit=0

## Discipline

- Sequence count and crest progression are existing telemetry, used as the machine proxy for the little mountains.
- Gap/velocity/micro/macro support are descriptive joins from the existing Orbital Clock; no new threshold is introduced.
- The +6s and +9s samples are post-exit diagnostics only, not proposed hold rules.
- Settlement correctness is not the same thing as trade quality; profitable wrong-side exits are preserved as their own class.
- The target question is whether current managers can distinguish ordinary snake counter-motion from a genuine structural escape.
