"""Exact recorded floor inputs and bounded, isolated floor observations.

Original lines are immutable and hash-bound. A component account reconstructs
one recorded entry through the public PAPER writer, then observes floors only.
Captured advisers/custody feed policy evaluation; this is not a full engine,
inventory, custody, entry-selection, exit or alternative-profit replay.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import zipfile

from strategy_core.commander import CommanderDecision
from strategy_core.paper_execution import PaperBook, PaperExecutioner, PaperPosition, PriceLevel
from strategy_core.paper_runtime import ToolRackPaperEngine, plain, snapshot_from_book
from strategy_core.types import Action, Lane, Side, ToolIntent


DIRECTORY=Path(__file__).with_name('fixtures')
MANIFEST=DIRECTORY/'pid4824_floor_manifest.json'


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


@lru_cache(maxsize=1)
def manifest():
    evidence=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if evidence['schema']!='TACHYOS_PID4824_FLOOR_ORIGINAL_CASES_V1':
        raise ValueError('Unexpected PID4824 floor fixture schema')
    if hashlib.sha256((DIRECTORY/evidence['cases_file']).read_bytes()).hexdigest()!=evidence['cases_sha256']:
        raise ValueError('PID4824 original floor cases changed')
    return evidence


@lru_cache(maxsize=1)
def _corpus():
    evidence=manifest();records={}
    with gzip.open(DIRECTORY/evidence['cases_file'],'rb') as source:
        for sequence in evidence['record_order']:
            raw=source.readline();record=json.loads(raw);reference=evidence['records'][str(sequence)]
            digest=hashlib.sha256(canonical({k:v for k,v in record.items() if k!='sha256'})).hexdigest()
            if (record['sequence']!=sequence or len(raw)!=reference['byte_length']
                    or hashlib.sha256(raw).hexdigest()!=reference['original_line_sha256']
                    or digest!=record['sha256'] or digest!=reference['decision_sha256']):
                raise ValueError('Original PID4824 decision changed: '+str(sequence))
            records[sequence]=record
        if source.read(1):
            raise ValueError('Unexpected additional PID4824 floor records')
    for group in evidence['groups'].values():
        sequences=group['ordered_sequences'];previous=None;previous_time=None
        for expected,sequence in enumerate(sequences,sequences[0]):
            row=records[sequence]
            if sequence!=expected or previous is not None and row['previous_sha256']!=previous:
                raise ValueError('PID4824 floor trajectory is not the original ordered interval')
            if previous_time is not None and row['now_ts']<previous_time:
                raise ValueError('Original floor input clock regressed')
            previous,previous_time=row['sha256'],row['now_ts']
    return records


def record(sequence=2930):
    return deepcopy(_corpus()[sequence])


def typed_intent(raw):
    data=deepcopy(raw)
    data['side']=Side(data['side']) if data.get('side') else None
    data['lane'],data['action']=Lane(data['lane']),Action(data['action'])
    return ToolIntent(**data)


def typed_position(raw):
    data=deepcopy(raw)
    data['side'],data['lane']=Side(data['side']),Lane(data['lane'])
    for key in ('entry_price','cost','entry_fee_remaining','entry_time','close_ts',
                'peak_bid','floor_bid','trail_fraction','protected_peak_bid'):
        if data.get(key) is not None:
            data[key]=float(data[key])
    return PaperPosition(**data)


def book(data):
    raw=deepcopy(data['native_book'])
    for key in ('yes_bids','no_bids'):
        raw[key]=tuple(PriceLevel(**row) for row in raw[key])
    return PaperBook(**raw)


def snapshot(data):
    return snapshot_from_book(book(data),now_ts=data['now_ts'],metadata=data['physical_metadata'],
        ticker=data['market']['ticker'],close_ts=data['market']['close_ts'])


def held_inputs(sequence=2930,position_id='3'):
    data=record(sequence)
    position=typed_position(next(p for p in data['physical_metadata']['position_inventory']
        if p['position_id']==position_id))
    decision=next(d for d in data['decisions'] if d.get('position_id')==position_id)
    intents=tuple(typed_intent(i) for i in decision['tool_intents'])
    return data,snapshot(data),position,intents,decision


def _verified_component_journal(directory):
    previous='0'*64;rows=[];memory=io.BytesIO()
    with zipfile.ZipFile(memory,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for expected,path in enumerate(sorted((directory/'paper_journal').glob('*.json')),1):
            raw=path.read_bytes();row=json.loads(raw)
            digest=hashlib.sha256(canonical({k:v for k,v in row.items() if k!='sha256'})).hexdigest()
            if row['seq']!=expected or row['sha256']!=digest or row['previous_sha256']!=previous:
                raise ValueError('Isolated component journal integrity failure')
            previous=digest
            rows.append({'sequence':row['seq'],'kind':row['kind'],'sha256':digest,
                'original_account':False,'component_file':'paper_journal/'+path.name})
            archive.writestr('paper_journal/'+path.name,raw)
    return rows,memory.getvalue()


@lru_cache(maxsize=2)
def _floor_component(group_name):
    evidence=manifest();group=evidence['groups'][group_name];original_pid=group['position_id']
    entry=record(group['entry_sequence'])
    original_entry=next(d for d in entry['decisions'] if d['scope']=='ENTRY')
    command=original_entry['decision'];event=original_entry['receipt']['event']
    decision=CommanderDecision(Action(command['action']),typed_intent(command['intent']),command['reason'])
    trace=[];first_arm=None;first_breach=None;original_mark_mismatches=[]
    with tempfile.TemporaryDirectory(prefix='pid4824_floor_only_') as temporary:
        directory=Path(temporary)
        with PaperExecutioner(directory) as writer:
            receipt=writer.execute(decision,book(entry),now_ts=event['timestamp'],
                command_id='PID4824_ISOLATED_RECORDED_ENTRY_'+original_pid)
            if receipt.status!='BOOKED':
                raise ValueError('Recorded entry component failed: '+receipt.reason)
            for key in ('qty','price','cost','fees','timestamp','ticker','side'):
                if receipt.event[key]!=event[key]:
                    raise ValueError('Isolated component entry differs from original '+key)
            component_pid=receipt.position_id
            cash_after_entry=writer.snapshot()['cash']
            for sequence in group['ordered_sequences'][1:]:
                data,snap,original_position,intents,original_decision=held_inputs(sequence,original_pid)
                current=writer.positions[component_pid]
                # Preserve the original per-frame custody/adviser input while
                # carrying only the component's own monotonic floor mechanics.
                policy_position=replace(original_position,peak_bid=current.peak_bid,
                    floor_bid=current.floor_bid,protected_peak_bid=current.protected_peak_bid,
                    trail_fraction=current.trail_fraction,exit_required=current.exit_required,
                    exit_reason=current.exit_reason)
                policy=ToolRackPaperEngine._floor_policy(intents,policy_position,snap)
                observation=writer.observe_floors(book(data),now_ts=snap.now_ts,
                    policies={component_pid:policy},position_ids=(component_pid,))[0]
                observed=plain(observation)
                original=next(f for f in original_decision['floors'] if f['position_id']==original_pid)
                keys=('bid','peak_bid','floor_bid','armed','breached','reason','full_quantity_visible')
                different=[key for key in keys if observed[key]!=original[key]]
                if different:
                    original_mark_mismatches.append({'sequence':sequence,'fields':different})
                row={'sequence':sequence,'source':evidence['records'][str(sequence)],
                    'original_position_id':original_pid,'component_position_id':component_pid,
                    'original_custody_input':original_position.custody_state,
                    'policy':plain(policy),'floor_observation':observed,
                    'original_floor_observation':original}
                trace.append(row)
                if observation.armed and first_arm is None:first_arm=row
                if observation.breached:
                    first_breach=row
                    break
            state=writer.snapshot()
            if state['cash']!=cash_after_entry or len(writer.events)!=1:
                raise ValueError('Floor-only component unexpectedly booked economics')
            remaining=state['positions'][component_pid]
            if remaining['qty']!=event['qty'] or remaining['cost']!=event['cost']:
                raise ValueError('Floor component changed the original lot')
            journal_rows,journal_zip=_verified_component_journal(directory)
    report={'group':group_name,'scope':'ISOLATED_RECORDED_ENTRY_AND_FLOOR_ONLY_COMPONENT',
        'original_entry_event':event,'component_entry_event':receipt.event,
        'starting_component_cash':'1000.0','cash_after_entry':cash_after_entry,
        'cash_after_floor_observations':state['cash'],'component_event_count':1,
        'exit_executed':False,'whole_original_quantity':event['qty'],
        'source_steps_observed':len(trace),'first_arm':first_arm,'first_breach':first_breach,
        'trace':trace,'differences_from_original_floor_observations':original_mark_mismatches,
        'component_journal':journal_rows,
        'component_journal_sha256':hashlib.sha256(journal_zip).hexdigest(),
        'limits':evidence['limits']}
    return report,journal_zip


def floor_component(group_name,journal_zip_path=None):
    report,content=_floor_component(group_name)
    result=deepcopy(report)
    if journal_zip_path is not None:
        path=Path(journal_zip_path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
        result['component_journal_file']=path.name
    return result
