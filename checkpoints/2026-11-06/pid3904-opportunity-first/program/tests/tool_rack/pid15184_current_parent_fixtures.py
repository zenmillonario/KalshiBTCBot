"""Hash-bound PID15184 current-parent component evidence, not an engine replay.

The selected full decisions retain their original bytes and canonical hashes.
The ordered chronology is an explicitly selected-field projection of every
original decision, bound to its original hash/offset and to the fixture digest.
It retains observer inputs and original candidate order, never alternate fills.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, replace
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path

from strategy_core.paper_execution import PaperBook, PriceLevel
from strategy_core.paper_runtime import snapshot_from_book
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


DIRECTORY = Path(__file__).with_name('fixtures')
MANIFEST = DIRECTORY / 'pid15184_current_parent_manifest.json'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@lru_cache(maxsize=1)
def manifest():
    data = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if data['schema'] != 'TACHYOS_PID15184_CURRENT_PARENT_CASES_V1':
        raise ValueError('Unexpected PID15184 fixture schema')
    for name in ('cases', 'chronology'):
        if hashlib.sha256((DIRECTORY / data[name + '_file']).read_bytes()).hexdigest() != data[name + '_sha256']:
            raise ValueError('PID15184 fixture changed: ' + name)
    prefix = data.get('prior_positive_prefix')
    if prefix and hashlib.sha256((DIRECTORY / prefix['file']).read_bytes()).hexdigest() != prefix['sha256']:
        raise ValueError('PID17588 preserved positive calibration prefix changed')
    return data


@lru_cache(maxsize=1)
def _corpus():
    evidence = manifest()
    records, histories = {}, {}
    with gzip.open(DIRECTORY / evidence['cases_file'], 'rb') as source:
        for seq in evidence['record_order']:
            raw = source.readline()
            record = json.loads(raw)
            expected = evidence['records'][str(seq)]
            digest = hashlib.sha256(canonical({k:v for k,v in record.items() if k != 'sha256'})).hexdigest()
            if (record['sequence'] != seq or len(raw) != expected['byte_length']
                    or hashlib.sha256(raw).hexdigest() != expected['original_line_sha256']
                    or digest != record['sha256'] or digest != expected['decision_sha256']):
                raise ValueError('Original PID15184 decision changed: ' + str(seq))
            records[seq] = record
        if source.read(1):
            raise ValueError('Unexpected extra PID15184 decisions')
    for digest, item in evidence['histories'].items():
        raw = item['original_line'].encode()
        history = json.loads(raw)
        if (hashlib.sha256(raw).hexdigest() != item['original_line_sha256']
                or hashlib.sha256(canonical(history['candles'])).hexdigest() != digest
                or history['sha256'] != digest):
            raise ValueError('Original PID15184 mission history changed')
        histories[digest] = history
    return records, histories


def record(seq=26):
    return deepcopy(_corpus()[0][seq])


def snapshot(seq=26):
    data = record(seq)
    md = deepcopy(data['physical_metadata'])
    # These are logged diagnostics and are not copied back to the live
    # Commander snapshot by the captured runtime.
    md.pop('quote_wave', None)
    md.pop('candidate_review', None)
    native = deepcopy(data['native_book'])
    for side in ('yes_bids', 'no_bids'):
        native[side] = tuple(PriceLevel(**row) for row in native[side])
    snap = snapshot_from_book(PaperBook(**native), now_ts=data['now_ts'], metadata=md,
        ticker=data['market']['ticker'], close_ts=data['market']['close_ts'])
    history = _corpus()[1][md['mission_history_reference']]
    if history['known_at'] > data['now_ts']:
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


def component_snapshot(snap):
    """Select only fields consumed by the counterfade observer/filter.

    Values are copied verbatim. No clock, price, qualification, current-parent
    direction, origin witness or missing value is supplied by this projection.
    """
    md = snap.metadata
    selected = {}
    for key in ('physical_current', 'source', 'geometry_last_epoch_ms', 'source_generation',
                'geometry_continuity_generation', 'geometry_max_source_age_seconds',
                'geometry_max_future_skew_seconds', 'physical_source_receipt',
                'release_confirmed_current', 'release_candidate_side'):
        if key in md:
            selected[key] = deepcopy(md[key])
    groups = {
        'current_geometry': ('epoch_ms', 'btc_price', 'ema_gap', 'range180', 'arc_id',
            'arc_direction', 'connection_epoch', 'source_sequence', 'measurement_source'),
        'mission_context': ('current', 'source_ms', 'continuity_generation'),
        'mountain': ('owner_side', 'strong_active_release', 'terminal_evidence_qualified',
            'edge_window_active', 'failed_reextension', 'current_arc_id', 'edge_id'),
        'heist': ('visit_id', 'current_visit_id', 'qualified_box', 'box_id', 'current_zone'),
        'tp_geometry': ('contract_ownership_side',),
    }
    for group, keys in groups.items():
        if group in md:
            original = md.get(group) or {}
            selected[group] = {k:deepcopy(original[k]) for k in keys if k in original}
    context = md.get('mission_context') or {}
    if 'parent' in context:
        parent = context['parent'] or {}
        selected['mission_context']['parent'] = {k:deepcopy(parent[k]) for k in (
            'id', 'side', 'status', 'invalidated', 'supported', 'continuity_generation',
            'source_ms', 'known_ms', 'origin_ms', 'origin_observed', 'basis') if k in parent}
    mountain = md.get('mountain') or {}
    if 'parent_structure' in mountain:
        parent = mountain['parent_structure'] or {}
        selected['mountain']['parent_structure'] = {k:deepcopy(parent[k]) for k in (
            'parent_id', 'parent_side', 'parent_terminal_ready') if k in parent}
    cross = md.get('ema9_ema30_cross_context') or {}
    if 'gap_lifecycle' in cross:
        selected['ema9_ema30_cross_context'] = {'gap_lifecycle':deepcopy(cross['gap_lifecycle'])}
    return {**{f.name:getattr(snap,f.name) for f in fields(MarketSnapshot) if f.name != 'metadata'},
        'metadata':selected}


@lru_cache(maxsize=1)
def chronology():
    evidence = manifest()
    with gzip.open(DIRECTORY / evidence['chronology_file'], 'rt', encoding='utf-8') as source:
        rows = tuple(json.loads(line) for line in source)
    if len(rows) != evidence['chronology_rows']:
        raise ValueError('PID15184 chronology count changed')
    previous = None
    for seq, row in enumerate(rows,1):
        if row['source']['sequence'] != seq:
            raise ValueError('PID15184 chronology is not the complete ordered prefix')
        if previous is not None and row['source']['previous_sha256'] != previous:
            raise ValueError('PID15184 original hash-link order changed')
        previous = row['source']['sha256']
        if seq in _corpus()[0]:
            full = snapshot(seq)
            if component_snapshot(full) != row['snapshot']:
                raise ValueError('Selected component disagrees with its full original record')
    if previous != evidence['last_original_decision_sha256']:
        raise ValueError('PID15184 last original hash changed')
    return rows


@lru_cache(maxsize=1)
def chronology_probe():
    """Ordered observer/filter calls using original proposals and consumption.

    No engine, executor, inventory alteration, alternative fills or returns
    are simulated. Only filtering of each retained proposal is compared.
    """
    rack = ToolRackController()
    fills, changed, first, physical_count = [], [], None, 0
    for row in chronology():
        if not row['observe']:
            continue
        snap = MarketSnapshot(**deepcopy(row['snapshot']))
        rack._dual_counterfade.observe_first_physical_swing(snap)
        rack.filter_independent_lane_candidates(tuple(typed_intent(x) for x in row['reviewed']), snap)
        offers = tuple(typed_intent(x) for x in row['runtime_offers'])
        allowed = rack.filter_independent_lane_candidates(offers, snap) if row['runtime_called'] else ()
        if first is None and rack._dual_counterfade.last_observation:
            first = {'sequence':row['source']['sequence'],
                'observation':rack._dual_counterfade.last_observation}
        keys = {(x.opportunity_id, x.side.value if x.side else None) for x in allowed}
        for proposal in row['physical_proposals']:
            physical_count += 1
            key = (proposal['opportunity_id'], proposal['side'])
            current = key in keys
            if current != proposal['original_allowed']:
                changed.append({'sequence':row['source']['sequence'], 'opportunity_id':key[0],
                    'side':key[1], 'original_allowed':proposal['original_allowed'], 'current_allowed':current})
        if row.get('recorded_fill'):
            fill = row['recorded_fill']
            fills.append({'sequence':row['source']['sequence'], 'position_id':fill['position_id'],
                'current_filter_allowed':(fill['opportunity_id'],fill['side']) in keys,
                'first_observation':rack._dual_counterfade.last_observation})
    return {'chronology_rows':len(chronology()), 'physical_callbacks':physical_count,
        'changed_physical_callbacks':changed, 'recorded_fill_filter_results':fills,
        'first_current_parent_observation':first}


@lru_cache(maxsize=1)
def prior_positive_prefix():
    """Actual prior observations for the old isolated PID17588 positive case."""
    evidence = manifest()['prior_positive_prefix']
    with gzip.open(DIRECTORY / evidence['file'], 'rt', encoding='utf-8') as source:
        rows = tuple(json.loads(line) for line in source)
    if len(rows) != evidence['rows']:
        raise ValueError('Prior positive prefix row count changed')
    previous = None
    for seq, row in enumerate(rows,evidence['first_sequence']):
        if row['source']['sequence'] != seq:
            raise ValueError('Prior positive observation order changed')
        if previous is not None and row['source']['previous_sha256'] != previous:
            raise ValueError('Prior positive original hash-link order changed')
        previous = row['source']['sha256']
        parent = row['snapshot']['metadata']['mission_context']['parent']
        geo = row['snapshot']['metadata']['current_geometry']
        if [parent['id'],parent['side'],parent['continuity_generation'],geo['connection_epoch']] != evidence['parent_identities'][0]:
            raise ValueError('Prior positive parent/continuity changed')
    seed = rows[0];raw = seed['original_line'].encode();original = json.loads(raw)
    expected = evidence['seed_full_original_record']
    if (hashlib.sha256(raw).hexdigest() != expected['original_line_sha256']
            or len(raw) != expected['byte_length'] or original['sha256'] != seed['source']['sha256']
            or hashlib.sha256(canonical({k:v for k,v in original.items() if k != 'sha256'})).hexdigest() != expected['sha256']
            or previous != evidence['last_original_sha256']):
        raise ValueError('Prior positive original seed or boundary changed')
    native = deepcopy(original['native_book'])
    for side in ('yes_bids','no_bids'):
        native[side] = tuple(PriceLevel(**x) for x in native[side])
    full = snapshot_from_book(PaperBook(**native),now_ts=original['now_ts'],
        metadata=deepcopy(original['physical_metadata']),ticker=original['market']['ticker'],close_ts=original['market']['close_ts'])
    if component_snapshot(full) != seed['snapshot']:
        raise ValueError('Prior positive seed component disagrees with original bytes')
    return rows


def initialize_prior_positive_observer(group, rack):
    """Initialize only the preserved old case from source-bound observations.

    The control's paid candidate and expected admission remain unchanged. This
    supplies the real prior observation required by the new stateful rule;
    it never assigns memory fields, manufactures a swing, or books an order.
    """
    if group != 'PID17588_trade2_positive':
        return
    for row in prior_positive_prefix():
        snap = MarketSnapshot(**deepcopy(row['snapshot']))
        rack._dual_counterfade.observe_first_physical_swing(snap)
        rack.filter_independent_lane_candidates(tuple(typed_intent(x) for x in row['reviewed']),snap)
        rack.filter_independent_lane_candidates(tuple(typed_intent(x) for x in row['runtime_advisers']),snap)
