# TACHYOS CHAT MIGRATION — 2026-09-21 V9.5D LIVE RUN

## Immediate takeover instruction

Continue the Tachyos BTC/Kalshi 15-minute PAPER-TRADING project on branch `tachys-v9-5d-campaign-authority`.

**Do not modify the currently running engine before the user stops the run tonight.**
Archive the run first, then perform a full forensic review, then compile all adjustments together.

Important: the live process currently running was launched BEFORE the latest EMA9-formation authority patch. Therefore treat this as a **pre-patch V9.5D smoke/observation run**. The branch contains newer notes/patches than the live process.

Also important: the proposed **execution-shadow layer** for paper-vs-live realism has been discussed but was NOT yet implemented or committed. The prior coding attempt was interrupted before any engine write. Keep it on the post-run build list.

## Project / branch state

- Repo: `zenmillonario/KalshiBTCBot`
- Active branch: `tachys-v9-5d-campaign-authority`
- Engine: `tachys_v9_5d_campaign_authority.py`
- Dashboard: `tachyos_command_deck_v3_2.py`
- V9.5C overnight archive is frozen/immutable.
- V9.5D supervises V9.5C Leg Geometry; do not rewrite the perception layer casually.

Latest important code patch already on branch:
- `1fff486` — EMA9 formation authority patch
- `2b2dc91` — spec amendment
- `0b0ce67` — Fight Lesson 009

Latest observation/note commits this chat:
- `2f27274` — 11:00–12:00 open EMA dance forensic window
- `117347e` — counter-sleeve hypothesis
- `cfde16c` — counter-sleeve fight lesson
- `e1c8fa6` — tighter stop / +35% harvest rule for counter sleeves
- `7c90e15` — matching fight lesson
- `3a8ca29` — initial Trade #38 winner-giveback checkpoint
- `b8a5101` — intra-leg transition / mini-chaos hypothesis
- `2b813d2` — matching training lesson
- `a5218c6` — reclassify Trade #38 as short counter-step inside larger leg
- current handoff adds 3:30 PM two-headed cobra checkpoint to Fight Lessons.

## Core doctrine to preserve

- EMA30 is the Spine.
- The EMA9 return from one side of EMA30 and build on the other side are one leg.
- A cross is a transfer attempt. Separation is the transfer.
- Opposite candle = evidence. EMA9 formation = authority.
- Parent/Boss/Hand/MTF are context, not tactical veto.
- A stale signal may be the early next play.
- A dead position may be abandoned. The battlefield is never abandoned.
- Do not cut a winner because it became large. Cut it when it stops behaving like a winner.
- Finish the current contract with the current side; prepare the next leg before everyone else sees it.
- Contract boundaries are clock overlays, not structural resets.

## V9.5C forensic baseline

Frozen overnight V9.5C run:
- 281 trades
- realized P/L +$164.67
- win rate ~47%
- avg win +$2.615
- avg loss -$1.357
- profit factor 1.91
- core problem: Tachyos sees too many legs where there is really one campaign.

Key controls:
- Trade #112: reached +85.7% MFE then exited -14.3%; proves a winner cannot be allowed unlimited giveback.
- Trade #120: +75% to +100% in ~21 sec; proves strong expansion must be allowed to breathe.
- stale ROLLOVER_PREARM bug: 65.6% of prearm-tagged entries occurred >60s into contract; V9.5D adds TTL/consume lifecycle.

## V9.5D architecture already built

- Campaign Authority with sticky side.
- Winner Harvest.
- Exit Court.
- Rollover Pre-Arm lifecycle TTL 60s.
- Current-contract side separate from next-leg prep side.
- Parallel opposite-side transition support after confirmed authority.
- Campaign logs, Winner logs, Exit Court logs, Pre-Arm logs.
- Command Deck V3.2 shows Campaign, Pre-Arm, Winner Harvest, Exit Court.

## Latest EMA9 authority correction

The live smoke showed V9.5D still fighting individual opposite candles too much.
Correction already committed to branch but NOT loaded in the current running process:

- standard campaign transfer confirmation = 9 sec;
- strong formation override = 6 sec;
- bare RETURN_SLOPE is warning/preparation only;
- ordinary transfer waits for EMA30_APPROACH / TRANSFER / OPPOSITE_BUILD / EXPANSION;
- early RETURN_SLOPE leap allowed only with EMA9 curvature + 6/9-sec slope + non-opposing 3-sec slope + full 3/6/9 alignment.

Training law: **Opposite candle = evidence. EMA9 formation = authority.**

## Today's live observations to review tonight

### 1. 11:00 AM onward — snake territory / open Dance of Dragons

From roughly 11:00 ET onward, EMA9/EMA30 entered broad oscillatory geometry: repeated arcs, crossings, separation, return, renewed arcs. Use 11:00–12:00 ET as a named forensic training window.

Question: did Tachyos react to individual candles while the larger EMA9 formation remained coherent?

Training principle: **In open EMA9/EMA30 dance, read the formation first and the candle second.**

### 2. EMA flight-path projection

New predictive idea: instead of only reading current EMA state, ask:

**If the present EMA9/EMA30 flight path continues, what would BTC candles need to do over the next 3 / 6 / 9 minutes to create the next arc/cross?**

This turns EMA geometry into a forward requirement map. During forensics, for each major arc calculate the approximate BTC path required to bend EMA9 into the next expected formation, then compare with what actually happened.

Important rollover doctrine: the contract can end but the EMA flight path does not. Preserve EMA geometry/leg lineage and remap only the new Kalshi target.

### 3. Mid-leg in/out churn

Current V9.5D behaves better than V9.5C but still exits/re-enters during local bends inside a larger leg.

New hypothesis: preserve the main campaign position and allow a separate tactical **COUNTER SLEEVE** for a legitimate local opposite arc.

Required distinction:
- CAMPAIGN_POSITION
- COUNTER_SLEEVE_POSITION

Counter sleeve rules to test:
- smaller than main campaign initially;
- tighter stop than campaign;
- tactical only; cannot flip campaign_side;
- local arc failure exits quickly;
- **+35% ROI or better = collect**;
- do not use main Winner Harvest breathing logic;
- once dominant leg resumes, close counter sleeve and keep campaign.

Training law: **Campaign positions may breathe. Counter sleeves get paid and get out.**

### 4. Intra-leg transition / mini-chaos mode

User's idea: smaller breaks in the middle of a larger leg can be treated like the older chaos session between major legs.

Candidate state flow:
`CAMPAIGN_LEG -> INTRA_LEG_TRANSITION -> QUICK_TACTICAL_SLEEVE(S) -> DIRECTION_RESOLVING -> CAMPAIGN_RESUME`

or if structure truly changes:
`-> CAMPAIGN_TRANSFER`

Use quick profits while price fluctuates deciding direction. Once EMA9/EMA30 formation + 3/6/9 reveal the winner, stop fighting the leg.

Tonight compare:
1. actual exit/reverse/re-enter behavior;
2. keep main campaign + tactical counter sleeves;
3. simply wait through the mini-chaos with no counter sleeve.

Measure P/L, churn, drawdown, missed main-leg profit, and time-to-direction-resolution.

Training law: **Use the little chaos to get paid while the market decides; once it decides, stop fighting the leg.**

### 5. Trade #38

Trade #38 was clarified by the user as a **short step / counter-arc inside a larger leg**, not merely a generic +50% winner.

Observed: it reached about +50% and Tachyos let it go.

Desired classification:
`LARGER_CAMPAIGN_LEG -> SHORT_COUNTER_STEP (#38) -> QUICK_HARVEST -> CAMPAIGN_RESUME`

Review whether the correct behavior was a tactical +35%+ harvest while the main campaign position stayed open.

Training law: **A short step inside a larger leg is a tactical harvest, not automatically a new campaign.**

### 6. Live performance

User reported current run was approximately **+$52** despite still having some large losses. Interpretation: underlying edge appears better than execution quality; focus post-run work on reducing leakage/churn and preserving winners rather than inventing more signals.

Primary metric to inspect: **gross winner capture vs avoidable loss leakage**.

### 7. 3:30 PM repeat — possible two-headed cobra

The snake/cobra-like EMA9 pattern repeated around **3:30 PM ET**.

New forensic hypothesis: **the cobra may have two heads** — the first apparent terminal curl/head may not be the final release; a second similar head/arc may form before the larger directional move resolves.

Compare the earlier snake window with the ~3:30 PM repeat for:
- arc amplitude/duration;
- EMA9 curvature;
- EMA30 slope and spacing;
- target height;
- whether first head created false resolution;
- whether second head preceded true release;
- whether projected 3/6/9 EMA flight-path math could anticipate it.

Working law: **Do not assume the first terminal curl is the final release.**

## Paper vs live execution shadow — POST-RUN BUILD ITEM

User asked to add a paper-vs-live execution shadow. This is NOT implemented yet.

Desired observer-only behavior:
- never place/block/resize/exit trades;
- for each paper entry/exit record the theoretical signal price and realistic executable market conditions;
- use Tachyos's existing Kalshi Level-2 book to estimate depth-weighted fillability;
- capture immediate and short-latency scenarios, ideally 0 / 250ms / 500ms / 1000ms;
- estimate spread/slippage, partial fills, and fees;
- compute realistic-live net P/L beside paper P/L;
- later compare `Paper P/L` vs `Simulated-live P/L`.

Important: do not assume a displayed top price fills the entire quantity. Use available book depth when possible.

## Tonight's required workflow

1. User stops the live V9.5D process at a safe point.
2. Archive the entire run BEFORE pulling/changing code.
3. Preserve pre-patch V9.5D smoke separately.
4. Run full forensic reconstruction by trade and by campaign.
5. Review named windows: 11:00–12:00 ET, Trade #38, 3:30 PM repeat, any user-marked trades.
6. Evaluate Campaign Authority, Winner Harvest, Exit Court, Pre-Arm TTL, parallel transition, and formation authority.
7. Quantify in/out churn inside larger legs.
8. Replay counter-sleeve + intra-leg mini-chaos hypotheses.
9. Study projected EMA flight-path math.
10. Design/implement execution-shadow observer.
11. Compile all justified adjustments together rather than patching live one-by-one.
12. Pull/restart only after the consolidated build is ready.

## User preferences

- Full downloadable Python files when code changes are needed.
- Step-by-step Windows/GitHub Desktop guidance; do not skip steps.
- Keep paper trading only for now.
- Aggressive but bounded research; reasoned early leaps are allowed.
- Prefer 3/6/9 timing when evidence supports it.
- Avoid overusing poetic names in architecture; use them as visual shorthand/training terms, not as substitutes for measurable states.
- User likes the current Command Deck layout; do not redesign unnecessarily.

## Last instruction from user

Let the current run continue until tonight. Then archive it and compile all adjustments from the forensic review. The next chat should take over from this document.
