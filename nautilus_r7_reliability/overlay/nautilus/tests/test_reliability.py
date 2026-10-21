"""UI-only reliability tests: synthetic histories + source read-only checks."""
import hashlib
import http.client
import json
import math
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapter import resolve_run
from candle_history import CandleHistory, ReverseLines, bar, fingerprint, MAX_BARS
from reliability import Adapter, ClockGuard, SidecarHealth, verified_timer, HealthReceipt
from server import Publisher, Handler, LocalServer

T=1791790260


def write(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj),encoding='utf-8')


def candle(t,close=102):
    return dict(minute=t,open=100.,high=110.,low=90.,close=float(close))


def record(ts,bars,**extra):
    return dict(schema='HF21_SNAPSHOT_V1',identity={'run_id':'R','session_id':'S'},captured_at_epoch=ts,
                frame=dict(box_candles=bars,**extra))


def fixture(root,minutes=100):
    run=root/'runs'/'666_lab_TEST_PID1';run.mkdir(parents=True)
    manifest=dict(version='V9.5D-666-REASSEMBLED-R7',mode='PAPER_ONLY',pid=1,run_directory=str(run),
        run_root=str(run.parent),storage_policy_version='R7_E_BACKED_LONG_RUN_V1',
        hotfix_id='666-ROOT-AUDIT-REASSEMBLED-R7',reconciliation_build='ROOT-AUDIT-REASSEMBLED-R7',
        started_utc=T,ended_utc=T+minutes*60+2,status='STOPPED',source_commit='synthetic')
    runtime=dict(run_id='R',session_id='S',pid=1,updated_wall=T+minutes*60+1,status='STOPPED',positions=[],quote={})
    write(run/'launcher_manifest.json',manifest);write(run/'tachys_runtime_hf2.json',runtime)
    (run/'tachys_canonical_trade_events_hf2.csv').write_text('timestamp,event,trade_id,ticker,side,run_id,session_id\n')
    (run/'hf21_decision_snapshots.jsonl').write_text(''.join(json.dumps(record(T+(i+1)*60+1,[candle(T+j*60) for j in range(max(0,i-23),i+1)]))+'\n' for i in range(minutes)))
    return run,manifest,runtime


def drain(history,limit=100):
    for _ in range(limit):
        history.step(budget=.1)
        if history.snapshot()['status'] in ('READY','GAPS','MISSING','READ_ERROR'):
            return history.snapshot()
    raise AssertionError('History did not finish its bounded test scan')


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.run,self.man,self.rt=fixture(self.root)
    def history(self,**kw):
        h=CandleHistory(self.run,self.man,self.rt,**kw);self.addCleanup(h.close);return h
    def test_bootstrap_covers_45_minutes_plus_margin(self):
        h=self.history();s=drain(h)
        self.assertEqual(s['status'],'READY');self.assertEqual(s['completed_minutes'],45)
        self.assertGreaterEqual(len(s['candles']),60)
    def test_backward_request_extends_history(self):
        h=self.history();drain(h);h.request(T+60,T+45*60)
        s=drain(h);self.assertEqual(s['status'],'READY');self.assertTrue(any(b['time']==T+60 for b in s['candles']))
    def test_reverse_reader_handles_multiblock_utf8(self):
        p=self.root/'reverse';lines=['first','ñ'*15,'third'*20,'last']
        p.write_bytes(('\n'.join(lines)+'\npartial').encode())
        with patch('candle_history.CHUNK',13):
            r=ReverseLines(p,p.stat().st_size);out=[]
            while True:
                x=r.step()
                if x is None:break
                if x:out.append(x[1].decode())
        self.assertEqual(out,list(reversed(lines)))
    def test_reverse_resume_known_boundary(self):
        p=self.root/'reverse';p.write_bytes(b'a\nb\nc\n')
        r=ReverseLines(p,4,start=4);out=[]
        while True:
            x=r.step()
            if x is None:break
            if x and x[1]:out.append(x[1])
        self.assertEqual(out,[b'b',b'a'])
    def test_unknown_identity_not_promoted(self):
        h=self.history();o=record(T+61,[candle(T)]);o['identity']['session_id']='WRONG'
        h.ingest(json.dumps(o).encode(),'forward');self.assertFalse(h.bars);self.assertEqual(h.stats['identity_rejected'],1)
    def test_missing_identity_rejected(self):
        h=self.history();o=record(T+61,[candle(T)]);o['identity']={}
        h.ingest(json.dumps(o).encode(),'forward');self.assertFalse(h.bars)
    def test_invalid_ohlc_not_promoted(self):
        h=self.history();b=candle(T);b['high']=10
        h.ingest(json.dumps(record(T+61,[b])).encode(),'forward');self.assertFalse(h.bars)
    def test_future_bar_not_promoted(self):
        self.assertIsNone(bar(candle(T),T+30))
    def test_nan_or_bool_not_a_price(self):
        b=candle(T);b['high']=float('nan');self.assertIsNone(bar(b,T+61))
        b['high']=True;self.assertIsNone(bar(b,T+61))
    def test_completed_wins_over_older_observation(self):
        h=self.history();h.ingest(json.dumps(record(T+65,[candle(T,105)])).encode(),'forward')
        h.ingest(json.dumps(record(T+61,[candle(T,102)])).encode(),'backfill')
        self.assertEqual(h.bars[T]['close'],105);self.assertEqual(h.bars[T]['first_observed_in_scan'],T+61)
    def test_explicit_developing_separate(self):
        h=self.history();h.ingest(json.dumps(record(T+30,[],current_candle=candle(T))).encode(),'forward')
        self.assertFalse(h.bars);self.assertEqual(h.developing['quality'],'engine-developing')
    def test_observed_ticks_developing_stays_sampled(self):
        h=self.history();b=candle(T);b['source']='OBSERVED_TICKS_ONLY'
        h.ingest(json.dumps(record(T+30,[],current_candle=b)).encode(),'forward')
        self.assertEqual(h.developing['quality'],'sampled')
    def test_no_explicit_developing_not_invented(self):
        h=self.history();s=drain(h);self.assertIsNone(s['developing'])
    def test_missing_snapshot_reported(self):
        (self.run/'hf21_decision_snapshots.jsonl').unlink();self.assertEqual(drain(self.history())['status'],'MISSING')
    def test_malformed_snapshots_reported(self):
        h=self.history();h.ingest(b'{','forward');self.assertEqual(h.stats['malformed_records'],1)
    def test_capture_utc_mismatch(self):
        h=self.history();o=record(T+61,[candle(T)]);o['captured_at_utc']=T+65
        h.ingest(json.dumps(o).encode(),'forward');self.assertFalse(h.bars)
    def test_gaps_reported_without_approximation(self):
        (self.run/'hf21_decision_snapshots.jsonl').write_text(json.dumps(record(T+61,[candle(T)]))+'\n')
        self.assertEqual(drain(self.history())['status'],'GAPS')
    def test_cache_resumes_exact_source(self):
        h=self.history(cache_root=self.root/'cache');s=drain(h);h.save_cache(force=True)
        h2=self.history(cache_root=self.root/'cache');s2=drain(h2)
        self.assertTrue(s2['cache_loaded']);self.assertEqual(s['candles'],s2['candles'])
    def test_wrong_cache_identity_rejected(self):
        h=self.history(cache_root=self.root/'cache');drain(h);h.save_cache(force=True)
        x=json.loads(h.cache_path.read_text());x['identity']['session_id']='OTHER';write(h.cache_path,x)
        h2=self.history(cache_root=self.root/'cache');s=drain(h2)
        self.assertFalse(s['cache_loaded']);self.assertEqual(s['stats']['cache_rejected'],1)
    def test_cache_byte_anchor_mismatch_rejected(self):
        h=self.history(cache_root=self.root/'cache');drain(h);h.save_cache(force=True)
        x=json.loads(h.cache_path.read_text());x['anchor']='wrong';write(h.cache_path,x)
        s=drain(self.history(cache_root=self.root/'cache'));self.assertFalse(s['cache_loaded'])
    def test_cache_cannot_be_in_run(self):
        with self.assertRaises(ValueError):self.history(cache_root=self.run/'cache')
    def test_forward_append_after_cache_not_lost(self):
        h=self.history(cache_root=self.root/'cache');drain(h);h.save_cache(force=True)
        b=candle(T+99*60,108)
        with h.path.open('ab') as f:f.write((json.dumps(record(T+100*60+1,[b]))+'\n').encode())
        h2=self.history(cache_root=self.root/'cache');drain(h2)
        self.assertTrue(h2.cache_loaded);self.assertEqual(h2.bars[b['minute']]['close'],108)
    def test_incomplete_at_attachment_finishes(self):
        h=self.history();raw=(json.dumps(record(T+6001,[candle(T+5940,107)]))+'\n').encode()
        original=h.path.read_bytes();h.path.write_bytes(original+raw[:100]);drain(h)
        with h.path.open('ab') as f:f.write(raw[100:])
        h.step();self.assertEqual(h.bars[T+5940]['close'],107)
    def test_truncation_does_not_keep_previous_source_bars(self):
        h=self.history();drain(h);h.path.write_text(json.dumps(record(T+61,[candle(T)]))+'\n')
        h.step();self.assertEqual(len(h.bars),1);self.assertEqual(h.stats['source_resets'],1)
    def test_source_files_are_never_written(self):
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir()}
        h=self.history(cache_root=self.root/'cache');drain(h);h.save_cache(force=True)
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir()}
        self.assertEqual(before,after)
    def test_thread_stops_without_engine_process(self):
        h=self.history();h.start();time.sleep(.12);h.close();self.assertFalse(h.thread.is_alive())
    def test_invalid_view_request_does_not_change_coverage(self):
        h=self.history();old=h.requested_start
        self.assertFalse(h.request(float('nan'),T+60));self.assertFalse(h.request(T,T+999999));self.assertEqual(h.requested_start,old)


class ClockTests(unittest.TestCase):
    def state(self,**extra):
        r=dict(fresh=True,stopped=False,review=False,pointer_changed=False,updated=T);r.update(extra)
        return {'run':r,'market':{'fresh':False,'time':T-100}}
    def test_stale_price_does_not_stop_verified_clock(self):
        c=ClockGuard().sample(T,100);timer=verified_timer(self.state(),{'quote':{'ticker':'CONTRACT','close_ts':T+577}},T,c)
        self.assertTrue(timer['verified']);self.assertEqual(timer['status'],'RUNNING')
    def test_stale_quote_values_not_needed_for_close_time(self):
        c=ClockGuard().sample(T,100)
        self.assertTrue(verified_timer(self.state(),{'quote':{'ticker':'A','close_ts':T+500,'valid':False}},T,c)['verified'])
    def test_stale_runtime_pauses(self):
        t=verified_timer(self.state(fresh=False),{'quote':{'ticker':'A','close_ts':T+500}},T,ClockGuard().sample(T,100))
        self.assertFalse(t['verified'])
    def test_pointer_change_pauses(self):
        self.assertFalse(verified_timer(self.state(pointer_changed=True),{'quote':{'ticker':'A','close_ts':T+500}},T,ClockGuard().sample(T,100))['verified'])
    def test_clock_jump_quarantined_then_recovers(self):
        g=ClockGuard();self.assertTrue(g.sample(T,100)['continuous'])
        self.assertFalse(g.sample(T+11,101)['continuous']);self.assertTrue(g.sample(T+42,132)['continuous'])
    def test_missing_ticker_or_invalid_close_pauses(self):
        for q in [{'close_ts':T+500},{'ticker':'A','close_ts':T+1500},{'ticker':'A','close_ts':T-1}]:
            self.assertFalse(verified_timer(self.state(),{'quote':q},T,ClockGuard().sample(T,100))['verified'])
    def test_stopped_archive_not_running(self):
        for flag in ['stopped','review']:
            s=self.state(stopped=True,review=flag=='review')
            self.assertFalse(verified_timer(s,{'quote':{'ticker':'A','close_ts':T+500}},T,ClockGuard().sample(T,100))['verified'])


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.run,self.man,self.rt=fixture(self.root,minutes=2);self.lab=self.root/'lab';self.lab.mkdir()
    def observer(self,status='FAILED'):
        out=self.root/'obs';write(self.lab/'LATEST_OBSERVER42_R7.json',{'output_directory':str(out)})
        write(out/'observer_manifest.json',dict(source_run_directory=str(self.run),authority='NONE',
              observer_revision='TACHYS-COMMANDER-OBS4.2-ROOT-AUDIT-REASSEMBLED-R7',status=status,
              heartbeat_utc=T+100,failure_diagnostic={'exception_message':'Future CSV timestamp','recorded_utc':T+100}))
        return out
    def test_failed_observer_is_independent(self):
        self.observer();h=SidecarHealth(self.lab,str(self.run),self.man['version']).poll(T+101,False)
        self.assertEqual(h['observer']['status'],'FAILED');self.assertEqual(h['observer']['reason'],'Future CSV timestamp')
    def test_failed_observer_preserved_after_engine_stops(self):
        self.observer();h=SidecarHealth(self.lab,str(self.run),self.man['version']).poll(T+120,True)
        self.assertEqual(h['observer']['status'],'FAILED')
    def test_wrong_sidecar_not_attached_by_filename(self):
        out=self.observer();m=json.loads((out/'observer_manifest.json').read_text());m['source_run_directory']='E:/different/run';write(out/'observer_manifest.json',m)
        self.assertEqual(SidecarHealth(self.lab,str(self.run),self.man['version']).poll(T+101,False)['observer']['status'],'UNVERIFIED')
    def test_partial_sidecar_json_is_read_error_not_green(self):
        out=self.observer();health=SidecarHealth(self.lab,str(self.run),self.man['version']);health.poll(T+101,False)
        (out/'observer_manifest.json').write_text('{');s=health.poll(T+102,False)['observer']
        self.assertEqual(s['status'],'READ_ERROR');self.assertEqual(s['last_verified_status'],'FAILED');self.assertEqual(s['reader_errors'],1)
    def test_navigator_stale_is_explicit(self):
        write(self.lab/'LATEST_KINGS_NAVIGATOR_STATUS.json',dict(run_directory=str(self.run),engine_version=self.man['version'],execution_authority=False,timestamp_utc=T))
        h=SidecarHealth(self.lab,str(self.run),self.man['version']).poll(T+100,False)
        self.assertEqual(h['navigator']['status'],'STALE')
    def test_navigator_matching_basename_other_root_rejected(self):
        write(self.lab/'LATEST_KINGS_NAVIGATOR_STATUS.json',dict(run_directory='E:/other/'+self.run.name,engine_version=self.man['version'],execution_authority=False,timestamp_utc=T+100))
        self.assertEqual(SidecarHealth(self.lab,str(self.run),self.man['version']).poll(T+100,False)['navigator']['status'],'UNVERIFIED')
    def test_receipt_small_separate_and_truthfully_scoped(self):
        r=HealthReceipt(self.root/'health/test.json',{'session':'S'})
        state={'server_now':T,'health':{'observer':{'status':'FAILED'}},'diagnostics':{'storage':{}}}
        for _ in range(100):r.sample(state)
        r.request();r.close();d=json.loads(r.path.read_text())
        self.assertEqual(d['component_samples']['observer']['FAILED'],100);self.assertEqual(d['http_state_requests'],1);self.assertLess(r.path.stat().st_size,2000)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.run,self.man,self.rt=fixture(self.root,minutes=65)
    def test_preserved_accounting_and_async_history(self):
        a=Adapter(self.run,self.man,review=True,cache_root=self.root/'cache');self.addCleanup(a.close)
        s=a.poll(T+3902);self.assertEqual(s['accounting']['realized'],0);self.assertTrue(s['readonly'])
        drain(a.history);s=a.poll(T+3902);self.assertEqual(s['history']['status'],'READY')
        self.assertGreaterEqual(len(s['candles']),60)
    def test_health_failure_does_not_change_canonical_accounting(self):
        a=Adapter(self.run,self.man,lab=self.root/'missing',review=True);self.addCleanup(a.close)
        s=a.poll(T+3902);self.assertEqual(s['accounting']['realized'],0);self.assertFalse(s['accounting']['issues'])
        self.assertEqual(s['health']['observer']['status'],'MISSING')
    def test_http_still_read_only_and_history_query_is_bounded(self):
        a=Adapter(self.run,self.man,review=True);self.addCleanup(a.close);p=Publisher(a);p.once()
        server=LocalServer(('127.0.0.1',0),Handler);server.token='test';server.publisher=p
        t=threading.Thread(target=server.serve_forever,daemon=True);t.start()
        try:
            for method,path,expected in [('GET','/reliability-ui.js',200),('GET',f'/api/state?chart_from={T}&chart_to={T+3600}',200),('POST','/api/state',405),('GET','/api/close-all',404)]:
                c=http.client.HTTPConnection('127.0.0.1',server.server_port);c.request(method,path,headers={'X-Nautilus-Read':'test'});r=c.getresponse();r.read();self.assertEqual(r.status,expected);c.close()
        finally:server.shutdown();server.server_close();t.join()
    def test_engine_adapter_is_exact_R7_bytes(self):
        root=Path(__file__).resolve().parents[1]
        # SHA recorded by this release's construction from the actual R7 package.
        expected=json.loads((root.parent/'BASELINE_PROVENANCE.json').read_text())['sha256']['adapter.py']
        self.assertEqual(hashlib.sha256((root/'adapter.py').read_bytes()).hexdigest(),expected)

if __name__=='__main__':unittest.main()
