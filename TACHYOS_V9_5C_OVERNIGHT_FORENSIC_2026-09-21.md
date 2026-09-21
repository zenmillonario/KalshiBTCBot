# TACHYOS V9.5C OVERNIGHT FORENSIC — 2026-09-21

Archive: `runs/2026-09-21_v9_5c_leg_geometry_overnight_01`  
Frozen pushed head at review start: `ce392e3eb2bc8f4a7dedb40aaf8b05cbaab6f183`

## Executive result

- 281 completed paper trades
- realized P/L: **+$164.67**
- 132 wins / 133 losses / 16 flat
- win rate: **47.0%**
- gross profit: **$345.21**
- gross loss: **$180.54**
- profit factor: **1.91**
- average winner: **+$2.615**
- average loser: **-$1.357**
- median hold: **25 seconds**

V9.5C is profitable, but the overnight edge was produced with excessive tactical fragmentation.

## Exit-path evidence

### V95C_EXIT_OPPOSITE_LEG_CONFIRMED
- 238 exits
- total P/L: **+$23.254**
- 100 wins / 123 losses
- average ROI: **+0.75%**

Conclusion: this path is far too chatty to remain the primary exit authority without a campaign-level persistence filter.

### EARLY_TAKE_PROFIT_50
- 9 exits
- total P/L: **+$84.026**
- 9 wins / 0 losses
- average ROI: **+67.3%**

This one path produced roughly half of total run P/L. Do not simply remove the behavior. Replace the fixed legacy concept with dynamic Winner Harvest: allow continued expansion, harvest plateau/stall.

### Legacy local exits
- CORE_SWIRL_PROFIT_LOCK: 7 exits, +$21.67
- CORE_SWIRL_SNIP_TP_22_5: 4 exits, +$24.02
- EMA9_ARC_BROKEN: 7 exits, **-$15.08**, no winning exits
- Bird-in-hand 23->15: 6 exits, +$0.23 aggregate but included catastrophic Trade #112 giveback

Conclusion: profit-taking behavior has value; local arc-break authority does not. Whole-leg / Winner Harvest must replace the useful profit behavior without restoring sub-arc panic exits.

## Campaign fragmentation

There were **197 side flips** between sequential entries within contracts.

- 155 flips (78.7%) occurred within 60 seconds
- 104 occurred within 30 seconds
- 47 occurred within 15 seconds

39 of 45 contracts had at least 6 trades.

Those high-churn contracts:
- 264 trades
- +$118.99
- +$0.451 per trade

The six lower-churn contracts:
- 17 trades
- +$45.68
- +$2.687 per trade

Low-churn trade efficiency was roughly six times higher.

Worst example:
- KXBTC15M-26SEP210630-30
- 11 trades
- 7 side flips
- 5 flips within 60 sec
- -$8.20

Conclusion: V9.5C needs campaign authority above individual Leg Geometry flips.

## Leg Geometry diagnosis

The problem is not only routing.

In churn windows the Leg Geometry engine itself minted new leg IDs too quickly.

Example around Trades #122-126:
- LG00447 NO
- LG00448 YES
- LG00449 NO
- LG00450 YES
- LG00451 NO
- LG00452 YES
- LG00453 NO
- LG00454 YES
- LG00455 NO

These changes occurred around the same EMA/target transfer region.

Current V9.5C can create a new leg after a short opposite EMA9 return-slope confirmation. Three seconds is too permissive in a transfer/chop region.

Required correction:
- distinguish `LEG_CANDIDATE` from `CAMPAIGN_SIDE`
- a return slope can prepare the next leg without immediately replacing campaign authority
- mint a new campaign side only after genuine separation / target acceptance / structural break
- make top/bottom mountain geometry sticky until true north/south invalidation

## Target reclaim diagnosis

`TARGET_RECLAIM_REVERSAL` currently has too much authority outside the final minute.

Trades #123, #124 and #126 were exited by rapid target reclaim / opposite-leg logic in the first five minutes.

Near PT early/mid-contract, a quick cross and reclaim is common noise.

Required correction:
- outside the final 60 sec, target reclaim is evidence, not standalone exit authority
- require 6/9 sec persistence plus campaign/leg invalidation
- inside final 60 sec, settlement control may move to the front as already specified

## Rollover pre-arm bug

`ROLLOVER_PREARM` persists too long after rollover.

Example:
- Trade #125 entered at 03:03:40, about 220 sec into the contract
- decision still logged `V95C_ROLLOVER_PREARM`

Other later examples also carried rollover pre-arm well beyond the immediate opening window.

Required correction:
- pre-arm is one-shot / consumable
- expire after first authorized use, invalidation, or a short post-rollover TTL
- never leave a rollover bonus active several minutes into the contract

## Trade #112 — winner donation failure

NO entry:
- entry 0.21 at 02:07:17
- current target still favored YES by about $47.60
- +47.6% almost immediately
- +76.2% at 02:07:42
- MFE eventually +85.7%
- exited 02:08:45 at **-14.3% / -$2.13**

This is the single worst winner-management failure in the run: about 100 percentage points from MFE to exit.

Important context:
- the position was a tactical NO while BTC remained on the YES side of target
- target never became a durable NO settlement advantage during the big profit
- after a large counter-target tactical winner stalls, tolerance should shrink

Desired future behavior:
- MFE >= 50 activates Winner Harvest Watch
- continued fresh highs / expansion reset timer
- counter-target winner gets shorter stall tolerance
- once +75% stalls without target acquisition or continued expansion, harvest rather than donate

## Trade #120 — positive winner control

YES entry:
- entry .44 at 02:45:15
- target already favored YES by +$53.47

Progress:
- +52.3% at 02:45:34
- +61.4% at 02:46:03
- +77.3% at 02:46:12
- +90.9% at 02:46:16
- +100% at 02:46:33
- exit +105.45% at 02:47:12
- MFE +106.59%

Target Height improved strongly through the expansion:
+53 -> +78 -> +106 -> +128 -> +153 -> +232.

Conclusion:
- taking +75% would have been too early
- fresh highs and improving Target Height correctly argued for continued breathing
- after reaching +100%, the trade waited about 39 sec to gain only another ~5.5 percentage points
- future Winner Harvest should reset on fresh highs, but once extreme profit stops progressing for ~9 sec, harvest

Positive-control law:
`+75 -> strength persists -> fresh highs -> reset harvest timer -> +100 -> plateau -> take it`

## Trades #122-126 — campaign fragmentation

All within the first ~5 minutes of one contract:

- #122 YES .44 -> .60, +36.36%
- #123 NO .55 -> .53, -3.64%
- #124 YES .58 -> .46, -20.69%
- #125 NO .56 -> .59, +5.36%
- #126 YES .50 -> .48, -4.00%

The engine repeatedly minted opposite leg IDs and repeatedly used `EXIT_OPPOSITE_LEG_CONFIRMED`.

Notable:
- #124 entered with 60-sec trend efficiency only ~0.024
- #126 entered with efficiency ~0.126
- target was oscillating close to PT
- the region was a campaign under dispute, not a sequence of clean independent legs

Required correction:
- campaign side persists through micro-return slopes
- after two unconfirmed side flips in five minutes, increase burden of proof
- require true separation / acceptance / geometry break before further alternation

## New architecture priorities

### P0 — Campaign Authority
Add `campaign_id`, `campaign_side`, `campaign_state`, `flip_count`.

Leg candidates may form inside a campaign without automatically changing the campaign side.

### P0 — Whole-Leg exit must become truly centralized
No legacy reason should execute merely because the gate decides an exit is allowed.

The central gate should select the final reason/action itself.

### P0 — Winner Harvest
Replace rigid profit-floor concept:
- >=50% MFE arms harvest awareness
- fresh MFE highs / expanding geometry reset timer
- plateau/slowdown authorizes harvest
- target-aligned expanding winners breathe
- counter-target winners receive shorter plateau tolerance
- extreme +90/+100 winners do not need perfection once progress stalls

### P0 — Target reclaim context
- early/mid contract: evidence only
- final minute: settlement authority
- target reclaim alone must not create rapid side flips in ordinary time

### P0 — Expiring rollover pre-arm
One-shot and TTL-limited.

### P1 — Most-likely sticky side
Top mountain rolling south => NO until true north break.
Bottom valley rolling north => YES until true south break.

### P1 — Transfer-zone hysteresis
Micro-cross does not equal transfer.
Separation confirms transfer.

### P1 — Parallel transition positions
Allow new opposite paper position before old position exits once new campaign/leg authority is truly confirmed.

### P1 — Next-leg preparation
Maintain separate:
- current-contract side
- next-leg prep side

Carry high-conviction prep through rollover.

## Promotion / demotion board

### Keep / strengthen
- Leg Geometry concept
- Target Height
- dual-side tactical scoring
- Whole-Leg authority concept
- rollover continuity
- next-leg preparation
- dynamic Winner Harvest
- final-minute settlement authority

### Restrict
- raw leg-ID changes
- target reclaim outside final minute
- rollover pre-arm duration
- opposite-leg exit authority
- regeneration confirmation in tight transfer zones

### Demote / remove as direct authority
- EMA9_ARC_BROKEN
- bird-in-hand as final authority
- local profit-lock/sniper exits once Winner Harvest replaces them
- any legacy exit path that bypasses central campaign/whole-leg reasoning

## Bottom line

V9.5C proved the new direction is real: profitable run, profit factor 1.91, large asymmetric winners, successful early next-leg entries.

But the engine still trades the **microstructure of the leg** too often instead of the **campaign**.

The next version should not add more observers.

It should make existing perception sticky:
- one campaign
- one most-likely side
- candidate opposite leg can prepare
- side changes only on real invalidation/escape
- large winners breathe while expanding
- harvest when progress stops
- target becomes dominant only when time makes settlement dominant
