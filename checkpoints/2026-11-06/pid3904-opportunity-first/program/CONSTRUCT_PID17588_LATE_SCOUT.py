"""Offline existing-rule late-scout repair Construct; no orders or live feeds."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True

from tests.tool_rack.pid17588_late_scout_fixtures import (
    all_recorded_entry_probes, manifest,
)


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'PID17588_LATE_SCOUT_CONSTRUCT_RESULTS' / 'report.json'


def main() -> int:
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromName('tests.tool_rack.test_pid17588_late_scout')
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    corpus = manifest()
    probes = all_recorded_entry_probes()
    report = {
        'schema':'PID17588_LATE_SCOUT_CONSTRUCT_V1',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'passed':bool(result.wasSuccessful()),
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'test_output':stream.getvalue(),
        'scope':[
            'The historical correction under test is the existing _late_counter_return_has_runway guard in historical_extreme_release_candidates. This runner evaluates that component and retained source-rich positives under the current Commander.',
            'Exact original decision and contemporaneous history bytes are hash-verified; derived Historical Extreme context is recomputed and matches the recorded scout evidence.',
            'Candidate/admission probes use the original recorded clocks, geometry and native books with explicitly flat inventory; they are not full-engine replays, alternate fills or counterfactual profit results.',
            'PID19996 uses the complete two retained positive opening trajectories and the existing source-receipt bridge; no source or quote timestamp is shifted.',
            'Explicitly named synthetic unit variants cover the120-second boundary, supported or unavailable TP, mirror symmetry, source/quote safety, and the unchanged final60-second tactical limit. Synthetic variants are never called original observations.',
        ],
        'fixture':{
            'manifest':'tests/tool_rack/fixtures/pid17588_late_scout_manifest.json',
            'decision_file':'tests/tool_rack/fixtures/'+corpus['cases_file'],
            'history_file':'tests/tool_rack/fixtures/'+corpus['histories_file'],
            'decision_archive_sha256':corpus['cases_sha256'],
            'history_archive_sha256':corpus['histories_sha256'],
            'original_complete_decision_records':len(corpus['records']),
            'original_contemporaneous_history_records':len(corpus['histories']),
            'each_original_line_and_canonical_hash_verified':result.wasSuccessful(),
            'groups':{k:len(v) for k,v in corpus['groups'].items()},
        },
        'original_late_scout_corrected':probes['PID17588_trade1_entry'],
        'positive_controls':{k:v for k,v in probes.items() if k!='PID17588_trade1_entry'},
        'policy':{
            'existing_late_counter_return_seconds':120.,
            'required_tp_status':['BOUNCE_FAVORED','STARTING_LEG_FAVORED'],
            'required_tp_side':'the proposed scout side',
            'historical_scout_price_ceiling':.15,'historical_scout_size_allowance':15.,
            'no_new_profit_floor_or_promotion_policy':True,
            'no_opening_price_watch_or_side_coverage_change':True,
            'no_change_to_last60second_tactical_custody_boundary':True,
        },
        'current_commander_candidates_sha256':hashlib.sha256(
            (ROOT/'strategy_core/commander_candidates.py').read_bytes()).hexdigest(),
        'original_commander_candidates_sha256':corpus['original_program_commander_candidates_sha256'],
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if not result.wasSuccessful():
        print(stream.getvalue())
        print('PID17588 LATE SCOUT CONSTRUCT FAIL')
        return 1
    print('PID17588 LATE SCOUT CONSTRUCT PASS')
    print(f'{result.testsRun} tests;74 original decision records;7 contemporaneous history records.')
    print('Original late scout waits; both prior winners and both current winners preserve their entry components.')
    print(f'Report: {OUTPUT}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
