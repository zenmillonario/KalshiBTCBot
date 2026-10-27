# Tachyos Tool Rack Strategy Core v1

**Branch:** `tachyos-tool-rack-v1`  
**Base:** preserved R22 positive base `tachyos-r22-pid21520-positive-base-20261023`  
**Status:** DESIGN ONLY — no strategy runtime has been changed by this document.  
**Operating boundary:** Kalshi production data READ ONLY / INTERNAL PAPER ONLY until separately validated.

## 1. Purpose

Rebuild Tachyos strategy authority around the user's actual physical-market doctrine:

> **NAEVYR / EMA9 describes the living physical animal. The market presents a territory. Commander picks up the correct tool for that territory. The tool acts directly inside its own domain. A release/flip ends the territory and hands control to the next one.**

The new core must make simple behavior simple. If an established DOWN Rail owns and a new contract offers cheap NO, the Rail tool must be able to issue the entry without traversing unrelated Mountain, Heist, legacy campaign, consumed-generation, or specialist permission gates.

The strategy layer is intentionally separated from the already-proven mechanical infrastructure: native production data, PAPER book/depth, one Commander, one executioner, account/custody, journal, hard winner floors, finality/settlement, and read-only sidecars.

## 2. Non-negotiable authority model

1. **NAEVYR / EMA9 is the primary physical authority.**
2. **THAERYON / EMA30 is structural context and terrain geometry, never sovereign.**
3. **Territory Router classifies; it does not trade.**
4. **A territory automatically activates its matching tool.**
5. **A tool has authority only inside its territory/lane.**
6. **One Commander receives standardized intents; Commander does not re-run the tool's strategy.**
7. **One executioner books the selected PAPER action.**
8. **Specialists brief only. Navigator, Observer42, Looking Glass, Arc Echo, candles, PT/target, etc. do not veto or create orders.**
9. **Objective safety remains independent:** stale/conflicting feed, wrong ticker, unavailable depth/cash, exact-contract custody, verified finality, already-armed hard winner floors.
10. **Release/flip is the signature ending protocol for every territory.**

## 3. Core pipeline

```
PRODUCTION READ-ONLY MARKET DATA
        |
        v
PHYSICAL READER
  - EMA9 / NAEVYR
  - EMA30 / THAERYON
  - price
  - contract economics
        |
        v
TERRITORY ROUTER
        |
        +---------------------------+
        |                           |
        v                           v
PRIMARY TERRITORY TOOL        COMPATIBLE OVERLAYS
  MountainTool                  ReleaseWatcher
  RailTool                      Value/Protection aides
  MarketHeistTool
        |
        +------------ standardized INTENTS -----------+
                                                     |
                                                     v
                                               ONE COMMANDER
                                                     |
                                               OBJECTIVE SAFETY
                                                     |
                                                     v
                                               ONE EXECUTIONER
```

## 4. Standard tool contract

Every strategy tool implements the same interface:

```python
class StrategyTool:
    def on_activate(self, context): ...
    def on_market_event(self, event, context): ...
    def manage_position(self, position, context): ...
    def on_deactivate(self, context): ...
```

Tools return only standardized intents:

- `ENTER`
- `HOLD`
- `EXIT`
- `RELAY`
- `WAIT`

An intent contains:

```
tool
territory_id
lane
side
action
opportunity_id
max_price
size_tier
reason
source_time
expires_when
```

Commander checks conflicts and objective safety. It must not reinterpret the tool's terrain strategy through legacy campaign/generation rules.

## 5. Territory model

Initial primary territories:

- `ALTERNATING_MOUNTAIN`
- `ROLLING_MOUNTAIN`
- `UP_RAIL`
- `DOWN_RAIL`
- `MARKET_HEIST`
- `COMPRESSION_UNRESOLVED`
- `UNKNOWN`

Release is primarily a **handoff overlay / transitional custody**, not an ordinary competing primary territory.

Possible progression examples:

```
ALTERNATING_MOUNTAIN -> ROLLING_MOUNTAIN -> DOWN_RAIL
DOWN_RAIL -> RELEASE_UP -> UP_RAIL
MARKET_HEIST -> RELEASE_DOWN -> DOWN_RAIL
MOUNTAIN -> RELEASE -> MOUNTAIN / RAIL / HEIST / UNKNOWN
```

A territory remains owner until its own exit/release conditions are met. Local candle color, one wick, one shallow pullback, or a specialist label cannot silently replace the owner.

---

# 6. RailTool

## 6.1 Detection / acquisition

Rail is an open-ended directional chapter. It can be acquired when current physical history shows persistent same-direction rolling structure, typically after roughly 1–2 contracts or equivalent evidence:

- EMA9 and EMA30 broadly parallel;
- both persistently sloped in the same direction;
- EMA9 maintains directional residence relative to EMA30;
- price stair-steps in the same direction;
- pullbacks/rebounds are comparatively shallow;
- recent rolling Mountains repeatedly resolve the same way.

A Mountain may graduate directly into Rail mid-contract. No release is required when the same directional animal simply becomes a Rail.

## 6.2 Direction

- `UP_RAIL` -> MAIN side YES.
- `DOWN_RAIL` -> MAIN side NO.
- Ordinary opposite fades are OFF.
- ReleaseWatcher is the normal mechanism by which the opposite side gains authority.

## 6.3 Sizing

A confirmed Rail MAIN entry uses the **$25 structural PAPER tier** once value rules are satisfied.

## 6.4 Contract-opening participation

If Rail already owns when a new 15-minute contract opens, the Rail tool immediately creates a new ticker-specific economic opportunity.

Initial value ratchet:

- 0–60 sec: enter MAIN side at ask <= .40
- 60–120 sec: enter MAIN side at ask <= .42
- 120–240 sec: enter MAIN side at ask <= .44
- later: <= .50 soft ceiling for a qualified Rail value revisit

An expensive first observation does not consume the opportunity.

Example:

```
DOWN_RAIL
new contract
NO .58 -> WAIT
NO .49 -> WAIT
NO .37 -> ENTER $25 NO
```

## 6.5 Rail activation mid-contract

When a rolling Mountain graduates into Rail, RailTool immediately opens a similar activation-value window. It does not wait for the next rollover.

## 6.6 Profit exit and immediate same-Rail re-entry

**A profitable exit does not end the Rail territory.**

If the position is sold before contract close and the same Rail remains physically intact, the Rail tool immediately rearms its MAIN-side value hunt.

If price offers another comparable qualified value opportunity, **take it again under the same Rail rules**, including immediately after a fakeout.

Example:

```
DOWN_RAIL
NO entered .35
fakeout / protection / profit logic sells NO .55
Rail still DOWN
NO ask later returns .36
-> fresh Rail value opportunity
-> ENTER $25 NO again
```

No arbitrary one-entry-per-contract or one-entry-per-Rail rule.

No simultaneous same-ticker same-side stacking unless separately designed later. The intended cadence is:

```
ENTER -> profit/protection exit -> REARM -> ENTER again
```

Only a genuine release/territory transfer breaks this repeated same-direction Rail cycle.

## 6.7 Rail termination

Rail does NOT end because of:

- ordinary weakening;
- one opposing candle;
- a small serration;
- temporary EMA9 WARMING/None;
- a contract rollover;
- a profitable exit.

Rail ends when ReleaseWatcher / Router establishes an affirmative physical transfer out of Rail or a genuinely different terrain takes ownership.

---

# 7. AlternatingMountainTool

This tool uses the preserved **Clean Mountain Hard Relay** doctrine.

## 7.1 Core rule

**WAIT FOR THE EDGE. NEVER ENTER THE MIDDLE.**

The living EMA9 leg owns the Mountain. Price is noisier and often discovers the larger visible extreme first.

A fresh opposite Mountain entry is sought around the mature physical arc/price edge, not on ordinary mid-leg wiggles.

## 7.2 Edge evidence

Use the proven processes already developed around PID19420:

- recent 3–4 comparable EMA9 leg durations / shapes as context;
- current living EMA9 leg beyond the protected middle;
- strict owner-side price high/low;
- stall for at least one native beat;
- hesitation;
- failed re-extension;
- meaningful retreat;
- price extreme may lead EMA9;
- no perfect tick or visible curl required.

The terminal review window is naturally several one-minute candles wide (historically about 3–6 minutes, scaled by comparable legs), not one exact tick.

## 7.3 Mid-leg

Mid-leg cheapness is not permission.

```
Mountain mid-leg + ask .12 = WAIT
```

unless a different active territory/tool legitimately owns that lane.

## 7.4 Strong release exception

If the edge is still breaking out / breaking down / accelerating, MountainTool does not mechanically fade it.

The ReleaseWatcher remains active. When expansion exhausts/stalls/fails/retraces, Mountain edge relay may activate or the release may hand the market into the next territory.

## 7.5 Hold

After a correctly purchased edge becomes the living new EMA9 leg, ordinary child wobble does not cut it. Hold to the next real mature edge unless objective risk/floor/settlement authority outranks it.

---

# 8. MarketHeistTool

Market Heist is the tool for **compression and sideways repeated action**, not a generic label for every ugly Mountain.

## 8.1 Qualification

Typical evidence:

- bounded/revisited price area;
- repeated outer edges;
- compressed or sideways EMA behavior;
- recurring lower/upper visits;
- enough repetition to establish a real box rather than one local swing.

Unresolved compression = WAIT until a repeatable box or directional release establishes itself.

## 8.2 Trading behavior

When the box is qualified:

- lower edge can support YES renter;
- upper edge can support NO renter;
- repeated genuine edge-to-edge cycles remain tradable;
- frequency is part of the edge.

## 8.3 EMA lean

When EMA9/EMA30 develop a meaningful lean inside the Heist:

- Heist remains a compression/sideways tool;
- the leaning side is **favored**;
- leaning-side entries/holds may receive more confidence;
- the system prepares for the likely same-direction release;
- the opposite edge may remain a tactical renter only while the box itself remains genuinely intact.

The lean is preparation for release, not permission for EMA30 to become sovereign.

## 8.4 Ending

The signature ending of Market Heist is a breakout/drop release.

Once the release is real:

- stop fading the box;
- retire the stale opposite Heist edge;
- ReleaseWatcher takes transitional custody;
- catch the release early;
- Router determines the next territory.

---

# 9. ReleaseWatcher — universal ending overlay

ReleaseWatcher may run simultaneously with MountainTool, RailTool, or MarketHeistTool.

It has no ordinary fading authority. Its job is to prepare for the territory ending so the breakout/drop does not surprise Tachyos.

It watches for:

- failure of the current territory's continuation;
- decisive expansion beyond the territory's physical boundary;
- directional EMA9 transfer;
- failed re-extension of the old owner;
- accepted residence on the new side;
- other already-proven release evidence.

When release becomes affirmative:

```
PRIMARY TOOL -> deactivate / stop creating stale entries
ReleaseWatcher -> transitional custody
Commander -> catch/hold release
Router -> identify next territory
NEXT TOOL -> activate
```

A confirmed release / Leviathan receives more runway than an ordinary renter. First slowdown or one mixed candle must not automatically kill it while directional expansion remains physically intact.

---

# 10. Multiple tools at once

Multiple tools are allowed only through explicit lane compatibility, never voting.

Example compatibility:

| Primary | Overlay / secondary | Allowed? | Purpose |
|---|---|---:|---|
| RailTool | ReleaseWatcher | YES | detect/execute handoff |
| MountainTool | ReleaseWatcher | YES | prepare terminal breakout/flip |
| MarketHeistTool | ReleaseWatcher | YES | catch box breakout/drop |
| RailTool | opposite fade tool | NO | Rail MAIN owns until release |
| MountainTool | MarketHeistTool | CONDITIONAL | only if a genuinely separate qualified box exists; no child label may steal Mountain |
| MarketHeistTool | lean/release bias | YES | favor likely release side |

Each lane owns separate state. One tool cannot consume another tool's opportunity ID.

---

# 11. State isolation

No global strategy state may silently suppress all tools.

Each tool maintains its own namespaced state:

```
RailToolState
MountainToolState
MarketHeistToolState
ReleaseWatcherState
```

Physical territory identity is separate from Kalshi economic slices.

Example:

```
physical_territory_id = DOWN_RAIL_004

economic slices:
  ticker_A
  ticker_B
  ticker_C
```

The Rail is continuous; each ticker can create a fresh contract-opening value opportunity.

A Rail profit exit can create a fresh same-ticker re-entry opportunity if value returns and the Rail remains intact.

---

# 12. Configuration-first design

Tool behavior must be adjustable without editing unrelated strategy files.

Proposed structure:

```
strategy_core/
  router.py
  commander_intents.py
  compatibility.py

  tools/
    rail.py
    alternating_mountain.py
    market_heist.py
    release.py

  config/
    rail.yaml
    alternating_mountain.yaml
    market_heist.yaml
    release.yaml
```

Example `rail.yaml`:

```yaml
size_tier: 25

opening_value:
  first_60s: 0.40
  sec_60_120: 0.42
  sec_120_240: 0.44
  later_soft: 0.50

activation_window_seconds: 240

reentry_after_profit_exit: true
reentry_requires_same_rail_owner: true
opposite_fades: false
rollover_creates_new_slice: true
```

Changing Rail behavior must not require edits to Mountain, Heist, Commander, or execution code.

---

# 13. Nautilus observability requirement

The dashboard must make the strategy auditable in real time.

At minimum display:

```
TERRITORY
DOWN_RAIL #004
owner since 22:31:14

ACTIVE TOOLS
MAIN: RAIL_NO
OVERLAY: RELEASE_WATCHER

CURRENT OPPORTUNITY
KXBTC... contract open
NO ask .32
max .40
size $25
STATUS: ENTER

or

STATUS: WAIT
REASON: ASK .47 > MAX .40

or

STATUS: BLOCKED_OBJECTIVE_SAFETY
REASON: QUOTE_STALE
```

There should never again be a mysterious missed $.30 entry without an exact visible reason.

---

# 14. Acceptance tests — simple behavior first

## Rail — mandatory first proof

**R1. New-contract cheap entry**

Given:
- DOWN Rail already owns;
- new ticker opens;
- no same-ticker position;
- current quote/depth valid;
- NO ask = .30.

Then:
- RailTool emits ENTER NO;
- size tier = $25;
- Commander accepts absent objective safety failure;
- executioner journals the PAPER fill.

If this fails, the entire strategy build fails.

**R2. Expensive then cheap**

```
NO .58 -> WAIT
NO .30 -> ENTER
```

WAIT must not consume the opportunity.

**R3. Profit exit then re-entry**

```
DOWN Rail
ENTER NO
profit/protection EXIT
Rail still DOWN
NO returns to qualified value
-> ENTER NO again
```

**R4. Rollover**

Prior-contract NO holding/history cannot suppress the fresh new-ticker Rail slice.

**R5. Release ends cycle**

After affirmative UP release, no fresh NO Rail re-entry may occur.

## Mountain — mandatory first proof

**M1. Mid-leg cheap quote = WAIT.**

**M2. Mature upper extreme + stall/fail/retrace = NO relay.**

**M3. Mature lower extreme + stall/fail/retrace = YES relay.**

**M4. Strong active release = defer fade.**

**M5. Edge window survives several candles; no perfect curl required.**

## Market Heist — mandatory first proof

**H1. Unresolved compression = WAIT.**

**H2. Qualified lower edge = YES renter.**

**H3. Qualified upper edge = NO renter.**

**H4. EMA lean biases/favors aligned side without destroying real box geometry.**

**H5. Real breakout/drop retires box fade and hands to ReleaseWatcher.**

---

# 15. Build order

1. **Freeze R22 strategy code.** No more strategy hotfixes into legacy authority.
2. **Tool Rack v1 branch and design contract.**
3. **Physical Territory Router in shadow/read-only mode.**
4. **RailTool first.** Do not build other trading tools until R1–R5 pass end-to-end.
5. **AlternatingMountainTool** using preserved PID19420 hard-relay behavior.
6. **MarketHeistTool.**
7. **ReleaseWatcher universal overlay.**
8. **Compatibility / simultaneous-tool lanes.**
9. **Nautilus Tool Rack panel.**
10. **Only then supervised PAPER run.**

## 16. Migration rule

Do not copy the old R22 strategy permission maze into the new core.

Port only what belongs in the new architecture:

- physical measurements;
- proven terrain evidence;
- native feed/book handling;
- PAPER economics;
- custody/journal;
- objective safety;
- hard winner protection;
- verified finality;
- read-only specialists.

Old campaign labels, global consumed-generation rules, hard-edge laws, advisor routing, or opportunity normalization must not be imported unless a specific Tool Rack requirement explicitly needs them.

**A code restriction is not strategy merely because it existed in R22.**
