# Router V6.1 — Historical Path Interference Audit

Purpose: test whether V6's missing post-transfer ENTRY_GATE proposals were genuinely absent opportunities or artifacts of the historical trading path.

Why this matters: the V6 replay observes logs from a world in which the stale historical trade was actually taken. In the proposed router world, many of those stale trades would have been blocked, so position occupancy, mutex state, and the 20s same-side re-entry cooldown can differ.

Transfer epochs audited: 10
Historical authority path interfered at transfer: 6/10
Transfer-side CORE signal seen later in epoch: 3/10
Transfer-side pre-entry memory event seen later in epoch: 4/10
V9.5A final ENTRY_GATE attempt seen later in epoch: 1/10

## Per epoch

- tachys_v9_5a_price_freshness_active_treasury #6 KXBTC15M-26SEP181145-45 SAME_SIDE_CONTINUATION_RESET HAND_AUTHORITY_TRANSFER -> NO | staleActive=1 sideOccupied=1 oppSameTicker=0 cooldown=0 | coreSignals=0 oppSignals=0 preentry=1 finalAttempt=0
- tachys_v9_5a_price_freshness_active_treasury #41 KXBTC15M-26SEP181645-45 SAME_SIDE_CONTINUATION_RESET BOUNDARY_RELEASE -> NO | staleActive=0 sideOccupied=0 oppSameTicker=0 cooldown=0 | coreSignals=0 oppSignals=0 preentry=0 finalAttempt=0
- tachys_v9_5a_price_freshness_active_treasury #44 KXBTC15M-26SEP190345-45 SAME_SIDE_CONTINUATION_RESET HAND_AUTHORITY_TRANSFER -> NO | staleActive=1 sideOccupied=1 oppSameTicker=0 cooldown=0 | coreSignals=12 oppSignals=0 preentry=2 finalAttempt=0
- tachys_v9_5a_price_freshness_active_treasury #68 KXBTC15M-26SEP190815-15 OPPOSITE_SIDE_REVERSAL_RESET BOUNDARY_RELEASE -> YES | staleActive=0 sideOccupied=0 oppSameTicker=0 cooldown=0 | coreSignals=0 oppSignals=0 preentry=0 finalAttempt=0
- 2026-09-19_v9_5a_late_mature_shadow_5h #1 KXBTC15M-26SEP191245-45 SAME_SIDE_CONTINUATION_RESET BOUNDARY_RELEASE -> YES | staleActive=0 sideOccupied=0 oppSameTicker=0 cooldown=0 | coreSignals=0 oppSignals=0 preentry=0 finalAttempt=0
- 2026-09-19_v9_5a_late_mature_shadow_5h #11 KXBTC15M-26SEP191415-15 OPPOSITE_SIDE_REVERSAL_RESET BOUNDARY_RELEASE -> NO | staleActive=0 sideOccupied=0 oppSameTicker=0 cooldown=0 | coreSignals=12 oppSignals=2 preentry=4 finalAttempt=1
- 2026-09-19_v9_5a_late_mature_shadow_5h #13 KXBTC15M-26SEP191415-15 SAME_SIDE_CONTINUATION_RESET BOUNDARY_RELEASE -> NO | staleActive=1 sideOccupied=1 oppSameTicker=0 cooldown=0 | coreSignals=0 oppSignals=0 preentry=0 finalAttempt=0
- 2026-09-19_v9_5a_late_mature_shadow_5h #15 KXBTC15M-26SEP191430-30 OPPOSITE_SIDE_REVERSAL_RESET BOUNDARY_RELEASE -> NO | staleActive=1 sideOccupied=0 oppSameTicker=1 cooldown=0 | coreSignals=0 oppSignals=0 preentry=0 finalAttempt=0
- 2026-09-19_v9_5a_late_mature_shadow_5h #19 KXBTC15M-26SEP191515-15 SAME_SIDE_CONTINUATION_RESET BOUNDARY_RELEASE -> NO | staleActive=1 sideOccupied=1 oppSameTicker=0 cooldown=0 | coreSignals=0 oppSignals=0 preentry=0 finalAttempt=0
- 2026-09-20_v9_5a_swirl_orbit_long_01 #18 KXBTC15M-26SEP192115-15 SAME_SIDE_CONTINUATION_RESET HAND_AUTHORITY_TRANSFER -> NO | staleActive=1 sideOccupied=1 oppSameTicker=0 cooldown=0 | coreSignals=3 oppSignals=0 preentry=2 finalAttempt=0

## Discipline

- A missing V9.5A ENTRY_GATE row is not automatically evidence that the legacy engine failed to perceive the new chapter.
- If the historical stale position was still occupying the transfer side, the replay path is contaminated for counterfactual re-entry.
- Raw CORE signal and pre-entry telemetry are inspected because they can reveal recognition even when final paper authority could not re-enter.
- This audit does not change V9.5A authority and does not promote a new threshold.
