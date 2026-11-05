# TACHYOS PID21672 — verified 45-minute PAPER release (2026-11-05)

**Release status:** offline full extracted ZIP gate PASS. The original `PID21672_VALIDATION_STATUS.md` documents the *older migration candidate*, not this release, and remains a historical audit record. This Git note is a provenance index; it does **not** commit full source, a ZIP binary, or authorize live trading.

## Delivered conversation artifact
- Filename: `TACHYOS_PID21672_LIVE_PARENT_HANDOFF_45M_PAPER_20261105.zip`
- ZIP SHA-256: `a3db89fb77fe591015bac322e21179af1af858bb9bcd65654185fadccabc5eb6`
- Bytes: 50,645,601; 338 ZIP members, of which 337 individually hash-verified payloads.
- Launcher: `00_PREPARE_AND_RUN_45M_PAPER.cmd`; exactly 45-minute PAPER entry window, held-position drain, recorded for replay. Venue order authority: NONE.
- Extracted gate: 650/650 strategy tests across 45 modules; all mandatory historical Constructs; 109 capture/workflow/launcher tests; native Node.js Looking Glass JS Construct plus Python checks; four-stage synthetic three-way recorder/replay proof (309 process calls, nine journal records); final source/manifest/CRC/hash/preflight checks PASS.
- Root validation-timeout fix: the previous 600-second full nested test limit was too short; now 1800 seconds without removing acceptance controls.
- Core change: `strategy_core/commander_candidates.py` SHA-256 `98b186de6845510bac7528ee7f0584b73b1157c8f943d830eaa5c9acf2243572`. Preserves PID21672 #2 current-parent transfer negative control and restores PID17588 #5 confirmed strong inherited first-minute NO opening positive control, with specific proof. Existing risk/Commander/EMA9 architecture unchanged.
- Earlier original run remains PAPER net -$7.975. **No full original-run counterfactual engine replay or alternative profits verified.** Native Windows runtime **not executed** in the offline builder environment.

## Next forensic: trade #3
- 12:36 ET NO $0.270 → $0.180 at 12:39, $-10.05; entered independent MAIN Rail as `RAIL_MAIN_VALUE`, but mission role downgraded to TACTICAL, ending with `TACTICAL_MAX_HOLD_EXIT`.
- Native EMA9 was DOWN; inherited same-side residence ~1,878 s; contemporary `rail_established=false` and `entry_location_qualified=false`. Distinguish directional history from actual positive Rail entry location and custody grant.
- New 12:30 contract shadow YES asks $0.55–0.72 (first minute), $0.63–0.75 (next), $0.73–0.86 (following): no observed <=$0.35 cheap new-contract quote; expiring-contract subcent quote cannot be reused.
- Preserve #4 positive whole-lot floor and Nautilus Looking Glass. NO trade #3 custody/entry strategy changes in this release; investigate separately before authorization.
- Original seven-part archive independently SHA-256 verified: `8cf5be466d24ebc11f62f680602dd629b619708d12b6b727b76939669f1a8364`.

## Next run
Extract the delivered ZIP fully, then launch `00_PREPARE_AND_RUN_45M_PAPER.cmd` on Windows for a PAPER smoke test; do not bypass preflight. Return `00_SEND_FIRST_REVIEW.zip`, every numbered `01_RUN_PART_*.zip`, `READ_ME_FIRST.txt`, `TRANSFER_MANIFEST.json`. Preserve original recorded provenance and no hypothetical fills.
