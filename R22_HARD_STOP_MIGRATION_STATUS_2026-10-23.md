# R22 hard-stop migration status — 2026-10-23

This file records only the new migration-critical state from the stopped session. It does not restate or replace the strategy backbone.

## Authoritative strategy file
- `TACHYOS_STRATEGY_BACKBONE_V1.md`
- Local verified SHA-256: `b181fd3bcf2e3f892526d92c283c65eee9ee6cbac9d4c18be22a72903d4ac73b`
- The backbone was verified unchanged across the pre-regression PID8432 package, PID2328 restored-feed package, and later package.

## Stopped run
- Run: `PAPER_20261023T000641Z_PID17396`
- Compact diagnostics: `PAPER_20261023T000641Z_PID17396_R22_COMPACT_DIAGNOSTICS_1df8c1699e.zip`
- Diagnostics SHA-256: `80e3ba58d6780e4a4901182e94a9fd996915005c449de1d51eb6158eaa1fae8d`
- New regression identified in this run: entry starvation from repeated `NO_CURRENT_SOURCE_PHYSICAL_OPPORTUNITY` / strategic pre-Commander filtering after feed readiness had been repaired.

## Rejected build
- `TACHYOS_R22_STREAMLINED_ONE_LEG_3H_2026-10-23.zip`
- SHA-256: `d7c44b6ccce5a5d8e702b518279aa06d8cc62b3e4972d2e27c3e38dc55d154ca`
- REJECTED. Do not use as an approved baseline.
- It allowed a ~$0.99 entry after value/admission logic was over-loosened.

## Earlier restored-feed package
- `TACHYOS_R22_PID2328_RESTORED_NATIVE_FEED_3H_2026-10-22.zip`
- SHA-256: `fb6879bd703db251a747961a804a01df27528236bdddbbb3f4795508c4538fde`
- This package repaired the false native-feed readiness pauses but is not declared a final strategy baseline here.

## Current status
- HARD STOP.
- No later build from the stopped session is approved.
- Future work must read the preserved backbone and historical files rather than infer strategy from the rejected streamlined code.
