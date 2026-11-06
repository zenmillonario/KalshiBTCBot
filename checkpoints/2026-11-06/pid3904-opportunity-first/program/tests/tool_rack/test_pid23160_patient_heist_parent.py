"""PID23160 source-bound patient Heist / with-EMA9 behavior controls.

These frames and prefix geometry rows are from the SHA-256 verified original
PAPER recording. Decisions here are isolated candidates, not simulated fills
or an exact modified-engine tape replay.
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
    _current_ema9_renewed_flow_rejoin,
    _counterparent_level_rejection_sustained,
)
from strategy_core.detectors.heist_geometry import detect_heist_geometry
from strategy_core.config_loader import load_heist_detector_config

_ROOT = Path(__file__).resolve().parents[2]
_P = Path(__file__).with_name('fixtures') / 'pid23160_heist_parent_selected.json.gz'
with gzip.open(_P, 'rt', encoding='utf-8') as f:
    SOURCE = json.load(f)
_CFG = load_heist_detector_config(_ROOT/'strategy_core/config/heist.json')


def case(seq:int, *, reported_level:bool=False) -> MarketSnapshot:
    v=SOURCE['frames'][str(seq)]
    md=deepcopy(v['metadata'])
    if reported_level:
        assert v['source_reported_level'] is not None
        # The emitted intent carries the original contemporary level match.
        # It is reconstructed as a proposed candidate input, not a new signal.
        md['historical_extreme_release']={'recent_level_match':deepcopy(v['source_reported_level'])}
    return MarketSnapshot(now_ts=v['now_ts'],ticker=v['ticker'],contract_age_s=v['now_ts']-v['open_ts'],
        yes_bid=v['yes_bid'],no_bid=v['no_bid'],yes_ask=v['yes_ask'],no_ask=v['no_ask'],
        quote_current=v['quote_current'],depth_available=True,entry_allowed=v['entry_allowed'],metadata=md)


def terrain(seq:int):
    return detect_heist_geometry(SOURCE['frames'][str(seq)]['geometry_path_to_this_frame'],_CFG)


class PID23160PatientHeistTests(unittest.TestCase):
    def test_exact_original_source_identity_and_causal_prefixes(self):
        self.assertEqual(SOURCE['source_archive_sha256'],
                         'dd4f6eec165e1eaf6607e62dd4faeccc9ce41361c585ab1a7ed5ad2cb3dcfba5')
        self.assertEqual(SOURCE['original_frame_count'],7652)
        self.assertEqual(set(SOURCE['frames']),set(map(str,(2532,4029,4973,5587,6398,6908,7244,7533))))
        for key,v in SOURCE['frames'].items():
            with self.subTest(seq=key):
                self.assertEqual(v['sequence'],int(key))
                self.assertEqual(len(v['record_sha256']),64)
                rows=v['geometry_path_to_this_frame']
                self.assertTrue(rows)
                self.assertLessEqual(rows[-1]['epoch_ms'],v['now_ts']*1000+2000)
                self.assertTrue(all(a['epoch_ms']<b['epoch_ms'] for a,b in zip(rows,rows[1:])))
                self.assertEqual(rows[-1]['epoch_ms'],v['metadata']['current_geometry']['epoch_ms'])

    def test_true_classic_repeated_heist_is_not_removed(self):
        g=terrain(2532)
        self.assertTrue(g.qualified_box,g.diagnostics)
        self.assertTrue(g.diagnostics.get('classic_qualified'))
        self.assertFalse(g.diagnostics.get('wide_heist_qualified'))

    def test_wide_only_directional_boxes_remain_watch_not_heist_owner(self):
        for seq in (4029,4973,5587,6398,6908,7244):
            with self.subTest(seq=seq):
                g=terrain(seq)
                self.assertFalse(g.qualified_box,(seq,g.diagnostics))
                self.assertFalse(g.diagnostics.get('wide_heist_qualified'))
                self.assertTrue(g.compression_unresolved)

    def test_original_002101_no_29_is_physically_earned_regular_main(self):
        s=case(4973)
        self.assertAlmostEqual(s.no_ask,.29)
        self.assertEqual(s.metadata['ema9_ema30_cross_context']['gap_lifecycle']['current_side'],'NO')
        r=_current_ema9_renewed_flow_rejoin(s)
        self.assertIsNotNone(r)
        self.assertIs(r[0],Side.NO)
        intents=OneCommander().physical_entry_candidates(s)
        ours=[x for x in intents if x.reason=='COMMANDER_CURRENT_EMA9_RENEWED_PARENT_REJOIN']
        self.assertEqual(len(ours),1,[x.reason for x in intents])
        self.assertEqual(ours[0].size_tier,10)
        self.assertAlmostEqual(ours[0].max_price,.30)
        d=OneCommander().decide_entry(intents,s,{})
        self.assertIs(d.action,Action.ENTER,d)
        self.assertIs(d.intent.side,Side.NO)

    def test_existing_counterparent_and_expensive_states_do_not_get_main_join(self):
        for seq in (2532,4029,5587,6398,6908,7244,7533):
            with self.subTest(seq=seq):
                self.assertIsNone(_current_ema9_renewed_flow_rejoin(case(seq)))

    def test_rejoin_requires_direct_parent_tp_freshness_and_price(self):
        s=case(4973)
        self.assertIsNone(_current_ema9_renewed_flow_rejoin(replace(s,no_ask=.31)))
        self.assertIsNone(_current_ema9_renewed_flow_rejoin(replace(s,quote_current=False)))
        self.assertIsNone(_current_ema9_renewed_flow_rejoin(replace(s,entry_allowed=False)))
        md=deepcopy(s.metadata);md['tp_geometry']['contract_ownership_side']='YES'
        self.assertIsNone(_current_ema9_renewed_flow_rejoin(replace(s,metadata=md)))
        md=deepcopy(s.metadata);md['current_geometry']['btc_change9']=20.
        self.assertIsNone(_current_ema9_renewed_flow_rejoin(replace(s,metadata=md)))
        md=deepcopy(s.metadata);md['current_geometry']['ema9_change6']=3.
        self.assertIsNone(_current_ema9_renewed_flow_rejoin(replace(s,metadata=md)))
        md=deepcopy(s.metadata);md['physical_current']=False
        self.assertIsNone(_current_ema9_renewed_flow_rejoin(replace(s,metadata=md)))

    def test_000954_false_support_during_living_down_parent_not_allowed(self):
        s=case(2532,reported_level=True)
        self.assertAlmostEqual(s.yes_ask,.076)
        self.assertEqual(s.metadata['ema9_ema30_cross_context']['gap_lifecycle']['current_side'],'NO')
        self.assertEqual(s.metadata['current_geometry']['current_native_direction'],'UP')
        self.assertFalse(_counterparent_level_rejection_sustained(s,Side.YES))
        self.assertFalse(any(x.reason=='COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN'
                             for x in OneCommander().physical_entry_candidates(s)))

    def test_source_signed_gap_parent_not_short_child_direction(self):
        s=case(2532,reported_level=True)
        md=deepcopy(s.metadata)
        md['ema9_ema30_cross_context']['gap_lifecycle']['current_side']='YES'
        # Inconsistent source current gap/side is not valid evidence.
        self.assertFalse(_counterparent_level_rejection_sustained(replace(s,metadata=md),Side.YES))

    def test_pid23160_6_cheap_microstall_is_superseded_by_parent_scale_and_runway(self):
        s=case(7533)
        g=s.metadata['current_geometry'];m=s.metadata['mountain']
        self.assertLess(g['arc_age_sec'],60.)
        self.assertGreater(g['btc_change30'],0.);self.assertGreater(g['ema9_change30'],0.)
        self.assertFalse(m['parent_structure']['parent_terminal_ready'])
        self.assertLess(s.metadata['tp_geometry']['remaining_seconds'],155.)
        commander=OneCommander();c=commander.physical_entry_candidates(s)
        self.assertFalse(any(x.side is Side.NO for x in c))
        self.assertIn('OPPORTUNITY_MOUNTAIN_PARENT_TERMINAL_PROOF_REQUIRED',
            [p['reason'] for p in commander.opportunity_review['candidates']])

    def test_prior_pid18244_cheap_no_extreme_and_pid15740_opening_unchanged(self):
        from tests.tool_rack.test_pid18244_parent_custody_protection import PID18244RecordedControlTests
        from tests.tool_rack.test_pid15740_inherited_up_rail import case_snapshot
        PID18244RecordedControlTests().test_6_first_class_recent_level_match_no_entry_remains()
        s=case_snapshot('OPEN_0045')
        from strategy_core.commander_candidates import physical_entry_candidates
        self.assertTrue(any(x.side is Side.YES and x.reason=='COMMANDER_OBSERVED_INHERITED_PARENT_FIRST_MINUTE_CONTINUATION'
                            for x in physical_entry_candidates(s)))
        self.assertEqual(OneCommander().physical_entry_candidates(s),())

if __name__=='__main__':unittest.main()
