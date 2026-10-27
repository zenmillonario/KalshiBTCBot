"""Isolated PUBLIC market-data I/O for OBS3. Never called by --check/install.

Fixed Coinbase public URLs, GET seed + one market_trades subscription. No account
API, auth, environment secrets, broker orders, or engine imports. All received
trade envelopes are recorded before parsing. This thread cannot control HF2.
"""
from __future__ import annotations
import asyncio
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import gzip
import hashlib
import json
from pathlib import Path
import queue
import shutil
import ssl
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

from .btc_observation import TradeStream, FeedFault, validate_candles, SEED_BARS
from .common import utc

WS_URL='wss://advanced-trade-ws.coinbase.com'
SEED_URL='https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60'
MAX_TAPE_BYTES=4_000_000_000
MAX_QUEUE=10000


def public_fault_details(exc, wall):
    """Bounded local reason codes; never remote URLs, bodies or exception text."""
    cause=exc.reason if isinstance(exc,URLError) and isinstance(exc.reason,BaseException) else exc
    reason=str(exc) if isinstance(exc,FeedFault) else type(exc).__name__
    details={'reason':reason,'exception_type':type(exc).__name__,
             'occurred_wall':wall,'occurred_utc':utc(wall)}
    if isinstance(exc,HTTPError):
        details['http_status']=exc.code
        details['reason']='PUBLIC_HTTP_STATUS_'+str(exc.code)
    elif type(exc).__module__.startswith('websockets'):
        status=getattr(exc,'status_code',None)
        if type(status) is not int:status=getattr(getattr(exc,'response',None),'status_code',None)
        if type(status) is int and 100<=status<=599:
            details['http_status']=status
            details['reason']='PUBLIC_WEBSOCKET_HTTP_STATUS_'+str(status)
    if cause is not exc:details['underlying_exception_type']=type(cause).__name__
    if isinstance(cause,ssl.SSLCertVerificationError):
        details['reason']='PUBLIC_SSL_CERTIFICATE_VERIFY_FAILED'
        code=getattr(cause,'verify_code',None)
        if isinstance(code,int):details['ssl_verify_code']=code
    if isinstance(exc,FeedFault) and isinstance(getattr(exc,'seed_diagnostic',None),dict):
        # This summary is constructed locally from validated bucket counts and
        # allowlisted timing/cache facts, never remote bodies or exception text.
        details['seed_diagnostic']=dict(exc.seed_diagnostic)
    return details

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise FeedFault('PUBLIC_HTTP_REDIRECT_REFUSED')


def _cache_summary(headers):
    """Diagnostic cache facts only; these never establish candle freshness."""
    summary={}
    age=str(headers.get('Age','')).strip()
    if age.isdecimal() and len(age)<=8:summary['age_seconds']=int(age)
    status=str(headers.get('CF-Cache-Status','')).strip().upper()
    if status in ('HIT','MISS','DYNAMIC','EXPIRED','BYPASS','REVALIDATED','UPDATING','STALE'):
        summary['cf_cache_status']=status
    try:
        date=parsedate_to_datetime(str(headers.get('Date',''))[:128])
        if date.tzinfo is not None:summary['response_date_utc']=date.astimezone(timezone.utc).isoformat()
    except (TypeError,ValueError,OverflowError):pass
    for part in str(headers.get('Cache-Control',''))[:512].split(','):
        name,_,value=part.strip().partition('=');name=name.lower()
        if name in ('public','private','no-cache','no-store','must-revalidate'):
            summary[name.replace('-','_')]=True
        elif name=='max-age' and value.isdecimal() and len(value)<=8:
            summary['max_age_seconds']=int(value)
    return summary


def get_seed():
    begun=time.time()
    current=int(begun//60)*60
    start=datetime.fromtimestamp(current-SEED_BARS*60,timezone.utc).isoformat(timespec='microseconds')
    end=datetime.fromtimestamp(begun,timezone.utc).isoformat(timespec='microseconds')
    # An explicit current window avoids reusing the default endpoint's cached
    # history. It spans at most 241 minute buckets. Validation still owns truth.
    req=Request(SEED_URL+'&'+urlencode({'start':start,'end':end}),
        headers={'User-Agent':'Tachyos-ToolRack-MarketData/1.0','Accept':'application/json',
                 'Cache-Control':'no-cache, no-store','Pragma':'no-cache'},method='GET')
    with build_opener(NoRedirect).open(req,timeout=10) as response:
        raw=response.read(1_000_001)
        if len(raw)>1_000_000:raise FeedFault('OVERSIZED_CANDLE_RESPONSE')
        if response.status!=200:raise FeedFault('PUBLIC_HTTP_STATUS_NOT_200')
        cache=_cache_summary(response.headers)
    received=time.time()
    rows=json.loads(raw)
    transport=dict(requested_utc=utc(begun),received_utc=utc(received),
        request_window_start_utc=start,request_window_end_utc=end,
        response_sha256=hashlib.sha256(raw).hexdigest(),response_cache=cache,
        returned_rows=len(rows) if isinstance(rows,list) else None,
        request_crossed_minute_boundary=int(received//60)*60!=current)
    try:
        # A candle open at request time must not become a completed seed merely
        # because the response crossed a minute boundary. Never promote it.
        if transport['request_crossed_minute_boundary']:
            failure=FeedFault('SEED_REQUEST_CROSSED_MINUTE_BOUNDARY')
            failure.seed_diagnostic={
                'expected_latest_completed_bucket':int(received//60)*60-60,
                'latest_completed_bucket_at_request':current-60,
            }
            raise failure
        seed,meta=validate_candles(rows,received)
    except FeedFault as exc:
        exc.seed_diagnostic={**transport,**getattr(exc,'seed_diagnostic',{})}
        raise
    meta.update(transport)
    return seed,meta,rows


class PublicFeed:
    """Bounded daemon companion worker; main process observes explicit errors.

    Connect/reconnect replaces only THIS observer's market-data epoch. It never
    restarts the trading process. Missing paths are censored, not replayed as live.
    """
    def __init__(self,out,seed_fetch=get_seed,connect=None):
        self.out=Path(out);self.seed_fetch=seed_fetch;self.connect=connect
        self.queue=queue.Queue(MAX_QUEUE);self.stop_event=threading.Event()
        self.thread=None;self.error=None;self.state='NOT_STARTED';self.epoch=0
        self.last_receive=None;self.frames=0;self.total_bytes=0
        self.samples=0;self._tape=None;self._last_flush=0
        self.last_recoverable_fault=None

    def start(self):
        if self.thread is not None:raise FeedFault('PUBLIC_WORKER_ALREADY_STARTED')
        self.thread=threading.Thread(target=self._main,name='ToolRackPublicBTC',daemon=True)
        self.thread.start()

    def _put(self,kind,t,row,observed):
        try:self.queue.put_nowait({'kind':kind,'timestamp':t,'row':row,'observed_at':observed})
        except queue.Full:raise FeedFault('PUBLIC_OBSERVER_QUEUE_OVERFLOW') from None

    def _record(self,obj):
        b=(json.dumps(obj,ensure_ascii=True,allow_nan=False,separators=(',',':'))+'\n').encode()
        self.total_bytes+=len(b)
        if self.total_bytes>MAX_TAPE_BYTES:raise FeedFault('PUBLIC_TAPE_BYTE_LIMIT')
        try:self._tape.write(b)
        except OSError:raise FeedFault('PUBLIC_TAPE_WRITE_FAILED') from None
        now=time.monotonic()
        if now-self._last_flush>=1:
            self._tape.flush();self._last_flush=now
            if shutil.disk_usage(self.out).free<1024**3:raise FeedFault('OBSERVER_DISK_RESERVE_REACHED')

    def _main(self):
        try:
            with gzip.open(self.out/'btc_public_source.jsonl.gz','xb',compresslevel=3) as tape:
                self._tape=tape;asyncio.run(self._run())
        except BaseException as exc:
            self.error=str(exc) if isinstance(exc,FeedFault) else type(exc).__name__
            self.state='FAILED'
        finally:
            self._tape=None
            if self.state!='FAILED':self.state='STOPPED'

    async def _run(self):
        if self.connect is None:
            import websockets
            connect=websockets.connect
        else:connect=self.connect
        feed_failures=0;seed_waits=0;last_seed_attempt=float('-inf')
        while not self.stop_event.is_set():
            try:
                # Public history is for seed initialization only, not frequent polling.
                remaining=60-(time.monotonic()-last_seed_attempt)
                while remaining>0 and not self.stop_event.is_set():
                    await asyncio.sleep(min(.25,remaining));remaining=60-(time.monotonic()-last_seed_attempt)
                if self.stop_event.is_set():break
                self.state='SEEDING';last_seed_attempt=time.monotonic()
                seed,meta,rows=await asyncio.to_thread(self.seed_fetch)
                seed_waits=0
                if self.stop_event.is_set():break
                self.epoch+=1;now=time.time()
                self._record({'kind':'PUBLIC_SEED','epoch':self.epoch,'received_wall':now,'metadata':meta,'candles':rows})
                stream=TradeStream(seed,meta,self.epoch)
                self._put('btc_status',now,{'state':'PUBLIC_SEED_READY','epoch':self.epoch,'seed':meta},now)
                self.state='CONNECTING'
                async with connect(WS_URL,ping_interval=20,ping_timeout=20,open_timeout=10,close_timeout=2,max_size=1_000_000,max_queue=64) as ws:
                    await ws.send(json.dumps({'type':'subscribe','product_ids':['BTC-USD'],'channel':'market_trades'}))
                    self.state='AWAIT_PUBLIC_SNAPSHOT';opened=time.monotonic();last_frame=opened
                    while not self.stop_event.is_set():
                        try:raw=await asyncio.wait_for(ws.recv(),timeout=1)
                        except asyncio.TimeoutError:
                            if time.monotonic()-last_frame>15:raise FeedFault('NO_PUBLIC_ENVELOPE_15S')
                            continue
                        received=time.time();mono=time.monotonic();last_frame=mono
                        if len(raw)>1_000_000:raise FeedFault('OVERSIZED_PUBLIC_FRAME')
                        message=json.loads(raw)
                        self._record({'kind':'PUBLIC_FRAME','epoch':self.epoch,'received_wall':received,'received_utc':utc(received),'received_monotonic':mono,'message':message})
                        self.last_receive=received;self.frames+=1
                        geometry_rows=stream.consume(message,received,mono)
                        for tr in stream.last_accepted:
                            self._put('btc_trade',tr['timestamp_epoch'],tr,received)
                        for row in geometry_rows:
                            t=stream.last_trade_t
                            self._put('btc_geometry',t,row,received);self.samples+=1
                            self.state='PUBLIC_GEOMETRY_READY'
                        if mono-opened>30:feed_failures=0
                if self.stop_event.is_set():break
                raise FeedFault('PUBLIC_CONNECTION_ENDED')
            except asyncio.CancelledError:raise
            except Exception as exc:
                if self.stop_event.is_set():break
                if isinstance(exc,OSError) and getattr(exc,'errno',None) in (28,13):raise
                details=public_fault_details(exc,time.time())
                reason=details['reason']
                if reason in ('PUBLIC_OBSERVER_QUEUE_OVERFLOW','PUBLIC_TAPE_BYTE_LIMIT','OBSERVER_DISK_RESERVE_REACHED','PUBLIC_TAPE_WRITE_FAILED'):raise
                now=time.time();self.state='PUBLIC_DATA_GAP'
                self.last_recoverable_fault=details
                row={'state':self.state,**details,'epoch':self.epoch,'engine_unchanged':True,'gap_not_filled':True}
                self._record({'kind':'PUBLIC_FAULT','received_wall':now,**row})
                self._put('btc_gap',now,row,now)
                seed_timing_fault=reason in (
                    'SEED_NEEDS_30_RECENT_CONTIGUOUS_MINUTES',
                    'SEED_REQUEST_CROSSED_MINUTE_BOUNDARY',
                    'GAP_BETWEEN_SEED_AND_LIVE')
                if seed_timing_fault:
                    seed_waits+=1
                    if seed_waits>=10:raise FeedFault('PUBLIC_SEED_RETRY_LIMIT_OBSERVER_ONLY')
                    # These faults mean the seed/live handoff crossed a minute or
                    # the latest completed bucket was temporarily unavailable.
                    # Re-seed immediately; never fabricate the missing minute and
                    # never make the dashboard fault an engine pause.
                    last_seed_attempt=float('-inf')
                else:
                    feed_failures+=1
                    if feed_failures>=10:raise FeedFault('PUBLIC_FEED_RETRY_LIMIT_OBSERVER_ONLY')
                await asyncio.sleep(.25)

    def status(self):
        return {'state':self.state,'connection_epoch':self.epoch,'last_receive_wall':self.last_receive,
                'raw_frames':self.frames,'geometry_samples':self.samples,'raw_uncompressed_bytes':self.total_bytes,
                'queue_length':self.queue.qsize(),'error_type_or_code':self.error,
                'last_recoverable_fault':dict(self.last_recoverable_fault) if self.last_recoverable_fault else None,
                'public_only':True,'engine_controls':False}

    def stop(self,timeout=15):
        self.stop_event.set()
        if self.thread:self.thread.join(timeout=timeout)
        if self.thread and self.thread.is_alive():raise FeedFault('PUBLIC_WORKER_SHUTDOWN_TIMEOUT')
        if self.error:raise FeedFault(self.error)
