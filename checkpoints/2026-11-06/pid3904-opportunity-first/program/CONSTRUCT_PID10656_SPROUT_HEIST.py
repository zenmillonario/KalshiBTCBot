"""Offline PID10656 fresh-sprout Heist admission and opening-evidence gate."""
from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import heist_sprout_fade_ready
from tests.tool_rack.pid10656_sprout_fixtures import (
    entry_intent, manifest, opening_sequences, record, snapshot,
)


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'PID10656_SPROUT_HEIST_CONSTRUCT_RESULTS/report.json'
MODULES = (
    'tests.tool_rack.test_pid10656_sprout_heist',
    'tests.tool_rack.test_pid17224_release_heist',
    'tests.tool_rack.test_pid7812_sprout_promotion',
    'tests.tool_rack.test_dual_lane_main_tactical',
    'tests.tool_rack.test_pid15184_current_parent_calibration',
    'tests.tool_rack.test_pid19996_rail_fishing',
    'tests.tool_rack.test_pid15740_inherited_up_rail',
    'tests.tool_rack.test_pid4824_recovery_identity',
    'tests.tool_rack.test_pid4824_floor_authority',
)
SOURCE_FILES = ('strategy_core/commander_candidates.py','strategy_core/commander.py',
    'strategy_core/tool_rack.py')


def ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from ids(test)
        else:
            yield test.id()


def original_admission_probe():
    out = []
    for trade, seq in ((1,2618),(2,4771),(3,7304),(4,7584)):
        current, intent = snapshot(seq), entry_intent(seq)
        decision = OneCommander().decide_entry((intent,), current, {})
        data = record(seq)
        original = next(row['decision'] for row in data['decisions'] if row['scope'] == 'ENTRY')
        out.append({'trade':trade, 'sequence':seq, 'original_decision_sha256':data['sha256'],
            'original_action':original['action'], 'original_entry_reason':intent.reason,
            'current_action':decision.action.value, 'current_reason':decision.reason,
            'original_intent_preserved': bool(decision.intent is not None and replace(decision.intent,
                metadata={key:value for key,value in decision.intent.metadata.items()
                    if key!='commander_opportunity'}) == intent),
            'exact_entire_intent_equal':decision.intent == intent,
            'current_admission_annotation_added':bool(decision.intent is not None
                and decision.intent.metadata.get('commander_opportunity')),
            'sprout_quality_ready':heist_sprout_fade_ready(intent,current),
            'inventory_limit':'Isolated admission on original inputs; no replacement full-session inventory path.'})
    return out


def opening_probe():
    frames = [(seq,snapshot(seq)) for seq in opening_sequences()]
    quoted = [(seq,s) for seq,s in frames if s.yes_ask is not None]
    def row(seq):
        current = snapshot(seq)
        geometry = current.metadata['current_geometry']
        return {'sequence':seq, 'now_ts':current.now_ts, 'contract_age_s':current.contract_age_s,
            'yes_ask':current.yes_ask, 'btc_change6':geometry.get('btc_change6'),
            'ema9_change6':geometry.get('ema9_change6'),
            'current_mountain_owner':current.metadata['mountain'].get('owner_side'),
            'current_mission_parent_side':current.metadata['mission_context']['parent'].get('side'),
            'tp_side':current.metadata['tp_geometry'].get('contract_ownership_side'),
            'original_decision_sha256':record(seq)['sha256']}
    return {'quoted_first_minute_decisions':len(quoted),
        'yes_ask_min':min(s.yes_ask for _,s in quoted),
        'yes_ask_max':max(s.yes_ask for _,s in quoted),
        'first_valid_book':row(quoted[0][0]), 'first_ask_at_or_below_55c':row(7348),
        'minimum_first_minute_quote':row(7355), 'first_short_rejoin_after_opening_pullback':row(7366),
        'first_short_rejoin_after_pullback_with_tp_agreement':row(7379),
        'first_minute_affordable_and_short_rejoined_count':sum(1 for _,s in quoted
            if s.yes_ask <= .55 and s.metadata['current_geometry'].get('btc_change6',0) > 0
            and s.metadata['current_geometry'].get('ema9_change6',-1) >= 0),
        'approved_missing_first_minute_order_proved':False,
        'limitation':'Later frames retain the original held NO lot. No actual alternate YES entry or future result is asserted.'}


def main():
    suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    test_ids = list(ids(suite))
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    corpus = manifest()
    report = {
        'schema':'PID10656_SPROUT_HEIST_CONSTRUCT_V1',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'passed':result.wasSuccessful(), 'tests_run':result.testsRun,
        'failures':len(result.failures), 'errors':len(result.errors),
        'test_ids':test_ids, 'test_output':stream.getvalue(),
        'new_test_ids':[name for name in test_ids if '.test_pid10656_sprout_heist.' in name],
        'original_entry_component_results':original_admission_probe(),
        'original_opening_evidence':opening_probe(),
        'fixture':{'manifest':'tests/tool_rack/fixtures/pid10656_sprout_manifest.json',
            'manifest_sha256':hashlib.sha256((ROOT/'tests/tool_rack/fixtures/pid10656_sprout_manifest.json').read_bytes()).hexdigest(),
            'cases_file':corpus['cases_file'], 'cases_sha256':corpus['cases_sha256'],
            'original_decision_count':len(corpus['record_order']),
            'original_history_count':len(corpus['histories']),
            'original_source_archive_sha256':corpus['source_archive_sha256'],
            'original_decisions':corpus['original_decisions'], 'limits':corpus['limits']},
        'changed_source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCE_FILES},
        'original_program_sha256':corpus['original_program_sha256'],
        'scope':[
            'A later calibrated Market Heist visit cannot fade a source-current, witnessed same-side SPROUT while BTC and EMA9 still expand without the existing causal-turn proof.',
            'The rule applies before both the positive-briefing Heist fallback and the single Commander primary-family shortcut; same-tool metadata relabelling cannot bypass it.',
            'A stale covered motion subrow cannot cancel a current outward source-bound observation. Labels/age alone, unknown source, and unrelated mission-parent text supply no new restriction.',
            'Actual recorded entries1/2 retain prices, whole quantities, fees, execution fields and original intent metadata. Current admission appends commander_opportunity evidence; exact_entire_intent_equal therefore differs from original_intent_preserved. Release2 remains valid before the EMA9/EMA30 spine cross.',
            'Recorded negatives3/4 are withheld in isolated original-state controls. Mirrored directions and true measured/corrective transfers are tested.',
            'Prior tight-box/later-Heist, Release, rollover, rail-fishing, current-parent calibration, recovery identity and floor-authority controls run under their current evidence premises. PID17224 clock-aligned and measured-box positives are explicitly derived and accompanied by unmodified original-input negatives.',
            'No new entry route, price-cap increase, first-minute extension, position sizing, execution, fee, custody, floor, live-order or source-clock change.',
            'This Construct performs bounded component controls, not a full original engine replay and not an alternate session-profit calculation.',
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    if not result.wasSuccessful():
        print(stream.getvalue())
        print('PID10656 SPROUT HEIST CONSTRUCT FAIL')
        return 1
    print('PID10656 SPROUT HEIST CONSTRUCT PASS')
    print(f'{result.testsRun} tests; {len(report["new_test_ids"])} new tests; 131 exact original decisions.')
    print('Original1/2 remain eligible; original3/4 require a causal sprout turn. No alternate profit claim.')
    print(f'Report: {OUTPUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
