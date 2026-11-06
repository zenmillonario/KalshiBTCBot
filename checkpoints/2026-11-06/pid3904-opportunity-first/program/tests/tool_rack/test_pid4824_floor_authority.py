"""PID4824 current-parent floor binding and preserved original controls.

Original records and ordered floor-only components are distinct from synthetic
source/direction/Release variants. No test claims an alternative full run.
"""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import hashlib
from pathlib import Path
import tempfile
import unittest

from strategy_core.commander import CommanderDecision
from strategy_core.commander_candidates import ema9_continuation_precedent
from strategy_core.dual_lane import _current_mission_parent
from strategy_core.paper_execution import PaperExecutioner, PriceLevel, nominal_taker_fee
from strategy_core.paper_runtime import ToolRackPaperEngine, plain
from strategy_core.tools.management import entry_candle_evidence
from strategy_core.types import Action, Side
from tests.tool_rack.pid4824_floor_fixtures import (
    book, floor_component, held_inputs, manifest, record, typed_intent,
)


def variant(snapshot, mutate):
    """Explicit synthetic metadata variation; original records stay unchanged."""
    md=deepcopy(snapshot.metadata);mutate(md)
    return replace(snapshot,metadata=md)


class PID4824OriginalFloorEvidenceTests(unittest.TestCase):
    def test_complete_original_records_and_ordered_intervals_are_bound(self):
        evidence=manifest()
        self.assertEqual(len(evidence['record_order']),305)
        self.assertEqual(evidence['groups']['trade3_floor_only']['ordered_sequences'],list(range(2856,2935)))
        self.assertEqual(evidence['groups']['trade5_original_positive']['ordered_sequences'],list(range(6756,6979)))
        self.assertEqual(record(2930)['sha256'],evidence['records']['2930']['decision_sha256'])

    def test_original_peak_is_current_whole_lot_profit_under_opposing_parent(self):
        _,snapshot,position,_,decision=held_inputs()
        parent=_current_mission_parent(snapshot)
        self.assertEqual((parent['id'],parent['side']),('P000L000002','NO'))
        self.assertIs(position.side,Side.YES)
        self.assertEqual(position.qty,788)
        mark=next(f for f in decision['floors'] if f['position_id']=='3')
        self.assertTrue(mark['full_quantity_visible'])
        self.assertEqual(mark['bid'],.08)
        self.assertFalse(mark['armed'])
        self.assertAlmostEqual(snapshot.now_ts-position.entry_time,23.88040280342102)
        net=Decimal('0.08')*788-Decimal(str(position.cost))-Decimal(str(position.entry_fee_remaining))-nominal_taker_fee(788,Decimal('.08'))
        self.assertEqual(net,Decimal('33.9864'))

    def test_real_local_continuation_is_retained_without_parent_floor_authority(self):
        _,snapshot,position,intents,_=held_inputs()
        evidence=ema9_continuation_precedent(snapshot)
        self.assertTrue(evidence['qualified'])
        self.assertEqual(evidence['side'],'YES')
        self.assertTrue(evidence['current_motion_supports'])
        self.assertTrue(evidence['direct_arc_support'])
        self.assertEqual(snapshot.metadata['release_candidate_side'],'NO')
        policy=ToolRackPaperEngine._floor_policy(intents,position,snapshot)
        self.assertEqual((policy.arm_roi,policy.immediate_arm_roi),(1.,1.5))
        original=next(p for p in manifest()['original_policy_probes'] if p['source']['sequence']==2930)
        self.assertEqual(original['captured_policy_component']['immediate_arm_roi'],2.)
        self.assertEqual(ema9_continuation_precedent(snapshot),evidence)

    def test_immediate_150_protection_does_not_require_30_seconds_or_next_candle(self):
        _,snapshot,position,intents,decision=held_inputs(2927)
        policy=ToolRackPaperEngine._floor_policy(intents,position,snapshot)
        self.assertFalse(entry_candle_evidence(plain(position),snapshot)['entry_candle_complete'])
        self.assertFalse(policy.first_arm_allowed)
        self.assertLess(snapshot.now_ts-position.entry_time,30.)
        bid=Decimal(str(next(f for f in decision['floors'] if f['position_id']=='3')['bid']))
        self.assertGreaterEqual(bid/Decimal(str(position.entry_price))-1,Decimal(str(policy.immediate_arm_roi)))
        self.assertEqual(policy.immediate_arm_roi,1.5)

    def test_ordered_original_lot_arms_then_triggers_only_on_available_later_bid(self):
        result=floor_component('trade3_floor_only')
        first,last=result['first_arm'],result['first_breach']
        self.assertEqual([r['sequence'] for r in result['trace']],list(range(2857,2935)))
        self.assertEqual(first['sequence'],2927)
        self.assertEqual((first['floor_observation']['bid'],first['floor_observation']['floor_bid']),(.077,.07469))
        self.assertEqual(last['sequence'],2934)
        self.assertEqual((last['floor_observation']['bid'],last['floor_observation']['floor_bid']),(.075,.0776))
        self.assertEqual(result['whole_original_quantity'],788)
        self.assertEqual(result['cash_after_entry'],result['cash_after_floor_observations'])
        self.assertEqual(result['component_event_count'],1)
        self.assertFalse(result['exit_executed'])
        floors=[r['floor_observation']['floor_bid'] for r in result['trace'] if r['floor_observation']['armed']]
        self.assertEqual(floors,sorted(floors))

    def test_successful_original_heist_floor_trajectory_is_exactly_preserved(self):
        result=floor_component('trade5_original_positive')
        self.assertEqual(result['differences_from_original_floor_observations'],[])
        self.assertEqual(result['source_steps_observed'],222)
        self.assertEqual(result['whole_original_quantity'],32)
        self.assertEqual(result['first_arm']['sequence'],6968)
        self.assertEqual(result['first_arm']['floor_observation']['floor_bid'],.551)
        self.assertEqual(result['first_breach']['sequence'],6978)
        self.assertEqual(result['first_breach']['floor_observation']['bid'],.55)
        self.assertEqual({r['original_custody_input'] for r in result['trace']},{'NORMAL','PROMOTED_MAIN'})
        self.assertEqual(result['cash_after_entry'],result['cash_after_floor_observations'])
        self.assertFalse(result['exit_executed'])

    def test_unchanged_mechanics_adviser_and_inherited_behavioral_assertions(self):
        root=Path(__file__).resolve().parents[2]
        for name in ('strategy_core/paper_execution.py','strategy_core/dual_lane.py',
                'strategy_core/tools/management.py',
                'tests/tool_rack/test_pid7812_sprout_promotion.py',
                'tests/tool_rack/test_pid14312_arc_selection_custody.py'):
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),
                manifest()['original_program_sha256'][name],name)
        # November6 enriches three unrelated PID252 admission/inventory
        # premises with current numeric positive evidence. Preserve the exact
        # original floor/transition test bodies instead of pinning unrelated
        # imports and admission fixtures to their old incomplete source.
        import ast
        expected={
            'test_leg_aligned_winner_delays_first_floor_to_200pct_until_stall':'99bde6e40fa4f1920d66c0d03542f98b81a4a07bfa2378af6e9404d99b17fc6e',
            'test_floor_alignment_uses_physical_parent_before_stale_tool_owner':'8771f11ad2c54c241c221724bceaaf62bb7fdeb5960fa5c9f233ff578d3f7177',
            'test_inherited_rollover_continuation_has_transition_custody_against_old_parent':'cd1e145afa3ec4405148031cd372975c161f54d0cb84df74f20750f1d702bcec',
            'test_heist_return_has_transition_custody_even_if_primary_slot':'2432f354a6914baa7f86609b5bdb4b6719b4dc03ad721bad6fe3147f4c7aac41',
            'test_unpromoted_heist_renter_cannot_drift_to_settlement':'2d7ebdb562b03c435138dde58fa20505d0ea579ce23be25c77ccd91ee6b46020',
            'test_historical_extreme_scout_arms_protection_at_60pct':'598a4d7e22e8a9188b72427a50aca2a33bfb3160d2471fae80b4dd64797f1a20',
        }
        tree=ast.parse((root/'tests/tool_rack/test_pid252_tactical_promotions.py').read_text(encoding='utf-8'))
        actual={node.name:hashlib.sha256(ast.dump(node,include_attributes=False).encode('utf-8')).hexdigest()
                for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name in expected}
        self.assertEqual(actual,expected)


class PID4824FloorAuthorityBoundaryTests(unittest.TestCase):
    def test_known_same_side_parent_keeps_existing_200_percent_runway(self):
        _,snapshot,position,intents,_=held_inputs()
        current=variant(snapshot,lambda m:m['mission_context']['parent'].update(side='YES'))
        self.assertEqual(_current_mission_parent(current)['side'],'YES')
        policy=ToolRackPaperEngine._floor_policy(intents,position,current)
        self.assertEqual((policy.arm_roi,policy.immediate_arm_roi),(2.,2.))

    def test_genuine_same_side_current_release_keeps_existing_runway(self):
        _,snapshot,position,intents,_=held_inputs()
        current=variant(snapshot,lambda m:m.update(release_in_progress=True,release_candidate_side='YES'))
        self.assertEqual(_current_mission_parent(current)['side'],'NO')
        policy=ToolRackPaperEngine._floor_policy(intents,position,current)
        self.assertEqual((policy.arm_roi,policy.immediate_arm_roi),(2.,2.))

    def test_confirmed_current_handoff_preserves_preexisting_continuation_runway(self):
        _,snapshot,position,intents,_=held_inputs()
        current=variant(snapshot,lambda m:m.update(release_in_progress=False,
            release_confirmed_current=True,release_candidate_side='YES'))
        policy=ToolRackPaperEngine._floor_policy(intents,position,current)
        self.assertEqual((policy.arm_roi,policy.immediate_arm_roi),(2.,2.))

    def test_confirmed_flag_does_not_invent_a_new_continuation_or_floor_exception(self):
        _,snapshot,position,intents,_=held_inputs()
        def mutate(md):
            md.update(release_in_progress=False,release_confirmed_current=True,release_candidate_side='YES')
            md['mountain']['failed_reextension']=True
        current=variant(snapshot,mutate)
        self.assertFalse(ema9_continuation_precedent(current)['qualified'])
        self.assertEqual(ToolRackPaperEngine._floor_policy(intents,position,current).immediate_arm_roi,1.5)

    def test_unknown_current_parent_keeps_existing_local_continuation_fallback(self):
        _,snapshot,position,intents,_=held_inputs()
        current=variant(snapshot,lambda m:m.pop('mission_context'))
        self.assertEqual(_current_mission_parent(current),{})
        self.assertEqual(ToolRackPaperEngine._floor_policy(intents,position,current).immediate_arm_roi,2.)

    def test_unbound_or_stale_parent_cannot_supply_the_new_restriction(self):
        _,snapshot,position,intents,_=held_inputs()
        mutations={
            'context_not_current':lambda m:m['mission_context'].update(current=False),
            'context_source_mismatch':lambda m:m['mission_context'].update(source_ms=1.),
            'parent_source_mismatch':lambda m:m['mission_context']['parent'].update(source_ms=1.),
            'context_generation_mismatch':lambda m:m['mission_context'].update(continuity_generation=99),
            'parent_generation_mismatch':lambda m:m['mission_context']['parent'].update(continuity_generation=99),
            'future_parent_knowledge':lambda m:m['mission_context']['parent'].update(known_ms=m['current_geometry']['epoch_ms']+1.),
            'invalid_parent':lambda m:m['mission_context']['parent'].update(invalidated=True),
            'completed_parent':lambda m:m['mission_context']['parent'].update(status='COMPLETED'),
            'missing_source_receipt_for_original_clock_lead':lambda m:m.pop('physical_source_receipt'),
            'physical_not_current':lambda m:m.update(physical_current=False),
        }
        for name,mutate in mutations.items():
            with self.subTest(case=name):
                current=variant(snapshot,mutate)
                self.assertEqual(_current_mission_parent(current),{})
                self.assertTrue(ema9_continuation_precedent(current)['qualified'])
                self.assertEqual(ToolRackPaperEngine._floor_policy(intents,position,current).immediate_arm_roi,2.)

    def test_unsupported_but_current_active_parent_is_not_forgotten(self):
        _,snapshot,position,intents,_=held_inputs()
        current=variant(snapshot,lambda m:m['mission_context']['parent'].update(supported=False))
        self.assertEqual(_current_mission_parent(current)['side'],'NO')
        self.assertEqual(ToolRackPaperEngine._floor_policy(intents,position,current).immediate_arm_roi,1.5)

    def test_symmetric_no_return_keeps_ordinary_protection_under_current_yes_parent(self):
        # Explicit mirror packet, not a recorded NO trade or alternate quote.
        from tests.tool_rack.test_pid7812_sprout_promotion import snap
        _,_,position,intents,_=held_inputs()
        current=snap(t=1000.,owner='NO',gap_side='YES',metadata={
            'current_geometry':{'epoch_ms':1000000.,'connection_epoch':1},
            'mission_context':{'current':True,'source_ms':1000000.,'continuity_generation':1,
                'parent':{'id':'SYNTHETIC_YES_PARENT','side':'YES','status':'ACTIVE',
                    'known_ms':900000.,'source_ms':1000000.,'continuity_generation':1}},
        })
        mirrored=replace(position,side=Side.NO,entry_time=980.,close_ts=1900.)
        self.assertEqual(_current_mission_parent(current)['side'],'YES')
        self.assertEqual(ema9_continuation_precedent(current)['side'],'NO')
        self.assertTrue(ema9_continuation_precedent(current)['qualified'])
        self.assertEqual(ToolRackPaperEngine._floor_policy(intents,mirrored,current).immediate_arm_roi,1.5)

    def test_already_armed_original_floor_policy_is_byte_for_byte_equivalent(self):
        _,snapshot,position,intents,_=held_inputs(6978,'5')
        self.assertEqual(position.floor_bid,.551)
        actual=plain(ToolRackPaperEngine._floor_policy(intents,position,snapshot))
        expected=next(p['captured_policy_component'] for p in manifest()['original_policy_probes']
            if p['source']['sequence']==6978)
        self.assertEqual(actual,expected)

    def test_first_floor_still_requires_full_original_quantity_and_current_bid(self):
        entry=record(2856);d=next(x for x in entry['decisions'] if x['scope']=='ENTRY')
        command=d['decision'];event=d['receipt']['event']
        decision=CommanderDecision(Action(command['action']),typed_intent(command['intent']),command['reason'])
        data,snapshot,position,intents,_=held_inputs(2927)
        policy=ToolRackPaperEngine._floor_policy(intents,position,snapshot)
        for name,levels in (('missing',()),('thin',(PriceLevel(.077,1),))):
            with self.subTest(book=name),tempfile.TemporaryDirectory(prefix='pid4824_depth_') as directory:
                with PaperExecutioner(directory) as writer:
                    receipt=writer.execute(decision,book(entry),now_ts=event['timestamp'],command_id='DEPTH_COMPONENT_ENTRY')
                    self.assertEqual(receipt.status,'BOOKED')
                    altered=replace(book(data),quote_id=book(data).quote_id+':SYNTHETIC_'+name,yes_bids=levels)
                    observation=writer.observe_floors(altered,now_ts=snapshot.now_ts,
                        policies={receipt.position_id:policy})[0]
                    self.assertFalse(observation.armed)
                    self.assertIsNone(observation.floor_bid)


if __name__=='__main__':
    unittest.main()
