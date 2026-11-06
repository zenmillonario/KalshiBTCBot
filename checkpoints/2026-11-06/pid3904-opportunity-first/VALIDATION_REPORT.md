# TACHYOS Opportunity-First validation record

## Acceptance state

The final source was frozen at 2026-11-06T15:38:14Z after the bounded local-return exit fix. The complete Commander audit passes all 10 semantic controls. The fresh full engine Construct completed all 6,965 captured calls and passes all 11 semantic controls across 6,963 decision frames. Both accepted receipts match the exact final 68-file source set and have been copied into the runnable program. The first interrupted run and preview remain excluded. The parent has reported source full CHECK PASS (791 tests and 55 supplemental tests, plus the required historical Constructs); extracted-package delivery gates remain the parent's final release step. Native Windows launch and field execution are outside this validation.

## Baseline and recording integrity

The original source was retained separately from the candidate. Its 67 sealed strategy files and all 78 recorded source inventory files match the original recording. The unchanged tape reader verified the complete tape hash chain, delta decoding and lifecycle: one constructor, 6,963 process calls and one close, with no dropped calls. The original paper journal also passed verification.

The baseline full CHECK completed successfully: 742 tests plus the mandatory historical Constructs. It was run as:

```text
python -B CHECK_TOOL_RACK_PAPER.py --require-manifest --workers 3
```

Evidence: `baseline_preflight.txt`, `baseline_full_check.txt`, `baseline_integrity.json`.

The capture was made on Windows 11 with CPython 3.14.7. This workspace uses Linux and CPython 3.12.14. These validations do not constitute an exact native Windows replay.

## Complete Commander comparison

All 6,963 recorded decision frames were checked in their original order, retaining original timestamps, source generation, physical metadata, native quotes, original specialist proposals and actual original inventory/mission consumption. The old and candidate Commanders run in separate processes with persistent independent memory. No hypothetical orders, fills, exits or profit are created by this audit.

The baseline shadow admits seven of the eight historical entry-frame proposals. One quote-window timing case differs. Therefore the old shadow is a layer-specific comparison, not proof of whole-engine equivalence.

The frozen candidate passes all 10 semantic controls. There are eight qualified opportunity identities and three admission frames. The two callbacks at 5,381 and 5,382 concern the same physical opportunity; they are not two claimed trades. Original bad-entry frames 2,932, 3,192, 6,295 and 6,466 are denied. Controls permit an independently earned same-parent MAIN candidate on the correct side, rather than requiring unconditional WAIT. All 4,747 repeated native callbacks create no new physical watch identity.

| Source frame range | Species | Side | Qualified callbacks | Admission callbacks | Observed no-entry reason |
|---|---|---|---:|---:|---|
| 448–448 | MAIN_EMA9_REJOIN | NO | 1 | 1 | Admitted |
| 1263–1282 | REAL_HEIST_RETURN | NO | 20 | 0 | CURRENT_CONTRACT_SAME_SIDE_INVENTORY_NO_DUPLICATE: 20 |
| 1283–1462 | REAL_HEIST_RETURN | NO | 50 | 0 | COMMANDER_TACTICAL_FADES_PAUSED: 45; COMMANDER_HEIST_FRESH_SPROUT_REQUIRES_CAUSAL_TURN: 5 |
| 1639–1647 | REAL_HEIST_RETURN | NO | 9 | 0 | COMMANDER_HEIST_FRESH_SPROUT_REQUIRES_CAUSAL_TURN: 9 |
| 1649–1651 | REAL_HEIST_RETURN | NO | 3 | 0 | COMMANDER_HEIST_FRESH_SPROUT_REQUIRES_CAUSAL_TURN: 3 |
| 2793–2793 | REAL_HEIST_RETURN | NO | 1 | 0 | COMMANDER_HEIST_FRESH_SPROUT_REQUIRES_CAUSAL_TURN: 1 |
| 2794–2794 | REAL_HEIST_RETURN | NO | 1 | 0 | COMMANDER_HEIST_FRESH_SPROUT_REQUIRES_CAUSAL_TURN: 1 |
| 5381–5382 | MAIN_EMA9_REJOIN | YES | 2 | 2 | Admitted |

The compact result contains the complete 68-file candidate source dictionary and 67-file baseline dictionary, original decision file SHA-256, first/last bounds and no-entry reasons for each qualified opportunity. The compressed per-frame report retains every decision comparison and is hashed in the compact result.

Accepted files: `sequence_final_v2/OPPORTUNITY_FIRST_SEQUENCE_AUDIT.json` and `sequence_final_v2/OPPORTUNITY_FIRST_SEQUENCE_FRAMES.jsonl.gz`. Both have been copied to the runnable program. The earlier preview comparisons are superseded.

Reproduce with separate output directories:

```text
python -B AUDIT_OPPORTUNITY_FIRST_SEQUENCE.py --program BASELINE --recording PID3904 --out BASELINE_AUDIT
python -B AUDIT_OPPORTUNITY_FIRST_SEQUENCE.py --program CANDIDATE --recording PID3904 --out CANDIDATE_AUDIT
python -B AUDIT_OPPORTUNITY_FIRST_SEQUENCE.py compare --baseline BASELINE_AUDIT --candidate CANDIDATE_AUDIT --out COMPARISON
```

## Full engine Construct method

The separate driver verifies the original tape against the original source seals, decodes every captured call unchanged, and dispatches all 6,965 calls to a fresh candidate ToolRackPaperEngine with fresh inventory. The existing PAPER depth, fees, whole-lot execution, journal and custody implementation remain active. Network access is prohibited during dispatch.

Modified branches can read the clock a different number of times, so the clock is explicitly authored: first original per-call time, then 10 microseconds per engine read. The exact recorded replay API remains unchanged. This is a modified-engine chronological Construct, not exact historical replay.

Acceptance requires a complete stable-source run, exactly matched source frame identity and complete geometry/native book across all 6,963 decisions, valid decision chains, qualified admissions, actual modeled entries and exits with custody review, full-lot exits and no venue-fill claims. It fails if any candidate strategy byte changes during or after the run.

```text
python -B CONSTRUCT_OPPORTUNITY_FIRST_ENGINE_SEQUENCE.py --program CANDIDATE --baseline BASELINE --recording PID3904 --out CONSTRUCT
python -B CONSTRUCT_OPPORTUNITY_FIRST_ENGINE_SEQUENCE.py inspect --construct CONSTRUCT --program CANDIDATE --recording PID3904
```

The `engine_construct_preview` run started before the source freeze and was rejected by its source-change guard. The first `engine_construct_final` run was interrupted after source call 2,898 when the core was reopened and is explicitly excluded. The new frozen-source run is `engine_construct_final_v2`. Its driver is SHA-256 `79f2d00850bc37fbd3acc3127e2c131d07294569bec4caff772788dad7c74b68`; that digest is captured at run start and checked again by final inspection.

### Final full engine result

The final run and semantic inspection passed. It executed one constructor, 6,963 process calls and one close. Pairwise inspection found no mismatches in source frame identity, timestamp, source generation, current geometry, market or native book. Both decision chains and the 62-record modeled journal verify. The accepted receipt binds the original tape and decision file, the 67-file original baseline, all 68 candidate source files, the driver and the emitted trace. The candidate source and driver remained unchanged throughout the run and inspection.

The native sequence contains 6,960 WAIT decisions and three entry admissions, each backed by a qualified current Commander opportunity. There were 6,795 custody reviews and two full-lot exits, both governed by the already armed executable bid floor. Every modeled entry and exit explicitly records `venue_fill_claim=false`.

| Entry source frame | Side | Quantity | Qualified Commander species | Modeled custody outcome |
|---|---|---:|---|---|
| 448 | NO | 28 | MAIN_EMA9_REJOIN | Remains open awaiting official settlement for KXBTC15M-26NOV060715-15 |
| 4972 | YES | 134 | MOUNTAIN_RETURN | Full-lot armed-bid-floor exit at source frame 5089; remaining quantity 0 |
| 5381 | YES | 95 | MAIN_EMA9_REJOIN | Full-lot armed-bid-floor exit at source frame 5544; remaining quantity 0 |

The native adviser reason at frame 4972 is `HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED`; the qualified Commander opportunity recorded for that admission is `MOUNTAIN_RETURN`. The fixed-metadata Commander comparison and this fresh full pipeline therefore have different admission sets. The Construct rebuilds specialists, inventory and custody from the original chronological feed; the shadow audit retains those fields from the historical decisions.

All four original bad-entry source controls waited: 2932 and 3192 required current-parent terminal proof; 6295 was at a TP/EMA junction; 6466 lacked repeated bilateral wall proof. Their assertions forbid the original wrong-side entry while allowing a separately earned correct-side MAIN opportunity.

The tape contains **zero settlement calls**. The ending 28-contract NO lot is therefore explicitly unsettled. No terminal liquidation, settlement result or final counterfactual profit is invented. PAPER modeled depth sweeps do not establish live matching, latency, execution or profitability. A fixed recorded feed cannot respond to hypothetical actions.

Accepted receipt: `engine_construct_final_v2/OPPORTUNITY_FIRST_ENGINE_CONSTRUCT.json`, copied to the runnable program under the same filename. Receipt SHA-256: `93e9d905a0161ae0e0ac380de46c19f878ccc8e9ea7b9766419d96f6e8f20e2b`. Mandatory inspection output: `engine_construct_final_v2_inspect.log`. Original tape verification took 282.77 seconds; candidate engine execution took 1,492.49 seconds. The full trace and modeled run outputs remain under `engine_construct_final_v2` for the parent's evidence archive.

## Independent custody review

The original ledger contains eight completed positions. Original Rail positions 4 and 6 were exited by `COMMANDER_MOUNTAIN_ONLY_HELD_LEG_TERMINAL_EDGE` while their current MAIN parent geometry remained active and nonterminal. The old generic held-terminal field inherited a child terminal event at a different scale. Exact original exit frames 4,428 and 5,522 are HOLD under the bounded parent-aware fix, with current same-side parent evidence. This does not assert an alternate later exit or profit. Original position 5 was a Heist exited by its already armed executable bid floor; that floor behavior remains independent.

Evidence: `PID3904_CUSTODY_FINDINGS.json`, `PID3904_CUSTODY_NEW_REVIEW.json`, `PID3904_CUSTODY_NEW_COMMANDER.json`.

## PID17224 fixture repairs

The two assigned test modules pass all 34 tests. Raw PID17224 fixtures have physical source timestamps 0.46–1.58 seconds later than their captured decision time. Raw Heist examples also lack repeated bilateral wall evidence. Those records now explicitly test WAIT at the current-source boundary.

Custody, normalization, floor, quantity, depth, duplicate-inventory and objective-economic mechanics are exercised with clearly labelled derived controls: aligned source clocks, preserved original book/intents, an explicit contract runway for Release mechanics, and measured repeated bilateral visits for Heist mechanics. These amended controls are not presented as original historical admissions. No fixture source file or strategy core was changed for this repair.

```text
python -B -m unittest tests.tool_rack.test_pid17224_release_heist tests.tool_rack.test_pid17224_main_returns
```

Evidence: `pid17224_after2.txt` and the refreshed required runner receipt in `construct_checks/final_run/current/PID17224_APPROVED_CORRECTIONS/report.json`.

## Current historical Construct diagnostics

All eight assigned historical runners pass against the final source. Their fresh reports are saved under `construct_checks`. Each output directory was restored to its pre-run state and immediately verified; these eight temporary output directories were absent beforehand. Historical fixture and report bytes were not rewritten. The 614 test executions below overlap across runners and are not a count of distinct tests.

| Construct | Test executions | Result |
|---|---:|---|
| PID17224 approved corrections | 34 | PASS |
| PID19996 Rail value | 34 | PASS |
| PID4596 runtime repair | 17 | PASS |
| PID17588 late scout | 15 | PASS |
| PID15184 current-parent calibration | 127 | PASS |
| PID4824 recovery identity | 142 | PASS |
| PID4824 floor authority | 51 | PASS |
| PID10656 sprout Heist | 194 | PASS |

The PID17224 runner now requires the two original-source negatives as well as the existing derived mechanics controls. Reports distinguish recovery/filter component eligibility from final Commander admission, and distinguish preserved original execution fields from newly appended admission evidence. No source fixture or historical approval was rewritten. The exact runner/report digests and restoration evidence are in `construct_checks/CURRENT_CONSTRUCT_DIAGNOSTICS.json`.

## Final extracted-delivery closure

The final delivered archive passed all 791 current tests in 55 isolated modules and every mandatory historical Construct from its extracted contents. Supplemental capture/export checks, actual JavaScript Looking Glass, fresh synthetic three-way recorder/replay proof, final status/manifest verification and full archive byte comparison also passed. Exact counts and the full transcript are preserved in `delivery/OPPORTUNITY_FIRST_VALIDATION.json`; the delivered ZIP hash is in `delivery/FINAL_DELIVERY_RECEIPT.json`. Native Windows field execution and profitability remain unverified; the next 45-minute PAPER field run is the operational follow-up.
