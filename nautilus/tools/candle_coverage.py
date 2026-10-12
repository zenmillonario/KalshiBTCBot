"""Read-only HF21_SNAPSHOT_V1 candle-coverage audit. Standard library only.

Scans a fixed starting byte length, never imports the engine, modifies a source,
opens the network, or copies raw snapshots into its compact report. Unknown,
mixed-session, developing and sampled observations are not completed candles.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import heapq
import json
import math
import os
from pathlib import Path, PureWindowsPath
import secrets
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from zipfile import ZipFile, ZIP_DEFLATED

VERSION = '1.0.0-R7'
DEFAULT_RUN = r'E:\TACHYS_DATA\runs\666_lab_20261012_033042_556731_PID28648'
DEFAULT_OUT = r'E:\TACHYS_DATA\diagnostics'
MAX_LINE = 16_000_000
ADAPTER_TAIL = 8_000_000  # R7 Tail(... initial_bytes=8_000_000), not eight MiB
MAX_MINUTES = 10080  # explicitly bound coverage window to seven days
STOPPED = {'STOPPED', 'ENDED', 'COMPLETED', 'FAILED'}


def num(v):
    if isinstance(v, bool):
        return None
    try:
        n = float(v)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError, OverflowError):
        return None


def stamp(v):
    n = num(v)
    if n is None:
        try:
            d = datetime.fromisoformat(str(v).replace('Z', '+00:00'))
            n = d.timestamp() if d.tzinfo is not None else None
        except (ValueError, TypeError, OverflowError):
            return None
    if n is not None and n > 100_000_000_000:
        n /= 1000
    return n if n is not None and 946684800 <= n < 4102444800 else None


def utc(n):
    return datetime.fromtimestamp(n, timezone.utc).isoformat() if n is not None else None


def fingerprint(p):
    s = p.stat()
    return dict(size=s.st_size, mtime_ns=s.st_mtime_ns, device=s.st_dev, inode=s.st_ino)


def small_json(p, limit=4_000_000, required=False):
    if not p.is_file():
        if required:
            raise ValueError('Required source is missing: ' + p.name)
        return {}, {'status': 'MISSING'}
    before = fingerprint(p)
    with p.open('rb') as f:
        raw = f.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(p.name + ': exceeds bounded JSON limit')
    obj = json.loads(raw.decode('utf-8-sig'))
    if not isinstance(obj, dict):
        raise ValueError(p.name + ': expected JSON object')
    after = fingerprint(p)
    return obj, dict(status='READ', before=before, after=after,
                     stable=before == after, sha256=hashlib.sha256(raw).hexdigest())


def bounded_count(counter, name):
    key = str(name)[:100] if name not in (None, '') else '(missing)'
    if key not in counter and len(counter) >= 64:
        key = '(other values beyond 64)'
    counter[key] += 1


class Timeline:
    def __init__(self):
        self.count = 0
        self.first = self.last = self.previous = None
        self.backwards = self.same_time = self.over5 = self.over30 = 0
        self.largest = []

    def add(self, t):
        self.count += 1
        self.first = t if self.first is None else min(self.first, t)
        self.last = t if self.last is None else max(self.last, t)
        if self.previous is not None:
            delta = t - self.previous
            self.backwards += delta < 0
            self.same_time += delta == 0
            self.over5 += delta > 5
            self.over30 += delta > 30
            if delta > 0:
                item = (delta, self.previous, t)
                if len(self.largest) < 20:
                    heapq.heappush(self.largest, item)
                elif item > self.largest[0]:
                    heapq.heapreplace(self.largest, item)
        self.previous = t

    def report(self):
        return dict(records=self.count, first_utc=utc(self.first), last_utc=utc(self.last),
                    out_of_order=self.backwards, identical_capture_time=self.same_time,
                    consecutive_gaps_over_5s=self.over5, consecutive_gaps_over_30s=self.over30,
                    largest_gaps=[dict(seconds=round(d, 6), from_utc=utc(a), to_utc=utc(b))
                                  for d, a, b in sorted(self.largest, reverse=True)])


class SnapshotStream:
    """One complete pass; fixed high-water mark; bounded oversized-line draining."""
    def __init__(self, path, progress=None):
        self.path, self.progress = path, progress
        self.before = fingerprint(path)
        self.sha = hashlib.sha256()
        self.bytes_read = 0
        self.after = None

    def __iter__(self):
        with self.path.open('rb') as f:
            if fingerprint(self.path) != self.before:
                raise ValueError('Snapshot changed before the scan opened it')
            size = self.before['size']
            line_no = 0
            while self.bytes_read < size:
                start = self.bytes_read
                raw = f.readline(min(MAX_LINE + 1, size - self.bytes_read))
                if not raw:
                    break
                self.sha.update(raw)
                self.bytes_read += len(raw)
                oversized = len(raw) > MAX_LINE
                last = raw
                if oversized:
                    while not last.endswith(b'\n') and self.bytes_read < size:
                        last = f.readline(min(1_000_000, size - self.bytes_read))
                        if not last:
                            break
                        self.sha.update(last)
                        self.bytes_read += len(last)
                line_no += 1
                yield line_no, start, (b'' if oversized else raw), oversized, last.endswith(b'\n')
                if self.progress:
                    self.progress(self.bytes_read, size)
            self.after = fingerprint(self.path)

    def report(self):
        return dict(before=self.before, after=self.after,
                    bytes_scanned=self.bytes_read, sha256_scanned_bytes=self.sha.hexdigest(),
                    full_starting_file_read=self.bytes_read == self.before['size'],
                    stable=self.before == self.after)


def candle(row):
    """Require real OHLC fields; never convert one last-price into a candle."""
    if not isinstance(row, dict):
        return None, 'not_object'
    t = stamp(row.get('minute', row.get('time')))
    if t is None or t % 60 != 0:
        return None, 'invalid_minute'
    v = tuple(num(row.get(k)) for k in ('open', 'high', 'low', 'close'))
    if any(x is None or x <= 0 for x in v):
        return None, 'missing_or_invalid_ohlc'
    o, h, low, c = v
    if low > min(o, c) or h < max(o, c) or low > h:
        return None, 'inconsistent_ohlc'
    return (int(t), v), None


def ranges(minutes):
    blocks = []
    for t in sorted(minutes):
        if blocks and blocks[-1][1] == t:
            blocks[-1][1] += 60
            blocks[-1][2] += 1
        else:
            blocks.append([t, t + 60, 1])
    return [dict(from_utc=utc(a), until_utc_exclusive=utc(b), minutes=n) for a, b, n in blocks]


def analyze(run, *, allow_live=False, progress=None):
    run = Path(run).resolve()
    manifest, mf = small_json(run/'launcher_manifest.json', required=True)
    runtime, rf = small_json(run/'tachys_runtime_hf2.json', required=True)
    if manifest.get('mode') != 'PAPER_ONLY':
        raise ValueError('Refusing a run not explicitly marked PAPER_ONLY')
    expected_name = PureWindowsPath(str(manifest.get('run_directory', ''))).name
    if expected_name != run.name:
        raise ValueError('Manifest basename does not match the selected run directory')
    if num(manifest.get('pid')) is None or manifest.get('pid') != runtime.get('pid'):
        raise ValueError('Manifest/runtime PID disagreement')
    if manifest.get('status') not in STOPPED and not allow_live:
        raise ValueError('Run is not stopped. Stop/finish it first, or explicitly use --allow-live for a partial scan.')
    start = stamp(manifest.get('started_utc'))
    end = stamp(manifest.get('ended_utc'))
    if end is None and allow_live:
        end = stamp(runtime.get('updated_wall', runtime.get('updated_utc')))
    if start is None or end is None or not 0 < end - start <= MAX_MINUTES * 60:
        raise ValueError('Explicit run window is absent, invalid or longer than seven days')
    first_full = int(math.ceil(start / 60) * 60)
    last_boundary = int(end // 60 * 60)
    expected = set(range(first_full, last_boundary, 60))
    run_minutes = set(range(int(start//60*60), int(end//60*60)+1, 60))
    lower, upper = start - 86400, end + 60  # cap warmup/post-run minute inventory
    run_id, session_id = runtime.get('run_id'), runtime.get('session_id')
    identities_known = bool(run_id and session_id)
    stats, sf = small_json(run/'hf21_decision_snapshots.jsonl.stats.json')
    path = run/'hf21_decision_snapshots.jsonl'
    if not path.is_file():
        raise ValueError('Snapshot JSONL is missing here. Select the original E:-backed run, not the ZIP export.')
    stream = SnapshotStream(path, progress)
    counts = Counter({k: 0 for k in (
        'physical_lines', 'newline_terminated_lines', 'nonblank_complete_lines',
        'unterminated_final_line', 'oversized_lines', 'blank_lines', 'malformed_json',
        'nonobject_json', 'json_objects', 'unsupported_schema', 'capture_timestamp_conflicts',
        'missing_capture_time', 'foreign_identity_records', 'verified_identity_records',
        'unverified_identity_records', 'capture_outside_run_window', 'missing_frame_object',
        'frame_objects', 'frame_time_future', 'frame_age_over_5s', 'missing_frame_time',
        'missing_box_candles_list', 'records_with_box_candles_list',
        'records_with_nonempty_box_candles', 'completed_candle_occurrences_examined',
        'records_with_current_candle_field')})
    schemas, events = Counter(), Counter()
    fields, invalid = Counter(), Counter()
    timeline, matched_timeline = Timeline(), Timeline()
    minutes, examples = {}, []
    tail_start = max(0, stream.before['size'] - ADAPTER_TAIL)

    def warn(line, reason):
        if len(examples) < 20:
            examples.append(dict(line=line, reason=reason))  # never write raw payload

    def entry(t):
        return minutes.setdefault(t, dict(completed=0, verified=0, unverified=0,
            tail8mb_verified=0, in_time_verified=0, developing=0, revisions=0,
            first_seen=None, last_seen=None, first_verified=None,
            ohlc=None, last_value_capture=None, seed=False))

    for line, offset, raw, oversized, terminated in stream:
        counts['physical_lines'] += 1
        if not terminated:
            counts['unterminated_final_line'] += 1
            warn(line, 'Unterminated record at scan boundary; not counted as written complete JSONL')
            continue
        counts['newline_terminated_lines'] += 1
        if oversized:
            counts['oversized_lines'] += 1
            warn(line, 'Record exceeds 16,000,000 bytes; drained without parsing')
            continue
        if not raw.strip():
            counts['blank_lines'] += 1
            continue
        counts['nonblank_complete_lines'] += 1
        try:
            obj = json.loads(raw.decode('utf-8-sig'), parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
        except (ValueError, UnicodeError, RecursionError):
            counts['malformed_json'] += 1
            warn(line, 'Invalid UTF-8/JSON/nonfinite JSON; contents withheld')
            continue
        if not isinstance(obj, dict):
            counts['nonobject_json'] += 1
            continue
        counts['json_objects'] += 1
        bounded_count(schemas, obj.get('schema'))
        bounded_count(events, obj.get('event'))
        if obj.get('schema') != 'HF21_SNAPSHOT_V1':
            counts['unsupported_schema'] += 1
            continue
        a, b = stamp(obj.get('captured_at_epoch')), stamp(obj.get('captured_at_utc'))
        if a is not None and b is not None and abs(a-b) > .01:
            counts['capture_timestamp_conflicts'] += 1
            warn(line, 'Epoch/UTC capture fields disagree by more than 10 ms')
            continue
        captured = a if a is not None else b
        if captured is None:
            counts['missing_capture_time'] += 1
            continue
        timeline.add(captured)
        ident = obj.get('identity')
        ident = ident if isinstance(ident, dict) else {}
        mismatched = ((run_id and ident.get('run_id') not in (None, '', run_id)) or
                      (session_id and ident.get('session_id') not in (None, '', session_id)))
        if mismatched:
            counts['foreign_identity_records'] += 1
            warn(line, 'Snapshot has a foreign run_id/session_id')
            continue
        verified = identities_known and ident.get('run_id') == run_id and ident.get('session_id') == session_id
        counts['verified_identity_records' if verified else 'unverified_identity_records'] += 1
        if captured < start or captured > end:
            counts['capture_outside_run_window'] += 1
            continue
        if verified:
            matched_timeline.add(captured)
        frame = obj.get('frame')
        if not isinstance(frame, dict):
            counts['missing_frame_object'] += 1
            continue
        counts['frame_objects'] += 1
        for k in frame:
            bounded_count(fields, k)
        fnow = stamp(frame.get('now'))
        if fnow is not None:
            lag = captured - fnow
            counts['frame_time_future'] += lag < 0
            counts['frame_age_over_5s'] += lag > 5
        else:
            counts['missing_frame_time'] += 1
        rows = frame.get('box_candles')
        if not isinstance(rows, list):
            counts['missing_box_candles_list'] += 1
            rows = []
        else:
            counts['records_with_box_candles_list'] += 1
            counts['records_with_nonempty_box_candles'] += bool(rows)
        for row in rows:
            counts['completed_candle_occurrences_examined'] += 1
            parsed, error = candle(row)
            if error:
                invalid[error] += 1
                continue
            t, values = parsed
            if t + 60 > captured:
                invalid['not_completed_at_capture'] += 1
                continue
            if t < lower or t > upper:
                invalid['outside_bounded_window'] += 1
                continue
            rec = entry(t)
            rec['completed'] += 1
            rec['verified' if verified else 'unverified'] += 1
            rec['first_seen'] = min(rec['first_seen'], captured) if rec['first_seen'] is not None else captured
            rec['last_seen'] = max(rec['last_seen'], captured) if rec['last_seen'] is not None else captured
            if verified:
                rec['tail8mb_verified'] += offset > tail_start or tail_start == 0
                rec['in_time_verified'] += captured < end
                rec['first_verified'] = min(rec['first_verified'], captured) if rec['first_verified'] is not None else captured
                if rec['last_value_capture'] is None or captured >= rec['last_value_capture']:
                    rec['revisions'] += rec['ohlc'] is not None and rec['ohlc'] != values
                    rec['ohlc'], rec['last_value_capture'] = values, captured
        current = frame.get('current_candle')
        if current is not None:
            counts['records_with_current_candle_field'] += 1
            parsed, error = candle(current)
            if error:
                invalid['current_' + error] += 1
            else:
                t, _ = parsed
                if t <= captured < t + 60 and lower <= t <= upper:
                    if verified:
                        entry(t)['developing'] += 1
                else:
                    invalid['current_not_in_capture_minute'] += 1
    source = stream.report()
    _, stats_after = small_json(run/'hf21_decision_snapshots.jsonl.stats.json')
    source_stable = source['stable'] and source['full_starting_file_read']
    metadata_stable = (mf.get('stable') and rf.get('stable') and
        fingerprint(run/'launcher_manifest.json') == mf['after'] and
        fingerprint(run/'tachys_runtime_hf2.json') == rf['after'])
    stats_stable = sf.get('stable') and sf.get('sha256') == stats_after.get('sha256')
    seed, seed_f = small_json(run/'tachys_r15_history_seed.json')
    seed_rows = seed.get('candles', [])
    seed_ts = stamp((seed.get('status') or {}).get('observed_at'))
    seed_count = 0
    if isinstance(seed_rows, list):
        for row in seed_rows:
            parsed, error = candle(row)
            if not error:
                t, _ = parsed
                if lower <= t <= upper and seed_ts is not None and t+60 <= seed_ts:
                    entry(t)['seed'] = True
                    seed_count += 1
    # Price telemetry is assessed separately; it is not promoted to full OHLC.
    samples, sample_time, sample_meta = {}, Timeline(), {'status': 'MISSING'}
    sample_path = run/'tachys_price_arc_phase_v9_4j.csv'
    sample_bad = 0
    if sample_path.is_file():
        sample_stream = SnapshotStream(sample_path, progress)
        reader_header = None
        for line, offset, raw, oversized, terminated in sample_stream:
            if oversized or not terminated:
                sample_bad += 1
                continue
            try:
                row = next(csv.reader([raw.decode('utf-8-sig')], strict=True))
                if reader_header is None:
                    reader_header = row
                    if not {'timestamp','btc_price'}.issubset(reader_header):
                        raise ValueError('Missing market schema columns')
                    continue
                if len(row) != len(reader_header):
                    sample_bad += 1
                    continue
                row = dict(zip(reader_header, row))
                ts, value = stamp(row.get('timestamp')), num(row.get('btc_price'))
                if ts is None or value is None or value <= 0:
                    sample_bad += 1
                    continue
                if not start <= ts <= end:
                    continue
                sample_time.add(ts)
                minute = int(ts//60*60)
                s = samples.setdefault(minute, dict(count=0, high=value, low=value))
                s['count'] += 1
                s['high'], s['low'] = max(s['high'], value), min(s['low'], value)
            except (ValueError, csv.Error, UnicodeError):
                sample_bad += 1
        sample_meta = dict(status='SCANNED', **sample_stream.report())
    verified_set = {t for t, r in minutes.items() if r['verified']}
    any_set = {t for t, r in minutes.items() if r['completed']}
    tail_set = {t for t, r in minutes.items() if r['tail8mb_verified']}
    missing = expected - verified_set
    rows, extrema_misses = [], 0
    for t in sorted(run_minutes):
        r, s = minutes.get(t, {}), samples.get(t, {})
        lag = r['first_verified'] - t - 60 if r.get('first_verified') is not None else None
        high_miss = low_miss = None
        if r.get('ohlc') and s:
            high_miss = max(0, r['ohlc'][1]-s['high'])
            low_miss = max(0, s['low']-r['ohlc'][2])
            extrema_misses += high_miss > .000001 or low_miss > .000001
        rows.append(dict(minute_utc=utc(t), fully_contained_in_run=t in expected,
                         verified_completed_observations=r.get('verified', 0),
                         unverified_completed_observations=r.get('unverified', 0),
                         completed_first_verified_utc=utc(r.get('first_verified')),
                         first_verified_lag_after_close_sec=round(lag,6) if lag is not None else None,
                         in_default_8MB_snapshot_tail=t in tail_set,
                         developing_observations=r.get('developing', 0),
                         completed_value_changes=r.get('revisions', 0),
                         sampled_price_records=s.get('count', 0),
                         sampled_high_shortfall=high_miss, sampled_low_shortfall=low_miss))
    writer_count = num(stats.get('written'))
    written_match = (writer_count == counts['newline_terminated_lines'] and source_stable and
                     stats_stable and manifest.get('status') in STOPPED)
    integrity_bad = any(counts[k] for k in ('malformed_json', 'nonobject_json', 'unsupported_schema',
        'capture_timestamp_conflicts', 'missing_capture_time', 'foreign_identity_records',
        'unverified_identity_records', 'oversized_lines', 'unterminated_final_line', 'blank_lines',
        'capture_outside_run_window'))
    eligible = (source_stable and metadata_stable and identities_known and not integrity_bad and
                manifest.get('status') in STOPPED)
    if not eligible:
        verdict = 'INCOMPLETE_OR_IDENTITY_INTEGRITY_UNVERIFIED'
    elif missing:
        verdict = 'COMPLETED_CANDLE_GAPS'
    else:
        verdict = 'COMPLETED_CANDLE_COVERAGE_PRESENT'
    lag_values = [r['first_verified_lag_after_close_sec'] for r in rows
                  if r['fully_contained_in_run'] and r['first_verified_lag_after_close_sec'] is not None]
    summary = dict(tool_version=VERSION, generated_utc=utc(time.time()),
        source_identity=dict(run_directory=str(run), manifest_directory=manifest.get('run_directory'),
            engine_version=manifest.get('version'), run_id=run_id, session_id=session_id,
            pid=manifest.get('pid'), status=manifest.get('status'), started_utc=utc(start), ended_utc=utc(end),
            association='Snapshot run_id AND session_id must match runtime; stats alone carry no identity'),
        scope=dict(fixed_initial_file_size=True, allow_live=allow_live, max_record_bytes=MAX_LINE,
            full_stream_scanned=True, prices_not_execution_claims=True, browser_uptime_measured=False),
        verdict=verdict, sources=dict(snapshot=source, manifest=mf, runtime=rf, writer_stats=sf, seed=seed_f,
                                     price_telemetry=sample_meta),
        metadata_stable=bool(metadata_stable), record_counts=dict(counts), schema_counts=dict(schemas),
        event_counts=dict(events), frame_fields=dict(fields), invalid_candle_counts=dict(invalid),
        snapshots_all_timeline=timeline.report(), snapshots_verified_timeline=matched_timeline.report(),
        writer=dict(reported=stats, stats_stable=bool(stats_stable),
                    complete_lines_match_written=bool(written_match),
                    note='Counter agreement does not validate OHLC or browser delivery; co-located stats are not signed run identity'),
        candle_coverage=dict(expected_fully_contained_minutes=len(expected),
            unique_verified_completed_minutes=len(expected & verified_set),
            unique_completed_minutes_any_identity=len(expected & any_set),
            missing_verified_minutes=len(missing), missing_ranges=ranges(missing),
            verified_completed_unique_including_warmup=len(verified_set),
            valid_seed_occurrences=seed_count, current_candle_minutes=len({t for t,r in minutes.items() if r['developing']} & expected),
            completed_minutes_in_default_8MB_tail=len(expected & tail_set),
            first_seen_lag_seconds=dict(min=min(lag_values) if lag_values else None,
                max=max(lag_values) if lag_values else None,
                mean=sum(lag_values)/len(lag_values) if lag_values else None,
                over5=sum(n>5 for n in lag_values), over30=sum(n>30 for n in lag_values)),
            revised_completed_minutes=sum(bool(r.get('revisions')) for t,r in minutes.items() if t in expected),
            note='Expected minutes are fully inside [run start, run end]. Startup/shutdown partial minutes are listed separately. Historical box_candles repeats count once per minute.'),
        price_samples=dict(timeline=sample_time.report(), malformed_records=sample_bad,
            minutes=len(samples), minutes_with_high_or_low_not_reached_by_samples=extrema_misses,
            note='Different source cadence can miss extrema. This comparison does not certify exchange candle parity.'),
        limited_examples=examples,
        limitations=['No engine, strategy, snapshot writer, dashboard or sidecar files are changed.',
            'No decisions, quote payloads, private credentials or raw snapshot lines are exported.',
            'Completed bars are engine-exported observations, not proof of exchange-feed completeness.',
            'An existing completed bar can arrive late or be revised. See per-minute lag and revision counts.',
            'The eight-million-byte tail comparison models an initial read, not the browser\'s actual intake.',
            'No screen-uptime, actual clock-offset, RAM-endurance or past drive-free-space measurements are inferred.'])
    return summary, rows


def render(summary):
    s, c, w = summary, summary['candle_coverage'], summary['writer']
    lines = ['# Nautilus R7 - local candle-coverage report', '',
        '**Verdict:** `' + s['verdict'] + '`', '',
        'This describes recorded data availability, not a new trading signal or proof of browser delivery.', '',
        '## Exact source', '', '```json', json.dumps(s['source_identity'], indent=2), '```', '',
        '## Completed one-minute candles', '',
        f"- Fully contained run minutes: **{c['expected_fully_contained_minutes']}**",
        f"- Minutes with valid, session-matched completed OHLC: **{c['unique_verified_completed_minutes']}**",
        f"- Missing verified minutes: **{c['missing_verified_minutes']}**",
        f"- Completed minutes available to an initial 8,000,000-byte tail: **{c['completed_minutes_in_default_8MB_tail']}**",
        f"- Minutes with an explicit developing current_candle: **{c['current_candle_minutes']}**",
        f"- Completed minutes whose values later changed: **{c['revised_completed_minutes']}**", '',
        c['note'], '', '## Capture and delivery lag', '', '```json',
        json.dumps(dict(capture=s['snapshots_verified_timeline'], completed_first_seen_lag=c['first_seen_lag_seconds']),indent=2),
        '```', '', '## Writer counter reconciliation', '', '```json', json.dumps(w,indent=2), '```', '',
        '## Record integrity', '', '```json', json.dumps(dict(records=s['record_counts'],invalid_candles=s['invalid_candle_counts'],
        schemas=s['schema_counts'],metadata_stable=s['metadata_stable'],snapshot_file=s['sources']['snapshot']),indent=2), '```', '',
        '## Missing completed-minute ranges', '', '```json', json.dumps(c['missing_ranges'],indent=2), '```', '',
        '## What this does not establish', '']
    lines += ['- '+x for x in s['limitations']]
    lines += ['', 'See coverage.json for the machine-readable report and minutes.csv for bounded per-minute counts.', '']
    return '\n'.join(lines)


def write_report(summary, rows, out_root):
    run = Path(summary['source_identity']['run_directory']).resolve()
    root = Path(out_root).resolve()
    if root == run or run in root.parents:
        raise ValueError('Reports must be outside the engine run directory')
    tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + secrets.token_hex(3)
    destination = root/('Nautilus_R7_Candle_Coverage_'+tag)
    destination.mkdir(parents=True, exist_ok=False)
    (destination/'coverage.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (destination/'REPORT.md').write_text(render(summary),encoding='utf-8')
    with (destination/'minutes.csv').open('w',encoding='utf-8',newline='') as f:
        if rows:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    archive=destination.with_suffix('.zip')
    with ZipFile(archive,'x',ZIP_DEFLATED,compresslevel=6) as z:
        for name in ['REPORT.md','coverage.json','minutes.csv']:
            z.write(destination/name, name)
    return archive


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=Path(DEFAULT_RUN))
    parser.add_argument('--out-root',type=Path,default=Path(DEFAULT_OUT))
    parser.add_argument('--allow-live',action='store_true',help='Explicit partial snapshot at current byte length; never a stopped-run coverage pass')
    args=parser.parse_args(argv)
    then=time.monotonic(); last=[0.0]
    def progress(n,total):
        now=time.monotonic()
        if now-last[0]>10:
            print(f'Reading {n/1048576:,.1f} / {total/1048576:,.1f} MiB (bounded memory; originals unchanged)',flush=True)
            last[0]=now
    try:
        print('NAUTILUS LOCAL CANDLE COVERAGE | READ ONLY\nRun: '+str(args.run),flush=True)
        print('The large snapshot stays on E:. Only a small report is created.',flush=True)
        summary,rows=analyze(args.run,allow_live=args.allow_live,progress=progress)
        archive=write_report(summary,rows,args.out_root)
        c=summary['candle_coverage']
        print(f"\nSCAN FINISHED in {time.monotonic()-then:.1f}s\nVerdict: {summary['verdict']}\nCompleted minutes: {c['unique_verified_completed_minutes']} / {c['expected_fully_contained_minutes']}\nREPORT ZIP: {archive}\nUpload only that report ZIP; keep the original snapshot locally.",flush=True)
        return 0
    except KeyboardInterrupt:
        print('\nCancelled. Original run files are unchanged. No complete report was issued.',file=sys.stderr)
        return 130
    except (OSError,ValueError,TypeError,KeyError,csv.Error) as exc:
        print('\nCHECK DID NOT COMPLETE: '+str(exc)+'\nNo engine or snapshot files were changed.',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
