# TACHYOS FIGHT LESSONS

These are battlefield lessons learned from live paper runs. They are training examples for future Tachyos revisions, not mythology names and not a substitute for the canonical Leg Geometry doctrine.

## Lesson 001 — The target can lie for a few seconds

**Context:** final ~60 seconds of a 15-minute Kalshi BTC contract.

A brief BTC cross of the contract target is not automatically a true transfer of settlement control.

A common pattern is:

\`ACTIVE LEG -> PRICE TOUCHES/CROSSES PT -> FAST RECLAIM -> ORIGINAL SETTLEMENT SIDE RESTORED\`

Tachyos must ask:

- How many seconds remain?
- How far did BTC cross the target?
- How quickly was the target reclaimed?
- How long did price actually hold on the other side?
- Did Whole-Leg Geometry transfer, or did only price flick through PT?
- What do the 3/6/9-second displacement and efficiency say?
- Are candle wicks rejecting the crossed side?
- Is the current Kalshi price still offering a useful reversal entry?

**Training law:**  
**A target cross is evidence. A target reclaim can prove the cross was a fakeout.**

Inside the final minute, settlement-control processes must move to the front of tactical authority.

## Lesson 002 — Do not wait for the old position to die before joining the new leg

When the market turns, the opposite leg can become valid before the existing position's Whole-Leg Exit Gate has formally released the old trade.

Paper Tachyos must be allowed to hold a short transition overlap:

\`OLD POSITION STILL OPEN + NEW OPPOSITE LEG CONFIRMED -> OPEN NEW OPPOSITE POSITION\`

The positions are managed independently.

This is not an automatic hedge. The opposite side must earn normal tactical authority.

**Training law:**  
**Entry authority for the new leg must not be held hostage by exit authority for the old position.**

Restrictions for the experiment:

- one active position per side during the transition;
- separate trade IDs and leg IDs;
- separate P/L accounting;
- no automatic liquidation of the old position just because the new side entered;
- PAPER ONLY until forensic validation.

## Lesson 003 — The whole leg outranks the flicker

Sub-arcs, one candle, one target touch, or one brief tactical score flip do not automatically create a new leg.

The return slope from one side of EMA30 and the build on the other side are one continuous leg.

**Training law:**  
**Do not confuse a momentary event with a completed transfer of the leg.**

## Lesson 004 — Large winners breathe until they stall

Reaching +50%, +60%, or +75% MFE does not mean Tachyos should automatically trail tightly or take profit.

If the trade is still expanding, making new highs, and the active leg is still paying, **let it breathe**.

The danger is not a large winner.

The danger is a large winner that stops advancing and begins hovering.

Training behavior:

- +50% MFE arms awareness, not an automatic exit;
- fresh highs / continued expansion reset any harvest timer;
- if the winner hovers or slows for roughly a 9-second confirmation window, harvest becomes authorized;
- at +75% or higher, still let a genuine breakout continue, but treat a plateau more seriously;
- Leg Geometry, 3/6/9 displacement, target progress, quote velocity, rejection wicks and opposite-side build all help decide whether the move is still alive.

**Training law:**  
**Do not cut a winner because it became large. Cut it when it stops behaving like a winner.**


## Lesson 005 — A cross is not a new leg

When price and EMA9 hover around the EMA30 Spine, the market may cross back and forth many times without actually transferring direction.

Tiny alternating candles, repeated EMA touches/crosses and rapidly changing tactical scores are a **transfer zone**, not permission to rapid-fire both sides.

Training behavior:

- declare \`TRANSFER_ZONE_UNRESOLVED\`;
- stop fresh side entries while the market is knitting around the Spine;
- require increasing separation plus aligned 3/6/9 displacement;
- require roughly 6 seconds of directional persistence before confirming the escape;
- after confirmation, use roughly 9 seconds of side-flip hysteresis so one tiny recross cannot immediately reverse authority;
- a fast target fakeout/reclaim or genuinely violent opposite displacement may override the hysteresis.

**Training law:**  
**A cross is a transfer attempt. Separation is the transfer.**


## Lesson 006 — Pick the most likely side and make the market disprove it

Anti-ping-pong does not mean permanent neutrality.

If the geometry already shows the top of a small upper mountain and EMA9 is rolling down toward the Spine, the most likely next leg is NO.

Take NO and stay with NO unless price/EMA geometry **breaks north** strongly enough to invalidate it.

Mirror the rule at a lower valley for YES.

Do not flip because of:

- one EMA touch;
- one micro-cross;
- one alternating candle;
- one temporary tactical-score change.

Flip only after real invalidation.

**Training law:**  
**Choose the most likely leg. Stick with it until the market proves it wrong.**


## Lesson 007 — Finish this contract while preparing the next leg

Near expiry, the side most likely to settle the current contract and the side most likely to form the next leg can be opposite.

Example:

- BTC is still deeply below target with two minutes left -> current contract remains NO;
- the lower EMA9 geometry is extended and the next natural motion may be the return slope back toward EMA30 -> prepare YES for the next leg.

Tachyos should shout the preparation clearly:

\`PREPARE YES — NEXT LEG LIKELY — HIGH CONVICTION\`

without confusing that with an instruction to abandon the current NO immediately.

If the turn begins early, parallel transition authority may enter the new side before the old position exits.

**Training law:**  
**Finish the current contract with the current side. Prepare the next leg before everyone else sees it.**


## Forensic checkpoint — Trade #120: +75% to +100%

Review trade **#120** specifically.

Question to answer:

**Did the winner-harvest process correctly let the trade breathe from roughly +75% toward +100% because strength remained intact?**

Verify:

- timestamp when +75% MFE was first reached;
- whether a harvest/plateau timer armed at that point;
- whether fresh highs reset/cancelled that timer;
- 3/6/9-second displacement through the +75% -> +100% transition;
- EMA9 Leg Geometry state during the transition;
- Target Height progression;
- quote velocity / Kalshi price acceleration;
- whether opposite-side score or rejection evidence ever became strong enough to justify harvesting;
- whether the final +100% outcome came from continued expansion rather than a lucky last-second spike.

Desired behavior:

\`+75% MFE -> STRENGTH STILL PRESENT -> WINNER_EXPANDING -> HARVEST TIMER RESET -> LET IT BREATHE -> +100%\`

This case is a positive control for Lesson 004.

**Do not tighten Winner Harvest in a way that would have cut #120 early if the evidence shows the move was still expanding with strength.**


## Lesson 008 — Five trades can still be one campaign

Live case: trades #122 through #126 occurred inside roughly the first five minutes of one contract and alternated:

\`YES -> NO -> YES -> NO -> YES\`

The market was hovering around the same target / EMA transfer region.

This is the signature of **campaign fragmentation**: Tachyos may be recognizing every small counter-move as a brand-new leg.

Training behavior:

- choose the most-likely campaign side;
- keep the campaign side sticky through ordinary micro-crosses;
- require actual separation / target acceptance / Leg Geometry transfer before flipping;
- after two rapid same-campaign flips without a true escape, stop alternating entries until the market proves a side.

**Training law:**  
**One wobble does not deserve five theses.**


## Lesson 009 — The candle is not the formation

A single opposite candle can warn Tachyos that the active leg may be changing, but it does not deserve campaign authority by itself.

Use EMA9 formation as the guide:

- RETURN_SLOPE = warning / preparation;
- EMA30_APPROACH = stronger evidence;
- TRANSFER / OPPOSITE_BUILD = legitimate campaign-transfer territory;
- a strong early turn may act sooner only when EMA9 curvature, 6/9-second slope, and 3/6/9 displacement agree.

Do not fight every candle.

**Training law:**  
**Opposite candle = evidence. EMA9 formation = authority.**


## Forensic training window — 2026-09-21 11:00–12:00 ET

Operator observation: from roughly 11:00 ET onward, BTC entered what we call **snake territory / open Dance of Dragons** — broad EMA9/EMA30 oscillatory geometry with repeated large arcs, crossings, separation, returns, and renewed arcs.

Use this window during the post-run forensic review.

Questions:

- Did Tachyos mistake individual opposite candles for campaign transfers?
- Did the EMA9 formation remain readable even while candles alternated?
- Where did EMA9 complete a meaningful upper/lower arc versus merely crossing the Spine?
- Did Campaign Authority preserve the most-likely side long enough?
- Did entries occur near formation turns or only after candles made the move obvious?
- Did Exit Court abandon positions on local candle noise while the larger formation remained intact?
- Did 3/6/9 displacement help distinguish a true formation turn from a transient candle?
- Were there moments where waiting several more seconds for EMA9 confirmation would have materially improved entry quality?

Training principle:

**In open EMA9/EMA30 dance, read the formation first and the candle second.**
