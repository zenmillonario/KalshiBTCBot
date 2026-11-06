from __future__ import annotations
import json
import unittest
from pathlib import Path
from strategy_core.commander_candidates import physical_entry_candidates
from strategy_core.directional_parent import directional_parent_evidence
from strategy_core.paper_execution import PaperPosition
from strategy_core.paper_runtime import ToolRackPaperEngine
from strategy_core.router import PhysicalEvidence
from strategy_core.tool_rack import ToolRackController
from strategy_core.tools.heist import MarketHeistTool
from strategy_core.types import MarketSnapshot,Side,Territory,Lane

SAMPLES=Path(__file__).resolve().parents[2]/'docs'/'PID7412_DIRECTIONAL_TRANSFER_SAMPLES.json'

def snapshot_from_sample(key):
    rows=json.loads(SAMPLES.read_text(encoding='utf-8'))['rows']
    row=next(x for x in rows if x['label']==key)
    gap=row['gap'];mountain=row['mountain'];geo=row['geometry'];b=row['book'];tp=row['tp']
    md={
        'physical_current':bool(row['source']['btc_current']),
        'geometry_last_epoch_ms':geo.get('epoch_ms'),
        'current_geometry':geo,
        'mountain':{
            'owner_side':mountain.get('owner_side'),
            'parent_structure':mountain.get('parent') or {},
            'current_arc_id':mountain.get('current_arc_id'),
            'terminal_evidence_qualified':mountain.get('terminal_evidence_qualified'),
            'mature_edge':mountain.get('mature_edge'),
            'edge_window_active':mountain.get('edge_window_active'),
            'strong_active_release':mountain.get('strong_active_release'),
            'current_motion':mountain.get('current_motion'),
        },
        'ema9_ema30_cross_context':{'gap_lifecycle':{
            'stage':gap.get('stage'),
            'current_side':gap.get('gap_side'),
            'age_seconds_since_observed_cross':gap.get('age_s'),
            'current_abs_gap_btc':gap.get('abs_gap'),
            'continued_on_cross_side':gap.get('continued_on_cross_side'),
            'touching_spine':gap.get('touching_spine'),
        }},
        'tp_geometry':tp,
        'commander_strategy':{'owned_territory':'MARKET_HEIST','active_overlays':['MARKET_HEIST']},
    }
    return MarketSnapshot(now_ts=row['time'],ticker=row['ticker'],contract_age_s=row['contract_age_s'],
        yes_ask=b.get('yes_ask'),no_ask=b.get('no_ask'),
        yes_bid=b.get('yes_bid'),no_bid=b.get('no_bid'),quote_current=True,
        depth_available=True,metadata=md)

class PID7412DirectionalTransferTests(unittest.TestCase):
    def test_developing_gap_does_not_steal_balanced_heist(self):
        self.assertFalse(directional_parent_evidence(snapshot_from_sample('DEVELOPING_NOT_PARENT'))['qualified'])
    def test_six_contract_yes_gap_is_directional_parent_not_child_heist(self):
        for label in ('UP_PARENT','UP_PARENT_CHILD_FLICKER','UP_PARENT_TERMINAL_WATCH'):
            proof=directional_parent_evidence(snapshot_from_sample(label))
            self.assertTrue(proof['qualified'],label)
            self.assertEqual(proof['side'],'YES',label)
    def test_old_yes_gap_collapses_at_new_down_transfer(self):
        self.assertFalse(directional_parent_evidence(snapshot_from_sample('OLD_UP_GAP_COLLAPSED'))['qualified'])
    def test_down_gap_graduates_without_six_contract_wait(self):
        proof=directional_parent_evidence(snapshot_from_sample('DOWN_PARENT'))
        self.assertTrue(proof['qualified']);self.assertEqual(proof['side'],'NO')
    def test_replay_real_up_dip_can_brief_with_wind_yes(self):
        s=snapshot_from_sample('UP_VALUE_DIP')
        got=physical_entry_candidates(s)
        self.assertTrue(any(x.side is Side.YES and x.reason=='COMMANDER_DIRECTIONAL_PARENT_PULLBACK_REJOIN' for x in got),
                        [x.reason for x in got])
    def test_tp_against_parent_does_not_create_with_wind_entry(self):
        s=snapshot_from_sample('UP_TP_CONTRADICTION')
        self.assertFalse(any(x.reason=='COMMANDER_DIRECTIONAL_PARENT_PULLBACK_REJOIN'
                             for x in physical_entry_candidates(s)))
    def test_heist_owned_state_yields_to_long_parent(self):
        s=snapshot_from_sample('UP_PARENT')
        # Simulate current qualified-box classifier even though the larger
        # physical gap has accumulated a multi-contract YES direction.
        s=MarketSnapshot(**{**s.__dict__,'metadata':{**s.metadata,'heist':{'qualified_box':True}}})
        rack=ToolRackController()
        rack._owned_territory=Territory.MARKET_HEIST
        rack._owned_side=Side.NO
        rack._territory_id='HEIST-OLD'
        rack._active_tool=MarketHeistTool(territory_id='HEIST-OLD')
        res=rack.observe(PhysicalEvidence(qualified_heist=True),s)
        self.assertEqual(res.owned_territory,Territory.ROLLING_MOUNTAIN)
        self.assertIs(res.owned_side,Side.YES)
    def test_counterwind_tactical_arms_early_profit_without_downgrading_main(self):
        s=snapshot_from_sample('UP_PARENT')
        p=PaperPosition(position_id='T',ticker=s.ticker,side=Side.NO,qty=100,
            entry_price=.10,cost=10.,entry_fee_remaining=.25,entry_time=s.now_ts-60,
            close_ts=s.now_ts+200,tool='MARKET_HEIST',territory_id='H',opportunity_id='V',
            lane=Lane.TACTICAL,entry_quote_id='Q',entry_reason='HEIST_OUTER_EDGE_TACTICAL_RENTER',
            entry_metadata={'floor_policy':{'arm_roi':.60,'trail_fraction':.10,'min_age_s':0,
                                            'first_arm_from_current_bid':True}},
            peak_bid=.12,floor_bid=None,trail_fraction=None,exit_required=False,exit_reason=None)
        policy=ToolRackPaperEngine._floor_policy((),p,s)
        self.assertEqual(policy.arm_roi,.30)
        self.assertEqual(policy.trail_fraction,.05)
        self.assertTrue(policy.first_arm_from_current_bid)
    def test_stalled_winner_over_100_tightens_not_loosen_existing_floor(self):
        s=snapshot_from_sample('UP_PARENT_TERMINAL_WATCH')
        md={**s.metadata,'mountain':{**s.metadata['mountain'],'stall':True}}
        s=MarketSnapshot(**{**s.__dict__,'metadata':md})
        p=PaperPosition(position_id='M',ticker=s.ticker,side=Side.YES,qty=20,
            entry_price=.20,cost=4.,entry_fee_remaining=.15,entry_time=s.now_ts-70,
            close_ts=s.now_ts+200,tool='ALTERNATING_MOUNTAIN',territory_id='M',
            opportunity_id='EDGE',lane=Lane.MAIN,entry_quote_id='Q',entry_reason='MOUNTAIN_TRUE_EDGE',
            entry_metadata={'floor_policy':{'arm_roi':1.,'trail_fraction':.05,'min_age_s':0}},
            peak_bid=.45,floor_bid=None,trail_fraction=None,exit_required=False,exit_reason=None)
        policy=ToolRackPaperEngine._floor_policy((),p,s)
        self.assertLessEqual(policy.trail_fraction,.035)

if __name__=='__main__':unittest.main()
