"""PID19616 selected source-bound positive/negative Commander admission controls.

No future quotes, hypothetical fills or retrospective P&L are inputs. Recorded
physical frames and original intent metadata are not engineered or mirrored.
Derived boundary variations are explicitly marked synthetic.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import gzip
import json
from pathlib import Path
import unittest

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import (
    _recent_level_return_location_ready, _mature_premium_opening_has_fresh_momentum,
    heist_stalled_edge_earned, physical_entry_candidates,
)
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from tests.tool_rack.test_pid15740_inherited_up_rail import case_snapshot
from tests.tool_rack.test_pid18244_parent_custody_protection import (
    PID18244RecordedControlTests,
)
from tests.tool_rack.test_pid17224_main_returns import level_match_snapshot

with gzip.open(Path(__file__).parent / 'fixtures/pid19616_selected_source_decisions.json.gz',
               'rt', encoding='utf-8') as _f:
    CORPUS = json.load(_f)


def recorded(seq: int) -> MarketSnapshot:
    row = CORPUS['frames'][str(seq)]
    book = row['market_book_top']
    return MarketSnapshot(now_ts=row['now_ts'], ticker=row['ticker'],
        contract_age_s=row['contract_age_s'],
        yes_bid=book['yes_bid'], no_bid=book['no_bid'],
        yes_ask=book['yes_ask'], no_ask=book['no_ask'],
        quote_current=True, depth_available=True,
        metadata=deepcopy(row['physical_metadata']))


def recorded_heist(seq: int) -> ToolIntent:
    row = CORPUS['frames'][str(seq)]
    match = next(x for x in row['candidate_intents'] if x['tool'] == 'MARKET_HEIST')
    return ToolIntent(tool=match['tool'],territory_id=match['territory_id'],
        lane=Lane(match['lane']),side=Side(match['side']),action=Action(match['action']),
        opportunity_id=match['opportunity_id'],max_price=match['max_price'],
        size_tier=match['size_tier'],reason=match['reason'],source_time=match['source_time'],
        metadata=deepcopy(match['metadata']))


class PID19616EntryQualityTests(unittest.TestCase):
    def test_seven_selected_original_frames_have_exact_source_provenance(self):
        self.assertEqual(CORPUS['original_archive_sha256'],
            '22028d8a01034bd76f66caf164ff622f660a0d5b7cc76dca765218d21fe117e5')
        self.assertEqual(set(CORPUS['frames']), {'1701','2029','6398','7013','7480','7707','8301'})
        for label, row in CORPUS['frames'].items():
            with self.subTest(seq=label):
                self.assertEqual(len(row['source_sha256']),64)
                self.assertTrue(row['physical_metadata']['physical_current'])
                self.assertGreater(row['now_ts']*1000 -
                    row['physical_metadata']['current_geometry']['epoch_ms'],0)
                self.assertLess(row['now_ts']*1000 -
                    row['physical_metadata']['current_geometry']['epoch_ms'],3000)

    def test_3_recorded_broken_prior_low_rejected_before_25_dollar_candidate(self):
        s=recorded(2029)
        match=s.metadata['historical_extreme_release']['recent_level_match']
        self.assertEqual(match['side'],'YES')
        self.assertAlmostEqual(match['distance_btc'],-32.52,places=2)
        self.assertFalse(_recent_level_return_location_ready(s,match))
        self.assertFalse(any(x.reason=='COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN'
            for x in physical_entry_candidates(s)))

    def test_3_near_old_low_is_positive_location_only_not_a_future_trade(self):
        s=recorded(2029)
        md=deepcopy(s.metadata)
        match=md['historical_extreme_release']['recent_level_match']
        md['current_geometry']['btc_price']=match['anchor'] - 5.0  # synthetic nearby anchor test
        nearby=replace(s,metadata=md)
        self.assertTrue(_recent_level_return_location_ready(nearby,match))

    def test_old_pid18244_6_and_pid17224_valid_level_retests_remain_qualified(self):
        # Actual recorded source cases, not invented future trades.
        PID18244RecordedControlTests().test_6_first_class_recent_level_match_no_entry_remains()
        s=level_match_snapshot()
        self.assertTrue(_recent_level_return_location_ready(
            s,s.metadata['historical_extreme_release']['recent_level_match']))

    def test_7_stalled_edge_of_expanding_down_parent_is_not_causal_return(self):
        s=recorded(7707)
        i=recorded_heist(7707)
        g=s.metadata['current_geometry']
        self.assertLess(g['ema9_change30'],-50)
        self.assertLess(g['btc_change9'],-80)
        self.assertLess(abs(g['btc_change6']),1)
        self.assertFalse(heist_stalled_edge_earned(i,s))
        self.assertEqual(OneCommander()._entry_strategy_denial(i,s),
            'COMMANDER_HEIST_STALLED_EDGE_NEEDS_PHYSICAL_RETURN')

    def test_4_and_6_positive_steep_extremes_are_not_treated_as_7_microstall(self):
        for seq in (6398,7480):
            with self.subTest(seq=seq):
                s,i=recorded(seq),recorded_heist(seq)
                self.assertTrue(heist_stalled_edge_earned(i,s))
                self.assertNotEqual(OneCommander()._entry_strategy_denial(i,s),
                    'COMMANDER_HEIST_STALLED_EDGE_NEEDS_PHYSICAL_RETURN')

    def test_2_5_positive_heist_species_are_unchanged(self):
        for seq in (1701,7013):
            with self.subTest(seq=seq):
                self.assertTrue(heist_stalled_edge_earned(recorded_heist(seq),recorded(seq)))

    def test_7_actual_return_turn_is_not_equivalent_to_paused_microstall(self):
        s=recorded(7707);i=recorded_heist(7707)
        md=deepcopy(s.metadata)
        md['current_geometry'].update(btc_change6=12.0,ema9_change6=2.0)
        # Only changes the recorded live 6s motion (synthetic positive boundary).
        self.assertTrue(heist_stalled_edge_earned(i,replace(s,metadata=md)))

    def test_7_stale_or_missing_native_parent_cannot_supply_new_negative(self):
        s=recorded(7707);i=recorded_heist(7707)
        md=deepcopy(s.metadata)
        md['current_geometry']['epoch_ms'] -= 30000.
        self.assertTrue(heist_stalled_edge_earned(i,replace(s,metadata=md)))

    def test_8_recorded_2_85_contract_parent_has_no_new_premium_opening(self):
        s=recorded(8301)
        g=s.metadata['current_geometry']
        self.assertAlmostEqual(g['btc_change60'],-1.90,places=2)
        self.assertAlmostEqual(s.no_ask,.51)
        self.assertFalse(_mature_premium_opening_has_fresh_momentum(s,Side.NO,2564.63,.51))
        self.assertFalse(any(x.reason=='COMMANDER_OBSERVED_INHERITED_PARENT_FIRST_MINUTE_CONTINUATION'
            for x in physical_entry_candidates(s)))

    def test_8_mature_premium_new_proven_continuation_still_qualifies(self):
        s=recorded(8301)
        md=deepcopy(s.metadata)
        md['current_geometry']['btc_change60']=-20.  # synthetic WITH-parent fresh pace
        new=replace(s,metadata=md)
        self.assertTrue(_mature_premium_opening_has_fresh_momentum(new,Side.NO,2564.63,.51))
        self.assertTrue(any(x.reason=='COMMANDER_OBSERVED_INHERITED_PARENT_FIRST_MINUTE_CONTINUATION'
            for x in physical_entry_candidates(new)))

    def test_prior_pid15740_53c_opening_positive_remains(self):
        s=case_snapshot('OPEN_0045')
        # PID15740's preserved wrapper lacks authentic generation/receipt.
        # Its measured candidate remains; no missing source may execute it.
        matches=[x for x in physical_entry_candidates(s) if
            x.reason=='COMMANDER_OBSERVED_INHERITED_PARENT_FIRST_MINUTE_CONTINUATION']
        self.assertEqual(len(matches),1)
        decision=OneCommander().decide_entry(matches,s,{})
        self.assertIs(decision.action,Action.WAIT)
        self.assertEqual(decision.reason,'OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED')

    def test_8_value_price_not_in_new_premium_maturity_restriction(self):
        s=recorded(8301)
        self.assertTrue(_mature_premium_opening_has_fresh_momentum(s,Side.NO,2564.63,.34))


if __name__=='__main__':
    unittest.main()
