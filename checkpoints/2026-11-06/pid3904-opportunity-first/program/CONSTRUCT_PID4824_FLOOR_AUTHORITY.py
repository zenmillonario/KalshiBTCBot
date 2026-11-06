"""Offline PID4824 first-floor authority Construct; no live feeds/orders."""
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode=True

from tests.tool_rack.pid4824_floor_fixtures import floor_component, manifest


ROOT=Path(__file__).resolve().parent
DIRECTORY=ROOT/'PID4824_FLOOR_AUTHORITY_CONSTRUCT_RESULTS'
OUTPUT=DIRECTORY/'report.json'
MODULES=(
    'tests.tool_rack.test_pid4824_floor_authority',
    'tests.tool_rack.test_pid252_tactical_promotions',
    'tests.tool_rack.test_pid7812_sprout_promotion',
    'tests.tool_rack.test_pid14312_arc_selection_custody',
)


def ids(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):
            yield from ids(item)
        else:
            yield item.id()


def main():
    suite=unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    test_ids=list(ids(suite));stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    evidence=manifest();components={};component_errors=[]
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    for name in ('trade3_floor_only','trade5_original_positive'):
        try:
            components[name]=floor_component(name,DIRECTORY/(name+'_component_journal.zip'))
        except Exception as exc:
            component_errors.append({'group':name,'error':type(exc).__name__,'detail':str(exc)})
    passed=bool(result.wasSuccessful() and not component_errors)
    report={
        'schema':'PID4824_FLOOR_AUTHORITY_CONSTRUCT_V1',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'passed':passed,'tests_run':int(result.testsRun),
        'failures':len(result.failures),'errors':len(result.errors),
        'test_ids':test_ids,'test_output':stream.getvalue(),
        'scope':[
            'A source-bound current living parent opposing the held side prevents local continuation alone from granting the existing +200% first-arm exception.',
            'These floor components retain the existing same-side owner and current Release exceptions; unknown/stale/unbound parents do not acquire floor authority. They do not establish admission or a complete custody/exit path under the current Commander.',
            'Original D2930 still has genuinely qualified YES continuation, but current parent NO and opposite NO Release. The ordinary100%/150% policy is restored without changing its thresholds.',
            'The exact original #3 entry is reconstructed in an artificial isolated account; original ordered books first arm atD2927 and breach atD2934. No exit or alternate sale is executed.',
            'Original #5 floor observations remain identical across all222 held inputs through its actual floor breach.',
            'Original-inventory anti-spray denials and this original-held-lot floor check are conditional component results. They are not an additive savings calculation or a full alternative run.',
            'Inherited PID252 physical-parent, PID7812 continuation/promotion and PID14312 return-seed/late-Release assertions execute with the current suites and their explicitly labelled source-rich mechanics premises.',
        ],
        'fixture':{'manifest':'tests/tool_rack/fixtures/pid4824_floor_manifest.json',
            'manifest_sha256':hashlib.sha256((ROOT/'tests/tool_rack/fixtures/pid4824_floor_manifest.json').read_bytes()).hexdigest(),
            'original_complete_records':len(evidence['record_order']),
            'cases_file':evidence['cases_file'],'cases_sha256':evidence['cases_sha256'],
            'limits':evidence['limits']},
        'original_policy_probes':evidence['original_policy_probes'],
        'bounded_components':components,'component_errors':component_errors,
        'changed_source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ('strategy_core/paper_runtime.py',
                'tests/tool_rack/pid4824_floor_fixtures.py',
                'tests/tool_rack/test_pid4824_floor_authority.py',
                'CONSTRUCT_PID4824_FLOOR_AUTHORITY.py')},
        'original_program_sha256':evidence['original_program_sha256'],
        'policy':{'new_profit_threshold':False,'new_hold_timer':False,
            'changed_continuation_adviser':False,'changed_custody_rules':False,
            'changed_already_armed_protection':False,'alternative_exit_executed':False,
            'full_modified_engine_replay':False,'current_parent_source_max_age_seconds':3.},
    }
    OUTPUT.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if not passed:
        print(stream.getvalue())
        if component_errors:print(json.dumps(component_errors,indent=2))
        print('PID4824 FLOOR AUTHORITY CONSTRUCT FAIL')
        return 1
    print('PID4824 FLOOR AUTHORITY CONSTRUCT PASS')
    print(f'{result.testsRun} tests;305 exact original records; two bounded floor-only components.')
    print('Original #3: first arm D2927; first breach D2934. Original #5 floor trajectory preserved.')
    print('No alternative sale, combined savings, or modified full-run profit is claimed.')
    print(f'Report: {OUTPUT}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
