"""Bounded original PID21672 snapshots; no hypothetical whole-run replay claim."""
import gzip
import json
import unittest
from copy import deepcopy
from pathlib import Path

from strategy_core.commander_candidates import main_return_matches_established_parent
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent

FIXTURE = Path(__file__).with_name('fixtures') / 'pid21672_live_parent_cases.json.gz'


def cases():
    with gzip.open(FIXTURE, 'rt') as f:
        v = json.load(f)
    assert v['schema'] == 'pid21672.current_parent.admission.v1'
    return {r['sequence']:r for r in v['records']}


def snapshot_and_intent(r):
    m = deepcopy(r['metadata'])
    book = r['native_book']
    yes_bid = book['yes_bids'][0]['price'] if book['yes_bids'] else None
    no_bid = book['no_bids'][0]['price'] if book['no_bids'] else None
    # Kalshi YES ask is 1 - NO bid and vice versa.
    s=MarketSnapshot(now_ts=r['now_ts'],ticker=r['ticker'],contract_age_s=r['now_ts']-r['open_ts'],
        yes_ask=(1-no_bid if no_bid is not None else None),
        no_ask=(1-yes_bid if yes_bid is not None else None),
        yes_bid=yes_bid,no_bid=no_bid,metadata=m,quote_current=True,depth_available=True)
    raw=r['intent'];i=ToolIntent(tool=raw['tool'],territory_id=raw['territory_id'],
        lane=Lane(raw['lane']),side=Side(raw['side']),action=Action(raw['action']),
        opportunity_id=raw.get('opportunity_id'),max_price=raw.get('max_price'),
        size_tier=raw.get('size_tier'),reason=raw['reason'],source_time=raw['source_time'],
        expires_when=raw.get('expires_when'),metadata=raw.get('metadata') or {})
    return s,i


class PID21672ParentTransfer(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.records=cases()

    def test_recorded_no_mountain_conflicts_with_living_yes_release(self):
        s,i=snapshot_and_intent(self.records[5487])
        self.assertEqual(s.metadata['mission_context']['parent']['side'],'YES')
        self.assertEqual(s.metadata['mission_context']['parent']['basis'],'CONFIRMED_RELEASE_TRANSFER')
        self.assertFalse(main_return_matches_established_parent(i,s))

    def test_later_no_rail_is_separate_policy_not_banned(self):
        s,i=snapshot_and_intent(self.records[6109]);self.assertEqual(i.tool,'RAIL')
        self.assertTrue(main_return_matches_established_parent(i,s))

    def test_heist_entry_not_new_main_veto(self):
        for seq in (621,6617):
            with self.subTest(seq=seq):
                s,i=snapshot_and_intent(self.records[seq]);self.assertEqual(i.tool,'MARKET_HEIST')
                self.assertTrue(main_return_matches_established_parent(i,s))

    def test_recorded_pid17588_first_minute_inherited_no_stays_eligible(self):
        # A separately authorized rollover continuation, not a hypothetical
        # replay or a first-minute price-only permission.
        from tests.tool_rack.pid17588_late_scout_fixtures import snapshot
        from strategy_core.commander_candidates import _physical_entry_candidates
        s=snapshot('PID17588:7037')
        matching=[i for i in _physical_entry_candidates(s)
                  if i.reason == 'COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION']
        self.assertEqual(len(matching),1)
        self.assertTrue(main_return_matches_established_parent(matching[0],s))
        modified=deepcopy(matching[0].metadata)
        modified['commander_physical_evidence']['inherited_leg_live']['price_still_advancing']=False
        from dataclasses import replace
        self.assertFalse(main_return_matches_established_parent(
            replace(matching[0],metadata=modified),s))

    def test_old_release_not_accepted_without_same_sample_evidence(self):
        s,i=snapshot_and_intent(self.records[5487]);
        s.metadata['mission_context']['parent']['source_ms']-=1000
        self.assertTrue(main_return_matches_established_parent(i,s))

    def test_unconfirmed_transfer_not_new_veto(self):
        s,i=snapshot_and_intent(self.records[5487]);
        s.metadata['mission_context']['parent']['basis']='OBSERVED_COMPARISON_ENVELOPE'
        self.assertTrue(main_return_matches_established_parent(i,s))

if __name__=='__main__':unittest.main()
