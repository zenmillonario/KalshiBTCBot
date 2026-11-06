# PID10092 restart and finality fix

Date: 28 October 2026. Base strategy commit: `b310b37`.

Release: `TOOL_RACK_PID10092_MISSIONS_RESTART_FIX_20261028`.
Runtime: `TOOL_RACK_PAPER_PID10092_MISSIONS_RESTART_FIX_20261028`.
Nautilus: `TOOL_RACK_NAUTILUS_TV_V7_MISSIONS`.

## Why startup stopped

The prior run's committed journal retained one unresolved PAPER position. The startup check correctly refused to create another $1,000 ledger while that inventory remained. The earlier forensic report calculated the effect of a later official result separately; it did not append settlement to the user's Windows ledger. The base candidate lacked the explicit recovery command needed to finish that stopped ledger.

The supplied PID10092 diagnostics contain 230 verified journal records ending at SHA-256 `cad10b45e6a4ef2978551dab78de18e5fdbf362304af4f26bb14891e3af3f420`. Position #22 is YES, 252 contracts at .0370, with $9.3240 remaining cost and $.63 remaining entry fee. Its exact ticker is `KXBTC15M-26OCT272230-30`, pinned close October 27 at 10:30 PM Eastern.

The saved later public receipt reports finalized NO, with zero YES payout. It was observed after the old run stopped and is not backdated into the old session. Correct settlement recognizes −$9.9540 for #22, making the old run's total net −$66.3460. Cash remains $933.6540: entry cost and fee were already deducted. There is no second purchase-cost deduction and no additional modeled settlement fee.

The repair on the user's machine requests a fresh exact-market public receipt. It does not hard-code this saved outcome or infer settlement from the chart or current BTC price.

## Operator steps

1. Extract this complete updated ZIP into a new folder.
2. Open `05_RECONCILE_PREVIOUS_TOOL_RACK_RUN.cmd`. It checks both normal last-run pointers automatically, including the prior E:\\TachyosToolRackPaper run.
3. Wait for `COMPLETE_FLAT` and `unresolved: 0`.
4. Open `01_START_TOOL_RACK_PAPER_90M.cmd` from the same new folder. The ordinary startup guard verifies the now-flat prior journal before creating the next separate PAPER session.

The reconciliation command does not start the new run. If an old engine is still running, stop it first. An unavailable or nonfinal official result leaves the position unresolved and displays the actual error. A corrupt journal, unexpired position or existing per-run writer lock also remains blocked. No pointer, lock or position is deleted to obtain a fresh balance.

An explicit stopped folder can be selected with:

```bat
05_RECONCILE_PREVIOUS_TOOL_RACK_RUN.cmd --run "E:\TachyosToolRackPaper\TOOL_RACK_PAPER_20261028T010410Z_PID10092"
```

This does not alter either last-run pointer. Normal startup still checks both pointers afterward.

## Recovery mechanics

The command holds the process-wide OS lease and the existing per-run writer lock. It verifies the full hash-linked journal, checks that all held positions have reached their pinned close, and rechecks the expected head when opening a dedicated settlement-only writer. Ordinary open-inventory resume remains forbidden.

Before any settlement, it creates and verifies `reconciliation/<attempt>/before.zip`, containing the original journal and the existing ledger, stopped status, summary and run manifest. Credential files and the large price/decision streams are excluded. It then fetches exact public market results through the existing bounded, unauthenticated TLS GET client. Every required response must validate ticker, binary market, pinned close, finalized non-provisional state, chronology and payout before the first settlement is committed. No credentials, WebSocket, order endpoint or strategy engine are used.

The dedicated writer permits only `OFFICIAL_SETTLEMENT` journal commits. Entry, sale, floor and custody mutation routes are rejected. Existing journal records remain byte-for-byte unchanged; a valid official settlement appends a new record. Cash, cost, fees and position identity are loaded from the prior committed ledger. No baseline or fresh treasury is created by recovery.

The stopped `PAPER_LEDGER.json`, `STATUS.json` and `RUN_SUMMARY.json` are refreshed from the resulting journal. Both normal and final sequence/hash references are updated. Original runtime identity and stop reason remain recorded. The source manifest and original decision/source logs remain unchanged. Each attempt stores its report and official receipt separately, and the exporter includes this recovery evidence and backup.

If settlement commits but a Windows file lock interrupts a projection update, the journal remains authoritative. Running the reconciliation command again republishes the already-flat state without another settlement, cash debit or fee. The report cannot claim completion if an evidence or projection write fails.

## Validation

The full offline source gate passed **549 tests without skips** in 70.468 seconds on Python 3.12.14, with cryptography 50.0.2 and websockets 16.0. This includes **27 new recovery/startup checks**. The package contains 151 whitelisted files plus its generated manifest. Publication requires the actual ZIP extraction to pass the full gate again with its manifest verified.

The actual PID10092 journal was exercised on a separate copy using the previously captured official receipt. The original 230 records remained byte-for-byte unchanged; one settlement appended record 231 and closed #22. The resulting ledger had 44 economic events, no open positions, cash $933.6540, gross −$47.9660, fees $18.38 and net −$66.3460. The normal startup guard accepted it. Subsequent calls added no settlement, fee, cash debit or public-result request. Stopped projections agreed with the final journal boundary, and the original run manifest remained unchanged. The uploaded original diagnostics were not modified.

An initial parallel rehearsal encountered an existing writer lock on retry after a successful settlement. Its cause was not established. A retained clean copy then passed two calls with logging around the unchanged lock methods, followed by an uninstrumented production-path call; lock removal succeeded each time. No lock override or relaxed ownership rule was introduced. Detailed results are in `pid10092_restart_rehearsal.json`.

The focused checks also cover wrong ticker/close/payout, provisional or missing finality, unexpired positions, active engine/writer locks, corrupt or uncommitted journal data, failed receipt publication, and a projection-write failure after settlement followed by a successful retry. Startup now gives the reconciliation command without launching a new session or changing pointers when inventory remains unresolved.

Validation was offline on Linux. The command has not been executed on the user's Windows computer, and no remote Windows CI result is claimed. The operator command retrieves a fresh public receipt; the local rehearsal used the saved receipt without network access.

This is an operational recovery fix. It does not alter entry selection, the 40% tactical screen, holding rules, Lazarus qualification or the Nautilus interface. No new market feed or trading session is started during preparation.
