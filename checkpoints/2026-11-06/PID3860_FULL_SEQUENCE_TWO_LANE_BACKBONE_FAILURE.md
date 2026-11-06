# TACHYOS PID3860 — Full original-run forensic and two-lane backbone acceptance

**2026-11-06 · PAPER ONLY · Original source verified / strategy behavioral acceptance FAILED.** No strategy code patched and no new run ZIP authorized. This branch contains evidence notes, not the 522 MB original recording.

## Provenance
- Original `TOOL_RACK_PAPER_20261106T071752Z_PID3860`, complete 6/6 individual transport parts and SHA-256 verified, 521,641,014 bytes, SHA-256 **`1422d691d76e22a17454ba9f042eae97f36214933f5b032c2fa7ffc414ddb8fb`**, 456 ZIP members CRC PASS.
- 7,779/7,779 recorded engine calls with zero drops; 7,776 decisions in continuous sequence/hash-pointer chain; 67/67 sealed source hashes verified. Captured Commander, heist geometry, and PAPER runtime identical to validated PID23160 release.
- Six closed PAPER trades, cash $1000 -> $927.7838, gross -$62.7462, fees $9.47, **net -$72.2162**. Original-engine replay / altered-engine fills NOT performed.
- #1 NO .4->.2 -$5.25; #2 NO .17->.003 -$9.755; #3 YES .39->.31 -$6.82; #4 YES .17->.093 -$12.816; #5 YES .044->.025 -$12.588; #6 YES .0024->settlement 0 -$24.9872.

## Backbone compliance is the problem, not missing strategy doctrine
User restates the original backbone: **MAIN trades with the living EMA9 leg and HOLDS while structurally sound; TACTICAL Market Heist independently trades real bounded swings; qualified tactical positions can transfer to MAIN; ONE Commander coordinates.** A mature parent-scale arc extreme allows anticipatory opposition BEFORE EMA9 curls, rather than chasing a spent return. This applies especially across rollover. A small child-arc wobble or false level is not a mature edge. Momentum may be less important inside *genuine* compression/repeated walls and at a fresh defended support/resistance test, not at an obsolete/broken level.

User independently made a manual NO return following a reported >$400 UP arc from the preceding contract, entering early at rollover and holding, and reports a further manual trade; these are **human examples only**, not original bot orders or hypothetical fills.

## Source-bound failures
1. **02:45:05 rollover:** actual source YES $.39, EMA9 signed gap +$113.21 but BTC9 -$20.50 and BTC60 **-$90.77**. Inherited UP parent `price_still_advancing=false`, `owner_price_retreating=true`, `mature_old_leg=true`, nevertheless `spent=false` because the EMA gap had not collapsed; `COMMANDER_MOUNTAIN_ROLLOVER_TARGET_REACHABLE` bought the old UP direction. Source: `strategy_core/commander_candidates.py` around lines 2317-2367 and `_inherited_leg_still_live` around 1153-1211. Target reachability plus old gap does not justify the fresh opening YES as price is sharply declining. Mature arc-top NO evaluation must be possible before curl, but quote/risk/runway proof remains essential.
2. **02:39:14 TACTICAL NO** against contemporaneous UP EMA9: entry metadata `lean_side=YES`, `lean_aligned=false`; BTC60 +$25.20. The available lean was advisory and did not prevent a weak upper-fade renter. Preserve real mature edges and prior PID18244 #6 positive entry rather than blanket countertrend vetoes.
3. **MAIN participation absent:** 804 DOWN_RAIL and 751 UP_RAIL original decision frames, **zero actual entries in either Rail**. Not all are valid missed trades: many prices were expensive or inventory was active. Need positive admission and full parent-scale hold when physically earned rather than forced trade count.
4. **Same-contract position policy serializes executions:** `commander.py` ~1224-1256 prevents same-side duplicate lot and waits for opposite-side flatten before corrective entry. Parallel MAIN/TACTICAL **evaluation** is present, but two simultaneous same-contract holdings are not currently supported. This needs separate explicit risk authorization if desired; source-supported custody transfer is the near-term priority.
5. **Repeated unearned late YES** (#4, #5, #6) while no UP parent had been confirmed; #6 bought $.0024 counter to a current DOWN EMA9 leg 128 seconds before close, 9,728 contracts but only ~$23.35 position cost, settled zero. Cheapness and a few seconds of bouncing are not edge proof in a wide directional Mountain.
6. **#3 high-water winner protection question:** entry YES .39, observed full-lot peak bid .69 (about +77% gross) with `floor_bid=None`, eventually sale .31. Investigate independently; retain historical winning whole-lot floors.

## Chronological Construct result
A new **read-only** Construct scanned **all 7,776 original decision frames** after exact ZIP/hash/CRC/source authentication, and generated six observed FAIL controls: no Rail entries, against-lean Heist NO, contrary-price rollover YES, inherited gap not marked spent, late cheap counterparent YES, and favorable high-water without armed floor. **Source integrity PASS; original-run behavioral acceptance FAIL.** A read-only old-run audit is **not** a modified-engine full replay and does not support alternative fills/returns.

Conversation artifacts (verified exact local bytes):
- `PID3860_FULL_RUN_FORENSICS_AND_TWO_LANE_ACCEPTANCE_2026-11-06.md` SHA `c625e5a4fb00a70de69f11f6c98da4bfafd282a02ac6a7c3e4c3fe2b03af8fb4`
- `PID3860_CHRONOLOGICAL_BEHAVIORAL_CONSTRUCT.py` SHA `c1028395e035d12e871de5eb4a87c9dd86b24ff6193ee6bf6db3fb1a6d298404`
- `PID3860_CHRONOLOGICAL_AUDIT_RESULT_2026-11-06.json` SHA `9073c079442d99a5f09f4e83263d9f345bf2bf0977d2aebd36daa4d00d10634b`

## Mandatory next gate
Frozen backbone / one Commander / EMA9 sovereignty / EMA30 spine / MAIN with-wind hold + independently evaluating real TACTICAL Heist and qualified transfer / genuine anticipatory parent-scale Mountain extreme / prior successful winners and quote-floor controls. No new generic entry shortcuts. Before another 45m PAPER release, demonstrate both positive participation and patient counter-leg restraint across *entire recorded chronological sequences*, with separate historical Construct, extracted ZIP tests, capture/export, actual Looking Glass JS, strict source hashes and, if claimed, genuine matching-runtime exact engine replay. Do not fabricate profits.
