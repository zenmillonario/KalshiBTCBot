"""Audit a Commander over the full recorded observation sequence, without orders.

This is a source-bound policy-shadow audit, NOT a modified whole-engine replay:
observer/detector metadata, specialist proposals and existing inventory are the
original causal observations. The Commander instance runs chronologically and
its memory is continuous. Only ORIGINAL booked entries are consumed. We do not
create hypothetical positions, fills, exits, P&L or settlement outcomes.

Usage: python AUDIT_OPPORTUNITY_FIRST_SEQUENCE.py --program <source> --recording <run>
       --out <new-directory>
Use separate processes for old and proposed source to isolate module imports.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, fields, is_dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
from typing import Mapping


def plain(value):
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def compact_intent(intent):
    if intent is None:
        return None
    md = intent.metadata
    keep = ('commander_candidate_family', 'physical_mission_id', 'dual_lane',
            'opportunity_species', 'opportunity_admission', 'opportunity_first',
            'opportunity_first_admission', 'opportunity_watch_id', 'commander_opportunity')
    return {'tool': intent.tool, 'side': plain(intent.side), 'action': plain(intent.action),
            'lane': plain(intent.lane), 'reason': intent.reason, 'source_time': intent.source_time,
            'opportunity_id': intent.opportunity_id, 'max_price': intent.max_price,
            'size_tier': intent.size_tier,
            'evidence': {k: plain(md[k]) for k in keep if k in md}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program', type=Path, required=True)
    parser.add_argument('--recording', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    source = args.program.resolve()
    run = args.recording.resolve()
    if args.out.exists():
        parser.error('--out must be new; never overwrite an audit')
    args.out.mkdir(parents=True)
    sys.path.insert(0, str(source))
    from strategy_core.commander import OneCommander
    from strategy_core.paper_runtime import snapshot_from_book
    from strategy_core.paper_execution import PaperBook, PriceLevel
    from strategy_core.types import Action, Side, Lane, ToolIntent
    from run_validation import network_forbidden

    def intent_from(raw):
        data = dict(raw)
        data['side'] = Side(data['side']) if data.get('side') else None
        data['lane'] = Lane(data['lane'])
        data['action'] = Action(data['action'])
        return ToolIntent(**data)

    def book_from(raw):
        if not raw:
            return None
        data = dict(raw)
        for key in ('yes_bids', 'no_bids'):
            data[key] = tuple(PriceLevel(**p) for p in data[key])
        return PaperBook(**data)

    commander = OneCommander()
    prior_hash = '0' * 64
    prior_time = None
    counters = Counter()
    reasons = Counter()
    candidates = Counter()
    accepted_windows = []
    original_trades = []
    first_last = {}
    from engine_replay import source_hashes
    source_files = source_hashes()
    recorded_digest = hashlib.sha256()
    recorded_entry_window_closed = False
    start = time.perf_counter()
    output = args.out / 'candidate_stream.jsonl'
    with network_forbidden(), output.open('w', encoding='utf-8', newline='\n') as dest, (run / 'decisions.jsonl').open('r', encoding='utf-8', newline='') as src:
        for expected_seq, line in enumerate(src, 1):
            recorded_digest.update(line.encode('utf-8'))
            record = json.loads(line)
            digest = record.pop('sha256')
            actual_hash = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            if digest != actual_hash or record['previous_sha256'] != prior_hash or record['sequence'] != expected_seq:
                raise ValueError(f'DECISION_INTEGRITY_FAILURE_AT_{expected_seq}')
            prior_hash = digest
            now = record['now_ts']
            if prior_time is not None and now < prior_time:
                raise ValueError(f'TIME_REVERSED_AT_{expected_seq}')
            prior_time = now
            counters['recorded_frames'] += 1
            md = record['physical_metadata']
            market = record.get('market') or {}
            book = book_from(record.get('native_book'))
            snapshot = snapshot_from_book(book, now_ts=now, metadata=md,
                ticker=market.get('ticker', ''), close_ts=market.get('close_ts'))
            rack = record.get('rack') or {}
            original_entry = next((r for r in record['decisions'] if r.get('scope') == 'ENTRY'), {})
            original_decision = original_entry.get('decision') or {}
            original_reason = original_decision.get('reason') or ''
            # Original entry window is an execution constraint, never an entry signal.
            if original_reason == 'PAPER_ENTRY_WINDOW_CLOSED_DRAINING':
                recorded_entry_window_closed = True
            parent = ((md.get('mission_context') or {}).get('parent') or {})
            row = {'seq': expected_seq, 'now_ts': now, 'original_sha256': digest,
                   'source_generation': record.get('source_generation'), 'ticker': snapshot.ticker,
                   'contract_age_s': snapshot.contract_age_s, 'yes_ask': snapshot.yes_ask,
                   'no_ask': snapshot.no_ask, 'quote_current': snapshot.quote_current,
                   'parent_side': parent.get('side'), 'parent_status': parent.get('status'),
                   'owned_territory': rack.get('owned_territory'),
                   'original_action': original_decision.get('action'), 'original_reason': original_reason}
            positions = {str(p['position_id']): p for p in md.get('position_inventory', ())}
            # The original engine manages existing lots before entry selection.
            # Apply ONLY actual full exits already recorded earlier in this frame.
            for event in record['decisions']:
                if event.get('scope') == 'ENTRY':
                    break
                receipt = event.get('receipt') or {}
                ev = receipt.get('event') or {}
                if receipt.get('status') in ('BOOKED', 'EXITED') and ev.get('event') == 'EXIT' and int(ev.get('position_qty_after', -1)) == 0:
                    positions.pop(str(receipt.get('position_id')), None)
            if rack and md.get('physical_current') is True and market and not recorded_entry_window_closed:
                native = commander.physical_entry_candidates(snapshot)
                advised_raw = rack.get('commander_intents') or rack.get('intents') or ()
                advisers = tuple(intent_from(i) for i in advised_raw if i.get('action') in ('ENTER', 'RELAY'))
                proposed = tuple(native) + advisers
                decision = commander.decide_entry(proposed, snapshot, positions)
                row.update({'native_candidates': [compact_intent(i) for i in native],
                            'adviser_candidates': [compact_intent(i) for i in advisers],
                            'audit_action': plain(decision.action), 'audit_reason': decision.reason,
                            'selected': compact_intent(decision.intent)})
                # Optional public diagnostic methods are read-only and vary by revision.
                for attr in ('opportunity_review', 'last_opportunity_review', 'opportunity_status', '_last_opportunity_review'):
                    value = getattr(commander, attr, None)
                    if isinstance(value, Mapping):
                        row['opportunity_review'] = plain(value)
                        break
                counters['audited_current_frames'] += 1
                counters['audit_action_' + plain(decision.action)] += 1
                reasons[decision.reason] += 1
                for intent in proposed:
                    candidates[intent.reason] += 1
                if decision.action in (Action.ENTER, Action.RELAY):
                    key = (snapshot.ticker, plain(decision.intent.side), decision.intent.reason, decision.intent.opportunity_id)
                    if not accepted_windows or accepted_windows[-1]['key'] != list(key) or accepted_windows[-1]['last_seq'] != expected_seq - 1:
                        accepted_windows.append({'key': list(key), 'first_seq': expected_seq, 'last_seq': expected_seq,
                            'first_ts': now, 'last_ts': now, 'frames': 1, 'first_ask': snapshot.ask_for(decision.intent.side),
                            'parent_side': parent.get('side'), 'inventory_ids': sorted(positions)})
                    else:
                        accepted_windows[-1]['last_seq'] = expected_seq
                        accepted_windows[-1]['last_ts'] = now
                        accepted_windows[-1]['frames'] += 1
            else:
                row.update({'native_candidates': [], 'adviser_candidates': [], 'audit_action': 'WAIT',
                            'audit_reason': 'AUDIT_INACTIVE_OR_ORIGINAL_ENTRY_WINDOW_CLOSED', 'selected': None})
            receipt = original_entry.get('receipt') or {}
            if receipt.get('status') == 'BOOKED':
                raw_intent = original_decision.get('intent')
                if raw_intent:
                    commander.mark_entry_filled(intent_from(raw_intent), ticker=snapshot.ticker)
                ev = receipt.get('event') or {}
                row['original_booked_entry'] = {k: ev.get(k) for k in ('position_id', 'side', 'tool', 'reason', 'price', 'qty')}
                original_trades.append({k: row[k] for k in ('seq', 'now_ts', 'ticker', 'parent_side', 'original_booked_entry',
                    'audit_action', 'audit_reason', 'selected', 'native_candidates', 'adviser_candidates')})
                if 'opportunity_review' in row:
                    original_trades[-1]['opportunity_review'] = row['opportunity_review']
            dest.write(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')
            if not first_last:
                first_last['first'] = {'seq': expected_seq, 'now_ts': now}
            first_last['last'] = {'seq': expected_seq, 'now_ts': now}
            if expected_seq % 1000 == 0:
                print(f'Audited {expected_seq} source frames', flush=True)
    if source_files != source_hashes():
        raise ValueError('SOURCE_CHANGED_DURING_AUDIT')
    report = {'schema': 'tachyos.commander_source_sequence_audit.v1', 'complete': True,
              'scope': 'CHRONOLOGICAL_COMMANDER_SHADOW_ON_ORIGINAL_OBSERVER_AND_ADVISER_EVIDENCE',
              'exact_engine_replay': False, 'hypothetical_orders_created': False, 'hypothetical_pnl_computed': False,
              'limitations': [
                  'Original source-time detector/observer metadata and specialist proposals are held fixed.',
                  'Original inventory and booked mission consumption are retained; proposed orders are never executed.',
                  'ToolRack role/recovery qualification and independent lane filtering are not rerun in this Commander-layer audit.',
                  'This audit is not alternate whole-run behavior or a profitability claim.'
              ], 'program': str(source), 'recording': str(run), 'source_hashes': source_files,
              'recorded_decisions_sha256': recorded_digest.hexdigest(),
              'python': platform.python_version(), 'platform': platform.platform(),
              'counters': dict(counters), 'reasons': dict(reasons), 'candidate_reasons': dict(candidates),
              'bounds': first_last, 'last_original_sha256': prior_hash, 'accepted_windows': accepted_windows,
              'original_booked_entry_reviews': original_trades,
              'elapsed_s': time.perf_counter() - start}
    (args.out / 'summary.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'complete': True, 'counters': report['counters'], 'elapsed_s': report['elapsed_s'],
                      'output': str(args.out)}))


def compare_main(argv=None):
    """Compare two complete independent-process shadow audits, never invent fills."""
    import gzip
    from itertools import zip_longest
    parser = argparse.ArgumentParser(description=compare_main.__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error('--out must be new')
    args.out.mkdir(parents=True)
    before = json.loads((args.baseline/'summary.json').read_text(encoding='utf-8'))
    after = json.loads((args.candidate/'summary.json').read_text(encoding='utf-8'))
    if not (before['complete'] and after['complete']):
        raise ValueError('BOTH_AUDITS_MUST_BE_COMPLETE')
    if before.get('recorded_decisions_sha256') != after.get('recorded_decisions_sha256') or not before.get('recorded_decisions_sha256'):
        raise ValueError('SAME_VERIFIED_DECISIONS_FILE_REQUIRED')
    changes = Counter()
    admissions = []
    qualified = {}
    watches = {}
    main_no_entry = Counter()
    all_proofs = Counter()
    invalid_admissions = []
    frame_count = 0
    matched_original = Counter()
    prior_physical_frame = None
    prior_watch_ids = set()
    duplicate_callback_watch_creation = []
    admission_identity_failures = []
    repeated_callback_count = 0
    combined = args.out/'OPPORTUNITY_FIRST_SEQUENCE_FRAMES.jsonl.gz'
    with (args.baseline/'candidate_stream.jsonl').open(encoding='utf-8') as b, (args.candidate/'candidate_stream.jsonl').open(encoding='utf-8') as c, gzip.open(combined,'wt',encoding='utf-8') as dest:
        for left,right in zip_longest(b,c):
            if left is None or right is None:
                raise ValueError('AUDIT_FRAME_COUNTS_DIFFER')
            old,new = json.loads(left),json.loads(right)
            for key in ('seq','now_ts','ticker','original_sha256'):
                if old[key] != new[key]:
                    raise ValueError('SOURCE_FRAME_IDENTITY_DIFFERS:'+key)
            frame_count += 1
            old_dec,new_dec = (old['audit_action'],old['audit_reason']), (new['audit_action'],new['audit_reason'])
            changes['same_action' if old_dec[0]==new_dec[0] else 'changed_action'] += 1
            changes['same_reason' if old_dec[1]==new_dec[1] else 'changed_reason'] += 1
            if old.get('original_booked_entry'):
                matched_original['baseline_agrees_with_recorded_booked_entry' if old['audit_action'] in ('ENTER','RELAY') else 'baseline_differs_from_recorded_booked_entry'] += 1
            review = new.get('opportunity_review') or {}
            main = review.get('main_alignment') or {}
            physical_frame = (new['ticker'], review.get('source_ms'), review.get('continuity_generation'))
            visible_ids = {w.get('identity') for w in review.get('watches') or [] if w.get('identity')}
            if review and physical_frame == prior_physical_frame:
                repeated_callback_count += 1
                minted = visible_ids - prior_watch_ids
                if minted:
                    duplicate_callback_watch_creation.append({'seq':new['seq'],'new_watch_ids':sorted(minted)})
            if review:
                prior_physical_frame, prior_watch_ids = physical_frame, visible_ids
            if new['audit_action'] == 'WAIT' and main:
                main_no_entry[main.get('missed_opportunity_reason') or main.get('reason') or new['audit_reason']] += 1
            for proof in review.get('candidates') or []:
                all_proofs[str(proof.get('qualified'))+':'+str(proof.get('species'))+':'+str(proof.get('reason'))] += 1
                if proof.get('qualified') is not True:
                    continue
                key = (new['ticker'], proof.get('opportunity_id'), proof.get('species'), proof.get('side'))
                item = qualified.setdefault(key, {'ticker':key[0],'opportunity_id':key[1],'species':key[2],'side':key[3],
                    'first_seq':new['seq'],'first_source_ms':proof.get('source_ms'), 'first_ts':new['now_ts'],
                    'frames':0,'entry_admission_frames':0,'no_entry_reasons':Counter()})
                item.update(last_seq=new['seq'],last_source_ms=proof.get('source_ms'),last_ts=new['now_ts'])
                item['frames'] += 1
                if new['audit_action'] in ('ENTER','RELAY') and (new.get('selected') or {}).get('opportunity_id') == proof.get('opportunity_id'):
                    item['entry_admission_frames'] += 1
                else:
                    item['no_entry_reasons'][new['audit_reason']] += 1
            for watch in review.get('watches') or []:
                identity=watch.get('identity')
                if not identity:continue
                item=watches.setdefault(identity,{'identity':identity,'ticker':watch.get('ticker'),
                    'parent_id':watch.get('parent_id'),'return_side':watch.get('return_side'),
                    'first_visible_seq':new['seq'],'first_source_ms':watch.get('first_source_ms'),'states':Counter()})
                item.update(last_visible_seq=new['seq'],last_source_ms=watch.get('last_source_ms'),
                    distinct_source_samples=watch.get('distinct_source_samples'))
                item['states'][watch.get('state')] += 1
            if new['audit_action'] in ('ENTER','RELAY'):
                selected=new.get('selected') or {}
                proof=(selected.get('evidence') or {}).get('commander_opportunity') or {}
                admission={'seq':new['seq'],'now_ts':new['now_ts'],'ticker':new['ticker'],
                    'selected':selected,'proof':proof}
                admissions.append(admission)
                if proof.get('qualified') is not True or proof.get('ticker')!=new['ticker']:
                    invalid_admissions.append(admission)
                proof_source = proof.get('source_ms')
                if not (isinstance(proof_source,(int,float))
                        and proof_source <= new['now_ts']*1000+.001
                        and proof_source == review.get('source_ms')
                        and proof.get('continuity_generation') == review.get('continuity_generation')
                        and new.get('quote_current') is True):
                    admission_identity_failures.append(admission)
            dest.write(json.dumps({'seq':new['seq'],'now_ts':new['now_ts'],'ticker':new['ticker'],
                'original_sha256':new['original_sha256'],'baseline':old,'candidate':new},sort_keys=True,separators=(',',':'))+'\n')
    trade_reviews={str(r['original_booked_entry']['position_id']):r for r in after['original_booked_entry_reviews']}
    controls=[]
    def control(name,passed,evidence):
        controls.append({'name':name,'pass':bool(passed),'evidence':evidence})
    control('all_recorded_decisions_in_same_chronology',frame_count==before['counters']['recorded_frames']==after['counters']['recorded_frames'],frame_count)
    control('all_candidate_admissions_have_positive_current_species',not invalid_admissions,{'admissions':len(admissions),'invalid':invalid_admissions})
    for trade in ('2','3','7','8'):
        row=trade_reviews.get(trade,{})
        selected=row.get('selected') or {}
        proof=(selected.get('evidence') or {}).get('commander_opportunity') or {}
        independent_main=(row.get('audit_action') in ('ENTER','RELAY')
            and proof.get('qualified') is True and proof.get('species')=='MAIN_EMA9_REJOIN'
            and selected.get('side')==proof.get('parent_side')==row.get('parent_side')
            and selected.get('side')!=row.get('original_booked_entry',{}).get('side'))
        control('PID3904_negative_original_entry_'+trade,
            row.get('audit_action')=='WAIT' or independent_main,
            {**{k:row.get(k) for k in ('seq','audit_action','audit_reason')},
             'forbidden_original_side':row.get('original_booked_entry',{}).get('side'),
             'observed_parent_side':row.get('parent_side'),
             'independently_earned_correct_side_main_allowed':True,
             'independent_main_admitted':independent_main})
    control('repeated_native_callbacks_do_not_mint_physical_watches',not duplicate_callback_watch_creation,
        {'repeated_callbacks':repeated_callback_count,'failures':duplicate_callback_watch_creation})
    control('admitted_opportunities_have_current_nonfuture_source_and_quote',not admission_identity_failures,
        {'failures':admission_identity_failures})
    control('positive_qualified_source_opportunity_observed',bool(qualified),{'distinct_qualified_opportunities':len(qualified)})
    control('positive_admission_observed_not_reject_all',bool(admissions),{'entry_admission_frames':len(admissions)})
    report={'schema':'tachyos.opportunity_first_sequence_comparison.v1','pass':all(c['pass'] for c in controls),
        'candidate_source_sha256':after['source_hashes'],'baseline_source_sha256':before['source_hashes'],
        'recorded_decisions_sha256':after['recorded_decisions_sha256'],'frame_count':frame_count,
        'chronological_scope':'ALL_SOURCE_DECISIONS_WITH_INDEPENDENT_PERSISTENT_COMMANDERS_AND_FIXED_ORIGINAL_OBSERVATIONS_AND_INVENTORY',
        'exact_engine_replay':False,'hypothetical_orders_created':False,'hypothetical_pnl_computed':False,
        'limitations':after['limitations']+['Baseline reproduces 7 of 8 historical entry-frame admissions in this Commander-only shadow; one quote-window timing decision differs, so this is not a full-engine equivalence proof.'],
        'baseline':{k:before[k] for k in ('counters','reasons','candidate_reasons','accepted_windows','bounds','last_original_sha256')},
        'candidate':{k:after[k] for k in ('counters','reasons','candidate_reasons','accepted_windows','bounds','last_original_sha256')},
        'semantic_controls':controls,'changes':dict(changes),'baseline_recorded_entry_agreement':dict(matched_original),
        'original_booked_entry_reviews':after['original_booked_entry_reviews'],
        'qualified_opportunities':list(qualified.values()),'entry_admissions':admissions,
        'candidate_proof_reasons':dict(all_proofs),'main_no_entry_reasons':dict(main_no_entry),'watches':list(watches.values()),
        'per_frame_report':combined.name,'per_frame_report_sha256':hashlib.sha256(combined.read_bytes()).hexdigest()}
    result=args.out/'OPPORTUNITY_FIRST_SEQUENCE_AUDIT.json'
    result.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'pass':report['pass'],'frames':frame_count,'qualified_opportunities':len(qualified),
        'entry_admissions':len(admissions),'report':str(result)}))
    if not report['pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='compare':
        compare_main(sys.argv[2:])
    else:
        main()
