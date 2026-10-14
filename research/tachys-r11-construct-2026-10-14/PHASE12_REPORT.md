# TACHYS — Construct Phase 12 | Whole-Mountain Causal Research

**2026-10-13 · OFFLINE RESEARCH ONLY · No R12 release · No engine or live/PAPER trading authority modified**

## Research question

Do completed physical EMA9 arc histories, contemporaneous source slowdown labels, and successive measured returns distinguish real early turns from false crests/troughs **before** outcomes are known? Phase 12 tests the full observed lifespan of the arcs in original R9 and R11 engine records, not only selected winning entry moments.

## Source and accounting limits

Original engine audit archives used:

- R9 `666_lab_20261012_232558_169685_PID6268_audit_20261013T061800Z_25af4ded.zip`
- R11 `666_lab_20261013_121945_880967_PID16800_audit_20261013T180403Z_5720c5c7.zip`

Three untouched, SHA256-documented original CSVs per run are packaged under `input/`: `tachys_ema_geometry_v9_4i.csv`, `tachys_leg_geometry_v9_5c.csv`, and `tachys_price_arc_phase_v9_4j.csv`. R9 phase-5 historical entry controls and the compact R11 paper ledger are also included for anchors; anchor *outcomes* are **never inputs to the research observer**.

Engine geometry is **derived telemetry**, not independent raw one-minute candle OHLC, Kalshi native bid/ask book, or a full historical fill simulation. Adjacent leg and price-arc sources are joined **only backward in time** and require publication age <=4s (research provenance, NOT the executable HF2 quote limit). Missing joins are missing. BTC spot and the EMA9/EMA30 physical arc continue across contract ticks; YES/NO contracts and prices remain separate.

## Coverage

| Measurement | Observed |
|---|---:|
| R9 EMA geometry rows | 3,982 |
| R11 EMA geometry rows | 2,751 |
| Named EMA9 arcs | **49** (24 R9, 25 R11) |
| Arcs with an observed next arc | **47** |
| Last arc of each archive, end-censored | **2** |
| Arcs spanning two or more Kalshi contracts | **13** |
| Arcs with at least one >30s internal source gap | **10** |
| Distinct first-occurrence causal sequence events | **175** |
| Events having a sufficiently covered following 60 seconds of BTC telemetry | **151** |

A named arc is an **engine-produced `arc_id`**, not a guarantee that an independently measured arc has a continuous exchange tick stream. The recorded last observation before the succeeding arc is not necessarily the market's exact crest/trough. The 10 long internal gaps and the right-censored final arcs constrain comparisons.

The 13 cross-contract arcs directly support the doctrine: **the mountain continues while each Kalshi price target/contract is a new economic slice**. For example, R11 `A00008` is a DOWN arc with roughly **24 minutes 59 seconds** of sampled span across **three** contracts; it includes the problematic R11 #9Y, #10Y, and #11Y entries at different stages. Its largest within-arc telemetry gap is approximately **103.5 seconds**, so it is inappropriate to claim uniform continuous sampling.

## What the single-event checks actually showed

An independent forward-only observer records the first appearance within each named arc of:

1. Native source `WEAKENING` label.
2. Native source `CREST_FORMING` or `TROUGH_FORMING` label.
3. A measured retreat from its **previously observed** BTC/EMA9 extension peak.
4. A subsequent recovery attempt that turns back down before exceeding the **already observed** earlier extension peak.
5. The first observed BTC price move to the opposite side of EMA9.

These are **research events, not permission criteria**. The measured extension resolution ($5 BTC and a fifth of the *past/current* source range60 for initial retreat) is an instrument for recording geometry, not a fitted trading threshold. All recorded event features come from that or older source frames; neither future price, settlement nor later completed-arc statistics enter them.

As a deliberately rough evaluation yardstick, each event was checked for whether the sampled underlying BTC price subsequently traveled $20 or more **against the current arc direction** over a sufficiently covered 60-second period. This is not a Kalshi trade payoff or even necessarily a coherent side switch. Events sharing the same arc are **correlated**, and the yardstick was chosen to explore false-turn behavior—not as a trading parameter.

| First event type | Coverage-qualified examples | Followed by $20+ opposite BTC excursion |
|---|---:|---:|
| First native weakening | 33 | 17 (51.5%) |
| First named terminal phase | 27 | 11 (40.7%) |
| First measured return | 32 | 12 (37.5%) |
| First measured failed re-extension | 21 | 9 (42.9%) |
| First opposite-side BTC/EMA9 reclaim | 38 | 16 (42.1%) |

**No single first-event category clearly separates true turns from false attempts.** These are tiny correlated descriptive samples; differences in percentages are not statistical proof of predictive ranking. The price motion may not produce meaningful Kalshi economic capacity and may contain long spreads or unsafe quotes. Thus no direct permission or P&L inference is warranted.

## Crucial physical freshness discovery: #10 versus #20

### R9 #10 NO: attractive but not automatically qualified

- Historical entry **2026-10-13 04:20:09.706 UTC**, NO .29, inside the engine's **A00011 UP** arc.
- As-of source still called the arc **`EXPANDING / STRENGTHENING`**, BTC approximately **$57.73 above EMA9**. R9 #10's 60-second prior BTC movement remained **+$62.91 in UP direction**.
- The observer had seen the **first current-arc return from a known extreme about 4.69 seconds before** the trade entry. The first measured failed re-extension **did not appear until 2.45 seconds after entry**; using it to justify the original entry would be look-ahead.
- The last observed current-arc BTC high was only **6.7 seconds old**, and price was only about **$3.67 below** that source high. An early opposite entry here was brave and the later NO excursion was substantial, but Phase12 does not prove it was justified at the recorded purchase time.

### R9 #20 NO: deceptively terminal

- Historical entry **2026-10-13 05:17:50.180 UTC**, NO .32, inside **A00019 UP**, after about **11 minutes 12 seconds** of that named arc.
- As-of EMA source said **`CREST_FORMING / WEAKENING`**; nevertheless the first `CREST_FORMING` within this same arc had occurred about **672.7 seconds** before this entry, and the first mechanically measured failed re-extension **about 562.9 seconds earlier**. Those old events cannot be regarded as *fresh* permission for an entry at 05:17:50.
- A different physical high had been observed about **82 seconds earlier**, and BTC was about **$7.52 below** its prior arc high. Despite apparently more mature named source labels, this NO ultimately lost.

**Interpretation:** the missing distinction isn't a higher `crest_score`. It is **generation- and recency-aware interpretation of the physical attempt**: an old attempted turn is historical context, not an evergreen entry pass. Each renewed dominant-leg extension can invalidate an earlier terminal thesis and requires examining the most recent *fresh* crest/trough attempt. This must not become an arbitrary time cutoff; actual extension/return sequence defines a new attempt.

### R11 #9Y, #10Y, #11Y — same physical mountain, changing economics

All three original YES entries occurred during **A00008 DOWN**. #9 and #10 were premature opposite entries; #11 later achieved a profitable rebound but its **original** entry-time YES was still physically unqualified. At #11, the first terminal label of the whole long A00008 arc was about **19.6 minutes old**. This does not deny that *new* weakening/return evidence may have appeared later: it shows the danger of treating the first historical label as if it proves an active, newly earned turn.

Phase 9 already captured #11's developing actual physical handoff later. Phase 8 proved the tempting YES .54 moment was **exchange-stale >3s** and correctly safety-blocked. This Phase 12 study does **not** overwrite that finding with a spot-only profitability claim.

## Phase 12's practical conclusion

**Keep the four territories. Keep one EMA9 sovereign living arc. The missing process is tracking repeated physical attempts *within* the arc and retiring stale attempted-turn permission after a new dominant extension.** The same continuous physical history survives rollover, but every fresh contract is evaluated with strict native book ages, target distance, quote capacity, fees, and inventory.

Research outcomes argue **against releasing a new turn rule now**. Next engineering work must measure full **attempt generations** (extension → return → partial recovery → failed re-extension / new extreme), demonstrate early qualifying fresh attempts in both directions on independent archives, and only then promote evidence to One Command. That promotion must pass already-known positive controls (early R9 #6N/#10N, later developing R11 #11Y, valid #14N/#18N), reject old wrong-side entries (R11 #9Y/#10Y/#15N/#16Y/#17Y), and preserve whole-position hard-floor exits, premium re-entry control, custody, terminal review, sub20 observer-only authorization, and HF2 dual-source quote freshness. Final verification requires candidate-owned inventory through a complete chronological feed; do not report candidate P&L until this exists.

## Artifacts and exact limits

- `PHASE12_WHOLE_ARC_ATLAS.csv` — retrospective completed/observed arc summaries and explicit censoring; **do not load final amplitudes as as-of features**.
- `PHASE12_ASOF_SEQUENCE_EVENTS.csv` — causally available first-ever per-arc event observations only; do not equate first-ever with current attempts.
- `PHASE12_FUTURE_BTC_OUTCOMES_EVAL_ONLY.csv` — explicit hindsight-only BTC excursion evaluations; never train Command on it as current input.
- `PHASE12_TRADE_ANCHOR_CHECKPOINTS.csv` and `PHASE12_ANCHOR_ASOF_RECENCY.csv` — contemporaneous source evidence at selected historical trade offsets, with source freshness flags.
- `build_phase12.py` and `test_phase12.py` — reproducible offline atlas and source-integrity tests.
- `SOURCE_MANIFEST.json` and `input/` — original source filenames, byte counts, SHA256 and untouched source CSVs.

**Gate: RESEARCH PASS; EXECUTION RELEASE BLOCKED.** No engine files patched or run, no new commander, no fake candlesticks, no implied probability of profitable trading, no HF2 quote checks substituted by telemetry age.