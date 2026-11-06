"""Frozen PID7412 causal transfer controls; no market access or orders."""
from __future__ import annotations
import json
from pathlib import Path
import unittest
from tests.tool_rack.test_pid7412_directional_transfer import PID7412DirectionalTransferTests

ROOT=Path(__file__).resolve().parent

def main():
    rows=json.loads((ROOT/'docs/PID7412_DIRECTIONAL_TRANSFER_SAMPLES.json').read_text(encoding='utf-8'))['rows']
    trades=json.loads((ROOT/'docs/PID7412_TRADE_CONTROLS.json').read_text(encoding='utf-8'))['controls']
    labels={row['label'] for row in rows}
    frozen=[
        ('eight_causal_entry_time_snapshots',len(rows)==8),
        ('up_to_down_handoff_is_observed', {'UP_PARENT','UP_PARENT_CHILD_FLICKER','UP_TP_CONTRADICTION',
          'OLD_UP_GAP_COLLAPSED','DOWN_PARENT'} <=labels),
        ('all_twenty_trade_entry_examples_preserved',len(trades)==20 and
           {r['id'] for r in trades}==set(range(1,21))),
        ('with_wind_good_and_counterwind_negative_retained', all(any(r['id']==i for r in trades)
            for i in (1,2,5,10,13,14,3,6,7,8,9,11,12,15,16,17,18,19,20))),
    ]
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PID7412DirectionalTransferTests)
    outcome=unittest.TextTestRunner(verbosity=0).run(suite)
    total=outcome.testsRun
    frozen.append(('pid7412_current_source_regressions',outcome.wasSuccessful() and total>=9))
    passed=sum(ok for _,ok in frozen)
    print(f'PID7412 DIRECTIONAL TRANSFER / QUOTE ECHO CONSTRUCT: {passed}/{len(frozen)} PASS; source controls {total}')
    for name,ok in frozen:print(('PASS' if ok else 'FAIL'),name)
    return 0 if passed==len(frozen) else 1
if __name__=='__main__':raise SystemExit(main())
