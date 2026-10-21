"""1.3.1: post-read clock and stopped-run bounds. All markets/updates are fixtures."""
import ast
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reliability import Adapter, HealthReceipt
from candle_history import CandleHistory
from test_nautilus import fixture, NOW
from test_reliability import fixture as history_fixture, T, candle, record, write, drain


class AdvancingTime:
    def __init__(self, wall, mono=500.): self.wall, self.mono = wall, mono
    def time(self): return self.wall
    def monotonic(self): return self.mono
    def advance(self, seconds): self.wall += seconds; self.mono += seconds


class PostReadClockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lab, self.run, self.man, self.pointer, self.rt = fixture(self.root)
        self.man['started_utc']=NOW-100; self.man['ended_utc']=None
        write(self.run/'launcher_manifest.json', self.man)
        self.time = AdvancingTime(NOW)

    def adapter(self):
        a = Adapter(self.run,self.man,self.lab,self.pointer,history_enabled=False)
        self.addCleanup(a.close)
        return a

    def poll_with_midread_update(self, *, update_delta=.25, end_delta=.30, quote_age=.2, pid=None):
        a=self.adapter(); original=a.safe_json
        def reader(name,limit=4_000_000):
            if name=='tachys_runtime_hf2.json':
                # Emulate the engine replacing its file AFTER the poll began.
                self.rt['updated_wall']=NOW+update_delta
                self.rt['quote']['receive_age_sec']=quote_age
                if pid is not None: self.rt['pid']=pid
                write(self.run/name,self.rt)
                self.time.advance(end_delta)
            return original(name,limit)
        a.safe_json=reader
        with patch('adapter.time',self.time), patch('reliability.time',self.time):
            state=a.poll()
        return a,state

    def test_runtime_written_after_poll_start_is_current(self):
        _,s=self.poll_with_midread_update()
        self.assertTrue(s['run']['fresh'])
        self.assertEqual(s['health']['engine']['status'],'CURRENT')
        self.assertTrue(s['clock']['verified'])
        d=s['diagnostics']['freshness_check']
        self.assertAlmostEqual(d['runtime_age_seconds'],.05,places=5)
        self.assertTrue(d['update_arrived_during_read'])
        self.assertEqual(d['read_started_wall'],NOW)
        self.assertAlmostEqual(d['read_ended_wall'],NOW+.30)

    def test_genuine_future_timestamp_still_rejected(self):
        _,s=self.poll_with_midread_update(update_delta=.50,end_delta=.30)
        self.assertFalse(s['run']['fresh'])
        self.assertEqual(s['diagnostics']['freshness_check']['reason'],'FUTURE_TIMESTAMP')
        self.assertFalse(s['clock']['verified'])
        self.assertIsNone(s['quote']['yes_bid'])
        self.assertFalse(s['positions'][0]['mark_valid'])

    def test_runtime_expired_after_read_stays_stale(self):
        _,s=self.poll_with_midread_update(update_delta=-5.01,end_delta=.1)
        self.assertFalse(s['run']['fresh'])
        self.assertEqual(s['diagnostics']['freshness_check']['reason'],'EXPIRED')

    def test_runtime_ttl_boundary_not_extended(self):
        _,s=self.poll_with_midread_update(update_delta=-5,end_delta=0)
        self.assertTrue(s['run']['fresh'])
        self.assertEqual(s['diagnostics']['freshness_check']['runtime_ttl_seconds'],5)

    def test_quote_expiry_not_extended_to_fix_engine(self):
        _,s=self.poll_with_midread_update(quote_age=3.1)
        self.assertTrue(s['run']['fresh']); self.assertTrue(s['clock']['verified'])
        self.assertFalse(s['quote']['fresh']);self.assertFalse(s['positions'][0]['mark_valid'])

    def test_invalid_quote_permissions_remain_blocked(self):
        self.rt['quote'].update(yes_sell_allowed=False,no_sell_allowed=False,entry_allowed=False)
        _,s=self.poll_with_midread_update()
        self.assertFalse(s['quote']['fresh']);self.assertFalse(s['positions'][0]['mark_valid'])
        self.assertTrue(s['clock']['verified'])

    def test_wrong_runtime_pid_never_rehabilitated(self):
        _,s=self.poll_with_midread_update(pid=999)
        self.assertFalse(s['run']['fresh']);self.assertFalse(s['clock']['verified'])
        self.assertIsNone(s['accounting']['realized'])
        self.assertEqual(s['diagnostics']['freshness_check']['reason'],'IDENTITY_UNVERIFIED')

    def test_ledger_read_delay_is_included_in_freshness_age(self):
        a=self.adapter()
        import adapter
        original=adapter.complete_csv
        def slow(path,*args,**kw):
            rows=original(path,*args,**kw)
            self.time.advance(6)
            return rows
        with patch('adapter.time',self.time),patch('reliability.time',self.time),patch('adapter.complete_csv',slow):
            s=a.poll()
        self.assertFalse(s['run']['fresh'])
        self.assertEqual(s['diagnostics']['freshness_check']['reason'],'EXPIRED')

    def test_stale_btc_does_not_disable_fresh_contract_clock(self):
        _,s=self.poll_with_midread_update(update_delta=11.25,end_delta=11.30)
        self.assertTrue(s['run']['fresh']);self.assertFalse(s['market']['fresh'])
        self.assertTrue(s['clock']['verified'])
        self.assertEqual(s['health']['price']['status'],'STALE')

    def test_deterministic_explicit_evaluation_clock_retained(self):
        a=self.adapter()
        s=a.poll(NOW)
        self.assertEqual(s['server_now'],NOW)
        self.assertTrue(s['diagnostics']['freshness_check']['deterministic_time_override'])

    def test_receipt_contains_bounded_timing_evidence(self):
        _,s=self.poll_with_midread_update()
        r=HealthReceipt(self.root/'receipt.json',{'test':True})
        for _ in range(100):r.sample(s)
        r.close();data=json.loads(r.path.read_text())
        self.assertEqual(data['freshness_reason_samples']['CURRENT'],100)
        self.assertEqual(data['updates_during_read'],100)
        self.assertEqual(len(data['recent_freshness_checks']),32)
        self.assertLess(r.path.stat().st_size,50000)


class StopBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.run,self.man,self.rt=history_fixture(self.root,minutes=20)
        # Reproduce startup at :24 and stop 20 minutes later at :26, with
        # future chart padding to :56. There are 19 full run minutes, not 21.
        self.start=1791822864.04189
        self.stop=1791824066.4921222
        self.first=1791822900
        self.padded=1791824160.
        self.man.update(started_utc=self.start,ended_utc=None,status='RUNNING')
        self.rt.update(updated_wall=self.start+1,status='RUNNING')
        write(self.run/'launcher_manifest.json',self.man);write(self.run/'tachys_runtime_hf2.json',self.rt)
        self.h=CandleHistory(self.run,self.man,self.rt)
        self.addCleanup(self.h.close)
        self.h.request(1791821460.,self.padded)
        self.final=dict(self.man,status='STOPPED',ended_utc=self.stop)
        self.finalrt=dict(self.rt,status='STOPPED',updated_wall=self.stop)
        for i in range(19):
            b=candle(self.first+i*60)
            self.h.ingest(json.dumps(record(b['minute']+61,[b])).encode(),'forward')

    def test_live_worker_learns_end_and_21_becomes_19(self):
        self.assertIsNone(self.h.run_end)
        self.assertEqual(len(self.h.expected(1791821460.,self.padded)),21)
        self.assertTrue(self.h.sync_lifecycle(self.final,self.finalrt,self.stop+2))
        s=self.h.snapshot()
        self.assertEqual((s['completed_minutes'],s['requested_minutes']),(19,19))
        self.assertEqual(s['status'],'READY')
        self.assertEqual(s['run_end_source'],'FINAL_MANIFEST')
        self.assertEqual(s['requested_end'],self.stop)

    def test_every_later_request_clips_to_final_end(self):
        self.h.sync_lifecycle(self.final,self.finalrt,self.stop+2)
        for future in (self.padded,self.padded+900,self.padded+3600):
            self.h.request(1791821460.,future)
            self.assertEqual(self.h.requested_end,self.stop)
            self.assertEqual(len(self.h.expected(1791821460.,future)),19)

    def test_real_internal_missing_minute_not_hidden(self):
        del self.h.bars[self.first+5*60]
        self.h.sync_lifecycle(self.final,self.finalrt,self.stop+2)
        self.h.rev=SimpleNamespace(finished=True)
        s=self.h.snapshot()
        self.assertEqual((s['completed_minutes'],s['requested_minutes']),(18,19))
        self.assertEqual(s['status'],'GAPS')
        self.assertEqual(s['missing_minutes'],[self.first+5*60])

    def test_partial_shutdown_minute_excluded(self):
        self.h.sync_lifecycle(self.final,self.finalrt,self.stop+2)
        expected=self.h.expected(self.start,self.padded)
        self.assertNotIn(1791824040,expected);self.assertNotIn(1791824100,expected)
        self.assertNotIn(1791822840,expected)

    def test_wrong_session_cannot_set_end(self):
        foreign=dict(self.finalrt,session_id='OTHER')
        self.assertFalse(self.h.sync_lifecycle(self.final,foreign,self.stop+2))
        self.assertIsNone(self.h.run_end)
        self.assertEqual(self.h.snapshot()['status'],'BOUNDARY_UNVERIFIED')

    def test_wrong_manifest_cannot_set_end(self):
        for key,val in [('pid',99),('source_commit','DIFFERENT'),('run_directory','E:/other'),('mode','LIVE')]:
            self.assertFalse(self.h.sync_lifecycle(dict(self.final,**{key:val}),self.finalrt,self.stop+2))
            self.assertIsNone(self.h.run_end)

    def test_future_or_before_start_final_end_rejected(self):
        for end in [self.stop+1000,self.start-1,float('nan'),'bad',True]:
            self.assertFalse(self.h.sync_lifecycle(dict(self.final,ended_utc=end),self.finalrt,self.stop+2))
            self.assertIsNone(self.h.run_end)

    def test_runtime_stop_bound_can_precede_final_manifest(self):
        self.assertTrue(self.h.sync_lifecycle(self.man,self.finalrt,self.stop+2))
        self.assertEqual(self.h.run_end_source,'STOPPED_RUNTIME')
        self.assertEqual(self.h.snapshot()['requested_minutes'],19)
        final=dict(self.final,ended_utc=self.stop+.03)
        self.assertTrue(self.h.sync_lifecycle(final,self.finalrt,self.stop+2))
        self.assertEqual(self.h.run_end,self.stop+.03)
        self.assertEqual(self.h.run_end_source,'FINAL_MANIFEST')

    def test_final_end_is_frozen_not_extended_by_later_edits(self):
        self.h.sync_lifecycle(self.final,self.finalrt,self.stop+2)
        other=dict(self.final,ended_utc=self.stop+100)
        self.assertFalse(self.h.sync_lifecycle(other,self.finalrt,self.stop+200))
        self.assertEqual(self.h.run_end,self.stop)
        self.assertEqual(self.h.boundary_error,'FINAL_END_CONFLICT')

    def test_stopped_missing_end_does_not_guess_now(self):
        no_end=dict(self.man,status='STOPPED')
        no_endrt=dict(self.rt,status='STOPPED',updated_wall=None)
        self.assertFalse(self.h.sync_lifecycle(no_end,no_endrt,self.stop+2))
        self.assertIsNone(self.h.run_end)
        self.assertEqual(self.h.boundary_error,'STOPPED_END_UNVERIFIED')

    def test_end_sync_does_not_remove_genuine_bars_or_recenter_view(self):
        before=copy.deepcopy(self.h.bars);start=self.h.requested_start
        self.h.sync_lifecycle(self.final,self.finalrt,self.stop+2)
        self.assertEqual(before,self.h.bars);self.assertEqual(start,self.h.requested_start)

    def test_lifecycle_transition_is_wired_through_real_adapter(self):
        a=Adapter(self.run,self.man,history_enabled=True);self.addCleanup(a.close)
        a.poll(self.start+2)
        self.assertIsNone(a.history.run_end)
        a.history.request(1791821460.,self.padded)
        a.history.bars=copy.deepcopy(self.h.bars)
        write(self.run/'launcher_manifest.json',self.final)
        write(self.run/'tachys_runtime_hf2.json',self.finalrt)
        s=a.poll(self.stop+2)
        self.assertEqual(s['history']['run_end'],self.stop)
        self.assertEqual((s['history']['completed_minutes'],s['history']['requested_minutes']),(19,19))
        self.assertTrue(s['run']['stopped']);self.assertFalse(s['clock']['verified'])
        self.assertEqual(s['accounting']['realized'],0)


if __name__=='__main__':unittest.main()
