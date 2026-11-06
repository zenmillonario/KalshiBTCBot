"""PID17744 entry-time causal replay: preserve #11; do not brief #12-15.

A trade's later P&L/MFE is deliberately excluded from the fixture. Historical
extreme/level-match candidate metadata is reconstructed from the committed
entry reason, as documented in the fixture. All geometry/gap/TP values are
those observed at the entry timestamp, not hindsight settlement outcomes.
"""
from __future__ import annotations
import json
import unittest
from pathlib import Path
from strategy_core.types import MarketSnapshot,Side
from strategy_core.commander_candidates import (
    physical_entry_candidates, historical_extreme_release_candidates,
    _counter_parent_return_briefing_ready,
)

PATH = Path(__file__).resolve().parents[2] / 'docs' / 'PID17744_RETURN_BRIEFING_CONTROLS.json'


def sample(trade: str, *, seconds_left: float|None = None, mirror: bool=False) -> MarketSnapshot:
    r=json.loads(PATH.read_text(encoding='utf-8'))['rows'][str(trade)]
    g=dict(r['geometry']); m=dict(r['mountain']); gap=dict(r['gap']); tp=dict(r['tp']); book=dict(r['book'])
    extra=dict(r.get('metadata_mission_evidence') or {})
    if mirror:
        def other(s): return 'NO' if s=='YES' else 'YES' if s=='NO' else s
        for k in ('ema_gap','btc_change6','btc_change9','btc_change30','btc_change60','ema9_change6','ema9_change30','ema9_change60'):
            if isinstance(g.get(k),(float,int)): g[k]=-g[k]
        for k in ('side','gap_side'): gap[k]=other(gap.get(k))
        m['owner_side']=other(m.get('owner_side'))
        if 'parent' in m: m['parent']={**m['parent'],'parent_side':other(m['parent'].get('parent_side'))}
        for k in ('contract_ownership_side','observed_target_side'): tp[k]=other(tp.get(k))
        book['no_ask'],book['yes_ask']=book.get('yes_ask'),book.get('no_ask')
        book['no_bid'],book['yes_bid']=book.get('yes_bid'),book.get('no_bid')
    parent=dict(m.get('parent') or {})
    md={
        'physical_current':True,
        'current_geometry':g,
        'mountain':{
            **m,
            'parent_structure':parent,
            'full_leg_scale_evidence': {'qualified':bool(parent.get('extended_parent'))},
            'completed_minute_parent_reference':{'mature_extension':False},
            'diagnostics':{'current_age_s':parent.get('parent_age_s'), 'source_ms':m.get('source_ms')},
        },
        'tp_geometry':tp,
        'ema9_ema30_cross_context':{'gap_lifecycle':{
            'current_side':gap.get('gap_side'),
            'stage':gap.get('stage'),
            'age_seconds_since_observed_cross':gap.get('age_s'),
            'current_abs_gap_btc':gap.get('abs_gap'),
            'continued_on_latest_cross_side':gap.get('continued_on_cross_side'),
            'continued_on_cross_side':gap.get('continued_on_cross_side'),
            'touching_spine':gap.get('touching_spine'),
        }},
        'commander_strategy':{'owned_territory':'ROLLING_MOUNTAIN','owned_side':m['owner_side']},
        **extra,
    }
    if mirror:
        ex=md.get('historical_extreme_release')
        if isinstance(ex,dict):
            ex=dict(ex)
            if 'side' in ex: ex['side']=other(ex['side'])
            if isinstance(ex.get('recent_level_match'),dict):
                ex['recent_level_match']={**ex['recent_level_match'],'side':other(ex['recent_level_match'].get('side'))}
            md['historical_extreme_release']=ex
    remaining=seconds_left if seconds_left is not None else r['seconds_left']
    return MarketSnapshot(now_ts=r['recorded_at_epoch'],ticker=r['ticker'],
        contract_age_s=900.0-remaining,
        yes_ask=book.get('yes_ask'),no_ask=book.get('no_ask'),
        yes_bid=book.get('yes_bid'),no_bid=book.get('no_bid'),
        quote_current=True,depth_available=True,metadata=md)


class PID17744ReturnBriefingTests(unittest.TestCase):
    def test_11_real_crest_turn_preserves_early_no_seed(self):
        s=sample('11')
        self.assertTrue(_counter_parent_return_briefing_ready(s,Side.NO,s.metadata['mountain']))
        self.assertTrue(any(i.side is Side.NO and 'EXTREME_SUB20_RETURN' in i.reason
                             for i in physical_entry_candidates(s)))

    def test_12_only_six_second_green_bounce_no_early_yes_briefing(self):
        s=sample('12')
        self.assertFalse(_counter_parent_return_briefing_ready(s,Side.YES,s.metadata['mountain']))
        self.assertFalse(any(i.side is Side.YES and 'EXTREME_SUB20_RETURN' in i.reason
                              for i in physical_entry_candidates(s)))

    def test_13_cheaper_repeat_while_down_expanding_stays_silent(self):
        s=sample('13')
        self.assertFalse(any(i.side is Side.YES and 'EXTREME_SUB20_RETURN' in i.reason
                              for i in physical_entry_candidates(s)))

    def test_14_small_short_counterpop_not_a_reversal_entry_window(self):
        s=sample('14')
        self.assertFalse(_counter_parent_return_briefing_ready(s,Side.YES,s.metadata['mountain']))
        self.assertFalse(any(i.side is Side.YES for i in historical_extreme_release_candidates(s)))

    def test_15_late_level_retest_below_parent_ema9_no_yes_entry(self):
        s=sample('15')
        self.assertFalse(any(i.side is Side.YES and 'LEVEL_MATCH' in i.reason
                              for i in physical_entry_candidates(s)))

    def test_16_parent_aligned_no_rollover_not_suppressed(self):
        s=sample('16')
        self.assertTrue(_counter_parent_return_briefing_ready(s,Side.NO,s.metadata['mountain']))

    def test_mirrored_real_crest_turn_for_yes_remains_available(self):
        s=sample('11',mirror=True)
        self.assertTrue(_counter_parent_return_briefing_ready(s,Side.YES,s.metadata['mountain']))
        self.assertTrue(any(i.side is Side.YES and 'EXTREME_SUB20_RETURN' in i.reason
                             for i in physical_entry_candidates(s)))

    def test_mirrored_false_counter_bounce_no_briefing(self):
        s=sample('12',mirror=True)
        self.assertFalse(_counter_parent_return_briefing_ready(s,Side.NO,s.metadata['mountain']))
        self.assertFalse(any(i.side is Side.NO and 'EXTREME_SUB20_RETURN' in i.reason
                             for i in physical_entry_candidates(s)))

    def test_old_parent_tp_with_only_two_minutes_remains_quiet(self):
        s=sample('11',seconds_left=140)
        self.assertFalse(_counter_parent_return_briefing_ready(s,Side.NO,s.metadata['mountain']))

    def test_developed_opposite_30s_counter_pullback_not_permanently_banned(self):
        s=sample('12')
        md=dict(s.metadata); g=dict(md['current_geometry']);g['btc_change30']=20.0
        md['current_geometry']=g
        # This confirms the change concerns genuinely developed movement,
        # not an inflexible block on counter-arcs or the age of a Rail.
        s=MarketSnapshot(now_ts=s.now_ts,ticker=s.ticker,contract_age_s=s.contract_age_s,
            yes_ask=s.yes_ask,no_ask=s.no_ask,yes_bid=s.yes_bid,no_bid=s.no_bid,
            quote_current=True,depth_available=True,metadata=md)
        self.assertTrue(_counter_parent_return_briefing_ready(s,Side.YES,md['mountain']))

if __name__=='__main__':unittest.main()
