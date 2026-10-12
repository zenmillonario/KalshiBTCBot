"""R7 UI reliability layer. Canonical accounting and trading code stay unchanged.

A component can fail independently of the engine. Clock continuity is local wall
clock vs monotonic time; this does NOT claim measured exchange clock offset.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import threading
import time
from collections import Counter
from pathlib import Path
from adapter import Adapter as R7Adapter, Tail, epoch, number, json_file, STOPPED
from candle_history import CandleHistory

VERSION='1.3.0-R7'


def canonical_path(value):
    return str(value or '').replace('\\','/').rstrip('/').casefold()


def component(status, *, updated=None, now=None, reason=None, **extra):
    return dict(status=status,updated=updated,age_seconds=now-updated if now is not None and updated is not None else None,
                reason=reason,**extra)


class ClockGuard:
    def __init__(self):
        self.previous=None
        self.untrusted_until=0

    def sample(self, wall, mono):
        delta=None
        if self.previous:
            old_wall,old_mono=self.previous
            delta=(wall-old_wall)-(mono-old_mono)
            if mono<old_mono or abs(delta)>2:
                self.untrusted_until=mono+30
        self.previous=(wall,mono)
        return dict(continuous=mono>=self.untrusted_until,wall_monotonic_delta=delta,
                    valid_until=wall+5,basis='LOCAL_WALL_CLOCK_WITH_MONOTONIC_CONTINUITY',
                    exchange_offset_measured=False)


def verified_timer(state, runtime, now, clock):
    q=runtime.get('quote') or {}
    ticker=q.get('ticker');end=number(q.get('close_ts'))
    good=bool(state['run']['fresh'] and not state['run']['stopped'] and not state['run']['pointer_changed'] and
              clock['continuous'] and ticker and isinstance(ticker,str) and end is not None and
              0 <= end-now <= 905 and not q.get('market_closed'))
    status='RUNNING' if good else 'ARCHIVE' if state['run']['review'] else 'ENDED' if state['run']['stopped'] else 'CLOCK_UNTRUSTED' if not clock['continuous'] else 'AWAITING_CONTRACT' if end is not None and end<=now else 'PAUSED'
    return dict(status=status,verified=good,ticker=ticker,close_ts=end,
                updated=state['run']['updated'],valid_until=min(clock['valid_until'],(state['run']['updated'] or 0)+5),
                basis='Exact current runtime quote contract close; independent of price/quote-value age',clock=clock)


class NoSnapshotTail(Tail):
    """The old synchronous 8MB tail is replaced, not run in parallel."""
    def lines(self,is_csv=False):
        return []


class SidecarHealth:
    def __init__(self, lab, original_run, engine_version):
        self.lab=Path(lab) if lab else None
        self.original_run=original_run
        self.engine_version=engine_version
        self.errors=Counter()
        self.previous={}

    def read(self,path,name,limit=500_000):
        try:
            obj=json_file(path,limit)
            if not obj:
                return None,'MISSING'
            return obj,None
        except (OSError,ValueError,TypeError):
            self.errors[name]+=1
            return None,'READ_ERROR'

    def unavailable(self,name,why):
        return component(why,reader_errors=self.errors[name],
                         last_verified_status=(self.previous.get(name) or {}).get('status'))

    def poll(self,now,stopped):
        if not self.lab:
            return {k:self.unavailable(k,'UNAVAILABLE') for k in ('observer','navigator')}
        result={}
        op,err=self.read(self.lab/'LATEST_OBSERVER42_R7.json','observer')
        if err:
            result['observer']=self.unavailable('observer',err)
        elif not op.get('output_directory'):
            result['observer']=self.unavailable('observer','UNVERIFIED')
        else:
            om,err=self.read(Path(op['output_directory'])/'observer_manifest.json','observer')
            if err:
                result['observer']=self.unavailable('observer',err)
            elif (canonical_path(om.get('source_run_directory'))!=canonical_path(self.original_run) or
                  om.get('observer_revision')!='TACHYS-COMMANDER-OBS4.2-ROOT-AUDIT-REASSEMBLED-R7' or
                  om.get('authority')!='NONE'):
                result['observer']=self.unavailable('observer','UNVERIFIED')
            else:
                ts=epoch(om.get('heartbeat_utc'))
                failure=om.get('failure_diagnostic') or {}
                native=str(om.get('status') or 'UNKNOWN').upper()
                status='FAILED' if native=='FAILED' else 'STOPPED' if native in STOPPED else 'LAST_RECORDED' if stopped else 'CURRENT' if ts is not None and 0<=now-ts<=15 else 'STALE'
                result['observer']=component(status,updated=ts,now=now,reader_errors=self.errors['observer'],
                    source_status=native,reason=failure.get('exception_message') or om.get('stop_reason'),
                    failed_at=epoch(failure.get('recorded_utc')) or epoch(om.get('ended_utc')),
                    output_directory=op['output_directory'],authority='NONE')
                self.previous['observer']=result['observer']
        nav,err=self.read(self.lab/'LATEST_KINGS_NAVIGATOR_STATUS.json','navigator')
        if err:
            result['navigator']=self.unavailable('navigator',err)
        elif (canonical_path(nav.get('run_directory'))!=canonical_path(self.original_run) or
              nav.get('engine_version')!=self.engine_version or nav.get('execution_authority') is not False):
            result['navigator']=self.unavailable('navigator','UNVERIFIED')
        else:
            ts=epoch(nav.get('timestamp_utc',nav.get('updated_utc')))
            native=str(nav.get('status') or '').upper()
            status='FAILED' if native=='FAILED' else 'STOPPED' if native in STOPPED else 'LAST_RECORDED' if stopped else 'CURRENT' if ts is not None and 0<=now-ts<=15 else 'STALE'
            result['navigator']=component(status,updated=ts,now=now,reader_errors=self.errors['navigator'],
                reason=nav.get('reason'),authority='NONE',
                error_note='Reader errors observed by this viewer only; absence is not proof of no sidecar errors')
            self.previous['navigator']=result['navigator']
        return result


class HealthReceipt:
    """Single compact per-viewer file; bounded counters, not another engine tape."""
    def __init__(self,path,identity):
        self.path=Path(path) if path else None
        self.lock=threading.Lock()
        self.body=dict(format=1,version=VERSION,identity=identity,started_utc=time.time(),
                       samples=0,http_state_requests=0,component_samples={},
                       note='Viewer-server observations since launch. HTTP requests are not proof of browser rendering or past uptime.')
        self.last_save=0;self.error=None

    def sample(self,state):
        with self.lock:
            self.body['samples']+=1
            self.body['last_sample_utc']=state['server_now']
            self.body['latest_health']=state.get('health')
            for name,detail in state.get('health',{}).items():
                s=detail['status'];counts=self.body['component_samples'].setdefault(name,{})
                counts[s]=counts.get(s,0)+1
            self.body['storage_last_observed']=state['diagnostics'].get('storage')
            self.body['latest_snapshot_writer_stats']=state['diagnostics'].get('snapshot_writer_stats')
            self.body['latest_history']={k:v for k,v in state.get('history',{}).items() if k not in ('missing_minutes',)}
            self.body.setdefault('storage_first_observed',self.body['storage_last_observed'])
        self.save()

    def request(self):
        with self.lock:
            self.body['http_state_requests']+=1
            self.body['last_http_request_utc']=time.time()

    def save(self,force=False):
        if not self.path or (not force and time.monotonic()-self.last_save<30):
            return
        temp=None
        try:
            with self.lock:
                raw=json.dumps(self.body,separators=(',',':'),allow_nan=False).encode()
            if len(raw)>200_000:
                raise ValueError('Receipt too large')
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.path.with_name(self.path.name+'.tmp')
            with temp.open('xb') as f:f.write(raw)
            os.replace(temp,self.path)
            self.last_save=time.monotonic();self.error=None
        except (OSError,ValueError) as exc:
            self.error=type(exc).__name__+': '+str(exc)[:120]
        finally:
            if temp and temp.exists():
                try:temp.unlink()
                except OSError:pass

    def close(self):
        with self.lock:
            self.body['viewer_stopped_utc']=time.time()
        self.save(force=True)


class Adapter(R7Adapter):
    def __init__(self,*args,cache_root=None,receipt_root=None,history_enabled=True,**kwargs):
        super().__init__(*args,**kwargs)
        self.runtime_record={};self.manifest_record={};self.history=None
        self.feeds['snapshots']=NoSnapshotTail(self.run/'hf21_decision_snapshots.jsonl')
        self.cache_root=cache_root;self.history_enabled=history_enabled;self.history_started=False
        self.clock_guard=ClockGuard()
        self.sidecar_health=SidecarHealth(self.lab,self.manifest.get('run_directory'),self.manifest.get('version'))
        self.receipt=None;self.receipt_root=Path(receipt_root) if receipt_root else None
        self.requested_window=None
        self.last_history_generation=None
        self.history_keys=set()

    def safe_json(self,name,limit=4_000_000):
        value=super().safe_json(name,limit)
        if name=='tachys_runtime_hf2.json':self.runtime_record=value
        if name=='launcher_manifest.json':self.manifest_record=value
        return value

    def start(self):
        self.history_started=True
        if self.history:self.history.start()

    def request_window(self,start,end):
        if self.history:
            return self.history.request(start,end)
        self.requested_window=(start,end)
        return False

    def poll(self,now=None):
        now=time.time() if now is None else now
        clock=self.clock_guard.sample(now,time.monotonic())
        state=super().poll(now)
        runtime=self.runtime_record
        identity_ok=(runtime.get('pid')==self.manifest.get('pid') and runtime.get('run_id') and runtime.get('session_id') and
                     all(self.manifest_record.get(k)==self.manifest.get(k) for k in ('pid','version','run_directory','mode','source_commit')))
        if identity_ok and self.history is None and self.history_enabled:
            self.history=CandleHistory(self.run,self.manifest_record,runtime,cache_root=self.cache_root)
            if self.requested_window:self.history.request(*self.requested_window)
            if self.history_started:self.history.start()
        if self.history and not all(runtime.get(k)==self.history.identity.get(k) for k in ('run_id','session_id','pid')):
            identity_ok=False
        if not identity_ok:
            state['run']['fresh']=False
        state['clock']=verified_timer(state,runtime,now,clock)
        h=self.history.snapshot() if self.history else dict(status='UNVERIFIED',candles=[],developing=None,completed_minutes=0,requested_minutes=0)
        if not identity_ok:
            h=dict(h,status='UNVERIFIED',candles=[],developing=None)
        # The inherited market buffer is never overwritten by history/cache. Merge for
        # display, so a source reset removes old historical generations immediately.
        displayed={b['time']:b for b in state['candles']}
        for b in h['candles']:
            displayed[b['time']]=b
        forming=h.get('developing')
        if forming and not state['run']['stopped'] and forming['time']<=now<forming['time']+60:
            old=displayed.get(forming['time'])
            if not old or old['quality'] not in ('engine-completed','engine-seed'):
                displayed[forming['time']]=forming
        state['candles']=sorted(displayed.values(),key=lambda b:b['time'])[-1440:]
        h={k:v for k,v in h.items() if k not in ('candles','developing')}
        current=next((b for b in reversed(state['candles']) if b['time']<=now<b['time']+60),None)
        h['developing_status']='EXPORTED' if forming and forming['time']<=now<forming['time']+60 else 'SAMPLED_ONLY' if current and current['quality']=='sampled' else 'UNAVAILABLE'
        h['developing_note']='R7 has no explicit current_candle export in the audited run. Sampled partial OHLC is not a full-feed forming candle.'
        h['snapshot_capture_age_seconds']=now-h['latest_capture'] if h.get('latest_capture') is not None else None
        state['history']=h
        state['diagnostics']['sampled_candles']=sum(b['quality']=='sampled' for b in state['candles'])
        state['diagnostics']['complete_candles']=sum(b['quality'] in ('engine-completed','engine-seed') for b in state['candles'])
        state['diagnostics']['candle_note']='Solid historical bars: verified engine OHLC. Dashed bars: sampled approximation. Cyan-outline bars: explicit developing export when available. First seen means earliest scanned observation, not measured browser delivery.'
        state['diagnostics']['readers']['snapshots'].update(reader='INDEPENDENT_TIME_COVERAGE_WORKER',tail_limited=False,
            lag_bytes=h.get('live_tail_lag_bytes'),history_status=h['status'])
        m=state['market'];q=state['quote'];r=state['run']
        engine_status='FAILED' if r['status']=='FAILED' else 'STOPPED' if r['stopped'] else 'CURRENT' if r['fresh'] else 'STALE'
        health=dict(engine=component(engine_status,updated=r['updated'],now=now,reason=runtime.get('halt_reason')),
            price=component('LAST_RECORDED' if r['stopped'] else 'CURRENT' if m.get('fresh') else 'STALE',updated=m.get('time'),now=now,reason='Chart-price source age; independent of contract timer'),
            quotes=component('LAST_RECORDED' if r['stopped'] else 'CURRENT' if q.get('fresh') else 'UNAVAILABLE',updated=q.get('time'),now=now,reason=q.get('reason')),
            candles=component('INPUT_STALE' if h['status']=='READY' and not r['stopped'] and (h.get('latest_capture') is None or now-h['latest_capture']>10) else h['status'],updated=h.get('latest_capture'),now=now,
                completed=h['completed_minutes'],expected=h['requested_minutes'],reason=h.get('error'),developing=h['developing_status']))
        health.update(self.sidecar_health.poll(now,r['stopped']))
        state['health']=health
        # Do not display unmatched sidecar detail cards beside stricter health status.
        for key,name in [('navigator','navigator'),('observer42','observer')]:
            if health[name]['status'] in ('UNVERIFIED','MISSING','UNAVAILABLE','READ_ERROR'):
                state['interpretation'][key]={}
        try:
            stats=json_file(self.run/'hf21_decision_snapshots.jsonl.stats.json',100_000)
            state['diagnostics']['snapshot_writer_stats']=dict(status='REPORTED' if stats else 'NOT_RECORDED',
                counters={k:stats.get(k) for k in ('written','enqueued','dropped','errors','shutdown_drained','worker_stopped')},
                source='Co-located stats file; no independent run identity or OHLC completeness claim')
        except (OSError,ValueError):
            state['diagnostics']['snapshot_writer_stats']={'status':'READ_ERROR'}
        if self.lab:
            try:
                state['diagnostics']['storage'].update(code_root=str(self.lab),code_free_gib=round(shutil.disk_usage(self.lab).free/1073741824,2))
            except OSError:
                state['diagnostics']['storage'].update(code_root=str(self.lab),code_free_gib=None)
        state['version']=VERSION
        if self.receipt is None and self.receipt_root and identity_ok:
            if self.run.resolve()==self.receipt_root.resolve() or self.run.resolve() in self.receipt_root.resolve().parents:
                raise ValueError('Receipt directory must be outside the engine run')
            name=hashlib.sha256((str(self.run)+runtime['session_id']).encode()).hexdigest()[:16]
            self.receipt=HealthReceipt(self.receipt_root/f'{name}_{os.getpid()}_{time.time_ns()}.json',
                dict(run_directory=str(self.run),session_id=runtime['session_id'],version=VERSION))
        if self.receipt:
            self.receipt.sample(state)
            state['diagnostics']['health_receipt']=dict(path=str(self.receipt.path),error=self.receipt.error,
                scope='This viewer server only; not retrospective browser uptime')
        return state

    def close(self):
        if self.history:self.history.close()
        if self.receipt:self.receipt.close()
