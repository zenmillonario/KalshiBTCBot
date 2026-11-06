# TACHYOS PID19616 — verified entry-quality 45-minute Windows PAPER release (2026-11-05)

**Status:** FULL extracted-package validation PASS + independent archive audit PASS. **PAPER ONLY.** No live venue order authority. Original PID19616 eight-trade market run was NOT engine-replayed; no alternative fills or hypothetical profits claimed. The final ZIP has NOT been run on the user's Windows machine yet. This Git branch is a provenance/audit checkpoint, **not** a full repository source or production deployment. Keep `main` untouched.

## Delivered artifact

- File: `TACHYOS_PID19616_ENTRY_QUALITY_45M_PAPER_20261105.zip`
- Exact final ZIP SHA-256: **`af24aea6d690c2a88cc2b3ee4acbb3dd6b8777634e04142bb6a3c2990452784b`**
- Bytes: **51,272,849**.
- **349 ZIP members; 348/348 independently verified payload hashes; 67/67 sealed source hashes.** Identity reconciled across archive manifest, approval, NEXT_RUN_STATUS, and PID19616_VALIDATION.
- Launcher: `00_PREPARE_AND_RUN_45M_PAPER.cmd`. Strict preflight, 45-minute new-entry window, usual held-position drain and lossless upload exports.
- Approval: `mode=PAPER`, `venue_order_authority=NONE`; native Windows field launch not yet performed.

## Acceptance

- **683/683 strategy tests across 47 isolated modules**.
- **145/145 capture, archive, regression and Windows-launcher tests across 15 module invocations** (some overlap with focused strategy controls). Tests were run against the extracted release ZIP.
- All mandatory historical Constructs PASS, including Rail Value, inherited current-parent calibration, runtime repair, recovery and whole-lot floor authority, and fresh-sprout Heist.
- Actual Node.js Looking Glass JavaScript plus Python checks PASS.
- Four-stage SYNTHETIC recorder/replay proof PASS. Not an exact replay of original PID19616 market tape.
- Final archive whitelist, CRC, sizes, hashes, 67 sealed-source identities, approved-change reconciliation and independent byte-for-byte prior-release comparison PASS.

## Only two sealed trading-source files changed

- `strategy_core/commander.py` SHA-256 `a48d2f2f4136d3fef288229506dc9882ba719ad6d8e4eef4291a94d6939751b2`
- `strategy_core/commander_candidates.py` SHA-256 `6310feef2261a347a9141d66ba2062065cdbb093f59e5fd6e10955b30616e4ab`

All other sealed strategy/risk/custody/profit-floor/Looking Glass sources and original Windows launcher remain byte-identical to prior release `TACHYOS_PID18244_PARENT_CUSTODY_PROTECTION_45M_PAPER_20261105.zip` SHA-256 `0fd242727ac163e16fed1ec29be06a2d5c5e78a525149ca8d3341db7d8770b61`.

### Approved narrow rules

1. **PID19616 #3** false recent-low/support Mountain match: $32.52 beyond old reference below anchor while current physical parent DOWN. Demand close physical location rather than using excessively wide 180-second tolerance; maintain historic genuine PID18244 #6 cheap NO recent-level-match winner. The protected fixture actually used ~$18.97 distance at its snapshot, so the qualified near-level tolerance retains that positive.
2. **PID19616 #7** unearned YES Heist stalled-edge fade on a near-zero six-second pause despite strong 9s/30s downtrend and EMA9 DOWN parent. Require genuine physical return when present source supports a fresh contrary parent; do not disallow all real tactical upper/lower edge returns. Preserve profitable Heist rotations.
3. **PID19616 #8** exceptional first-minute NO $0.51 inherited continuation after 2.85 contracts with only $1.90 60-second net momentum. Mature premium early joining now requires meaningful new same-side 60-second progress. Preserve historic PID15740 strong $0.53 inherited YES opening, cheap entries, and authorized earlier continuations.

No generalized strategy restart, new advisory veto, unapproved changes to risk size/limits, profit-floor handling, Lazarus or one-Commander/two-lane EMA9 architecture.

## Original recorded run remains an unchanged source

`TOOL_RACK_PAPER_20261105T223220Z_PID19616` original 556,916,480-byte ZIP SHA-256 `22028d8a01034bd76f66caf164ff622f660a0d5b7cc76dca765218d21fe117e5`; 8 trades, net **−$40.1716 PAPER**. This is a historical outcome of the *prior* release, not a result of this new change.

## Next action

Extract full release ZIP to a normal Windows folder. Double-click `00_PREPARE_AND_RUN_45M_PAPER.cmd` once; do not bypass preflight or writer lock, and do not authorize live orders. After normal run closure and export, return `00_SEND_FIRST_REVIEW.zip`, **all** numbered `01_RUN_PART_*.zip`, `TRANSFER_MANIFEST.json`, and `READ_ME_FIRST.txt`. Validate byte hashes and perform full original-run forensics before further strategy edits.

Independent audit conversation artifacts: `PID19616_RELEASE_INDEPENDENT_AUDIT_2026-11-05.md` and `PID19616_RELEASE_INDEPENDENT_AUDIT_2026-11-05.json`.
