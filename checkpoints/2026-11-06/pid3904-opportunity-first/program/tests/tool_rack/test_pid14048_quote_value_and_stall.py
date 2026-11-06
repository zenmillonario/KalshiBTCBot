"""PID14048 source-bound discipline: value watch and a *current* near-peak harvest.

Recorded price/time values originate in the independently SHA-256 verified
PID14048 original; synthetic inputs below are decision-level fixtures, not
modified-engine tape replay or an assertion that alternate orders would fill.
"""
from __future__ import annotations

from copy import deepcopy
import unittest
from strategy_core.types import MarketSnapshot, ToolIntent, Action, Side, Lane
from strategy_core.commander import OneCommander
from strategy_core.custody_evidence import build_custody_evidence
from tests.tool_rack.test_opportunity_first_commander import real_heist_snapshot


def quote_snapshot(t:float, ask:float, *, ticker='KX-TEST', generation=7,
                   territory='MARKET_HEIST', physical=True, release=False,
                   history=None, side=Side.NO):
    if history is None:
        history=[(t-9,.19,'Q1'),(t-7,.21,'Q2'),(t-5,.20,'Q3'),(t-3,.22,'Q4'),(t,ask,'Q5')]
    series=[{'time':a,'ask':v,'quote_id':q} for a,v,q in history]
    # Quote timing is downstream of earned geometry. Supply an explicitly
    # synthetic repeated range with coherent source identity, rather than
    # treating the former bare qualified_box flag as entry authority.
    md=deepcopy(real_heist_snapshot(t,age=200.).metadata)
    if side is Side.NO:
        g=md['current_geometry']
        for key in ('btc_price','ema9','ema30'):
            g[key]=200.-g[key]
        for key in ('btc_change6','btc_change9','btc_change30','btc_change60',
                    'ema9_change6','ema9_change30','ema9_change60'):
            g[key]=-g[key]
        g.update(arc_id='SYNTHETIC_UP1',arc_direction='UP',parent_direction='UP')
        md['mountain'].update(owner_side='YES',current_arc_id='SYNTHETIC_UP1',owner_extreme_btc=111.)
        md['heist'].update(at_lower_edge=False,at_upper_edge=True,current_zone='UPPER',visit_id='UPPER2')
    md.update(physical_current=physical,geometry_continuity_generation=generation,
              commander_strategy={'owned_territory':territory},release_in_progress=release,
              quote_wave={'sides':{side.value:{'available':True,'series':series}}})
    md['mountain']['strong_active_release']=False
    return MarketSnapshot(now_ts=t,ticker=ticker,contract_age_s=200,
        yes_ask=ask if side is Side.YES else 1-ask,
        no_ask=ask if side is Side.NO else 1-ask,
        yes_bid=ask-.01 if side is Side.YES else 1-ask-.01,
        no_bid=ask-.01 if side is Side.NO else 1-ask-.01,
        quote_current=True,depth_available=True,entry_allowed=True,
        metadata=md)


def edge_intent(t=1000., *, side=Side.NO, mission='EDGE-A', cap=.4):
    return ToolIntent(tool='MARKET_HEIST',territory_id='MARKET_HEIST',lane=Lane.TACTICAL,
        side=side,action=Action.ENTER,opportunity_id=mission,max_price=cap,
        size_tier=10.,reason='HEIST_OUTER_EDGE_TACTICAL_RENTER',source_time=t,
        metadata={'physical_mission_id':mission})


def exit_position():
    return {'position_id':'P3','ticker':'KX-TEST','side':Side.YES,'position_role':'PRIMARY',
        'tool':'ONE_COMMANDER_PRIMARY','territory_id':'MOUNTAIN_CONTRACT_LEG',
        'opportunity_id':'M-3','lane':'MAIN','entry_price':.43,
        'entry_time':1000.,'close_ts':1900.,'peak_bid':.63,'floor_bid':None,
        'custody_state':'NORMAL',
        'entry_metadata':{'commander_candidate_family':'MOUNTAIN_CONTRACT_LEG'}}


def exit_snapshot(*, at=1100., bid=.60, btc9=-8.61, ema6=-1.956,
                  release=False,net=7.47,mature=True,full=True,available=True,
                  territory='ALTERNATING_MOUNTAIN',position_id='P3',physical=True):
    md={'physical_current':physical,'release_in_progress':release,
        'commander_strategy':{'owned_territory':territory,'owned_side':'YES'},
        'current_geometry':{'parent_direction':'UP','btc_change9':btc9,
                            'ema9_change6':ema6},
        'mountain':{'owner_side':'YES','mature_edge':mature,'edge_window_active':True,
                    'stall':True,'hesitation':False,'failed_reextension':False,
                    'strong_active_release':False},
        'paper_exit_mark':{'version':'PAPER_REMAINING_EXIT_MARK_V1',
                           'ticker':'KX-TEST','position_id':position_id,
                           'current':True,'full_quantity_visible':full,
                           'full_lot_bid':bid,'net_after_fees':net}}
    return MarketSnapshot(now_ts=at,ticker='KX-TEST',contract_age_s=at-1000,
                          yes_ask=bid+.01,no_ask=1-bid,
                          yes_bid=bid,no_bid=1-bid-.01,
                          quote_current=available,yes_sell_allowed=available,
                          no_sell_allowed=True,metadata=md)


class OriginalChronologyControls(unittest.TestCase):
    def test_complete_pid14048_recorded_sequence_is_unmodified(self):
        import gzip, json
        from pathlib import Path
        fixture=Path(__file__).with_name('fixtures')/'pid14048_full_sequence.json.gz'
        original=json.loads(gzip.decompress(fixture.read_bytes()))
        self.assertEqual(original['original_archive_sha256'],
            '31eea05ad08bae678bae1efaa5eb24053dc513f6d7987049d7a10aa7c2b97c05')
        frames=original['frames']
        self.assertEqual(len(frames),8179)
        self.assertEqual([r['seq'] for r in frames],list(range(1,8180)))
        self.assertTrue(all(frames[i]['prev_sha']==frames[i-1]['orig_sha']
                            for i in range(1,len(frames))))
        entry=[r for r in frames if r['entry_action'] in {'ENTER','RELAY'}]
        # The original ledger remains six? This run contains THREE booked entries;
        # do not reconstruct hypothetical market fills from this fixture.
        self.assertEqual(len(entry),3)
        self.assertTrue({'04:40:00','05:01:55','05:02:00'}
                        <=set(original['selected_frames']))

class QuoteValueWatchTests(unittest.TestCase):
    def test_earned_edge_brief_wait_then_improved_current_ask_enter(self):
        # Historical NO quote around 04:40:00 was 26c, ~1.1s later 24c.
        # This verifies a bounded policy decision, NOT a hypothetical buy.
        c=OneCommander();t=1000.
        i=edge_intent(t)
        a=c.decide_entry([i],quote_snapshot(t,.26),{})
        self.assertIs(a.action,Action.WAIT)
        self.assertEqual(a.reason,'COMMANDER_EARNED_EDGE_BRIEF_QUOTE_VALUE_WINDOW')
        history=[(t-9,.19,'Q1'),(t-7,.21,'Q2'),(t-5,.20,'Q3'),
                 (t-3,.22,'Q4'),(t,.26,'Q5'),(t+1.2,.24,'Q6')]
        b=c.decide_entry([edge_intent(t+1.2)],quote_snapshot(t+1.2,.24,history=history),{})
        self.assertIs(b.action,Action.ENTER)
        self.assertIs(b.intent.side,Side.NO)

    def test_no_infinite_wait_at_same_qualified_edge(self):
        c=OneCommander();t=1000.
        self.assertIs(c.decide_entry([edge_intent(t)],quote_snapshot(t,.26),{}).action,Action.WAIT)
        s=quote_snapshot(t+3,.26,history=[(t-9,.19,'Q1'),(t-7,.21,'Q2'),
            (t-5,.20,'Q3'),(t-3,.22,'Q4'),(t,.26,'Q5'),(t+3,.26,'Q6')])
        self.assertIs(c.decide_entry([edge_intent(t+3)],s,{}).action,Action.ENTER)

    def test_low_value_or_no_true_recent_oscillation_never_delays(self):
        c=OneCommander()
        cheap=quote_snapshot(1000,.19,history=[(991,.10,'1'),(993,.12,'2'),
                      (995,.14,'3'),(997,.16,'4'),(1000,.19,'5')])
        self.assertIs(c.decide_entry([edge_intent()],cheap,{}).action,Action.ENTER)
        flat=quote_snapshot(1000,.26,history=[(991,.24,'1'),(993,.24,'2'),
                      (995,.25,'3'),(997,.25,'4'),(1000,.26,'5')])
        self.assertIs(OneCommander().decide_entry([edge_intent()],flat,{}).action,Action.ENTER)

    def test_chapter_change_never_replays_an_old_value_watch(self):
        c=OneCommander();t=1000.
        self.assertIs(c.decide_entry([edge_intent(t)],quote_snapshot(t,.26),{}).action,Action.WAIT)
        n=c.decide_entry([edge_intent(t+1,mission='EDGE-B')],quote_snapshot(t+1,.26),{})
        self.assertIs(n.action,Action.WAIT)
        n=c.decide_entry([edge_intent(t+1)],quote_snapshot(t+1,.26,generation=8),{})
        self.assertIs(n.action,Action.WAIT)
        n=c.decide_entry([edge_intent(t+1)],quote_snapshot(t+1,.26,ticker='NEXT-15M'),{})
        self.assertIs(n.action,Action.WAIT)

    def test_no_adviser_quote_veto_when_release_or_no_current_quote(self):
        for kw in ({'release':True},{'territory':'DOWN_RAIL'},
                   {'physical':False}):
            with self.subTest(kw=kw):
                c=OneCommander();s=quote_snapshot(1000,.26,**kw)
                # Invoke the value watch itself: a stale physical source is
                # independently denied by objective Commander source checks.
                self.assertIsNone(c._entry_quote_value_wait(edge_intent(),s))

    def test_original_price_limit_and_quote_health_still_control(self):
        c=OneCommander();s=quote_snapshot(1000,.26)
        self.assertEqual(c.decide_entry([edge_intent(cap=.20)],s,{}).reason,
                         'OBJECTIVE_PRICE_MOVED_ABOVE_TOOL_LIMIT')
        s=quote_snapshot(1000,.26)
        s=MarketSnapshot(**{**vars(s),'quote_current':False})
        self.assertEqual(c.decide_entry([edge_intent()],s,{}).reason,'OBJECTIVE_QUOTE_STALE')


class MatureNearPeakCollectionTests(unittest.TestCase):
    def test_pid14048_050155_first_stall_while_nine_second_motion_positive_wait(self):
        e=build_custody_evidence(exit_position(),
            exit_snapshot(at=1095,bid=.60,btc9=11.59,ema6=-.904))
        self.assertFalse(e['mature_stall_near_peak_collect'])

    def test_pid14048_050200_mature_stall_after_current_btc_ema9_turn_collect(self):
        snap=exit_snapshot()
        evidence=build_custody_evidence(exit_position(),snap)
        self.assertTrue(evidence['mature_stall_near_peak_collect'],evidence)
        self.assertEqual(evidence['reason'],'COMMANDER_MATURE_STALL_CURRENT_PROFIT_NEAR_PEAK')
        result=OneCommander().decide_position([],snap,exit_position())
        self.assertIs(result.action,Action.EXIT)
        self.assertEqual(result.intent.reason,'COMMANDER_MATURE_STALL_CURRENT_PROFIT_NEAR_PEAK')

    def test_weak_or_first_wobble_living_leg_must_hold(self):
        for kw in ({'btc9':10.},{'ema6':1.},{'mature':False},
                   {'at':1012},{'bid':.56},{'net':-.01},
                   {'release':True},{'territory':'DOWN_RAIL'},
                   {'available':False},{'full':False},{'position_id':'WRONG'},
                   {'physical':False}):
            with self.subTest(kw=kw):
                evidence=build_custody_evidence(exit_position(),exit_snapshot(**kw))
                self.assertFalse(evidence['mature_stall_near_peak_collect'],kw)

    def test_floor_and_original_100_percent_protection_unmodified(self):
        import inspect
        from strategy_core.paper_execution import PaperExecutioner
        self.assertIn('p["floor_bid"] is not None',inspect.getsource(PaperExecutioner))

if __name__=='__main__':
    unittest.main()
