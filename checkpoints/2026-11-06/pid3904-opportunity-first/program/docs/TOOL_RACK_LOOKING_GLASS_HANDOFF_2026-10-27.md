# Looking Glass / Hurricane restoration — review candidate

Date: 2026-10-27 (America/New_York).

## Scope

Restore a useful standalone Looking Glass briefing and Hurricane-style conditional paths in Nautilus. The current candidate reads the already published market, historical candles/EMAs and exact-contract native quotes. It has no order, veto, role-allocation, holding or settlement authority, and imports no legacy engine. This is an observer restoration, not the pending PID10092 entry/profit correction release.

The user's latest strategy instruction is recorded in [operator Note 13](TOOL_RACK_RUN_OBSERVATIONS_2026-10-27.md): contract-direction thesis first using one or two preceding contract intervals; adaptive entry timing without a hard four-minute cutoff; separately qualified tactical swings around a provisional 40% gross return on entry price. The user explicitly confirmed the percentage basis.

## Identities and configuration

- Branch: `tachyos-tool-rack-pid10092-looking-glass-20261027`.
- Candidate package: `TOOL_RACK_LOOKING_GLASS_REVIEW_CANDIDATE_20261027`.
- Nautilus: `TOOL_RACK_NAUTILUS_TV_V6_LOOKING_GLASS`.
- Trading policy/runtime revision remains `TOOL_RACK_PAPER_PID7516_ENTRIES_RUNNERS_20261027` because this work does not change its entry/exit decisions.
- `strategy_core/config/looking_glass.json`: `minimum_gross_roi: 0.40`, `history_contracts: 2`. These are observer review settings. They do not activate an execution filter or fixed profit target.

## Model and presentation

The pure `strategy_core/looking_glass.py` model returns a detached, finite JSON view. It uses causal completed history, shows coverage limits, and creates explicitly conditional continuation, rotation/stall and reversal paths from the latest observation to the current contract's known close. Competing endpoints do not become a fabricated probability distribution. Current directional lean, conditional continuation and a genuinely mixed scenario set remain distinguishable. A hypothetical Coinbase BTC/EMA trajectory is not an official settlement prediction.

The restored model uses the phase-matched remainder of each complete preceding 15-minute profile. It translates that remainder to the present observation, or removes its net displacement for the rotation case, or mirrors it for the opposing return case. This is a new standalone historical comparison model, not a bit-for-bit port of the archived arc matcher. Its dotted EMA9 traces are translated historical analogues rather than EMAs recursively recomputed from the hypothetical BTC paths. Each path ends at the exact current expiry, including with fractional Unix timestamps.

Completed history and current direction have separate requirements. A missing current continuous EMA9 observation suppresses directional paths even when older profiles are complete. Flat current motion, or a prior remainder with no net EMA9 direction, can supply rotation context without manufacturing continuation/reversal evidence. Candle coverage and directional-reference coverage are reported separately. The model never supplies future candles, reconstructed intraminute paths or a next-contract target.

The tactical review computes the sale bid required to reach the configured gross return from the current valid ask. At 40%, $0.30 implies $0.42. This is an arithmetic review hurdle, not an order price or automatic exit. Any past ask-to-later-bid excursion remains marked as historical, exact-ticker evidence with no proof of future availability or full-position execution. An unavailable prospective bid/physical estimate remains unassessed.

Nautilus provides a Looking Glass toggle, visually distinct future paths, a current-time boundary, expiry context and a briefing that separates the contract thesis from swing review. Current projections must not appear as historical evidence while inspecting an earlier trade. Existing narrow-feed/large-position TV layout remains the baseline.

Projection integration isolates model/configuration/serialization errors. An unavailable observer must not suppress the committed ledger, engine feed, current positions or existing decision record. The engine already treats dashboard publication as nonfatal; the local observer boundary also preserves the rest of the dashboard when its own calculation fails.

## Validation

- The full offline source acceptance passed **423 tests across 45 explicitly selected modules**. The initial restricted run could not open three local dashboard sockets; the same suite passed with loopback access. This was a local test-environment restriction, not a model or strategy failure.
- Four subsequent regressions cover large fractional expiry timestamps, nondirectional prior remainders, a mixed directional/nondirectional reference set, and the actual production startup chain. The final focused command passed **37 tests**: 21 model, 5 integration/isolation and 11 existing Nautilus projection tests. The final selected package suite therefore contains **427 tests**.
- Production startup compatibility uses the real `validate_candles → seed_chart_candles → _ChartHistory → MinuteEMAs → NautilusProjection` chain with 239 synthetic completed bars. It supplies both complete prior-contract profiles, each with 16 boundary/close observations, and produces six paths. The early EMA warmup rows remain outside these recent windows. This verifies the schema under continuous coverage; actual source gaps still remain unavailable.
- The isolated JavaScript chart checks and browser source syntax checks passed. They cover exact-contract/source anchors, expiry bounds, mutation isolation, current-view eligibility and history-span preservation.
- Real Chromium acceptance passed at desktop and **390 × 844 mobile** sizes using a clearly labelled synthetic fixture. It checks the actual model's six paths, exact expiry, the 40% `.300 → .420` arithmetic, persisted toggle, current versus historical review, manual pan, stale clearing even while an API response is unanswered, frozen repeated payloads, mobile chart rendering and existing ledger/ROI/role/feed behavior. There were no browser errors, CSP violations or external resource requests. Desktop and mobile output were visually inspected.
- The strict bundle contains **130 whitelisted source/assets/test files**, plus its manifest. The builder extracts that ZIP and runs the full manifest-enforced acceptance gate before publishing any delivery archive. A failed extraction, hash check or test prevents publication.

No live feed, Windows strategy run or venue order is part of these checks. Automated acceptance establishes the observer's implementation boundaries; it does not establish predictive accuracy, profitability or compliance of the existing PID10092 trade decisions with the user's intended strategy.

## Outstanding strategy work

The PID10092 role/scope and premature-collection findings remain open. This restoration does not certify the reported #3–#8 decisions, select new live trades, implement a calibrated settlement-side predictor, or enforce expected 40% swing admission. The current diagnostics export is required to replay the actual entry/exit paths and evaluate the proposed policies causally. Losing-to-settlement and recovery-policy redesign remain outside the authorized correction scope.

The next entry/holding correction must demonstrate these behaviors against causal inputs:

| Required behavior | Evidence that must govern it |
| --- | --- |
| Contract-direction priority | The current target, time remaining, observed parent leg and one/two-contract context, before role allocation or local-fade selection. An empty slot cannot promote a local fade to PRIMARY. |
| Earlier usable edge entries | Current executable ask/depth within a still-valid observed edge region, including broad tops/bottoms, without waiting for a confirmed future pivot or chasing a spent return. |
| Independent substantial tactical swings | A distinct physical swing and credible remaining ask-to-sale-bid opportunity at the configured gross ROI level, with fees and size checked. A past whole-contract excursion is insufficient prospective evidence. |
| Main-leg holding through internal weakness | The held position's own physical scope, including ordinary pullbacks and applicable EMA-cross context. Completion of a smaller swing must not automatically end the main leg. |
| Scope-aware collection and rollover | Actual terminal/invalidating evidence, existing earned protection and contract rules, with the ordinary same-entry-candle exit restriction preserved. No fixed four-minute deadline or +40% automatic take-profit is introduced. |

The exact PID10092 diagnostics are still needed for its decision-time physical observations, native quotes/depth, role assignment, command reasons, source pin and committed fills. Screenshot observations remain labelled as observations rather than a causal replay.
