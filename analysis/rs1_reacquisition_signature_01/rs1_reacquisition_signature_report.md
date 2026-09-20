# RS1 Reacquisition Signature Forensics

This pass compares contemporaneous features at the moment a same-side proposal reappeared after a losing exit. Settlement correctness is used only as an outcome label and is not available prospectively.

- Same-side post-exit proposals matched: 12
- New-arc proposals: 8
- New-arc outcome labels: eventually-correct thesis=6 eventually-wrong thesis=2

## New-arc contemporaneous comparison

- Eventually-correct thesis: N=6 askMedian=0.76 arcAgeMedian=164.7s secondsLeftMedian=253.8s
- Eventually-wrong thesis: N=2 askMedian=0.55 arcAgeMedian=155.7s secondsLeftMedian=536.3s
- Arc direction aligned: correct 6/6 | wrong 2/2
- Target already supports side: correct 5/6 | wrong 0/2
- Hand aligned: correct 2/6 | wrong 0/2
- Boss aligned: correct 3/6 | wrong 0/2
- EMA gap supports side: correct 1/4 | wrong 0/2
- EMA gap velocity supports side: correct 2/3 | wrong 0/0
- Orbital micro side aligned: correct 1/4 | wrong 0/1
- Orbital macro side aligned: correct 0/3 | wrong 0/1

### Existing categorical telemetry

- Crest progression, correct: LOWER=4, HIGHER=1, NONE=1
- Crest progression, wrong: LOWER=1, HIGHER=1
- Sequence count, correct: 3=2, 2=1, 1=1, 5=1, 6=1
- Sequence count, wrong: 5=2
- Battlefield, correct: MIXED_STORM=2, COMPRESSION_STORM=2, CLEAN_TERRITORY=1, LOCAL_FOG=1
- Battlefield, wrong: COMPRESSION_STORM=1, MIXED_STORM=1
- Churn, correct: MIXED_CHURN=2, COMPRESSION_CHURN=2, NONE=2
- Churn, wrong: COMPRESSION_CHURN=1, MIXED_CHURN=1
- Dragon, correct: DRAGONS_UNCLEAR=2, DRAGONS_SWIRLING=2, DRAGONS_ENTANGLED=2
- Dragon, wrong: DRAGONS_ENTANGLED=1, DRAGONS_SWIRLING=1
- Price arc phase, correct: PEAK_TROUGH_BUILD=4, RETURN_TO_EMA9=2
- Price arc phase, wrong: PEAK_TROUGH_BUILD=1, EXTENSION_SLOW=1

## New-arc proposal detail

- parent #3 YES labelCorrect=1 ask=0.77 arc=A00007 dir=UP seq=3 crest=HIGHER phase=PEAK_TROUGH_BUILD battle=MIXED_STORM churn=MIXED_CHURN dragon=DRAGONS_UNCLEAR targetSupport=1 handAligned=0 bossAligned=0 gapSupport=0 velSupport=1 microAligned=0 macroAligned=0 arcAge=89.64433979988098s left=87.80135321617126s
- parent #7 YES labelCorrect=0 ask=0.56 arc=A00015 dir=UP seq=5 crest=LOWER phase=PEAK_TROUGH_BUILD battle=COMPRESSION_STORM churn=COMPRESSION_CHURN dragon=DRAGONS_ENTANGLED targetSupport=0 handAligned=0 bossAligned=0 gapSupport=0 velSupport= microAligned= macroAligned= arcAge=80.71053171157837s left=463.67156624794006s
- parent #12 NO labelCorrect=1 ask=0.64 arc=A00024 dir=DOWN seq=2 crest=LOWER phase=RETURN_TO_EMA9 battle=COMPRESSION_STORM churn=COMPRESSION_CHURN dragon=DRAGONS_UNCLEAR targetSupport=1 handAligned=0 bossAligned=1 gapSupport=0 velSupport=0 microAligned=0 macroAligned=0 arcAge=84.28912901878357s left=515.1981194019318s
- parent #15 YES labelCorrect=1 ask=0.61 arc=A00025 dir=UP seq=1 crest=NONE phase=PEAK_TROUGH_BUILD battle=CLEAN_TERRITORY churn=NONE dragon=DRAGONS_SWIRLING targetSupport=0 handAligned=0 bossAligned=0 gapSupport= velSupport= microAligned= macroAligned= arcAge=172.41289591789246s left=271.8971381187439s
- parent #21 NO labelCorrect=1 ask=0.78 arc=A00044 dir=DOWN seq=3 crest=LOWER phase=RETURN_TO_EMA9 battle=LOCAL_FOG churn=NONE dragon=DRAGONS_SWIRLING targetSupport=1 handAligned=1 bossAligned=1 gapSupport= velSupport= microAligned= macroAligned= arcAge=357.91325092315674s left=235.69056916236877s
- parent #23 YES labelCorrect=0 ask=0.54 arc=A00047 dir=UP seq=5 crest=HIGHER phase=EXTENSION_SLOW battle=MIXED_STORM churn=MIXED_CHURN dragon=DRAGONS_SWIRLING targetSupport=0 handAligned=0 bossAligned=0 gapSupport=0 velSupport= microAligned=0 macroAligned=0 arcAge=230.62599205970764s left=608.9305055141449s
- parent #26 NO labelCorrect=1 ask=0.79 arc=A00048 dir=DOWN seq=5 crest=LOWER phase=PEAK_TROUGH_BUILD battle=MIXED_STORM churn=MIXED_CHURN dragon=DRAGONS_ENTANGLED targetSupport=1 handAligned=1 bossAligned=1 gapSupport=1 velSupport= microAligned=1 macroAligned= arcAge=156.9978425502777s left=198.946462392807s
- parent #28 YES labelCorrect=1 ask=0.75 arc=A00049 dir=UP seq=6 crest=LOWER phase=PEAK_TROUGH_BUILD battle=COMPRESSION_STORM churn=COMPRESSION_CHURN dragon=DRAGONS_ENTANGLED targetSupport=1 handAligned=0 bossAligned=0 gapSupport=0 velSupport=1 microAligned=0 macroAligned=0 arcAge=205.014093875885s left=485.2198839187622s

## Discipline

- The outcome label is hindsight and must never become a prospective input.
- No score, threshold, or entry rule is fitted from this tiny RS1 sample.
- The goal is to identify which already-existing battlefield fields deserve prospective logging around a dead-position / live-thesis reacquisition state.
- A new arc alone is explicitly insufficient because wrong theses also regenerated onto new arcs.
- V9.5A remains the frozen paper authority baseline.
