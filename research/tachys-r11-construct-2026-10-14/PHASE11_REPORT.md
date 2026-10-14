# TACHYS R11 — Four-Territory Construct Phase 11

**OFFLINE research only · no R12 launcher · no actual engine started · no trading authority changed**

## Scope / original source

Phase 11 extends Phase 10's causal spot-point research by grounding it in **three original engine output streams** extracted from the separately retained R9/R11 engine audit ZIPs: `tachys_ema_geometry_v9_4i.csv`, `tachys_leg_geometry_v9_5c.csv`, `tachys_price_arc_phase_v9_4j.csv`. These are original **engine-generated geometry classifications**; they are not a complete independent collection of raw exchange candles or full order-book events. Original raw source subsets, original filenames, and byte-for-byte SHA256 digests are included for independent reproduction.

The sources are joined to **442 Phase 10 as-of checkpoints over 41 recorded entries**. Every joined publication was created no later than its checkpoint; the separate geometry research window is at most **4 seconds**. This is **not** the HF2 executable bid/ask freshness allowance. Engine geometry source coverage within that 4-second window: **434 EMA-geometry**, **407 leg-geometry**, **401 price-arc** checkpoints. Missing source evidence remains missing; nothing is backfilled from future rows.

## The decisive counterleg controls

| Source at actual entry | R9 #10 NO — ultimately profitable | R9 #20 NO — ultimately losing |
|---|---|---|
| BTC relative to EMA9 | Above EMA9 | Above EMA9 |
| Native EMA-arc source | `EXPANDING / STRENGTHENING` | `CREST_FORMING / WEAKENING` |
| Native leg `wick_rejection` | `UPPER_WICK` | `UPPER_WICK` |
| Native price-arc source | `PEAK_TROUGH_BUILD` | `PEAK_TROUGH_BUILD` |
| +10 seconds | Return toward EMA9, still pre-cross | Return toward EMA9, still pre-cross |

**A losing example already had the stronger-looking crest source label.** Therefore, pre-cross weakening/upper-wick/slowdown is not sufficient entry justification. Neither direction, an apparently mature crest, nor transient counterprice pressure is a calibrated prediction of a profitable swing. The R9 #10 early profitable NO is still an unresolved *opportunity-control*, not a proven causally valid original entry. In R9 #20 the first counterpressure later retracts; using the future retraction to justify a decision at entry would be look-ahead.

Additional R11 cross-checks: #9Y/#10Y initially remain below EMA9 inside continuing DOWN territory. #11Y at its original entry had the native **EMA9-arc** label `TROUGH_FORMING / WEAKENING`, while the distinct native **price-arc** report was `EXTENSION`. Those describe **different estimators**, not proof of a coherent jointly qualified turn. The R11 Command's actual proposed YES still lacked full physical qualification. The eventual profit does not retroactively qualify that original entry. The original .54 quote at the later price reclaim was exchange-stale; no quote safety was weakened.

## What changed in the offline candidate

Two research-only telemetry additions to existing offline R11/Phase10 Command source:

- `tachys_physical_edge_sequence_research.py` records distinct same-arc BTC-to-EMA9 observations: current-side extension, return toward EMA9, short recovery attempts below the prior extreme, failed attempts to re-extend, and measured price reclaim. A source-identical frame is not a new beat. Unproven leg IDs cannot carry authority across a contract rollover; a positively identified physical arc can keep its history while the contract ticker changes.
- `tachys_reassembled_command_v1.py` **only** instantiates that observer and attaches its output to the logged Command decision as `phase11_edge_sequence_research`. It never conditions an entry, exit, custody, settlement, quote check, or hard floor on that field. All outputs say `shadow_only=True`, `execution_authority=False`, `predicted_win=False`, `tradable=False`.

This is not a new trading commander, permission engine, or proposed arbitrary anticipation threshold. The observer's $0.50 separation resolution is a measurement-noise setting for BTC geometry, **not** entry permission or profit cutoff. `wick_rejection` remains an **engine-derived label**, not proof of independent OHLC body/wick observations.

## Recorded Command-sequence replay

The observer was run read-only over **1,570 original R11 decision frames with usable physical context**. This is *not* a candidate-owned inventory/quote/book replay, and frame counts are **not trades or independent profitable opportunities**. The observer sees both early returns and subsequent extension/recovery movements; no winning classification is inferred from these states. See `PHASE11_RECORDED_COMMAND_PHYSICAL_TIMELINE.csv` and the corresponding summary for source-state counts.

## Offline tests and release gate

**148 / 148 selected regression tests passed**, each suite in its own Python process to avoid the known inherited hook-reinstallation problem. They cover Phase11 source-as-of/no-authority measurement, the actual PAPER Command path, Phase10/9 observers, Phase8 dual-source HF2 quote freshness, Phase7 original successive Command decisions and whole-position hard-floor lifecycle, Phase3 mirrored physical entries, and R10 early-anticipation historical controls. Some inherited tests overlap and must not be described as 148 independent market scenarios.

The three deliberately RED historical anticipation release controls persist: **R9 #6 NO, R9 #10 NO, R11 #11 YES**. Their observed favorable outcomes do not validate original entry-timing decisions. **R12 remains blocked.** Also unresolved: candidate-owned complete native chronological BTC/quote/book/position/settlement replay; actual independent candle body/wick sourcing; original R11 #18 unresolved feed safety halt; sub-$0.20 authorization provenance; and inherited same-process test hook hygiene.

## Next controlled engineering experiment

Measure **dominant-leg renewal versus repeatedly failing renewed extension** across many completed historical arcs, not only entry-centered winning/losing samples. Check how often apparent mature crests/troughs regenerate. Combine strictly as-of multiple-leg ancestry, quote wave/source validity, and original genuine candle residence *when verifiable* before allowing any promotion of a turn to the existing One Command. Preserve current EMA9 sovereignty, Heist-edge qualification, independent mission generations, legitimate early tactical counters, whole-position executable-bid hard floors, Lazarus custody, terminal loss review, and continuous physical territory across independent contract/target/quote economics.

**No new R12 run, no changed live engine sources, no simulated P&L claim.**