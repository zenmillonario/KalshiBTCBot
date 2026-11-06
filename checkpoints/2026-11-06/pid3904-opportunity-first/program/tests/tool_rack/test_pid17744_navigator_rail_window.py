"""Recorded PID17744 21:30 first-minute missed Rail window; Navigator is advisory."""
from __future__ import annotations
import json
from pathlib import Path
import unittest
from strategy_core.types import MarketSnapshot
from strategy_core.navigator_briefing import navigator_terrain_briefing
from strategy_core.directional_parent import directional_parent_evidence

FIXTURE=Path(__file__).resolve().parents[2]/'docs/PID17744_2130_NAVIGATOR_CHECKPOINTS.json'

def at(which: str, *, tp_override=None, physical=True) -> MarketSnapshot:
    row=json.loads(FIXTURE.read_text(encoding='utf-8'))['rows'][which]
    gap=row['gap']
    tp=dict(row['tp'])
    if tp_override:tp.update(tp_override)
    return MarketSnapshot(
        now_ts=row['t'],ticker=row['ticker'],
        contract_age_s=row['contract_age_s'],
        yes_ask=row['book'].get('yes_ask'),no_ask=row['book'].get('no_ask'),
        yes_bid=row['book'].get('yes_bid'),no_bid=row['book'].get('no_bid'),
        quote_current=True,depth_available=True,
        metadata={'physical_current':physical,'current_geometry':row['geometry'],
             'mountain':{'parent_structure':row['mountain_parent']},
             'tp_geometry':tp,
             'ema9_ema30_cross_context':{'gap_lifecycle':{
                 'current_side':gap['gap_side'],'stage':gap['stage'],
                 'age_seconds_since_observed_cross':gap['age_s'],
                 'current_abs_gap_btc':gap['abs_gap'],
                 'continued_on_cross_side':gap['continued_on_cross_side'],
                 'touching_spine':gap['touching_spine']}}})

class PID17744NavigatorRailWindowTests(unittest.TestCase):
    def test_2130_16_no_49c_parent_mature_but_tp_not_earned(self):
        s=at('213016')
        self.assertAlmostEqual(s.no_ask,.49)
        self.assertEqual(directional_parent_evidence(s)['side'],'NO')
        b=navigator_terrain_briefing(s)
        self.assertEqual((b['state'],b['side']),('PREPARE','NO'))
        self.assertTrue(b['evidence']['tp_ema_junction'])
        self.assertEqual(b['evidence']['tp_ownership_side'],'YES')
        self.assertFalse(b['execution_authority'])
        self.assertFalse(b['can_veto'])

    def test_2130_50_no_62c_tp_agrees_but_junction_remains(self):
        s=at('213050')
        self.assertAlmostEqual(s.no_ask,.62)
        self.assertEqual(navigator_terrain_briefing(s)['state'],'PREPARE')
        self.assertEqual(navigator_terrain_briefing(s)['side'],'NO')

    def test_fish_when_parent_tp_and_junction_all_support(self):
        s=at('213050',tp_override={'target_between_ema9_ema30':False})
        b=navigator_terrain_briefing(s)
        self.assertEqual((b['state'],b['side']),('FISH','NO'))
        self.assertIsNone(b['max_price'])
        self.assertFalse(b['execution_authority'])

    def test_no_current_physical_source_no_navigator(self):
        self.assertIsNone(navigator_terrain_briefing(at('213016',physical=False)))

    def test_no_parent_qualifies_no_navigator(self):
        s=at('213050')
        md=dict(s.metadata)
        cross=dict(md['ema9_ema30_cross_context']); gap=dict(cross['gap_lifecycle']); gap['age_seconds_since_observed_cross']=18
        cross['gap_lifecycle']=gap;md['ema9_ema30_cross_context']=cross
        other=MarketSnapshot(now_ts=s.now_ts,ticker=s.ticker,contract_age_s=s.contract_age_s,
            yes_ask=s.yes_ask,no_ask=s.no_ask,yes_bid=s.yes_bid,no_bid=s.no_bid,
            quote_current=True,depth_available=True,metadata=md)
        self.assertIsNone(navigator_terrain_briefing(other))

if __name__=='__main__':unittest.main()
