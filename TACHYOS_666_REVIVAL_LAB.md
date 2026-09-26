# Tachyos V9.5D — 666 Revival Lab 01

## Purpose

Revisit the September 21–22 V9.5D session that recorded **$666.291 gross winning P/L**, **$406.466 gross losing P/L**, and **+$259.825 paper P/L** across 232 closed trades, while testing a deliberately narrow set of repairs.

Historical archive:

`runs/2026-09-21_v9_5d_campaign_authority_smoke_pre_ema9_01`

The historical run was pre-EMA9-formation patch. Its source reconstruction is not guaranteed to be byte-identical to the process that was loaded during that session. This lab therefore tests a reconstructed lineage, not a claim of exact deterministic replay.

## Active strategy changes

1. **EMA9 formation-confirmed campaign transfer**
   - Bare `RETURN_SLOPE` does not normally transfer campaign authority.
   - Progression toward/through the spine can confirm.
   - A strong early return-slope exception still exists when EMA9 slope, curvature, and 3/6/9 displacement all agree.

2. **Independent tactical pre-arm lifecycle**
   - Opposing fresh pre-arm positions are treated as tactical unless they earn promotion.
   - Tactical stake remains $5.
   - Tactical harvest: +35% ROI.
   - Tactical invalidation: -15% ROI, confirmed for 1.5 seconds and after a minimum 3-second position age.
   - A tactical sleeve can be promoted only after campaign transfer plus spine/target confirmation.

3. **Tiered winner-floor protection before the old 9-second grace rule**
   - MFE >= 50%: protect +25% after a 1.5-second confirmed breach.
   - MFE >= 60%: protect +35% after a 1.5-second confirmed breach.
   - MFE >= 75%: protect +50% after a 1.5-second confirmed breach.
   - At 50–60% MFE, strong continuation can override the floor temporarily when campaign, 3/6/9 strength, and recent target progress agree.
   - At >=75% MFE the +50% floor is mandatory; continuation does not override it.

The confirmation timer is intentional because the historical archive contained very fast quote oscillations whose executability could not be established.

## Deliberately inactive in LAB-01

These later restraints are present in the inherited source but disabled so they do not confound the revival experiment:

- active churn re-entry quarantine
- negative-transfer candle holding
- compression entry quarantine
- stretched-main/opposite-tactical wait
- extra late/mature entry filters
- sub-50% midwinner harvest
- tactical 30–35% stalled harvest

## Chop / no-parent-arc hypothesis

The user hypothesis is:

> When there is chop or no reliable parent arc, postpone campaign commitment and study/rider local legs or edges if they are long enough and predictable.

LAB-01 records these conditions as `LEG_LAB_OBSERVER_ONLY` in `tachys_churn_court_v9_5d.csv`.

**It does not yet grant new entry authority.**

That choice is intentional: the September 21–22 audit showed the existing COMPRESSION label was profitable in-sample, so a broad chop veto would risk deleting a real edge. The observer should first measure leg duration, direction, target progress, and hypothetical harvest/stop outcomes.

## Telemetry to review

Primary:
- `tachys_paper_trades_v9_2_6.csv`
- `tachys_campaign_authority_v9_5d.csv`
- `tachys_winner_harvest_v9_5d.csv`
- `tachys_exit_court_v9_5d.csv`
- `tachys_tactical_lifecycle_v9_5d.csv`
- `tachys_churn_court_v9_5d.csv`
- `tachys_quote_integrity_v9_5d.csv`
- `tachys_execution_shadow_trades_v9_5d.csv`
- `tachys_execution_shadow_quotes_v9_5d.csv`

## First-run review questions

1. Did formation confirmation reduce fast losing campaign transfers without making valid reversals materially late?
2. Did tactical sleeves retain useful counter-leg gains while cutting the large override losses seen in the historical run?
3. How often did each 50/60/75 floor arm, how often was it overridden by strong continuation, and what happened afterward?
4. In `LEG_LAB_OBSERVER_ONLY` periods, were there repeatable local legs with enough duration and quote quality to justify a future active sleeve?
5. What is paper P/L versus execution-shadow P/L? No promotion decision should use paper P/L alone.

## Run discipline

- PAPER ONLY.
- Do not run simultaneously with another Tachyos process writing the same root CSV files.
- Archive the current run before starting this lab.
- Let the first clean run proceed without parameter changes unless there is a code or data-integrity failure.
- Evaluate the whole run and contract-level behavior, not a few visually memorable trades.
