"""Frozen causal PID8552 counterfade vs Rail-wick whole-lot controls.

Construct uses entry-time decision snapshots only. All outcome details remain
for forensic comparison and cannot enter trading decisions.
"""
from __future__ import annotations
import json
from pathlib import Path
import unittest
from tests.tool_rack.test_pid8552_rail_wick_custody import PID8552RailWickCustodyTests

ROOT=Path(__file__).resolve().parent

def main() -> int:
    d=json.loads((ROOT/'docs/PID8552_RAIL_WICK_ENTRY_TIME_CONTROLS.json').read_text(encoding='utf-8'))
    rows=d['rows']
    controls=[
        ('five_frozen_causal_checkpoints',len(rows)==5),
        ('early_young_fades_saved',all(x in rows for x in ('LATE_YES_1','EARLY_YES_2','EARLY_YES_3'))),
        ('rail_floors_have_real_entry_time_evidence',all(
             rows['NO_5_ALIGNED_EXPANSION']['geometry'].get(k) is not None
             for k in ('ema_gap','ema9_change30','ema9_change60','btc_change30','btc_change60'))),
    ]
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PID8552RailWickCustodyTests)
    result=unittest.TextTestRunner(verbosity=0).run(suite)
    controls.append(('all_nine_recorded_and_mirrored_strategy_controls',result.wasSuccessful() and result.testsRun==9))
    passed=sum(bool(ok) for _,ok in controls)
    print(f'PID8552 RAIL WICK / WHOLE LOT CONSTRUCT: {passed}/{len(controls)} PASS; {result.testsRun} scenario tests')
    for name,ok in controls:
        print(('PASS' if ok else 'FAIL'),name)
    return 0 if passed==len(controls) else 1
if __name__=='__main__':raise SystemExit(main())
