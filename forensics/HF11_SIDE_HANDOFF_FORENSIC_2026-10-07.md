# TACHYS R15-HF11 — STOPPED SIDE-HANDOFF FORENSIC

## Run
- Engine: `666_lab_20261006_224520_289319_PID8844.zip`
- Observer: `commander_obs42_20261007T024524_502543Z_03392275_records.zip`
- Build: `V9.5D-666-RECONCILIATION-R15-HF11`
- Planned: 120m; actual ~81.1m; operator stopped
- 6 entries / 6 closed
- ALL 6 entries NO
- 4W / 2L
- PAPER gross: **-$1.27**

## Core finding
HF11 did not lack YES perception; it lacked YES execution sovereignty.

Command log:
- 727 side-bearing DECISION rows
- 454 final-side YES decisions; **all WAIT, zero YES ENTER**
- 273 final-side NO decisions; all 6 ENTERs
- 259 rows final NO while `development.side=YES`
- 243 of those also had `wall_side=YES` and `tube_side=YES`

Independent OBS4.2 confirmed the recovery: during the screenshot interval its public EMA spine remained UP while the EMA9/EMA30 gap expanded roughly +$37 to +$53 and observed UP persistence grew from ~475s to >826s.

## Root cause 1 — multi-arc recovery fails tube proof
HF11's early tube proof requires `strong_recent_quality`, including wall efficiency >= .50.

Around the screenshot the actual YES wall had roughly:
- age ~603s
- EMA9 displacement +$97
- retracement 0
- gap +$50
- 30/60/120 EMA9 horizons all YES
- zero spine crosses
- efficiency only ~0.355

Therefore `current_history_strength=False` and `persistent_tube=False`.

Trade #5 is stronger:
- YES wall age ~768s
- displacement +$114.6
- retracement ~0.004
- gap +$54
- development YES
- efficiency ~0.376
- still denied directional tube because age <900 and efficiency <.50

The recovery's repeated arcs/zigzags lowered path efficiency even while the broader direction was clearly UP. The old 900s dependency therefore survives in disguised form for multi-arc directional walls.

## Root cause 2 — WIDE receives opposite-side sovereignty
When `persistent_tube=False`, pilot routing falls directly to active WIDE and assigns `wide.side`.

At an upper edge, WIDE selects NO even when:
- development side YES
- wall/tube side YES
- long EMA9 horizons YES
- EMA9 above EMA30
- geometry is rising / inclined WIDE

Late in the recovery, 138 contradictory NO decisions were specifically `WIDE_ZIGZAG_OUTER_EDGE` while development side was YES.

This violates the intended ONE COMMAND hierarchy. WIDE should locate entries inside the battlefield, not seize side sovereignty from an already directional parent.

## Trade controls
- #1 NO .32: loss -$9.92; inherited stale NO parent while current wall/dev already YES.
- #2 NO .34: loss -$9.86; WIDE upper edge NO while wall/dev YES, positive 30/60 slopes, EMA9 ~-$16 from EMA30 and approaching contact. Independent observer flipped spine UP about one minute later.
- #3 NO .21: +$6.03; profitable counter-leg despite parent YES.
- #4 NO .037: +$2.10; profitable counter-leg, range already INCLINED_WIDE_ZIGZAG.
- #5 NO .49: +$5.20; strongest contradiction: mature YES wall/gap/displacement but WIDE still owns NO.
- #6 NO .27: +$5.18; valid positive control. Parent YES tube was proven and NO qualified explicitly as `TUBE_MICRO_LEG`. Preserve this behavior.

## Repair direction
1. Add **multi-arc directional proof**: mature wall + low retracement + large displacement + aligned 30/60/120 EMA9 + aligned EMA9/EMA30 gap can establish directional parent even when path efficiency <.50.
2. Separate **neutral WIDE** from **inclined WIDE**. Neutral WIDE can trade both edges. Inclined WIDE ordinary entries align with parent direction; opposite edge requires explicit short/micro-leg qualification.
3. Allow **Contact/Handoff Watch on a developing challenger before full tube qualification**. #2 proves requiring `history_strength=True` before contact watch is too late.
4. Preserve explicit opposite `TUBE_MICRO_LEG` behavior (#6).
5. Only after authority repair, replay the 454 YES WAITs to determine whether `ARM_AWAIT_NEW_EXECUTABLE_OBSERVATION` remains too sticky.

## Bottom line
HF11's recovery was visible to both engine internals and OBS4.2, but the hierarchy converted rising multi-arc structure into neutral WIDE because of an efficiency threshold, then let WIDE repeatedly choose NO at the upper edge. Fix battlefield ownership before increasing trade frequency.
