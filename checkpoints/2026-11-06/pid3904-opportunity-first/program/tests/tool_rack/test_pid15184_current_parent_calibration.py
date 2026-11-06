"""PID15184 narrow current-parent calibration and preserved permission tests.

Recorded cases are identified as such. Synthetic variants exercise identity,
source safety and exceptions; they are never claimed as recorded executions.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest

from strategy_core.commander import OneCommander
from strategy_core.directional_parent import directional_parent_evidence
from strategy_core.dual_lane import DualLaneCounterfadeMemory, _current_mission_parent, _direction
from strategy_core.mission_scopes import qualified_full_arc_candidate
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from tests.tool_rack.pid15184_current_parent_fixtures import (
    chronology, chronology_probe, manifest, prior_positive_prefix, record, snapshot, typed_intent,
)


def synthetic(t=1000., parent='NO', parent_id='P1', swing='S1', generation=0, epoch=1):
    """Explicit unit packet with a known current mission, not recorded data."""
    return MarketSnapshot(now_ts=t,ticker='SYNTHETIC_A',contract_age_s=400.,
        yes_ask=.19,no_ask=.19,yes_bid=.18,no_bid=.18,metadata={
        'physical_current':True,'geometry_continuity_generation':generation,
        'current_geometry':{'epoch_ms':t*1000.,'btc_price':200.,'range180':100.,
            'arc_id':swing,'arc_direction':'UP' if parent=='NO' else 'DOWN',
            'connection_epoch':epoch},
        'mission_context':{'current':True,'source_ms':t*1000.,'continuity_generation':generation,
            'parent':{'id':parent_id,'side':parent,'status':'ACTIVE','invalidated':False,
                'supported':False,'source_ms':t*1000.,'known_ms':900000.,
                'continuity_generation':generation,'origin_ms':700000.,
                'origin_observed':False,'basis':'OBSERVED_COMPLETED_CLOSE_CONTEXT'}},
        'ema9_ema30_cross_context':{'gap_lifecycle':{'current_side':parent,
            'stage':'INHERITED_OR_UNOBSERVED_CROSS','age_seconds_since_observed_cross':None,
            'observed_side_residence_start_source_ms':800000.,
            'observed_side_residence_seconds':t-800.,'observed_side_residence_samples':10,
            'observed_side_residence_continuous':True,'current_abs_gap_btc':40.,
            'touching_spine':False}},
        'mountain':{'owner_side':parent,'strong_active_release':False,
            'parent_structure':{'parent_id':'PHYSICAL1','parent_side':parent,'parent_terminal_ready':False}},
        'heist':{'qualified_box':True,'visit_id':swing,'box_id':'BOX','current_zone':'LOWER'},
        'tp_geometry':{},
    })


def offer(snap, side=None, *, lane=Lane.TACTICAL, role='TACTICAL'):
    side = side or (Side.YES if snap.metadata['mission_context']['parent']['side']=='NO' else Side.NO)
    swing = snap.metadata['heist']['visit_id']
    return ToolIntent(tool='MARKET_HEIST',territory_id='UNIT_HEIST',lane=lane,
        side=side,action=Action.ENTER,opportunity_id='H:'+swing,max_price=.35,size_tier=10.,
        reason='HEIST_OUTER_EDGE_TACTICAL_RENTER',source_time=snap.now_ts,
        metadata={'position_role':role,'physical_mission_id':'HEIST:BOX:'+swing})


class PID15184RecordedCalibrationTests(unittest.TestCase):
    def test_exact_original_case_hashes_and_complete_chronology_are_verified(self):
        evidence=manifest()
        self.assertEqual(evidence['record_order'],[26,104,1337,2006,2865,3388,3389,4050,5341])
        self.assertEqual(len(chronology()),7915)
        self.assertEqual(evidence['original_observer_reconstruction_mismatches'],[])
        for seq in evidence['record_order']:
            self.assertEqual(record(seq)['sha256'],evidence['records'][str(seq)]['decision_sha256'])

    def test_original26_has_current_completed_close_parent_not_witnessed_origin(self):
        snap=snapshot(26);parent=_current_mission_parent(snap)
        self.assertEqual(parent['id'],'P000L000001')
        self.assertEqual(parent['side'],'NO')
        self.assertEqual(parent['basis'],'OBSERVED_COMPLETED_CLOSE_CONTEXT')
        self.assertFalse(parent['origin_observed'])
        self.assertTrue(parent['supported'])
        self.assertFalse(directional_parent_evidence(snap)['qualified'])
        self.assertIsNone(snap.metadata['current_geometry']['arc_id'])
        self.assertIs(_direction(snap),Side.NO)
        entry=next(x for x in record(26)['decisions']if x['scope']=='ENTRY')['decision']['intent']
        self.assertFalse(DualLaneCounterfadeMemory().consider(typed_intent(entry),snap))

    def test_only_first_recorded_entry_changes_in_original_ordered_component_stream(self):
        result=chronology_probe()
        self.assertEqual(result['physical_callbacks'],43)
        self.assertEqual([(x['sequence'],x['original_allowed'],x['current_allowed'])
            for x in result['changed_physical_callbacks']],[(26,True,False)])
        self.assertEqual([(x['sequence'],x['current_filter_allowed'])for x in result['recorded_fill_filter_results']],
            [(26,False),(1337,True),(2006,True),(4050,True),(5341,True)])

    def test_first_current_observation_precedes_later_entries_and_history_qualification(self):
        result=chronology_probe()
        first=result['first_current_parent_observation']
        self.assertEqual(first['sequence'],104)
        self.assertEqual(first['observation']['first_swing'],'P000L000001')
        for row in result['recorded_fill_filter_results'][1:]:
            self.assertEqual(row['first_observation']['first_swing'],'P000L000001')
            self.assertEqual(row['first_observation']['first_seen_ts'],record(104)['now_ts'])
        self.assertFalse(directional_parent_evidence(snapshot(3388))['qualified'])
        self.assertTrue(directional_parent_evidence(snapshot(3389))['qualified'])

    def test_current_full_arc_proof_is_preserved_and_shared_admission_checks_actual_quality(self):
        expected={1337:(Action.ENTER,'COMMANDER_ACCEPTED_TOOL_INTENT'),
            2006:(Action.WAIT,'OPPORTUNITY_MOUNTAIN_PARENT_TERMINAL_PROOF_REQUIRED'),
            4050:(Action.WAIT,'OPPORTUNITY_TP_EMA_JUNCTION_WAIT'),
            5341:(Action.WAIT,'OPPORTUNITY_RETURN_TARGET_RUNWAY_NOT_PROVEN')}
        for seq in (1337,2006,4050,5341):
            with self.subTest(sequence=seq):
                snap=snapshot(seq)
                self.assertTrue(qualified_full_arc_candidate(snap.metadata['mission_context'],Side.YES))
                entry=next(x for x in record(seq)['decisions']if x['scope']=='ENTRY')['decision']['intent']
                intent=typed_intent(entry)
                self.assertNotIn('mission',intent.metadata)
                commander=OneCommander();decision=commander.decide_entry((intent,),snap,{})
                self.assertEqual((decision.action,decision.reason),expected[seq])
                g=snap.metadata['current_geometry'];tp=snap.metadata['tp_geometry']
                if seq==1337:
                    # The logical parent carries real completed-minute scale;
                    # the current child has a22.89BTC rejection. Retained.
                    self.assertGreater(g['btc_change6'],22.)
                    proof=decision.intent.metadata['commander_opportunity']
                    self.assertTrue(proof['evidence']['source_bound_parent_scale_with_current_rejection'])
                elif seq==2006:
                    # Old cheap-extreme authority was a0.01BTC microstall,
                    # still outward30sEMA9,223.8s left and166.76BTC to TP.
                    self.assertLess(abs(g['btc_change6']),.02)
                    self.assertLess(g['ema9_change30'],0.)
                    self.assertGreater(tp['required_move_to_target_btc'],166.)
                elif seq==4050:self.assertTrue(tp['target_between_ema9_ema30'])
                else:
                    self.assertLess(tp['remaining_seconds'],148.)
                    self.assertGreater(tp['required_move_to_target_btc'],122.)
        self.assertFalse(qualified_full_arc_candidate(snapshot(26).metadata['mission_context'],Side.YES))

    def test_candidate_custody_and_freshness_modules_are_byte_unchanged(self):
        """Preserve the historical candidate pin through the reviewed deltas.

        The candidate module is intentionally updated in PID10656. Its exact
        original byte identity remains pinned in the historical source chain.
        Opportunity-first changes the single Commander admission boundary;
        candidate bytes remain exactly the immediate PID3904 source. Both
        identities are checked rather than rewriting the historical baseline.
        """
        root=Path(__file__).resolve().parents[2]
        for name in ('strategy_core/directional_parent.py',
                     'strategy_core/source_freshness.py'):
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),
                manifest()['original_program_sha256'][name],name)
        from CHECK_TOOL_RACK_PAPER import verify_authorized_delta
        self.assertNotIn('strategy_core/commander_candidates.py',
                         verify_authorized_delta(root)['changed_files'])
        name='strategy_core/commander_candidates.py'
        ancestor=json.loads((root/'PID4824_SOURCE_SHA256.json').read_text(encoding='utf-8'))
        approval=json.loads((root/'PID3904_APPROVAL.json').read_text(encoding='utf-8'))
        immediate=json.loads((root/'PID3904_SOURCE_SHA256.json').read_text(encoding='utf-8'))
        self.assertEqual(ancestor[name],manifest()['original_program_sha256'][name])
        self.assertEqual(immediate[name],hashlib.sha256((root/name).read_bytes()).hexdigest())
        self.assertEqual(approval['changed_core_files'][name],{
            'baseline_sha256':ancestor[name],
            'release_sha256':hashlib.sha256((root/name).read_bytes()).hexdigest()})

    def test_prior_positive_uses_actual_ordered_observations_without_chapter_reset(self):
        prefix=prior_positive_prefix()
        self.assertEqual(len(prefix),907)
        self.assertEqual([prefix[0]['source']['sequence'],prefix[-1]['source']['sequence']],[3509,4415])
        self.assertEqual(prefix[0]['snapshot']['metadata']['current_geometry']['arc_id'],'G000A000015')
        self.assertEqual(prefix[0]['snapshot']['metadata']['current_geometry']['arc_direction'],'UP')
        from tests.tool_rack.pid17588_late_scout_fixtures import manifest as prior_manifest, probe_group
        group='PID17588_trade2_positive'
        self.assertEqual([x['decision'] for x in probe_group(group)],
            prior_manifest()['expected_baseline_components'][group])
        self.assertEqual(probe_group(group)[0]['decision']['action'],'ENTER')

    def test_prior_behavior_archive_and_original_positive_fixture_bytes_are_unchanged(self):
        root=Path(__file__).resolve().parents[2]
        for name,digest in manifest()['unmodified_inherited_assets_sha256'].items():
            # Opportunity-first admission adds precise WAIT diagnostics to the
            # current behavior test. Preserve its exact inherited source here;
            # the original recorded fixtures and their manifest stay untouched.
            path = (root/'tests/tool_rack/fixtures/pid17588_pre_opportunity_behavior_test.py.txt'
                    if name == 'tests/tool_rack/test_pid17588_late_scout.py' else root/name)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest,name)


class PID15184CurrentParentSourceTests(unittest.TestCase):
    def test_supported_false_does_not_invalidate_active_known_parent(self):
        snap=synthetic()
        self.assertFalse(snap.metadata['mission_context']['parent']['supported'])
        self.assertIs(_direction(snap),Side.NO)
        self.assertFalse(DualLaneCounterfadeMemory().consider(offer(snap),snap))

    def test_no_owner_only_or_nonterminal_structure_fallback_is_added(self):
        snap=synthetic();md=deepcopy(snap.metadata);md.pop('mission_context')
        current=replace(snap,metadata=md)
        self.assertIsNone(_direction(current))
        self.assertTrue(DualLaneCounterfadeMemory().consider(offer(snap),current))

    def test_missing_stale_unrelated_or_invalid_current_packets_supply_no_parent(self):
        mutations=(
            ('physical_current',lambda m:m.update(physical_current=False)),
            ('not_current',lambda m:m['mission_context'].update(current=False)),
            ('context_source',lambda m:m['mission_context'].update(source_ms=999999.)),
            ('parent_source',lambda m:m['mission_context']['parent'].update(source_ms=999999.)),
            ('context_generation',lambda m:m['mission_context'].update(continuity_generation=1)),
            ('parent_generation',lambda m:m['mission_context']['parent'].update(continuity_generation=1)),
            ('boolean_generation',lambda m:m['mission_context']['parent'].update(continuity_generation=False)),
            ('unknown_known_at',lambda m:m['mission_context']['parent'].pop('known_ms')),
            ('future_known_at',lambda m:m['mission_context']['parent'].update(known_ms=1000001.)),
            ('invalidated',lambda m:m['mission_context']['parent'].update(invalidated=True)),
            ('completed',lambda m:m['mission_context']['parent'].update(status='COMPLETED')),
            ('no_identity',lambda m:m['mission_context']['parent'].update(id='')),
            ('unknown_side',lambda m:m['mission_context']['parent'].update(side='UNKNOWN')),
        )
        for name,mutate in mutations:
            with self.subTest(case=name):
                snap=synthetic();md=deepcopy(snap.metadata);mutate(md)
                self.assertIsNone(_direction(replace(snap,metadata=md)))
        self.assertIsNone(_direction(replace(synthetic(),now_ts=1003.001)))

    def test_current_source_clock_lead_requires_original_receipt(self):
        snap=snapshot(26)
        self.assertGreater(snap.metadata['current_geometry']['epoch_ms']/1000.,snap.now_ts)
        self.assertIs(_direction(snap),Side.NO)
        for mode in ('missing','stale_receipt','wrong_source'):
            with self.subTest(case=mode):
                md=deepcopy(snap.metadata)
                if mode=='missing':md.pop('physical_source_receipt')
                elif mode=='stale_receipt':md['physical_source_receipt']['receive_age_seconds_at_capture']=6.
                else:md['physical_source_receipt']['source_ms']-=1.
                self.assertIsNone(_direction(replace(snap,metadata=md)))

    def test_legacy_historical_and_release_directions_remain_available(self):
        snap=synthetic(t=1700.)
        md=deepcopy(snap.metadata);md.pop('mission_context')
        self.assertIs(_direction(replace(snap,metadata=md)),Side.NO)
        md['ema9_ema30_cross_context']['gap_lifecycle']['observed_side_residence_seconds']=1.
        md['mountain']['strong_active_release']=True
        self.assertIs(_direction(replace(snap,metadata=md)),Side.NO)

    def test_qualified_history_precedes_opposite_current_mission(self):
        snap=synthetic(t=1700.,parent='YES')
        md=deepcopy(snap.metadata)
        md['ema9_ema30_cross_context']['gap_lifecycle']['current_side']='NO'
        self.assertIs(_direction(replace(snap,metadata=md)),Side.NO)


class PID15184PhysicalChapterTests(unittest.TestCase):
    def test_all_main_and_tactical_counter_families_observe_first_swing(self):
        for lane,role in ((Lane.MAIN,'PRIMARY'),(Lane.TACTICAL,'TACTICAL')):
            with self.subTest(lane=lane):
                memory=DualLaneCounterfadeMemory();snap=synthetic()
                self.assertFalse(memory.consider(offer(snap,lane=lane,role=role),snap))
                later=synthetic(t=1020.,swing='S2')
                self.assertTrue(memory.consider(offer(later,lane=lane,role=role),later))

    def test_current_parent_first_and_later_swing_are_symmetric(self):
        for parent in ('NO','YES'):
            with self.subTest(parent=parent):
                memory=DualLaneCounterfadeMemory();snap=synthetic(parent=parent)
                self.assertFalse(memory.consider(offer(snap),snap))
                later=synthetic(t=1020.,parent=parent,swing='S2')
                intent=offer(later)
                self.assertTrue(memory.consider(intent,later))
                self.assertEqual(memory.calibration_for(intent,later)['parent_side'],parent)

    def test_quote_and_rolling_box_changes_do_not_create_later_swing(self):
        memory=DualLaneCounterfadeMemory()
        for n in range(5):
            snap=synthetic(t=1000.+n)
            md=deepcopy(snap.metadata);md['heist']['box_id']='ROLLING:'+str(n)
            snap=replace(snap,yes_ask=.19-.01*n,metadata=md)
            self.assertFalse(memory.consider(offer(snap),snap))
        self.assertEqual(memory.last_observation['first_swing'],'S1')

    def test_rollover_and_benign_mission_labels_preserve_current_chapter(self):
        memory=DualLaneCounterfadeMemory();first=synthetic()
        self.assertFalse(memory.consider(offer(first),first))
        later=synthetic(t=1020.,swing='S2')
        md=deepcopy(later.metadata);md['mission_context']['parent'].update(supported=True,basis='CURRENT_CONTINUATION')
        md['mountain']['owner_side']='YES'
        later=replace(later,ticker='SYNTHETIC_B',contract_age_s=5.,metadata=md)
        self.assertTrue(memory.consider(offer(later),later))
        self.assertEqual(len(memory._records),1)

    def test_gaining_historical_qualification_is_not_a_second_first_swing(self):
        memory=DualLaneCounterfadeMemory();first=synthetic()
        self.assertFalse(memory.consider(offer(first),first))
        qualified=synthetic(t=1700.,swing='S2')
        self.assertTrue(directional_parent_evidence(qualified)['qualified'])
        self.assertTrue(memory.consider(offer(qualified),qualified))
        self.assertEqual(len(memory._records),1)
        # When the local mission later points away, historical direction keeps
        # the same previously bound chapter rather than borrowing its new ID.
        md=deepcopy(qualified.metadata)
        md['mission_context']['parent'].update(id='OPPOSITE',side='YES')
        historical=replace(qualified,metadata=md)
        self.assertTrue(memory.consider(offer(qualified),historical))
        self.assertEqual(len(memory._records),1)

    def test_genuine_parent_side_identity_and_continuity_changes_reset_sample(self):
        for change in ({'parent_id':'P2'},{'parent':'YES'},{'generation':1},{'epoch':2}):
            with self.subTest(change=change):
                memory=DualLaneCounterfadeMemory();first=synthetic()
                self.assertFalse(memory.consider(offer(first),first))
                later=synthetic(t=1020.,swing='S2',**change)
                self.assertFalse(memory.consider(offer(later),later))

    def test_opposite_gap_cannot_name_current_mission_or_reuse_calibration(self):
        memory=DualLaneCounterfadeMemory();snap=synthetic(parent='YES')
        md=deepcopy(snap.metadata)
        md['ema9_ema30_cross_context']['gap_lifecycle']['current_side']='NO'
        current=replace(snap,metadata=md)
        self.assertFalse(memory.consider(offer(snap),current))
        chapter=next(iter(memory._records))
        self.assertEqual(chapter[:3],('YES','CURRENT_MISSION','P1'))
        qualified=synthetic(t=1700.,parent='YES',swing='S2')
        md=deepcopy(qualified.metadata);md['ema9_ema30_cross_context']['gap_lifecycle']['current_side']='NO'
        qualified=replace(qualified,metadata=md)
        self.assertFalse(memory.consider(offer(qualified,Side.YES),qualified))

    def test_actual_opposite_child_can_be_observed_before_a_paid_offer(self):
        memory=DualLaneCounterfadeMemory();first=synthetic()
        memory.observe_first_physical_swing(first)
        self.assertEqual(memory.last_observation['first_swing'],'S1')
        later=synthetic(t=1020.,swing='S2')
        self.assertTrue(memory.consider(offer(later),later))


class PID15184CurrentMarkerTests(unittest.TestCase):
    def calibrated_rack(self):
        rack=ToolRackController();first=synthetic()
        self.assertEqual(rack.filter_independent_lane_candidates((offer(first),),first),())
        later=synthetic(t=1020.,swing='S2')
        allowed=rack.filter_independent_lane_candidates((offer(later),),later)
        self.assertTrue(allowed[0].metadata['dual_lane_counterfade_calibrated'])
        return rack,later,allowed[0]

    def test_later_current_parent_heist_marker_uses_same_actual_calibration(self):
        rack,later,intent=self.calibrated_rack()
        self.assertFalse(directional_parent_evidence(later)['qualified'])
        self.assertEqual(rack._dual_counterfade.last_observation['first_swing'],'S1')
        self.assertEqual(intent.metadata['position_role'],'TACTICAL')

    def test_no_marker_on_main_or_primary_label(self):
        for lane,role in ((Lane.MAIN,'PRIMARY'),(Lane.TACTICAL,'PRIMARY')):
            with self.subTest(lane=lane,role=role):
                rack,later,_=self.calibrated_rack()
                accepted=rack.filter_independent_lane_candidates((offer(later,lane=lane,role=role),),later)
                self.assertNotIn('dual_lane_counterfade_calibrated',accepted[0].metadata)

    def test_same_side_unknown_and_nonentry_bypasses_clear_stale_marker(self):
        for mode in ('same_side','unknown','nonentry'):
            with self.subTest(mode=mode):
                rack,snap,old=self.calibrated_rack()
                candidate=old
                if mode=='same_side':candidate=replace(old,side=Side.NO)
                elif mode=='unknown':
                    md=deepcopy(snap.metadata);md.pop('mission_context');snap=replace(snap,metadata=md)
                else:candidate=replace(old,action=Action.HOLD)
                accepted=rack.filter_independent_lane_candidates((candidate,),snap)
                self.assertEqual(len(accepted),1)
                self.assertNotIn('dual_lane_counterfade_calibrated',accepted[0].metadata)
                self.assertIsNone(rack._dual_counterfade.calibration_for(candidate,snap))

    def test_release_handoff_and_confirmed_release_bypasses_clear_stale_marker(self):
        for mode in ('handoff','confirmed'):
            with self.subTest(mode=mode):
                rack,snap,old=self.calibrated_rack()
                candidate=old
                if mode=='handoff':candidate=replace(old,tool='RELEASE_WATCHER',lane=Lane.HANDOFF,action=Action.RELAY)
                else:
                    md=deepcopy(snap.metadata);md.update(release_confirmed_current=True,release_candidate_side='YES')
                    snap=replace(snap,metadata=md)
                accepted=rack.filter_independent_lane_candidates((candidate,),snap)
                self.assertEqual(len(accepted),1)
                self.assertNotIn('dual_lane_counterfade_calibrated',accepted[0].metadata)

    def test_genuine_terminal_plus_tp_bypass_clears_stale_marker(self):
        rack,snap,old=self.calibrated_rack()
        md=deepcopy(snap.metadata)
        md['mountain'].update(terminal_evidence_qualified=True,edge_window_active=True,failed_reextension=True)
        md['tp_geometry']['contract_ownership_side']='YES'
        snap=replace(snap,metadata=md)
        accepted=rack.filter_independent_lane_candidates((old,),snap)
        self.assertEqual(len(accepted),1)
        self.assertNotIn('dual_lane_counterfade_calibrated',accepted[0].metadata)

    def test_new_chapter_cannot_reuse_previous_offer_marker(self):
        rack,_,old=self.calibrated_rack()
        fresh=synthetic(t=1040.,parent_id='P2',swing='S3')
        proposed=replace(offer(fresh),metadata={**offer(fresh).metadata,'dual_lane_counterfade_calibrated':True})
        self.assertEqual(rack.filter_independent_lane_candidates((proposed,),fresh),())
        self.assertIsNone(rack._dual_counterfade.calibration_for(proposed,fresh))

    def test_proof_is_bound_to_exact_intent_and_snapshot_consideration(self):
        memory=DualLaneCounterfadeMemory();first=synthetic()
        self.assertFalse(memory.consider(offer(first),first))
        later=synthetic(t=1020.,swing='S2');intent=offer(later)
        self.assertTrue(memory.consider(intent,later))
        self.assertIsNotNone(memory.calibration_for(intent,later))
        self.assertIsNone(memory.calibration_for(replace(intent,opportunity_id='OTHER'),later))
        self.assertIsNone(memory.calibration_for(intent,replace(later,ticker='OTHER')))
        memory.observe_first_physical_swing(later)
        self.assertIsNone(memory.calibration_for(intent,later))


if __name__=='__main__':
    unittest.main()
