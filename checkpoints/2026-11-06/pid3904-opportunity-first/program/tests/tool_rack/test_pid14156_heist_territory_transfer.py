"""PID14156: strict current-EMA9 Heist admission and true Mountain parent scale.

This corpus preserves the original recorded source frames and tentative intents;
no simulated fills, market-path hindsight, or future prices enter the tests.
No adviser WAIT overrides the single Commander.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import gzip
import json
from pathlib import Path
import unittest

from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import physical_entry_candidates

with gzip.open(Path(__file__).parent / 'fixtures/pid14156_selected_source_decisions.json.gz',
               'rt',encoding='utf-8') as f:
    CORPUS = json.load(f)


def case(seq: int):
    r=CORPUS['frames'][str(seq)]
    s=MarketSnapshot(now_ts=r['now_ts'],ticker=r['ticker'],
        contract_age_s=r['contract_age_s'],metadata=deepcopy(r['physical_metadata']),
        quote_current=True,depth_available=True,**r['book_top'])
    intents=[]
    for raw in r['candidate_intents']:
        intents.append(ToolIntent(tool=raw['tool'],territory_id=raw['territory_id'],
            lane=Lane(raw['lane']),side=Side(raw['side']),action=Action(raw['action']),
            opportunity_id=raw['opportunity_id'],max_price=raw['max_price'],
            size_tier=raw['size_tier'],reason=raw['reason'],source_time=raw['source_time'],
            metadata=deepcopy(raw['metadata'])))
    return s,intents


class PID14156HeistTerritoryTransferTests(unittest.TestCase):
    def test_recorded_source_identity_no_alternate_run_or_fill_claim(self):
        self.assertEqual(CORPUS['original_sha256'],
            '5ee2434582df7924a19c507c82df62d098316ab20e74ec1cd5eb8f35b7bab5f4')
        self.assertEqual(set(CORPUS['frames']), {'1444','2384','4250','4285','4329','4345','6902','7868'})
        for key,rec in CORPUS['frames'].items():
            with self.subTest(seq=key):
                self.assertEqual(rec['sequence'],int(key))
                self.assertIs(rec['physical_metadata']['physical_current'],True)
                self.assertLess(rec['now_ts']-rec['physical_metadata']['current_geometry']['epoch_ms']/1000,3.)

    def test_1950_earliest_falling_lower_edge_is_still_wait(self):
        s,intents=case(4250)
        self.assertEqual(s.metadata['heist']['current_zone'],'LOWER')
        self.assertLess(s.metadata['current_geometry']['btc_change6'],0)
        self.assertFalse(OneCommander()._same_gap_heist_lower_return_earned(intents[0],s))
        self.assertEqual(OneCommander()._entry_strategy_denial(intents[0],s),
            'OPPORTUNITY_HEIST_REPEATED_BILATERAL_WALLS_REQUIRED')

    def test_1950_first_earned_same_gap_heist_lower_return_is_not_false_fade(self):
        s,intents=case(4285)
        self.assertEqual(len(intents),1)
        self.assertAlmostEqual(s.yes_ask,.13)
        self.assertEqual(s.metadata['ema9_ema30_cross_context']['gap_lifecycle']['current_side'],'YES')
        self.assertEqual(s.metadata['mountain']['owner_side'],'NO')  # opposite SHORT child
        self.assertGreater(s.metadata['current_geometry']['btc_change6'],14.)
        self.assertTrue(OneCommander()._same_gap_heist_lower_return_earned(intents[0],s))
        self.assertIsNone(OneCommander()._entry_strategy_denial(intents[0],s))
        # No invented modeled fills: here the Commander only grants further
        # normal quote/source/depth/mission admission consideration.

    def test_1950_repeated_lower_edge_without_current_rebound_remains_wait(self):
        s,intents=case(4329)
        self.assertLess(s.metadata['current_geometry']['btc_change9'],0)
        self.assertFalse(OneCommander()._same_gap_heist_lower_return_earned(intents[0],s))
        self.assertEqual(OneCommander()._entry_strategy_denial(intents[0],s),
            'OPPORTUNITY_HEIST_REPEATED_BILATERAL_WALLS_REQUIRED')

    def test_1950_inner_zone_after_rebound_does_not_spawn_entry(self):
        s,intents=case(4345)
        self.assertEqual(s.metadata['heist']['current_zone'],'INNER')
        self.assertEqual(intents,[])

    def test_1934_opposite_gap_heist_no_does_not_use_same_gap_exception(self):
        s,intents=case(1444)
        self.assertEqual(s.metadata['ema9_ema30_cross_context']['gap_lifecycle']['current_side'],'YES')
        self.assertFalse(OneCommander()._same_gap_heist_lower_return_earned(intents[0],s))

    def test_2003_expensive_counter_spout_yes_not_granted_exemption(self):
        s,intents=case(6902)
        self.assertEqual(s.metadata['ema9_ema30_cross_context']['gap_lifecycle']['current_side'],'NO')
        self.assertAlmostEqual(s.yes_ask,.40)
        self.assertFalse(OneCommander()._same_gap_heist_lower_return_earned(intents[0],s))

    def test_source_stale_or_opportunity_stale_or_fake_level_cannot_grant_exception(self):
        s,intents=case(4285)
        md=deepcopy(s.metadata)
        md['current_geometry']['epoch_ms']-=30000.
        self.assertFalse(OneCommander()._same_gap_heist_lower_return_earned(intents[0],replace(s,metadata=md)))
        self.assertFalse(OneCommander()._same_gap_heist_lower_return_earned(
            replace(intents[0],source_time=s.now_ts-20),s))
        md=deepcopy(s.metadata);md['heist']['current_zone']='CENTER'
        self.assertFalse(OneCommander()._same_gap_heist_lower_return_earned(intents[0],replace(s,metadata=md)))
        md=deepcopy(s.metadata);md['ema9_ema30_cross_context']['gap_lifecycle']['current_side']='NO'
        self.assertFalse(OneCommander()._same_gap_heist_lower_return_earned(intents[0],replace(s,metadata=md)))

    def test_1938_immature_fast_extreme_does_not_count_as_parent_terminal(self):
        s,intents=case(2384)
        m=s.metadata['mountain'];g=s.metadata['current_geometry']
        self.assertEqual(m.get('full_leg_scale_evidence',{}),{})
        self.assertEqual(m.get('completed_minute_parent_reference',{}),{})
        self.assertIs(m['mature_edge'],False)
        self.assertLess(g['arc_age_sec'],13.)
        self.assertFalse(any(x.reason=='COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN'
            for x in physical_entry_candidates(s)))

    def test_true_full_scale_fast_extreme_positive_boundary_still_eligible(self):
        s,_=case(2384)
        md=deepcopy(s.metadata)
        md['mountain']['full_leg_scale_evidence']={'qualified':True,'source_ms':md['mountain']['source_ms']}
        # Synthetic *qualification proof* variation, never described as
        # historical PID14156 winning fill.
        self.assertTrue(any(x.reason=='COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN'
            for x in physical_entry_candidates(replace(s,metadata=md))))

    def test_historical_pid17588_one_minute_true_extreme_is_not_starved(self):
        # Actual ordered prehistory, not synthetic replacement geometry. The
        # approved NO parent has a current 60.45s arc and 27s extreme age,
        # unlike the 12.49s/2.21s PID14156 false upper-edge fade.
        from tests.tool_rack.pid17588_late_scout_fixtures import (
            snapshot, probe_group,
        )
        old=snapshot('PID17588:4416')
        self.assertGreater(old.metadata['current_geometry']['arc_age_sec'],60.0)
        self.assertGreater((old.metadata['mountain']['source_ms']-
                            old.metadata['mountain']['edge_extreme_ms'])/1000.0,25.0)
        rows=probe_group('PID17588_trade2_positive')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['decision']['action'],'ENTER')
        self.assertEqual(rows[0]['decision']['side'],'YES')

    def test_original_pid18244_level_match_large_winner_entry_stays_authorized(self):
        from tests.tool_rack.test_pid18244_parent_custody_protection import PID18244RecordedControlTests
        PID18244RecordedControlTests().test_6_first_class_recent_level_match_no_entry_remains()


if __name__=='__main__':
    unittest.main()
