"""Synthetic HF21 fixtures. No trading or network imports."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

SPEC=importlib.util.spec_from_file_location('coverage_tool',Path(__file__).resolve().parents[1]/'tools'/'candle_coverage.py')
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)
T=1791790260  # minute-aligned UTC

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.run=self.root/'666_lab_TEST_PID1';self.run.mkdir()
        self.manifest=dict(mode='PAPER_ONLY',status='STOPPED',pid=1,run_directory=str(self.run),
                           version='V9.5D-666-REASSEMBLED-R7',started_utc=m.utc(T),ended_utc=m.utc(T+185))
        self.runtime=dict(run_id='R',session_id='S',pid=1,updated_wall=T+185)
        self.write('launcher_manifest.json',self.manifest);self.write('tachys_runtime_hf2.json',self.runtime)
        self.records=[self.record(T+60,T),self.record(T+120,T+60),self.record(T+180,T+120)]
        self.snapshots()
        self.write('hf21_decision_snapshots.jsonl.stats.json',dict(enqueued=3,written=3,errors=0,dropped=0,shutdown_drained=True,worker_stopped=True))
    def write(self,name,data):
        (self.run/name).write_text(json.dumps(data),encoding='utf-8')
    def bar(self,t,**extra):
        return dict(minute=t,open=100.,high=110.,low=90.,close=102.,**extra)
    def record(self,t,minute):
        return dict(schema='HF21_SNAPSHOT_V1',captured_at_epoch=t,captured_at_utc=m.utc(t),
                    identity=dict(run_id='R',session_id='S'),event='POSITION',
                    frame=dict(now=t,box_candles=[self.bar(minute)]))
    def snapshots(self,raw=None):
        (self.run/'hf21_decision_snapshots.jsonl').write_bytes(raw if raw is not None else ''.join(json.dumps(r)+'\n' for r in self.records).encode())
    def audit(self):return m.analyze(self.run)
    def test_complete_three_minutes(self):
        s,r=self.audit();self.assertEqual(s['verdict'],'COMPLETED_CANDLE_COVERAGE_PRESENT')
        self.assertEqual(s['candle_coverage']['unique_verified_completed_minutes'],3)
        self.assertTrue(s['writer']['complete_lines_match_written'])
        self.assertEqual(len(r),4)
    def test_partial_start_end_minutes_not_required(self):
        self.manifest.update(started_utc=m.utc(T+10),ended_utc=m.utc(T+185));self.write('launcher_manifest.json',self.manifest)
        s,r=self.audit();self.assertEqual(s['candle_coverage']['expected_fully_contained_minutes'],2)
        self.assertFalse(r[0]['fully_contained_in_run']);self.assertFalse(r[-1]['fully_contained_in_run'])
    def test_repeated_history_is_unique_not_new_candles(self):
        self.records[1]['frame']['box_candles'].append(self.bar(T));self.snapshots()
        s,_=self.audit();self.assertEqual(s['candle_coverage']['unique_verified_completed_minutes'],3)
        self.assertEqual(s['record_counts']['completed_candle_occurrences_examined'],4)
    def test_foreign_session_excluded(self):
        self.records[1]['identity']['session_id']='FOREIGN';self.snapshots()
        s,_=self.audit();self.assertEqual(s['candle_coverage']['missing_verified_minutes'],1)
        self.assertEqual(s['record_counts']['foreign_identity_records'],1)
        self.assertNotEqual(s['verdict'],'COMPLETED_CANDLE_COVERAGE_PRESENT')
    def test_missing_identity_not_promoted(self):
        self.records[1]['identity']={};self.snapshots();s,_=self.audit()
        self.assertEqual(s['candle_coverage']['unique_completed_minutes_any_identity'],3)
        self.assertEqual(s['candle_coverage']['unique_verified_completed_minutes'],2)
    def test_missing_runtime_identity_unverified(self):
        del self.runtime['session_id'];self.write('tachys_runtime_hf2.json',self.runtime)
        s,_=self.audit();self.assertEqual(s['candle_coverage']['unique_verified_completed_minutes'],0)
    def test_future_completed_bar_rejected(self):
        self.records[1]['frame']['box_candles']=[self.bar(T+120)];self.snapshots()
        s,_=self.audit();self.assertEqual(s['invalid_candle_counts']['not_completed_at_capture'],1)
        self.assertEqual(s['candle_coverage']['missing_verified_minutes'],1)
    def test_invalid_ohlc_rejected(self):
        self.records[1]['frame']['box_candles'][0]['low']=120;self.snapshots()
        s,_=self.audit();self.assertEqual(s['invalid_candle_counts']['inconsistent_ohlc'],1)
    def test_missing_price_not_fabricated(self):
        del self.records[1]['frame']['box_candles'][0]['high'];self.snapshots()
        s,_=self.audit();self.assertEqual(s['invalid_candle_counts']['missing_or_invalid_ohlc'],1)
    def test_unaligned_minute_rejected(self):
        self.records[1]['frame']['box_candles'][0]['minute']+=1;self.snapshots()
        s,_=self.audit();self.assertEqual(s['invalid_candle_counts']['invalid_minute'],1)
    def test_developing_does_not_count_completed(self):
        self.records[1]['frame']['current_candle']=self.bar(T+120)
        self.records[1]['frame']['box_candles']=[];self.snapshots()
        s,_=self.audit();self.assertEqual(s['candle_coverage']['current_candle_minutes'],1)
        self.assertEqual(s['candle_coverage']['missing_verified_minutes'],1)
    def test_no_current_candle_not_error_in_writer(self):
        s,_=self.audit();self.assertEqual(s['candle_coverage']['current_candle_minutes'],0)
        self.assertTrue(s['writer']['complete_lines_match_written'])
    def test_truncated_final_line_excluded(self):
        data=(self.run/'hf21_decision_snapshots.jsonl').read_bytes();self.snapshots(data[:-1])
        s,_=self.audit();self.assertEqual(s['record_counts']['unterminated_final_line'],1)
        self.assertFalse(s['writer']['complete_lines_match_written'])
    def test_malformed_json_no_raw_payload_exported(self):
        self.snapshots(b'badSECRETJSON\n');s,_=self.audit()
        self.assertEqual(s['record_counts']['malformed_json'],1)
        self.assertNotIn('SECRET',json.dumps(s))
    def test_json_infinity_rejected(self):
        self.snapshots(b'{"bad":Infinity}\n');s,_=self.audit()
        self.assertEqual(s['record_counts']['malformed_json'],1)
    def test_unsupported_schema_explicit(self):
        self.records[0]['schema']='OTHER';self.snapshots();s,_=self.audit()
        self.assertEqual(s['record_counts']['unsupported_schema'],1)
    def test_timestamp_fields_conflict(self):
        self.records[0]['captured_at_utc']=m.utc(T+100);self.snapshots();s,_=self.audit()
        self.assertEqual(s['record_counts']['capture_timestamp_conflicts'],1)
    def test_timezone_naive_not_assumed(self):
        self.assertIsNone(m.stamp('2026-10-12T00:00:00'));self.assertIsNone(m.stamp(True))
    def test_completed_revision_and_lag(self):
        b=self.bar(T);b['high']=115
        self.records[1]['frame']['box_candles'].append(b);self.snapshots()
        s,r=self.audit();self.assertEqual(r[0]['completed_value_changes'],1)
        self.assertEqual(r[0]['first_verified_lag_after_close_sec'],0)
    def test_out_of_order_capture_detected(self):
        self.records.reverse();self.snapshots();s,_=self.audit()
        self.assertEqual(s['snapshots_verified_timeline']['out_of_order'],2)
    def test_tail_window_is_not_full_stream(self):
        with patch.object(m,'ADAPTER_TAIL',200):s,_=self.audit()
        self.assertEqual(s['candle_coverage']['unique_verified_completed_minutes'],3)
        self.assertLess(s['candle_coverage']['completed_minutes_in_default_8MB_tail'],3)
    def test_live_run_refused_without_opt_in(self):
        self.manifest['status']='RUNNING';self.write('launcher_manifest.json',self.manifest)
        with self.assertRaises(ValueError):self.audit()
        s,_=m.analyze(self.run,allow_live=True)
        self.assertNotEqual(s['verdict'],'COMPLETED_CANDLE_COVERAGE_PRESENT')
    def test_pid_disagreement_refused(self):
        self.runtime['pid']=2;self.write('tachys_runtime_hf2.json',self.runtime)
        with self.assertRaises(ValueError):self.audit()
    def test_wrong_directory_refused(self):
        self.manifest['run_directory']='E:\\runs\\another';self.write('launcher_manifest.json',self.manifest)
        with self.assertRaises(ValueError):self.audit()
    def test_no_snapshot_no_fake_report(self):
        (self.run/'hf21_decision_snapshots.jsonl').unlink()
        with self.assertRaises(ValueError):self.audit()
    def test_changed_source_cannot_pass(self):
        changed=[]
        def progress(n,total):
            if not changed:
                with (self.run/'hf21_decision_snapshots.jsonl').open('ab') as f:f.write(b'{}\n')
                changed.append(True)
        s,_=m.analyze(self.run,progress=progress)
        self.assertFalse(s['sources']['snapshot']['stable'])
        self.assertEqual(s['record_counts']['json_objects'],3)
        self.assertNotEqual(s['verdict'],'COMPLETED_CANDLE_COVERAGE_PRESENT')
    def test_oversized_line_drained_bounded_then_next_line_read(self):
        self.snapshots(b'x'*101+b'\n'+b'{}\n')
        with patch.object(m,'MAX_LINE',100):s,_=self.audit()
        self.assertEqual(s['record_counts']['oversized_lines'],1)
        self.assertEqual(s['record_counts']['json_objects'],1)
    def test_report_outside_run_and_no_source_changes(self):
        before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir()}
        s,r=self.audit()
        with self.assertRaises(ValueError):m.write_report(s,r,self.run/'report')
        z=m.write_report(s,r,self.root/'diagnostics')
        with ZipFile(z) as f:self.assertEqual(set(f.namelist()),{'REPORT.md','coverage.json','minutes.csv'})
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.run.iterdir()}
        self.assertEqual(before,after)
    def test_price_samples_are_separate(self):
        (self.run/'tachys_price_arc_phase_v9_4j.csv').write_text('timestamp,btc_price\n'+m.utc(T+5)+',100\n'+m.utc(T+30)+',105\n')
        s,r=self.audit();self.assertEqual(s['price_samples']['timeline']['records'],2)
        self.assertEqual(r[0]['sampled_high_shortfall'],5)
        self.assertEqual(r[0]['sampled_low_shortfall'],10)
    def test_stats_count_difference_does_not_claim_match(self):
        self.write('hf21_decision_snapshots.jsonl.stats.json',{'written':4})
        s,_=self.audit();self.assertFalse(s['writer']['complete_lines_match_written'])
    def test_seed_does_not_fill_missing_live_minutes(self):
        self.write('tachys_r15_history_seed.json',dict(status={'observed_at':T+180},candles=[self.bar(T+60)]))
        self.records[1]['frame']['box_candles']=[];self.snapshots()
        s,_=self.audit();self.assertEqual(s['candle_coverage']['missing_verified_minutes'],1)
    def test_windows_manifest_path_supported(self):
        self.manifest['run_directory']='E:\\TACHYS_DATA\\runs\\'+self.run.name
        self.write('launcher_manifest.json',self.manifest);s,_=self.audit()
        self.assertEqual(s['verdict'],'COMPLETED_CANDLE_COVERAGE_PRESENT')
    def test_missing_writer_stats_not_assumed_zero(self):
        (self.run/'hf21_decision_snapshots.jsonl.stats.json').unlink()
        s,_=self.audit();self.assertFalse(s['writer']['complete_lines_match_written'])
        self.assertEqual(s['sources']['writer_stats']['status'],'MISSING')
    def test_byte_fingerprint_covers_entire_scanned_file(self):
        s,_=self.audit();raw=(self.run/'hf21_decision_snapshots.jsonl').read_bytes()
        self.assertEqual(s['sources']['snapshot']['sha256_scanned_bytes'],hashlib.sha256(raw).hexdigest())
    def test_report_counters_reconcile_as_written_not_queue_assumption(self):
        s,_=self.audit()
        self.assertEqual(s['record_counts']['physical_lines'],3)
        self.assertTrue(s['writer']['complete_lines_match_written'])

if __name__=='__main__':unittest.main()
