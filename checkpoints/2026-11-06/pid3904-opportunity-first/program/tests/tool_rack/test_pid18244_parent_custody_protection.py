"""PID18244 selective source-bound regression cases; NOT a full original-run replay.

Recorded physical source frames are copied verbatim from the SHA-256 verified
PAPER archive. Commander/management context variants are explicitly synthetic;
no test asserts an alternate trade, exit fill, or hypothetical P&L.

The legacy selected-physical trade-6 row occurs after the original proposal
and is not a complete captured admission snapshot. Its authored wrapper must
WAIT without invented continuity, receipt or target proof. The separately
recovered full original seq8122 fixture now preserves the real positive
Commander admission at its exact source, without later rows or outcome input.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import gzip
import json
from pathlib import Path
import unittest

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import ema9_continuation_precedent, physical_entry_candidates
from strategy_core.paper_execution import PaperPosition
from strategy_core.paper_runtime import ToolRackPaperEngine
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from tests.tool_rack.test_pid7812_sprout_promotion import snap as sprout_snapshot
from tests.tool_rack.test_opportunity_first_commander import source_snapshot, typed_intent

DATA = json.loads((Path(__file__).parent/'fixtures/pid18244_selected_physical_frames.json').read_text(encoding='utf-8'))


def frame(name):
    return deepcopy(DATA['frames'][name]['physical_geometry'])


def seed_position(side=Side.NO, *, t=1793911284.9):
    return {'position_id':'3', 'ticker':'KX-PID18244-1545', 'side':side,
        'entry_price':.055, 'entry_time':t-32., 'close_ts':t+200.,
        'tool':'MARKET_HEIST','territory_id':'HEIST-UP-SPROUT',
        'opportunity_id':'HEIST-3', 'lane':Lane.TACTICAL,
        'position_role':'TACTICAL', 'custody_state':'NORMAL',
        'entry_reason':'HEIST_PARALLEL_STALLED_EDGE_RETURN',
        'entry_metadata':{'position_role':'TACTICAL'}}


def promotion_snapshot(*, physical_parent='UP', release_side=None):
    physical=frame('trade3_promotion')
    t=physical['epoch_ms']/1000.+.5
    # The old historical NO continuation precedent is intentionally combined
    # with the exact current UP-parent native frame to reproduce the custody
    # *conflict*. This is a selected-frame regression, not a whole-run replay.
    base=sprout_snapshot(t=t, owner='NO', gap_side='YES', stage='SPROUT')
    md=deepcopy(base.metadata)
    md['current_geometry'].update(physical)
    md['geometry_last_epoch_ms']=physical['epoch_ms']
    md['physical_current']=True
    md['commander_strategy']['owned_side']='YES'
    md['release_in_progress']=release_side is not None
    md['release_candidate_side']=release_side
    # A past NO cross can qualify a local NO precedent; it cannot override
    # the *current* upward EMA9 parent just because the child arc is DOWN.
    return replace(base,now_ts=t,ticker='KX-PID18244-1545',metadata=md)


def tactical_floor_inputs(*, parent_direction='UP', time_shift=0, promoted=False, already_armed=False):
    physical=frame('trade4_peak')
    physical['parent_direction']=parent_direction
    physical['epoch_ms']+=time_shift*1000
    t=frame('trade4_peak')['epoch_ms']/1000.+.3
    entry_time=1793911650.9090908
    original={'arm_roi':.40,'trail_fraction':.03,'min_age_s':0.,
        'immediate_arm_roi':.40,'first_arm_from_current_bid':True,
        'profit_policy_revision':'OPERATOR_AUTHORIZED_QUICK_HEIST_40_ARM_3_TRAIL_V1'}
    pos=PaperPosition(position_id='4',ticker='KX-PID18244-1600',side=Side.NO,qty=36,
        entry_price=.26,cost=9.36,entry_fee_remaining=.49,
        entry_time=entry_time,close_ts=1793912400.,tool='MARKET_HEIST',
        territory_id='HEIST-UP-SPROUT',opportunity_id='HEIST-4',lane=Lane.TACTICAL,
        entry_quote_id='Q',entry_reason='HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED',
        entry_metadata={'position_role':'TACTICAL','floor_policy':original,
            'entry_geometry':{'epoch_ms':1793911650700.}},
        peak_bid=.51,floor_bid=.4900 if already_armed else None,
        trail_fraction=.03 if already_armed else None,
        exit_required=False,exit_reason=None,
        position_role='TACTICAL',custody_state='PROMOTED_MAIN' if promoted else 'NORMAL')
    # The child-adviser/management wrapper mistakenly labeled the temporary
    # DOWN move as a living NO leg while the native EMA9 parent was UP.
    md={'physical_current':True,'current_geometry':physical,
        'geometry_last_epoch_ms':physical['epoch_ms'],
        'commander_strategy':{'owned_side':'NO'},
        'mountain':{'owner_side':'NO','terminal_evidence_qualified':False,'stall':False,'hesitation':False},
        'ema9_ema30_cross_context':{'gap_lifecycle':{'stage':'DEVELOPING','current_side':'YES'}}}
    ss=MarketSnapshot(now_ts=t,ticker=pos.ticker,contract_age_s=750.,
        yes_ask=.5,no_ask=.52,yes_bid=.49,no_bid=.51,metadata=md)
    # Captured management-style deferral. The initial quick floor in the
    # immutable entry metadata must survive counterparent TACTICAL custody.
    defer={'arm_roi':.40,'trail_fraction':.05,'min_age_s':0.,
        'immediate_arm_roi':1.0,'first_arm_allowed':False,
        'first_arm_from_current_bid':True,
        'roi_trail_tiers':[[1.0,.05],[1.5,.03],[6.0,.02]],
        'profit_policy_revision':'PID19832_EARNED_PEAK_LOCK_100_5_150_3'}
    it=ToolIntent(tool='MARKET_HEIST',territory_id='HEIST-UP-SPROUT',
        lane=Lane.TACTICAL,side=Side.NO,action=Action.HOLD,
        opportunity_id='HEIST-4',max_price=None,size_tier=None,
        reason='LIVING_LEG_BREATHING_WITH_100_PERCENT_PEAK_LOCK',source_time=t,
        metadata={'floor_policy':defer})
    return ss,pos,(it,)


class PID18244RecordedControlTests(unittest.TestCase):
    def test_exact_source_frames_3_4_6_and_ledger_unchanged(self):
        self.assertEqual(DATA['source_zip_sha256'],'2600a6273a54ee1831f6ba40aced24b998cbd6c1f3b142dfd495ac8804bb9b12')
        self.assertEqual({name:frame(name)['parent_direction'] for name in
            ('trade3_promotion','trade4_peak','trade6_entry')},
            {'trade3_promotion':'UP','trade4_peak':'UP','trade6_entry':'UP'})
        rows={x['id']:x for x in DATA['ledger_controls']}
        self.assertEqual((rows[3]['entry_price'],rows[3]['exit_price'],rows[3]['net_pnl']),(.055,0.,-9.97))
        self.assertEqual((rows[4]['entry_price'],rows[4]['exit_price'],rows[4]['net_pnl']),(.26,.28,-.28))
        self.assertEqual((rows[6]['entry_price'],rows[6]['exit_price']),(.0877,.35))
        self.assertAlmostEqual(rows[6]['net_pnl'],64.2741)

    def test_3_historical_no_precedent_does_not_grant_wrong_side_main(self):
        ss=promotion_snapshot()
        precedent=ema9_continuation_precedent(ss)
        self.assertTrue(precedent['qualified'],precedent)
        self.assertEqual(precedent['side'],'NO')
        self.assertEqual(ss.metadata['current_geometry']['parent_direction'],'UP')
        decision=OneCommander().decide_position((),ss,seed_position(t=ss.now_ts))
        self.assertNotEqual((decision.custody_update or {}).get('state'),'PROMOTED_MAIN')
        self.assertNotIn('PROMOTED_TO_LIVING',decision.reason)

    def test_3_block_applies_after_lazarus_recovery_too(self):
        ss=promotion_snapshot()
        p={**seed_position(t=ss.now_ts),'custody_state':'RECOVERED_NORMAL'}
        decision=OneCommander().decide_position((),ss,p)
        self.assertNotEqual((decision.custody_update or {}).get('state'),'PROMOTED_MAIN')

    def test_true_same_side_release_handoff_still_promotes(self):
        ss=promotion_snapshot(release_side='NO')
        d=OneCommander().decide_position((),ss,seed_position(t=ss.now_ts))
        self.assertIs(d.action,Action.HOLD)
        self.assertEqual((d.custody_update or {}).get('state'),'PROMOTED_MAIN')
        self.assertEqual(d.reason,'COMMANDER_HEIST_SEED_PROMOTED_TO_RELEASE_CUSTODY')

    def test_4_current_opposing_parent_restores_40pct_tactical_first_floor(self):
        ss,pos,intents=tactical_floor_inputs()
        policy=ToolRackPaperEngine._floor_policy(intents,pos,ss)
        self.assertAlmostEqual(policy.arm_roi,.4)
        self.assertAlmostEqual(policy.immediate_arm_roi,.4)
        self.assertAlmostEqual(policy.trail_fraction,.03)
        self.assertTrue(policy.first_arm_allowed)
        self.assertTrue(policy.first_arm_from_current_bid)
        self.assertEqual(pos.floor_bid,None)

    def test_4_missing_or_stale_source_does_not_invent_new_floor_authority(self):
        for shift in (-60,10):
            with self.subTest(shift=shift):
                ss,pos,intents=tactical_floor_inputs(time_shift=shift)
                policy=ToolRackPaperEngine._floor_policy(intents,pos,ss)
                self.assertGreater(policy.immediate_arm_roi,.4)
                self.assertFalse(policy.first_arm_allowed)

    def test_4_true_same_side_parent_keeps_living_runner_policy(self):
        ss,pos,intents=tactical_floor_inputs(parent_direction='DOWN')
        policy=ToolRackPaperEngine._floor_policy(intents,pos,ss)
        self.assertGreater(policy.immediate_arm_roi,.4)
        self.assertFalse(policy.first_arm_allowed)

    def test_4_already_committed_floor_is_not_loosened(self):
        ss,pos,intents=tactical_floor_inputs(already_armed=True)
        policy=ToolRackPaperEngine._floor_policy(intents,pos,ss)
        self.assertGreater(policy.immediate_arm_roi,.4)
        self.assertAlmostEqual(pos.floor_bid,.49)

    def test_6_first_class_recent_level_match_no_entry_remains(self):
        # Keep this method name for the historical suites that reuse it, now
        # using the actual captured proposal and its same-row source metadata.
        path=Path(__file__).parent/'fixtures/pid18244_opportunity_source_sequence.json.gz'
        with gzip.open(path,'rt',encoding='utf-8') as handle:
            data=json.load(handle)
        self.assertEqual(data['original_archive_sha256'],DATA['source_zip_sha256'])
        raw=data['frames']['8122']
        self.assertEqual(raw['source_row_sha256'],
            '73f1ef83d5be758c3dc93459bfc37a1a7822fdbfe4abcafae6b3f9584a2fe7d2')
        self.assertNotIn('decisions',raw)
        self.assertNotIn('ledger',raw)
        ss=source_snapshot(raw)
        self.assertEqual(ss.metadata['current_geometry']['epoch_ms'],1793912081292.4841)
        self.assertLess(ss.metadata['current_geometry']['epoch_ms'],ss.now_ts*1000.)
        candidates=[typed_intent(i) for i in raw['candidate_intents']]
        self.assertEqual(len(candidates),1)
        self.assertEqual(candidates[0].reason,'COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN')
        original=deepcopy(candidates[0])
        commander=OneCommander()
        commander.physical_entry_candidates(ss)
        decision=commander.decide_entry(candidates,ss,{})
        self.assertIs(decision.action,Action.ENTER,decision)
        self.assertIs(decision.intent.side,Side.NO)
        self.assertEqual((decision.intent.max_price,decision.intent.size_tier),(.20,25.))
        self.assertEqual(candidates[0],original)
        proof=decision.intent.metadata['commander_opportunity']
        self.assertEqual(proof['species'],'MOUNTAIN_RETURN')
        self.assertTrue(proof['evidence']['current_terminal_with_comparable_maturity'])
        self.assertTrue(proof['evidence']['defended_level_with_current_rejection'])
        runway=proof['evidence']['return_runway']
        self.assertEqual(runway['basis'],'PROVEN_RETURN_LEG_CAN_REACH_TP')
        self.assertLess(runway['required_total_runway_seconds'],runway['remaining_seconds'])
        # .087 is the observed ask. The later .0877 modeled fill and .35 exit
        # are not inputs or hypothetical execution assertions in this test.
        self.assertAlmostEqual(proof['ask'],.087)

    def test_6_later_partial_row_is_not_original_entry_admission_proof(self):
        p=frame('trade6_entry')
        self.assertGreater(p['epoch_ms'],1793912081826.264)
        now=p['epoch_ms']/1000.+.3
        md={'physical_current':True,'current_geometry':p,'geometry_last_epoch_ms':p['epoch_ms'],
            'historical_extreme_release':{'qualified':False,'recent_level_match':{
                'side':'NO','anchor':76197.03,'anchor_time':now-401.83,
                'age_s':401.83,'distance_btc':4.93}},
            'mountain':{'owner_side':'YES','failed_reextension':False,
                'stall':False,'hesitation':False,'meaningful_retreat':False,
                'strong_active_release':False},
            'commander_strategy':{'active_overlays':[]},'tp_geometry':{}}
        ss=MarketSnapshot(now_ts=now,ticker='KX-PID18244-1600',contract_age_s=582.,
            yes_ask=.912,no_ask=.088,yes_bid=.90,no_bid=.08,metadata=md)
        candidates=physical_entry_candidates(ss)
        self.assertTrue(any(i.reason=='COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN'
                            and i.side is Side.NO and i.size_tier==25.
                            and i.max_price==.2 for i in candidates),candidates)
        self.assertEqual(ss.metadata['current_geometry'],frame('trade6_entry'))
        self.assertNotIn('geometry_continuity_generation',ss.metadata)
        self.assertNotIn('physical_source_receipt',ss.metadata)
        self.assertFalse(ss.metadata['tp_geometry'])
        # Both candidate publication and direct candidate submission must
        # obey the shared source boundary. Do not enrich the archived wrapper
        # with fictional feed receipts, target values or current measurements.
        self.assertFalse(OneCommander().physical_entry_candidates(ss))
        decision=OneCommander().decide_entry(list(candidates),ss,{})
        self.assertIs(decision.action,Action.WAIT,decision)
        self.assertEqual(decision.reason,'OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED')

    def test_2_5_positive_heist_returns_and_6_protected_exit_immutable(self):
        ledger={row['id']:row for row in DATA['ledger_controls']}
        self.assertEqual(ledger[2]['entry_reason'],'HEIST_OUTER_EDGE_TACTICAL_RENTER')
        self.assertEqual(ledger[5]['entry_reason'],'HEIST_PARALLEL_STALLED_EDGE_RETURN')
        self.assertEqual(ledger[6]['exit_reason'],'ALREADY_ARMED_EXECUTABLE_BID_FLOOR')
        self.assertGreater(ledger[2]['net_pnl'],0)
        self.assertGreater(ledger[5]['net_pnl'],0)
        self.assertGreater(ledger[6]['net_pnl'],0)


if __name__=='__main__':unittest.main()
