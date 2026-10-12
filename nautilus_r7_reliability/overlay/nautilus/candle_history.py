"""Session-bound chart history. Reads engine JSONL; writes only optional UI cache.

Backfills by requested time coverage on a separate worker, not a byte-sized view.
The original decision stream is never modified, copied, truncated or rotated.
Only validated completed OHLC and explicit developing OHLC reach the chart.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
import threading
import time
from collections import Counter
from pathlib import Path

CHUNK = 1024 * 1024
MAX_RECORD = 16 * CHUNK
MAX_BARS = 1440
CACHE_LIMIT = 2 * CHUNK


def finite(v):
    if isinstance(v, bool):
        return None
    try:
        v = float(v)
        return v if math.isfinite(v) else None
    except (ValueError, TypeError, OverflowError):
        return None


def fingerprint(path):
    s = path.stat()
    return {"device": s.st_dev, "inode": s.st_ino, "size": s.st_size, "mtime_ns": s.st_mtime_ns}


def anchor(path, offset):
    with path.open('rb') as f:
        prefix = f.read(min(4096, offset))
        f.seek(max(0, offset - 4096))
        end = f.read(min(4096, offset))
    return hashlib.sha256(prefix + end).hexdigest()


def bar(row, captured, completed=True):
    if not isinstance(row, dict):
        return None
    t = finite(row.get('minute', row.get('time')))
    values = [finite(row.get(k)) for k in ('open', 'high', 'low', 'close')]
    if t is None or t % 60 or t < 946684800 or any(v is None or v <= 0 for v in values):
        return None
    o, h, lo, c = values
    if lo > min(o, c) or h < max(o, c) or lo > h:
        return None
    if completed and t + 60 > captured:
        return None
    if not completed and not t <= captured < t + 60:
        return None
    source = str(row.get('source') or '')
    # Explicit observed-tick OHLC is useful but is not promoted to complete feed OHLC.
    quality = 'engine-completed' if completed else ('sampled' if 'OBSERVED' in source.upper() else 'engine-developing')
    return dict(time=int(t), open=o, high=h, low=lo, close=c, quality=quality,
                known_at=captured, source=source or 'HF21 frame.box_candles' if completed else source or 'HF21 frame.current_candle')


class ReverseLines:
    """Bounded reverse reader, returning complete lines with byte positions.

    Skip only the incomplete last record at initial high-water, preserve record
    boundaries across blocks, and yield progress even when a large line spans blocks.
    """
    def __init__(self, path, end, start=None):
        self.path = path
        self.cursor = end if start is None else start
        self.buffer = b''
        self.buffer_start = self.cursor
        self.initial = True
        self.complete_boundary = start is not None  # resumed at a known line start
        self.finished = False
        self.bytes_read = 0
        self.oversized = 0
        self.discard = False

    def step(self):
        if self.finished:
            return None
        # The buffer's right edge is a newline or known EOF boundary once trimmed.
        pos = self.buffer.rfind(b'\n')
        if self.initial:
            if self.complete_boundary:
                self.initial = False
            elif pos >= 0:
                self.buffer = self.buffer[:pos]  # trailing partial (possibly empty)
                self.initial = False
            elif self.cursor == 0:
                self.finished = True
                return None
        if not self.initial:
            pos = self.buffer.rfind(b'\n')
            if pos >= 0:
                raw = self.buffer[pos+1:]
                start = self.buffer_start + pos + 1
                self.buffer = self.buffer[:pos]
                if self.discard:
                    self.discard = False
                    return ()
                if len(raw) > MAX_RECORD:
                    self.oversized += 1
                    return ()
                return start, raw
            if self.cursor == 0:
                self.finished = True
                if self.buffer and not self.discard:
                    return 0, self.buffer
                return None
        if len(self.buffer) > MAX_RECORD:
            self.buffer = b''
            self.discard = True
            self.oversized += 1
        amount = min(CHUNK, self.cursor)
        if not amount:
            self.finished = True
            return None
        at = self.cursor - amount
        with self.path.open('rb') as f:
            f.seek(at)
            data = f.read(amount)
        if len(data) != amount:
            raise OSError('Snapshot shrank during backward history read')
        self.bytes_read += amount
        self.cursor = at
        self.buffer_start = at
        self.buffer = data + self.buffer
        return ()  # worker can service the live tail between disk chunks


class CandleHistory:
    def __init__(self, run, manifest, runtime, *, cache_root=None, buffer_minutes=15):
        self.run = Path(run)
        self.path = self.run/'hf21_decision_snapshots.jsonl'
        self.identity = {k: runtime.get(k) for k in ('run_id', 'session_id', 'pid')}
        self.identity.update(engine_version=manifest.get('version'), run_directory=manifest.get('run_directory'))
        self.key = hashlib.sha256(json.dumps(self.identity, sort_keys=True).encode()).hexdigest()[:24]
        self.cache_path = Path(cache_root)/(self.key+'_candles.json') if cache_root else None
        if self.cache_path and (self.run.resolve() == self.cache_path.parent.resolve() or self.run.resolve() in self.cache_path.resolve().parents):
            raise ValueError('UI candle cache must be outside the engine run')
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread = None
        self.bars = {}
        self.developing = None
        self.stats = Counter({k: 0 for k in ('backfill_bytes_read','cache_rejected','completed_revisions_observed','explicit_developing_observations','forward_bytes_read','identity_rejected','invalid_bars','malformed_records','oversized_records','oversized_reverse_records','read_errors','records_examined','schema_rejected','source_resets','time_rejected')})
        self.error = None
        self.cache_error = None
        self.cache_loaded = False
        self.last_write = 0
        self.buffer_seconds = max(0, min(30, buffer_minutes))*60
        self.requested_start = None
        self.requested_end = None
        self.wanted_start = None
        self.backfill_cursor = None
        self.rev = None
        self.forward_offset = None
        self.forward_partial = b''
        self.forward_discard = False
        self.source_id = None
        self.source_size = 0
        self.latest_capture = None
        self.last_read_wall = None
        self.newest_seen_capture = None
        self.last_reverse_capture = None
        self.started = None
        self.completed = False
        self.cache_dirty = False
        self.closed = False
        self.generation = 0
        self.started_utc = manifest.get('started_utc')
        self.ended_utc = manifest.get('ended_utc')
        from adapter import epoch
        self.run_start = epoch(self.started_utc)
        self.run_end = epoch(self.ended_utc)
        reference = self.run_end or finite(runtime.get('updated_wall')) or time.time()
        self.request(reference - 45*60, reference)

    def request(self, start, end):
        start, end = finite(start), finite(end)
        if start is None or end is None or not 60 <= end - start <= (MAX_BARS-30)*60:
            return False
        # Loaded history is bounded; do not let a malformed browser request sweep arbitrary epochs.
        high = self.run_end or time.time()
        low = max((self.run_start or high)-4*3600, high-MAX_BARS*60)
        start, end = max(start, low), min(end, high)
        if start >= end:
            return False
        with self.lock:
            self.requested_start, self.requested_end = start, end
            goal = max(low, start-self.buffer_seconds)
            if self.wanted_start is None or goal < self.wanted_start:
                self.wanted_start = goal
            self.completed = False
        return True

    def expected(self, start, end):
        # Live/late-start partial startup bar isn't falsely declared a full run minute.
        a = max(math.floor(start/60)*60, math.ceil((self.run_start or start)/60)*60)
        return set(range(int(math.ceil(a/60)*60), int(end//60*60), 60))

    def ingest(self, raw, direction):
        if not raw.strip():
            return
        self.stats['records_examined'] += 1
        try:
            obj = json.loads(raw.decode('utf-8-sig'), parse_constant=lambda _: None)
            if not isinstance(obj, dict) or obj.get('schema') != 'HF21_SNAPSHOT_V1':
                self.stats['schema_rejected'] += 1
                return
            ident = obj.get('identity') or {}
            if not self.identity['run_id'] or not self.identity['session_id'] or any(ident.get(k) != self.identity[k] for k in ('run_id', 'session_id')):
                self.stats['identity_rejected'] += 1
                return
            captured = finite(obj.get('captured_at_epoch'))
            from adapter import epoch
            stated = epoch(obj.get('captured_at_utc'))
            if captured is None:
                captured = stated
            if captured is None or (stated is not None and abs(stated-captured) > .01):
                self.stats['time_rejected'] += 1
                return
            if (self.run_start and captured < self.run_start) or captured > (self.run_end or time.time()) + .5:
                self.stats['time_rejected'] += 1
                return
            if direction == 'backfill':
                self.last_reverse_capture = captured
            frame = obj.get('frame')
            if not isinstance(frame, dict):
                return  # known valid non-candle events are not parser failures
            with self.lock:
                self.latest_capture = max(self.latest_capture or captured, captured)
                for row in frame.get('box_candles') or []:
                    b = bar(row, captured)
                    if b is None:
                        self.stats['invalid_bars'] += 1
                        continue
                    if b['time'] < (self.run_start or captured)-4*3600 or b['time'] < (self.run_end or captured)-MAX_BARS*60:
                        continue
                    prior = self.bars.get(b['time'])
                    if prior:
                        first = min(prior.get('first_observed_in_scan', captured), captured)
                        if captured < prior['known_at']:
                            prior['first_observed_in_scan'] = first
                            continue
                        b['first_observed_in_scan'] = first
                        if any(b[k] != prior[k] for k in ('open','high','low','close')):
                            self.stats['completed_revisions_observed'] += 1
                    else:
                        b['first_observed_in_scan'] = captured
                    self.bars[b['time']] = b
                    self.cache_dirty = True
                row = frame.get('current_candle')
                if row is not None:
                    b = bar(row, captured, completed=False)
                    if b and (not self.developing or captured >= self.developing['known_at']):
                        self.developing = b
                        self.stats['explicit_developing_observations'] += 1
                if len(self.bars) > MAX_BARS:
                    keep = sorted(self.bars)[-MAX_BARS:]
                    self.bars = {k:self.bars[k] for k in keep}
            self.last_read_wall = time.time()
        except (ValueError, TypeError, UnicodeError, AttributeError, RecursionError):
            self.stats['malformed_records'] += 1

    def _open(self):
        st = fingerprint(self.path)
        ident = (st['device'], st['inode'])
        if self.source_id is not None and (ident != self.source_id or st['size'] < (self.forward_offset or 0)):
            with self.lock:
                self.bars.clear(); self.developing=None; self.latest_capture=None
                self.stats['source_resets'] += 1; self.generation += 1
            self.forward_offset=None; self.rev=None; self.forward_partial=b''
            self.backfill_cursor=None; self.cache_loaded=False; self.last_reverse_capture=None
        self.source_id = ident
        self.source_size = st['size']
        if self.forward_offset is None:
            self.forward_offset = st['size']
            self.forward_discard = False
            if st['size']:
                # The ordinary newline-complete case needs one byte, not a 16 MB
                # read. An unfinished current record is resumed from its boundary.
                with self.path.open('rb') as f:
                    f.seek(st['size']-1)
                    complete=f.read(1)==b'\n'
                    if not complete:
                        left=max(0,st['size']-MAX_RECORD)
                        f.seek(left)
                        tail=f.read(st['size']-left)
                        at=tail.rfind(b'\n')
                        if at>=0:
                            self.forward_offset=left+at+1
                        elif left==0:
                            self.forward_offset=0
                        else:
                            self.forward_discard=True
            self.rev = ReverseLines(self.path, st['size'])
            self.backfill_cursor=st['size']
            self.load_cache(st)
        return st

    def load_cache(self, st):
        if not self.cache_path or not self.cache_path.is_file():
            return
        try:
            if self.cache_path.stat().st_size > CACHE_LIMIT:
                raise ValueError('Candle cache exceeds limit')
            obj = json.loads(self.cache_path.read_text(encoding='utf-8'))
            old = obj.get('source') or {}
            endpoint = obj.get('forward_offset')
            if obj.get('format') != 1 or obj.get('identity') != self.identity:
                raise ValueError('Cache session identity mismatch')
            if (old.get('device'),old.get('inode')) != self.source_id or not isinstance(endpoint,int) or not 0 <= endpoint <= st['size']:
                raise ValueError('Cache source fingerprint mismatch')
            if old.get('size') == st['size'] and old.get('mtime_ns') != st['mtime_ns']:
                raise ValueError('Same-size source changed since cached read')
            if anchor(self.path,endpoint) != obj.get('anchor'):
                raise ValueError('Cache/source boundary mismatch')
            loaded = {}
            for b in obj.get('candles') or []:
                checked = bar(b,finite(b.get('known_at')) or 0)
                if not checked:
                    raise ValueError('Invalid cached candle')
                checked['first_observed_in_scan'] = finite(b.get('first_observed_in_scan')) or checked['known_at']
                loaded[checked['time']]=checked
            if len(loaded)>MAX_BARS:
                raise ValueError('Too many cached candles')
            cursor=obj.get('backfill_cursor')
            if not isinstance(cursor,int) or not 0 <= cursor <= endpoint:
                raise ValueError('Invalid cache cursor')
            with self.lock:
                self.bars=loaded
            self.forward_offset=endpoint; self.forward_discard=False
            self.backfill_cursor=cursor
            self.rev=ReverseLines(self.path,cursor,start=cursor)
            self.cache_loaded=True
            self.latest_capture=finite(obj.get('latest_capture'))
            self.last_reverse_capture=finite(obj.get('last_reverse_capture'))
        except (OSError,ValueError,TypeError,KeyError):
            self.stats['cache_rejected']+=1  # rebuild from source, never keep another run's chart

    def save_cache(self, force=False):
        if not self.cache_path or self.forward_offset is None or not self.cache_dirty:
            return
        if not force and time.monotonic()-self.last_write<15:
            return
        temp=None
        try:
            st=fingerprint(self.path)
            endpoint=self.forward_offset-len(self.forward_partial)
            if self.forward_discard:
                return
            if (st['device'],st['inode'])!=self.source_id or st['size']<endpoint:
                return
            with self.lock:
                obj=dict(format=1,identity=self.identity,source=st,forward_offset=endpoint,
                         backfill_cursor=min(self.backfill_cursor or 0,endpoint),anchor=anchor(self.path,endpoint),
                         candles=sorted(self.bars.values(),key=lambda b:b['time']),latest_capture=self.latest_capture,
                         last_reverse_capture=self.last_reverse_capture)
            raw=json.dumps(obj,separators=(',',':'),allow_nan=False).encode()
            if len(raw)>CACHE_LIMIT:
                raise ValueError('Cache exceeds bounded limit')
            self.cache_path.parent.mkdir(parents=True,exist_ok=True)
            if self.cache_path.is_symlink() or self.cache_path.parent.is_symlink():
                raise ValueError('Cache destination may not be a symlink')
            temp=self.cache_path.with_name(self.cache_path.name+f'.{os.getpid()}.tmp')
            with temp.open('xb') as f: f.write(raw)
            os.replace(temp,self.cache_path)
            self.last_write=time.monotonic();self.cache_dirty=False;self.cache_error=None
        except (OSError,ValueError) as exc:
            self.cache_error=type(exc).__name__+': '+str(exc)[:160]
        finally:
            if temp and temp.is_file():
                try:temp.unlink()
                except OSError:pass

    def forward(self):
        if self.source_size <= self.forward_offset:
            return
        with self.path.open('rb') as f:
            f.seek(self.forward_offset)
            raw=f.read(CHUNK)
        self.forward_offset+=len(raw)
        self.stats['forward_bytes_read']+=len(raw)
        data=self.forward_partial+raw
        lines=data.split(b'\n');self.forward_partial=lines.pop()
        for line in lines:
            if self.forward_discard:
                self.forward_discard=False
                continue
            if len(line)>MAX_RECORD:
                self.stats['oversized_records']+=1
            else:
                self.ingest(line,'forward')
        if len(self.forward_partial)>MAX_RECORD:
            self.forward_partial=b'';self.forward_discard=True
            self.stats['oversized_records']+=1

    def step(self, budget=.08):
        try:
            self._open()
            self.forward()
            with self.lock:
                desired=self.expected(self.wanted_start,self.requested_end)
                missing=desired-set(self.bars)
            backfill_needed=bool(missing) and not (self.rev and self.rev.finished)
            # Once we've scanned earlier captures than the requested start, older frames
            # cannot supply still-missing future completed candles; report genuine gaps.
            if self.last_reverse_capture is not None and self.last_reverse_capture < self.wanted_start:
                backfill_needed=False
            began=time.monotonic()
            while backfill_needed and not self.stop_event.is_set() and time.monotonic()-began<budget:
                result=self.rev.step()
                if result is None:
                    self.backfill_cursor=0
                    break
                if result:
                    offset,raw=result
                    self.ingest(raw,'backfill')
                    self.backfill_cursor=offset
                    if self.last_reverse_capture is not None and self.last_reverse_capture<self.wanted_start:
                        break
                    with self.lock:
                        if desired.issubset(self.bars):
                            break
            self.stats['backfill_bytes_read']=self.rev.bytes_read if self.rev else 0
            self.stats['oversized_reverse_records']=self.rev.oversized if self.rev else 0
            self.error=None
            self.save_cache()
        except FileNotFoundError:
            self.error='SNAPSHOT_SOURCE_MISSING'
        except (OSError,ValueError,TypeError,RuntimeError) as exc:
            self.error=type(exc).__name__+': '+str(exc)[:180]
            self.stats['read_errors']+=1

    def snapshot(self):
        with self.lock:
            expected=self.expected(self.requested_start,self.requested_end)
            missing=expected-set(self.bars)
            exhausted=bool(self.rev and (self.rev.finished or (self.last_reverse_capture is not None and self.last_reverse_capture<self.wanted_start)))
            status='MISSING' if self.error=='SNAPSHOT_SOURCE_MISSING' else 'READ_ERROR' if self.error else 'READY' if not missing else 'GAPS' if exhausted else 'BACKFILLING'
            return dict(status=status,requested_start=self.requested_start,requested_end=self.requested_end,
                requested_minutes=len(expected),completed_minutes=len(expected)-len(missing),missing_minutes=sorted(missing),
                buffered_from=self.wanted_start,candles=sorted(self.bars.values(),key=lambda b:b['time']),
                developing=dict(self.developing) if self.developing else None,latest_capture=self.latest_capture,
                last_successful_read=self.last_read_wall,source_bytes=self.source_size,
                live_tail_lag_bytes=max(0,self.source_size-(self.forward_offset or 0)),
                stats=dict(self.stats),error=self.error,cache_error=self.cache_error,
                cache_loaded=self.cache_loaded,cache_path=str(self.cache_path) if self.cache_path else None,
                cache_max_bytes=CACHE_LIMIT,worker_alive=bool(self.thread and self.thread.is_alive()),
                generation=self.generation,proof='Data availability only; not proof of browser delivery or exchange OHLC parity',
                first_seen_scope='Earliest observation in scanned records, not a full-stream first-availability audit')

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.started=time.time()
        def work():
            while not self.stop_event.is_set():
                self.step()
                self.stop_event.wait(.08 if not self.error else 1)
            self.save_cache(force=True)
        self.thread=threading.Thread(target=work,name='NautilusCandleHistory',daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        elif self.forward_offset is not None:
            self.save_cache(force=True)
        self.closed=True
