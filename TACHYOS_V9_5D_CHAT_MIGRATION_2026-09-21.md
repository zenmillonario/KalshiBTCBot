# TACHYOS V9.5D — CHAT MIGRATION HANDOFF
## 2026-09-21 live smoke / forensic training run

### Current branch
`tachys-v9-5d-campaign-authority`

### Important run-state warning
The **currently running V9.5D process was started before the latest EMA9-formation transfer patch**. Do not assume the live process contains commit `1fff4866e142ac8b7b3f25e1347762336a45c56e`.

The current live run should be left untouched until the operator stops it tonight. Treat it as a valuable **pre-EMA9-patch V9.5D smoke/forensic run**.

After the run ends:
1. archive the entire run first;
2. do forensic analysis before code changes;
3. compile today's adjustments together;
4. then pull/restart the updated branch.

Suggested archive name:
`runs\2026-09-21_v9_5d_campaign_authority_smoke_pre_ema9_01`

---

## Architecture entering this run

V9.5D supervises V9.5C Leg Geometry rather than replacing it.

Core ideas already implemented in the branch:
- Campaign Authority / sticky campaign side.
- EMA9 formation-aware campaign transfer patch:
  - standard transfer confirmation = 9 sec;
  - strong early RETURN_SLOPE override = 6 sec only with EMA9 curvature + 6/9 slope + aligned 3/6/9;
  - RETURN_SLOPE alone is warning/preparation, not ordinary transfer authority;
  - normal transfer requires progression into EMA30_APPROACH / TRANSFER / OPPOSITE_BUILD / EXPANSION.
- Rollover Pre-Arm lifecycle with 60 sec TTL and first-use consumption.
- Winner Harvest.
- Exit Court.
- parallel opposite-side positions after authorized transfer.
- current contract side and next-leg prep separated.

Key doctrine:
- EMA30 is the spine.
- EMA9 return slope + transfer + opposite-side build are one leg.
- A cross is a transfer attempt. Separation is the transfer.
- Opposite candle = evidence. EMA9 formation = authority.
- A stale signal is not dead information. It may be the early next play.
- A dead position may be abandoned. The battlefield is never abandoned.
- Do not cut a winner because it became large. Cut it when it stops behaving like a winner.

---

## V9.5C forensic baseline

Full overnight V9.5C archive:
`runs\2026-09-21_v9_5c_leg_geometry_overnight_01`

Results:
- 281 entries / 281 exits
- realized P/L: +$164.67
- wins 132 / losses 133 / flats 16
- win rate 47.0%
- average win +$2.615
- average loss -$1.357
- gross profit $345.21
- gross loss $180.54
- profit factor 1.91
- median hold 25 sec

Main problem:
**Tachyos sees too many legs where there is really one campaign.**

Major stale prearm bug found:
- 128 entries carried V95C_ROLLOVER_PREARM
- only 44 were in first 60 sec of new contract
- 84/128 occurred >60 sec into contract
- fix: PREARM_FRESH -> USED / INVALIDATED / EXPIRED; TTL 60 sec.

Control examples:
- Trade #112: reached +85.7% MFE, eventually exited -14.3% ROI. Negative-control winner giveback.
- Trade #120: +75% -> +100% in ~21 sec with fresh highs; positive-control winner expansion.

---

## Live V9.5D observations from today

### 1. Better overall behavior, but still loss leakage
Operator reported V9.5D is behaving much better than prior version and was already about **+$52** during the live run despite still taking some large losses.

Interpretation for later forensics:
focus less on raw win rate and more on:
- gross winner capture;
- avoidable loss leakage;
- churn reduction;
- how much strong-leg profit was sacrificed to local in/out behavior.

### 2. Still fighting too many candles during a leg
Observed around the late-morning run:
- Campaign Authority reduced ping-pong somewhat.
- Tachyos was still reacting too much to individual opposite candles.
- EMA9 formation must outrank individual candle direction.

Latest branch patch already written but NOT loaded by the running process:
commit `1fff4866e142ac8b7b3f25e1347762336a45c56e`.

### 3. Snake territory / open EMA9-EMA30 dance
Around **11:00 AM onward**, EMA9 began making broad repeated arcs around EMA30:
- repeated crossings;
- separation;
- return;
- new arc;
- larger open oscillatory structure.

Training window:
**11:00 AM–12:15 PM ET approximately**.

Forensics should compare every entry/exit against the whole EMA9 formation, not the triggering candle.

Training law:
**In open EMA9/EMA30 dance, read the formation first and the candle second.**

### 4. Forward EMA flight-path projection
Important new idea:
Do not only ask what EMA9/EMA30 are doing now.

Ask:
**If the current EMA flight path continues, what would BTC candles need to do over the next 3 / 6 / 9 minutes to produce the next expected arc/cross?**

This turns EMA geometry into a forward requirement map.

For each major arc during forensic replay:
- record EMA9, EMA30, gap, curvature, slopes;
- calculate approximate candle path needed over 3/6/9 minutes to compress/cross/expand;
- compare required path to actual BTC behavior;
- assess whether this predicts the next leg early enough to matter.

Key concept:
**pattern projection, not only pattern recognition.**

### 5. Contract boundary does not end EMA flight path
At one contract finish, BTC wick touched/crossed the target, while the EMA9 lower arc had already curled strongly back toward EMA30.

Doctrine:
- contract can end;
- EMA geometry continues;
- rollover should preserve the leg / arc / curvature / EMA gap / lineage;
- only Kalshi target remaps.

At rollover, Tachyos should ask:
**Given the already-existing EMA flight path, what does the new target mean?**

### 6. Counter-sleeve hypothesis
Current V9.5D still sometimes does:
main leg -> local opposite move -> exit -> opposite trade -> exit -> re-enter main leg.

Hypothesis to test:
keep the main campaign position alive and allow a **smaller opposite tactical counter sleeve** for a legitimate local counter-arc.

Required distinction:
- CAMPAIGN_POSITION
- COUNTER_SLEEVE_POSITION

Counter sleeve:
- must not flip campaign_side by itself;
- must not force main position closed;
- one counter sleeve max initially;
- smaller than main campaign in first paper replay;
- exits on local arc completion, Spine return, failure, or quick profit harvest.

Training law:
**Do not abandon the campaign just because the snake bends the other way for a moment.**

### 7. Counter-sleeve management
Operator specified:
- counter sleeves need a tighter stop;
- once around **+35% ROI or better**, collect;
- do not use main Winner Harvest breathing logic.

Training law:
**Campaign positions may breathe. Counter sleeves get paid and get out.**

Exact stop remains a replay variable; do not invent it before measuring actual counter-arc failures.

### 8. Intra-leg transition / mini-chaos mode
New conceptual layer:
a smaller break in the middle of a larger leg can act like a **mini chaos session**.

Candidate progression:
CAMPAIGN_LEG
-> INTRA_LEG_TRANSITION
-> QUICK_TACTICAL_SLEEVE(S)
-> DIRECTION_RESOLVING
-> CAMPAIGN_RESUME

If larger structure truly changes:
-> CAMPAIGN_TRANSFER

The purpose:
- keep main campaign;
- harvest temporary oscillation with small quick tactical positions;
- use the chaos as information about which direction ultimately wins;
- once direction resolves, stop counter-trading and resume dominant leg.

Forensic comparison:
1. actual V9.5D exit/reverse/re-enter;
2. keep main + counter sleeve;
3. keep main and ignore local chaos.

Compare P/L, churn, drawdown, missed main-leg profit, and time-to-direction-recognition.

Training law:
**Use the little chaos to get paid while the market decides; once it decides, stop fighting the leg.**

### 9. Trade #38
Operator clarified Trade #38 was:
**a short local step inside a larger leg**, not simply a generic winner giveback.

It reached roughly +50% and then was allowed to go.

Classify:
LARGER_CAMPAIGN_LEG
-> SHORT_COUNTER_STEP (#38)
-> QUICK_HARVEST
-> CAMPAIGN_RESUME

Forensics:
- exact MFE;
- time above +35 / +50;
- whether larger campaign remained intact;
- where EMA9 turned back into dominant leg;
- whether campaign transfer logic overreacted;
- whether counter-sleeve +35% harvest would have solved it.

Training law:
**A short step inside a larger leg is a tactical harvest, not automatically a new campaign.**

### 10. 3:30 PM repeat — Cobra may have two heads
Operator observed the snake/cobra pattern repeated again around **3:30 PM ET**.

New hypothesis:
**Cobra may have two heads.**

Possible interpretation:
- first head = local bend / counter-step / tactical transition;
- second head = true directional release / campaign-level continuation or transfer.

Compare the late-morning snake window with the ~3:30 PM repeat:
- arc spacing;
- EMA9/EMA30 crossing sequence;
- gap compression/expansion;
- target relation;
- 3/6/9 displacement;
- first decision point vs second decision point.

Test whether:
- first head earns only counter-sleeve authority;
- second head earns campaign-transfer authority.

Training phrase:
**Cobra may have two heads: the first can be the local bend; the second can be the true directional release.**

---

## Winner-management checkpoints

### Trade #38
See above: counter-step inside larger leg; reached ~+50%.

### Trade #120
Positive control:
+75% -> +100% in about 21 sec with fresh highs.
Do not prematurely cap strong expansion.

Winner law:
**At +50%+, a winner must either still be demonstrably expanding or be under active harvest protection.**

---

## Real-vs-paper execution shadow — REQUESTED, NOT YET IMPLEMENTED

The operator asked to add a **live-execution shadow** to paper trading.

Important:
As of chat migration, this was being designed but **has NOT been committed into the engine yet**.

Purpose:
For every paper entry/exit, estimate realistic live execution without changing paper authority.

Desired shadow telemetry:
- signal price;
- contemporaneous executable best ask/bid;
- Kalshi Level-2 depth;
- depth-weighted estimated fill for actual quantity;
- quote at +250 ms;
- quote at +500 ms;
- quote at +1000 ms;
- estimated partial fill / fillability;
- spread/slippage;
- estimated fees;
- paper P/L;
- realistic-live shadow P/L after friction.

The current engine already maintains native Kalshi Level-2 books in `core.kalshi_book` and exposes `core.level2_snapshot()`.

Design principle:
**Paper trading tests the brain. Execution shadow tests the hands.**

The shadow must be observer-only:
- no entry blocking;
- no resizing;
- no exits;
- no changes to paper positions;
- no changes to Campaign Authority.

Suggested new log:
`tachys_execution_shadow_v9_5d.csv`

Suggested scenario labels:
- LIVE_SHADOW_T0
- LIVE_SHADOW_250MS
- LIVE_SHADOW_500MS
- LIVE_SHADOW_1000MS

Need to inspect current Kalshi fee formula before final fee implementation; do not invent fee math if not already encoded in the repo.

---

## Files / docs already updated today

Core engine:
- `tachys_v9_5d_campaign_authority.py`

Command Deck:
- `tachyos_command_deck_v3_2.py`

Specs / lessons:
- `TACHYOS_V9_5D_CAMPAIGN_AUTHORITY_SPEC.md`
- `TACHYOS_FIGHT_LESSONS.md`
- `TACHYOS_V9_5D_SMOKE_TEST.md`

Relevant commits before/through today:
- `1fff486` — EMA9 formation transfer patch
- `2b2dc91` — spec amendment for EMA9 formation authority
- `0b0ce67` — Fight Lesson 009
- `2f27274` — 11 AM open EMA dance forensic window
- `117347e` — counter-sleeve hypothesis
- `cfde16c` — counter-sleeve lesson
- `e1c8fa6` — tighter stop / +35% counter harvest spec
- `7c90e15` — counter harvest lesson
- `3a8ca29` — Trade #38 winner checkpoint
- `b8a5101` — intra-leg transition hypothesis
- `2b813d2` — mini-chaos training lesson
- `a5218c6` — reclassify #38 as intra-leg counter-step

A separate commit was added during migration for the 3:30 PM two-headed-cobra checkpoint.

---

## What the next chat should do when the run ends

Do NOT immediately code.

First:
1. Stop at safe point.
2. Archive all CSV/log outputs.
3. Verify archive file count.
4. Commit/push the archive if that is the existing workflow.
5. Perform full forensic run.

Forensic priorities:
1. whole-run P/L / gross profit / gross loss / PF / win rate / hold times;
2. campaign-by-campaign reconstruction;
3. quantify in/out churn within same larger EMA leg;
4. Trade #38;
5. every +35%, +50%, +75% winner giveback;
6. Winner Harvest timing;
7. compare Campaign Transfer events to actual EMA9 formation;
8. 11:00–12:15 snake/open-dance window;
9. ~3:30 PM repeat / two-headed-cobra hypothesis;
10. counter-sleeve replay;
11. mini-chaos replay;
12. rollover continuity / prearm TTL;
13. check whether parallel opposite positions actually occurred;
14. inspect whether stale prearm is fully gone;
15. derive tighter counter-sleeve stop from evidence;
16. build projected EMA flight-path replay;
17. only after forensics, compile one consolidated V9.5D adjustment package.

Do not rush to V9.5E unless the supervisory architecture itself needs changing. V9.5D can continue to be patched during validation.

---

## Operator preferences / working style
- full downloadable Python file when code changes are delivered;
- step-by-step Windows / GitHub Desktop instructions;
- paper trading only for current research;
- preserve the Command Deck layout;
- reasoned leaps of faith are allowed when geometry strongly supports them;
- favor 3/6/9 timing when supported by evidence;
- do not turn every visual metaphor into a code variable;
- use metaphors like snake/cobra/dragons as research shorthand, then translate them into measurable EMA geometry.
