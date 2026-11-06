"""PID15740 source-value controls: inherited cross, counter-NO errors, 53c opening.

No future settlement or later quote maxima are used as entry input. The four
negative snapshots retain their recorded 30-second BTC/EMA9 state, TP/side,
prices and reason. The wrapper's same-side residence, comparison qualification
and complementary quotes are authored unit-test context, not a full captured
source stream. Original geometry timestamps and the historical wall clock are
left unchanged, including their mismatch; no original source receipt or
continuity generation is available here.

Lower-level candidate tests preserve the measured species/value behavior.
The shared Commander must WAIT on the incomplete wrapper, so these controls
cannot be reported as an exact replay or proof of complete entry admission.
"""
from __future__ import annotations
import json
import unittest
from dataclasses import replace
from pathlib import Path
from strategy_core.types import MarketSnapshot, Side, Action, Lane, ToolIntent
from strategy_core.physical_source import ema9_ema30_cross_context
from strategy_core.directional_parent import directional_parent_evidence
from strategy_core.commander_candidates import physical_entry_candidates, historical_extreme_release_candidates, positive_candidate_matches_continuation
from strategy_core.dual_lane import DualLaneCounterfadeMemory
from strategy_core.commander import OneCommander
from strategy_core.tool_rack import ToolRackController

PATH = Path(__file__).resolve().parents[2] / 'docs' / 'PID15740_ENTRY_TIME_CONTROLS.json'

def inherited_cross_context(t=1800., side='YES', *, count=110, step=10):
    # Synthetic same-side rows exercise residence logic without inventing a
    # crossed-at time. They are not recovered rows from the historical tape.
    e9, e30 = (100., 60.) if side == 'YES' else (60., 100.)
    rows=[{'epoch_ms':(t-(count-1-i)*step)*1000., 'ema9':e9,'ema30':e30,
           'connection_epoch':'SAME','arc_id':'ONE'} for i in range(count)]
    return ema9_ema30_cross_context(rows)

def case_snapshot(key, *, mirror=False):
    """Return the unchanged hybrid wrapper, not authenticated captured input."""
    sample=json.loads(PATH.read_text(encoding='utf-8'))['cases'][key]
    g=dict(sample['geometry']);m=dict(sample['mountain']);tp=dict(sample['tp'])
    clock=float(sample['t'])
    gap=inherited_cross_context(clock, 'YES', count=125)
    # Use the recorded current gap magnitude in the synthetic residence
    # context. Do not imply that the authored residence rows are original tape.
    gap['gap_lifecycle']['current_abs_gap_btc']=abs(g['ema_gap'])
    raw_side='YES'
    ask_no=float(sample['ask'])
    ask_yes=.53 if key=='OPEN_0045' else .65
    if mirror:
        raw_side='NO'; ask_yes=ask_no;ask_no=.53
        g.update({k:(-v if isinstance(v,(int,float)) else v)
                  for k,v in g.items() if k in {'ema_gap','btc_change6','btc_change9',
                        'btc_change30','btc_change60','ema9_change6','ema9_change30'}})
        g['arc_direction']='DOWN' if g.get('arc_direction')=='UP' else 'UP'
        g['parent_direction']='DOWN'
        m['owner_side']='NO'
        m['parent']={**m['parent'],'parent_side':'NO'}
        tp['contract_ownership_side']='NO' if tp.get('contract_ownership_side')=='YES' else 'YES'
        gap=inherited_cross_context(clock,'NO',count=125)
        gap['gap_lifecycle']['current_abs_gap_btc']=abs(g['ema_gap'])
    md={'physical_current':True,'current_geometry':g,
        'geometry_last_epoch_ms':clock*1000.,
        'ema9_ema30_cross_context':gap,
        'mountain':{**m,'parent_structure':m['parent'],
                    'full_leg_scale_evidence':{'qualified':True},
                    'current_arc_id':g.get('arc_id'),
                    'edge_id':g.get('arc_id'),
                    'diagnostics':{'current_age_s':m['parent'].get('parent_age_s'),
                                   'source_ms':clock*1000.}},
        'historical_extreme_release':{'qualified':True,'side':('YES' if mirror else 'NO'),
                                     'prior_low_anchor':0,'prior_high_anchor':0},
        'tp_geometry':tp,
        'commander_strategy':{'owned_territory':sample['territory'],
                              'owned_side':m['owner_side'],'active_overlays':['MARKET_HEIST']},
    }
    return MarketSnapshot(now_ts=clock,ticker=sample['ticker'],
        contract_age_s=float(sample['contract_age_s']),
        yes_ask=ask_yes,no_ask=ask_no,yes_bid=max(.001,ask_yes-.01),no_bid=max(.001,ask_no-.01),
        quote_current=True,depth_available=True,metadata=md)

class PID15740InheritedUpRailTests(unittest.TestCase):
    def test_original_cross_age_remains_unknown_but_observed_parent_is_qualified(self):
        ctx=inherited_cross_context()
        gap=ctx['gap_lifecycle']
        self.assertIsNone(gap['age_seconds_since_observed_cross'])
        self.assertEqual(gap['stage'],'INHERITED_OR_UNOBSERVED_CROSS')
        self.assertGreater(gap['observed_side_residence_seconds'],900.)
        s=case_snapshot('NO_2')
        parent=directional_parent_evidence(s)
        self.assertTrue(parent['qualified'],parent)
        self.assertEqual(parent['side'],'YES')
        self.assertEqual(parent['basis'],'OBSERVED_INHERITED_SAME_SIDE_RESIDENCE')

    def test_source_break_resets_residence_and_cannot_invent_old_parent(self):
        t=1800.; rows=[]
        for i in range(100): rows.append({'epoch_ms':(100+i*10)*1000.,'ema9':100.,'ema30':60.,'connection_epoch':'S'})
        rows.append({'epoch_ms':(100+99*10+30)*1000.,'ema9':100.,'ema30':60.,'connection_epoch':'S'})
        ctx=ema9_ema30_cross_context(rows)
        self.assertEqual(ctx['gap_lifecycle']['observed_side_residence_seconds'],0.)
        s=case_snapshot('NO_2');md={**s.metadata,'ema9_ema30_cross_context':ctx}
        self.assertFalse(directional_parent_evidence(replace(s,metadata=md))['qualified'])

    def test_four_recorded_no_entry_routes_are_silent_in_up_parent(self):
        for key in ('NO_1','NO_2','NO_3','NO_4'):
            with self.subTest(key=key):
                s=case_snapshot(key)
                self.assertTrue(directional_parent_evidence(s)['qualified'])
                extreme=historical_extreme_release_candidates(s)
                self.assertFalse(any(x.side is Side.NO for x in extreme),extreme)
                candidates=physical_entry_candidates(s)
                self.assertFalse(any(x.side is Side.NO for x in candidates),[(x.reason,x.side) for x in candidates])
                self.assertFalse(any(x.side is Side.NO for x in OneCommander().physical_entry_candidates(s)))

    def test_first_counterfade_calibration_reaches_commander_created_main_candidates(self):
        s=case_snapshot('NO_2')
        mem=DualLaneCounterfadeMemory()
        def pretend(arc, ts):
            snap=replace(s,now_ts=ts,metadata={**s.metadata,
                   'current_geometry':{**s.metadata['current_geometry'],'arc_id':arc}})
            intent=ToolIntent(tool='ONE_COMMANDER_PRIMARY',territory_id='MOUNTAIN_EDGE',lane=Lane.MAIN,
                    side=Side.NO,action=Action.ENTER,opportunity_id=f'M:{arc}',max_price=.2,size_tier=10.,
                    reason='COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN',source_time=ts,
                    metadata={'commander_primary_candidate':True,'commander_candidate_family':'MOUNTAIN_EDGE'})
            return mem.consider(intent,snap)
        self.assertFalse(pretend('FIRST',s.now_ts))
        self.assertFalse(pretend('FIRST',s.now_ts+2))
        self.assertTrue(pretend('SECOND',s.now_ts+25))

    def test_main_lane_parent_qualifies_with_unknown_original_cross(self):
        s=case_snapshot('OPEN_0045')
        rack=ToolRackController()
        # Direct independent MAIN evaluation must instantiate Rail even if
        # local Heist owns the displayed territory.
        rack._independent_lane_intents(s)
        self.assertIsNotNone(rack._dual_main_rail)
        self.assertIs(rack._dual_main_rail.side, Side.YES)

    def test_recorded_53c_opening_candidate_survives_but_incomplete_wrapper_waits(self):
        s=case_snapshot('OPEN_0045')
        # This lower-level classification remains positive at the original
        # price tier. It does not bypass the shared current-source contract.
        entries=physical_entry_candidates(s)
        matching=[x for x in entries if x.side is Side.YES and
                  x.reason=='COMMANDER_OBSERVED_INHERITED_PARENT_FIRST_MINUTE_CONTINUATION']
        self.assertEqual(len(matching),1,[(i.reason,i.side) for i in entries])
        self.assertEqual(matching[0].max_price,.55)
        self.assertEqual(matching[0].size_tier,25.)
        self.assertGreater(s.metadata['current_geometry']['epoch_ms'],s.now_ts*1000.)
        self.assertNotEqual(s.metadata['current_geometry']['epoch_ms'],
                            s.metadata['geometry_last_epoch_ms'])
        self.assertNotIn('geometry_continuity_generation',s.metadata)
        self.assertNotIn('physical_source_receipt',s.metadata)
        self.assertFalse(OneCommander().physical_entry_candidates(s))
        decision=OneCommander().decide_entry(entries,s,{})
        self.assertIs(decision.action,Action.WAIT,decision)
        self.assertEqual(decision.reason,'OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED')

    def test_opening_not_authorized_without_tp_or_with_late_clock(self):
        s=case_snapshot('OPEN_0045')
        tp={**s.metadata['tp_geometry'],'contract_ownership_side':'NO'}
        # Exercise the physical TP/window rule directly: a shared source
        # rejection alone would make these two negative controls vacuous.
        self.assertFalse(any('OBSERVED_INHERITED_PARENT' in x.reason
                    for x in physical_entry_candidates(replace(s,metadata={**s.metadata,'tp_geometry':tp}))))
        s=replace(s,contract_age_s=67.)
        self.assertFalse(any('OBSERVED_INHERITED_PARENT' in x.reason
                    for x in physical_entry_candidates(s)))

    def test_mirrored_down_parent_same_rules(self):
        s=case_snapshot('NO_2',mirror=True)
        self.assertTrue(directional_parent_evidence(s)['qualified'])
        self.assertEqual(directional_parent_evidence(s)['side'],'NO')
        self.assertFalse(any(x.side is Side.YES for x in historical_extreme_release_candidates(s)))

if __name__=='__main__': unittest.main()
