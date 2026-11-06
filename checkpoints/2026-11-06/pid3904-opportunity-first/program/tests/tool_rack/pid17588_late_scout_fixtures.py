"""Hermetic exact PID17588 late-scout and preserved PID19996 entry evidence.

Original record bytes and canonical hashes are verified before use. Runtime
Historical Extreme context is recomputed from the original contemporaneous
history identified by each decision. Only the existing PID19996 source-receipt
bridge is derived. No source, quote, decision, or history timestamp is moved.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path

from strategy_core.commander import OneCommander
from strategy_core.paper_execution import PaperBook, PriceLevel
from strategy_core.paper_runtime import snapshot_from_book
from strategy_core.source_freshness import RECEIPT_KEY, capture_source_receipt
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, Lane, Side, ToolIntent


DIRECTORY = Path(__file__).with_name('fixtures')
MANIFEST = DIRECTORY / 'pid17588_late_scout_manifest.json'


@lru_cache(maxsize=1)
def manifest():
    result = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if result['schema'] != 'TACHYOS_PID17588_LATE_SCOUT_RECORDED_CASES_V1':
        raise ValueError('Unexpected PID17588 fixture schema')
    for file_key, hash_key in (('cases_file', 'cases_sha256'),
                              ('histories_file', 'histories_sha256')):
        if hashlib.sha256((DIRECTORY / result[file_key]).read_bytes()).hexdigest() != result[hash_key]:
            raise ValueError('PID17588 compressed fixture changed: ' + result[file_key])
    return result


@lru_cache(maxsize=1)
def _corpus():
    evidence = manifest()
    records, histories = {}, {}
    with gzip.open(DIRECTORY / evidence['cases_file'], 'rb') as source:
        for key in evidence['record_order']:
            raw = source.readline()
            record = json.loads(raw)
            expected = evidence['records'][key]
            digest = hashlib.sha256(json.dumps({k: v for k, v in record.items() if k != 'sha256'},
                sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            if (record['sequence'] != expected['sequence']
                    or hashlib.sha256(raw).hexdigest() != expected['original_line_sha256']
                    or digest != record['sha256'] or digest != expected['decision_sha256']):
                raise ValueError('Original PID17588/PID19996 decision changed: ' + key)
            records[key] = record
        if source.read(1):
            raise ValueError('Unexpected extra PID17588 fixture decisions')
    with gzip.open(DIRECTORY / evidence['histories_file'], 'rb') as source:
        for key in evidence['history_order']:
            raw = source.readline()
            record = json.loads(raw)
            expected = evidence['histories'][key]
            digest = hashlib.sha256(json.dumps(record['candles'], sort_keys=True,
                separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            if (hashlib.sha256(raw).hexdigest() != expected['original_line_sha256']
                    or digest != record['sha256'] or digest != expected['history_sha256']):
                raise ValueError('Original mission history changed: ' + key)
            histories[key] = record
        if source.read(1):
            raise ValueError('Unexpected extra PID17588 fixture histories')
    return records, histories


def record(key='PID17588:2729'):
    return deepcopy(_corpus()[0][key])


def snapshot(key='PID17588:2729'):
    data = record(key)
    run = key.split(':', 1)[0]
    metadata = deepcopy(data['physical_metadata'])
    if run == 'PID19996':
        source_ms = metadata['current_geometry']['epoch_ms']
        captured_at = source_ms / 1000.0 + data['source_status']['btc_geometry_age_seconds']
        metadata[RECEIPT_KEY] = capture_source_receipt(metadata, data['source_status'],
            captured_at=captured_at, source_generation=data['source_generation'])
    native = deepcopy(data['native_book'])
    for side in ('yes_bids', 'no_bids'):
        native[side] = tuple(PriceLevel(**row) for row in native[side])
    snap = snapshot_from_book(PaperBook(**native), now_ts=data['now_ts'],
        metadata=metadata, ticker=data['market']['ticker'], close_ts=data['market']['close_ts'])
    history = _corpus()[1][run + ':' + metadata['mission_history_reference']]
    if history['known_at'] > data['now_ts']:
        raise ValueError('A historical context was not yet known at the decision')
    rack = ToolRackController()
    rack._mission_history = tuple(history['candles'])
    extreme = rack._historical_extreme_release_context(snap)
    original = next(row for row in data['decisions'] if row['scope'] == 'ENTRY')
    original_metadata = (original['decision'].get('intent') or {}).get('metadata', {})
    if 'historical_extreme_release' in original_metadata:
        if extreme != original_metadata['historical_extreme_release']:
            raise ValueError('Recomputed Historical Extreme differs from recorded entry evidence')
    return replace(snap, metadata={**snap.metadata, 'historical_extreme_release': extreme})


def typed_intent(raw):
    data = deepcopy(raw)
    data['side'] = Side(data['side']) if data.get('side') else None
    data['lane'], data['action'] = Lane(data['lane']), Action(data['action'])
    return ToolIntent(**data)


def decision_brief(decision):
    intent = decision.intent
    return {'action': decision.action.value, 'reason': decision.reason,
        'intent_reason': intent.reason if intent else None,
        'side': intent.side.value if intent and intent.side else None,
        'opportunity_id': intent.opportunity_id if intent else None,
        'max_price': intent.max_price if intent else None,
        'size_tier': intent.size_tier if intent else None}


@lru_cache(maxsize=8)
def probe_group(name):
    """Rebuild flat-inventory entry admission, never a claimed execution replay."""
    commander, rack = OneCommander(), ToolRackController()
    # The current-parent calibration rule needs actual preceding observations
    # for this formerly isolated positive case. Preserve its original bytes,
    # paid-candidate list and expected entry; do not invent a fresh exception.
    from tests.tool_rack.pid15184_current_parent_fixtures import initialize_prior_positive_observer
    initialize_prior_positive_observer(name, rack)
    rows = []
    for key in manifest()['groups'][name]:
        data, snap = record(key), snapshot(key)
        if data['physical_metadata'].get('position_inventory'):
            raise ValueError('Flat-inventory probe was given a held-position frame')
        advisers = tuple(typed_intent(raw) for raw in
            (data['rack'].get('commander_intents') or data['rack'].get('intents') or [])
            if raw['action'] in ('ENTER', 'RELAY'))
        primary = commander.physical_entry_candidates(snap)
        proposed = tuple(rack.qualify_independent_role_mission(
            rack.qualify_independent_recovery_mission(intent, snap, {}), snap, {})
            for intent in primary + advisers)
        proposed = rack.filter_independent_lane_candidates(proposed, snap)
        decision = commander.decide_entry(proposed, snap, {})
        rows.append({'reference': key, 'now_ts': snap.now_ts,
            'contract_age_s': snap.contract_age_s, 'seconds_left': 900.0 - snap.contract_age_s,
            'original_decision_sha256': data['sha256'], 'decision': decision_brief(decision),
            'opening_watch_retained': commander._opening_rail_value_watch.state is not None})
    return rows


def all_recorded_entry_probes():
    return {name: probe_group(name) for name in manifest()['groups']
            if name != 'original_contract_boundaries'}
