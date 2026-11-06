# Tachyos PID21672 — Recorded PAPER forensic review (2026-11-05)

Source: `TOOL_RACK_PAPER_20261105T170438Z_PID21672`, seven upload parts, reconstructed 605,488,970-byte original ZIP, SHA-256 `8cf5be466d24ebc11f62f680602dd629b619708d12b6b727b76939669f1a8364`. This is PAPER only. Recording reported complete and matching source; full original-engine replay was **not** performed.

## Committed outcomes (ET)

| Trade | Bought | Sold | Net after modeled fees | Recorded reason |
|---|---|---|---:|---|
| #1 YES | 12:07:19 at 0.089, 105 | 12:10:19 at 0.074 | -2.6850 | Entry HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED; exit PRIMARY_OPPOSES_LIVING_EMA9_PARENT |
| #2 NO | 12:31:33 at 0.370, 25 | 12:34:33 at 0.160 | -5.9000 | Entry MOUNTAIN_ROLLOVER_TARGET_REACHABLE; exit PRIMARY_OPPOSES_LIVING_EMA9_PARENT |
| #3 NO | 12:36:00 at 0.270, 88 | 12:39:00 at 0.180 | -10.0500 | Entry RAIL_MAIN_VALUE; exit TACTICAL_MAX_HOLD_EXIT |
| #4 YES | 12:40:34 at 0.330, 28 | 12:43:27 at 0.740 | +10.6600 | Entry HEIST_PARALLEL_STALLED_EDGE_RETURN; exit ALREADY_ARMED_EXECUTABLE_BID_FLOOR |

Starting PAPER $1000; ending $992.0250; net -$7.9750; fees $4.71; all four positions closed and unresolved inventory zero. The screenshot's final display corroborates the four trades but the ledger is the authoritative accounting.

## Root-cause finding for #2 (one narrow correction)

At original decision sequence 5487, the ordinary Commander MAIN Mountain NO proposal qualified as `COMMANDER_MOUNTAIN_ROLLOVER_TARGET_REACHABLE`. Its metadata still used historical/inherited NO gap and a short DOWN child. At that **same recorded decision**, however, `mission_context.parent` was **ACTIVE YES**, `supported=True`, `basis=CONFIRMED_RELEASE_TRANSFER`, `invalidated=False`, current on the same source sample/continuity generation, and not terminal-qualified. The current 30-second BTC and EMA9 short motions were DOWN, so this is not a blanket prohibition on NO movement; it is an inconsistency between a current confirmed parent transfer and an ordinary MAIN proposal treating historical NO as current parent ownership.

Correction: only ordinary Commander MAIN Mountain entries must respect a currently confirmed, supported, same-sample opposing mission parent. TACTICAL Heist and independent Rail proposal families are unchanged. Do not add blanket adviser vetoes. Bound this rule by current source, generation, and confirmed transfer, not old labels.

A recorded-case test of seq 5487 now returns `WAIT` at the admission check. No alternate buy or entire-run P&L is claimed. The later #3 NO Rail at seq 6109 and the Heist cases #1/#4 remain eligible in the bounded checks.

## #3 is still a research problem, NOT corrected in this release

At seq 6109 the mission parent was current NO and its source was aligned. The short BTC readings were mixed: 6s DOWN, 9s UP, 30s DOWN; no identical confirmed YES parent transfer exists to reject it by the same rule. Its $25-style size and three-minute tactical hold remain priority research for the next chat. The exit at 12:39:00 was `TACTICAL_MAX_HOLD_EXIT`, not successful structural ownership. Need evaluate a parent-scale NO continuation vs tactically trading the emerging return; do not assert that a counterfactual YES entry would be executable/profitable.

## #4 is a positive whole-lot protection control

The 12:40:34 YES Heist bought at 0.330 and exited as a whole lot at 0.740 on `ALREADY_ARMED_EXECUTABLE_BID_FLOOR`, +$10.6600 net. Preserve entry/exit and no partial sales. The previous #1 Heist bought correctly near a lower edge by operator visual assessment but the booked trade lost -$2.685; preserve its *entry investigation* rather than declare it a successful P&L positive control.

## Rollover idea for next forensic (NOT automatically authorized)

The user's TradingView reading identified a persistent downward Rail over several contracts, an extended EMA9 near a low TP at rollover, and the possibility of a tactical YES return early in the next contract. Test when the live physical evidence actually supported an independent subsequent bounce and whether executable YES quotes and minimum runway existed. TACTICAL should be able to collect a genuine shorter return or promote an earned Release to MAIN. Do not treat cheap YES or a single cross alone as automatic release authority; do not revise first-minute wait or premium caps without separate evidence/approval.

## Looking Glass research status

The current bright active-pattern continuation and fixed earlier display trace are a positive UI step. They are conditional visual research, not probability-calibrated forecasts or trading authorities. Preserve display. A separate durable pre-event forecast archive remains research work; avoid retrospective redrawing of forecasts.

## Scope and validation limits

Only `strategy_core/commander_candidates.py` changes in strategy code. New bounded admission fixture and test are included. Existing quote freshness, whole-lot custody, Rail dipping watch, first-counterfade observation, Looking Glass, recorder/export workflow and PAPER-only authority remain unchanged. Old historical unit-test baselines remain in their original archive; the approval and source inventory identify the reviewed new hash. The next live market is an unseen PAPER validation, not a profitability guarantee.
