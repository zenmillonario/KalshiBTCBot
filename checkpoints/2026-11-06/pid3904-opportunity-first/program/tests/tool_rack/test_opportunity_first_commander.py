"""Opportunity-first admission, physical state and exact source controls.

The generated unit trajectories below are explicitly synthetic. Recorded
PID3904 inputs are causal source projections with their original row hashes;
neither their recorded outcomes nor future frames are candidate inputs. These
are admission/state controls, never replacement executions or a P&L replay.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import gzip
import json
from pathlib import Path
import unittest

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import physical_entry_candidates
from strategy_core.opportunity_first import OpportunityBook, current_parent, main_runway, real_heist
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from strategy_core.paper_execution import nominal_taker_fee
from strategy_core.tools.management import mission_collection_evidence


def real_heist_snapshot(t=1000., *, age=400., visit="LOWER2", price=91.):
    """Explicit numeric, source-current repeated-range unit premise."""
    g={"epoch_ms":t*1000,"btc_price":price,"ema9":95.,"ema30":97.,
       "range60":20.,"range180":25.,"btc_change6":2.,"btc_change9":3.,
       "btc_change30":1.,"btc_change60":-2.,"ema9_change6":.4,
       "ema9_change30":.2,"ema9_change60":-.4,"connection_epoch":1,
       "arc_origin_observed":True,"arc_id":"DOWN1","arc_direction":"DOWN",
       "parent_direction":"DOWN","arc_age_sec":180.,"arc_start_ms":(t-180)*1000,
       "arc_amplitude":15.,"arc_prominence_threshold":3.}
    proof={"window_start_ms":(t-300)*1000,"window_end_ms":t*1000,
       "strict_source_times":True,"single_connection_epoch":True,"connection_epoch":1,
       "lower":90.,"upper":110.,"edge_tolerance":2.,"tight_box":True,
       "heist_environment":True,"compression":True,"parallel_emas":True,
       "lower_visits":2,"upper_visits":2,"center_traversals":2,
       "repeatability_visits":[{"zone":z,"epoch_ms":(t-300+i*40)*1000}
           for i,z in enumerate(("LOWER","CENTER","UPPER","CENTER","LOWER","UPPER"))]}
    md={"physical_current":True,"geometry_last_epoch_ms":t*1000,
       "geometry_continuity_generation":0,"current_geometry":g,
       "heist":{"qualified_box":True,"lower":90.,"upper":110.,"edge_tolerance":2.,
           "at_lower_edge":True,"at_upper_edge":False,"current_zone":"LOWER",
           "visit_id":visit,"box_id":"SYNTHETIC_BOX","repeatability_proof":proof},
       "tp_geometry":{"target":100.,"remaining_seconds":900-age,"target_between_ema9_ema30":False},
       "mountain":{"owner_side":"NO","source_ms":t*1000,"current_arc_id":"DOWN1",
           "retreat_threshold":2.,"owner_extreme_btc":89.,"edge_extreme_ms":(t-10)*1000}}
    return MarketSnapshot(now_ts=t,ticker="SYNTHETIC_HEIST",contract_age_s=age,
        yes_ask=.25,no_ask=.76,yes_bid=.24,no_bid=.75,metadata=md)


def heist_intent(s, *, opportunity="SYNTHETIC_H1"):
    return ToolIntent(tool="MARKET_HEIST",territory_id="H",lane=Lane.TACTICAL,
        side=Side.YES,action=Action.ENTER,opportunity_id=opportunity,max_price=.35,
        size_tier=10.,reason="HEIST_OUTER_EDGE_TACTICAL_RENTER",source_time=s.now_ts,
        metadata={"visit_id":s.metadata["heist"]["visit_id"],"position_role":"TACTICAL"})


def parent_snapshot(t=1000., *, price=120., age=400., ask=.25,
                    child="UP1", direction="UP", extreme=None, child_start=800.):
    """Continuous numeric parent/child packet for entire unit trajectories."""
    g={"epoch_ms":t*1000,"btc_price":price,"ema9":price-1.,"ema30":price-4.,
       "range60":20.,"range180":50.,"btc_change6":8.,"btc_change9":10.,
       "btc_change30":12.,"btc_change60":30.,"ema9_change6":1.6,
       "ema9_change30":2.4,"ema9_change60":6.,"connection_epoch":1,
       "arc_origin_observed":True,"arc_id":child,"arc_direction":direction,
       "current_native_direction":direction,"parent_direction":"UP",
       "arc_age_sec":t-child_start,"arc_start_ms":child_start*1000,
       "arc_amplitude":20.,"arc_prominence_threshold":3.}
    md={"source":"DIRECT_BTC_AND_NATIVE_KALSHI","physical_current":True,
       "geometry_last_epoch_ms":t*1000,"geometry_continuity_generation":0,
       "current_geometry":g,"tp_geometry":{"target":100.,"remaining_seconds":900-age,
           "contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"YES",
           "observed_target_side":"YES","required_move_to_target_btc":0.,
           "target_between_ema9_ema30":False},
       "mission_context":{"current":True,"source_ms":t*1000,"continuity_generation":0,
           "parent":{"id":"P1","side":"YES","status":"ACTIVE","supported":True,
               "invalidated":False,"source_ms":t*1000,"known_ms":600000.,"origin_ms":600000.,
               "continuity_generation":0,"basis":"OBSERVED_COMPARISON_ENVELOPE"}},
       "mountain":{"owner_side":"YES" if direction=="UP" else "NO",
           "source_ms":t*1000,"current_arc_id":child,"owner_extreme_btc":price if extreme is None else extreme,
           "edge_extreme_ms":t*1000,"retreat_threshold":3.,"spent_edge":False,
           "parent_structure":{"parent_id":"E1","parent_side":"YES","parent_age_s":t-600.,
               "parent_terminal_ready":False}}}
    return MarketSnapshot(now_ts=t,ticker="SYNTHETIC_PARENT",contract_age_s=age,
        yes_ask=ask,no_ask=.76,yes_bid=ask-.01,no_bid=.75,metadata=md)


def typed_intent(raw):
    return ToolIntent(**{**raw,"action":Action(raw["action"]),"lane":Lane(raw["lane"]),
                         "side":Side(raw["side"]) if raw.get("side") else None})


def source_snapshot(raw):
    status=raw["source_status"]
    return MarketSnapshot(now_ts=raw["now_ts"],ticker=raw["ticker"],
        contract_age_s=raw["contract_age_s"],metadata=raw["physical_metadata"],
        quote_current=status.get("book_current") is True,
        depth_available=status.get("entry_quote_available") is True,**raw["book_top"])


def synthetic_frozen_return_lifecycle():
    """Exact recorded entry, then explicitly synthetic path and executable mark.

    This management premise is not a historical fill, later path or P&L replay.
    """
    from tests.tool_rack.test_pid14156_heist_territory_transfer import case
    source_snapshot, original_intents = case(4285)
    commander = OneCommander()
    admission = commander.decide_entry(original_intents, source_snapshot, {})
    assert admission.action is Action.ENTER, admission
    intent = admission.intent
    now = source_snapshot.now_ts + 60.
    source = now * 1000.
    origin = (source_snapshot.now_ts + 1.) * 1000.
    target = intent.metadata['mission']['destination']['btc']
    btc = target + 1.
    generation = intent.metadata['mission']['continuity_generation']
    scope = 'EXPLICIT_SYNTHETIC_RETURN'
    geometry = {
        'epoch_ms': source, 'btc_price': btc, 'ema9': target + 5.,
        'ema30': target + 10., 'arc_id': scope, 'arc_direction': 'UP',
        'parent_direction': 'DOWN', 'arc_start_ms': origin,
        'arc_known_ms': origin, 'arc_origin_observed': True,
        'btc_change6': -1., 'btc_change9': -1., 'btc_change30': -1.,
        'ema9_change6': 0., 'ema9_change30': 0.,
    }
    mountain = {
        'source_ms': source, 'current_arc_id': scope, 'owner_side': 'YES',
        'current_btc': btc, 'arc_origin_ms': origin,
        'arc_origin_observed': True, 'contact_width': 1.,
        'owner_extreme_btc': target + 3., 'edge_extreme_ms': source - 13000.,
        'current_path_coverage': {
            'complete_observed_path': True, 'source_continuous': True,
            'endpoints_are_actual_observations': True, 'origin_observed': True,
            'first_source_ms': origin, 'last_source_ms': source,
        },
        'current_motion': {
            str(seconds): {
                'covered': True, 'source_continuous': True,
                'endpoints_are_actual_observations': True, 'source_ms': source,
                'current_price': btc, 'start_source_ms': source - seconds * 1000.,
                'first_price': btc + 1.,
            }
            for seconds in (6, 12)
        },
        'mature_edge': False, 'terminal_evidence_qualified': False,
        'edge_window_active': False, 'strong_active_release': False,
    }
    metadata = {
        'physical_current': True, 'geometry_last_epoch_ms': source,
        'geometry_continuity_generation': generation,
        'current_geometry': geometry, 'mountain': mountain,
        'mission_context': {
            'current': True, 'source_ms': source,
            'continuity_generation': generation,
            'local': {
                'arc_id': scope, 'scope_id': scope, 'side': 'YES',
                'origin_ms': origin, 'known_ms': origin,
                'terminal': {'qualified': False},
            },
        },
        'quote_id': 'SYNTHETIC_QUOTE', 'quote_observed_ts': now,
    }
    position = {
        'position_id': 'SYNTHETIC', 'ticker': source_snapshot.ticker,
        'side': 'YES', 'tool': intent.tool, 'territory_id': intent.territory_id,
        'opportunity_id': intent.opportunity_id, 'lane': intent.lane,
        'position_role': 'TACTICAL', 'entry_metadata': deepcopy(intent.metadata),
        'entry_reason': intent.reason, 'entry_time': source_snapshot.now_ts,
        'close_ts': now + 500., 'entry_price': .13, 'qty': 10, 'cost': 1.3,
        'entry_fee_remaining': .08, 'custody_state': 'NORMAL',
    }
    exit_fee = nominal_taker_fee(10, .2)
    net = Decimal('2') - Decimal('1.3') - Decimal('.08') - exit_fee
    metadata['native_depth'] = {
        'ticker': source_snapshot.ticker, 'quote_id': 'SYNTHETIC_QUOTE',
        'yes_bids': [[.2, 100]], 'no_bids': [[.79, 100]],
    }
    metadata['paper_execution_state'] = {'journal_seq': 1, 'journal_sha256': 'a' * 64}
    metadata['paper_exit_mark'] = {
        'version': 'PAPER_REMAINING_EXIT_MARK_V1', 'current': True,
        'remaining_depth_applied': True, 'position_id': 'SYNTHETIC',
        'ticker': source_snapshot.ticker, 'side': 'YES',
        'quote_id': 'SYNTHETIC_QUOTE', 'quote_observed_ts': now,
        'evaluated_at': now, 'quantity': 10, 'cost': 1.3,
        'entry_fee_remaining': .08, 'journal_seq': 1,
        'journal_sha256': 'a' * 64, 'used_bid_levels': {},
        'full_quantity_visible': True, 'full_lot_bid': .2,
        'exit_fee': float(exit_fee), 'net_after_fees': float(net),
    }
    snapshot = replace(source_snapshot, now_ts=now,
        contract_age_s=source_snapshot.contract_age_s + 60.,
        yes_bid=.2, yes_ask=.21, yes_sell_allowed=True, metadata=metadata)
    return commander, admission, position, snapshot


class SharedPositiveAdmissionTests(unittest.TestCase):
    def test_earned_local_return_binds_frozen_tactical_destination_not_main(self):
        from tests.tool_rack.test_pid14156_heist_territory_transfer import case
        s,intents=case(4285);original=deepcopy(intents[0]);c=OneCommander()
        d=c.decide_entry(intents,s,{})
        self.assertIs(d.action,Action.ENTER,d)
        self.assertEqual(d.intent.metadata['position_role'],'TACTICAL')
        self.assertIs(d.intent.lane,Lane.TACTICAL)
        mission=d.intent.metadata['mission'];self.assertEqual(mission['purpose'],'TACTICAL_RETURN')
        self.assertEqual(mission['destination']['kind'],'EMA9_RETURN')
        self.assertEqual(mission['destination']['btc'],s.metadata['current_geometry']['ema9'])
        self.assertTrue(mission['destination']['frozen_at_entry'])
        self.assertEqual(d.intent.metadata['floor_policy'],original.metadata['floor_policy'])
        self.assertEqual((d.intent.max_price,d.intent.size_tier),(original.max_price,original.size_tier))
        self.assertEqual(c._resolve_entry_custody(d.intent,s),d.intent)
        self.assertEqual(intents[0],original)

    def test_real_repeated_heist_is_positive_and_input_is_immutable(self):
        s=real_heist_snapshot(); i=heist_intent(s); original=deepcopy(i)
        d=OneCommander().decide([i],s)
        self.assertIs(d.action,Action.ENTER,d)
        self.assertEqual(d.intent.metadata["commander_opportunity"]["species"],"REAL_HEIST_RETURN")
        self.assertEqual(i,original)
        self.assertEqual((d.intent.max_price,d.intent.size_tier),(.35,10.))

    def test_wide_box_or_primary_label_cannot_replace_repeated_walls(self):
        s=real_heist_snapshot();md=deepcopy(s.metadata)
        md["heist"]["repeatability_proof"]["upper_visits"]=1
        s=replace(s,metadata=md); i=heist_intent(s)
        for family in (None,"MOUNTAIN_EDGE","EDGE_HEIST","QUOTE_WAVE_SCALP"):
            candidate=i if family is None else replace(i,metadata={**i.metadata,
                "commander_primary_candidate":True,"commander_candidate_family":family})
            d=OneCommander().decide([candidate],s)
            self.assertIs(d.action,Action.WAIT,(family,d))

    def test_source_missing_stale_mixed_generation_and_future_visits_cannot_enter(self):
        base=real_heist_snapshot()
        mutations=(lambda md:md.pop("geometry_continuity_generation"),
           lambda md:md.update(geometry_last_epoch_ms=999000.),
           lambda md:md.update(physical_current=False),
           lambda md:md["heist"]["repeatability_proof"]["repeatability_visits"][0].update(epoch_ms=1000001.))
        for mutate in mutations:
            md=deepcopy(base.metadata);mutate(md);s=replace(base,metadata=md)
            self.assertIs(OneCommander().decide([heist_intent(s)],s).action,Action.WAIT)
        stale=replace(base,now_ts=1004.)
        self.assertIs(OneCommander().decide([heist_intent(stale)],stale).action,Action.WAIT)

    def test_rejected_nonfinite_quote_audit_is_json_safe_and_detached(self):
        s=replace(real_heist_snapshot(),yes_ask=float('nan'));c=OneCommander()
        self.assertIs(c.decide([heist_intent(s)],s).action,Action.WAIT)
        review=c.opportunity_review;json.dumps(review,allow_nan=False)
        review['main_alignment']['reason']='CALLER_MUTATED_COPY'
        self.assertNotEqual(c.opportunity_review['main_alignment']['reason'],'CALLER_MUTATED_COPY')

    def test_exact_junction_is_wait_even_when_heist_label_is_qualified(self):
        s=real_heist_snapshot();md=deepcopy(s.metadata);md["tp_geometry"]["target_between_ema9_ema30"]=True
        s=replace(s,metadata=md)
        self.assertEqual(OneCommander().decide([heist_intent(s)],s).reason,"OPPORTUNITY_TP_EMA_JUNCTION_WAIT")

    def test_lower_wall_label_cannot_buy_middle_or_wrong_actual_edge(self):
        s=real_heist_snapshot(price=105.)
        self.assertTrue(s.metadata['heist']['at_lower_edge'])
        self.assertIs(OneCommander().decide([heist_intent(s)],s).action,Action.WAIT)

    def test_book_callbacks_do_not_create_physical_watch_samples(self):
        c=OneCommander();s=parent_snapshot();c.decide([],s)
        first=c.opportunity_review["watches"][0]
        for n in range(1,9):c.decide([],replace(s,now_ts=s.now_ts+n*.1,yes_ask=.20+n*.001))
        current=c.opportunity_review["watches"][0]
        self.assertEqual(current["identity"],first["identity"])
        self.assertEqual(current["distinct_source_samples"],1)

    def test_filled_heist_visit_cannot_respray_but_new_visit_is_independent(self):
        c=OneCommander();s=real_heist_snapshot();d=c.decide([heist_intent(s)],s)
        c.mark_entry_filled(d.intent,ticker=s.ticker)
        self.assertIs(c.decide([heist_intent(s,opportunity="RENAMED")],s).action,Action.WAIT)
        next_s=real_heist_snapshot(t=1010.,visit="LOWER3")
        self.assertIs(c.decide([heist_intent(next_s,opportunity="NEW_VISIT")],next_s).action,Action.ENTER)


class FrozenLocalReturnCustodyTests(unittest.TestCase):
    def test_observed_exhausted_frozen_destination_exits_without_adviser_authority(self):
        commander, admission, position, snapshot = synthetic_frozen_return_lifecycle()
        original_position, original_metadata = deepcopy(position), deepcopy(snapshot.metadata)
        proof = mission_collection_evidence(position, snapshot)
        self.assertTrue(proof['collection_qualified'])
        self.assertEqual(proof['collection_authority'], 'TACTICAL_DESTINATION_EXHAUSTED')
        self.assertFalse(proof['terminal_qualified'])
        for action in (None, Action.HOLD, Action.EXIT):
            advice = [] if action is None else [replace(admission.intent, action=action,
                reason='EXPLICIT_SYNTHETIC_ADVISER_OPINION', source_time=snapshot.now_ts,
                max_price=None, size_tier=None)]
            decision = commander.decide_position(advice, snapshot, position)
            self.assertIs(decision.action, Action.EXIT, decision)
            self.assertEqual(decision.reason, 'COMMANDER_ACCEPTED_EXACT_HELD_SIDE_EXIT')
            self.assertEqual(decision.intent.reason, 'TACTICAL_DESTINATION_EXHAUSTED')
            self.assertEqual(decision.custody_update['state'], 'EXIT_PENDING')
            sale = decision.intent.metadata['commander_local_return_collection']['tactical_full_lot_sale']
            self.assertTrue(sale['remaining_depth_mark_valid'])
            self.assertEqual(sale['quantity'], position['qty'])
            self.assertGreater(sale['net_after_fees'], 0.)
        self.assertEqual(position, original_position)
        self.assertEqual(snapshot.metadata, original_metadata)

    def test_before_target_and_still_advancing_remain_local_holds(self):
        for scenario in ('BEFORE_TARGET', 'STILL_ADVANCING'):
            with self.subTest(scenario=scenario):
                commander, _, position, snapshot = synthetic_frozen_return_lifecycle()
                md = deepcopy(snapshot.metadata)
                if scenario == 'BEFORE_TARGET':
                    btc = position['entry_metadata']['mission']['destination']['btc'] - 1.
                    md['current_geometry']['btc_price'] = btc
                    md['mountain']['current_btc'] = btc
                    for motion in md['mountain']['current_motion'].values():
                        motion.update(current_price=btc, first_price=btc + 1.)
                else:
                    for motion in md['mountain']['current_motion'].values():
                        motion['first_price'] = motion['current_price'] - 1.
                snapshot = replace(snapshot, metadata=md)
                decision = commander.decide_position([], snapshot, position)
                self.assertIs(decision.action, Action.HOLD, decision)
                self.assertIsNone(decision.custody_update)
                scoped = decision.intent.metadata['commander_local_return_collection']
                self.assertFalse(scoped['collection_qualified'])
                self.assertEqual(scoped['destination_reached'], scenario == 'STILL_ADVANCING')
                self.assertEqual(decision.reason, 'TACTICAL_RETURN_STILL_ADVANCING_OR_END_UNPROVEN')

    def test_stale_foreign_or_mixed_proof_cannot_fall_through_to_unrelated_child_terminal(self):
        for scenario in ('STALE_CLOCK', 'FOREIGN_LOCAL', 'FOREIGN_MARK', 'MIXED_GENERATION',
                         'STALE_CONTEXT', 'MIXED_SOURCE', 'INCOMPLETE_PATH'):
            with self.subTest(scenario=scenario):
                commander, _, position, snapshot = synthetic_frozen_return_lifecycle()
                md = deepcopy(snapshot.metadata)
                source = md['current_geometry']['epoch_ms']
                md['mountain'].update(mature_edge=True, terminal_evidence_qualified=True,
                    edge_window_active=True, edge_id='UNRELATED:' + str(int(source - 1000.)))
                if scenario == 'STALE_CLOCK':
                    snapshot = replace(snapshot, now_ts=snapshot.now_ts + 10.)
                elif scenario == 'FOREIGN_LOCAL':
                    md['mission_context']['local']['scope_id'] = 'FOREIGN_RETURN'
                elif scenario == 'FOREIGN_MARK':
                    md['paper_exit_mark']['position_id'] = 'FOREIGN_POSITION'
                elif scenario == 'MIXED_GENERATION':
                    md['mission_context']['continuity_generation'] += 1
                elif scenario == 'STALE_CONTEXT':
                    md['mission_context']['current'] = False
                elif scenario == 'MIXED_SOURCE':
                    md['mountain']['source_ms'] -= 1000.
                else:
                    md['mountain']['current_path_coverage']['complete_observed_path'] = False
                decision = commander.decide_position([], replace(snapshot, metadata=md), position)
                self.assertIs(decision.action, Action.HOLD, decision)
                scoped = decision.intent.metadata['commander_local_return_collection']
                self.assertFalse(scoped['collection_qualified'])
                self.assertIsNone(decision.custody_update)

    def test_collection_requires_current_positive_net_for_the_full_remaining_lot(self):
        for scenario in ('MISSING_MARK', 'WRONG_QUANTITY', 'QUOTE_CHANGED', 'DEPTH_CONSUMED',
                         'JOURNAL_CHANGED', 'NEGATIVE_NET', 'LEGACY_COLLECTION_POLICY'):
            with self.subTest(scenario=scenario):
                commander, _, position, snapshot = synthetic_frozen_return_lifecycle()
                md = deepcopy(snapshot.metadata)
                mark = md['paper_exit_mark']
                if scenario == 'MISSING_MARK':
                    md.pop('paper_exit_mark')
                elif scenario == 'WRONG_QUANTITY':
                    mark['quantity'] -= 1
                elif scenario == 'QUOTE_CHANGED':
                    mark['quote_id'] = 'FOREIGN_QUOTE'
                elif scenario == 'DEPTH_CONSUMED':
                    mark['used_bid_levels'] = {'0.2': 95}
                elif scenario == 'JOURNAL_CHANGED':
                    md['paper_execution_state']['journal_seq'] += 1
                elif scenario == 'LEGACY_COLLECTION_POLICY':
                    position['entry_metadata']['mission']['collection_policy'] = 'LEGACY'
                else:
                    position['cost'] = mark['cost'] = 2.
                    mark['net_after_fees'] = -.20
                decision = commander.decide_position([], replace(snapshot, metadata=md), position)
                self.assertIs(decision.action, Action.HOLD, decision)
                if scenario == 'LEGACY_COLLECTION_POLICY':
                    self.assertEqual(decision.reason, 'COMMANDER_LOCAL_RETURN_COLLECTION_POLICY_REQUIRED')
                    continue
                self.assertEqual(decision.reason, 'TACTICAL_FULL_LOT_POSITIVE_NET_BID_REQUIRED')
                scoped = decision.intent.metadata['commander_local_return_collection']
                self.assertTrue(scoped['tactical_return_proof']['destination_exhausted'])
                self.assertFalse(scoped['tactical_full_lot_sale']['qualified'])
                if scenario == 'NEGATIVE_NET':
                    self.assertTrue(scoped['tactical_full_lot_sale']['remaining_depth_mark_valid'])
                    self.assertLess(scoped['tactical_full_lot_sale']['net_after_fees'], 0.)

    def test_floor_manual_stop_recovery_and_finality_keep_prior_authority(self):
        commander, _, position, snapshot = synthetic_frozen_return_lifecycle()
        for kwargs, expected in (({'floor_breached': True}, 'ALREADY_ARMED_EXECUTABLE_BID_FLOOR'),
                                 ({'stop_requested': True}, 'OPERATOR_PAPER_STOP')):
            decision = commander.decide_position([], snapshot, position, **kwargs)
            self.assertIs(decision.action, Action.EXIT)
            self.assertEqual(decision.intent.reason, expected)
            self.assertTrue(decision.intent.metadata['objective_exit'])
        unavailable = commander.decide_position([], replace(snapshot, quote_current=False),
            position, floor_breached=True)
        self.assertIs(unavailable.action, Action.WAIT)
        self.assertEqual(unavailable.reason, 'OBJECTIVE_QUOTE_STALE_EXIT_PENDING')
        review = {'position_id': position['position_id'], 'previous_state': 'NORMAL',
            'reviewed_at': snapshot.now_ts, 'action': 'HOLD', 'reason': 'SYNTHETIC_QUALIFIED_RECOVERY',
            'next_state': 'LAZARUS', 'hard_exit': False}
        recovered = commander.decide_position([], snapshot, position, recovery_review=review)
        self.assertIs(recovered.action, Action.HOLD)
        self.assertEqual(recovered.custody_update['state'], 'LAZARUS')
        self.assertEqual(recovered.intent.reason, review['reason'])
        finalized = commander.decide_position([], replace(snapshot, now_ts=position['close_ts']), position)
        self.assertEqual(finalized.reason, 'EXACT_CONTRACT_AWAITING_OFFICIAL_FINALITY')
        md = deepcopy(snapshot.metadata); md['physical_current'] = False
        stale = commander.decide_position([], replace(snapshot, metadata=md), position)
        self.assertEqual(stale.reason, 'PHYSICAL_SOURCE_STALE_CUSTODY_UNCHANGED')

    def test_local_seed_families_reach_destination_consumer_but_keep_their_time_limit(self):
        for family in ('EDGE_HEIST', 'QUOTE_WAVE_SCALP'):
            with self.subTest(family=family):
                commander, _, position, snapshot = synthetic_frozen_return_lifecycle()
                position['entry_metadata']['commander_candidate_family'] = family
                decision = commander.decide_position([], snapshot, position)
                self.assertIs(decision.action, Action.EXIT, decision)
                self.assertEqual(decision.intent.reason, 'TACTICAL_DESTINATION_EXHAUSTED')
                later = replace(snapshot, now_ts=position['entry_time'] + 200.)
                expired = commander.decide_position([], later, position)
                self.assertIs(expired.action, Action.EXIT, expired)
                self.assertEqual(expired.intent.reason, family + '_MAX_HOLD_EXIT')

    def test_promoted_main_does_not_reuse_its_old_frozen_local_target(self):
        commander, _, position, snapshot = synthetic_frozen_return_lifecycle()
        position.update(custody_state='PROMOTED_MAIN', position_role='PRIMARY', lane=Lane.MAIN)
        decision = commander.decide_position([], snapshot, position)
        self.assertIs(decision.action, Action.HOLD, decision)
        self.assertNotIn('commander_local_return_collection', decision.intent.metadata)
        self.assertNotEqual(decision.intent.reason, 'TACTICAL_DESTINATION_EXHAUSTED')


class PhysicalOpportunitySequenceTests(unittest.TestCase):
    def test_same_child_reextension_cancels_pending_return_without_new_identity(self):
        book=OpportunityBook();s=parent_snapshot(price=120.,extreme=120.)
        book.observe(s);identity=book.review["watches"][-1]["identity"]
        book.observe(parent_snapshot(t=1010.,price=115.,extreme=120.))
        book.observe(parent_snapshot(t=1020.,price=125.,extreme=125.))
        w=book.review["watches"][-1]
        self.assertEqual(w["identity"],identity);self.assertEqual(w["reextensions"],1)
        self.assertIn("REEXTENSION",w["reason"]);self.assertEqual(w["state"],"PREPARE")

    def test_completed_retreat_then_new_child_creates_distinct_excursion_same_parent(self):
        book=OpportunityBook();book.observe(parent_snapshot(price=120.,extreme=120.))
        old=book.review["watches"][-1]["identity"]
        # Completed physical opposite child; a new quote or new extreme alone
        # cannot supply these distinct source-time observations.
        book.observe(parent_snapshot(t=1020.,price=108.,direction="DOWN",child="DOWN2",child_start=1010.))
        book.observe(parent_snapshot(t=1050.,price=124.,direction="UP",child="UP3",child_start=1030.))
        up=[w for w in book.review["watches"] if w["parent_side"]=="YES"]
        self.assertEqual(len(up),2);self.assertNotEqual(up[-1]["identity"],old)
        self.assertTrue(up[0]["completed_return_observed"])

    def test_breakout_cancels_counterwatch(self):
        book=OpportunityBook();s=parent_snapshot();book.observe(s)
        md=deepcopy(parent_snapshot(t=1010.,price=126.).metadata);md["mountain"]["strong_active_release"]=True
        book.observe(replace(parent_snapshot(t=1010.,price=126.),metadata=md))
        self.assertEqual(book.review["watches"][-1]["state"],"WAIT")
        self.assertEqual(book.review["watches"][-1]["reason"],"DIRECTIONAL_BREAKOUT_CANCELLED_COUNTERWATCH")

    def test_main_value_search_observes_dip_then_current_rejoin_without_adviser(self):
        c=OneCommander();c.physical_entry_candidates(parent_snapshot(price=120.))
        c.physical_entry_candidates(parent_snapshot(t=1010.,price=110.))
        s=parent_snapshot(t=1020.,price=116.,age=470.)
        candidates=c.physical_entry_candidates(s)
        main=[i for i in candidates if i.reason=="COMMANDER_OPPORTUNITY_MAIN_EMA9_VALUE_REJOIN"]
        self.assertEqual(len(main),1,c.opportunity_review)
        d=c.decide_entry(main,s,{})
        self.assertIs(d.action,Action.ENTER,d)
        self.assertEqual((d.intent.max_price,d.intent.size_tier),(.35,10.))
        self.assertEqual(c.opportunity_review["cadence"],"SECOND_HALF_ALIGNMENT_REVIEW")
        self.assertTrue(c.opportunity_review["main_alignment"]["qualified"])

    def test_missed_expensive_dip_expires_on_new_high_and_cheap_midleg_does_not_revive(self):
        b=OpportunityBook();b.observe(parent_snapshot(price=120.))
        b.observe(parent_snapshot(t=1010.,price=110.,ask=.55))
        self.assertIsNone(b.main_candidate(parent_snapshot(t=1020.,price=116.,ask=.55)))
        b.observe(parent_snapshot(t=1030.,price=120.,ask=.55))
        self.assertIsNone(b._main_dip)
        self.assertIsNone(b.main_candidate(parent_snapshot(t=1040.,price=121.,ask=.25)))

    def test_normal_main_cannot_skip_first_five_minutes(self):
        c=OneCommander();c.physical_entry_candidates(parent_snapshot(price=120.,age=200.))
        c.physical_entry_candidates(parent_snapshot(t=1010.,price=110.,age=210.))
        s=parent_snapshot(t=1020.,price=116.,age=220.)
        rail=ToolIntent(tool="RAIL",territory_id="R",lane=Lane.MAIN,side=Side.YES,
            action=Action.ENTER,opportunity_id="R1",max_price=.35,size_tier=10.,
            reason="RAIL_MAIN_VALUE",source_time=s.now_ts,metadata={"ema9_dip_value":{"eligible":True}})
        self.assertEqual(c.decide([rail],s).reason,"OPPORTUNITY_MAIN_OBSERVE_UNTIL_300S")

    def test_actual_target_distance_overrules_favorable_shape_label(self):
        s=parent_snapshot(age=780.);md=deepcopy(s.metadata)
        md["tp_geometry"].update(target=227.,remaining_seconds=120.,required_move_to_target_btc=0.)
        ok,proof=main_runway(replace(s,metadata=md),Side.YES)
        self.assertFalse(ok);self.assertEqual(proof["actual_target_side"],"NO")
        self.assertEqual(proof["remaining_move_btc"],107.)
        self.assertFalse(proof["shape_label_is_settlement_ownership"])

    def test_parent_age_never_restarts_with_new_child_comparison_envelope(self):
        s=parent_snapshot();md=deepcopy(s.metadata);md["mountain"]["parent_structure"]["parent_age_s"]=45.
        p=current_parent(replace(s,metadata=md))
        self.assertEqual(p["parent_age_s"],400.);self.assertEqual(p["comparison_envelope_age_s"],45.)
        md['mission_context']['parent']['supported']=False
        still_known=current_parent(replace(s,metadata=md))
        self.assertEqual(still_known['id'],'P1')
        self.assertEqual(still_known['parent_age_s'],400.)


class PID3904SourceSequenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=Path(__file__).parent/"fixtures/pid3904_opportunity_sequences.json.gz"
        cls.data=json.load(gzip.open(path,"rt",encoding="utf-8"))

    def test_original_input_hashes_and_no_outcomes_in_candidate_projection(self):
        self.assertEqual(self.data["original_archive_sha256"],
            "ef711c357a903e0c39d20b2b9179d8c8b7aa00a2ba8febb8f89ed716261d78b6")
        for r in self.data["frames"].values():
            self.assertEqual(len(r["source_row_sha256"]),64)
            self.assertNotIn("decisions",r);self.assertNotIn("ledger",r)

    def test_recorded_mountain_reextension_sequence_is_one_unpaid_watch(self):
        c=OneCommander();identities={};denials={}
        for n in self.data["mountain_window_order"]:
            r=self.data["frames"][str(n)];s=source_snapshot(r)
            candidates=c.physical_entry_candidates(s)
            c.decide_entry(candidates,s,{})
            if n in (2932,3192):
                self.assertFalse(any(i.side is Side.NO for i in candidates))
                w=next(w for w in c.opportunity_review["watches"]
                    if w["origin_child_id"]=="G000A000015" and w["parent_side"]=="YES")
                identities[n]=w["identity"]
                denials[n]=[p["reason"] for p in c.opportunity_review["candidates"]]
        self.assertEqual(set(identities),{2932,3192});self.assertEqual(identities[2932],identities[3192])
        self.assertTrue(all("OPPORTUNITY_MOUNTAIN_PARENT_TERMINAL_PROOF_REQUIRED" in v for v in denials.values()))

    def test_original_opening_and_wide_only_heists_do_not_gain_authority_from_pnl(self):
        for n in (1082,4928,6295,6466):
            with self.subTest(sequence=n):
                r=self.data["frames"][str(n)];s=source_snapshot(r)
                intents=[typed_intent(i) for i in r["candidate_intents"]]
                self.assertTrue(intents)
                d=OneCommander().decide_entry(intents,s,{})
                self.assertIs(d.action,Action.WAIT,d)
        first=source_snapshot(self.data["frames"]["1082"])
        self.assertTrue(real_heist(first)[0])  # Geometry preserved; opening trigger still lacks proof.

    def test_exact_second_half_target_review_names_actual_side_and_reason(self):
        r=self.data["frames"]["5785"];s=source_snapshot(r);c=OneCommander()
        c.decide_entry(c.physical_entry_candidates(s),s,{})
        review=c.opportunity_review
        self.assertEqual(review["main_alignment"]["target_side"],"NO")
        self.assertEqual(review["main_alignment"]["descriptive_shape_side"],"YES")
        self.assertEqual(review["source_ms"],s.metadata["current_geometry"]["epoch_ms"])
        self.assertIsInstance(review["main_alignment"]["reason"],str)
        json.dumps(review,allow_nan=False)


class PID18244ExactPositiveSequenceTests(unittest.TestCase):
    def test_original_upper_rejection_remains_admitted_on_exact_source_order(self):
        path=Path(__file__).parent/"fixtures/pid18244_opportunity_source_sequence.json.gz"
        data=json.load(gzip.open(path,"rt",encoding="utf-8"))
        self.assertEqual(data["original_archive_sha256"],
            "2600a6273a54ee1831f6ba40aced24b998cbd6c1f3b142dfd495ac8804bb9b12")
        self.assertEqual(len(data["frames"]),67)
        c=OneCommander();decision=None
        # Use every captured predecessor in this bounded source window, stop
        # at the proposal. Later prices/outcomes cannot inform this decision.
        for n in data["order"]:
            if n>8122:break
            r=data["frames"][str(n)];s=source_snapshot(r)
            c.physical_entry_candidates(s)
            candidates=[typed_intent(i) for i in r["candidate_intents"]]
            current=c.decide_entry(candidates,s,{})
            if n==8122:decision=current
        self.assertIsNotNone(decision)
        self.assertIs(decision.action,Action.ENTER,decision)
        self.assertIs(decision.intent.side,Side.NO)
        self.assertEqual((decision.intent.max_price,decision.intent.size_tier),(.20,25.))
        proof=decision.intent.metadata["commander_opportunity"]
        self.assertEqual(proof["species"],"MOUNTAIN_RETURN")
        self.assertTrue(proof["evidence"]["current_terminal_with_comparable_maturity"])
        self.assertTrue(proof["evidence"]["defended_level_with_current_rejection"])
        runway=proof["evidence"]["return_runway"]
        self.assertEqual(runway["basis"],"PROVEN_RETURN_LEG_CAN_REACH_TP")
        self.assertLess(runway["required_total_runway_seconds"],runway["remaining_seconds"])
        self.assertAlmostEqual(proof["ask"],.087)
        self.assertEqual(proof["source_ms"],1793912081292.4841)


if __name__=="__main__":unittest.main()
