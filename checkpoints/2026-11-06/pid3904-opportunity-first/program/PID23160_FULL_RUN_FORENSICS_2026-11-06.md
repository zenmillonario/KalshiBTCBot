# TACHYOS — PID23160 complete original PAPER forensics

**Report date:** 2026-11-06. **State:** original archive and source identities verified; all 7,652 recorded Commander decision frames chronologically inspected. **This is not an exact execution-engine replay, a changed strategy, or a new PAPER release.** No alternative fills, trades, or profits are assumed. The earlier operator assessment that the bot has regressed toward over-eager speculative entries is supported by the entry-location and territory-classification evidence.

## 1. Source provenance and integrity

- Run: `TOOL_RACK_PAPER_20261106T045859Z_PID23160`, Windows PAPER, recorded 23:59–00:45 ET (the current date is November 6 in ET after midnight).
- User's six numbered ZIPs were each verified against `TRANSFER_MANIFEST(20261106-054926).json`; `archive_chunk.bin` byte streams reassembled in order. Reconstructed original: **547,953,611 bytes**, SHA-256 **`dd4f6eec165e1eaf6607e62dd4faeccc9ce41361c585ab1a7ed5ad2cb3dcfba5`**, **424 ZIP members**, CRC check **PASS**. The original was not changed.
- All **67/67 sealed source hashes match** the previously verified `TACHYOS_PID10760_PREOPEN_EMA9_CONTINUATION_45M_PAPER_20261105.zip`. In particular `strategy_core/commander.py` `476d5b8682c5ab2946dbea617ba7495521ff7f6f0e0d62ede21c6cb35c42151d`; `strategy_core/commander_candidates.py` `f3793fcc79d77192c9c94626c603da6db972e05cdc6822e2a662837291c6aa3a`. This is **not** an old-release installation regression.
- Recorded input tape: **7,654/7,654 engine calls written, zero dropped**. Engine decisions: **7,652 ordered frames**. No source integrity gap identified.
- Exact replay: **NOT performed**. The source's own replay header requires **Windows CPython 3.14.7** and rejects mismatch by default; this Linux analysis environment runs CPython 3.13.5. The completed review is a read-only, full-sequence original-decision/quote/EMA9 examination, **not** a modified-engine Construct run or synthetic-trade backtest.

## 2. Recorded final PAPER ledger

Initial $1,000.0000 → final **$986.4160**; gross **−$3.6640**, modeled fees **$9.92**, realized net **−$13.5840**, **six full-lot entries and closes**, no unresolved inventory. The `closed_positions.close_ts` field is contract expiration rather than the actual exit time; the following times are taken from booked `ENTRY` and `EXIT` events.

| # | Entry–exit ET | Side | Contracts | Price in → out | Modeled gross | Net PAPER | Recorded exit reason |
|---|---|---|---:|---|---:|---:|---|
| 1 | 00:09:54–00:13:22 | YES | 308 | $0.076 → $0.001 | −$23.10 | **−$24.65** | `LAZARUS_HARD_ADVERSE_STRUCTURE` |
| 2 | 00:24:14–00:25:48 | YES | 49 | $0.190 → $0.240 | +$2.45 | **+$1.29** | `ALREADY_ARMED_EXECUTABLE_BID_FLOOR` |
| 3 | 00:30:34–00:33:34 | YES | 35 | $0.270 → $0.380 | +$3.85 | **+$2.78** | `TACTICAL_MAX_HOLD_EXIT` |
| 4 | 00:35:12–00:38:01 | NO | 23 | $0.400 → $0.240 | −$3.68 | **−$4.37** | `LAZARUS_HARD_ADVERSE_STRUCTURE` |
| 5 | 00:38:36–00:41:01 | NO | 52 | $0.180 → $0.034 | −$7.592 | **−$8.252** | `LAZARUS_HARD_ADVERSE_STRUCTURE` |
| 6 | 00:42:25–00:43:02 | NO | 1,017 | $0.023 → $0.047 | +$24.408 | **+$19.618** | `COMMANDER_HIGH_PROFIT_PEAK_HOVER_COLLECT` |

**Five of the six entries opposed the contemporaneous native EMA9 parent.** #4 was the exception in the raw geometry, but its local 30-second price and EMA9 were rising strongly, and the mission parent had already changed to YES. Thus this run had no convincing MAIN entry riding a developing with-EMA9 directional leg. This is a *selectivity and positive-admission* problem, not evidence that the raw trade count was too high (only six trades in the run).

## 3. Strong positive omission: 00:21:01 NO directional window

- Contract: `KXBTC15M-26NOV060030-30`; real source around **00:21:01 ET**, decision **sequence 4973**.
- BTC **$75,522.88**, target **$75,489.05** (approximately $33.83 away from the NO side), native EMA9 parent **DOWN** with EMA9–EMA30 gap **−$18.80**, BTC6 **−$11.89**, BTC9 **−$20.07**, BTC60 **−$49.94**, EMA9_6 **−$8.64**.
- Native NO ask **$0.29**, bid **$0.28**; TP reported **`STARTING_LEG_FAVORED`**; sources current. Detected owner `MARKET_HEIST`, zone **CENTER**, not a proven Heist outer edge. The Commander produced **`WAIT: NO_TOOL_INTENT`** and the candidate list was empty. A directional MAIN route did not appear.
- By 00:24:31 the same contract's native NO bid was recorded around **$0.84**. This is a later observed price, **not proof of an earlier order fill or an alternative realized return**.
- Corroboration: at 00:16:39 there had been a `RAIL` NO candidate with reason `PARENT_SCALE_RAIL_DIRECT_AUTHORITY`, but the Commander instead returned `COMMANDER_RELEASE_CHAPTER_OWNS_DIRECTION`. BTC60 then was **+$58.99** against NO and TP was unresolved, so that frame is a routing diagnostic, **not** an automatically valid NO entry.
- **Next test:** Find a physically earned, with-parent NO rejoin route at a current cheap quote, without authorizing arbitrary mid-leg chasing, while diagnosing why an expanding DOWN movement was repeatedly labeled a Heist center.

## 4. Principal regression: wide Market Heist masquerading as directional terrain

The captured code's `strategy_core/detectors/heist_geometry.py` allows classic Heist with at least two lower and two upper visits and two center traversals. Its *wide* alternative (lines ~324–338) can qualify after a longer window with **only one visit to each wall and one center traversal**, provided drift is measured against the size of that window. It also currently sets `tight_box = True` pending further checks (line ~283), so a very large directional window can make that drift ratio look acceptable.

**All four filled TACTICAL trades (#2–#5) used `wide_heist_qualified=true` while `classic_qualified=false`:**

| # | Heist detected BTC range | Lower / upper visits | Center traversals | Entry consequence |
|---|---:|---|---:|---|
| #2 | ~$272 | 1 / 1 | 1 | Lower-edge YES counter to advancing DOWN parent; realized small win |
| #3 | ~$206 | 2 / 1 | 2 | Early YES during still-expanding DOWN movement; later won |
| #4 | ~$223 | 1 / 2 | 2 | NO at $0.40 while strong upward child was still advancing; loss |
| #5 | ~$312 | 1 / 1 | 2 | NO while newly recognized parent UP; loss |

These *wide* boxes are not, by themselves, evidence of the tight repeated alternating Market Heist the operator authorized. The large windows contain long directional arcs and the same detector grants a current edge inside them. This is the most likely systemic source of **early tactical fades after too little reversal proof**. A profitable #2 or #3 does not independently validate its entry location. #6 is separate: it entered via first-class Commander Mountain, not Heist TACTICAL.

## 5. Trade-by-trade causal controls

**#1 YES — unearned old low, large counterparent risk.** Commander-native `COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN`, $25 tier at $0.076 (308 contracts). A historical low at $75,550 from about **474 seconds earlier** appeared close to current BTC **$75,545.42**, but native parent and gap were DOWN (−$45.33), no mature Mountain terminal evidence was qualified, and required move to contract target was **$127.23**. A positive BTC9 bounce (~+$21.43) was insufficient parent-scale reversal proof. This is a negative admission case; price <$0.20 and proximity to an old low are not enough. Preserve the earlier PID18244 #6 exceptionally well evidenced NO upper extreme as distinct positive control.

**#2 YES — floor positive, entry not automatically high-quality.** $0.19 lower wide-Heist edge with native parent DOWN, BTC9 **−$11.09** and BTC60 **−$63.27**; box width ~$272 and one visit per wall. Whole-lot bid floor correctly collected +$1.29. Retain the real floor behavior but test the entry's patience independently.

**#3 YES — winning trade entered while price was still falling.** At entry, BTC6 **−$24.69**, BTC9 **−$29.31**, BTC60 **−$93.75**, EMA9_6 **−$4.94**, gap **−$68.76**, parent **DOWN**, and Heist `lean_side=NO`. The intent was `HEIST_PARALLEL_STALLED_EDGE_RETURN`; wide box, not classic. This contradicts the earlier image-only characterization of a well-timed earned UP turn. TACTICAL exited after ~180s at $0.38, with already established floor about $0.3686 and current bid $0.38. Later recorded YES bid reached ~$0.71 around 00:36:01, but the EMA9 parent was still DOWN at exit; automatically extending every tactical hold is **not justified** by the later price.

**#4 NO — false upper-edge rejection.** $0.40 entry with BTC30 **+$54.00**, EMA9_30 **+$19.78**, BTC9 **+$7.65**. Native geometry still reported a DOWN parent, while mission-context parent was **YES**, showing a parent-identity transition worth testing. A ~6-second −$0.63 pause was not a substantial physical upper rejection. Wide box only, not classic. Loses −$4.37. Clear negative patience control.

**#5 NO — repeated fade during genuine UP parent.** Entry $0.18, native **UP** parent, BTC30 **+$36.45**, EMA9_30 **+$7.29**, slight BTC9 **−$5.46**. The wide Heist box was ~$312 with only one lower and one upper visit. Lost −$8.252. The source formally admitted a new TACTICAL return based on too weak a short-term opposite turn; do not protect it merely because it was under $0.20.

**#6 NO — short winning counter-UP extreme, not proof of a new DOWN Rail.** Commander-native `COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN` at actual $0.023 with 1,017 contracts; current UP arc about **55.6 seconds** old, upper extreme about **15.46 seconds** old, BTC9 **−$11.50** while BTC30 and EMA9_30 still positive. The Mountain detector did **not** report a fully mature terminal or completed-minute reference. The move was harvested promptly in ~37 seconds from $0.023 to $0.047, +$19.618 net after fees. Preserve the genuinely profitable *whole-lot fast collection* and exact entry as a recorded case, while keeping the structural question open—this is not equivalent to earlier PID18244 #6's demonstrated historical level-match rejection.

## 6. Why isolated tests passed but overall behavior regressed

The previous 708/708 strategy suite and synthetic recorder/replay certified tested decisions, code integrity, and recording determinism. They did **not** prove selectivity across this continuous market sequence or execute the original market tape through the modified engine.

This original-run chronological audit identifies a **paired systematic failure**:

1. **Heist routing over-admission** — broad windows with insufficient genuine wall alternation qualify and stimulate fast counter-parent entries on small wobbles.
2. **MAIN directional starvation** — even with a current DOWN EMA9 parent, favorable short-term BTC momentum, TP beginning to favor NO, and NO ask around $0.29, the engine offers no positive directionally aligned entry candidate because the session is classified as Heist center and Mountain only wants edges.

The user wants a laid-back, selective Commander, not more trades. We should repair positive directional entry **and** tighten proven false Heist edges, ensuring the Commander still enters genuine mature returns. Do not add a global countertrade veto and do not force a trade quota.

## 7. Recommended acceptance sequence before any next run ZIP

1. Preserve this full original recording as an untouched holdout, including **all 7,652 ordered frames** (not cherry-picked losers).
2. Introduce negative controls for #1 stale level / unearned terminal, #3 falling-knife Heist YES, #4 early expensive NO, #5 fresh-UP NO, and wide-Heist one-visit boxes; positive controls for the prior PID18244 #6 entry/floor, true multi-excursion Heists, recorded #2/#3 floors *separate from their questionable entry timing*, and #6's bounded collection.
3. Add a positive with-EMA9 NO candidate control for 00:21:01, subject to current physical evidence, price, quality and reachable target; keep negative control against late premium mid-leg chases. Distinguish MAIN and TACTICAL lanes under one Commander.
4. Require a **multi-contract chronological Construct** with fixed baseline source and explicit entry/WAIT/exit positions, PLUS the existing 708+ historical tests/Constructs, looking-glass JavaScript, original risk and custody tests, lossless export, and synthetic replay. Verify the candidate from the **extracted ZIP**, compare hashes and use independent untouched holdouts. Do not call the chronological observation audit or synthetic recorder test an exact engine-replay profit result.
5. Only then issue a fresh **45-minute Windows PAPER** candidate and observe a new field run. No live deployment authorization.

**No trading code was modified and no new PAPER release was built in this forensic pass.** The attached machine-readable evidence file `PID23160_SOURCE_BOUND_CHRONOLOGY_2026-11-06.json` provides exact source-bound frame values and recorded event causes.
