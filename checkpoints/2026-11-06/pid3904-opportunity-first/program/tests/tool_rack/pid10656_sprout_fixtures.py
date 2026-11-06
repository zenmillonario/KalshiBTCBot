"""Exact PID10656 admission/opening records; component controls, not replay."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path

from strategy_core.paper_execution import PaperBook, PriceLevel
from strategy_core.paper_runtime import snapshot_from_book
from strategy_core.router import PhysicalEvidence
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, Lane, Side, ToolIntent


DIRECTORY = Path(__file__).with_name('fixtures')
MANIFEST = DIRECTORY / 'pid10656_sprout_manifest.json'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@lru_cache(maxsize=1)
def manifest():
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if data['schema'] != 'TACHYOS_PID10656_SPROUT_CASES_V1':
        raise ValueError('Unexpected PID10656 fixture schema')
    if hashlib.sha256((DIRECTORY / data['cases_file']).read_bytes()).hexdigest() != data['cases_sha256']:
        raise ValueError('PID10656 original case fixture changed')
    return data


@lru_cache(maxsize=1)
def _corpus():
    evidence = manifest()
    records, histories = {}, {}
    with gzip.open(DIRECTORY / evidence['cases_file'], 'rb') as source:
        for seq in evidence['record_order']:
            raw = source.readline()
            data = json.loads(raw)
            expected = evidence['records'][str(seq)]
            digest = hashlib.sha256(canonical({k:v for k,v in data.items() if k != 'sha256'})).hexdigest()
            if (data['sequence'] != seq or len(raw) != expected['length']
                    or hashlib.sha256(raw).hexdigest() != expected['raw_sha256']
                    or digest != expected['sha256'] or digest != data['sha256']
                    or data['previous_sha256'] != expected['previous_sha256']):
                raise ValueError('Original PID10656 decision changed: ' + str(seq))
            records[seq] = data
        if source.read(1):
            raise ValueError('Unexpected extra PID10656 decision')
    for digest, item in evidence['histories'].items():
        raw = item['original_line'].encode()
        data = json.loads(raw)
        if (len(raw) != item['length'] or hashlib.sha256(raw).hexdigest() != item['raw_sha256']
                or hashlib.sha256(canonical(data['candles'])).hexdigest() != digest
                or data['sha256'] != digest):
            raise ValueError('Original PID10656 mission history changed')
        histories[digest] = data
    return records, histories


def record(sequence):
    return deepcopy(_corpus()[0][sequence])


def book(sequence):
    native = deepcopy(_corpus()[0][sequence]['native_book'])
    for side in ('yes_bids', 'no_bids'):
        native[side] = tuple(PriceLevel(**row) for row in native[side])
    return PaperBook(**native)


def snapshot(sequence):
    data = _corpus()[0][sequence]
    md = deepcopy(data['physical_metadata'])
    # These logged diagnostic products are not copied back as fresh adviser
    # input by the captured coordinator. Original inventory remains untouched.
    md.pop('candidate_review', None)
    md.pop('quote_wave', None)
    snap = snapshot_from_book(book(sequence), now_ts=data['now_ts'], metadata=md,
        ticker=data['market']['ticker'], close_ts=data['market']['close_ts'])
    history = _corpus()[1][md['mission_history_reference']]
    if history['known_at'] > snap.now_ts:
        raise ValueError('Mission history was not known at the original decision')
    rack = ToolRackController()
    rack._mission_history = tuple(history['candles'])
    extreme = rack._historical_extreme_release_context(snap)
    return replace(snap, metadata={**snap.metadata, 'historical_extreme_release':extreme})


def typed_intent(raw):
    data = deepcopy(raw)
    data['side'] = Side(data['side']) if data.get('side') else None
    data['lane'], data['action'] = Lane(data['lane']), Action(data['action'])
    return ToolIntent(**data)


def entry_intent(sequence):
    raw = next(row['decision']['intent'] for row in _corpus()[0][sequence]['decisions']
        if row['scope'] == 'ENTRY' and row['decision']['action'] in ('ENTER','RELAY'))
    return typed_intent(raw)


def physical(sequence):
    data = deepcopy(_corpus()[0][sequence]['physical'])
    for key in ('ema9_direction','ema30_direction','mountain_direction','rail_launch_side',
                'release_candidate_side','release_side'):
        if data.get(key) is not None:
            data[key] = Side(data[key])
    return PhysicalEvidence(**data)


def original_event(sequence, event):
    return deepcopy(next(row['receipt']['event'] for row in _corpus()[0][sequence]['decisions']
        if (row.get('receipt') or {}).get('event', {}).get('event') == event))


def opening_sequences():
    return tuple(seq for seq in manifest()['opening_window_sequences']
        if _corpus()[0][seq]['market']['ticker'] == 'KXBTC15M-26NOV051130-30'
        and 0 <= _corpus()[0][seq]['now_ts'] - _corpus()[0][seq]['market']['open_ts'] < 60.)


def mirrored(snapshot_value, intent):
    """Explicit synthetic direction mirror of an immutable recorded control.

    Relative-to-owner motion stays unchanged. No mirrored record is described
    as an event that occurred in the original session.
    """
    sides = {'YES':'NO', 'NO':'YES', 'UP':'DOWN', 'DOWN':'UP'}
    def swap(value):
        if isinstance(value, dict):
            return {k:swap(v) for k,v in value.items()}
        if isinstance(value, list):
            return [swap(v) for v in value]
        if isinstance(value, tuple):
            return tuple(swap(v) for v in value)
        if isinstance(value, str):
            return sides.get(value, value)
        return value
    md = swap(deepcopy(snapshot_value.metadata))
    geometry = md['current_geometry']
    for key in ('btc_price','ema9','ema30'):
        if geometry.get(key) is not None:
            geometry[key] = 200000. - geometry[key]
    for key in ('ema_gap','btc_change6','btc_change9','btc_change30','btc_change60',
                'ema9_change6','ema9_change30','ema9_change60'):
        if geometry.get(key) is not None:
            geometry[key] = -geometry[key]
    cross = md['ema9_ema30_cross_context']
    if cross.get('current_signed_gap_btc') is not None:
        cross['current_signed_gap_btc'] = -cross['current_signed_gap_btc']
    mirrored_snap = replace(snapshot_value, yes_ask=snapshot_value.no_ask,
        no_ask=snapshot_value.yes_ask, yes_bid=snapshot_value.no_bid,
        no_bid=snapshot_value.yes_bid, metadata=md)
    mirrored_intent = replace(intent, side=Side.NO if intent.side is Side.YES else Side.YES,
        metadata=swap(deepcopy(intent.metadata)))
    return mirrored_snap, mirrored_intent
