"""Source-bound PID10760 inherited BTC push / unproven EMA9 parent distinction.

All listed physical snapshots and ledger source SHAs originate from the original
PID10760 closed PAPER recording, not a hypothetical replay. Entry decisions in
these tests are *candidate* decisions, never modeled fills or profits.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import replace
import gzip
import json
from pathlib import Path
import unittest

from strategy_core.types import MarketSnapshot, Action, Side
from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import (
    physical_entry_candidates, _preopen_observed_ema9_sprout_continuation,
)
from strategy_core.directional_parent import directional_parent_evidence

SOURCE = Path(__file__).with_name('fixtures') / 'pid10760_preopen_rollover_source_frames.json.gz'
with gzip.open(SOURCE, 'rt', encoding='utf8') as f:
    CORPUS = json.load(f)


def recorded_case(seq: int) -> MarketSnapshot:
    r=CORPUS['frames'][str(seq)]
    return MarketSnapshot(now_ts=r['now_ts'], ticker=r['ticker'],
        contract_age_s=r['now_ts']-r['open_ts'], yes_ask=r['yes_ask'],
        no_ask=r['no_ask'], yes_bid=r['yes_bid'], quote_current=r['quote_current'],
        depth_available=True, entry_allowed=r['entry_allowed'],
        metadata=deepcopy(r['metadata']))


class PID10760CausalPreopenTests(unittest.TestCase):
    def test_source_provenance_and_no_invented_historical_ema9_parent(self):
        self.assertEqual(CORPUS['source_zip_sha256'],
            'f676cdc8b44688f92382972c489dbb2eb745096ab1f8a6216493e7b00a61a0ff')
        self.assertEqual(sorted(CORPUS['frames']), sorted(map(str,(354,445,461,480,500,520,539,598,704,1480))))
        for key,row in CORPUS['frames'].items():
            with self.subTest(seq=key):
                self.assertEqual(row['sequence'],int(key))
                self.assertEqual(len(row['source_decision_sha256']),64)
                self.assertAlmostEqual(row['metadata']['current_geometry']['epoch_ms']/1000.,
                                       row['metadata']['ema9_ema30_cross_context']['source_ms']/1000.,places=3)
        s=recorded_case(480)
        self.assertFalse(directional_parent_evidence(s)['qualified'])
        self.assertEqual(directional_parent_evidence(s)['gap_side'],'NO')
        self.assertEqual(s.metadata['current_geometry']['arc_direction'],'UP')

    def test_214521_falling_price_first_quote_remains_wait(self):
        s=recorded_case(445)
        self.assertAlmostEqual(s.yes_ask,.49)
        self.assertEqual(OneCommander().physical_entry_candidates(s),())

    def test_214525_dip_remains_wait(self):
        s=recorded_case(461)
        self.assertAlmostEqual(s.yes_ask,.49)
        self.assertEqual(OneCommander().physical_entry_candidates(s),())

    def test_214530_physically_earned_preopen_spanning_yes_is_eligible(self):
        s=recorded_case(480)
        self.assertAlmostEqual(s.yes_ask,.53)
        self.assertAlmostEqual(s.metadata['current_geometry']['btc_change60'],25.22)
        self.assertFalse(directional_parent_evidence(s)['qualified'])
        cands=OneCommander().physical_entry_candidates(s)
        selected=[x for x in cands if x.reason=='COMMANDER_OBSERVED_PREOPEN_EMA9_SPROUT_CONTINUATION']
        self.assertEqual(len(selected),1,[x.reason for x in cands])
        self.assertIs(selected[0].side,Side.YES)
        self.assertAlmostEqual(selected[0].size_tier,25.)
        self.assertAlmostEqual(selected[0].max_price,.55)
        proof=selected[0].metadata['commander_physical_evidence']
        self.assertIs(proof['historical_parent_qualified'],False)
        self.assertEqual(proof['causal_parent_claim'], 'CURRENT_EMA9_CHILD_ONLY_NOT_MATURE_INHERITED_PARENT')
        self.assertLess(proof['preopen_source_coverage_start_ms'],(s.now_ts-s.contract_age_s-30.)*1000.)
        decision=OneCommander().decide_entry(cands,s,{})
        self.assertIs(decision.action,Action.ENTER,decision)
        # Not an actual bought order; all fills remain the original recorded ledger.

    def test_214535_poor_micro_momentum_does_not_chase(self):
        s=recorded_case(500)
        self.assertFalse(OneCommander().physical_entry_candidates(s))

    def test_original_beyond_55c_window_stays_wait(self):
        for seq in (520,539,598,704):
            with self.subTest(seq=seq):
                s=recorded_case(seq)
                self.assertGreater(s.yes_ask,.55)
                self.assertFalse(any(x.reason=='COMMANDER_OBSERVED_PREOPEN_EMA9_SPROUT_CONTINUATION'
                                     for x in OneCommander().physical_entry_candidates(s)))

    def test_no_open_entry_without_30s_of_source_before_ticker(self):
        s=recorded_case(480)
        md=deepcopy(s.metadata)
        md['ema9_ema30_cross_context']['coverage']['first_source_ms']=(s.now_ts-s.contract_age_s-10.)*1000.
        self.assertIsNone(_preopen_observed_ema9_sprout_continuation(replace(s,metadata=md),directional_parent_evidence(s)))
        md=deepcopy(s.metadata)
        md['ema9_ema30_cross_context']['coverage']['max_observed_source_gap_seconds']=20.
        self.assertIsNone(_preopen_observed_ema9_sprout_continuation(replace(s,metadata=md),directional_parent_evidence(s)))

    def test_generation_change_stale_geometry_or_book_cannot_buy(self):
        s=recorded_case(480)
        self.assertEqual(OneCommander().physical_entry_candidates(replace(s,quote_current=False)),())
        self.assertEqual(OneCommander().physical_entry_candidates(replace(s,entry_allowed=False)),())
        md=deepcopy(s.metadata)
        md['current_geometry']['connection_epoch']=4
        self.assertEqual(OneCommander().physical_entry_candidates(replace(s,metadata=md)),())
        md=deepcopy(s.metadata)
        md['current_geometry']['epoch_ms']-=15000.
        self.assertEqual(OneCommander().physical_entry_candidates(replace(s,metadata=md)),())

    def test_opposite_confirmed_parent_tp_or_spine_collision_remain_wait(self):
        s=recorded_case(480)
        md=deepcopy(s.metadata)
        md['tp_geometry']['contract_ownership_side']='NO'
        self.assertEqual(OneCommander().physical_entry_candidates(replace(s,metadata=md)),())
        md=deepcopy(s.metadata)
        md['tp_geometry']['target_between_ema9_ema30']=True
        self.assertEqual(OneCommander().physical_entry_candidates(replace(s,metadata=md)),())
        md=deepcopy(s.metadata)
        md['release_confirmed_current']=True
        self.assertEqual(OneCommander().physical_entry_candidates(replace(s,metadata=md)),())
        md=deepcopy(s.metadata)
        md['ema9_ema30_cross_context']['gap_lifecycle'].update({
            'observed_side_residence_seconds':1000., 'stage':'MATURE',
            'current_side':'NO', 'current_abs_gap_btc':100.,
        })
        self.assertTrue(directional_parent_evidence(replace(s,metadata=md))['qualified'])
        self.assertFalse(OneCommander().physical_entry_candidates(replace(s,metadata=md)))

    def test_premium_cap_and_out_of_open_window_not_relaxed(self):
        s=recorded_case(480)
        self.assertFalse(OneCommander().physical_entry_candidates(replace(s,yes_ask=.56)))
        self.assertFalse(OneCommander().physical_entry_candidates(replace(s,contract_age_s=65.)))
        self.assertFalse(OneCommander().physical_entry_candidates(replace(s,contract_age_s=11.)))

    def test_bad_price_60s_or_gap_trend_is_not_earned(self):
        s=recorded_case(480)
        for key, bad in [('btc_change6',0.), ('btc_change9',3.),('btc_change30',10.),('btc_change60',5.),
                         ('ema9_change6',0.), ('ema9_change30',1.),('ema9_change60',0.),('ema_gap',-20.)]:
            with self.subTest(key=key):
                md=deepcopy(s.metadata);md['current_geometry'][key]=bad
                self.assertFalse(OneCommander().physical_entry_candidates(replace(s,metadata=md)))

    def test_historical_strong_inherited_53c_opening_remains_authorized(self):
        from tests.tool_rack.test_pid15740_inherited_up_rail import case_snapshot
        s=case_snapshot('OPEN_0045')
        from strategy_core.commander_candidates import physical_entry_candidates
        # Historical partial wrapper retains its measured opening species;
        # executable shared-source provenance is separately tested by PID15740.
        self.assertTrue(any(x.reason=='COMMANDER_OBSERVED_INHERITED_PARENT_FIRST_MINUTE_CONTINUATION'
            and x.side is Side.YES for x in physical_entry_candidates(s)))
        self.assertEqual(OneCommander().physical_entry_candidates(s),())

    def test_original_pid18244_no_extreme_winner_stays_eligible(self):
        from tests.tool_rack.test_pid18244_parent_custody_protection import PID18244RecordedControlTests
        PID18244RecordedControlTests().test_6_first_class_recent_level_match_no_entry_remains()


if __name__ == '__main__':
    unittest.main()
