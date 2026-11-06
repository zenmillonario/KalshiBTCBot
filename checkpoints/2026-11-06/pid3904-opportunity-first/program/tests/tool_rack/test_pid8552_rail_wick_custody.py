"""PID8552 exact causal control data: rail-like #5 hold, wrong first fades #1-3.

PAPER only. All entry and hold decisions are based on the frozen observed
physical snapshot at that point; no hindsight bid peaks enter the decision.
"""
import json
import unittest
from pathlib import Path
from strategy_core.types import MarketSnapshot,Side,Lane
from strategy_core.paper_execution import PaperPosition
from strategy_core.paper_runtime import ToolRackPaperEngine
from strategy_core.commander_candidates import physical_entry_candidates

CONTROLS = Path(__file__).resolve().parents[2]/'docs'/'PID8552_RAIL_WICK_ENTRY_TIME_CONTROLS.json'

def control(label):
    return json.loads(CONTROLS.read_text(encoding='utf-8'))['rows'][label]

def sample(label, *, mirror=False, stall=False, seconds_left=None):
    r = control(label)
    geo = dict(r['geometry'])
    gap = dict(r['gap'])
    mountain = dict(r['mountain'])
    book = dict(r['book'])
    tp = dict(r['tp'])
    strategy = dict(r['strategy'])
    if mirror:
        for k in ('ema_gap','btc_change6','btc_change9','btc_change30','btc_change60','ema9_change6','ema9_change30','ema9_change60'):
            if isinstance(geo.get(k),(float,int)):
                geo[k] = -geo[k]
        for k in ('side','gap_side'):
            if gap.get(k) in ('YES','NO'):
                gap[k] = 'YES' if gap[k]=='NO' else 'NO'
        if mountain.get('owner_side') in ('YES','NO'):
            mountain['owner_side'] = 'YES' if mountain['owner_side']=='NO' else 'NO'
        if mountain.get('parent',{}).get('parent_side') in ('YES','NO'):
            mountain['parent']['parent_side'] = 'YES' if mountain['parent']['parent_side']=='NO' else 'NO'
        book['yes_ask'],book['no_ask']=book['no_ask'],book['yes_ask']
        book['yes_bid'],book['no_bid']=book['no_bid'],book['yes_bid']
    if stall:
        mountain.update({'stall':True,'terminal_evidence_qualified':True,
                         'mature_edge':True,'edge_window_active':True})
    now=r['t']
    if seconds_left is not None:
        now=r['t']+(r['seconds_left']-seconds_left)
    md = {
        'physical_current':r['source']['btc_current'],
        'current_geometry':geo,
        'ema9_ema30_cross_context':{'gap_lifecycle':{
            'stage':gap.get('stage'),'current_side':gap.get('gap_side'),
            'current_abs_gap_btc':gap.get('abs_gap'),
            'continued_on_cross_side':gap.get('continued_on_cross_side'),
            'touching_spine':gap.get('touching_spine'),
        }},
        'mountain':{'owner_side':mountain.get('owner_side'),
            'terminal_evidence_qualified':mountain.get('terminal_evidence_qualified'),
            'mature_edge':mountain.get('mature_edge'),
            'edge_window_active':mountain.get('edge_window_active'),
            'stall':mountain.get('stall'),
            'hesitation':mountain.get('hesitation'),
            'failed_reextension':mountain.get('failed_reextension'),
            'meaningful_retreat':mountain.get('meaningful_retreat'),
            'spent_edge':mountain.get('spent_edge'),
            'strong_active_release':mountain.get('strong_active_release'),
            'current_arc_id':mountain.get('current_arc_id'),
            'source_ms':mountain.get('source_ms'),
            'edge_extreme_ms':mountain.get('edge_extreme_ms'),
            'edge_id':mountain.get('edge_id'),
            'diagnostics':{'current_age_s':mountain.get('current_age_s')},
            'full_leg_scale_evidence':{'qualified': bool(mountain.get('parent',{}).get('extended_parent'))},
            'parent_structure':mountain.get('parent',{}),
        },
        'tp_geometry':tp,
        'commander_strategy':strategy,
    }
    return MarketSnapshot(now_ts=now,ticker=r['ticker'],contract_age_s=900-(seconds_left if seconds_left is not None else r['seconds_left']),
        yes_ask=book.get('yes_ask'),no_ask=book.get('no_ask'),
        yes_bid=book.get('yes_bid'),no_bid=book.get('no_bid'),
        quote_current=True,depth_available=True,metadata=md)

def position(s, *, side=Side.NO, floor=None, role=Lane.MAIN, family='MOUNTAIN_EDGE', peak=.63):
    return PaperPosition(position_id='5',ticker=s.ticker,side=side,qty=124,
        entry_price=.19,cost=23.56,entry_fee_remaining=1.34,
        entry_time=s.now_ts-144,close_ts=s.now_ts+(900-s.contract_age_s),
        tool='ONE_COMMANDER_PRIMARY',territory_id='MOUNTAIN_EDGE',
        opportunity_id='PID8552-NO5',lane=role,entry_quote_id='Q5',
        entry_reason='COMMANDER_MOUNTAIN_TRUE_EDGE_RETURN',
        entry_metadata={'commander_candidate_family':family,
           'floor_policy':{'arm_roi':1.0,'trail_fraction':.05,'min_age_s':30.0,
                           'immediate_arm_roi':1.0,'first_arm_from_current_bid':True,
                           'roi_trail_tiers':[[1.5,.03],[6.0,.02]]}},
        peak_bid=peak,floor_bid=floor,trail_fraction=.03 if floor is not None else None,
        exit_required=False,exit_reason=None)

class PID8552RailWickCustodyTests(unittest.TestCase):
    def test_trade5_rail_style_living_down_leg_no_first_floor_at_204_seconds(self):
        s=sample('NO_5_ALIGNED_EXPANSION')
        pol=ToolRackPaperEngine._floor_policy((),position(s),s)
        self.assertFalse(pol.first_arm_allowed)
        self.assertGreater(pol.arm_roi,10.)
        self.assertIsNone(pol.immediate_arm_roi)
        self.assertEqual(pol.roi_trail_tiers,())

    def test_mirrored_up_rail_style_runner_breathes(self):
        s=sample('NO_5_ALIGNED_EXPANSION',mirror=True)
        pol=ToolRackPaperEngine._floor_policy((),position(s,side=Side.YES),s)
        self.assertGreater(pol.arm_roi,10.)

    def test_at_90s_remaining_do_not_use_open_ended_rail_exception(self):
        s=sample('NO_5_ALIGNED_EXPANSION',seconds_left=90)
        pol=ToolRackPaperEngine._floor_policy((),position(s),s)
        self.assertLess(pol.arm_roi,10.)

    def test_stalled_mountain_gives_peak_protection(self):
        s=sample('NO_5_ALIGNED_EXPANSION',stall=True)
        pol=ToolRackPaperEngine._floor_policy((),position(s),s)
        self.assertLess(pol.arm_roi,10.)
        self.assertLessEqual(pol.trail_fraction,.035)

    def test_already_committed_floor_never_loosened(self):
        s=sample('NO_5_ALIGNED_EXPANSION')
        pol=ToolRackPaperEngine._floor_policy((),position(s,floor=.6111),s)
        self.assertLess(pol.arm_roi,10.)

    def test_counterwind_tactical_no_rail_style_exemption(self):
        s=sample('NO_5_ALIGNED_EXPANSION')
        pol=ToolRackPaperEngine._floor_policy((),position(s,side=Side.YES,role=Lane.TACTICAL),s)
        self.assertLess(pol.arm_roi,10.)

    def test_trade2_no_early_yes_against_continuing_down(self):
        s=sample('EARLY_YES_2')
        self.assertFalse(any(i.side is Side.YES and 'EXTREME_SUB20_RETURN' in i.reason
                             for i in physical_entry_candidates(s)))

    def test_trade3_no_repeat_cheap_yes_without_green_ema9_turn(self):
        s=sample('EARLY_YES_3')
        self.assertFalse(any(i.side is Side.YES and 'EXTREME_SUB20_RETURN' in i.reason
                             for i in physical_entry_candidates(s)))

    def test_trade1_last_97s_no_proven_yes_contract_runway(self):
        s=sample('LATE_YES_1')
        self.assertFalse(any(i.side is Side.YES and 'LEVEL_MATCH' in i.reason
                             for i in physical_entry_candidates(s)))

if __name__=='__main__':unittest.main()
