# TACHYOS — PID23160 complete original-run forensic + chronological Construct gate

**2026-11-06 · STATUS: FULL RECORDED BEHAVIORAL GATE FAILED.** Frozen strategy source, PAPER only. No trading code changed and no replacement release approved. This is **not** exact engine replay of modified rules or a profit counterfactual. The original recording came from Windows Python 3.14.7; this Linux analysis environment has Python 3.13.5 and the exact replay tool deliberately requires the matching environment.

## Immutable provenance
- Run `TOOL_RACK_PAPER_20261106T045859Z_PID23160`. Six individually SHA-256 verified numbered payloads reconstruct **547,953,611 bytes** of original ZIP, SHA-256 `dd4f6eec165e1eaf6607e62dd4faeccc9ce41361c585ab1a7ed5ad2cb3dcfba5`, **424 members**, full CRC PASS.
- Source matches verified `TACHYOS_PID10760_PREOPEN_EMA9_CONTINUATION_45M_PAPER_20261105.zip` **67/67** sealed source identities; not an old-package relapse.
- 7,654 captured engine calls, zero dropped. 7,652 complete, sequential, hash-chained original Commander decision frames analyzed.
- Recorded 6 closed whole-lot PAPER positions; cash $1,000 to $986.4160, **−$13.5840 net**, gross −$3.6640, fees $9.92, no unresolved inventory.
- Trade ledger: #1 YES .076→.001 −$24.65; #2 YES .190→.240 +$1.29; #3 YES .270→.380 +$2.78; #4 NO .400→.240 −$4.37; #5 NO .180→.034 −$8.252; #6 NO .023→.047 +$19.618. Do not infer simulated alternative fills.

## Full chronological Construct result
An independent read-only audit scanned **every original decision frame**, checked decision sequence/hash chain and ZIP CRC, and asserted six observed regression controls. Source integrity **PASS**; overall strategy-behavior acceptance **FAIL_OBSERVED_SELECTIVITY**. All six anomaly checks were reproduced; 'anomaly reproduced' does NOT mean strategy passed or code repair has been tested.

1. **With-EMA9 entry starvation:** at **00:21:01**, seq4973, source-confirmed parent DOWN, BTC9 −$20.07, BTC60 −$49.94, EMA9_6 −$8.64, live NO ask **$0.29**, TP `STARTING_LEG_FAVORED`, but Commander returned `NO_TOOL_INTENT`, with no proposal. Market Heist owned CENTER while a potential directional NO rejoin went unbriefed. Later same-contract NO bid ~$0.84 at 00:24:31 is historical observation, not a hypothetical fill.
2. **Terrain misclassification candidate:** all **four** TACTICAL entries (#2–#5) used `wide_heist_qualified=true`, `classic_qualified=false`. Their boxes spanned BTC **~$272, $206, $223, $312** with only 1–2 outer-wall visits. Source `strategy_core/detectors/heist_geometry.py` lines 324–338 allows wide qualification with merely one visit per wall and one center traverse, using drift relative to inflated box width. Likely treats developing directional Mountains as Heist. No blanket Heist ban; legitimate tight repeated rotations remain protected.
3. **#1 false support/MAIN:** historical level near spot (~474s old), but native DOWN parent and no mature Mountain terminal; BTC was ~$127 below YES target. A tiny short bounce admitted exceptional 308 YES contracts and produced −$24.65 net.
4. **#3 YES too early despite eventual win:** at 00:30:33 BTC6 −$24.69, BTC9 −$29.31, BTC60 −$93.75; EMA9 parent DOWN, local Heist lean NO. The trade collected +$2.78 on 180-second `TACTICAL_MAX_HOLD_EXIT`, but its winning result does NOT validate entry timing. Longer hold isn't automatically justified while parent still DOWN.
5. **#4 NO unearned rejection:** $0.40 as BTC30 +$54 and EMA9_30 +$19.78; one small six-second slowdown, mission parent already YES although raw native parent still DOWN. Loses −$4.37.
6. **#5 NO fade of confirmed UP:** native parent UP, BTC30 +$36.45, EMA9_30 +$7.29, short BTC9 −$5.46; wide-only Heist used to buy NO .18 and lost −$8.252. #6 NO .023 was a separate fast Commander Mountain extreme ($0.023→$0.047, +$19.618), **not** a new DOWN Rail; maintain its precise case and earlier positive PID18244 #6 extreme/floor controls.

## Required NEXT engineering gate before a new PAPER ZIP
- Freeze one Commander, independent MAIN/TACTICAL, EMA9 authority, EMA30 spine only, existing risk tiers, Lazarus, Nautilus, and protected whole-lot floors.
- First build a **representative multi-contract source-bound behavioral Construct** with explicit positive NO directional admission at 00:21 and negative first-microstall / inflated-wide-Heist cases; protect authentic mature Heist edges, the prior PID18244 #6 $0.0877 extreme, prior PID17588 strong rollover, and previous floor positives.
- Only then design narrow positive admission + Heist territory proof changes; never fix trade count by adding shortcuts. Execute candidate code through full historical suite, extracted Construct, source hashes, capture/Windows export, Looking Glass JS, synthetic recorder/replay and fresh PAPER. A modified-engine full original tape run would require its recorded matching Python/Windows runtime and must be separately labeled.
- The current offline PASS on old 708-test gate is **not sufficient** for behavioral acceptance. No replacement run ZIP published from this forensic pass.

## Conversation artifacts
- `PID23160_FULL_RUN_FORENSICS_2026-11-06.md`, SHA `38fc04b32b91e39f98e1bad524bd2ef15f373ef6e6c128cba18a78b2a4fe841b`
- `PID23160_SOURCE_BOUND_CHRONOLOGY_2026-11-06.json`, SHA `c925c56a532147be9fb8955859b8a599d0d1fce6e119cd63401cba084e0c1ad6`
- `PID23160_CHRONOLOGICAL_EVIDENCE_CONSTRUCT.py`, SHA `469606b8131826f0a1d47b1205635414f391f9d34d33971f202218853367f139`
- `PID23160_CHRONOLOGICAL_CONSTRUCT_RESULT_2026-11-06.json`, SHA `f8d54bff1bfe3c240ebe3ffbf06de034e93f0bf434bfc50f3eb43882d64847d2`.

This branch contains only forensic/provenance notes, not the 548MB archived recording nor a modified strategy source tree. Preserve `main`.
