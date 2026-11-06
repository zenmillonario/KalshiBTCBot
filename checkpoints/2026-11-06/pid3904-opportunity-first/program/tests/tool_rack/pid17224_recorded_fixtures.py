"""Exact recorded PID17224 controls; snapshot reconstruction sees entry-time evidence only."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path

from strategy_core.paper_execution import PaperBook, PriceLevel
from strategy_core.paper_runtime import snapshot_from_book
from strategy_core.types import Action, Lane, Side, ToolIntent

PATH=Path(__file__).with_name('fixtures')/'pid17224_recorded_cases.json.gz'

@lru_cache(maxsize=1)
def _corpus():
    data=json.loads(gzip.decompress(PATH.read_bytes()))
    if data['schema']!='TACHYOS_PID17224_EXACT_RECORDED_CASES_V1':
        raise ValueError('Unexpected PID17224 control schema')
    for key,item in data['records'].items():
        record=dict(item['record']);expected=record.pop('sha256')
        actual=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        if actual!=expected or int(key)!=record['sequence']:
            raise ValueError('Recorded decision changed: '+key)
    return data

def record(sequence):
    return deepcopy(_corpus()['records'][str(sequence)]['record'])

def provenance(sequence):
    item=_corpus()['records'][str(sequence)]
    return {k:v for k,v in item.items() if k!='record'}

def book(sequence):
    data=record(sequence)['native_book']
    data['yes_bids']=tuple(PriceLevel(**row) for row in data['yes_bids'])
    data['no_bids']=tuple(PriceLevel(**row) for row in data['no_bids'])
    return PaperBook(**data)

def snapshot(sequence):
    data=record(sequence)
    return snapshot_from_book(book(sequence),now_ts=data['now_ts'],
        metadata=data['physical_metadata'],ticker=data['market']['ticker'],
        close_ts=data['market']['close_ts'])

def intent_from_dict(raw):
    data=deepcopy(raw)
    data['lane']=Lane(data['lane'])
    data['action']=Action(data['action'])
    data['side']=Side(data['side']) if data.get('side') is not None else None
    return ToolIntent(**data)

def intents(sequence,field='commander_intents'):
    return tuple(intent_from_dict(raw) for raw in record(sequence)['rack'].get(field) or [])

def entry_intent(sequence):
    rows=record(sequence)['decisions']
    raw=next(row['decision'].get('intent') for row in rows if row['scope']=='ENTRY')
    if raw is None:raise ValueError('Recorded ENTRY decision has no intent: '+str(sequence))
    return intent_from_dict(raw)

def journal_record(sequence):
    return deepcopy(_corpus()['journal'][str(sequence)])

def journal_state(sequence):
    return journal_record(sequence)['state']
