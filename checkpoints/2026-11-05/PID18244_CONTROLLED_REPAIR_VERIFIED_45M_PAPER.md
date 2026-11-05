# TACHYOS PID18244 — verified controlled custody/protection 45m PAPER release (2026-11-05)

**State: Offline extracted-package full acceptance PASS.** The original PID18244 recording remains unchanged; its six trades yielded +$69.7041 net PAPER, which is an historical ledger result, **not** a simulated counterfactual of the repairs. Exact original PID18244 engine replay was NOT performed. Native Windows runtime of the new build was NOT executed here. This Git branch is a lightweight audit index; do not mistake it for a complete source checkout or production deployment. Keep `main` untouched.

## Delivered conversation artifact
- Release ZIP: `TACHYOS_PID18244_PARENT_CUSTODY_PROTECTION_45M_PAPER_20261105.zip`
- Final independently verified ZIP SHA-256: **`0fd242727ac163e16fed1ec29be06a2d5c5e78a525149ca8d3341db7d8770b61`**
- ZIP bytes: **50,849,167**, 343 members, 342 individually verified payloads plus manifest; exact file whitelist, CRC, payload sizes and SHA-256 all passed. 67/67 sealed strategy/config/UI source hashes match, and historical approval deltas reconcile.
- Source hash — `strategy_core/commander.py`: `34d93123421310b6c3cfbb4480333b33b578e105614636cd0ab884f3cc4ff6ef`.
- Source hash — `strategy_core/paper_runtime.py`: `c02af95418283848190a54a23c49a8dcbf984bc74324616c9208b6cc8f46a100`.
- Upload helper hash — `make_upload_parts.py`: `9fe440b0c43ff7c93965f87b7a9774b11b5497b82ddaa8304f591e97c6c8b6d0`.
- Launcher `00_PREPARE_AND_RUN_45M_PAPER.cmd`, 45-minute new-entry window followed by original held-position drain; PAPER only, venue order authority NONE.

## Verified offline acceptance
- **660/660 strategy tests across 46 isolated modules**, including the 10 PID18244 source-bound regression controls.
- **122/122 capture/launcher/packaging tests** across 14 test-module invocations.
- ALL historical Mountain/EMA9, dual-lane, Rail, current-parent, recovery, floor authority and fresh-sprout Constructs passed.
- Nautilus Looking Glass Python and actual Node.js JavaScript PASS.
- Four-stage SYNTHETIC recorder/replay proof passed (313 captured calls, 9 journal records, first-divergence and evidence-integrity controls); **not the original PID18244 full-engine replay**.
- Final extracted preflight PASS. No real venue orders, live credentials or live exchange session.

## Exactly scoped correction
1. Original new-run **#3 NO** `$0.055 -> settlement $0` bought against a native YES parent and incorrectly received `PROMOTED_MAIN` custody from historical NO crossing precedent, replacing tactical +40% first-floor with MAIN +200%. The new Commander rule allows a newly introduced parent-conflict block only when a **fresh, causally verified current native EMA9 parent** actually opposes the held seed. Unsupported historic NO evidence cannot give MAIN graduation. Existing same-side current Release and approved positive opening continuation controls still pass; no general entry prohibition.
2. Original new-run **#4 NO** `$0.26 -> $0.28` despite observed peak bid `$0.51`; its counter-YES TACTICAL position borrowed a local child NO living-runner deferral and missed its early +40% first-floor window. Under fresh native opposite-parent evidence and only after the initial candle, the policy preserves the **entry's existing 40% arm / 3% trail**, not the 100% MAIN peak lock. Already-armed positions, promoted MAIN, Lazarus, and source-stale cases remain protected by existing rules; no historical sale at $0.51 claimed.
3. Preserve positive original new-run **#2 and #5 Heist scalps and #6 Commander recent-level-match Mountain edge** `NO $0.0877 -> $0.35, +$64.2741 net PAPER`. Unmodified entry authority and full-lot floor are covered by regression controls.
4. Integrate previously synthetic-tested **lossless >25MB post-run small-upload fix**: review ZIP explicitly names omitted COMPLETE journal members; original bytes remain verifiable in all numbered parts, original ZIP untouched.
5. #1 potential early Release collection is FOR NEXT FORENSICS; deliberately unchanged.

## Final metadata identity reconciled
`NEXT_RUN_STATUS.json` now identifies **PID18244** previous run and +$69.7041 net, this exact release ID, correct `PID18244_VALIDATION.json`, and ready-for-PAPER true only after full final gate. `APPROVED_STRATEGY_CHANGES.json` / manifest / validation share same release ID. Previous `PID21672_VALIDATION.json` remains as untouched historical audit.

## Next Windows run / return
Extract entire released ZIP to an ordinary Windows folder; launch `00_PREPARE_AND_RUN_45M_PAPER.cmd` once. Respect preflight and writer-lock errors; no live trading authorization. After its automatic drain/export return `00_SEND_FIRST_REVIEW.zip`, all numbered `01_RUN_PART_*.zip`, `TRANSFER_MANIFEST.json`, and `READ_ME_FIRST.txt` for full forensic review. This first native-Windows PAPER run remains a FIELD verification step.
