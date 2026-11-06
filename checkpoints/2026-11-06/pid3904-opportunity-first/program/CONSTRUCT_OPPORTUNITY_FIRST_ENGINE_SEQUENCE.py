"""Run a fresh modified PAPER engine over every verified historical engine call.

This is a chronological offline Construct, NOT an exact replay.  The recording
was made by a different source version/environment.  Every captured feed/book
argument is decoded unchanged.  Modified decisions can change internal state,
inventory and custody.  The existing tested conservative PAPER depth model is
used; model fills are not venue fills, and this report makes no profit claim.

The exact original replay API is not modified or bypassed.  This separate
experiment verifies the tape against its original source hashes before any
engine is constructed, then dispatches all calls to a fresh candidate engine.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import sys
import time


def source_hashes_at(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root/'strategy_core').rglob('*'))
            if p.is_file() and p.suffix in ('.py','.json','.html','.css','.js')}


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1024*1024),b''):
            digest.update(data)
    return digest.hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--program',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--recording',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists():p.error('--out must be new')
    program,baseline,recording=a.program.resolve(),a.baseline.resolve(),a.recording.resolve()
    expected=json.loads((baseline/'SOURCE_SHA256.json').read_text(encoding='utf-8'))
    if source_hashes_at(baseline)!=expected:raise ValueError('BASELINE_SOURCE_SEALS_MISMATCH')
    candidate=source_hashes_at(program)
    driver_path=Path(__file__).resolve()
    driver_digest=sha(driver_path)
    sys.path.insert(0,str(program))
    from bounded_tape import iter_tape
    from engine_replay import runtime_clock,ClockProxy,ScriptClock,source_hashes
    from strategy_core.paper_runtime import ToolRackPaperEngine
    from strategy_core.paper_execution import PaperExecutioner
    from run_validation import network_forbidden
    if source_hashes()!=candidate:raise ValueError('WRONG_CANDIDATE_IMPORT')
    start=time.perf_counter()
    a.out.mkdir(parents=True)
    tape=recording/'replay_capture/engine_inputs.jsonl'
    print('Verifying complete original tape and source before engine instantiation',flush=True)
    header,calls=iter_tape(tape,expected_source_hashes=expected)
    verified=time.perf_counter()
    print('Complete original tape verified; starting source-time candidate Construct',flush=True)
    counters=Counter();engine=None;last_base=None;trace_sha=hashlib.sha256()
    run_dir=a.out/header['run_id']
    error=None;finished=False
    try:
        with network_forbidden(),(a.out/'engine_call_trace.jsonl').open('w',encoding='utf-8',newline='\n') as trace:
            for index,envelope in enumerate(calls,1):
                call=envelope['call'];method=call['method'];arguments=call['arguments']
                # Authored deterministic clock, explicitly separate from exact
                # recorded clock-tape replay when branch/read count changes.
                stamps=envelope['clocks']
                base=(float(stamps[0]) if stamps else float(arguments.get('now_ts',last_base or 0)))
                clock=ScriptClock(base,increment=.00001)
                if last_base is not None and base<last_base:raise ValueError('SOURCE_DISPATCH_TIME_REVERSED')
                last_base=base
                with runtime_clock(ClockProxy(clock)):
                    if method=='init':engine=ToolRackPaperEngine(run_dir,source_root=program)
                    elif method in ('process','settle','close') and engine is not None:
                        getattr(engine,method)(**arguments)
                    else:raise ValueError('INVALID_CALL_LIFECYCLE')
                row={'call_index':index,'method':method,'source_clock_base':base,
                    'source_now_ts':arguments.get('now_ts'),'original_clock_reads':len(stamps),
                    'construct_clock_reads':clock.reads,'original_decision_seq':envelope['expected']['decision_seq'],
                    'construct_decision_seq':engine._seq,'construct_journal_seq':engine.executor._seq}
                if row['original_decision_seq']!=row['construct_decision_seq']:
                    raise ValueError('ORIGINAL_TO_CONSTRUCT_DECISION_SEQUENCE_IDENTITY_DIVERGED')
                text=json.dumps(row,sort_keys=True,separators=(',',':'))+'\n'
                trace.write(text);trace_sha.update(text.encode())
                counters[method]+=1
                if index%500==0:print(f'Constructed {index} calls in {time.perf_counter()-verified:.1f}s',flush=True)
            finished=True
    except Exception as exc:
        error={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        calls.close()
        if engine is not None and not engine.executor._closed:
            with runtime_clock(ClockProxy(lambda:last_base or 0.0)):
                engine.close(reason='INCOMPLETE_OFFLINE_CONSTRUCT_NOT_ACCEPTED')
        unchanged=source_hashes_at(program)==candidate
        driver_unchanged=sha(driver_path)==driver_digest
        report={'schema':'tachyos.opportunity_first_engine_construct.v1','complete':finished,
            'scope':'CHRONOLOGICAL_MODIFIED_ENGINE_CONSTRUCT','exact_engine_replay':False,
            'source_time_clock':'First original per-call clock value; each engine read advances 10us. No original clock-count equivalence claimed.',
            'actual_captured_feed_book_arguments_unchanged':True,
            'fresh_candidate_engine_and_inventory':True,'hypothetical_model_fills_possible':True,
            'execution_model':'Existing conservative integer native-depth PAPER model; never venue fills.',
            'profit_claim':False,'source_changed_during_construct':not unchanged,
            'construct_driver_sha256':driver_digest,'driver_changed_during_construct':not driver_unchanged,
            'baseline_source_sha256':expected,'candidate_source_sha256':candidate,
            'recorded_decisions_sha256':sha(recording/'decisions.jsonl'),
            'program':str(program),'baseline':str(baseline),'recording':str(recording),
            'recorded_tape_sha256':sha(tape),'recorded_python':header.get('python'),
            'recorded_platform':header.get('platform'),'construct_python':platform.python_version(),
            'construct_platform':platform.platform(),'call_count':sum(counters.values()),'method_counts':dict(counters),
            'trace_sha256':trace_sha.hexdigest(),'source_run':header['run_id'],'run_dir':str(run_dir),
            'verification_seconds':verified-start,'execution_seconds':time.perf_counter()-verified,
            'error':error,'limitations':['Modified source and authored clock preclude exact historical replay equivalence.',
                'Paper depth sweeps are modeled; live matching, latency and venue fills are not validated.',
                'The captured feed is fixed and cannot respond to hypothetical strategy actions.',
                'No simulated or alternate net profit is reported as an actual result.']}
        if finished and unchanged:
            journal=PaperExecutioner.inspect_journal(run_dir)
            report['journal_integrity']={k:journal.get(k) for k in ('records','sha256','pass') if k in journal}
        (a.out/'OPPORTUNITY_FIRST_ENGINE_CONSTRUCT.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    if not unchanged:raise ValueError('CANDIDATE_SOURCE_CHANGED_DURING_CONSTRUCT')
    if not driver_unchanged:raise ValueError('CONSTRUCT_DRIVER_CHANGED_DURING_EXECUTION')
    print(json.dumps({'complete':True,'calls':sum(counters.values()),'out':str(a.out)}))


def inspect_construct(argv=None):
    """Add semantic acceptance to a complete Construct; never report model P&L."""
    p=argparse.ArgumentParser(description=inspect_construct.__doc__)
    p.add_argument('--construct',type=Path,required=True)
    p.add_argument('--program',type=Path,required=True)
    p.add_argument('--recording',type=Path,required=True)
    a=p.parse_args(argv)
    receipt=a.construct/'OPPORTUNITY_FIRST_ENGINE_CONSTRUCT.json'
    report=json.loads(receipt.read_text(encoding='utf-8'))
    if (not report['complete'] or report['error'] or report['source_changed_during_construct']
            or report.get('driver_changed_during_construct') is True):
        raise ValueError('COMPLETE_STABLE_SOURCE_AND_DRIVER_CONSTRUCT_REQUIRED')
    if report.get('construct_driver_sha256')!=sha(Path(__file__).resolve()):
        raise ValueError('CONSTRUCT_DRIVER_CHANGED_SINCE_EXECUTION')
    if source_hashes_at(a.program.resolve())!=report['candidate_source_sha256']:
        raise ValueError('CANDIDATE_SOURCE_CHANGED_SINCE_CONSTRUCT')
    original_decisions_sha=sha(a.recording/'decisions.jsonl')
    if report.get('recorded_decisions_sha256',original_decisions_sha)!=original_decisions_sha:
        raise ValueError('ORIGINAL_DECISIONS_CHANGED_SINCE_CONSTRUCT')
    report['recorded_decisions_sha256']=original_decisions_sha
    if sha(a.recording/'replay_capture/engine_inputs.jsonl')!=report['recorded_tape_sha256']:
        raise ValueError('ORIGINAL_TAPE_CHANGED_SINCE_CONSTRUCT')
    if sha(a.construct/'engine_call_trace.jsonl')!=report['trace_sha256']:
        raise ValueError('CONSTRUCT_TRACE_CHANGED')
    run=Path(report['run_dir'])
    from itertools import zip_longest
    actions=Counter();custody=Counter();species=Counter();admitted=[];model_entries=[];model_exits=[]
    source_mismatches=[];unqualified=[];negatives={2932:None,3192:None,6295:None,6466:None};frames=0
    original_bad_sides={2932:'NO',3192:'NO',6295:'YES',6466:'YES'}
    previous_hashes=['0'*64,'0'*64]
    source_bounds={}
    with (a.recording/'decisions.jsonl').open(encoding='utf-8') as old,(run/'decisions.jsonl').open(encoding='utf-8') as new:
        for left,right in zip_longest(old,new):
            if left is None or right is None:raise ValueError('SOURCE_CONSTRUCT_FRAME_COUNTS_DIFFER')
            before,after=json.loads(left),json.loads(right);frames+=1
            if frames==1:source_bounds['first']={'sequence':before['sequence'],'now_ts':before['now_ts']}
            source_bounds['last']={'sequence':before['sequence'],'now_ts':before['now_ts']}
            for record_index,record in enumerate((before,after)):
                payload={k:v for k,v in record.items() if k!='sha256'}
                digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()
                if digest!=record['sha256'] or record['previous_sha256']!=previous_hashes[record_index] or record['sequence']!=frames:
                    raise ValueError('DECISION_CHAIN_FAILURE_AT_'+str(frames)+'_STREAM_'+str(record_index))
                previous_hashes[record_index]=digest
            bgeo=before.get('physical_metadata',{}).get('current_geometry',{})
            ageo=after.get('physical_metadata',{}).get('current_geometry',{})
            identity={key:after.get(key)==before.get(key) for key in ('sequence','now_ts','source_generation')}
            identity['physical_source_epoch']=bgeo.get('epoch_ms')==ageo.get('epoch_ms')
            identity['complete_current_geometry']=bgeo==ageo
            identity['market']=before.get('market')==after.get('market')
            identity['native_book']=before.get('native_book')==after.get('native_book')
            if not all(identity.values()):source_mismatches.append({'seq':frames,'identity':identity})
            for row in after['decisions']:
                d=row.get('decision') or {};r=row.get('receipt') or {};event=r.get('event') or {};intent=d.get('intent') or {}
                if row.get('scope')=='ENTRY':
                    actions[d.get('action')]+=1
                    if frames in negatives:
                        proof=(intent.get('metadata') or {}).get('commander_opportunity') or {}
                        parent_side=(((after.get('physical_metadata') or {}).get('mission_context') or {}).get('parent') or {}).get('side')
                        independent_main=(d.get('action') in ('ENTER','RELAY')
                            and proof.get('qualified') is True and proof.get('species')=='MAIN_EMA9_REJOIN'
                            and intent.get('side')==proof.get('parent_side')==parent_side
                            and intent.get('side')!=original_bad_sides[frames])
                        negatives[frames]={'action':d.get('action'),'reason':d.get('reason'),'intent_reason':intent.get('reason'),
                            'side':intent.get('side'),'observed_parent_side':parent_side,'species':proof.get('species'),
                            'forbidden_original_side':original_bad_sides[frames],
                            'independently_earned_correct_side_main_allowed':True,'independent_main_admitted':independent_main}
                    if d.get('action') in ('ENTER','RELAY'):
                        proof=(intent.get('metadata') or {}).get('commander_opportunity') or {}
                        detail={'seq':frames,'source_ts':after['now_ts'],'ticker':(after.get('market') or {}).get('ticker'),
                            'action':d.get('action'),'reason':intent.get('reason'),'side':intent.get('side'),
                            'species':proof.get('species'),'qualified':proof.get('qualified'),
                            'parent_side':proof.get('parent_side'),'proof_source_ms':proof.get('source_ms')}
                        admitted.append(detail);species[proof.get('species')]+=1
                        if proof.get('qualified') is not True:unqualified.append(detail)
                elif row.get('scope')=='POSITION':custody[intent.get('reason') or d.get('reason')]+=1
                if event.get('event')=='ENTRY':
                    model_entries.append({'source_seq':frames,'position_id':event.get('position_id'),
                        'ticker':event.get('ticker'),'side':event.get('side'),'reason':event.get('reason'),
                        'quantity':event.get('qty'),'venue_fill_claim':event.get('venue_fill_claim')})
                elif event.get('event')=='EXIT':
                    model_exits.append({'source_seq':frames,'position_id':event.get('position_id'),
                        'reason':event.get('reason'),'quantity':event.get('qty'),
                        'remaining':event.get('position_qty_after'),'venue_fill_claim':event.get('venue_fill_claim')})
    ending_ledger=json.loads((run/'PAPER_LEDGER.json').read_text(encoding='utf-8'))
    ending_positions=[{key:position.get(key) for key in ('position_id','ticker','side','qty','position_role','custody_state')}
        for position in ending_ledger.get('positions',{}).values()]
    settlement_coverage={'recorded_settlement_calls':report['method_counts'].get('settle',0),
        'ending_model_position_count':len(ending_positions),
        'invented_settlement_or_liquidation':False}
    if ending_positions and not settlement_coverage['recorded_settlement_calls']:
        limitation=('The captured tape contains no settlement calls. Ending modeled inventory remains '
            'unsettled; no terminal liquidation, settlement result, or final counterfactual P&L is invented.')
        if limitation not in report['limitations']:report['limitations'].append(limitation)
    checks=[]
    def check(name,ok,evidence):checks.append({'name':name,'pass':bool(ok),'evidence':evidence})
    check('all_original_calls_executed',report['method_counts']=={'init':1,'process':6963,'close':1},report['method_counts'])
    check('all_source_frame_identities_preserved',frames==6963 and not source_mismatches,{'frames':frames,'mismatches':source_mismatches})
    check('fresh_model_sequence_has_positive_admission',bool(admitted),{'admission_frames':len(admitted),'species':dict(species)})
    check('every_entry_has_positive_commander_species',not unqualified,{'failures':unqualified})
    for seq,result in negatives.items():
        check('original_negative_source_frame_'+str(seq),
            result and (result['action']=='WAIT' or result['independent_main_admitted']),result)
    check('fresh_inventory_and_custody_exercised',bool(model_entries) and bool(model_exits) and bool(custody),
        {'model_entries':len(model_entries),'model_exits':len(model_exits),'custody_reviews':sum(custody.values())})
    check('whole_lot_model_exits',all(e['remaining']==0 for e in model_exits),{'model_exits':len(model_exits)})
    check('no_venue_fill_claim',all(e['venue_fill_claim'] is False for e in model_entries+model_exits),{'model_entries':len(model_entries),'model_exits':len(model_exits)})
    report.update(pass_semantic=all(c['pass'] for c in checks),semantic_controls=checks,
        frame_count=frames,source_bounds=source_bounds,entry_actions=dict(actions),custody_reasons=dict(custody),
        model_ending_positions=ending_positions,settlement_coverage=settlement_coverage,forced_hypothetical_liquidation=False,
        original_decision_chain_sha256=previous_hashes[0],construct_decision_chain_sha256=previous_hashes[1],
        construct_decisions_sha256=sha(run/'decisions.jsonl'),
        species_admissions=dict(species),entry_admissions=admitted,model_entries=model_entries,
        model_exits=model_exits)
    receipt.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'pass_semantic':report['pass_semantic'],'frames':frames,
        'admission_frames':len(admitted),'model_entries':len(model_entries),'model_exits':len(model_exits)}))
    if not report['pass_semantic']:
        raise SystemExit(1)


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='inspect':inspect_construct(sys.argv[2:])
    else:main()
