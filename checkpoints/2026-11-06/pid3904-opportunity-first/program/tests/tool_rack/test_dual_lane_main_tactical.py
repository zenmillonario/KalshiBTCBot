"""MAIN and TACTICAL independent positive-briefing controls (PAPER only)."""
from __future__ import annotations
import unittest
from dataclasses import replace
from strategy_core.commander import OneCommander
from strategy_core.dual_lane import DualLaneCounterfadeMemory, early_main_policy
from strategy_core.tool_rack import ToolRackController
from strategy_core.types import Action, Lane, MarketSnapshot, Side, Territory, ToolIntent
from tests.tool_rack.test_pid7412_directional_transfer import snapshot_from_sample
from tests.tool_rack.test_pid14048_quote_value_and_stall import quote_snapshot


def candle(t=1000., age=360., swing='U1', side='YES', ask=.19):
    md={
       'physical_current':True,
       'current_geometry':{'btc_price':200., 'epoch_ms':t*1000., 'parent_direction':'UP',
                           'range180':100.,'range60':100.,'btc_change6':2.,'ema9_change6':1.,
                           'arc_id':swing},
       'ema9_ema30_cross_context':{'gap_lifecycle':{'current_side':'YES',
                'stage':'MATURE','age_seconds_since_observed_cross':1800.+(t-1000.),
                'current_abs_gap_btc':40.,'continued_on_cross_side':True,
                'touching_spine':False}},
       'mountain':{'owner_side':'YES','strong_active_release':False,
                   'parent_structure':{'parent_side':'YES','parent_terminal_ready':False}},
       'heist':{'qualified_box':True,'visit_id':swing,'box_id':'B','current_zone':'UPPER'},
       'tp_geometry':{},
       'commander_strategy':{'owned_territory':'MARKET_HEIST','owned_side':'YES',
                              'active_tool':'MARKET_HEIST'},
    }
    return MarketSnapshot(now_ts=t,ticker='KX15',contract_age_s=age,yes_ask=.19,no_ask=ask,
        yes_bid=.18,no_bid=max(.001,ask-.01),metadata=md)


def fade(t=1000., swing='U1'):
    return ToolIntent(tool='MARKET_HEIST',territory_id='H',lane=Lane.TACTICAL,
        side=Side.NO,action=Action.ENTER,opportunity_id=f'H:{swing}',max_price=.35,
        size_tier=10.,reason='HEIST_OUTER_EDGE_TACTICAL_RENTER',source_time=t,
        metadata={'position_role':'TACTICAL','box_id':'B','visit_id':swing,
                  'physical_mission_id':f'HEIST:B:VISIT:{swing}'})


class DualLaneTests(unittest.TestCase):
    def test_release_handoff_never_consumed_as_first_counterfade(self):
        mem=DualLaneCounterfadeMemory()
        intent=ToolIntent(tool='RELEASE_WATCHER',territory_id='R',lane=Lane.HANDOFF,
            side=Side.NO,action=Action.RELAY,opportunity_id='REL',max_price=.2,
            size_tier=25.,reason='RELEASE_CONFIRMED_LEVIATHAN_HANDOFF',source_time=1000,
            metadata={'position_role':'TACTICAL'})
        self.assertTrue(mem.consider(intent,candle()))
        self.assertIsNone(mem.last_observation)

    def test_first_opposite_swing_is_observation_not_order(self):
        mem=DualLaneCounterfadeMemory()
        self.assertFalse(mem.consider(fade(),candle()))
        self.assertEqual(mem.last_observation['state'],'OBSERVE')
        self.assertEqual(mem.last_observation['first_swing'],'U1')
    def test_many_quotes_same_first_swing_do_not_unlock_second(self):
        mem=DualLaneCounterfadeMemory()
        for n in range(8):
            self.assertFalse(mem.consider(fade(1000+n),candle(t=1000+n,ask=.15+.01*(n%3))))
        self.assertGreaterEqual(mem.last_observation['ticks'],8)
        self.assertLess(mem.last_observation['min_ask'],mem.last_observation['max_ask'])
    def test_later_distinct_swing_can_offer_tactical(self):
        mem=DualLaneCounterfadeMemory()
        self.assertFalse(mem.consider(fade(),candle()))
        self.assertTrue(mem.consider(fade(1020,'U2'),candle(t=1020,swing='U2')))
    def test_first_opposite_child_is_observed_before_any_entry_candidate(self):
        mem=DualLaneCounterfadeMemory()
        s=candle(swing='FIRST')
        md={**s.metadata,'current_geometry':{**s.metadata['current_geometry'],
             'arc_direction':'DOWN','arc_id':'FIRST'}}
        mem.observe_first_physical_swing(replace(s,metadata=md))
        self.assertEqual(mem.last_observation['state'],'OBSERVE')
        self.assertEqual(mem.last_observation['first_swing'],'FIRST')
        self.assertFalse(mem.consider(fade(1000.,'FIRST'),replace(s,metadata=md)))
        later=candle(t=1020,swing='SECOND')
        self.assertTrue(mem.consider(fade(1020,'SECOND'),later))
    def test_contract_rollover_does_not_reset_first_counterfade_memory(self):
        mem=DualLaneCounterfadeMemory()
        self.assertFalse(mem.consider(fade(),candle()))
        next_contract=replace(candle(t=1900,swing='U2'),ticker='KX16')
        self.assertTrue(mem.consider(fade(t=1900,swing='U2'),next_contract))

    def test_same_direction_tactical_does_not_require_counterfade_observation(self):
        mem=DualLaneCounterfadeMemory()
        self.assertTrue(mem.consider(replace(fade(),side=Side.YES),candle()))
    def test_new_parent_side_resets_first_counterfade(self):
        mem=DualLaneCounterfadeMemory()
        self.assertFalse(mem.consider(fade(),candle()))
        self.assertTrue(mem.consider(fade(1020,'U2'),candle(t=1020,swing='U2')))
        s=candle(t=1040,swing='L1');md={**s.metadata,
            'ema9_ema30_cross_context':{'gap_lifecycle':{'current_side':'NO','stage':'MATURE',
            'age_seconds_since_observed_cross':960., 'current_abs_gap_btc':40.,
            'continued_on_cross_side':True,'touching_spine':False}}}
        s=replace(s,metadata=md)
        opposite=replace(fade(1040,'L1'),side=Side.YES)
        self.assertFalse(mem.consider(opposite,s))
    def test_main_default_observation_first_five_minutes(self):
        intent=replace(fade(),lane=Lane.MAIN,side=Side.YES)
        self.assertFalse(early_main_policy(intent,candle(age=299.)))
        self.assertTrue(early_main_policy(intent,candle(age=300.)))
    def test_earned_early_main_exception_retained(self):
        intent=replace(fade(),lane=Lane.MAIN,side=Side.YES,
            metadata={'inherited_rollover':True})
        self.assertTrue(early_main_policy(intent,candle(age=12.)))
    def test_main_rail_observes_even_if_heist_primary(self):
        from tests.tool_rack.test_authorized_reactivation import AuthorizedReactivationTests
        ss=AuthorizedReactivationTests()._rail_snapshot(amp=300,duration=120)
        md={**ss.metadata,'physical_current':True,
            'ema9_ema30_cross_context':{'gap_lifecycle':{'current_side':'YES','stage':'ROLLING',
                'age_seconds_since_observed_cross':3600.,'current_abs_gap_btc':40.,
                'continued_on_cross_side':True,'touching_spine':False}},
            'heist':{'qualified_box':True}}
        ss=replace(ss,metadata=md)
        rack=ToolRackController();rack._owned_territory=Territory.MARKET_HEIST
        actions=rack._independent_lane_intents(ss)
        self.assertTrue(any(x.tool=='RAIL' and x.side is Side.YES
                            and x.metadata.get('dual_lane')=='MAIN' for x in actions),actions)
        self.assertIsNotNone(rack._dual_tactical_heist)
    def test_early_main_parallel_rail_waits_but_heist_still_observes(self):
        ss=candle(age=80.)
        rack=ToolRackController();rack._owned_territory=Territory.MARKET_HEIST
        actions=rack._independent_lane_intents(ss)
        self.assertFalse(any(x.metadata.get('dual_lane')=='MAIN' for x in actions))
        self.assertIsNotNone(rack._dual_tactical_heist)
    def test_second_calibrated_heist_has_a_narrow_directional_parent_path(self):
        # Counterfade calibration is tested on an independently earned
        # repeated synthetic range, never on a bare qualified_box flag.
        s=quote_snapshot(1020.,.19)
        s=replace(s,metadata={**s.metadata,
            'heist':{**s.metadata['heist'],'visit_id':'U2'},
            'ema9_ema30_cross_context':{'gap_lifecycle':{'stage':'MATURE','current_side':'YES'}},
            'mountain':{**s.metadata['mountain'],'parent_structure':{
                'parent_side':'YES','parent_terminal_ready':False}}})
        mountain={**s.metadata['mountain'],
          'current_motion':{'30':{'covered':True,'owner_price_rate_btc_s':2.,
              'owner_ema9_rate_btc_s':1.}}}
        md={**s.metadata,'mountain':mountain,
            'commander_strategy':{'owned_territory':'UP_RAIL','owned_side':'YES',
                                  'active_tool':'RAIL'}}
        s=replace(s,metadata=md)
        first=fade(1020.,'U2')
        one=OneCommander()
        self.assertEqual(one._entry_strategy_denial(first,s),
            'COMMANDER_HEIST_BLOCKED_LIVING_DIRECTIONAL_PARENT')
        earned=replace(first,metadata={**first.metadata,
            'dual_lane_counterfade_calibrated':True})
        self.assertIsNone(one._entry_strategy_denial(earned,s))
        expansion=replace(s,metadata={**md,'mountain':{**mountain,
                'strong_active_release':True}})
        self.assertEqual(one._entry_strategy_denial(earned,expansion),
            'OPPORTUNITY_DIRECTIONAL_RELEASE_CANCELS_HEIST_RETURN')

    def test_other_side_inventory_is_not_silently_net_as_two_lots(self):
        ss=quote_snapshot(1000.,.19)
        candidate=fade(1000.,ss.metadata['heist']['visit_id'])
        self.assertIs(OneCommander().decide_entry([candidate],ss,{}).action,Action.ENTER)
        held={'1':{'ticker':ss.ticker,'side':'YES','position_role':'PRIMARY',
                   'custody_state':'NORMAL','entry_metadata':{}}}
        decision=OneCommander().decide_entry([candidate],ss,held)
        self.assertEqual(decision.action,Action.WAIT)
        self.assertIn('INVENTORY',decision.reason)

if __name__=='__main__': unittest.main()
