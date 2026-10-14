# THE NAUTILUS / TACHYS — PHASE 9: CONTINUOUS PHYSICAL HANDOFF PERCEPTION

**Session:** October 13, 2026 · R9 independent comparator + R11 closed PAPER session  
**Disposition:** **OFFLINE RESEARCH CANDIDATE ONLY. R12 BLOCKED.** No live order authority, no active bot run, no strategy release, no historical profitability improvement claim.

## Executive conclusion

The Phase 7 candidate successfully blocked repeated R11 #9Y/#10Y stale-DOWN-mountain violations, but Phase 8 found that R11 #11Y developed a *new physical* YES qualification while the original R11 Command kept presenting NO through the Heist route. Its early .54 YES quote was HF2-stale. Phase 9 separates those two questions by installing a **shadow-only, chronological physical-handoff observer inside the existing PAPER Command path**, with no changes to any executable decision rule.

**Phase 9 solves observation, not execution.** It now records *when the current price/EMA9 physical context and independently qualified next candidate are evolving toward the other side*, alongside the ORIGINAL Command ruling and its unmodified HF2 mechanical safety. It does **not** promote the entry, retire a position, alter winner hard-floors, reject the opposite side, or create a new commander.

## Exact #11Y causal handoff evidence

| Actual R11 Command frame, UTC | ET | Current-living leg / next candidate | Phase 9 physical reading | Original R11 action |
|---|---|---|---|---|
| 17:15:10.627 | 1:15:10.6 PM | NO / unqualified YES; prior opposing blocks | `NEXT_NOT_PHYSICALLY_QUALIFIED` | Original R11 entered YES .50. Candidate rightly *does not use* its later outcome to qualify this entry. |
| 17:15:22.929 | 1:15:22.9 PM | NO / qualified YES, blocks cleared, source BTC ≈$5.34 **above EMA9** | `HANDOFF_FORMING_AWAIT_SECOND_PHYSICAL_BEAT` | **WAIT / HARD_MECHANICAL_SAFETY**; original quoted .54 YES was exchange-age >3s and not HF2 executable |
| 17:15:25.233 | 1:15:25.2 PM | NO / still qualified YES, BTC ≈$7.62 above EMA9 | `HANDOFF_PHYSICALLY_OBSERVED`; second *distinct* physical reading | **WAIT / HEIST_RELEASE_PRESENTS_TO_MOUNTAIN**, presenting NO |
| 17:15:36.246 | 1:15:36.2 PM | NO / qualified YES, BTC ≈$11.95 above EMA9 | Physical handoff remains observed | **WAIT / HARD_MECHANICAL_SAFETY** |

The **reported handoff at 17:15:25 is a shadow physical reading, not an executable signal**. The Phase 8 one-second as-of quote atlas finds its first later physical-reclaim/dual-HF2-fresh YES ask around original+32s at **.71**, offering **40.85% maximum theoretical gross payout if YES settles**, not an executable scalp claim and not a Command fill at that second. The original Command's .54 safety stop must not be weakened.

## Cross-run negative and positive controls

- **R11 #9Y / #10Y:** During each first 30 seconds after the original bad entry, no source-based observed opposite YES physical handoff passed the chronological observer. Old completed arc A00007 does not qualify a new turn in living A00008.
- **R11 #14N and #18N:** The original legitimate Mountain and Heist-edge routes remain executable in controlled synthetic PAPER books. The hard-floor collection / immediate premium same-leg re-buy prevention around #14N→#15N is unchanged.
- **R9 #10N:** Its NO-friendly deceleration occurred **before** BTC crossed EMA9, with a distinct HF2-fresh NO book in the research atlas. This remains a crucial **pre-cross** anticipation research case. This Phase 9 observer does NOT pretend a price/EMA9 cross is necessary for all future valid anticipations. R9 #6N and the R9 #20N brief false pulse remain independent checks.
- **Contract rollover:** Source physical arc identity survives while ticker, quote freshness, fee/settlement and position identity are never transferred or conflated.

## Technical implementation

Changed *offline candidate* `release/engine/tachys_reassembled_command_v1.py` by four isolated additions: importing the observer, instantiating it, recording each as-of physical observation into `af`, and retaining the result in final decision telemetry. New source: `release/engine/tachys_asof_physical_turn_research.py`. This is **not** installed on the user's Windows system. Both main entry and position management calculations are unchanged from frozen Phase 7.

The observer requires a live current-arc ID, the opposite candidate's own source qualification and absence of blocks, a causally observed BTC/EMA9 price sign change, and at least **two distinct**, time-ordered source physical measurements. Duplicate timestamps, repeated unchanged source geometry, nonfinite data, missing context, and out-of-order frames do not establish a handoff. It remains advisory even when its physical evidence is compelling.

**Data caveat:** The retained `source_frame.local_arc.signed_sep` is an arc-side-signed BTC-minus-EMA9 observation; the observer converts it to BTC-minus-EMA9 by the documented side convention. Original source frame `ts` is available, but no independent subsecond age for every derived physical measurement is preserved. Therefore the observer cannot claim stronger source freshness than the telemetry actually provides. The two-beat condition is a **research observation discipline**, not a tuned trade-admission threshold.

## Source-wide research scan

The replay processed **1,570 of 1,623 archived R11 decision frames** carrying sufficient recorded physical context. There are **85 frames labeled `HANDOFF_PHYSICALLY_OBSERVED`**, representing multiple subsequent updates of the same possible turns, **NOT 85 independent turns, entries or predicted profitable opportunities**. One such cluster corresponds to #11Y. There is no evidence-based precision/recall or profitability claim from that raw frame count.

## Validation and release gates

- **87/87 selected fresh-process offline tests PASS**: 14 new as-of physical/quote tests, 1 real PAPER Command observer-integration test, 18 source-freshness Phase 8 tests, 12 Phase 7 causal evidence, 6 Phase 7 real Command chronology, 3 protected winner lifecycle, 15 Phase 3 physical/mirrors, 18 inherited R10 anticipatory/mirrored controls.
- **3/3 future-entry research expectations intentionally remain RED**: R9 #6N, R9 #10N, R11 #11Y. They are opportunities to explain or recover *when source justified*, not a license to fit past winner outcomes.
- Original PAPER `MechanicalSafety`, same-ticker HF2 exchange **and** receive freshness, no-chase, >=35% maximum payout eligibility, low-price observer-only policy, hard runner floor, Lazarus, late terminal review, position occupancy and settlement are **not changed**.
- No full candidate-owned native orderbook/position replay, no native candle body/wick evidence, no out-of-sample performance estimate. R11 #18 unresolved data-invalid halt and same-process logging hook idempotence remain outstanding.

**Release verdict: R12 BLOCKED.** Next Phase 10 should compare other physically comparable, *pre-cross* early-turn controls using candle residence / failed extension / native quote-waves, then consider a single integrated PRIMARY/NEXT/Heist handoff promotion only behind the existing rigorous mechanical and economic gates, in a candidate-owned stateful chronological test. There must be no extra tactical commander or compulsory wait until EMA9 slope itself crosses EMA30.

### Portable reproducer

In the extracted bundle, with Python and the original offline dependencies installed:

```bash
python -B build_phase9_observer_timeline.py
python -B run_phase9_offline_gate.py
```

`PHASE9_SOURCE_DECISION_OBSERVER_TIMELINE.csv` is research evidence using original recorded R11 inventory/decisions, **not a new PAPER fill log**. The ZIP intentionally includes **no launch scripts**. Do not copy its research source into a running production/live bot.