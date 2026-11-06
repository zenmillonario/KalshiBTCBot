"""Offline bounded recovery-identity Construct; no feeds, engine or orders."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode=True
from tests.tool_rack.pid4824_recovery_fixtures import bounded_results,manifest

ROOT=Path(__file__).resolve().parent
OUTPUT=ROOT/'PID4824_RECOVERY_IDENTITY_CONSTRUCT_RESULTS/report.json'
MODULES=(
    'tests.tool_rack.test_pid4824_recovery_identity',
    'tests.tool_rack.test_pid19996_source_freshness',
    'tests.tool_rack.test_pid15184_current_parent_calibration',
    'tests.tool_rack.test_dual_lane_main_tactical',
    'tests.tool_rack.test_pid17588_late_scout',
    'tests.tool_rack.test_pid19996_rail_fishing',
)

def ids(suite):
    for test in suite:
        if isinstance(test,unittest.TestSuite):yield from ids(test)
        else:yield test.id()

def main():
    suite=unittest.defaultTestLoader.loadTestsFromNames(MODULES);test_ids=list(ids(suite))
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    evidence=manifest()
    report={'schema':'PID4824_RECOVERY_IDENTITY_CONSTRUCT_V1',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'passed':bool(result.wasSuccessful()),'tests_run':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),
        'test_ids':test_ids,'test_output':stream.getvalue(),
        'scope':[
            'Complete the existing same-parent Lazarus anti-spray rule for Commander labels and timestamped Mountain extremes.',
            'Pin source-bound current physical owner/arc at original admission; identity itself never earns an entry.',
            'Preserve flat inventory, bounded opposite corrective missions, genuine new owners, validated parent-scope acquisition, and an actually measured post-fill retreat/retest/rejection.',
            'Preserve source-receipt, exact-lot, custody, exit-required, finality, entry-window and capacity boundaries.',
            'Original2441 and2856 are separate original-inventory recovery-component denials. With flat inventory,2856 clears this recovery component; independent shared opportunity admission still applies. No completed alternative run, two-trade removal, or P/L is claimed.',
            'All34 original late NO Release controls keep their original component result. The24 offers after the closed entry window are controls only, not attempted entries.',
            'No price cap, startup timer, first-counter policy, entry count, floor or custody policy is changed by this Construct.',
        ],
        'bounded_results':bounded_results(),
        'fixture':{'manifest':'tests/tool_rack/fixtures/pid4824_recovery_manifest.json',
            'manifest_sha256':hashlib.sha256((ROOT/'tests/tool_rack/fixtures/pid4824_recovery_manifest.json').read_bytes()).hexdigest(),
            'original_full_decisions':len(evidence['record_order']),'original_journal_snapshots':len(evidence['journals']),
            'original_history_records':len(evidence['history']),
            'cases':evidence['cases'],'journal':evidence['journal'],'parent_prefix':evidence['parent_prefix']},
        'source_sha256':{'strategy_core/tool_rack.py':hashlib.sha256((ROOT/'strategy_core/tool_rack.py').read_bytes()).hexdigest()},
        'original_program_sha256':evidence['baseline_program_sha256'],
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if not result.wasSuccessful():
        print(stream.getvalue());print('PID4824 RECOVERY IDENTITY CONSTRUCT FAIL');return 1
    print('PID4824 RECOVERY IDENTITY CONSTRUCT PASS')
    print(f'{result.testsRun} tests;42 exact decisions;18 original journals;813 original parent-prefix frames.')
    print('Original2441/2856 separately denied by recovery; flat2856 clears that component only. No alternate run/profit claim.')
    print(f'Report: {OUTPUT}')
    return 0

if __name__=='__main__':raise SystemExit(main())
