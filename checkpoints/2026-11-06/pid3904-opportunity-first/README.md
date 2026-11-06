# PID3904 Opportunity-First Commander — accepted PAPER release

**Final delivery validation: PASS. Ready for the next 45-minute Windows PAPER entry window, followed by the existing held-position drain.** The accepted delivery is `TACHYOS_OPPORTUNITY_FIRST_COMMANDER_45M_PAPER_20261106.zip`. Extract the complete ZIP to a new folder and run `00_PREPARE_AND_RUN_45M_PAPER.cmd` once. Return the new review ZIP and every numbered recording part.

This final checkpoint supersedes the pending delivery status recorded at the earlier frozen-source commit `ed0fc2374b80789787095827e49211052c203298`. The final `program/NEXT_RUN_STATUS.json` is ready and `program/OPPORTUNITY_FIRST_VALIDATION.json` is PASS. Both files are byte-identical to the delivered ZIP.

## What is preserved here

The checkpoint contains 331 selected program files: every one of the 68 sealed strategy/config/UI source files, current Python implementation and tests, Windows launchers, governing instructions, forensic reports, source-bound chronological and full-engine receipts, full final validation JSON, and the final ZIP payload manifest. The 327 static files were independently compared with the actual delivered ZIP using byte count, SHA256 and Git blob SHA1; the four final status/validation/manifest files were extracted directly from that ZIP. `SOURCE_CHECKPOINT_MANIFEST.json` records the exact tracked scope.

Three existing core files changed (`commander.py`, `custody_evidence.py`, `paper_runtime.py`); `opportunity_first.py` was added. The other 64 existing sealed source/config/UI files match PID3904. One Commander, EMA9 authority, EMA30 context, independent positive MAIN and TACTICAL briefings, whole lots and irreversible floors remain the governing contract. No venue order authority is granted.

## Acceptance evidence

- Final extracted engineering gate: **791 strategy tests across 55 modules**, all mandatory historical Constructs, capture/export/launcher modules, actual JavaScript checks and fresh synthetic three-way recorder/replay proof passed.
- Mountain Construct: **82/82** cases passed, including the real modeled ENTER/BOOKED to HOLD to whole-lot EXIT/EXITED lifecycle and preserved floor values.
- Chronological Commander audit: **6,963 frames and 10 semantic controls** passed against the final source.
- Fresh modified-engine Construct: **6,965 calls / 6,963 frames and 11 semantic controls** passed, with unchanged original decoded feed/book arguments, fresh inventory, source/driver seals and decision-chain verification.
- Construct outcomes: three modeled entries, two full-lot floor exits, one ending unsettled position. Entry frame4972 is a **MOUNTAIN_RETURN proposed through the Heist adviser**.
- Final runnable ZIP: 398 payload files plus manifest; all member bytes, source seals and ZIP integrity verified. Evidence ZIP: 292 payload files plus manifest, all streamed through a complete readback with SHA256 and CRC checks.

See [VALIDATION_REPORT.md](VALIDATION_REPORT.md), [FINAL_ARTIFACTS.json](FINAL_ARTIFACTS.json), and [program/PID3904_FORENSICS.md](program/PID3904_FORENSICS.md).

## Delivered archives

| Archive | Bytes | SHA256 |
|---|---:|---|
| `TACHYOS_OPPORTUNITY_FIRST_COMMANDER_45M_PAPER_20261106.zip` | 70161725 | `ceed15cd87ab6028d58add025619b6641a19c2653c4f1da3ee107a2100571a6a` |
| `PID3904_OPPORTUNITY_FIRST_EVIDENCE_20261106.zip` | 262944117 | `c4e1fe218c100dbf06c43ea8f31f1483a9a1c684bd66ec13f34541b0f9ab5fd4` |

Both archives were delivered as saved downloads in the originating conversation. The runnable archive includes all packaged binary/large fixtures. The evidence archive includes the complete accepted modeled run and execution trace, independent local-return probes, original source-linked forensic extracts, historical control evidence, core diff, logs and provenance. The 468,249,829-byte original recording was reconstructed and verified from all five uploaded parts; it is not duplicated inside these archives. This Git checkpoint is a source/tests/validation checkpoint, not a complete backup of the original binary recording or all large fixtures.

## Interpretation limits

The original run has eight completed trades, starting cash1000, ending cash933.0906, gross-54.6094, fees12.30 and net-66.9094, flat. Any earlier six-trade account is superseded by the complete ledger.

The modified-engine Construct uses an explicitly authored source-time clock under Linux/Python3.12.14. The original capture was Windows11/Python3.14.7. Exact native Windows replay and the next Windows field run have not been verified here. Modeled fills are not venue fills. The captured tape contains zero settlement calls, so the final modeled position remains unsettled; no settlement, terminal liquidation or alternate final profit was invented. Profitability and six-hour capture acceptance are not established.

The new separate branch is `tachyos/checkpoint-2026-11-06-pid3904-opportunity-first` in `zenmillonario/KalshiBTCBot`. This task did not change main, older research branches or Revival-Lab history. Continue from this final accepted checkpoint and the delivered archives; preserve the source and artifact hashes.
