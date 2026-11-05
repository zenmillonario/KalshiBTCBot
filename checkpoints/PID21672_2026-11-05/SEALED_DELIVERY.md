# PID21672 — Sealed runnable PAPER delivery

Release: `TACHYOS_PID21672_ROLLOVER_PROVENANCE_MAIN_CUSTODY_45M_20261105`
ZIP filename: `TACHYOS_PID21672_ROLLOVER_CUSTODY_45M_PAPER_2026-11-05.zip`
ZIP bytes: `50661772`
ZIP SHA-256: `181f93a1d9d8f9a44d228b7b56a31b22fdefb31949a74737f17efd0b47b03c3e`

The ZIP was generated directly from the full captured PID10656 program with only these **two production** strategy files changed:
- `strategy_core/commander_candidates.py` SHA-256 `3e2fdf72957b71e0f50967353ae066dd3f3daab83010f7f55a2c9d26211dae05`
- `strategy_core/mission_policy.py` SHA-256 `eed85cd2115263147d0a211d0f6c92e95b0e328675c6e1cb509050743a95805f`

The prior PID10656 source and approval are byte-pinned separately. Other production files including Nautilus/Looking Glass remain unchanged. The seal includes 67 core/config/UI files, with 340 delivery ZIP members and a strict allowlist.

Validation **PASS** on extracted output (Python 3.13.5, not a native Windows/Python 3.14 run):
- 649 current strategy tests in 45 modules;
- 103 recording/export tests including small-upload and Windows-launcher simulators;
- previous positive-control Constructs;
- Python and actual JavaScript Looking Glass pattern checks;
- fresh synthetic three-way original-vs-recorded-vs-replay comparison **PASS**;
- final SHA, manifest and ZIP archive integrity **PASS**.
- Real PID21672 complete-market exact replay on native Windows Python remains **NOT RUN**. These tests do not establish market profitability.

Launch from the complete extracted ZIP (not from a ZIP preview) by double-clicking `00_PREPARE_AND_RUN_45M_PAPER.cmd`. PAPER only, 45 minutes of new entries, then normal held-position drain, and automatic small upload ZIPs. For the next forensic review upload `00_SEND_FIRST_REVIEW.zip` plus every `01_RUN_PART_...zip`, `TRANSFER_MANIFEST.json` and `READ_ME_FIRST.txt`.

The Git branch intentionally stores **migration documentation, exact source delta and provenance**, not a fake full current checkout of the older repository. The sealed Windows program itself is distributed as the above independently verified ZIP.
