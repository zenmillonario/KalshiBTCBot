"""PID14048 original-run chronology + source-bound Commander decision controls.

READ ONLY. This is *not* a changed-engine replay and does not execute trades,
modify market history, predict a future cheapest ask, or credit profits.
"""
from __future__ import annotations
import gzip
import json
from pathlib import Path
import unittest

from tests.tool_rack import test_pid14048_quote_value_and_stall as cases

ROOT=Path(__file__).resolve().parent
PATH=ROOT/'tests/tool_rack/fixtures/pid14048_full_sequence.json.gz'

def main()->int:
    obj=json.loads(gzip.decompress(PATH.read_bytes()))
    frames=obj['frames']
    if (len(frames)!=8179
            or [v['seq'] for v in frames] != list(range(1,8180))
            or not all(frames[i]['prev_sha']==frames[i-1]['orig_sha'] for i in range(1,len(frames)))):
        raise AssertionError('ORIGINAL_PID14048_CHRONOLOGY_OR_HASH_POINTER_MISMATCH')
    selected=obj['selected_frames']
    first=selected['04:40:00']['row']
    after=selected['04:40:01']['row']
    hover1=selected['05:01:55']['row']
    hover2=selected['05:02:00']['row']
    if (first['entry_action']!='RELAY' or first['side']!='NO'
            or not .25<=1-first['yes_bid']<=.27
            or not .23<=1-after['yes_bid']<=.26
            or hover1['btc9']<=0 or hover2['btc9']>=0
            or hover2['ema6']>=0):
        raise AssertionError('PID14048_RECORDING_SCENES_MISMATCH')
    suite=unittest.defaultTestLoader.loadTestsFromModule(cases)
    runner=unittest.TextTestRunner(verbosity=0)
    result=runner.run(suite)
    if not result.wasSuccessful():
        raise AssertionError('PID14048_SOURCE_BOUND_COMMANDER_TESTS_FAILED')
    print('PID14048 QUOTE VALUE AND STALL CONSTRUCT PASS: '+str(result.testsRun)
          +' source-bound controls; 8179 recorded old-engine decisions verified.'
          +' No modified-engine original-run replay or alternate fills.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
