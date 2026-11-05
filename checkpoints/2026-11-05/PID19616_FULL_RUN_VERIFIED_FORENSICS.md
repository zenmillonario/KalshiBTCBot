# TACHYOS PID19616 — verified new-run forensics (2026-11-05)

**PAPER only. Forensic checkpoint, NOT a new release or strategy authorization.** Original exact engine replay was **not** performed. Do not confuse this 8-trade PID19616 ledger with 6-trade positive PID18244.

## Provenance
- Run: `TOOL_RACK_PAPER_20261105T223220Z_PID19616`.
- 6 of 6 separately SHA-256 validated raw numbered parts reconstruct the **556,916,480-byte** 444-member source ZIP, verified SHA-256 `22028d8a01034bd76f66caf164ff622f660a0d5b7cc76dca765218d21fe117e5`.
- Capture 8641/8641 calls, zero drops; complete. Original machine run flat, no inventory, stop `PAPER_ENTRY_WINDOW_COMPLETE_FLAT`.
- Source release: `TACHYOS_PID18244_PARENT_CUSTODY_PROTECTION_45M_PAPER_20261105`. Source SHA-256 Commander `34d93123421310b6c3cfbb4480333b33b578e105614636cd0ab884f3cc4ff6ef`; paper_runtime `c02af95418283848190a54a23c49a8dcbf984bc74324616c9208b6cc8f46a100`; candidates `98b186de6845510bac7528ee7f0584b73b1157c8f943d830eaa5c9acf2243572`.
- Cash $1,000 → **$959.8284**, gross **−$30.6016**, fees **$9.57**, net **−$40.1716**. Eight closed positions. These are recorded simulated PAPER fills, **not live orders or alternate-strategy outcomes**.
- Local comprehensive report `PID19616_FULL_RUN_FORENSICS_2026-11-05.md` SHA `648c2ac1f4e26562404736eaf27640c6cc6506a032b4f4fa2cefb4ff938ee20a`; source-bound entry evidence `PID19616_SOURCE_BOUND_EVIDENCE_2026-11-05.json` SHA `75e5e91ede578b0f1d5e69bf9b47792fe0dfb24a65629aace1462f55217b8ab8`. These are conversation artifacts; binary archive not committed.

## Exact 8-trade PAPER ledger, ET
| # | Side | Entry → exit | Net | Physical admission/close |
|---|---|---|---|---|
| 1 | YES, 38 | .250 → .057, 17:38:08–17:39:31 | **−$7.9840** | `HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED` to Lazarus loss, DOWN EMA9 parent |
| 2 | YES, 228 | .041 → .0653, 17:39:40–17:40:55 | **+$3.9304** | true cheap Heist excursion, armed floor |
| 3 | YES, 213 | .110 → 0 at 17:45 settlement | **−$24.8900** | `COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN`, false loose level-match |
| 4 | YES, 49 | .190 → .290, 18:01:37–18:02:11 | **+$3.6600** | oversold tactical edge, armed floor |
| 5 | YES, 31 | .300 → .380, 18:05:15–18:07:22 | **+$1.5000** | armed floor after provisional release-custody promotion |
| 6 | YES, 94 | .100 → .130, 18:08:29–18:09:29 | **+$1.4700** | small Heist excursion, armed floor |
| 7 | YES, 208 | .045 → .004, 18:10:15–18:12:33 | **−$9.2180** | cheap counter-DOWN Heist fade during expanding parent |
| 8 | NO, 47 | .510 → .360, 18:15:11–18:18:12 | **−$8.6400** | expensive first-minute inherited NO parent, fading 60s momentum |

## Priority recorded causal controls for future patch
**A. PID19616 #3 false-support + exceptional-size negative.** At seq 2029 BTC $75,742.38, EMA9 $75,769.35, EMA30 $75,824.36; GAP **−$55.01**, parent DOWN, TP ownership UNRESOLVED, no confirmed YES parent. 6s BTC +$39.54 and 9s +$44.18 were only short bounce. Completed low reference $75,774.90 was 786.3s old, current BTC was **$32.52 below** the referenced prior low but recognition tolerance `max($12, 25% range180)` treated it as a support level-match, admitting 213 YES $.11 with $25 tier. Never assert a hypothetical no-entry profit. Candidate: tighten *physical level location* before first-class MAIN level-match return; preserve previously earned PID18244 #6 NO near upper level (+$4.93 relative to anchor, 9s real DOWN turn) and approved PID17224 genuine transfer.

**B. PID19616 #7 cheap counterparent negative; #1 similar early weak return.** #7 seq 7707 YES $.045 entered under DOWN parent, GAP **−$147.27**, BTC9 **−$82.52**, BTC30 **−$197.59**, EMA9 30s **−$52.70**. `HEIST_PARALLEL_STALLED_EDGE_RETURN` signaled while owner remained NO ROLLING_MOUNTAIN; brief 6s stall did not establish earned upward edge. #1 similarly YES $.25 while physical parent NO, 9s BTC still down. Investigate **genuine bounded Heist** versus fresh/expanding directional parent, but preserve valid #2/#4/#5/#6 tactical returns. No blanket fade veto.

**C. PID19616 #8 aging Rail expensive opening negative.** Seq 8301, new contract 18:15:11 ET age 11.5s, NO $.51 $25 tier entered via `COMMANDER_OBSERVED_INHERITED_PARENT_FIRST_MINUTE_CONTINUATION`. Historical NO residence **2564.63s ≈2.85 contracts**; EMA9 gap **−$140.28**, TP favored NO, but 60s BTC progress was only **−$1.90** with 60s range $53.41; 30s BTC −$21.23. This was old-direction recognition without renewed meaningful acceleration. Mature >2.5-contract parent invokes *transition watch*, not forced reverse and not unconditional early 51c commitment. Candidate: require fresh, meaningful with-side current 60s movement (source-bound) for exceptional opening, preserving approved PID15740 53c opening with BTC60 +$52.15 / range60 $56.58. Do not abolish operator-authorized first-minute continuation.

**D. Custody observation #5.** At ~18:07:21, YES TACTICAL promoted to MAIN release-custody with gap and rack parent still NO, release candidate YES / `handoff_confirmed=false`, short-term EMA9 positive. Previous executable floor closed lot ~1s later, no observed damage. Audit against true current parent-release qualification; do not claim a regression loss from this event.

**E. Preserved positive controls.** #2, #4, #5, #6 all earned profits through ALREADY_ARMED_EXECUTABLE_BID_FLOOR. Existing prior-run PID18244 #6 NO .0877→.35 +$64.2741 positive Commander extreme, PID21672 trade #4 whole-lot protection, PID17588 inherited opening, independent MAIN/TACTICAL and Nautilus remain mandatory.

## Validation/control status
- Already-installed original PID18244 27 focused PID18244 / PID15740 / PID17224 tests **pass** in the captured source.
- **No new source edits or trading ZIP produced in this forensic pass.** Next step requires explicit user authorization for new *positive Commander admission* rules; then source-bound neg/pos tests, full 46-module suite + mandatory historical Constructs, native JS Looking Glass, capture/Windows/export, synthetic three-way replay, strictly extracted full ZIP/hash preflight. Do not claim full original replay, hindsight profits, or 45-minute Windows success without evidence.
