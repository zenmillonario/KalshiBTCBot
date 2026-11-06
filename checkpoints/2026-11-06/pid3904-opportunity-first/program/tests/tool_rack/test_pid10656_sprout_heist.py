"""Current-source sprout quality controls and the actual PID10656 opening.

The later opening decisions retain original NO inventory. These isolated
admission/briefing checks never assert a replacement entry, exit or P/L path.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import tempfile
import unittest
from unittest.mock import patch

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import (
    MOUNTAIN_ROLLOVER_CONTINUATION_MAX, MOUNTAIN_ROLLOVER_CONTINUATION_WINDOW_S,
    heist_sprout_fade_ready, positive_candidate_matches_continuation,
)
from strategy_core.paper_execution import PaperExecutioner
from strategy_core.tool_rack import ToolRackController
from strategy_core.tools.heist import HeistConfig
from strategy_core.tools.release import ReleaseConfig
from strategy_core.types import Action, Side
from tests.tool_rack.pid10656_sprout_fixtures import (
    book, entry_intent, manifest, mirrored, opening_sequences, original_event,
    physical, record, snapshot,
)


DENIAL = 'COMMANDER_HEIST_FRESH_SPROUT_REQUIRES_CAUSAL_TURN'


class PID10656SproutHeistTests(unittest.TestCase):
    def test_original_records_and_histories_remain_hash_bound(self):
        evidence = manifest()
        self.assertEqual(evidence['source_archive_sha256'],
            '187a2fa705d5aa609c3b84e6de2213322821e9ccb04b233b742e43d90f3864f7')
        self.assertEqual(evidence['original_decisions']['sha256'],
            'f608ed8cd87cc9e6907b56cca771635b2f6432c66df6756cf684b2b84a134c0e')
        self.assertEqual(len(evidence['record_order']), 131)
        for seq in evidence['record_order']:
            data = record(seq)  # Validates the full raw/canonical corpus once.
            self.assertEqual(data['sequence'], seq)
            self.assertEqual(data['sha256'], evidence['records'][str(seq)]['sha256'])
        for previous, current in zip(range(7257,7380), range(7258,7381)):
            self.assertEqual(record(current)['previous_sha256'], record(previous)['sha256'])

    def test_original_winning_entries_keep_intent_price_quantity_and_fee(self):
        for seq, qty, price, fee in ((2618,47,'0.5100','0.83'), (4771,312,'0.0750','1.52')):
            with self.subTest(sequence=seq), tempfile.TemporaryDirectory() as temp:
                current, intent = snapshot(seq), entry_intent(seq)
                preserved = deepcopy(intent)
                decision = OneCommander().decide_entry((intent,), current, {})
                self.assertIsNotNone(decision.intent,decision)
                # Admission appends current species/source diagnostics; all
                # original execution fields and metadata remain byte-equal.
                self.assertEqual(replace(decision.intent,metadata={k:v for k,v in decision.intent.metadata.items()
                    if k!='commander_opportunity'}),preserved)
                self.assertTrue(decision.intent.metadata['commander_opportunity']['qualified'])
                self.assertEqual(decision.reason, 'COMMANDER_ACCEPTED_TOOL_INTENT')
                # A fresh component ledger uses the executor's mandatory
                # $1,000 start. Both original $25 lots fit that balance; no
                # prior account or alternate session path is manufactured.
                with PaperExecutioner(temp) as executor:
                    receipt = executor.execute(decision, book(seq), now_ts=current.now_ts,
                        command_id=f'PID10656:{seq}:PRESERVED_COMPONENT')
                    self.assertEqual(receipt.status, 'BOOKED', receipt.reason)
                    event = receipt.event
                    self.assertEqual(event['qty'], qty)
                    self.assertEqual(Decimal(event['price']), Decimal(price))
                    self.assertEqual(Decimal(event['fees']), Decimal(fee))
                    original = original_event(seq, 'ENTRY')
                    for key in ('price','qty','fees','cost','cash_delta','reason','side'):
                        self.assertEqual(event[key], original[key], key)
                self.assertEqual(intent, preserved)

    def test_original_positive_outcomes_are_recorded_controls_not_added_profit(self):
        for seq, price, net in ((4770,'0.9460','19.4920'),(4792,'0.1600','22.0600')):
            event = original_event(seq, 'EXIT')
            self.assertEqual(Decimal(event['price']), Decimal(price))
            self.assertEqual(Decimal(event['net_pnl']), Decimal(net))
        self.assertEqual(entry_intent(4771).reason, 'RELEASE_CONFIRMED_LEVIATHAN_HANDOFF')

    def test_recorded_trade3_calibrated_heist_waits_for_actual_turn(self):
        current, intent = snapshot(7304), entry_intent(7304)
        self.assertTrue(intent.metadata['dual_lane_counterfade_calibrated'])
        self.assertTrue(current.metadata['heist']['qualified_box'])
        self.assertFalse(heist_sprout_fade_ready(intent, current))
        self.assertFalse(positive_candidate_matches_continuation(intent, current))
        decision = OneCommander().decide_entry((intent,), current, {})
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason, DENIAL)

    def test_recorded_trade4_cheap_mature_edge_label_is_not_parent_turn(self):
        current, intent = snapshot(7584), entry_intent(7584)
        self.assertEqual(current.no_ask, .20)
        self.assertTrue(current.metadata['mountain']['mature_edge'])
        self.assertFalse(current.metadata['mountain']['terminal_evidence_qualified'])
        self.assertFalse(heist_sprout_fade_ready(intent, current))
        self.assertFalse(positive_candidate_matches_continuation(intent, current))
        decision = OneCommander().decide_entry((intent,), current, {})
        self.assertIs(decision.action, Action.WAIT)
        self.assertEqual(decision.reason, DENIAL)

    def test_already_calibrated_recorded_proposals_do_not_bypass_rack_briefing(self):
        # Inject only the *actual recorded calibrated proposal* at the adviser
        # boundary. This explicitly bounded observer control does not fabricate
        # earlier calibration or claim a new complete rack/inventory history.
        for seq in (7304,7584):
            with self.subTest(sequence=seq):
                rack, current, intent = ToolRackController(), snapshot(seq), entry_intent(seq)
                with patch.object(rack, 'filter_independent_lane_candidates', return_value=(intent,)):
                    result = rack.observe(physical(seq), current)
                self.assertNotIn(intent, result.commander_intents)
                self.assertFalse(any(row.get('opportunity_id') == intent.opportunity_id
                    for row in result.briefings))

    def test_mirrored_recorded_fresh_down_sprouts_do_not_accept_yes_fades(self):
        for seq in (7304,7584):
            with self.subTest(sequence=seq):
                current, intent = mirrored(snapshot(seq), entry_intent(seq))
                self.assertIs(intent.side, Side.YES)
                self.assertFalse(heist_sprout_fade_ready(intent, current))
                decision = OneCommander().decide_entry((intent,), current, {})
                self.assertIs(decision.action, Action.WAIT)
                self.assertEqual(decision.reason, DENIAL)

    def test_single_retreat_flag_cannot_override_opening_cadence_or_stale_wall_visit(self):
        for field in ('meaningful_retreat','failed_reextension'):
            for seq in (7304,7584):
                with self.subTest(sequence=seq, evidence=field):
                    current, intent = snapshot(seq), entry_intent(seq)
                    md = deepcopy(current.metadata)
                    md['mountain'][field] = True
                    current = replace(current, metadata=md)
                    self.assertTrue(heist_sprout_fade_ready(intent, current))
                    # This old unit toggle only releases the sprout-specific
                    # restraint. At7304 the24s opening is unearned; at7584
                    # the recorded intent points to an older upper-wall visit.
                    decision=OneCommander().decide_entry((intent,), current, {})
                    self.assertIs(decision.action,Action.WAIT)
                    expected=('OPPORTUNITY_FIRST_MINUTE_WAIT_EARNED_EXCEPTION_REQUIRED' if seq==7304
                        else 'OPPORTUNITY_CURRENT_PHYSICAL_HEIST_VISIT_REQUIRED')
                    self.assertEqual(decision.reason,expected)
                    if seq==7584:
                        self.assertNotEqual(intent.metadata['visit_id'],current.metadata['heist']['visit_id'])

    def test_joint_turn_releases_sprout_restraint_but_still_needs_positive_species(self):
        for horizon in ('30','60'):
            current, intent = snapshot(7304), entry_intent(7304)
            md = deepcopy(current.metadata)
            md['mountain']['current_motion'][horizon].update(
                owner_price_rate_btc_s=-.25, owner_ema9_rate_btc_s=-.05)
            current = replace(current, metadata=md)
            self.assertTrue(heist_sprout_fade_ready(intent, current))
            decision=OneCommander().decide_entry((intent,), current, {})
            self.assertIs(decision.action,Action.WAIT)
            self.assertEqual(decision.reason,'OPPORTUNITY_FIRST_MINUTE_WAIT_EARNED_EXCEPTION_REQUIRED')

    def test_price_only_wick_does_not_override_still_outward_ema9(self):
        current, intent = snapshot(7304), entry_intent(7304)
        md = deepcopy(current.metadata)
        md['mountain']['current_motion']['30']['owner_price_rate_btc_s'] = -.25
        current = replace(current, metadata=md)
        self.assertFalse(heist_sprout_fade_ready(intent, current))
        self.assertEqual(OneCommander().decide_entry((intent,), current, {}).reason, DENIAL)

    def test_old_turn_subrow_cannot_nullify_current_outward_sprout(self):
        for horizon in ('30','60'):
            current, intent = snapshot(7304), entry_intent(7304)
            md = deepcopy(current.metadata)
            row = md['mountain']['current_motion'][horizon]
            row.update(owner_price_rate_btc_s=-.25, owner_ema9_rate_btc_s=-.05,
                source_ms=row['source_ms']-1000.)
            current = replace(current, metadata=md)
            self.assertFalse(heist_sprout_fade_ready(intent, current))
            self.assertEqual(OneCommander().decide_entry((intent,), current, {}).reason, DENIAL)

    def test_primary_family_relabel_cannot_bypass_same_heist_quality_boundary(self):
        for family in ('MOUNTAIN_EDGE','MOUNTAIN_CONTRACT_LEG','EDGE_HEIST','QUOTE_WAVE_SCALP'):
            current, intent = snapshot(7304), entry_intent(7304)
            intent = replace(intent, metadata={**intent.metadata,
                'commander_primary_candidate':True, 'commander_candidate_family':family,
                'position_role':'PRIMARY'})
            self.assertEqual(OneCommander().decide_entry((intent,), current, {}).reason, DENIAL)

    def test_micro_stall_and_terminal_label_alone_do_not_fade_outward_sprout(self):
        current, intent = snapshot(7304), entry_intent(7304)
        md = deepcopy(current.metadata)
        md['mountain'].update(stall=True, hesitation=True, mature_edge=True,
            terminal_evidence_qualified=True, edge_window_active=True)
        current = replace(current, metadata=md)
        self.assertFalse(heist_sprout_fade_ready(intent, current))
        self.assertEqual(OneCommander().decide_entry((intent,), current, {}).reason, DENIAL)

    def test_confirmed_corrective_transfer_retains_existing_authority(self):
        current, intent = snapshot(7304), entry_intent(7304)
        md = deepcopy(current.metadata)
        md.update(release_confirmed_current=True, release_candidate_side='NO')
        self.assertTrue(heist_sprout_fade_ready(intent, replace(current, metadata=md)))

    def test_same_side_heist_is_outside_counter_sprout_boundary(self):
        current, intent = snapshot(7304), entry_intent(7304)
        same = replace(intent, side=Side.YES)
        self.assertTrue(heist_sprout_fade_ready(same, current))
        # This eligibility predicate never raises a price cap or books a lot.
        self.assertGreater(current.yes_ask, same.max_price)

    def test_release_before_ema_spine_cross_keeps_its_independent_admission(self):
        current, intent = snapshot(4771), entry_intent(4771)
        self.assertIs(intent.side, Side.YES)
        self.assertEqual(current.metadata['ema9_ema30_cross_context']['gap_lifecycle']['current_side'], 'NO')
        self.assertIsNone(current.metadata['ema9_ema30_cross_context']['gap_lifecycle']['age_seconds_since_observed_cross'])
        self.assertTrue(heist_sprout_fade_ready(intent, current))
        self.assertIs(OneCommander().decide_entry((intent,), current, {}).action, Action.RELAY)

    def test_other_gap_stages_do_not_acquire_a_new_global_heist_pause(self):
        for stage in ('DEVELOPING','MATURE','ROLLING','INHERITED_OR_UNOBSERVED_CROSS','TOUCHING_SPINE'):
            with self.subTest(stage=stage):
                current, intent = snapshot(7304), entry_intent(7304)
                md = deepcopy(current.metadata)
                md['ema9_ema30_cross_context']['gap_lifecycle']['stage'] = stage
                self.assertTrue(heist_sprout_fade_ready(intent, replace(current, metadata=md)))

    def test_unwitnessed_gap_label_alone_has_no_new_sprout_authority(self):
        for field in ('latest_cross_observed_continuously','continued_on_latest_cross_side'):
            current, intent = snapshot(7304), entry_intent(7304)
            md = deepcopy(current.metadata)
            md['ema9_ema30_cross_context']['gap_lifecycle'][field] = False
            self.assertTrue(heist_sprout_fade_ready(intent, replace(current, metadata=md)))

    def test_stale_or_mismatched_source_does_not_become_a_new_parent_proof(self):
        for group in ('mountain','ema9_ema30_cross_context'):
            current, intent = snapshot(7304), entry_intent(7304)
            md = deepcopy(current.metadata)
            md[group]['source_ms'] -= 1000.
            self.assertTrue(heist_sprout_fade_ready(intent, replace(current, metadata=md)))
        current, intent = snapshot(7304), entry_intent(7304)
        self.assertTrue(heist_sprout_fade_ready(intent, replace(current, now_ts=current.now_ts+10.)))

    def test_unknown_motion_and_clock_only_label_do_not_create_protection(self):
        current, intent = snapshot(7304), entry_intent(7304)
        md = deepcopy(current.metadata)
        for horizon in ('30','60'):
            md['mountain']['current_motion'][horizon]['covered'] = False
        self.assertTrue(heist_sprout_fade_ready(intent, replace(current, metadata=md)))

    def test_existing_price_caps_sizes_and_window_remain_unchanged(self):
        self.assertEqual(MOUNTAIN_ROLLOVER_CONTINUATION_MAX, .55)
        self.assertEqual(MOUNTAIN_ROLLOVER_CONTINUATION_WINDOW_S, 60.)
        self.assertEqual(ReleaseConfig().soft_max_price, .20)
        self.assertEqual(ReleaseConfig().structural_size, 25.)
        self.assertEqual(HeistConfig().wide_normal_max_price, .30)
        self.assertEqual(HeistConfig().wide_exceptional_max_price, .35)
        self.assertEqual(HeistConfig().regular_size, 10.)


class PID10656OpeningEvidenceTests(unittest.TestCase):
    def test_observed_cross_is_at_source_rollover_and_book_is_not_yet_tradeable(self):
        before, crossed = snapshot(7257), snapshot(7258)
        self.assertEqual(before.metadata['ema9_ema30_cross_context']['current_side'], 'NO')
        cross = crossed.metadata['ema9_ema30_cross_context']
        self.assertEqual(cross['current_side'], 'YES')
        self.assertEqual(cross['source_ms'], 1793895300483.87)
        self.assertEqual(cross['gap_lifecycle']['age_seconds_since_observed_cross'], 0.)
        self.assertIsNone(crossed.yes_ask)
        self.assertIsNone(crossed.no_ask)

    def test_first_minute_actual_yes_quotes_have_forty_six_to_sixty_nine_cent_range(self):
        observations = [(seq,snapshot(seq)) for seq in opening_sequences()]
        quoted = [(seq,s) for seq,s in observations if s.yes_ask is not None]
        self.assertEqual(len(quoted), 66)
        self.assertEqual(quoted[0][0], 7294)
        self.assertAlmostEqual(quoted[0][1].contract_age_s, 18.688641786575317)
        self.assertEqual(quoted[0][1].yes_ask, .65)
        self.assertEqual(min(s.yes_ask for _,s in quoted), .46)
        self.assertEqual(max(s.yes_ask for _,s in quoted), .69)

    def test_first_minute_affordable_prices_do_not_already_have_causal_rejoin(self):
        for seq in opening_sequences():
            current = snapshot(seq)
            if current.yes_ask is None or current.yes_ask > .55:
                continue
            with self.subTest(sequence=seq):
                geometry = current.metadata['current_geometry']
                self.assertLess(geometry['btc_change6'], 0.)
                self.assertLess(geometry['ema9_change6'], 0.)
                self.assertFalse(any(intent.side is Side.YES
                    for intent in OneCommander().physical_entry_candidates(current)))

    def test_minimum_quote_during_first_minute_has_unresolved_target_ownership(self):
        current = snapshot(7355)
        self.assertEqual(current.yes_ask, .46)
        self.assertEqual(current.metadata['mission_context']['parent']['side'], 'YES')
        self.assertEqual(current.metadata['mountain']['owner_side'], 'NO')
        self.assertEqual(current.metadata['tp_geometry']['contract_ownership'], 'UNRESOLVED')
        self.assertIsNone(current.metadata['tp_geometry']['contract_ownership_side'])

    def test_rejoin_then_target_agreement_arrive_after_premium_first_minute(self):
        rejoin = snapshot(7366)
        self.assertEqual(rejoin.yes_ask, .47)
        self.assertGreater(rejoin.contract_age_s, 60.)
        self.assertGreater(rejoin.metadata['current_geometry']['btc_change6'], 0.)
        self.assertGreater(rejoin.metadata['current_geometry']['ema9_change6'], 0.)
        self.assertIsNone(rejoin.metadata['tp_geometry']['contract_ownership_side'])
        agreed = snapshot(7379)
        self.assertEqual(agreed.yes_ask, .55)
        self.assertGreater(agreed.contract_age_s, 60.)
        self.assertEqual(agreed.metadata['tp_geometry']['contract_ownership_side'], 'YES')
        self.assertFalse(any(i.side is Side.YES for i in OneCommander().physical_entry_candidates(agreed)))

    def test_opening_audit_retains_original_held_inventory_and_future_limits(self):
        later = record(7355)
        inventory = later['physical_metadata']['position_inventory']
        self.assertTrue(inventory)
        self.assertTrue(any(row['scope'] == 'POSITION' for row in later['decisions']))
        self.assertTrue(any('originally held NO position' in line for line in manifest()['limits']))
        self.assertTrue(any('not a modified whole-session' in line for line in manifest()['limits']))


if __name__ == '__main__':
    unittest.main()
