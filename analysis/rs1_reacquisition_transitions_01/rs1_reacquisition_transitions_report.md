# RS1 Reacquisition Transition Forensics

This pass studies only actual same-side re-entries after a losing exit. It is transition-level evidence, not a new entry rule or authority change.

## Actual same-side re-entry transitions

- ALL: N=9 reentryWins=5/9 reentryPnL=$+5.32 settlementCorrect=6/9 cheaper=2/9 medianDelay=105.0s
- RIGHT_SIDE_LOSS parent: N=6 reentryWins=4/6 reentryPnL=$+6.89 settlementCorrect=6/6 cheaper=2/6 medianDelay=96.5s
- WRONG_SIDE_LOSS parent: N=3 reentryWins=1/3 reentryPnL=$-1.57 settlementCorrect=0/3 cheaper=0/3 medianDelay=130.0s

## Parent correctness x arc reset

- Correct-side parent -> NEW arc: N=4 reentryWins=4/4 reentryPnL=$+11.57 settlementCorrect=4/4 cheaper=1/4 medianDelay=95.5s
- Correct-side parent -> SAME arc: N=2 reentryWins=0/2 reentryPnL=$-4.68 settlementCorrect=2/2 cheaper=1/2 medianDelay=104.0s
- Wrong-side parent -> NEW arc: N=2 reentryWins=0/2 reentryPnL=$-1.75 settlementCorrect=0/2 cheaper=0/2 medianDelay=193.0s
- Wrong-side parent -> SAME arc: N=1 reentryWins=1/1 reentryPnL=$+0.18 settlementCorrect=0/1 cheaper=0/1 medianDelay=33.0s

## Transition detail

- #2 -> #3 RIGHT_SIDE_LOSS YES newArc=0 seq=2 crest=LOWER ask 0.75 -> 0.8 cheaper=0 delay=120.0s reentryPnL=$-3.96 reentrySettlementCorrect=1 exit=ANTICIPATION_FAST_FAIL
- #3 -> #4 RIGHT_SIDE_LOSS YES newArc=1 seq=3 crest=HIGHER ask 0.8 -> 0.77 cheaper=1 delay=105.0s reentryPnL=$+3.57 reentrySettlementCorrect=1 exit=CORE_LATE_TP_22_5
- #7 -> #8 WRONG_SIDE_LOSS YES newArc=1 seq=5 crest=LOWER ask 0.45 -> 0.56 cheaper=0 delay=130.0s reentryPnL=$-0.85 reentrySettlementCorrect=0 exit=V92_STRUCTURE_BROKEN
- #11 -> #12 RIGHT_SIDE_LOSS NO newArc=0 seq=1 crest=NONE ask 0.6699999999999999 -> 0.54 cheaper=1 delay=88.0s reentryPnL=$-0.72 reentrySettlementCorrect=1 exit=EMA9_ARC_BROKEN
- #12 -> #13 RIGHT_SIDE_LOSS NO newArc=1 seq=2 crest=LOWER ask 0.54 -> 0.64 cheaper=0 delay=86.0s reentryPnL=$+3.68 reentrySettlementCorrect=1 exit=CORE_SWIRL_SNIP_TP_22_5
- #21 -> #22 RIGHT_SIDE_LOSS NO newArc=1 seq=3 crest=LOWER ask 0.4 -> 0.69 cheaper=0 delay=448.0s reentryPnL=$+0.56 reentrySettlementCorrect=1 exit=V95A_ACTIVE_TREASURY_DEFEND
- #23 -> #24 WRONG_SIDE_LOSS YES newArc=1 seq=5 crest=HIGHER ask 0.47 -> 0.54 cheaper=0 delay=256.0s reentryPnL=$-0.90 reentrySettlementCorrect=0 exit=EMA9_ARC_BROKEN
- #24 -> #25 WRONG_SIDE_LOSS YES newArc=0 seq=5 crest=HIGHER ask 0.54 -> 0.54 cheaper=0 delay=33.0s reentryPnL=$+0.18 reentrySettlementCorrect=0 exit=V95A_ACTIVE_TREASURY_DEFEND
- #26 -> #27 RIGHT_SIDE_LOSS NO newArc=1 seq=5 crest=LOWER ask 0.41000000000000003 -> 0.79 cheaper=0 delay=71.0s reentryPnL=$+3.76 reentrySettlementCorrect=1 exit=CONTRACT_CLOSE

## Interpretation discipline

- A new arc is tested as structural regeneration after a dead position; it is not assumed to prove direction.
- Parent settlement correctness is known only after the contract settles and therefore cannot be used prospectively as a feature.
- This tiny RS1 transition set is useful for architecture design, not threshold fitting.
- Same-arc retry versus new-arc regeneration is deliberately separated because the watched contract showed both behaviors.
- Price improvement is descriptive only. A structurally regenerated opportunity may reappear at a worse price, and a cheaper retry may still be bad.
- Any future implementation should remain shadow-only first and should preserve V9.5A trading authority.
