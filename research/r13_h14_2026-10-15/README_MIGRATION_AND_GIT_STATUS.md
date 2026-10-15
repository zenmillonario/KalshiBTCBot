# Tachyos R13-H14 — 2026-10-15 migration checkpoint

**Current:** H14 PAPER release BLOCKED after crash on PID 30336, Oct 15 at 02:50 EDT; open #3 unresolved. No live trading. Do not reuse old H14 launcher.

## GitHub status, authenticated connector

GitHub private repo: `zenmillonario/KalshiBTCBot`. New archival branch:

`tachys-r13-h14-20261015-migration-crash-blocked`

This branch was created from verified Phase13/14 checkpoint `8e7d923bdf436f31e44f2e42493eb930f510043e` and is NOT `main` and NOT the old Revival-Lab branch.

**Already committed by ChatGPT through connected GitHub:**
- H14 structural third-arc and first-rebound rulebook.
- H11 PID30928 zero-entry forensic.
- `MIGRATION_STATUS_AND_RELEASE_BLOCKERS.md`: H14 three trades, crash and next actions.
- H14 pilot source README, verification receipt.
- H13/H14 as-of signals evaluation CSVs.
- `COPY_TO_NEXT_CHAT.md`: paste-ready continuity and provenance.

**NOT automatically Git-committed:** the full H14 executable-source binary ZIP, prior H12/H13 release ZIPs, Observer42/Navigator original ZIPs, and the complete forensic report. These are included inside `GIT_ADD_FILES/` with their SHA256s and can be pushed to that same Git branch by the optional Windows script. No host Git credentials exist in this container, so this Git push has NOT been represented as complete.

**Original 43 MB engine and 62 MB combined run-audit ZIPs:** kept as original user-provided uploads, not copied to Git because of size/sensitive run data. The `EVIDENCE_SHA256_MANIFEST.json` records their exact names and hashes. They remain essential for full chronological replay; upload them in the next chat if necessary.

## How to archive all INCLUDED frozen sources to Git from Windows

1. Extract this migration bundle into a clean folder, without overwriting existing R13 releases.
2. Read `CONTINUITY_MESSAGE_FOR_NEW_CHAT.md`; use it as the first message in the new chat.
3. If Git for Windows and GitHub authentication are already set up, double-click `PUSH_SOURCE_AND_RESEARCH_TO_GITHUB.cmd`. It verifies every included ZIP's SHA256, shallow-clones the exact archival branch into a new `_GIT_STAGING_COPY_DO_NOT_RUN_BOT` folder, copies the `GIT_ADD_FILES` artifacts, commits, pushes and confirms remote HEAD SHA.
4. On failure, keep the screen text, do not force-push and do not start a trading engine. If the staging directory exists, do not rerun over the same folder; inspect it or extract a fresh copy.
5. **Nothing in these archival scripts starts Tachyos, changes strategy, or places an order.**

## Current forensic essentials

H14 intended 1h ran only ~16m52s, 2:33:20–2:50:12 AM EDT. Trades #1 YES $0.70→$0.82 +$1.68 closed; #2 NO $0.23→$0.10 −$7.67 closed (same contract settled YES); #3 YES $0.26 OPEN at crash. Actual closed paper gross −$5.99. #1 missed a known near-0.99 whole-lot terminal sale despite Sentinel COLLECT_NOW; #2's later sub-.05 tactical NO and new-contract opening NO were not admitted; #3 generic H13 soft-force reacted prematurely to one tiny green candle against strong DOWN leg. P0 crash is conditional local import of `corner_handoff_review` in `tachys_r15_command.py` followed by unconditional call. Follow the full causal report and continuity message.

*No Git commit by itself certifies the experimental strategy, actual PAPER performance, or live-readiness.*