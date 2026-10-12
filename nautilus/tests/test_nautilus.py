"""Run with: python -B -m unittest discover -s nautilus/tests -v.

Synthetic fixtures exercise edge cases; no trading modules or credentials used.
"""
import csv
import gzip
import hashlib
import http.client
import json
import math
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapter import Adapter, Tail, assemble_trades, complete_csv, epoch, feed_line, mark_position, resolve_run
from server import Handler, LocalServer, Publisher, finite_json

NOW = 1_790_000_100.0
RUN_ID, SESSION = 'DTEST', 'DTEST_PID100'
FIELDS = ['timestamp', 'run_id', 'session_id', 'event', 'trade_id', 'ticker', 'side', 'role', 'entry_ask', 'bid', 'qty', 'cost', 'pnl', 'mfe_pct', 'mae_pct', 'reason']


def event(kind='ENTRY', trade_id='1', **changes):
    row = dict(timestamp=str(NOW - (20 if kind == 'ENTRY' else 5)), run_id=RUN_ID,
               session_id=SESSION, event=kind, trade_id=trade_id, ticker='CONTRACT_A',
               side='YES', role='MAIN', entry_ask='0.40', bid='0.60', qty='10',
               cost='4.00', pnl='2.00', mfe_pct='50', mae_pct='-5', reason='Recorded reason')
    row.update(changes)
    return row


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=fields)
        wr.writeheader()
        wr.writerows(rows)


def fixture(root, closed=False):
    lab = root / 'lab'
    run = lab / 'runs' / '666_lab_TEST_PID100'
    run.mkdir(parents=True)
    manifest = dict(mode='PAPER_ONLY', version='V9.5D-666-REASSEMBLED-R6',
                    hotfix_id='666-ROOT-AUDIT-REASSEMBLED-R6',
                    reconciliation_build='ROOT-AUDIT-REASSEMBLED-R6',
                    run_directory=str(run), pid=100, status='RUNNING', source_commit='test-only')
    (run / 'launcher_manifest.json').write_text(json.dumps(manifest))
    pointer = lab / 'LATEST_TACHYS_REASSEMBLED_R6_RUN.json'
    pointer.write_text(json.dumps({'run_directory': str(run)}))
    rows = [event()] + ([event('EXIT')] if closed else [])
    write_csv(run / 'tachys_canonical_trade_events_hf2.csv', FIELDS, rows)
    q = dict(ticker='CONTRACT_A', quote_id='Q1', valid=True, receive_age_sec=.2,
             yes_bid=.6, yes_ask=.61, no_bid=.39, no_ask=.4, close_ts=NOW+400,
             yes_sell_allowed=True, no_sell_allowed=True, entry_allowed=True, reason='VALID')
    p = dict(ticker='CONTRACT_A', trade_id='1', side='YES', role='MAIN', current_bid=.6,
             quote_id='Q1', mark_valid=True, open_pnl=2, mfe_pct=50)
    runtime = dict(run_id=RUN_ID, session_id=SESSION, pid=100, status='RUNNING',
                   updated_wall=NOW, quote=q, positions=[] if closed else [p])
    (run / 'tachys_runtime_hf2.json').write_text(json.dumps(runtime))
    market = dict(timestamp=str(NOW), ticker='CONTRACT_A', btc_price='83001.50',
                  ema9='83000.00', ema30='82998.00', target='83000.00', seconds_left='400',
                  price_arc_phase='EXPANSION', arc_direction='UP', battlefield_class='MOUNTAIN')
    write_csv(run / 'tachys_price_arc_phase_v9_4j.csv', list(market), [market])
    (run / 'console.log').write_text('QUOTE HEALTH | VALID\nENTRY | YES #1\n')
    return lab, run, manifest, pointer, runtime


class ReaderTests(unittest.TestCase):
    def test_epochs_are_explicit_and_finite(self):
        self.assertIsNone(epoch('2026-10-11T12:00:00'))
        self.assertIsNotNone(epoch('2026-10-11T12:00:00+00:00'))
        self.assertEqual(epoch(1790000000000), 1790000000)
        self.assertIsNone(epoch('NaN'))

    def test_partial_csv_is_not_published_until_complete(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'t.csv';p.write_bytes(b'a,b\n1,')
            reader = Tail(p)
            self.assertEqual(reader.rows(), [])
            with p.open('ab') as f:f.write(b'2\n')
            self.assertEqual(reader.rows()[0]['b'], '2')
            self.assertEqual(reader.rows(), [])

    def test_incomplete_header_recovers(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'t.csv';p.write_bytes(b'a,')
            reader = Tail(p);self.assertEqual(reader.rows(), [])
            with p.open('ab') as f:f.write(b'b\n1,2\n')
            self.assertEqual(reader.rows()[0]['a'], '1')

    def test_tail_rotation_and_truncation(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'t.log';p.write_text('longer first entry\n')
            reader = Tail(p);a = reader.lines()
            p.write_text('new\n');b = reader.lines()
            self.assertEqual(b[0][1], 'new');self.assertNotEqual(a[0][0], b[0][0])

    def test_malformed_tail_rows_counted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'t.csv';p.write_text('a,b\n1,2,3\n2,4\n')
            r = Tail(p);self.assertEqual(len(r.rows()), 1);self.assertEqual(r.bad_rows, 1)

    def test_complete_accounting_refuses_tail(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'ledger.csv';write_csv(p, FIELDS, [event(),event('EXIT')])
            self.assertEqual(len(complete_csv(p)), 2)
            with self.assertRaises(ValueError):complete_csv(p, max_bytes=10)

    def test_secret_and_markup_stay_text(self):
        line = feed_line('1', 'Authorization: Bearer TOPSECRET <script>bad</script>')
        self.assertNotIn('TOPSECRET', line['text'])
        self.assertIn('<script>', line['text']) # browser must render as textContent, not HTML


class AccountingTests(unittest.TestCase):
    def test_full_ledger_total(self):
        trades,total,issues = assemble_trades([event(),event('EXIT')], RUN_ID, SESSION)
        self.assertEqual(total,2);self.assertEqual(issues,[]);self.assertEqual(trades[0]['roi'],50)

    def test_same_side_distinct_generations_are_kept(self):
        trades,_,issues = assemble_trades([event(),event(trade_id='2')], RUN_ID, SESSION)
        self.assertEqual(len(trades),2);self.assertFalse(issues)

    def test_duplicates_withhold_total(self):
        _,total,issues = assemble_trades([event(),event(),event('EXIT')], RUN_ID, SESSION)
        self.assertIsNone(total);self.assertTrue(issues)

    def test_orphan_exit_withholds_total(self):
        _,total,issues = assemble_trades([event('EXIT')], RUN_ID, SESSION)
        self.assertIsNone(total);self.assertTrue(issues)

    def test_wrong_session_cannot_merge(self):
        _,total,issues = assemble_trades([event(session_id='DIFFERENT')],RUN_ID,SESSION)
        self.assertIsNone(total);self.assertTrue(issues)

    def test_zero_and_negative_basis_rejected(self):
        for cost in ('0','-1'):
            _,total,issues = assemble_trades([event(cost=cost)],RUN_ID,SESSION)
            self.assertIsNone(total);self.assertTrue(issues)

    def test_legitimate_zero_bid_is_not_missing(self):
        trade = assemble_trades([event()],RUN_ID,SESSION)[0][0]
        q = dict(ticker='CONTRACT_A',quote_id='Q',yes_bid=0,yes_sell_allowed=True,
                 valid=False,receive_age_sec=.1)
        detail = dict(mark_valid=True,current_bid=0,quote_id='Q',open_pnl=-4)
        p = mark_position(trade,detail,dict(quote=q,updated_wall=NOW),NOW,False)
        self.assertTrue(p['mark_valid']);self.assertEqual(p['current_bid'],0)

    def test_mismatched_or_stale_quote_withholds_mark(self):
        trade = assemble_trades([event()],RUN_ID,SESSION)[0][0]
        q = dict(ticker='CONTRACT_A',quote_id='Q',yes_bid=.6,yes_sell_allowed=True,receive_age_sec=.1)
        detail = dict(mark_valid=True,current_bid=.6,quote_id='WRONG',open_pnl=2)
        p = mark_position(trade,detail,dict(quote=q,updated_wall=NOW),NOW,False)
        self.assertFalse(p['mark_valid']);self.assertIsNone(p['open_pnl'])
        detail['quote_id']='Q';q['receive_age_sec']=4
        self.assertFalse(mark_position(trade,detail,dict(quote=q,updated_wall=NOW),NOW,False)['mark_valid'])


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lab,self.run,self.manifest,self.pointer,self.runtime = fixture(self.root)

    def adapter(self,review=False):return Adapter(self.run,self.manifest,self.lab,self.pointer,review)

    def test_exact_pointer_and_build(self):
        run,m,_ = resolve_run(self.lab,'R6',None,False)
        self.assertEqual(run,self.run);self.assertEqual(m['pid'],100)
        with self.assertRaises(ValueError):resolve_run(self.lab,'R5',self.run,False)

    def test_live_manifest_path_mismatch_refused(self):
        m=dict(self.manifest,run_directory=str(self.root/'other'))
        (self.run/'launcher_manifest.json').write_text(json.dumps(m))
        with self.assertRaises(ValueError):resolve_run(self.lab,'R6',self.run,False)

    def test_live_mode_manifest_refused(self):
        m=dict(self.manifest,mode='LIVE')
        (self.run/'launcher_manifest.json').write_text(json.dumps(m))
        with self.assertRaises(ValueError):resolve_run(self.lab,'R6',self.run,False)

    def test_current_data_and_read_only(self):
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir()}
        data=self.adapter().poll(NOW)
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir()}
        self.assertEqual(before,after)
        self.assertTrue(data['run']['fresh']);self.assertEqual(data['positions'][0]['open_pnl'],2)
        self.assertEqual(data['quote']['yes_bid'],.6)
        self.assertEqual(data['candles'][0]['quality'],'sampled')

    def test_review_suppresses_marks_and_quotes(self):
        data=self.adapter(True).poll(NOW)
        self.assertFalse(data['run']['fresh']);self.assertIsNone(data['positions'][0]['open_pnl'])
        self.assertIsNone(data['quote']['yes_bid'])

    def test_stopped_state_not_green(self):
        self.runtime['status']='STOPPED';(self.run/'tachys_runtime_hf2.json').write_text(json.dumps(self.runtime))
        data=self.adapter().poll(NOW)
        self.assertTrue(data['run']['stopped']);self.assertFalse(data['run']['fresh'])

    def test_missing_ledger_not_flat(self):
        (self.run/'tachys_canonical_trade_events_hf2.csv').unlink()
        data=self.adapter().poll(NOW)
        self.assertIsNone(data['accounting']['realized']);self.assertTrue(data['accounting']['issues'])

    def test_runtime_pid_mismatch_not_current(self):
        self.runtime['pid']=200;(self.run/'tachys_runtime_hf2.json').write_text(json.dumps(self.runtime))
        data=self.adapter().poll(NOW)
        self.assertFalse(data['run']['fresh']);self.assertIsNone(data['accounting']['realized'])

    def test_manifest_change_does_not_borrow_identity(self):
        adapter=self.adapter();adapter.poll(NOW)
        (self.run/'launcher_manifest.json').write_text(json.dumps(dict(self.manifest,pid=200)))
        data=adapter.poll(NOW)
        self.assertFalse(data['run']['fresh']);self.assertTrue(data['diagnostics']['issues'])

    def test_pointer_change_does_not_rebind(self):
        adapter=self.adapter();adapter.poll(NOW)
        self.pointer.write_text(json.dumps({'run_directory':str(self.root/'other')}))
        data=adapter.poll(NOW)
        self.assertTrue(data['run']['pointer_changed']);self.assertEqual(data['run']['path'],str(self.run))

    def test_completed_candle_replaces_sample_and_rejects_future(self):
        a=self.adapter();a.poll(NOW)
        minute=int(NOW//60*60)
        candle=dict(minute=minute,open=83000,high=83020,low=82990,close=83005)
        a.ingest_snapshot({'captured_at_epoch':minute+61,'frame':{'box_candles':[candle]}})
        self.assertEqual(a.candles[minute]['quality'],'engine-completed')
        candle['minute']=minute+120
        a.ingest_snapshot({'captured_at_epoch':minute+61,'frame':{'box_candles':[candle]}})
        self.assertNotIn(minute+120,a.candles)

    def test_native_quote_contracts_never_synthesized(self):
        a=self.adapter()
        a.ingest_quote(dict(timestamp=str(NOW),ticker='A',yes_bid='.4',receive_age_sec='.1',valid='True'))
        a.ingest_quote(dict(timestamp=str(NOW+1),ticker='B',no_bid='.2',receive_age_sec='.1',valid='True'))
        self.assertIsNone(a.quotes[0]['no_bid']);self.assertEqual(a.quotes[1]['ticker'],'B')

    def test_stale_market_target_does_not_become_new_contract_target(self):
        self.runtime['quote']['ticker']='CONTRACT_B'
        (self.run/'tachys_runtime_hf2.json').write_text(json.dumps(self.runtime))
        d=self.adapter().poll(NOW)
        self.assertIsNone(d['market']['target']);self.assertFalse(d['market']['fresh'])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        lab,run,manifest,pointer,_=fixture(Path(self.temp.name),closed=True)
        self.server=LocalServer(('127.0.0.1',0),Handler)
        self.server.token='local-test-token';self.server.publisher=Publisher(Adapter(run,manifest,lab,pointer,True))
        self.server.publisher.once()
        thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def request(self,path='/',method='GET',headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        c.request(method,path,headers=headers or {});response=c.getresponse()
        result=(response.status,dict(response.getheaders()),response.read());c.close();return result

    def test_static_files_and_security_headers(self):
        for path in ['/','/app.js','/chart.js','/style.css']:
            status,headers,body=self.request(path)
            self.assertEqual(status,200);self.assertTrue(body)
            self.assertEqual(headers['X-Content-Type-Options'],'nosniff')
        self.assertIn(b'local-test-token',self.request('/')[2])

    def test_api_requires_token_and_returns_finite_json(self):
        self.assertEqual(self.request('/api/state')[0],403)
        status,_,body=self.request('/api/state',headers={'X-Nautilus-Read':'local-test-token'})
        data=json.loads(body);self.assertEqual(status,200);self.assertTrue(data['readonly'])
        self.assertEqual(data['accounting']['realized'],2)
        self.assertIsNone(finite_json(float('nan')))

    def test_gzip(self):
        status,headers,body=self.request('/api/state',headers={'X-Nautilus-Read':'local-test-token','Accept-Encoding':'gzip'})
        self.assertEqual(status,200);self.assertEqual(headers['Content-Encoding'],'gzip')
        self.assertEqual(json.loads(gzip.decompress(body))['mode'],'PAPER_ONLY')

    def test_write_methods_refused(self):
        for method in ['POST','PUT','PATCH','DELETE']:
            self.assertEqual(self.request('/api/state',method)[0],405)

    def test_arbitrary_file_paths_refused(self):
        for path in ['/../adapter.py','/%2e%2e/server.py','/launcher_manifest.json','/api/start','/api/close-all']:
            self.assertEqual(self.request(path)[0],404)

    def test_foreign_host_origin_and_cross_site_refused(self):
        for headers in [{'Host':'evil.example'},{'Origin':'https://evil.example'},{'Sec-Fetch-Site':'cross-site'}]:
            self.assertEqual(self.request('/',headers=headers)[0],403)


if __name__=='__main__':unittest.main()
