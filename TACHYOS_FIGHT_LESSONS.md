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


## Lesson 004 — A proven winner cannot be donated back

A trade that reaches +50% MFE has proven the thesis enough to deserve a hard profit floor.

Whole-Leg Geometry can justify staying through normal pullbacks, but it cannot justify turning a +50%, +60%, or +75% winner into a routine loss.

Training ladder:

- +50% MFE -> protect at least +25% ROI
- +60% MFE -> protect at least +35% ROI
- +75% MFE -> protect at least +50% ROI

**Training law:**  
**Let the leg breathe before +50. Protect the money after +50.**

