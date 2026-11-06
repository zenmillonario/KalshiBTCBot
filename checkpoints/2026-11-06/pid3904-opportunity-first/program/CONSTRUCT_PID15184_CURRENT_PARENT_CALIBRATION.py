"""Offline current-mission-parent calibration Construct; no live feeds/orders."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True

from tests.tool_rack.pid15184_current_parent_fixtures import chronology_probe, manifest


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT/'PID15184_CURRENT_PARENT_CALIBRATION_CONSTRUCT_RESULTS/report.json'
MODULES = (
    'tests.tool_rack.test_pid15184_current_parent_calibration',
    'tests.tool_rack.test_dual_lane_main_tactical',
    'tests.tool_rack.test_pid15740_inherited_up_rail',
    'tests.tool_rack.test_pid17224_release_heist',
    'tests.tool_rack.test_pid17588_late_scout',
    'tests.tool_rack.test_pid19996_rail_fishing',
    'tests.tool_rack.test_pid252_tactical_promotions.PID252TacticalPromotionTests.test_recent_level_match_sub20_return_bypasses_tool_wait_stack',
    'tests.tool_rack.test_pid252_tactical_promotions.PID252TacticalPromotionTests.test_recent_level_match_above_20_does_not_force_entry',
)


def ids(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):
            yield from ids(item)
        else:
            yield item.id()


def main():
    suite=unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    test_ids=list(ids(suite))
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    corpus=manifest()
    probes=chronology_probe()
    report={
        'schema':'PID15184_CURRENT_PARENT_CALIBRATION_CONSTRUCT_V1',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'passed':bool(result.wasSuccessful()),'tests_run':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),
        'test_ids':test_ids,'test_output':stream.getvalue(),
        'scope':[
            'Source-bound ACTIVE current mission context supplements only previously unavailable counterfade parent direction; qualified historical and existing Release precedence remain first.',
            'The same current parent keeps its first observation through ticker/label changes and later historical qualification; opposite gaps cannot name it and genuine parent/side/continuity changes reset it.',
            'A later tactical marker is bound to the exact current consideration and distinct swing; incoming or stale markers cannot survive same-side, unknown, Release or genuine-terminal bypasses.',
            'The ordered original PID15184 observer/filter projection changes only seq26 of43 original physical proposals; original entries2–5 remain filter-eligible and retain their separate full-arc evidence. Filter eligibility alone does not establish Commander admission.',
            'Under current shared admission, original1337 ENTERs;2006 waits for parent terminal proof,4050 waits at the TP/EMA junction, and5341 lacks proven return-target runway. These exact original-input outcomes are independently asserted.',
            'No complete modified engine run, alternate inventory/fills/exits, removed loss, or future profit is claimed.',
            'The prior PID17588 single-frame positive fixture receives its actual907-frame prior observation prefix; its original decision bytes, behavior test and ENTER expectation remain unchanged.',
            'Prior PID19996/PID17588 original positives and late-scout controls remain covered. Inherited-parent and Release mechanics use the evidence classifications documented by their current suites, including explicitly derived controls where original source proof is incomplete.',
        ],
        'original_ordered_component_results':probes,
        'fixture':{
            'manifest':'tests/tool_rack/fixtures/pid15184_current_parent_manifest.json',
            'manifest_sha256':hashlib.sha256((ROOT/'tests/tool_rack/fixtures/pid15184_current_parent_manifest.json').read_bytes()).hexdigest(),
            'original_complete_decision_records':len(corpus['record_order']),
            'original_complete_history_records':len(corpus['histories']),
            'projected_ordered_decisions':corpus['chronology_rows'],
            'baseline_original_observer_mismatches':corpus['original_observer_reconstruction_mismatches'],
            'cases_file':corpus['cases_file'],'cases_sha256':corpus['cases_sha256'],
            'chronology_file':corpus['chronology_file'],'chronology_sha256':corpus['chronology_sha256'],
            'prior_positive_prefix':corpus['prior_positive_prefix'],
            'projection_limits':corpus['limits'],
        },
        'changed_source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ('strategy_core/dual_lane.py','strategy_core/tool_rack.py',
                'tests/tool_rack/pid17588_late_scout_fixtures.py')},
        'original_program_sha256':corpus['original_program_sha256'],
        'unchanged_inherited_assets':corpus['unmodified_inherited_assets_sha256'],
        'policy':{'new_startup_timer':False,'new_native_origin_requirement':False,
            'supported_true_required':False,'owner_only_fallback':False,
            'new_trade_family_or_price_cap':False,'custody_or_floor_changes':False,
            'direct_current_source_max_age_seconds':3.,'no_future_price_qualification':True},
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if not result.wasSuccessful():
        print(stream.getvalue())
        print('PID15184 CURRENT PARENT CALIBRATION CONSTRUCT FAIL')
        return 1
    print('PID15184 CURRENT PARENT CALIBRATION CONSTRUCT PASS')
    print(f'{result.testsRun} tests;9 exact PID15184 decisions;7,915 ordered observer frames;907 prior-winner prefix frames.')
    print('Observer/filter projection: only original seq26 changes; entries2–5 remain filter-eligible. Shared Commander admission separately checks current species/target proof.')
    print(f'Report: {OUTPUT}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
