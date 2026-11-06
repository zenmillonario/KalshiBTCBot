"""Causal PID17744 positive briefing (no new veto committee) Construct."""
from __future__ import annotations
import json,unittest
from pathlib import Path
from tests.tool_rack.test_pid17744_return_briefings import PID17744ReturnBriefingTests
from tests.tool_rack.test_pid17744_navigator_rail_window import PID17744NavigatorRailWindowTests

ROOT=Path(__file__).resolve().parent

def main():
    d=json.loads((ROOT/'docs/PID17744_RETURN_BRIEFING_CONTROLS.json').read_text(encoding='utf-8'))
    suite=unittest.TestSuite([
        unittest.defaultTestLoader.loadTestsFromTestCase(PID17744ReturnBriefingTests),
        unittest.defaultTestLoader.loadTestsFromTestCase(PID17744NavigatorRailWindowTests),
    ])
    result=unittest.TextTestRunner(verbosity=0).run(suite)
    n=json.loads((ROOT/'docs/PID17744_2130_NAVIGATOR_CHECKPOINTS.json').read_text(encoding='utf-8'))
    controls=[
        ('six_distinct_frozen_trade_inputs',set(d['rows'])==set('11 12 13 14 15 16'.split())),
        ('source_is_pid17744_archive',d['source_archive'].endswith('PID17744_ULTRA_FORENSICS.zip')),
        ('entry_time_scenarios',result.wasSuccessful() and result.testsRun==15),
        ('rail_window_checkpoint_set',set(n['rows'])=={'213016','213050'}),
        ('no_navigator_entry_or_veto',result.wasSuccessful()),
    ]
    passed=sum(bool(ok) for _,ok in controls)
    print(f'PID17744 RETURN BRIEFING CONSTRUCT: {passed}/{len(controls)} PASS; {result.testsRun} scenarios')
    for label,ok in controls: print(('PASS' if ok else 'FAIL'),label)
    return 0 if passed==len(controls) else 1
if __name__=='__main__':raise SystemExit(main())
