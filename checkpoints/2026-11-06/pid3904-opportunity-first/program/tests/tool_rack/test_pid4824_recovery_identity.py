"""Original recovery denials and bounded synthetic preservation controls."""
from copy import deepcopy
from dataclasses import replace
import unittest

from strategy_core.recovery import independent_entry_denial
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, Side
from tests.tool_rack.pid4824_recovery_fixtures import (
    bounded_results, corpus, intent, manifest, original_pre_entry_positions,
    parent_prefix, pinned_original_positions, qualify, record, snapshot, late_release_results,
)


class PID4824RecoveryIdentityTests(unittest.TestCase):
    def scene(self):
        return snapshot(),intent(),pinned_original_positions()

    def changed_parent(self,snap,*,identity='P_SYNTHETIC_NEW_OWNER',arc='G_SYNTHETIC_NEW_ARC',reset=False,observed=True):
        md=deepcopy(snap.metadata);g=md['current_geometry'];ctx=md['mission_context'];p=ctx['parent']
        old=p['id'];p.update(id=identity,known_ms=g['epoch_ms'],origin_ms=g['epoch_ms']-100.,origin_observed=observed)
        ctx['parents_by_id'].pop(old,None);ctx['parents_by_id'][identity]=deepcopy(p)
        g['arc_id']=arc
        if reset:
            md['geometry_continuity_generation']+=1;g['connection_epoch']+=1
            ctx['continuity_generation']=md['geometry_continuity_generation']
            p['continuity_generation']=md['geometry_continuity_generation']
            ctx['parents_by_id'][identity]=deepcopy(p)
            md['physical_source_receipt'].update(continuity_generation=md['geometry_continuity_generation'],
                connection_epoch=g['connection_epoch'],geometry_connection_epoch=g['connection_epoch'])
        # Synthetic clock/source alignment, explicitly not an original case.
        return replace(snap,now_ts=g['epoch_ms']/1000.,metadata=md)

    def test_exact_original_hashes_journals_and_parent_prefix(self):
        self.assertEqual(len(corpus()[0]),42)
        self.assertEqual(len(parent_prefix()),813)
        self.assertEqual({x['parent']['id'] for x in parent_prefix()},{'P000L000002'})
        self.assertEqual({x['parent']['side'] for x in parent_prefix()},{'NO'})
        self.assertEqual({x['arc_id'] for x in parent_prefix()},{'G000A000008'})
        self.assertEqual({x['continuity_generation'] for x in parent_prefix()},{0})
        self.assertEqual({x['connection_epoch'] for x in parent_prefix()},{1})

    def test_original_second_entry_denied_with_first_lazarus_wound(self):
        p=original_pre_entry_positions();self.assertEqual(list(p),['1'])
        self.assertEqual(p['1']['custody_state'],'LAZARUS');self.assertFalse(p['1'].get('exit_required',False))
        self.assertIsNone(intent().metadata.get('entry_arc_id'))
        self.assertEqual(p['1']['entry_metadata']['entry_geometry']['arc_id'],'G000A000008')
        updated,denial=qualify();self.assertNotIn('independent_recovery_mission',updated.metadata)
        self.assertEqual(denial,'INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED')

    def test_original_third_entry_separately_denied_with_second_lazarus_wound(self):
        p=original_pre_entry_positions(2856);self.assertEqual(list(p),['2'])
        self.assertEqual(p['2']['custody_state'],'LAZARUS')
        self.assertEqual(qualify(2856)[1],'INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED')

    def test_original_flat_entries_and_real_heist_winner_preserved(self):
        for seq in (2044,5181,6756,7913):
            with self.subTest(seq=seq):
                before=intent(seq);after,denial=qualify(seq)
                self.assertIsNone(denial);self.assertEqual(after.reason,before.reason)
                self.assertEqual(after.side,before.side);self.assertEqual(after.max_price,before.max_price)
                self.assertEqual(after.metadata.get('floor_policy'),before.metadata.get('floor_policy'))

    def test_denied_second_entry_does_not_imply_third_removed_when_flat(self):
        self.assertEqual(qualify(2856)[1],'INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED')
        self.assertIsNone(qualify(2856,positions={})[1])
        self.assertIn('may then be flat',manifest()['inventory_boundary'])

    def test_prior_actual_independent_p18_p19_scope_preserved(self):
        p=original_pre_entry_positions(6294,'PID17588');old=p['3']['entry_metadata']['mission']['parent_leg_id']
        updated,denial=qualify(6294,'PID17588')
        self.assertIsNone(denial);self.assertEqual(old,'P000L000018')
        self.assertEqual(updated.metadata['mission']['parent_leg_id'],'P000L000019')
        self.assertIn('independent_recovery_mission',updated.metadata)

    def test_current_owner_is_pinned_at_flat_entry_without_changing_permission(self):
        updated,denial=qualify(2044);e=updated.metadata['recovery_physical_identity']
        self.assertIsNone(denial);self.assertEqual(e['parent_leg_id'],'P000L000002')
        self.assertEqual(e['parent_side'],'NO');self.assertEqual(e['arc_id'],'G000A000008')
        self.assertTrue(e['parent_origin_observed'])

    def test_completed_close_origin_stays_unobserved(self):
        updated,_=qualify(5181);e=updated.metadata['recovery_physical_identity']
        self.assertEqual(e['parent_leg_id'],'P002L000004');self.assertFalse(e['parent_origin_observed'])

    def test_new_extreme_route_and_commander_label_do_not_renew_same_parent(self):
        snap,proposed,positions=self.scene()
        for tool in ('ONE_COMMANDER_PRIMARY','ALTERNATING_MOUNTAIN','ROLLING_MOUNTAIN','MARKET_HEIST'):
            with self.subTest(tool=tool):
                renamed=replace(proposed,tool=tool,opportunity_id='RENAMED:CHILD:999999',
                    metadata={**proposed.metadata,'physical_mission_id':'NEW_ROUTE:999999'})
                self.assertEqual(qualify(positions=positions,proposed=renamed,current=snap)[1],
                    'INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED')

    def test_new_child_arc_does_not_refill_same_parent_wound(self):
        snap,proposed,positions=self.scene();md=deepcopy(snap.metadata);md['current_geometry']['arc_id']='NEW_CHILD'
        self.assertEqual(qualify(positions=positions,proposed=proposed,current=replace(snap,metadata=md))[1],
            'INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED')

    def test_current_genuinely_new_owner_with_new_arc_preserved(self):
        snap,proposed,positions=self.scene();snap=self.changed_parent(snap)
        self.assertIsNone(qualify(positions=positions,proposed=proposed,current=snap)[1])

    def test_current_new_owner_can_precede_local_arc_label_change(self):
        snap,proposed,positions=self.scene();snap=self.changed_parent(snap,arc='G000A000008')
        self.assertIsNone(qualify(positions=positions,proposed=proposed,current=snap)[1])

    def test_opposite_corrective_mission_preserved(self):
        snap,proposed,positions=self.scene();proposed=replace(proposed,side=Side.NO)
        self.assertIsNone(qualify(positions=positions,proposed=proposed,current=snap)[1])

    def test_no_parent_and_no_arc_are_not_equal_physical_identities(self):
        snap,proposed,positions=self.scene();md=deepcopy(snap.metadata);md.pop('mission_context',None);md['current_geometry'].pop('arc_id',None)
        for p in positions.values():p['entry_metadata'].pop('recovery_physical_identity',None);p['entry_metadata'].pop('entry_geometry',None)
        self.assertIsNone(qualify(positions=positions,proposed=proposed,current=replace(snap,metadata=md))[1])

    def test_reset_rename_without_observed_new_owner_does_not_renew(self):
        snap,proposed,positions=self.scene();snap=self.changed_parent(snap,reset=True,observed=False)
        self.assertEqual(qualify(positions=positions,proposed=proposed,current=snap)[1],
            'INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED')

    def test_observed_new_owner_after_reset_preserved(self):
        snap,proposed,positions=self.scene();snap=self.changed_parent(snap,reset=True,observed=True)
        self.assertIsNone(qualify(positions=positions,proposed=proposed,current=snap)[1])

    def test_future_or_not_yet_known_origin_cannot_prove_new_owner_after_reset(self):
        snap,proposed,positions=self.scene();snap=self.changed_parent(snap,reset=True,observed=True)
        for label in ('future_source','future_known'):
            with self.subTest(label=label):
                md=deepcopy(snap.metadata);p=md['mission_context']['parent']
                if label=='future_source':p['origin_ms']=md['current_geometry']['epoch_ms']+1.
                else:p['known_ms']=p['origin_ms']-1.
                self.assertEqual(qualify(positions=positions,proposed=proposed,current=replace(snap,metadata=md))[1],
                    'INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED')

    def test_missing_stale_or_unrelated_current_owner_cannot_renew_pinned_wound(self):
        snap,proposed,positions=self.scene()
        for label in ('missing','stale','generation','future_known','owner_label_only'):
            with self.subTest(label=label):
                md=deepcopy(snap.metadata)
                if label=='missing':md.pop('mission_context',None)
                elif label=='stale':md['mission_context']['source_ms']-=1000.
                elif label=='generation':md['mission_context']['parent']['continuity_generation']+=1
                elif label=='future_known':md['mission_context']['parent']['known_ms']=md['current_geometry']['epoch_ms']+1
                else:md['mission_context']['parent']={'id':'FAKE','side':'YES','status':'ACTIVE'}
                self.assertEqual(qualify(positions=positions,proposed=proposed,current=replace(snap,metadata=md))[1],
                    'INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED')

    def test_supplied_old_recovery_proof_is_removed_on_same_arc_denial(self):
        proposed=intent();self.assertIn('independent_recovery_mission',proposed.metadata)
        updated,denial=qualify(proposed=proposed)
        self.assertNotIn('independent_recovery_mission',updated.metadata);self.assertIsNotNone(denial)

    def measured(self):
        snap,proposed,positions=self.scene();old=positions['1'];t=old['entry_time'];observed=proposed.metadata['physical_renewal']['observed_at']
        renewal={'independent':True,'renewal_kind':'RETREAT_RETEST_REJECTION','observed_at':observed,
            'prior_attempt_id':old['entry_metadata']['physical_mission_id'],
            'retreat_source':t+10.,'retest_source':t+20.,'rejection_source':observed,
            'retreat_extreme':100.,'retreat_price':97.,'retest_extreme':99.,'rejection_price':96.,
            'measured_retreat_threshold':2.}
        return snap,replace(proposed,metadata={**proposed.metadata,'physical_renewal':renewal}),positions

    def test_actual_measured_post_fill_rejection_preserved(self):
        snap,proposed,positions=self.measured()
        self.assertIsNone(qualify(positions=positions,proposed=proposed,current=snap)[1])

    def test_mirrored_same_side_wound_denial_and_measured_rejection(self):
        snap,proposed,positions=self.measured();md=deepcopy(snap.metadata)
        md['mission_context']['parent']['side']='YES';md['current_geometry']['arc_direction']='UP'
        positions['1']['side']='NO';positions['1']['entry_metadata']['recovery_physical_identity']['parent_side']='YES'
        proposed=replace(proposed,side=Side.NO);renewal=deepcopy(proposed.metadata['physical_renewal'])
        renewal.update(retreat_extreme=100.,retreat_price=103.,retest_extreme=101.,rejection_price=104.)
        proposed=replace(proposed,metadata={**proposed.metadata,'physical_renewal':renewal});snap=replace(snap,metadata=md)
        self.assertIsNone(qualify(positions=positions,proposed=proposed,current=snap)[1])
        renewal['renewal_kind']='NEW_ARC'
        proposed=replace(proposed,metadata={**proposed.metadata,'physical_renewal':renewal})
        self.assertEqual(qualify(positions=positions,proposed=proposed,current=snap)[1],
            'INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED')

    def test_measured_rejection_label_or_old_unordered_measurements_do_not_renew(self):
        snap,proposed,positions=self.measured()
        for key,value in (('retreat_source',None),('retreat_source',positions['1']['entry_time']-1),
                ('retest_source',positions['1']['entry_time']+5),('prior_attempt_id','UNRELATED'),
                ('rejection_price',98.),('rejection_source',proposed.metadata['physical_renewal']['observed_at']+1)):
            with self.subTest(key=key,value=value):
                md=deepcopy(proposed.metadata);md['physical_renewal'][key]=value
                self.assertIsNotNone(qualify(positions=positions,proposed=replace(proposed,metadata=md),current=snap)[1])

    def test_same_parent_scope_and_unqualified_scope_do_not_renew(self):
        proposed=intent(6294,'PID17588');snap=snapshot(6294,'PID17588');positions=original_pre_entry_positions(6294,'PID17588')
        proposed=replace(proposed,metadata={**proposed.metadata,'physical_renewal':{
            **proposed.metadata['physical_renewal'],'renewal_kind':'PARENT_SCOPE_ACQUISITION'}})
        for label in ('same','unsupported','wrong_candidate'):
            with self.subTest(label=label):
                md=deepcopy(snap.metadata);meta=deepcopy(proposed.metadata);pid=meta['mission']['parent_leg_id']
                if label=='same':positions['3']['entry_metadata']['mission']['parent_leg_id']=pid
                elif label=='unsupported':md['mission_context']['parents_by_id'][pid]['supported']=False
                else:md['mission_context']['candidates']['YES']['parent_leg_id']='UNRELATED'
                self.assertIsNotNone(qualify(6294,'PID17588',positions=positions,
                    proposed=replace(proposed,metadata=meta),current=replace(snap,metadata=md))[1])
                positions=original_pre_entry_positions(6294,'PID17588')

    def test_scope_route_cannot_reacquire_same_pinned_legacy_owner(self):
        proposed=intent(6294,'PID17588');snap=snapshot(6294,'PID17588');positions=original_pre_entry_positions(6294,'PID17588')
        pid=proposed.metadata['mission']['parent_leg_id']
        positions['3']['entry_metadata'].pop('mission',None)
        positions['3']['entry_metadata']['recovery_physical_identity']={'parent_leg_id':pid}
        proposed=replace(proposed,metadata={**proposed.metadata,'physical_renewal':{
            **proposed.metadata['physical_renewal'],'renewal_kind':'PARENT_SCOPE_ACQUISITION'}})
        self.assertEqual(qualify(6294,'PID17588',positions=positions,proposed=proposed,current=snap)[1],
            'INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED')

    def test_source_pre_entry_rejection_is_not_post_fill_from_clock_skew(self):
        snap,proposed,positions=self.measured();old=positions['1'];local=old['entry_time']
        source=old['entry_metadata']['entry_geometry']['epoch_ms']/1000.
        self.assertGreater(source,local)
        md=deepcopy(proposed.metadata);md['physical_renewal'].update(
            retreat_source=local+.1,retest_source=local+.2,rejection_source=local+.3)
        self.assertLess(local+.3,source)
        self.assertEqual(qualify(positions=positions,proposed=replace(proposed,metadata=md),current=snap)[1],
            'INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED')

    def test_healed_wound_and_second_lot_capacity_keep_existing_boundary(self):
        snap,proposed,positions=self.scene()
        positions['1']['custody_state']='RECOVERED_NORMAL'
        self.assertEqual(qualify(positions=positions,current=snap,proposed=proposed)[1],
            'CURRENT_CONTRACT_INVENTORY_OWNS_CUSTODY')
        positions=original_pre_entry_positions();positions['EXTRA']=deepcopy(positions['1']);positions['EXTRA']['position_id']='EXTRA'
        self.assertEqual(qualify(positions=positions,current=snap,proposed=proposed)[1],
            'RECOVERY_COHORT_CAPACITY_ONE_WOUND_ONE_NEW_MISSION')

    def test_exit_required_is_not_cleared_by_new_owner(self):
        snap,proposed,positions=self.scene();snap=self.changed_parent(snap);positions['1']['exit_required']=True
        self.assertEqual(qualify(positions=positions,current=snap,proposed=proposed)[1],
            'CURRENT_CONTRACT_INVENTORY_OWNS_CUSTODY')

    def test_non_entry_action_remains_untouched(self):
        proposed=replace(intent(),action=Action.WAIT)
        self.assertIs(ToolRackController().qualify_independent_recovery_mission(proposed,snapshot(),{}),proposed)

    def test_bounded_report_separates_original_inventory_and_flat_sensitivity(self):
        report=bounded_results();denied=[x['sequence'] for x in report['original_cases'] if x['repaired_boundary_denial']]
        self.assertEqual(denied,[2441,2856]);self.assertIsNone(report['flat_sensitivity2856'])

    def test_all_34_original_release_offers_keep_original_component_denials(self):
        for pin in (False,True):
            with self.subTest(pin_new_identity_on_original_scout=pin):
                rows=late_release_results(pin_held_identity=pin);self.assertEqual(len(rows),34)
                self.assertEqual(sum(r['runtime_called'] for r in rows),10)
                self.assertEqual(sum(r['original_entry_reason']=='PAPER_ENTRY_WINDOW_CLOSED_DRAINING' for r in rows),24)
                for row in rows:self.assertEqual(row['new_component'],row['original_component'])

    def test_complete_original_published_callback_probe_has_no_new_grants(self):
        result=manifest()['original_callback_comparison']
        self.assertEqual(result['candidate_reconstruction_missing'],[])
        self.assertEqual(result['counts']['component_offers'],266)
        self.assertEqual(result['counts']['actual_runtime_calls'],242)
        self.assertEqual(result['counts']['new_proof_grants'],0)
        self.assertEqual(result['changed_sequences'],[2441,2856])


if __name__=='__main__':unittest.main()
