"""Bounded original recovery evidence; no engine replay or alternative fills."""
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
import gzip
import hashlib
import json

from strategy_core.paper_execution import PaperBook, PriceLevel
from strategy_core.paper_runtime import snapshot_from_book
from strategy_core.recovery import independent_entry_denial
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, Lane, Side, ToolIntent

DIRECTORY = Path(__file__).with_name('fixtures')

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

@lru_cache(maxsize=1)
def manifest():
    data=json.loads((DIRECTORY/'pid4824_recovery_manifest.json').read_text(encoding='utf-8'))
    if data['schema']!='TACHYOS_PID4824_RECOVERY_IDENTITY_CASES_V1':
        raise ValueError('Wrong PID4824 recovery fixture schema')
    for name in ('cases','journal','parent_prefix'):
        asset=data[name]
        if hashlib.sha256((DIRECTORY/asset['file']).read_bytes()).hexdigest()!=asset['sha256']:
            raise ValueError('PID4824 recovery asset changed: '+name)
    return data

@lru_cache(maxsize=1)
def corpus():
    m=manifest(); records={}; journals={}; histories={}
    with gzip.open(DIRECTORY/m['cases']['file'],'rb') as f:
        for key in m['record_order']:
            raw=f.readline();d=json.loads(raw);e=m['records'][key]
            if (len(raw)!=e['byte_length'] or d['sequence']!=e['sequence']
                    or hashlib.sha256(raw).hexdigest()!=e['original_line_sha256']
                    or d['sha256']!=e['sha256']
                    or hashlib.sha256(canonical({k:v for k,v in d.items() if k!='sha256'})).hexdigest()!=d['sha256']):
                raise ValueError('Original recovery decision changed: '+key)
            records[key]=d
        if f.read(1):raise ValueError('Unexpected extra recovery decision')
    with gzip.open(DIRECTORY/m['journal']['file'],'rt') as f:
        for line in f:
            envelope=json.loads(line);key=envelope['key'];raw=envelope['original_bytes_utf8'].encode()
            d=json.loads(raw);e=m['journals'][key]
            if (hashlib.sha256(raw).hexdigest()!=e['original_file_sha256']
                    or d['sha256']!=e['ledger_sha256']
                    or hashlib.sha256(canonical({k:v for k,v in d.items() if k!='sha256'})).hexdigest()!=d['sha256']):
                raise ValueError('Original recovery journal changed: '+key)
            journals[key]=d
    if set(journals)!=set(m['journals']):raise ValueError('Recovery journal corpus incomplete')
    for key,e in m['history'].items():
        raw=e['original_line'].encode();h=json.loads(raw)
        if (hashlib.sha256(raw).hexdigest()!=e['original_line_sha256']
                or h['sha256']!=e['sha256']
                or hashlib.sha256(canonical(h['candles'])).hexdigest()!=h['sha256']):
            raise ValueError('Recovery mission history changed')
        histories[key]=h
    return records,journals,histories

def record(seq=2441,run='PID4824'):
    return deepcopy(corpus()[0][f'{run}:{seq}'])

def snapshot(seq=2441,run='PID4824'):
    d=record(seq,run);md=deepcopy(d['physical_metadata']);md.pop('quote_wave',None);md.pop('candidate_review',None)
    native=deepcopy(d['native_book'])
    for side in ('yes_bids','no_bids'):native[side]=tuple(PriceLevel(**p) for p in native[side])
    snap=snapshot_from_book(PaperBook(**native),now_ts=d['now_ts'],metadata=md,
        ticker=d['market']['ticker'],close_ts=d['market']['close_ts'])
    history=corpus()[2][f"{run}:{md['mission_history_reference']}"]
    if history['known_at']>snap.now_ts:raise ValueError('Future history in recovery fixture')
    rack=ToolRackController();rack._mission_history=tuple(history['candles'])
    return replace(snap,metadata={**snap.metadata,
        'historical_extreme_release':rack._historical_extreme_release_context(snap)})

def typed(raw):
    raw=deepcopy(raw);raw['action']=Action(raw['action']);raw['lane']=Lane(raw['lane'])
    raw['side']=Side(raw['side']) if raw.get('side') else None
    return ToolIntent(**raw)

def intent(seq=2441,run='PID4824'):
    d=record(seq,run)
    return typed(next(x for x in d['decisions'] if x['scope']=='ENTRY')['decision']['intent'])

def original_pre_entry_positions(seq=2441,run='PID4824'):
    d=record(seq,run);n=d['ledger_seq'];before=deepcopy(corpus()[1][f'{run}:{n-1}']);after=corpus()[1][f'{run}:{n}']
    if after['kind']!='ENTRY' or after['previous_sha256']!=before['sha256'] or after['sha256']!=d['ledger_sha256']:
        raise ValueError('Selected record is not bound to its exact original entry boundary')
    return before['state']['positions']

def qualify(seq=2441,run='PID4824',*,positions=None,proposed=None,current=None):
    positions=original_pre_entry_positions(seq,run) if positions is None else deepcopy(positions)
    current=snapshot(seq,run) if current is None else current
    proposed=intent(seq,run) if proposed is None else proposed
    rack=ToolRackController()
    for p in positions.values():
        if p['custody_state']=='LAZARUS':
            rack._recovery_detached.add((p['ticker'],p['territory_id'],p['opportunity_id']))
    updated=rack.qualify_independent_recovery_mission(proposed,current,positions)
    held=[p for p in positions.values() if p['ticker']==current.ticker]
    denial=independent_entry_denial(updated,held,now_ts=current.now_ts,
        continuity_generation=current.metadata.get('geometry_continuity_generation'))
    return updated,denial

def pinned_original_positions(seq=2441):
    positions=original_pre_entry_positions(seq)
    for p in positions.values():
        origin={'1':2044,'2':2441}[p['position_id']]
        updated,_=qualify(origin,positions={})
        p['entry_metadata']['recovery_physical_identity']=deepcopy(updated.metadata['recovery_physical_identity'])
    return positions

@lru_cache(maxsize=1)
def parent_prefix():
    m=manifest()
    with gzip.open(DIRECTORY/m['parent_prefix']['file'],'rt') as f:rows=tuple(json.loads(line) for line in f)
    if len(rows)!=813:raise ValueError('Wrong original parent prefix count')
    previous=None
    for seq,row in enumerate(rows,2044):
        if row['source']['sequence']!=seq or (previous is not None and row['source']['previous_sha256']!=previous):
            raise ValueError('Original parent prefix has a gap/reset')
        previous=row['source']['sha256']
        key=f'PID4824:{seq}'
        if key in m['records']:
            d=record(seq);g=d['physical_metadata']['current_geometry'];context=d['physical_metadata']['mission_context']
            if (row['source']['sha256']!=d['sha256'] or row['arc_id']!=g['arc_id']
                    or row['parent']!={k:context['parent'].get(k) for k in row['parent']}):
                raise ValueError('Parent projection disagrees with original full case')
    return rows

def bounded_results():
    result=[]
    for run,seqs in [('PID4824',(2044,2441,2856,5181,6756,7913)),('PID17588',(6294,))]:
        for seq in seqs:
            proposed=intent(seq,run);positions=original_pre_entry_positions(seq,run);snap=snapshot(seq,run)
            baseline=independent_entry_denial(proposed,list(positions.values()),now_ts=snap.now_ts,
                continuity_generation=snap.metadata.get('geometry_continuity_generation'))
            updated,denial=qualify(seq,run)
            result.append({'run':run,'sequence':seq,'original_boundary_denial':baseline,
                'repaired_boundary_denial':denial,'original_held_ids':list(positions),
                'new_proof':updated.metadata.get('independent_recovery_mission'),
                'pinned_identity':updated.metadata.get('recovery_physical_identity')})
    return {'scope':'Separate original-inventory component decisions; no alternate filled path or P/L.',
        'original_cases':result,'flat_sensitivity2856':qualify(2856,positions={})[1],
        'original_same_parent_prefix_rows':len(parent_prefix()),
        'late_release_controls':late_release_results(),
        'original_callback_comparison':manifest()['original_callback_comparison']}

def late_release_results(*,pin_held_identity=False):
    results=[]
    for e in manifest()['late_release_original_component_baseline']:
        seq=e['sequence'];d=record(seq);snap=snapshot(seq)
        if d['sha256']!=e['decision_sha256']:
            raise ValueError('Late Release component source binding changed')
        actual=next(x for x in d['decisions'] if x['scope']=='ENTRY')['decision']['reason']
        if actual!=e['original_entry_reason']:
            raise ValueError('Late Release original runtime gate changed')
        positions=deepcopy(corpus()[1][f"PID4824:{d['ledger_seq']}"]['state']['positions'])
        if pin_held_identity:
            pinned,_=qualify(7913,positions={})
            positions['6']['entry_metadata']['recovery_physical_identity']=deepcopy(pinned.metadata['recovery_physical_identity'])
        offered=next(x for x in d['rack']['commander_intents'] if x['tool']=='RELEASE_WATCHER')
        updated,denial=qualify(seq,positions=positions,proposed=typed(offered),current=snap)
        results.append({'sequence':seq,'original_entry_reason':actual,'runtime_called':e['original_runtime_called'],
            'original_component':e['baseline'],
            'new_component':{'proof':bool(updated.metadata.get('independent_recovery_mission')),'boundary_denial':denial}})
    return results
