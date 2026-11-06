# PID12448: repeated wrong-direction entries and short holding

Date: October 28, 2026, America/New_York.

**Status: a confirmed source defect is corrected and additional decision evidence is implemented. The actual PID12448 entries and exits are not yet reconstructed. This is not approval for another PAPER run or a claim that the strategy is fixed.**

The available new evidence is `image(20261028-061128).png`, showing Nautilus V7 Missions and run `TOOL_RACK_PAPER_20261028T055826Z_PID12448`. The matching diagnostic archive has not been supplied. Source inspection starts from Git `4100b41`, the delivered restart/finality fix. No running Windows process, actual run ledger, inventory, source pointer or live configuration was changed by this audit.

## What the image establishes

| Visible item | Observation | Limit |
| --- | --- | --- |
| Trade #1 | NO entry .470, exit .330, net loss $3.46; entry row shows 02:06 ET | The image does not show the exact exit timestamp or decision reason. |
| Trade #2 | NO entry .260, 54 contracts, entry row shows 02:08 ET; still OPEN in this image | The user's report of its later rapid sale needs the later journal records. |
| Current engine thesis | YES, main contract thesis; parent YES / UP, terminal not qualified | Current thesis is not proof of the thesis at either entry. |
| Current inventory | Only the tactical NO position is shown | This is the behavior to investigate against the requested main-side-first strategy. |
| Current source message | Physical continuity reset, awaiting tool reacquisition | This blocks new entry at the displayed time; it does not establish why earlier orders were allowed. |

The code is the standalone Tool Rack architecture rather than an imported R22 execution runtime. The repeated behavioral concern remains valid: naming a parent mission and displaying a main-side thesis do not establish correct entry direction, timing or holding. Earlier mechanical validation did not establish those behaviors for this new run.

## Confirmed defect: tactical admission and collection used different destinations

Before correction, `MissionPolicy.tactical_economics` estimated the prospective bid at the center of the frozen EMA9 or box destination. `mission_collection_evidence` permits collection at the nearer edge of its tolerance band.

Using a controlled, past-only quote-response example:

| Item | Old admission calculation | First point eligible for destination collection |
| --- | ---: | ---: |
| Entry BTC | 100 | 100 |
| YES destination | 113 with tolerance 1 | 112 |
| Entry ask | .30 | .30 |
| Conditional estimated sale bid | .42 | .41 |
| Conditional gross return | 40% | 36.67% |

The old code admitted that fixture using travel the position was not required to hold through. When the tolerance band already contained the entry BTC price, it could also admit a supposed 40% return with effectively no distance left to its first collection point. The actual management helper then qualified collection after only .001 of favorable BTC movement.

The correction uses `target - tolerance` for YES and `target + tolerance` for NO. It rejects entries already at or inside that collection band, validates supported destination types and finite nonnegative tolerance, and records the center distance, tolerance, collection boundary and effective projection distance. Return, supported-distance and estimated-duration calculations use the same effective destination. A substantial return that still meets the existing 40% conditional screen at that boundary remains eligible. MAIN admission does not acquire a tactical return threshold.

The machine-readable comparison in `pid12448_admission_boundary_reproduction.json` loads the original policy directly from Git `4100b41` and compares it with the corrected source on identical synthetic inputs. Both YES and NO are covered. The original subthreshold and already-reached-band fixtures enter before correction and wait afterward; the adequate-return control enters in both versions. This is a source reproduction, not a PID12448 replay and not evidence of profitable future fills.

The existing positive 40% tests now place the center one tolerance width beyond their intended collection point. The new regressions retain the original failing geometry explicitly; the defect is not concealed by changing only the old test inputs.

## Why a YES thesis can coexist with a standalone NO trade

The Mountain tool has both a local countertrend proposal and a separate parent/main proposal. The latter requires an eligible current location, a matching physical classification and an ask no greater than its existing .50 cap. The rack prioritizes MAIN among actionable proposals. It does not require a main position to exist before any independent tactical return.

Consequently, the main proposal can disappear because its value window has passed, while an opposite local return remains actionable. This is a verified code path, not yet the established cause of #1 or #2. Increasing the cap would not establish that the earlier intended entry was recognized correctly.

The previous generator silently returned no main proposal at those gates. The audit adds a diagnostic record for the exact current contract thesis with stage `PHYSICAL_PROPOSAL`, decision `NOT_OFFERED` or `PROPOSED`, and the reason, observed ask, cap, source time, parent and location evidence. A physical proposal is not reported as accepted before the existing policy and Commander review it. The record reaches the existing decision/status candidate-review stream. These diagnostics preserve candidate selection and trading permissions.

The remaining tactical response model is a conditional sensitivity estimate. It can estimate a favorable return using bid response measured during an adverse move; its physical edge detector must supply the turning evidence. A passing arithmetic screen does not prove that the reversal will happen. Adding arbitrary extra confirmations could delay the early edge entries the operator requested; this requires inspection of the actual entry frames.

## Historical mountain context remains a specific review item

The chart's 239 completed bars inform conditional contract scenarios, range measurements and initial parent direction. They do not reconstruct all historical intraminute Mountain geometry. Parent origin, extrema and terminal measurements principally accumulate from received forward observations. The model can therefore display historical chart peaks while its live Mountain reference set is still incomplete, especially after a source reset.

This is a limitation of the current implementation relevant to the desired early entry. It has not been established as the cause of either PID12448 entry. Completed bars must retain their real resolution and known-at times if used for a separate historical parent model; they cannot be presented as observations of missing intraminute motion.

## What the rapid-exit check found

The current guard requires a later observed one-minute candle. It does not require 60 seconds of elapsed holding. A synthetic fill at timestamp 1079.8 and a fresh observation at 1080.2 are in different candles, so the candle check can pass after .4 seconds. The source comparison separately exercises collection qualification and this guard; it does not book an actual sale in PID12448.

No demonstrated same-entry-candle bypass was found in the ordinary tool and Commander routes reviewed. Source staleness and tool reacquisition alone do not issue a new sale or newly arm a profit floor. Already committed protection, accepted partial-exit obligations, explicit manual stop and official settlement retain their established authority. This audit changes neither those paths nor Lazarus/loss management.

The observed .47-to-.33 loss cannot be attributed to the destination defect without its actual exit reason. It may instead have used a structural failure, confirmed opposing release, protection or another recorded path. That must come from the journal and contemporaneous decisions.

## Construct and the validation gap

The original Construct was located in the retained HF15 source archive, `TACHYOS_R22_PID19340_AUTOMATIC_RAIL_ACQUISITION_HF15_4H_PAPER_2026-10-26.zip`. Its `RUN_R22_CONSTRUCT.py` verifies that R22 release and discovers `TEST_R22*.py` under a loopback-only network fence. Its strategy tests import the R22 engine's observers, mapper, fusion and Commander. Running it unchanged would exercise that engine, not the current standalone Tool Rack.

This Tool Rack candidate was validated with `CHECK_TOOL_RACK_PAPER.py`, its separate selected regression suite and the documented prior PID10092 replay. It was not validated by the original Construct runner. Equivalent coverage of the Construct's strategy scenarios has not been demonstrated.

The gap is substantive, not merely a filename. Many mission tests intentionally start with supplied classifications, qualified edges or a main thesis so they can isolate policy, custody and accounting. Those tests cannot establish that the live raw path generates the correct classification at the intended early entry. Some full source-path tests do exist, but they do not establish that all of the operator's specified mountain cases are represented. The prior PID10092 replay also injected the original recorded physical-detector outputs; it did not independently regenerate all detections from raw history. Missing completed chart history left its new main thesis UNKNOWN throughout, so it could not certify the new MAIN strategy.

The next strategy acceptance evidence must feed decision-time observations through the actual current Tool Rack source/geometry, parent context, tools, Commander and passive ledger. Required outcomes must be stated from the operator's strategy before inspecting output: qualified early valley/peak entries, rejection of a wrong-direction local fade when its required swing is absent, preservation of the larger holding through internal pullbacks, and a reasoned exit at its own destination or invalidation. Supplied detector labels cannot stand in for recognition in those tests. The original Construct also explicitly distinguishes synthetic wiring evidence from live detector quality; its name alone is not a guarantee.

The latest screenshot cannot supply the native quote depth, original detector inputs, receipt times or completed-history known-at times needed for that replay. The precise missing artifact is the PID12448 diagnostic archive below. This audit does not use that missing evidence to claim the current strategy passed.

## Validation and remaining evidence

The selected offline source gate completed **560 tests in 56 modules, all passed with no skips, in 70.216 seconds** on Python 3.12.14, Linux. It included 11 new test methods across the tactical-boundary and main-candidate diagnostics modules. The new cases cover the destination mismatch, already-reached bands, valid substantial returns on both sides, unchanged MAIN admission, and main-denial evidence without changing the rack's selected order. The full log is retained as `analysis_work/pid12448_admission_source_check.log` in the working evidence directory.

These results verify the narrow correction and regressions; they do not close the actual-run strategy findings. No Windows run, next trading session, venue order, new finality lookup or extracted replacement delivery was performed. The source comparison and original screenshot remain separate types of evidence.

The next forensic input is `TOOL_RACK_PAPER_20261028T055826Z_PID12448_DIAGNOSTICS.zip`, generated with `04_EXPORT_LAST_TOOL_RACK_RUN.cmd` after that session is stopped. Preserve the complete archive, especially `RUN_MANIFEST.json`, `decisions.jsonl`, `paper_journal`, `PAPER_LEDGER.json`, `physical_geometry.jsonl`, `market_data_source.jsonl` and `mission_history.jsonl`.

That archive is needed to determine:

1. The first qualifying lower-region main-side entry, its actual ask and available depth, and the gate that passed or denied it.
2. The parent and local-edge evidence that authorized each NO purchase, including whether the corrected collection-boundary screen would reject it.
3. Exact entry/exit timestamps and whether each sale came from destination collection, physical failure, release, protection, manual action or official finality.
4. Whether the second purchase paid a genuinely new physical opportunity or repeated the same attempted leg after an exit or reset.

Buy comparisons use the executable ask and available quantity; sale comparisons use the executable bid. A lower historical bid or an eventual chart trough alone does not prove an earlier buy was available or knowable.

No replacement runtime ZIP or next session has been issued by this audit. The direction, missed-entry and actual-exit findings remain open until this exact run is traced.
