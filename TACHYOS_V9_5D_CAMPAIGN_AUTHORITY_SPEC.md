# TACHYOS V9.5D — CAMPAIGN AUTHORITY / WINNER HARVEST / STATE LIFECYCLE

Mode: PAPER ONLY

Base:
- V9.5C Leg Geometry
- frozen overnight reference: runs/2026-09-21_v9_5c_leg_geometry_overnight_01
- forensic reference head: ce392e3
- development base head: 83a894c

## Why V9.5D exists

V9.5C proved Leg Geometry can find real asymmetric winners, but it over-fragmented one battlefield into many short-lived theses.

Overnight evidence:
- 281 exits, +$164.67 realized
- 47% win rate
- median hold ~25s
- 238 exits via V95C_EXIT_OPPOSITE_LEG_CONFIRMED, contributing only about +$23.25
- 39 of 45 contracts had 6+ trades
- stale ROLLOVER_PREARM remained usable deep into contracts
- trade #112 reached +85.7% MFE and finished negative
- trade #120 correctly expanded from +75% toward +100% and should remain the positive control

V9.5D does not add a new perception system. It supervises existing perception.

---

## 1. Campaign Authority

A Campaign is the current most-likely tactical side across local sub-arcs.

States:
- CAMPAIGN_NONE
- CAMPAIGN_YES
- CAMPAIGN_NO
- CAMPAIGN_TRANSFER_ARMED_YES
- CAMPAIGN_TRANSFER_ARMED_NO
- CAMPAIGN_TRANSFER_CONFIRMED_YES
- CAMPAIGN_TRANSFER_CONFIRMED_NO

The campaign side is sticky.

A local Leg Geometry state may move against the campaign without automatically changing campaign authority.

### Campaign establishment

Campaign side may be established by a coherent composite:
- current Leg Geometry side/state
- EMA9 slope and separation from EMA30
- 3/6/9-second displacement agreement
- target relationship / reclaim / acceptance
- wick rejection
- structural event / formation support
- rollover preparation if fresh

### Transfer burden

A campaign transfer requires all of:
1. candidate opposite side has score lead >= 2;
2. 3/6/9 displacement agrees with candidate side;
3. EMA9 is separating from EMA30 in candidate direction OR target reclaim/acceptance is decisive;
4. evidence persists at least 6 seconds;
5. no immediate recross through the Spine;
6. existing campaign is materially invalidated, not merely challenged.

After a confirmed transfer:
- apply 9-second side-flip hysteresis;
- a second opposite flip inside that window requires emergency-strength evidence.

### Same-campaign flip control

Track:
- campaign_id
- campaign_side
- campaign_age_sec
- campaign_flip_count
- seconds_since_last_flip
- true_transfer_confirmed

If campaign_flip_count >= 2 inside 5 minutes without a true transfer:
- suppress new alternating entries;
- keep current campaign side;
- require a fresh escape event.

Training law:
**One wobble does not deserve five theses.**

---

## 2. Rollover Pre-Arm lifecycle

ROLLOVER_PREARM is temporary memory, never standing authority.

States:
- PREARM_NONE
- PREARM_FRESH
- PREARM_USED
- PREARM_INVALIDATED
- PREARM_EXPIRED

Rules:
- create pre-arm only in final 2–3 minutes when next-leg evidence exists;
- after rollover, pre-arm TTL = 60 seconds maximum;
- consume after first successful use;
- invalidate immediately if new target / geometry contradicts it;
- expire at 60 seconds even if unused;
- never authorize another entry after PREARM_USED;
- never survive multiple campaign flips.

Audit:
- prearm_side
- prearm_created_ts
- prearm_age_sec
- prearm_state
- prearm_use_count
- prearm_invalidated_reason

Training law:
**Memory may cross the fencepost. Authority may not live forever.**

---

## 3. Most-Likely Scenario / Transfer-Zone behavior

Near EMA30, do not default to neutral if one side clearly owns the shape.

If at top of a small upper mountain and EMA9 rolls down:
- MOST_LIKELY_NO

If at bottom of a small lower valley and EMA9 rolls up:
- MOST_LIKELY_YES

TRANSFER_ZONE_UNRESOLVED is used only when shape advantage is genuinely balanced.

A cross is not a transfer.

A transfer requires separation.

Training law:
**Choose the most likely leg. Stick with it until the market proves it wrong.**

---

## 4. Winner Harvest

Winner Harvest starts awareness at +50% MFE but does not cap a winner.

States:
- WINNER_NONE
- WINNER_EXPANDING
- WINNER_HARVEST_WATCH
- WINNER_PLATEAU_9S
- WINNER_HARVEST_EXIT

### Continue holding

Keep WINNER_EXPANDING when:
- fresh MFE highs continue;
- quote/bid advances meaningfully;
- favorable 3/6/9 displacement remains alive;
- target height continues improving;
- campaign remains aligned;
- opposite transfer is not confirmed.

Every meaningful fresh high resets the harvest timer.

### Harvest

When MFE >= +50%:
- if no meaningful new MFE high for ~9 seconds AND
- quote velocity slows or tactical displacement decays AND
- campaign/leg is mature, flattening, or beginning return behavior,
then authorize WINNER_HARVEST_EXIT.

At MFE >= +75%:
- continue to let strength run;
- plateau evidence gets greater weight;
- do not demand perfection after the move has effectively finished.

Positive control:
- trade #120 must remain held through the +75% -> +100% expansion because fresh highs persisted.

Negative control:
- trade #112 must not be allowed to give +85.7% MFE back into a loss.

Training law:
**Do not cut a winner because it became large. Cut it when it stops behaving like a winner.**

---

## 5. Exit Court

All ordinary exit reasons become proposals.

Priority:
1. emergency / settlement integrity
2. Winner Harvest exit
3. confirmed Campaign transfer
4. terminal target/time invalidation
5. legacy exit proposals
6. HOLD

Legacy proposals include:
- V95C_EXIT_OPPOSITE_LEG_CONFIRMED
- EMA9_ARC_BROKEN
- Bird-in-Hand variants
- Swirl profit-lock/snips
- King Guard
- legacy giveback/trailing exits

No ordinary proposal may flatten a position by itself.

V95C_EXIT_OPPOSITE_LEG_CONFIRMED is demoted:
- local opposite leg may arm a campaign transfer
- only confirmed campaign transfer may force ordinary opposite-side exit

---

## 6. Parallel transition

Entry authority for a newly confirmed opposite campaign is independent of exit timing.

In PAPER mode:
- one active position per side may coexist during a confirmed transition;
- new opposite side may enter before old side is cut;
- positions get separate IDs and exit courts;
- no unlimited pyramiding.

Parallel transition is blocked in TRANSFER_ZONE_UNRESOLVED.

---

## 7. Next-leg preparation

Maintain:
- CURRENT_CONTRACT_SIDE
- NEXT_LEG_PREP_SIDE
- NEXT_LEG_CONVICTION

They may be opposite.

When high conviction appears near expiry:
- print PREPARE YES/NO — NEXT LEG LIKELY — HIGH CONVICTION
- carry preparation through rollover as PREARM_FRESH
- then enforce the pre-arm lifecycle above

---

## 8. Audit files

New:
- tachys_campaign_authority_v9_5d.csv
- tachys_winner_harvest_v9_5d.csv
- tachys_exit_court_v9_5d.csv
- tachys_prearm_lifecycle_v9_5d.csv
- tachys_run_manifest_v9_5d.csv

Campaign fields:
- timestamp
- ticker
- campaign_id
- campaign_side
- campaign_state
- campaign_age_sec
- candidate_side
- candidate_since
- candidate_age_sec
- yes_score
- no_score
- score_lead
- leg_id
- leg_side
- leg_state
- target_height
- target_event
- btc_change3
- btc_change6
- btc_change9
- ema_gap
- gap_delta6
- transfer_confirmed
- flip_count
- seconds_since_last_flip
- ruling
- reasons

Winner fields:
- trade_id
- side
- entry_ask
- current_bid
- roi
- mfe
- seconds_since_mfe_high
- last_mfe_high
- campaign_side
- leg_state
- target_height
- btc_change3
- btc_change6
- btc_change9
- winner_state
- harvest_timer_age
- ruling
- reasons

Exit Court fields:
- trade_id
- proposed_reason
- proposal_source
- winner_state
- campaign_side
- campaign_transfer_state
- target_terminal_state
- court_ruling
- final_action

Prearm fields:
- prearm_side
- created_ts
- age_sec
- state
- use_count
- invalidated_reason
- originating_leg_id
- from_ticker
- to_ticker

---

## 9. Required replay checks before long run

Mandatory cases:
- #112: large winner donation
- #120: +75% -> +100% expansion
- #122–126: first-five-minute fragmentation
- worst churn contract KXBTC15M-26SEP210630-30
- stale ROLLOVER_PREARM examples >180s into contract
- final-minute target fakeout
- next-leg pre-arm case before rollover

V9.5D is not ready for an unattended run unless:
- stale pre-arm cannot fire after 60 seconds;
- ordinary opposite-leg signals cannot directly flatten;
- campaign flip count is visible;
- Winner Harvest holds #120-type expansion and harvests #112-type plateau;
- no rapid YES/NO ping-pong occurs without true transfer.


## EMA9 Formation Confirmation Amendment

Observed during V9.5D smoke testing: Campaign Authority was still reacting too quickly to individual opposite candles.

Correction:

- one opposite candle is evidence, not authority;
- `RETURN_SLOPE` alone may arm awareness but does not normally confirm a campaign transfer;
- normal transfer waits for EMA9 formation progression into `EMA30_APPROACH`, `TRANSFER`, `OPPOSITE_BUILD`, or `EXPANSION`;
- early transfer remains possible only when EMA9 itself gives strong confirmation through curvature + 6/9-second slope + aligned 3/6/9 movement;
- standard campaign-transfer persistence is 9 seconds;
- strong EMA9-formation override may confirm after 6 seconds.

Training law:

**Opposite candle = evidence. EMA9 formation = authority.**

## Counter-sleeve hypothesis — preserve campaign, trade the local opposite arc separately

Observed during the live V9.5D smoke run: even with Campaign Authority, Tachyos still exits/re-enters too often during a larger coherent leg because local opposite EMA9 arcs are being treated as reasons to abandon/rebuild the main position.

For forensic testing tonight, evaluate a separate **counter sleeve**:

- keep the main campaign position open while the campaign thesis remains valid;
- allow one smaller opposite-side paper position when EMA9 forms a legitimate local counter-arc;
- the counter sleeve is tactical only and must NOT change campaign_side;
- the counter sleeve must NOT force the main position to exit;
- one counter sleeve maximum at a time;
- counter sleeve should be smaller than the main campaign position in the initial paper test;
- counter sleeve exits on local arc completion, return to the Spine, counter-arc failure, or short winner plateau;
- when the main campaign resumes, close the counter sleeve and keep the campaign position;
- if the larger campaign truly transfers, the ordinary Campaign Transfer process takes over and the counter position can become the new campaign-side position only through explicit state promotion.

Required distinction:

CAMPAIGN_POSITION
vs
COUNTER_SLEEVE_POSITION

Audit questions:
- how many V9.5D exits/re-entries would have been unnecessary if the original campaign position had remained open?
- could the opposite local arc have been traded profitably as a small independent sleeve?
- did the counter arc end at/near EMA30 or another repeatable geometric landmark?
- did keeping the main position open improve total campaign P/L and reduce churn?

Initial paper-only sizing idea for replay:
- main campaign stake remains unchanged;
- counter sleeve begins at roughly one-third of main stake, subject to replay evidence.

Training principle:

**Do not abandon the campaign just because the snake bends the other way for a moment. Trade the bend separately if it earns it.**

### Counter-sleeve management amendment

Counter sleeves use a different management regime from the main campaign position.

- Counter sleeves are tactical, not runners.
- Use a tighter stop than the campaign position.
- Exit quickly if the local counter-arc fails, EMA9 reclaims back into the campaign direction, or the counter move loses separation.
- Once a counter sleeve reaches roughly +35% ROI or better, collect the profit rather than applying the main Winner Harvest breathe/plateau logic.
- Do not let a profitable counter sleeve turn into a large giveback while waiting for whole-leg confirmation.
- The exact numeric stop distance remains a replay variable; do not invent a fixed stop until the forensic review measures the counter-arc behavior.

Initial paper rule for replay:

`COUNTER_SLEEVE >= +35% ROI -> HARVEST`

Training principle:

**Campaign positions may breathe. Counter sleeves get paid and get out.**

## Intra-leg transition mode — harvest local chaos without abandoning the campaign

Live-run hypothesis: the smaller breaks inside a larger leg may deserve a temporary mode analogous to the older chaos session between major legs.

Purpose:

- preserve the main campaign position and campaign_side;
- recognize a short period where price is fluctuating while the next local direction is being decided;
- allow quick tactical counter-sleeve trades during that uncertainty;
- use the resulting EMA9/EMA30 behavior as information about which direction ultimately wins;
- end the transition mode as soon as the next directional formation becomes clear.

Candidate state progression:

CAMPAIGN_LEG
-> INTRA_LEG_TRANSITION
-> QUICK_TACTICAL_SLEEVE(S)
-> DIRECTION_RESOLVING
-> CAMPAIGN_RESUME

or, if the larger structure truly changes:

-> CAMPAIGN_TRANSFER

Entry evidence for transition mode should include several of:

- EMA9 begins making small alternating arcs around or toward EMA30;
- candle direction alternates and follow-through shortens;
- 3/6/9 displacement loses sustained agreement;
- target distance oscillates rather than expands;
- tactical YES/NO scores alternate without a confirmed campaign transfer;
- EMA9 formation still belongs to the larger campaign geometry.

Management:

- campaign position remains open while campaign thesis is valid;
- counter sleeves are smaller tactical positions;
- tighter stop than the main campaign;
- collect counter-sleeve profit at roughly +35% ROI or better;
- do not apply main Winner Harvest breathing logic to these sleeves;
- no counter sleeve may itself change campaign_side;
- stop opening quick sleeves once EMA9 formation, separation, and 3/6/9 displacement establish the next directional leg.

Forensic test:

Replay today's mid-leg in/out sequences and compare:

1. actual V9.5D behavior: exit / reverse / re-enter;
2. hypothetical behavior: keep campaign position + trade temporary counter sleeves;
3. hypothetical behavior: no counter sleeve, simply wait for formation resolution.

Measure total P/L, number of trades, drawdown, missed main-leg profit, and time to recognize the eventual direction.

Training principle:

**Use the little chaos to get paid while the market decides; once it decides, stop fighting the leg.**

## Execution Reality Shadow — paper brain vs simulated live hands

V9.5D now includes a ZERO-AUTHORITY execution shadow. It does not place, block, resize, flip, cancel, or exit any paper trade.

For every successful paper entry and exit it records execution scenarios at:

- 0 ms
- 250 ms
- 500 ms (primary comparison)
- 1000 ms

The shadow walks the locally maintained Kalshi Level-2 book to estimate:

- executable top price;
- displayed depth;
- partial-fill quantity;
- depth-weighted average fill price (VWAP);
- worst consumed price;
- entry and exit fee estimates;
- fee/slippage/depth-adjusted simulated-live P/L;
- friction versus paper P/L.

New logs:

- `tachys_execution_shadow_quotes_v9_5d.csv`
- `tachys_execution_shadow_trades_v9_5d.csv`

Fee model: isolated configurable estimate using Kalshi's general event-contract taker formula (0.07 x multiplier x contracts x P x (1-P)), conservatively rounded upward to cents. Series-specific fee changes must be checked before any real-money deployment.

Important: if the Level-2 book is unavailable, the shadow records the top quote but DOES NOT invent fillable depth. In that case simulated-live quantity remains unfilled/unknown rather than assuming the entire paper order would have filled.

Research question:

**How much of paper Tachyos' edge survives realistic spread, latency, depth, partial fills, and fees?**

## Arc-angle / snake-gait hypothesis — normalize geometry, not chart pixels

Live observation on 2026-09-21: much of the session behaved like snake territory, but with wider EMA9/EMA30 separation than some earlier chop windows.

Do not use the literal visual chart angle because zoom and price-axis scaling can change it. Measure a normalized geometric equivalent.

Candidate measurements:

- **EMA9 pitch**: EMA9 slope over 3/6/9 seconds normalized by recent BTC range;
- **Arc width**: peak absolute EMA9-EMA30 gap normalized by range60 or another stable local volatility measure;
- **Turning intensity**: EMA9 curvature normalized by recent range;
- **Spine pitch**: EMA30 slope over 6/30 seconds, normalized similarly;
- **Arc symmetry / deterioration**: compare successive upper and lower arc amplitude, duration, pitch, and curvature;
- **Gap compression/expansion rate**: how quickly EMA9 approaches or separates from EMA30.

Research question:

If the current snake gait persists, can the prior 1-3 arcs define an expected envelope for the next arc's pitch, width, duration, and direction? Then ask what BTC candle path would be required to remain inside that envelope.

Potential use:

- distinguish harmless mid-leg bends from true campaign transfer;
- tune counter-sleeve timing;
- identify unusually steep arcs that deserve faster action;
- identify shallow/deteriorating arcs that should not trigger aggressive entries;
- carry the same flight-path model across contract rollover.

Training principle:

**The useful angle is not what the chart looks like. It is the normalized rate at which EMA9 bends around the Spine.**
