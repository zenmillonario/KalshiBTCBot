# TACHYOS V9.5B — LEVEL-2 BATTLE COUNCIL / INTERMISSION AUTHORITY / THESIS SHIELD

Status: PAPER-ONLY LONG-RUN EXPERIMENT  
Base: V9.5A-RS2 at `3821fdb`  
Authority principle: strategic sovereignty and tactical authority are separate.

## Doctrines preserved

- A dead position may be abandoned. The battlefield is never abandoned.
- Parent ≠ current play.
- Boss remains strategic parent unless sovereignty actually transfers.
- A tactical opposite leg may be authorized without pretending the parent vanished.
- Counter-trend ≠ counter-structure.
- Reject stale price. Arm opposite structure.
- Formation warnings persist through reclassification and contract rollover.
- No single noisy observer receives unilateral entry authority.
- Young theses are not killed by ordinary first-candle noise.
- Emergency / catastrophic invalidation remains allowed.

## Forensic basis

RS2 showed that the main defect was not missing sensors. Existing sensors often recognized useful structure well before Core:

- Trade #20: Flash NO near .57 roughly 152 seconds before Core paid .72.
- The ~2:07 stale-NO block deteriorated sharply and should have armed opposite-intermission research.
- Trade #24: target/structural YES and Flash preceded Core YES by roughly 30–50 seconds and ~16–19 cents.
- Trade #25: Structural target false-break + Formation FAILED/REVERSAL + emerging DOWN arc preceded Core NO by roughly 4–5.5 minutes and ~20–22 cents.
- Formation sometimes detected failure, then forgot it before rollover.
- Catastrophic Risk, Invalidation Persistence and Looking Glass repeatedly argued against fast-fail exits that legacy management executed.
- Reentry Watch often recognized that the battlefield remained alive immediately after the local position was closed.

## V9.5B authority changes

### 1. Level-2 Battle Council

Five evidence families may present a tactical thesis:

1. STRUCTURE — target acceptance / false break / structural bias and score.
2. FORMATION — current reversal/failure plus persistent failure memory.
3. ARC_EMA — arc direction, price/EMA9 relation, EMA30 short and 30-second slope context.
4. FRESHNESS — mature parent leg repriced beyond the V9.5A stale-price thresholds.
5. FLASH — RS1 observer-first directional recognition.

A tactical intermission may be armed only when the candidate side is opposite the strategic parent.

### 2. 3 / 6 / 9 adjudication clock

- ARM threshold: score >= 4 with at least two evidence families and a primary trigger.
- DECISIVE path: score >= 8, >=4 families, persists 3 seconds.
- STANDARD path: score >= 6, >=3 families, persists 6 seconds.
- By 9 seconds an armed thesis must either execute or explicitly STAND_DOWN.
- A >9c AND >25% repricing from the arm ask is a no-chase stand-down.
- Arms expire after 36 seconds.
- Maximum two Level-2 intermission entries per side per contract.
- Same-contract cooldown: 36 seconds.

A primary trigger is one of:
- target false-break/reclaim toward the candidate side;
- persistent/current Formation failure/reversal supporting the candidate;
- stale parent leg;
- exceptionally fresh directional recognition reinforced by another structural family.

### 3. Parent / intermission separation

Telemetry and Command Deck must explicitly show states such as:

- PARENT YES / INTERMISSION NO ARMED
- PARENT NO / INTERMISSION YES ARMED
- PARENT YES / INTERMISSION NO ENTERED
- PARENT NO / INTERMISSION YES STAND_DOWN

An intermission does not flip Boss sovereignty.

### 4. Formation warning memory

A meaningful Formation failure/reversal is persisted for 180 seconds unless contradicted by a genuine sovereignty change. It survives:

- a later FORMING repaint;
- a fresh-contract formation label;
- contract rollover.

Rollover logs must show what structural warning was carried.

### 5. Thesis Shield V1

For the first 120 seconds of a paper position:

- retire the ordinary ANTICIPATION_FAST_FAIL path while the thesis is structurally intact;
- defer ordinary structural / EMA-arc invalidation clocks to the shield window;
- do not suppress true emergency stops, contract close, or proven-profit Treasury defense.

The shield releases early only when catastrophic evidence accumulates, including combinations of:
- target accepted against the position;
- structural bias strongly opposite;
- EMA30 accepted against;
- hold authority INVALIDATE with a large score disadvantage.

This is deliberately narrower than “never exit for two minutes.”

### 6. Honest latency accounting

Measure separately:

- raw observer recognition -> entry;
- coherent Level-2 ARM -> decision;
- coherent Level-2 ARM ask -> entry ask;
- raw recognition ask -> entry ask.

The old Move Lateness clock remains historical telemetry; V9.5B does not treat Core approval as the first possible recognition time.

## New telemetry

- `tachys_level2_battle_council_v9_5b.csv`
- `tachys_thesis_shield_v9_5b.csv`
- `tachys_latency_accounting_v9_5b.csv`
- `tachys_rollover_memory_v9_5b.csv`
- `tachys_run_manifest_v9_5b.csv`

All logs are prospective and designed for forensic replay.

## Command Deck V2 requirements

The Deck remains read-only. It must add:

- Strategic Parent
- Tactical / Intermission Side
- Level-2 state: WATCH / ARMED / DECISIVE / ENTERED / STAND_DOWN
- Council score and independent family count
- arm age and 3/6/9 deadline
- observer-first ask/time/source
- Level-2 arm ask/time
- current ask and price-edge lost/saved
- Formation memory state and age
- Thesis Shield state / age / catastrophic points
- recent Level-2 decisions
- latency table
- rollover memory table
- V9.5B feed health

## Long-run grading

Do not grade by settlement alone. For every Level-2 event, record:

- information available at the moment;
- current ask;
- parent state;
- evidence families;
- decision latency;
- later 15/30/60/120-second quote outcomes;
- whether the same thesis regenerated after a local exit.

The objective is not maximum trade count. It is earlier high-quality action without turning Tachyos into a no-trade machine.
