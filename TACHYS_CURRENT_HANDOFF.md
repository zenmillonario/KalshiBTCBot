# TACHYS CURRENT HANDOFF — 2026-10-06

## READ THIS FIRST
This is the current-state continuity checkpoint for Tachys. Read this file before `COMMANDERS_LOG.md` when resuming in a new chat/session.

This file supplements the historical Commander’s Log; it does not replace the repo history.

## Active test
- Build: **V9.5D-666-RECONCILIATION-R15-HF10**
- Mode: **PAPER ONLY**
- Test length: **1 hour**
- Status at this checkpoint: **RUNNING**
- Engine + OBS4.2 + cockpit were manually confirmed running after launcher-wrapper issues.
- Do **not** change/restart the running engine solely to improve tooling or documentation.
- Released package SHA-256: `043d09c88cbcd311b5000020b2086c96087e9862cc0efe296a9569cc59ccc944`

## Immediate ancestry
HF9 four-hour PAPER result:
- 19 trades
- 11W / 8L
- gross P/L: **-$10.245**
- WIDE_ZIGZAG_EDGE_LEG: **+$17.305**
- continuation family: **-$17.80**
- HF9 proved the one-Command architecture but exposed a two-speed tube timing defect:
  1. tube recognition could arrive too late;
  2. once recognized, price-discovery/value hunting could become paralysis;
  3. stale tube authority could persist too long as EMA9 curled toward EMA30.

## HF10 — ONLY three strategic changes
1. **Earlier persistent-tube recognition**
   - remove rigid dependence on 900s / 15m when recent-contract EMA9 history already proves a persistent tube.
2. **Tube urgency**
   - hunt cheap same-side pullbacks first;
   - when pullbacks are shallow/brief and quickly reclaimed, allow earlier same-side participation so price discovery does not become paralysis.
3. **EMA9 -> EMA30 CONTACT WATCH / earlier tube retirement**
   - as EMA9 curls/approaches EMA30, the old tube loses automatic authority;
   - gather rejection/fakeout/breakthrough evidence;
   - do not require a completed cross;
   - obvious coherent handoff evidence may enter early.

No other strategy family was intentionally broadened in HF10.

## Current constitution — ONE COMMAND
The live strategic hierarchy is:

**EMA9 recent-history / nested geometry -> battlefield + side**
- EMA9 is the highest tactical authority.
- EMA30 is broader branch/spine/context.
- price <-> EMA9 tracks wobble, micro-leg, rejection, pullback and local reclaim.
- EMA9 <-> EMA30 tracks arcs, contact, rejection, penetration, release and handoff.
- briefings/observers are advisory evidence only.
- Market Heist is a specialized tight violent-box tool, not a general alternative authority.

Do not rebuild a parliament of independent YES/NO voters.

## Preserve unchanged unless a future forensic proves otherwise
- first-minute default WAIT / price discovery
- Wide Zigzag regular edge trading
- discounted re-entry
- Lazarus = custody for EXISTING LOSING positions only
- integrated bounded low-price tranche
- whole-position profit management
- Leviathan runner logic where already integrated
- Market Heist specialization
- mission-aware inventory; flat is acceptable
- selective few meaningful entries per contract rather than churn

## Shadow / research registry — evidence, not authority
These branches and observers must not silently become independent trade authorities.

### Known historical repo shadows
The revival branch contains extensive historical observer/shadow data including:
- Looking Glass / Looking Glass Rescue
- Dragon Dance / swirl-compression research
- Failed Regeneration
- Entry Value Field shadow
- Catastrophic Risk shadow
- King's Guard shadow
- battlefield-router shadows
- multitimeframe / EMA geometry / arc-voyage / target-tube / formation / re-entry research

### Newer / external shadow research to preserve explicitly
These are part of current project continuity even if not currently present by filename on this revival branch:
- **ULTRA05** — separate ultra-cheap asymmetric scout/research; not ordinary entry authority.
- **Hurricane / “spaghetti lines”** — multi-path structural forecast/shadow research; zero direct trading authority until explicitly graduated by evidence.
- **OBS5** / newer observer experiments where applicable — research/advisory only.
- spectral-decomposition / frequency research, precession/angle/velocity ideas, and other experimental geometry — research queue unless explicitly promoted.
- EA1/shadow entry-authority work and Leviathan/position-development research retain their historical evidence role unless already deliberately integrated into current lifecycle code.

Rule: **one Command, many senses.** Shadows compete for evidence and possible graduation, not for simultaneous sovereignty.

## HF10 post-run forensic priorities
Archive first. Then examine:
1. Did HF10 recognize a proven tube earlier than HF9 without inventing tubes from ordinary WIDE structure?
2. In a real persistent tube, did shallow/brief reclaimed pullbacks trigger useful same-side urgency before the contract repriced away?
3. Did CONTACT WATCH retire stale tube authority before a completed EMA9/EMA30 cross when evidence was obvious?
4. Did rejection at EMA30 correctly preserve the old tube when the contact failed?
5. Did HF10 preserve the profitable WIDE_ZIGZAG_EDGE behavior rather than suppressing it?
6. Did trade count remain disciplined?
7. Did any shadow research — especially ULTRA05 or Hurricane/spaghetti-path logic — see the tube/contact transition earlier and cleanly enough to merit further offline study?

Do not judge HF10 solely by total P/L; the three surgical behaviors above are the acceptance test.

## Operational continuity
For future chat migration:
1. Read this file.
2. Read `COMMANDERS_LOG.md`.
3. Inspect the latest run/archive commit or supplied run ZIP.
4. Do not re-audit old runs unless a new question requires it.
5. Preserve current authority hierarchy before proposing changes.
6. Update this handoff after each completed forensic/release so chat memory is never the only source of truth.

## Git discipline
- Branch: `tachys-v9-5d-666-revival-lab`
- Documentation updates may occur while a PAPER run is active.
- Do not alter live strategy source for the active run.
- Run packages/results should be archived with immutable hashes and a short forensic checkpoint before the next strategic change.
