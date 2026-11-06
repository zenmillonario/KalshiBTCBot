"""Offline acceptance gate for the standalone Tool Rack PAPER bundle.

This command never starts a feed, reads credentials, or installs dependencies.
The allowlists are also the authoritative package boundary for the builder.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import ast
import hashlib
import importlib
import importlib.metadata
import importlib.util
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


MANIFEST_NAME = "TOOL_RACK_PAPER_BUNDLE_MANIFEST.json"
MANIFEST_SCHEMA = "TACHYOS_TOOL_RACK_PAPER_BUNDLE_V1"
RELEASE_ID = "TACHYOS_OPPORTUNITY_FIRST_COMMANDER_45M_PAPER_20261106"
CAPTURE_CANDIDATE_REVISION = "TACHYOS_ENGINE_CAPTURE_NEXT_RUN_20261104"
BASELINE_PACKAGE_SHA256 = "0f87e79842e6ec29b8a9b6b5b73fd608de3c3b27b75074bb178ce8c39ccc09f2"
BASELINE_SOURCE_MANIFEST_SHA256 = "31dda05acafc94cd6cf859ef94a33ea5f03539723e82ce6d31bbf3a436b88f4b"
PID17224_PACKAGE_SHA256 = "1017bb355dc1ac9fd90181ecd031c836ae72568df8cf1f4e4673645e85ad1484"
PID19996_PACKAGE_SHA256 = "08134e26ce2a6066ded3ce7cc978583cf756265d1db5dac6c83eb7b786e490ed"
PID4596_PACKAGE_SHA256 = "3d18b5a70fb1e189a8223116f25f477f27de8787f45450aa810d6ffcf8caaac0"
PID17588_PACKAGE_SHA256 = "02a48450d412b96d70b474a910c5f28457f82b0bdabaff03252d67d995bfac98"
PID15184_PACKAGE_SHA256 = "82bc70e6a8362fc4b291cdf5c0a0a9c9fa1e1eb5769a0238708b18dc283c1ca4"
PREVIOUS_PACKAGE_SHA256 = "180a120d4096b7489fdc648cc34d55c505f98af63df68ec11d322d6320a7aff6"
PID4824_SOURCE_MANIFEST_SHA256 = "7adbce1236dcde4f13174c2dc1fa3d7f0edb67abad4b51b256c061a08382f873"
PID4824_APPROVAL_SHA256 = "f9b19119e2c4811f643359c0795ae3ebf6f7f509fb9e18f199e2126e05dadf2b"
PID3904_SOURCE_MANIFEST_SHA256 = "c501c3b489ad5c3145e376099715d450d49b6005bdcd5f17eb19d2eddf03542a"
PID3904_APPROVAL_SHA256 = "24821d2496ae15b4a1ddccb8254dffb13ce28164ebe11895925b1ab07d234c9b"
PID15184_SOURCE_MANIFEST_SHA256 = "4c72bb714412ab05911f0560ab880c2ba6b4f7f506a8bb4eb66d13f39127a47d"
PID15184_APPROVAL_SHA256 = "40df7abdfe24fea47f45f027c18f3f2583ddac6e35be0f8e01ef6eb6f08fb788"
PID17588_SOURCE_MANIFEST_SHA256 = "36495faeeccf77b891fbabbbc1f0309ae260c0462fb64f119daee11409edd345"
PID17588_APPROVAL_SHA256 = "2f324c1a6a22d984eaafc5f46179cc62aa47edb491efca113d6f70e481a23279"
PID4596_SOURCE_MANIFEST_SHA256 = "64271ca0ac5d937e1803e948efd2af769e61e5c1f2cec8546f12daeec56ad230"
PID4596_APPROVAL_SHA256 = "5bbe44af265945b7f6ce435956aad68080decc07894d6a618ad2a0a71390cfca"
PID19996_SOURCE_MANIFEST_SHA256 = "1dceda9ce2bdbb5993522cb5da558742d701084d12c2c143d0d15463394722d6"
PID19996_APPROVAL_SHA256 = "ba696821fc7ee23e0da299f7454541c07bd218244da4edfb9ed2104fca04f0fe"
PREVIOUS_SOURCE_MANIFEST_SHA256 = "cf5b43a901d1c6fd0f3a2b31acfca97e6d87e3fe11f97885c34c47fbc5185fe1"
PREVIOUS_APPROVAL_SHA256 = "bba50102f987a5ad5555a3eb570a80e1c486abafe2df6393f73ca03a4753127c"
APPROVED_CORRECTIONS = ["A", "B", "C", "PID19996_RAIL_VALUE", "PID19996_SOURCE_FRESHNESS",
                        "PID19996_RESEARCH_IDENTITY", "PID19996_COMPLETE_UPLOADS", "PID4596_NULL_EXIT_ESTIMATE",
                        "PID17588_SCOUT_LATE_TP", "PID15184_CURRENT_PARENT_CALIBRATION",
                        "PID4824_RECOVERY_IDENTITY", "PID4824_FLOOR_AUTHORITY",
                        "PID10656_FRESH_SPROUT_HEIST_QUALITY", "PID10656_LOOKING_GLASS_PATTERNS",
                        "PID21672_CONFIRMED_LIVE_PARENT_TRANSFER",
                        "PID18244_CURRENT_PARENT_PROMOTION", "PID18244_COUNTERPARENT_TACTICAL_FLOOR",
                        "PID18244_LOSSLESS_SMALL_UPLOADS",
                        "PID19616_LEVEL_MATCH_PRECISION", "PID19616_HEIST_STALLED_EDGE_PARENT_MOMENTUM",
                        "PID19616_MATURE_PREMIUM_OPENING_PACE",
                        "PID14156_EARNED_SAME_GAP_HEIST_LOWER_RETURN", "PID14156_TRUE_PARENT_SCALE_FAST_MOUNTAIN_EDGE",
                        "PID10760_CAUSAL_PREOPEN_YOUNG_EMA9_CONTINUATION",
                        "PID23160_WIDE_HEIST_REPEATABLE_PHYSICAL_OWNERSHIP", "PID23160_EARNED_CURRENT_EMA9_PARENT_VALUE_REJOIN", "PID23160_COUNTERPARENT_LEVEL_SUSTAINED_REJECTION",
                        "PID3860_MATURE_ROLLOVER_PRICE_RETREAT_NO_CHASE", "PID3860_FEE_POSITIVE_MATURE_STALL_COLLECTION",
                        "PID14048_EARNED_EDGE_BOUNDED_QUOTE_VALUE_WINDOW", "PID14048_NEAR_PEAK_MATURE_STALL_NET_COLLECTION",
                        "PID3904_OPPORTUNITY_FIRST_COMMANDER", "PID3904_OPPORTUNITY_REVIEW_PROVENANCE"]
HISTORICAL_APPROVED_FILES = frozenset({
    "strategy_core/commander.py", "strategy_core/commander_candidates.py",
})
PID19996_CHANGED_CORE_FILES = frozenset({
    "strategy_core/commander.py", "strategy_core/commander_candidates.py",
    "strategy_core/custody_evidence.py", "strategy_core/leg_ledger.py",
    "strategy_core/mission_policy.py", "strategy_core/paper_runtime.py",
    "strategy_core/position_roles.py", "strategy_core/recovery.py",
    "strategy_core/tool_rack.py", "strategy_core/tools/management.py",
    "strategy_core/tools/mountain.py", "strategy_core/tools/heist.py",
})
PID19996_ADDED_CORE_FILES = frozenset({"strategy_core/source_freshness.py"})
PID4596_CHANGED_CORE_FILES = frozenset({"strategy_core/mission_policy.py", "strategy_core/paper_runtime.py"})
PID17588_CHANGED_CORE_FILES = frozenset({"strategy_core/commander_candidates.py", "strategy_core/paper_runtime.py"})
PID15184_CHANGED_CORE_FILES = frozenset({"strategy_core/dual_lane.py", "strategy_core/tool_rack.py", "strategy_core/paper_runtime.py"})
PID4824_CHANGED_CORE_FILES = frozenset({"strategy_core/tool_rack.py", "strategy_core/paper_runtime.py"})
PID14048_CHANGED_CORE_FILES = frozenset({
    "strategy_core/commander.py", "strategy_core/commander_candidates.py", "strategy_core/custody_evidence.py", "strategy_core/tool_rack.py",
    "strategy_core/detectors/heist_geometry.py", "strategy_core/paper_runtime.py", "strategy_core/looking_glass.py", "strategy_core/nautilus_projection.py",
    "strategy_core/nautilus/chart.js", "strategy_core/nautilus/app.js", "strategy_core/nautilus/index.html",
    "strategy_core/nautilus/bridge.css", "strategy_core/nautilus/PROVENANCE.json",
})
APPROVED_CHANGED_CORE_FILES = frozenset({
    "strategy_core/commander.py",
    "strategy_core/paper_runtime.py", "strategy_core/custody_evidence.py",
})
APPROVED_ADDED_CORE_FILES = frozenset({"strategy_core/opportunity_first.py"})

CORE_FILES = (
    "strategy_core/__init__.py",
    "strategy_core/types.py",
    "strategy_core/compatibility.py",
    "strategy_core/config_loader.py",
    "strategy_core/lane_resolver.py",
    "strategy_core/router.py",
    "strategy_core/tool_rack.py",
    "strategy_core/directional_parent.py",
    "strategy_core/dual_lane.py",
    "strategy_core/navigator_briefing.py",
    "strategy_core/commander.py",
    "strategy_core/commander_candidates.py",
    "strategy_core/opportunity_first.py",
    "strategy_core/tp_geometry.py",
    "strategy_core/leg_ledger.py",
    "strategy_core/fade_evidence.py",
    "strategy_core/custody_evidence.py",
    "strategy_core/counter_observers.py",
    "strategy_core/physical_source.py",
    "strategy_core/paper_feed.py",
    "strategy_core/paper_execution.py",
    "strategy_core/paper_runtime.py",
    "strategy_core/paper_dashboard.py",
    "strategy_core/nautilus_projection.py",
    "strategy_core/looking_glass.py",
    "strategy_core/mission_context.py",
    "strategy_core/parent_references.py",
    "strategy_core/mission_scopes.py",
    "strategy_core/leg_weakness.py",
    "strategy_core/mission_policy.py",
    "strategy_core/source_freshness.py",
    "strategy_core/recovery.py",
    "strategy_core/position_roles.py",
    "strategy_core/tools/__init__.py",
    "strategy_core/tools/base.py",
    "strategy_core/tools/management.py",
    "strategy_core/tools/mountain.py",
    "strategy_core/tools/heist.py",
    "strategy_core/tools/rail.py",
    "strategy_core/tools/release.py",
    "strategy_core/detectors/__init__.py",
    "strategy_core/detectors/mountain_geometry.py",
    "strategy_core/detectors/heist_geometry.py",
    "strategy_core/detectors/rail_geometry.py",
    "strategy_core/detectors/release_geometry.py",
    "strategy_core/marketdata/__init__.py",
    "strategy_core/marketdata/common.py",
    "strategy_core/marketdata/btc_observation.py",
    "strategy_core/marketdata/btc_transport.py",
    "strategy_core/marketdata/native_book.py",
    "strategy_core/marketdata/native_receiver.py",
    "strategy_core/marketdata/kalshi_public.py",
)

ASSET_FILES = (
    "tests/tool_rack/fixtures/pid17588_pre_opportunity_behavior_test.py.txt",
    "tests/tool_rack/fixtures/pid18244_opportunity_source_sequence.json.gz",
    "tests/tool_rack/fixtures/pid3904_parent_custody.json.gz",
    "tests/tool_rack/fixtures/pid3904_opportunity_sequences.json.gz",
    "tests/tool_rack/fixtures/pid14048_full_sequence.json.gz",
    "tests/tool_rack/fixtures/pid3860_compact_decisions.json.gz",
    "tests/tool_rack/fixtures/pid23160_heist_parent_selected.json.gz",
    "tests/tool_rack/fixtures/pid14156_selected_source_decisions.json.gz",
    "tests/tool_rack/fixtures/pid10760_preopen_rollover_source_frames.json.gz",
    "tests/tool_rack/fixtures/pid19616_selected_source_decisions.json.gz",
    "tests/tool_rack/fixtures/pid18244_selected_physical_frames.json",
    "tests/tool_rack/fixtures/pid10656_looking_glass_contexts.json",
    "tests/tool_rack/fixtures/pid10656_sprout_cases.jsonl.gz",
    "tests/tool_rack/fixtures/pid10656_sprout_manifest.json",
    "tests/tool_rack/fixtures/pid4824_recovery_journal.jsonl.gz",
    "tests/tool_rack/fixtures/pid4824_recovery_parent_prefix.jsonl.gz",
    "tests/tool_rack/fixtures/pid4824_recovery_cases.jsonl.gz",
    "tests/tool_rack/fixtures/pid4824_recovery_manifest.json",
    "tests/tool_rack/fixtures/pid4824_floor_cases.jsonl.gz",
    "tests/tool_rack/fixtures/pid4824_floor_manifest.json",
    "tests/tool_rack/fixtures/pid15184_prior_pid17588_calibration_prefix.jsonl.gz",
    "tests/tool_rack/fixtures/pid15184_current_parent_cases.jsonl.gz",
    "tests/tool_rack/fixtures/pid15184_current_parent_chronology.jsonl.gz",
    "tests/tool_rack/fixtures/pid15184_current_parent_manifest.json",
    "tests/tool_rack/fixtures/pid17588_late_scout_cases.jsonl.gz",
    "tests/tool_rack/fixtures/pid17588_late_scout_histories.jsonl.gz",
    "tests/tool_rack/fixtures/pid17588_late_scout_manifest.json",
    "tests/tool_rack/fixtures/pid4596_optional_economics_cases.json.gz",
    "tests/tool_rack/fixtures/pid4596_optional_economics_manifest.json",
    "tests/tool_rack/fixtures/pid19996_rail_fishing_cases.jsonl.xz",
    "tests/tool_rack/fixtures/pid19996_rail_fishing_manifest.json",
    "tests/tool_rack/fixtures/pid19996_source_freshness_cases.json.gz",
    "tests/tool_rack/fixtures/pid19996_leg_accounting.json.gz",
    "tests/tool_rack/fixtures/pid17224_recorded_cases.json.gz",
    "strategy_core/config/physical.json",
    "strategy_core/config/mountain.json",
    "strategy_core/config/heist.json",
    "strategy_core/config/rail.json",
    "strategy_core/config/release.json",
    "strategy_core/config/looking_glass.json",
    "strategy_core/config/mission.json",
    "strategy_core/marketdata/VENDOR_PROVENANCE.json",
    "strategy_core/nautilus/index.html",
    "strategy_core/nautilus/style.css",
    "strategy_core/nautilus/bridge.css",
    "strategy_core/nautilus/chart.js",
    "strategy_core/nautilus/reliability-ui.js",
    "strategy_core/nautilus/app.js",
    "strategy_core/nautilus/bridge.js",
    "strategy_core/nautilus/PROVENANCE.json",
    "tests/tool_rack/fixtures/pid16280_mountain_geometry.json",
    "tests/tool_rack/fixtures/pid16280_release_custody.json",
    "tests/tool_rack/fixtures/pid13432_routing_frames.json",
    "tests/tool_rack/fixtures/pid13432_runtime_seq11090.json",
    "tests/tool_rack/fixtures/pid13432_mountain_geometry.json",
    "tests/tool_rack/fixtures/pid7516_physical_geometry.json",
    "tests/tool_rack/fixtures/pid7516_profit_taking.json",
    "tests/tool_rack/fixtures/pid7516_role_admission.json",
    "tests/tool_rack/fixtures/pid7516_entry_admission.json",
    "tests/tool_rack/fixtures/pid10092_missions.json",
    "tests/tool_rack/fixtures/pid12448_tactical_observations.json.gz",
    "tests/tool_rack/fixtures/pid12448_arc_contract_held.json.gz",
    "tests/tool_rack/fixtures/pid12448_main_location_19337.json",
    "tests/tool_rack/fixtures/pid5452_physical_geometry.jsonl.gz",
    "tests/tool_rack/fixtures/pid22736_geometry.jsonl",
    "tests/tool_rack/fixtures/pid8868_mountain_gate.json",
    "tests/tool_rack/fixtures/pid23072_entry_controls.json",
    "tests/tool_rack/fixtures/pid23072_physical_geometry.jsonl.gz",
    "tests/tool_rack/fixtures/pid3216_160950_ultra_geometry.jsonl.gz",
    "docs/pid13432_forensic_summary.json",
    "docs/PID13560_POSITIVE_CONTROL_CORPUS.json",
    "docs/PID7812_SPROUT_PROMOTION_CONTROLS.json",
    "docs/PID14312_ARC_SELECTION_CUSTODY_CONTROLS.json",
    "docs/PID7412_TRADE_CONTROLS.json",
    "docs/PID7412_DIRECTIONAL_TRANSFER_SAMPLES.json",
    "docs/PID8552_RAIL_WICK_ENTRY_TIME_CONTROLS.json",
    "docs/PID17744_RETURN_BRIEFING_CONTROLS.json",
    "docs/PID17744_2130_NAVIGATOR_CHECKPOINTS.json",
    "docs/PID15740_ENTRY_TIME_CONTROLS.json",
)

SUPPORT_FILES = (
    "PID3904_SOURCE_SHA256.json", "PID3904_APPROVAL.json",
    "PID3904_FORENSICS.md", "OPPORTUNITY_FIRST_IMPLEMENTATION.md",
    "PID3904_TRADE_AUDIT.json", "PID3904_CASE_ANNOTATIONS.json",
    "TACHYOS_PROPOSED_OPPORTUNITY_FIRST_COMMANDER_2026-11-06.md",
    "OPPORTUNITY_FIRST_VALIDATION.json", "OPPORTUNITY_FIRST_SEQUENCE_AUDIT.json",
    "OPPORTUNITY_FIRST_SEQUENCE_FRAMES.jsonl.gz", "OPPORTUNITY_FIRST_ENGINE_CONSTRUCT.json",
    "AUDIT_OPPORTUNITY_FIRST_SEQUENCE.py", "CONSTRUCT_OPPORTUNITY_FIRST_ENGINE_SEQUENCE.py",
    "PID3860_VALIDATION.json", "PID3860_BACKBONE_REPAIR_SCOPE_2026-11-06.md",
    "PID23160_VALIDATION.json", "PID23160_FULL_RUN_FORENSICS_2026-11-06.md",
    "PID23160_SOURCE_BOUND_CHRONOLOGY_2026-11-06.json", "PID23160_CHRONOLOGICAL_CONSTRUCT_RESULT_2026-11-06.json",
    "PID23160_NEW_MAIN_PARENT_CANDIDATE_SCAN_2026-11-06.json", "PID23160_PATIENT_HEIST_BUILD_NOTES_2026-11-06.md",
    "PID10760_VALIDATION.json", "PID10760_PRECONTRACT_UP_AND_THREE_TRADES_FORENSICS.md",
    "PID10760_SOURCE_BOUND_FORENSIC_EVIDENCE.json", "PID10760_BUILD_NOTES_2026-11-05.md",
    "PID14156_VALIDATION.json", "PID14156_FULL_RUN_FORENSICS_2026-11-05.md",
    "PID14156_SOURCE_BOUND_EVIDENCE_2026-11-05.json", "PID14156_BUILD_NOTES_2026-11-05.md",
    "PID19616_VALIDATION.json", "PID19616_FULL_RUN_FORENSICS_2026-11-05.md",
    "PID19616_SOURCE_BOUND_EVIDENCE_2026-11-05.json",
    "PID19616_BUILD_NOTES_2026-11-05.md",
    "PID18244_VALIDATION.json", "PID18244_FULL_RUN_FORENSICS_2026-11-05.md",
    "PID18244_FORENSIC_EVIDENCE_2026-11-05.json",
    "PID4824_SOURCE_SHA256.json", "PID4824_APPROVAL.json",
    "PID10656_BUILD_NOTES.txt", "PID10656_VALIDATION.json",
    "PID10656_RUN_REVIEW.txt", "PID10656_RUN_REVIEW.pdf", "PID10656_REVIEW_EVIDENCE.zip",
    "CONSTRUCT_PID10656_SPROUT_HEIST.py", "RUN_PID10656_LOOKING_GLASS_CONSTRUCT.py",
    "PID21672_FORENSIC_REVIEW.md", "PID21672_VALIDATION.json", "PROJECT_CHECKPOINT_NEXT_VISIT.md",
    "tests/tool_rack/pid10656_sprout_fixtures.py",
    "tests/tool_rack/fixtures/pid21672_live_parent_cases.json.gz",
    "tests/tool_rack/test_nautilus_pattern_paths.js",
    "PID15184_SOURCE_SHA256.json",
    "PID15184_APPROVAL.json",
    "PID4824_BUILD_NOTES.txt",
    "PID4824_VALIDATION.json",
    "PID4824_RUN_REVIEW.txt",
    "PID4824_RUN_REVIEW.pdf",
    "PID4824_REVIEW_EVIDENCE.zip",
    "CONSTRUCT_PID4824_RECOVERY_IDENTITY.py",
    "CONSTRUCT_PID4824_FLOOR_AUTHORITY.py",
    "tests/tool_rack/pid4824_recovery_fixtures.py",
    "tests/tool_rack/pid4824_floor_fixtures.py",
    "PID17588_SOURCE_SHA256.json",
    "PID17588_APPROVAL.json",
    "PID15184_BUILD_NOTES.txt",
    "PID15184_VALIDATION.json",
    "PID15184_RUN_REVIEW.txt",
    "PID15184_RUN_REVIEW.pdf",
    "PID15184_REVIEW_EVIDENCE.zip",
    "CONSTRUCT_PID15184_CURRENT_PARENT_CALIBRATION.py",
    "tests/tool_rack/pid15184_current_parent_fixtures.py",
    "PID4596_SOURCE_SHA256.json",
    "PID4596_APPROVAL.json",
    "PID17588_BUILD_NOTES.txt",
    "PID17588_VALIDATION.json",
    "PID17588_RUN_REVIEW.txt",
    "PID17588_RUN_REVIEW.pdf",
    "PID17588_REVIEW_EVIDENCE.zip",
    "CONSTRUCT_PID17588_LATE_SCOUT.py",
    "PID19996_SOURCE_SHA256.json",
    "PID19996_APPROVAL.json",
    "PID4596_BUILD_NOTES.txt",
    "PID4596_VALIDATION.json",
    "PID4596_RUN_REVIEW.txt",
    "PID4596_CAPTURE_AUDIT.json",
    "PID4596_OPPORTUNITY_AUDIT.json",
    "PID4596_LEG_LEDGER_AUDIT.json",
    "PID4596_OPPORTUNITY_REVIEW.md",
    "CONSTRUCT_PID4596_RUNTIME_REPAIR.py",
    "tests/tool_rack/pid17588_late_scout_fixtures.py",
    "tests/tool_rack/pid4596_runtime_fixtures.py",
    "PREVIOUS_RELEASE_SOURCE_SHA256.json",
    "PREVIOUS_RELEASE_APPROVAL.json",
    "PID19996_BUILD_NOTES.txt",
    "PID19996_VALIDATION.json",
    "CONSTRUCT_PID19996_RAIL_VALUE.py",
    "tests/tool_rack/pid19996_rail_fixtures.py",
    "make_upload_parts.py",
    "post_run_monitor.py",
    "test_upload_parts.py",
    "test_post_run_workflow.py",
    "APPROVED_STRATEGY_CHANGES.json",
    "BASELINE_SOURCE_SHA256.json",
    "PID17224_BUILD_NOTES.txt",
    "PID17224_VALIDATION.json",
    "CONSTRUCT_PID14048_QUOTE_VALUE_STALL.py",
    "PID14048_ENTRY_VALUE_HOVER_BUILD_NOTES.md",
    "PID14048_VALIDATION.json",
    "CONSTRUCT_PID17224_APPROVED_CORRECTIONS.py",
    "tests/tool_rack/pid17224_recorded_fixtures.py",
    "complete_paper_run.py",
    "test_complete_paper_run.py",
    "07_REPLAY_CLOSED_PAPER_RUN.cmd",
    "TOOL_RACK_PAPER.py",
    "TOOL_RACK_EXPORT.py",
    "TOOL_RACK_RECONCILE.py",
    "CHECK_TOOL_RACK_PAPER.py",
    "BUILD_TOOL_RACK_PAPER_BUNDLE.py",
    "00_PREPARE_AND_RUN_45M_PAPER.cmd",
    "01_START_TOOL_RACK_PAPER_6H.cmd",
    "01B_START_TOOL_RACK_PAPER_90M.cmd",
    "02_CHECK_TOOL_RACK_PAPER.cmd",
    "03_INSTALL_TOOL_RACK_DEPENDENCIES.cmd",
    "04_EXPORT_LAST_TOOL_RACK_RUN.cmd",
    "05_RECONCILE_PREVIOUS_TOOL_RACK_RUN.cmd",
    "06_EXPORT_LAST_RUN_COMPACT_FORENSICS.cmd",
    "09_EXPORT_DIRECT_ULTRA_FORENSICS.cmd",
    "requirements_tool_rack_paper.txt",
    "README_TOOL_RACK_PAPER.md",
    "TACHYOS_STRATEGY_BACKBONE_V1.md",
    "engine_replay.py",
    "input_codec.py",
    "bounded_tape.py",
    "snapshot_delta.py",
    "synthetic_session.py",
    "run_validation.py",
    "replay_capture.py",
    "test_capture_integrity.py",
    "test_snapshot_delta.py",
    "prepare_next_run.py",
    "test_next_run_capture.py",
    "capture_session.py",
    "finish_recorded_run.py",
    "test_capture_session.py",
    "SOURCE_SHA256.json",
    "NEXT_RUN_README.txt",
    "NEXT_RUN_STATUS.json",
    "docs/TACHYOS_TOOL_RACK_STRATEGY_CORE_V1.md",
    "docs/TOOL_RACK_PAPER_HANDOFF_2026-10-27.md",
    "docs/TOOL_RACK_PID16280_CORRECTIONS_HANDOFF_2026-10-27.md",
    "docs/TOOL_RACK_PID13432_FORENSIC_REPORT_2026-10-27.md",
    "docs/TOOL_RACK_PID13432_MOUNTAIN_REDO_HANDOFF_2026-10-27.md",
    "docs/TOOL_RACK_PID19832_FADE_PEAKLOCK_HANDOFF_2026-10-28.md",
    "docs/TOOL_RACK_PID19832_MAIN_FADE_GOVERNANCE_HANDOFF_2026-10-29.md",
    "docs/TOOL_RACK_COMMANDER_KERNEL_HANDOFF_2026-10-29.md",
    "docs/TOOL_RACK_MOUNTAIN_SPINE_NO_FADES_HANDOFF_2026-10-29.md",
    "docs/TOOL_RACK_MOUNTAIN_GAPLOCK_HANDOFF_2026-10-29.md",
    "docs/TOOL_RACK_PARENT_SCALE_RAIL_ROLLOVER_HANDOFF_2026-10-30.md",
    "docs/TOOL_RACK_PID16460_VALUE_EDGES_PARALLEL_RELEASE_HANDOFF_2026-10-30.md",
    "docs/TOOL_RACK_RUNNER_HARVEST_FAST_HANDOFF_HANDOFF_2026-10-30.md",
    "docs/TACHYOS_FULL_IMPLEMENTATION_AUDIT_2026-10-29.md",
    "docs/TOOL_RACK_RUN_OBSERVATIONS_2026-10-27.md",
    "docs/TOOL_RACK_PID7516_ENTRIES_RUNNERS_HANDOFF_2026-10-27.md",
    "docs/TOOL_RACK_LOOKING_GLASS_HANDOFF_2026-10-27.md",
    "docs/TOOL_RACK_PID10092_MISSIONS_HANDOFF_2026-10-28.md",
    "docs/pid10092_mission_replay_summary.json",
    "docs/TOOL_RACK_RESTART_FINALITY_FIX_2026-10-28.md",
    "docs/pid10092_restart_rehearsal.json",
    "docs/TOOL_RACK_PID12448_ADMISSION_AUDIT_2026-10-28.md",
    "docs/pid12448_admission_boundary_reproduction.json",
    "docs/TOOL_RACK_PID12448_RECORDED_FORENSICS_2026-10-28.md",
    "docs/pid12448_recorded_forensics.json",
    "docs/figures/pid12448_actual_peak_audit.png",
    "docs/TOOL_RACK_PID12448_PARENT_ARC_CORRECTION_2026-10-28.md",
    "docs/pid12448_parent_arc_correction.json",
    "docs/figures/pid12448_0230_final_replay.png",
    "docs/pid12448_recorded_acceptance.json",
    "docs/pid12448_recorded_hold_acceptance.json",
    "docs/pid12448_recorded_continuity_acceptance.json",
    "docs/pid12448_recorded_edge_acceptance.json",
    "docs/pid12448_recorded_maturity_contract_acceptance.json",
    "docs/pid12448_recorded_simple_zone_acceptance.json",
    "docs/pid12448_recorded_early_valley_acceptance.json",
    "docs/TOOL_RACK_SIMPLE_ZONES_REVIEW_2026-10-28.md",
    "docs/pid12448_simple_zones_review.json",
    "docs/figures/pid12448_simple_zone_replay.png",
    "docs/figures/pid12448_simple_zone_replay.json",
    "tests/tool_rack/mission_fixtures.py",
    "tests/tool_rack/fixtures/pid4756_release_flicker_controls.json",
    "tests/tool_rack/construct_arc_fixtures.py",
    "CONSTRUCT_TOOL_RACK_ARCS.py",
    "CONSTRUCT_TOOL_RACK_COMMANDER.py",
    "CONSTRUCT_MOUNTAIN_ONLY.py",
    "CONSTRUCT_EMA9_AUTHORITY.py",
    "CONSTRUCT_TOOL_ADVISORY_AUTHORITY.py",
    "CONSTRUCT_PID13560_POSITIVE_CONTROLS.py",
    "CONSTRUCT_PID7812_SPROUT_PROMOTION.py",
    "CONSTRUCT_PID14312_ARC_SELECTION_CUSTODY.py",
    "CONSTRUCT_PID7412_DIRECTIONAL_TRANSFER.py",
    "CONSTRUCT_PID8552_RAIL_WICK_CUSTODY.py",
    "CONSTRUCT_PID17744_RETURN_BRIEFINGS.py",
    "CONSTRUCT_DUAL_LANE_MAIN_TACTICAL.py",
    "CONSTRUCT_PID15740_INHERITED_UP_RAIL.py",
    "CONSTRUCT_TOOL_RACK_HOLDING.py",
    "tests/tool_rack/construct_holding_fixtures.py",
    "CONSTRUCT_TOOL_RACK_CONTRACT_INTERRUPTION.py",
    "tests/tool_rack/construct_contract_interruption_fixtures.py",
    "tests/tool_rack/test_nautilus_looking_glass.js",
    "tests/tool_rack/test_nautilus_browser.js",
    ".github/workflows/tool-rack-paper.yml",
)

# Deliberately explicit: discovery must not pull migration/shadow tests back in.
TEST_MODULES = (
    "tests.tool_rack.test_pid3904_parent_collection",
    "tests.tool_rack.test_opportunity_first_commander",
    "tests.tool_rack.test_opportunity_diagnostics",
    "tests.tool_rack.test_pid14048_quote_value_and_stall",
    "tests.tool_rack.test_pid3860_stall_harvest_rollover",
    "tests.tool_rack.test_pid23160_patient_heist_parent",
    "tests.tool_rack.test_pid10760_preopen_rollover",
    "tests.tool_rack.test_pid14156_heist_territory_transfer",
    "tests.tool_rack.test_pid19616_entry_quality",
    "tests.tool_rack.test_pid18244_parent_custody_protection",
    "tests.tool_rack.test_pid21672_confirmed_parent_transfer",
    "tests.tool_rack.test_pid10656_sprout_heist",
    "tests.tool_rack.test_looking_glass_patterns",
    "tests.tool_rack.test_pid4824_recovery_identity",
    "tests.tool_rack.test_pid4824_floor_authority",
    "tests.tool_rack.test_pid15184_current_parent_calibration",
    "tests.tool_rack.test_pid17588_late_scout",
    "tests.tool_rack.test_pid4596_optional_economics",
    "tests.tool_rack.test_pid19996_rail_fishing",
    "tests.tool_rack.test_pid19996_source_freshness",
    "tests.tool_rack.test_pid19996_leg_research",
    "tests.tool_rack.test_pid17224_release_heist",
    "tests.tool_rack.test_pid17224_main_returns",
    "tests.tool_rack.test_pid17224_package_identity",
    # Current Commander strategy and explicitly authorized specialist reactivation.
    "tests.tool_rack.test_mountain_only_reset",
    "tests.tool_rack.test_authorized_reactivation",
    "tests.tool_rack.test_authorized_heist_release_house",
    "tests.tool_rack.test_direct_paper_runtime",
    # Mountain geometry remains causal evidence.
    "tests.tool_rack.test_mountain_geometry_detector",
    "tests.tool_rack.test_pid3216_starvation_repair",
    "tests.tool_rack.test_pid2672_authorized_repairs",
    "tests.tool_rack.test_pid1172_authorized_repairs",
    "tests.tool_rack.test_wide_heist_rail_quote_wave",
    "tests.tool_rack.test_pid252_tactical_promotions",
    "tests.tool_rack.test_pid7812_sprout_promotion",
    "tests.tool_rack.test_pid14312_arc_selection_custody",
    "tests.tool_rack.test_pid7412_directional_transfer",
    "tests.tool_rack.test_pid8552_rail_wick_custody",
    "tests.tool_rack.test_pid17744_return_briefings",
    "tests.tool_rack.test_pid17744_navigator_rail_window",
    "tests.tool_rack.test_dual_lane_main_tactical",
    "tests.tool_rack.test_pid15740_inherited_up_rail",
    # Objective UI/evidence surfaces.
    "tests.tool_rack.test_nautilus_chart_source",
    "tests.tool_rack.test_nautilus_projection",
    "tests.tool_rack.test_looking_glass",
    "tests.tool_rack.test_looking_glass_projection",
    "tests.tool_rack.test_paper_dashboard",
    # Objective PAPER execution, feed, settlement and launch integrity.
    "tests.tool_rack.test_paper_execution",
    "tests.tool_rack.test_paper_feed",
    "tests.tool_rack.test_paper_settlement_recovery",
    "tests.tool_rack.test_paper_reconcile_launcher",
    "tests.tool_rack.test_paper_launcher_export",
    "tests.tool_rack.test_session_draining_launcher",
    "tests.tool_rack.test_recorded_session_launcher",
    "tests.tool_rack.test_windows_text_encoding_contract",
)

# Recorder integration has a finite extracted-package gate. The ordinary
# full CHECK remains available and keeps all of its existing strategy gates.
CAPTURE_TEST_MODULES = (
    "tests.tool_rack.test_pid14048_quote_value_and_stall",
    "tests.tool_rack.test_pid3860_stall_harvest_rollover",
    "tests.tool_rack.test_pid23160_patient_heist_parent",
    "tests.tool_rack.test_pid10760_preopen_rollover",
    "tests.tool_rack.test_pid14156_heist_territory_transfer",
    "tests.tool_rack.test_pid14156_heist_territory_transfer",
    "tests.tool_rack.test_pid19616_entry_quality",
    "tests.tool_rack.test_pid19616_entry_quality",
    "tests.tool_rack.test_pid18244_parent_custody_protection",
    "tests.tool_rack.test_pid21672_confirmed_parent_transfer",
    "test_upload_parts",
    "test_post_run_workflow",
    "test_complete_paper_run",
    "test_capture_integrity",
    "test_snapshot_delta",
    "test_next_run_capture",
    "test_capture_session",
    "tests.tool_rack.test_recorded_session_launcher",
    "tests.tool_rack.test_session_draining_launcher",
    "tests.tool_rack.test_paper_launcher_export",
    "tests.tool_rack.test_paper_reconcile_launcher",
    "tests.tool_rack.test_windows_text_encoding_contract",
)

EXCLUDED_LEGACY_TESTS = (
    # Historical tests below deliberately require strategies that are dormant
    # in this release.  They remain source history, not current acceptance.
    "test_commander_end_to_end",
    "test_entry_window_draining",
    "test_event_timeline",
    "test_full_arc_failure_management",
    "test_live_release_transition_integration",
    "test_live_terrain_source_integration",
    "test_nautilus_timeline_patch",
    "test_nautilus_vnext_patch",
    "test_ordinary_profit_breathing",
    "test_paid_arc_holding_independent",
    "test_paper_runtime_accounting",
    "test_pid10092_mission_policy",
    "test_pid10092_role_missions",
    "test_pid12156_physical_authority_regressions",
    "test_pid12448_main_candidate_review",
    "test_pid12448_tactical_collection_boundary",
    "test_pid13432_mountain_routing",
    "test_pid16280_mountain_corrections",
    "test_pid16280_release_custody",
    "test_profit_protection_corrections",
    "test_r22_adapter",
    "test_r22_run_source",
    "test_rail_tool",
    "test_release_transition_controller",
    "test_release_watcher",
    "test_shadow_bundle",
    "test_shadow_compare",
    "test_shadow_engine",
    "test_simple_zone_routing",
    "test_source_gap_reacquisition",
)


TEST_FILES = ("tests/__init__.py", "tests/tool_rack/__init__.py") + tuple(
    module.replace(".", "/") + ".py" for module in TEST_MODULES
)
PACKAGE_FILES = tuple(sorted(CORE_FILES + ASSET_FILES + SUPPORT_FILES + TEST_FILES))
THIRD_PARTY_IMPORTS = frozenset({"websockets", "cryptography"})
INSTALLER_VERSIONS = {"websockets": "16.0", "cryptography": "50.0.2"}

# These tests use the real Commander/executor/journal, not a shadow candidate.
# Renamed historical controls distinguish old adviser labels from the current
# shared positive admission contract. Exact source and objective mechanics
# remain mandatory, alongside all new opportunity/custody diagnostic controls.
MANDATORY_TEST_METHODS = frozenset({
    "test_observed_exhausted_frozen_destination_exits_without_adviser_authority",
    "test_before_target_and_still_advancing_remain_local_holds",
    "test_stale_foreign_or_mixed_proof_cannot_fall_through_to_unrelated_child_terminal",
    "test_collection_requires_current_positive_net_for_the_full_remaining_lot",
    "test_floor_manual_stop_recovery_and_finality_keep_prior_authority",
    "test_local_seed_families_reach_destination_consumer_but_keep_their_time_limit",
    "test_promoted_main_does_not_reuse_its_old_frozen_local_target",
    "test_earned_local_return_binds_frozen_tactical_destination_not_main",
    "test_real_repeated_heist_is_positive_and_input_is_immutable",
    "test_wide_box_or_primary_label_cannot_replace_repeated_walls",
    "test_source_missing_stale_mixed_generation_and_future_visits_cannot_enter",
    "test_rejected_nonfinite_quote_audit_is_json_safe_and_detached",
    "test_exact_junction_is_wait_even_when_heist_label_is_qualified",
    "test_lower_wall_label_cannot_buy_middle_or_wrong_actual_edge",
    "test_book_callbacks_do_not_create_physical_watch_samples",
    "test_filled_heist_visit_cannot_respray_but_new_visit_is_independent",
    "test_same_child_reextension_cancels_pending_return_without_new_identity",
    "test_completed_retreat_then_new_child_creates_distinct_excursion_same_parent",
    "test_breakout_cancels_counterwatch",
    "test_main_value_search_observes_dip_then_current_rejoin_without_adviser",
    "test_missed_expensive_dip_expires_on_new_high_and_cheap_midleg_does_not_revive",
    "test_normal_main_cannot_skip_first_five_minutes",
    "test_actual_target_distance_overrules_favorable_shape_label",
    "test_parent_age_never_restarts_with_new_child_comparison_envelope",
    "test_original_input_hashes_and_no_outcomes_in_candidate_projection",
    "test_recorded_mountain_reextension_sequence_is_one_unpaid_watch",
    "test_original_opening_and_wide_only_heists_do_not_gain_authority_from_pnl",
    "test_exact_second_half_target_review_names_actual_side_and_reason",
    "test_original_upper_rejection_remains_admitted_on_exact_source_order",
    "test_source_rail_six_does_not_collect_live_parent_at_child_terminal",
    "test_source_rail_four_opposite_child_is_not_held_parent_terminal",
    "test_synthetic_true_new_parent_terminal_still_collects",
    "test_synthetic_parent_geometry_identity_is_mandatory",
    "test_missing_parent_or_mismatched_mission_cannot_fall_back_to_child_exit",
    "test_missing_unparseable_or_future_parent_edge_cannot_collect",
    "test_synthetic_preentry_parent_edge_does_not_close_new_position",
    "test_objective_floor_and_latched_exit_keep_priority",
    "test_current_qualified_but_unbooked_opportunity_keeps_exact_final_reason",
    "test_same_source_but_skipped_evaluation_never_reuses_old_quote_review",
    "test_ticker_source_or_continuity_change_cannot_relabel_previous_review",
    "test_admission_is_distinct_from_actual_execution_receipt",
    "test_numeric_parent_pullback_rejoin_books_after_five_minutes",
    "test_complete_pid14048_recorded_sequence_is_unmodified",
    "test_earned_edge_brief_wait_then_improved_current_ask_enter",
    "test_no_infinite_wait_at_same_qualified_edge",
    "test_pid14048_050155_first_stall_while_nine_second_motion_positive_wait",
    "test_pid14048_050200_mature_stall_after_current_btc_ema9_turn_collect",
    "test_original_complete_decision_sequence_and_mature_rollover_case",
    "test_repeated_failed_mature_mountain_collects_at_current_fee_positive_peak",
    "test_000954_false_support_during_living_down_parent_not_allowed",
    "test_original_002101_no_29_is_physically_earned_regular_main",
    "test_wide_only_directional_boxes_remain_watch_not_heist_owner",
    "test_true_classic_repeated_heist_is_not_removed",
    "test_pid23160_6_cheap_microstall_is_superseded_by_parent_scale_and_runway",
    "test_214530_physically_earned_preopen_spanning_yes_is_eligible",
    "test_214521_falling_price_first_quote_remains_wait",
    "test_opposite_confirmed_parent_tp_or_spine_collision_remain_wait",
    "test_1950_earliest_falling_lower_edge_is_still_wait",
    "test_1950_first_earned_same_gap_heist_lower_return_is_not_false_fade",
    "test_1938_immature_fast_extreme_does_not_count_as_parent_terminal",
    "test_true_full_scale_fast_extreme_positive_boundary_still_eligible",
    "test_3_recorded_broken_prior_low_rejected_before_25_dollar_candidate",
    "test_7_stalled_edge_of_expanding_down_parent_is_not_causal_return",
    "test_8_recorded_2_85_contract_parent_has_no_new_premium_opening",
    "test_4_and_6_positive_steep_extremes_are_not_treated_as_7_microstall",
    "test_prior_pid15740_53c_opening_positive_remains",
    "test_3_historical_no_precedent_does_not_grant_wrong_side_main",
    "test_4_current_opposing_parent_restores_40pct_tactical_first_floor",
    "test_6_first_class_recent_level_match_no_entry_remains",
    # PID10656 reviewed sprout quality, pattern display and historical pins.
    "test_joint_turn_releases_sprout_restraint_but_still_needs_positive_species",
    "test_adapter_copies_parent_and_gap_source_without_creating_authority",
    "test_already_calibrated_recorded_proposals_do_not_bypass_rack_briefing",
    "test_alternating_and_rolling_mountains_keep_an_observed_turn",
    "test_as_issued_is_bounded_source_forward_and_cleared_for_a_new_run",
    "test_as_issued_requires_fresh_source_and_known_continuity",
    "test_confirmed_corrective_transfer_retains_existing_authority",
    "test_confirmed_release_and_forming_release_are_distinct",
    "test_down_rail_uses_down_shape_and_explicit_mirroring",
    "test_existing_price_caps_sizes_and_window_remain_unchanged",
    "test_finite_rail_fallback_stops_at_the_witnessed_shape",
    "test_first_issued_sample_stays_fixed_and_detached",
    "test_first_minute_actual_yes_quotes_have_forty_six_to_sixty_nine_cent_range",
    "test_first_minute_affordable_prices_do_not_already_have_causal_rejoin",
    "test_fresh_supported_parent_takes_precedence_over_local_heist",
    "test_future_or_unfinished_history_cannot_change_active_trace",
    "test_single_retreat_flag_cannot_override_opening_cadence_or_stale_wall_visit",
    "test_micro_stall_and_terminal_label_alone_do_not_fade_outward_sprout",
    "test_minimum_quote_during_first_minute_has_unresolved_target_ownership",
    "test_mirrored_recorded_fresh_down_sprouts_do_not_accept_yes_fades",
    "test_missing_shape_never_becomes_a_fabricated_next_mountain",
    "test_no_current_pattern_on_stale_wrong_contract_or_wrong_source",
    "test_observed_cross_is_at_source_rollover_and_book_is_not_yet_tradeable",
    "test_old_turn_subrow_cannot_nullify_current_outward_sprout",
    "test_opening_audit_retains_original_held_inventory_and_future_limits",
    "test_original_positive_outcomes_are_recorded_controls_not_added_profit",
    "test_original_records_and_histories_remain_hash_bound",
    "test_original_winning_entries_keep_intent_price_quantity_and_fee",
    "test_other_gap_stages_do_not_acquire_a_new_global_heist_pause",
    "test_pid4824_approval_identity_cannot_be_replaced_to_hide_changes",
    "test_pid4824_source_identity_cannot_be_replaced_to_hide_changes",
    "test_price_only_wick_does_not_override_still_outward_ema9",
    "test_primary_family_relabel_cannot_bypass_same_heist_quality_boundary",
    "test_rail_features_a_matching_unchanged_continuation",
    "test_recorded_7304_7584_contexts_feature_current_fresh_up_leg",
    "test_recorded_trade3_calibrated_heist_waits_for_actual_turn",
    "test_recorded_trade4_cheap_mature_edge_label_is_not_parent_turn",
    "test_rejoin_then_target_agreement_arrive_after_premium_first_minute",
    "test_release_before_ema_spine_cross_keeps_its_independent_admission",
    "test_same_side_heist_is_outside_counter_sprout_boundary",
    "test_stale_or_invalid_parent_cannot_borrow_the_sprout_label",
    "test_stale_or_mismatched_source_does_not_become_a_new_parent_proof",
    "test_unknown_motion_and_clock_only_label_do_not_create_protection",
    "test_unwitnessed_gap_label_alone_has_no_new_sprout_authority",
    "test_pid15184_source_identity_cannot_be_replaced_to_hide_changes",
    # PID15184 current-parent identity, original chronology and preserved admissions.
    "test_exact_original_case_hashes_and_complete_chronology_are_verified",
    "test_original26_has_current_completed_close_parent_not_witnessed_origin",
    "test_only_first_recorded_entry_changes_in_original_ordered_component_stream",
    "test_first_current_observation_precedes_later_entries_and_history_qualification",
    "test_current_full_arc_proof_is_preserved_and_shared_admission_checks_actual_quality",
    "test_candidate_custody_and_freshness_modules_are_byte_unchanged",
    "test_supported_false_does_not_invalidate_active_known_parent",
    "test_no_owner_only_or_nonterminal_structure_fallback_is_added",
    "test_missing_stale_unrelated_or_invalid_current_packets_supply_no_parent",
    "test_current_source_clock_lead_requires_original_receipt",
    "test_legacy_historical_and_release_directions_remain_available",
    "test_qualified_history_precedes_opposite_current_mission",
    "test_all_main_and_tactical_counter_families_observe_first_swing",
    "test_current_parent_first_and_later_swing_are_symmetric",
    "test_quote_and_rolling_box_changes_do_not_create_later_swing",
    "test_rollover_and_benign_mission_labels_preserve_current_chapter",
    "test_gaining_historical_qualification_is_not_a_second_first_swing",
    "test_genuine_parent_side_identity_and_continuity_changes_reset_sample",
    "test_opposite_gap_cannot_name_current_mission_or_reuse_calibration",
    "test_actual_opposite_child_can_be_observed_before_a_paid_offer",
    "test_later_current_parent_heist_marker_uses_same_actual_calibration",
    "test_no_marker_on_main_or_primary_label",
    "test_same_side_unknown_and_nonentry_bypasses_clear_stale_marker",
    "test_release_handoff_and_confirmed_release_bypasses_clear_stale_marker",
    "test_genuine_terminal_plus_tp_bypass_clears_stale_marker",
    "test_new_chapter_cannot_reuse_previous_offer_marker",
    "test_proof_is_bound_to_exact_intent_and_snapshot_consideration",
    "test_prior_behavior_archive_and_original_positive_fixture_bytes_are_unchanged",
    "test_prior_positive_uses_actual_ordered_observations_without_chapter_reset",
    "test_pid17588_source_identity_cannot_be_replaced_to_hide_changes",
    # Original late-scout omission and preserved successful admissions.
    "test_original_fixture_bytes_and_histories_are_verified",
    "test_original_late_scout_is_not_proposed_or_admitted",
    "test_original_120_second_source_boundary_retains_existing_meaning",
    "test_original_first_two_pid19996_entry_trajectories_keep_precise_wait_diagnostics",
    "test_original_pid17588_winners_keep_exact_entry_components",
    "test_synthetic_late_favored_return_remains_eligible",
    "test_synthetic_mirror_has_same_existing_clock_and_tp_requirement",
    "test_pid4596_source_identity_cannot_be_replaced_to_hide_changes",
    # Returned PID4596 crash: bounded original evidence and narrow runtime repair.
    "test_fixture_preserves_provenance_and_does_not_claim_missing_atomic_input",
    "test_raw_source_reproduces_previous_metadata_and_final_retained_geometry",
    "test_hash_verified_captured_source_reproduces_exact_error_and_line",
    "test_repair_returns_original_wait_advice_without_creating_price_or_authority",
    "test_unavailable_estimate_clears_prior_suggestion_on_rereview",
    "test_finite_passing_and_below_hurdle_scenarios_match_captured_behavior",
    "test_a_later_calibrated_observation_can_be_reviewed_after_missing_estimate",
    "test_pid19996_source_identity_cannot_be_replaced_to_hide_changes",
    "test_first_causal_value_rejoin_is_8860_at_35c_before_session_deadline",
    "test_first_two_winners_keep_original_first_eligible_entries",
    "test_consumed_original_opening_cannot_reenter_through_direct_admission",
    "test_quote_observer_replaces_stale_eleven_cent_quote_with_current_six_cents",
    "test_recorded_holds_successful_peak_exits_and_final_exit_keep_exact_floor_results",
    "test_receipt_must_belong_to_exact_geometry_epoch_sequence_and_continuity",
    "test_actual_invalid_63900_and_79900_percent_pairs_stay_separate",
    "test_actual_same_contract_six_to_twenty_one_cent_move_is_preserved",
    "test_new_delta_preserves_the_pinned_historical_two_file_approval",
    "test_added_helper_requires_exact_reviewed_hash",
    # PID8552 exact recorded counterfades and whole-lot sloped Rail custody.
    "test_trade5_rail_style_living_down_leg_no_first_floor_at_204_seconds",
    "test_trade2_no_early_yes_against_continuing_down",
    "test_trade3_no_repeat_cheap_yes_without_green_ema9_turn",
    "test_trade1_last_97s_no_proven_yes_contract_runway",
    # Mountain-only constitutional strategy controls.
    "test_true_top_under_20_enters_no",
    "test_true_top_at_20_waits",
    "test_rollover_contract_leg_explicit_tp_under_40_enters",
    "test_same_leg_after_four_minute_rollover_window_waits",
    "test_bounce_favored_true_edge_under_40_enters",
    "test_ema_tp_junction_waits",
    "test_strong_expansion_not_faded",
    "test_nonmountain_has_no_candidates",
    "test_authorized_specialist_needs_a_measured_location_not_only_its_label",
    "test_candidate_carries_approved_floor",
    "test_commander_candidate_commits_without_specialist_owner",
    "test_pid8868_partial_top_preserves_factory_species_but_shared_admission_waits",
    "test_pid8868_stale_cheap_hover_stays_blocked",
    "test_pid8868_partial_rollover_preserves_factory_species_but_shared_admission_waits",
    "test_pid8868_actual_current_held_no_terminal_triggers_exit",
    "test_late_top_far_tp_without_proven_return_runway_waits",
    "test_late_top_can_enter_only_when_recent_down_legs_can_reach_tp",
    "test_late_top_far_tp_blocks_even_when_quote_is_extremely_cheap",
    "test_gap_lifecycle_sprout_developing_mature_rolling_is_descriptive",
    "test_sprout_gap_still_expanding_blocks_false_peak_like_trade8",
    "test_sprout_gap_real_causal_turn_can_still_enter_like_trade1",
    "test_mature_gap_does_not_get_sprout_veto",
    "test_continuous_runway_blocks_quiet_regime_even_just_over_five_minutes",
    "test_continuous_runway_allows_late_large_swing_regime",
    "test_rollover_spent_mature_gap_collapsed_to_spine_blocks_trade7_shape",
    "test_pid3296_0831_rolling_gap_child_terminal_turn_waits_when_tp_owns_no",
    "test_rolling_gap_child_still_advancing_does_not_enter_mid_pullback",
    "test_mature_gap_without_current_child_terminal_does_not_gain_clock_authority",
    "test_rolling_gap_pullback_still_requires_dynamic_tp_runway",
    "test_rolling_gap_collapsed_to_spine_does_not_create_continuation",
    "test_pid3296_trade2_thin_tp_possession_is_not_automatic_runway",
    "test_target_possession_can_still_pass_late_in_fast_directional_regime",
    "test_pid23072_prefix_factory_controls_and_shared_quality_are_distinct",
    "test_pid23072_trade1_good_edge_has_proven_return_runway",
    "test_pid23072_trade7_new_gap_cannot_masquerade_as_inherited_leg",
    "test_pid23072_trade8_sprout_is_still_expanding_not_true_peak",
    "test_pid23072_trade10_extended_factory_candidate_needs_independent_terminal_proof",
    "test_collection_uses_stricter_terminal_than_entry_and_holds_early",
    "test_operator_authorized_profit_lock_blocks_120pct_peak_from_falling_to_36pct",
    "test_sideways_no_terrain_uses_only_operator_authorized_3pct_peak_lock",
    "test_sideways_no_terrain_120pct_peak_cannot_fall_to_36pct",
    "test_sideways_flag_does_not_override_an_owned_mountain_terrain",
    "test_pid12220_trade1_120pct_exact_peak_stall_collects_before_floor",
    "test_peak_hover_skim_does_not_fire_off_peak_or_during_release",
    "test_under_half_previous_arc_scale_has_hard_peak_veto",
    # PID3216 authorized implementation-defect repairs.
    "test_small_negative_geometry_age_is_clock_skew_not_stale",
    "test_materially_future_geometry_remains_invalid",
    "test_pid3216_style_hover_can_prove_terminal_before_duration_maturity",
    "test_pid3216_actual_ultra_160950_hover_now_qualifies_terminal",
    "test_still_advancing_parent_does_not_gain_hover_maturity",
    "test_pid3216_hover_does_not_change_tp_between_emas_wait_rule",
    "test_full_paper_entry_hold_exit_is_committed",
    "test_filled_physical_mission_does_not_rearm_on_quote_refresh",
    "test_compact_export_excludes_raw_decisions_and_keeps_selected_forensic_stream",
    # PID2672 operator-authorized junction / Rail EMA9 dip / paired-gap repairs.
    "test_looking_glass_tolerates_same_two_second_future_skew",
    "test_mission_context_tolerates_same_two_second_future_skew",
    "test_paired_gap_is_prepare_alert_not_paid_terminal_by_itself",
    "test_old_partial_tp_junction_proposal_cannot_publish_current_executable_candidate",
    "test_same_tp_junction_relaxation_is_not_available_inside_final_five_minutes",
    "test_pid2672_2016_mature_up_rail_ema9_dip_can_use_20c_value_ceiling",
    # PID252 tactical anti-starvation / Release promotion controls.
    "test_historical_extreme_release_prep_requires_reversal_and_cheap_value",
    "test_heist_seed_promotes_to_same_side_release_custody",
    "test_leg_aligned_winner_delays_first_floor_to_200pct_until_stall",
    "test_wide_heist_qualifies_after_long_bilateral_revisitation",
    # PID7812 seed-promotion / fresh-sprout anti-fade controls.
    "test_trade18_heist_seed_promotes_to_living_ema9_custody",
    "test_trade18_quick_heist_floor_waits_for_200pct_while_leg_alive",
    "test_trade19_opposite_heist_briefing_is_not_sent_during_yes_precedent",
    "test_trade20_fast_no_fade_is_not_generated_during_fresh_yes_sprout",
    "test_mirror_fresh_no_sprout_does_not_brief_yes_fade",
    # PID14312 arc-selection / custody controls.
    "test_trade2_young_yes_sprout_does_not_brief_no_fade",
    "test_trade3_ultracheap_extended_top_seed_remains_eligible",
    "test_trade5_expensive_counter_return_is_not_briefed",
    "test_trade7_up_arc_tp_continuation_suppresses_no_renter_before_cross",
    "test_trade8_mature_stalled_sub20_return_is_allowed",
    "test_level_match_return_floor_breathes_30_seconds",
    "test_promoted_trade3_survives_180s_when_current_arc_is_held_side",
    "test_trade8_level_match_survives_180s_while_tp_bounce_favors_held_side",
    "test_trade6_unsupported_return_exits_after_transition_window",
    "test_late_release_carries_60pct_floor_and_150pct_immediate_lock",
    "test_late_release_floor_is_not_promoted_to_200pct_runner",
    # PID1172 operator-authorized selection / Release / Heist / Rail-price repairs.
    "test_house_protected_still_allows_sub20_true_terminal_but_not_contract_leg",
    "test_mountain_late_defer_is_advisory_not_commander_veto",
    "test_release_local_bounce_cannot_break_intact_mature_opposite_gap",
    "test_heist_pop_prep_real_break_plus_expansion_can_confirm_release",
    "test_heist_blocked_inside_living_mature_directional_parent",
    "test_far_tp_single_outlier_does_not_prove_return_runway",
    "test_rail_preferred_35_and_established_dip_hard_below_40",
    "test_wide_heist_32c_requires_confirmed_return_and_then_enters",
    "test_wide_heist_above_35_waits",
    "test_quote_wave_revisits_do_not_replace_physical_terminal_or_repeated_walls",
    "test_quote_wave_scalp_does_not_create_trade_without_edge",
    "test_rail_requires_two_same_direction_arcs_and_long_persistence",
    # Operator-authorized Release / Rail / Heist reactivation controls.
    "test_parallel_heist_arms_excursion_but_does_not_fade_extension",
    "test_parallel_heist_enters_no_only_after_upper_excursion_returns",
    "test_qualified_parallel_box_also_waits_for_return_not_first_push",
    "test_unproven_parallel_return_remains_advice_until_repeated_walls_exist",
    "test_parallel_heist_release_cancels_return",
    "test_late_heist_fast_regime_can_enter",
    "test_late_heist_quiet_regime_is_blocked_by_dynamic_runway",
    "test_late_rail_fast_regime_can_enter",
    "test_late_rail_quiet_regime_is_blocked",
    "test_confirmed_release_is_reactivated_but_first_slowdown_is_not",
    "test_commander_blocks_unapproved_specialist_and_legacy_mountain_intent",
    # Operator-authorized Heist / Release / rollover / house-protection controls.
    "test_parallel_heist_overlay_coexists_with_mountain_and_survives_to_return",
    "test_primary_heist_arm_survives_classifier_flicker_to_mountain",
    "test_armed_heist_overlay_owns_quick_return_and_suppresses_competing_mountain_edge",
    "test_living_release_suppresses_parallel_heist_overlay",
    "test_confirmed_release_is_attached_to_mountain_owner_and_produces_relay",
    "test_three_completed_quick_heist_contracts_prepare_fourth_without_entry_authority",
    "test_quick_heist_entry_carries_immediate_40pct_3pct_peak_lock",
    "test_quick_heist_40pct_floor_actually_arms_in_executor",
    "test_rollover_terminal_return_below_50_has_quick_floor_and_50_is_strict",
    "test_pop_prep_context_reaches_confirmed_release_without_granting_early_entry",
    "test_house_state_one_win_caution_two_wins_or_100pct_protected",
    "test_house_protected_blocks_non_heist_but_good_heist_remains_exception",
    "test_house_caution_uses_live_ask_and_does_not_replace_source_proof",
    # End-to-end PAPER Rail admission/provenance/anti-spray controls.
    "test_raw_monotone_rail_label_and_cheap_quote_wait_for_located_rejoin",
    "test_repeat_rail_observation_does_not_spray_same_contract",
    "test_rail_value_window_waits_expensive_then_books_value",
    "test_reactivated_rail_keeps_existing_custody_policy_unchanged",
    "test_long_parent_rail_rollover_does_not_create_unearned_first_minute_entry",
    "test_stale_native_quote_does_not_book_despite_qualified_rail",
    "test_parent_scale_rail_without_history_is_detected_but_paused",
    "test_parent_scale_rail_without_target_is_detected_but_paused",
    "test_future_known_seed_cannot_create_thesis_and_rail_remains_paused",
    # Objective PAPER ledger / exact execution safety.
    "test_sub20_budget_reproduces_138_contracts_and_fee_aware_cash",
    "test_exact_modeled_round_trip_and_committed_net",
    "test_losing_position_can_exit_no_sanctuary",
    "test_armed_floor_cannot_be_lowered_or_waived_and_never_autosells",
    "test_only_official_final_exact_contract_result_settles",
    "test_failed_atomic_commit_never_publishes_uncommitted_position",
    "test_existing_ledger_cannot_be_blindly_restarted",
    "test_recovery_loads_exact_lot_and_appends_only_official_settlement",
    # PID4824 source-bound recovery identity and first-floor authority controls.
    "test_actual_measured_post_fill_rejection_preserved",
    "test_all_34_original_release_offers_keep_original_component_denials",
    "test_bounded_report_separates_original_inventory_and_flat_sensitivity",
    "test_complete_original_published_callback_probe_has_no_new_grants",
    "test_completed_close_origin_stays_unobserved",
    "test_current_genuinely_new_owner_with_new_arc_preserved",
    "test_current_new_owner_can_precede_local_arc_label_change",
    "test_current_owner_is_pinned_at_flat_entry_without_changing_permission",
    "test_denied_second_entry_does_not_imply_third_removed_when_flat",
    "test_exact_original_hashes_journals_and_parent_prefix",
    "test_exit_required_is_not_cleared_by_new_owner",
    "test_future_or_not_yet_known_origin_cannot_prove_new_owner_after_reset",
    "test_healed_wound_and_second_lot_capacity_keep_existing_boundary",
    "test_measured_rejection_label_or_old_unordered_measurements_do_not_renew",
    "test_mirrored_same_side_wound_denial_and_measured_rejection",
    "test_missing_stale_or_unrelated_current_owner_cannot_renew_pinned_wound",
    "test_new_child_arc_does_not_refill_same_parent_wound",
    "test_new_extreme_route_and_commander_label_do_not_renew_same_parent",
    "test_no_parent_and_no_arc_are_not_equal_physical_identities",
    "test_non_entry_action_remains_untouched",
    "test_observed_new_owner_after_reset_preserved",
    "test_opposite_corrective_mission_preserved",
    "test_original_flat_entries_and_real_heist_winner_preserved",
    "test_original_second_entry_denied_with_first_lazarus_wound",
    "test_original_third_entry_separately_denied_with_second_lazarus_wound",
    "test_prior_actual_independent_p18_p19_scope_preserved",
    "test_reset_rename_without_observed_new_owner_does_not_renew",
    "test_same_parent_scope_and_unqualified_scope_do_not_renew",
    "test_scope_route_cannot_reacquire_same_pinned_legacy_owner",
    "test_source_pre_entry_rejection_is_not_post_fill_from_clock_skew",
    "test_supplied_old_recovery_proof_is_removed_on_same_arc_denial",
    "test_already_armed_original_floor_policy_is_byte_for_byte_equivalent",
    "test_complete_original_records_and_ordered_intervals_are_bound",
    "test_confirmed_current_handoff_preserves_preexisting_continuation_runway",
    "test_confirmed_flag_does_not_invent_a_new_continuation_or_floor_exception",
    "test_first_floor_still_requires_full_original_quantity_and_current_bid",
    "test_genuine_same_side_current_release_keeps_existing_runway",
    "test_immediate_150_protection_does_not_require_30_seconds_or_next_candle",
    "test_known_same_side_parent_keeps_existing_200_percent_runway",
    "test_ordered_original_lot_arms_then_triggers_only_on_available_later_bid",
    "test_original_peak_is_current_whole_lot_profit_under_opposing_parent",
    "test_real_local_continuation_is_retained_without_parent_floor_authority",
    "test_successful_original_heist_floor_trajectory_is_exactly_preserved",
    "test_symmetric_no_return_keeps_ordinary_protection_under_current_yes_parent",
    "test_unbound_or_stale_parent_cannot_supply_the_new_restriction",
    "test_unchanged_mechanics_adviser_and_inherited_behavioral_assertions",
    "test_unknown_current_parent_keeps_existing_local_continuation_fallback",
    "test_unsupported_but_current_active_parent_is_not_forgotten",
})


def module_name(relative: str) -> str:
    name = relative[:-3].replace("/", ".")
    return name[:-9] if name.endswith(".__init__") else name


def audit_package_files(root: Path) -> None:
    """Validate complete files, syntax, UTF-8 I/O and static import closure."""
    selected = set(PACKAGE_FILES)
    if len(selected) != len(PACKAGE_FILES):
        raise ValueError("Duplicate path in PAPER package whitelist")
    missing = [name for name in PACKAGE_FILES if not (root / name).is_file()]
    if missing:
        raise ValueError("Incomplete PAPER package: " + ", ".join(missing))
    modules = {module_name(name) for name in PACKAGE_FILES if name.endswith(".py")}
    local_roots = {name.split(".")[0] for name in modules}
    problems = []
    for relative in PACKAGE_FILES:
        path = root / relative
        if path.resolve() != path.absolute() or path.is_symlink():
            problems.append(relative + ": package sources must be regular, non-symlink files")
        if relative.endswith(".cmd"):
            data = path.read_bytes()
            data.decode("utf-8")
            if data.startswith(b"\xef\xbb\xbf") or b"\n" in data.replace(b"\r\n", b""):
                problems.append(relative + ": launcher requires UTF-8 without BOM and CRLF lines")
            if "INSTALL" not in relative and b"pip install" in data.lower():
                problems.append(relative + ": start/check/export may not install dependencies")
        if not relative.endswith(".py"):
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        compile(tree, relative, "exec")
        current = module_name(relative)
        package = current if relative.endswith("/__init__.py") else current.rpartition(".")[0]
        for node in ast.walk(tree):
            imported = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    imported = [importlib.util.resolve_name("." * node.level + (node.module or ""), package)]
                elif node.module:
                    imported = [node.module]
            for name in imported:
                top = name.split(".")[0]
                if top in local_roots and name not in modules:
                    problems.append(f"{relative}:{node.lineno}: local import outside whitelist: {name}")
                elif top not in local_roots | THIRD_PARTY_IMPORTS | sys.stdlib_module_names:
                    problems.append(f"{relative}:{node.lineno}: undeclared dependency: {name}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                if attr in ("read_text", "write_text"):
                    explicit = any(key.arg == "encoding" for key in node.keywords)
                    explicit |= len(node.args) >= (1 if attr == "read_text" else 2)
                    if not explicit:
                        problems.append(f"{relative}:{node.lineno}: {attr} requires explicit encoding")
    if problems:
        raise ValueError("PAPER package audit failed:\n" + "\n".join(problems))


def verify_manifest(root: Path, *, required: bool = False) -> bool:
    path = root / MANIFEST_NAME
    if not path.is_file():
        if required:
            raise ValueError("Extracted bundle manifest is missing")
        return False
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("Unexpected PAPER bundle manifest schema")
    if manifest.get("release_id") != RELEASE_ID:
        raise ValueError("PAPER bundle release identifier does not match this correction package")
    if manifest.get("mode") != "PAPER" or manifest.get("venue_order_authority") != "NONE":
        raise ValueError("PAPER-only manifest authority mismatch")
    if (manifest.get("strategy_modified") is not True
            or manifest.get("approved_strategy_corrections") != APPROVED_CORRECTIONS
            or manifest.get("baseline_package_sha256") != BASELINE_PACKAGE_SHA256
            or manifest.get("previous_package_sha256") != PREVIOUS_PACKAGE_SHA256):
        raise ValueError("Approved correction release identity is missing or misleading")
    if manifest.get("engineering_candidate") is True:
        raise ValueError("Approved strategy corrections require the full delivery gate")
    if manifest.get("windows_runtime_verified") is not False:
        raise ValueError("This correction package has no new native Windows run evidence")
    if manifest.get("recommended_entry_window_minutes") != 45:
        raise ValueError("Approved next-run commissioning window must be 45 minutes")
    records = manifest.get("files", {})
    if set(records) != set(PACKAGE_FILES):
        raise ValueError("Manifest file set differs from the strict PAPER whitelist")
    for relative, record in records.items():
        data = (root / relative).read_bytes()
        if len(data) != record["size"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError("Bundle file changed or is incomplete: " + relative)
    for folder in ("strategy_core", "tests"):
        for extra in (root / folder).rglob("*.py"):
            if extra.relative_to(root).as_posix() not in records:
                raise ValueError("Unexpected Python file inside extracted bundle: " + str(extra))
    return True


def verify_frozen_source(root: Path) -> int:
    """Verify every sealed source file for this approved release, without import."""
    expected = json.loads((root / "SOURCE_SHA256.json").read_text(encoding="utf-8"))
    frozen_files = tuple(name for name in CORE_FILES + ASSET_FILES
                         if name.startswith("strategy_core/"))
    if not isinstance(expected, dict) or set(expected) != set(frozen_files) or len(expected) != len(frozen_files):
        raise ValueError("Sealed source manifest must identify every whitelisted strategy/config/UI file")
    actual = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in frozen_files}
    if actual != expected:
        changed = sorted(name for name in frozen_files if actual[name] != expected[name])
        raise ValueError("Sealed strategy/config/UI source changed: " + ", ".join(changed))
    verify_authorized_delta(root, actual)
    return len(actual)


def verify_authorized_delta(root: Path, current: dict[str, str] | None = None) -> dict:
    """Preserve historical lineage and bind this change to the captured PID3904 source."""
    def pinned(name, digest, message):
        raw = (root / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(message)
        return json.loads(raw)
    baseline = pinned("BASELINE_SOURCE_SHA256.json", BASELINE_SOURCE_MANIFEST_SHA256,
                      "PID17224 captured baseline source manifest changed")
    abc = pinned("PREVIOUS_RELEASE_SOURCE_SHA256.json", PREVIOUS_SOURCE_MANIFEST_SHA256,
                 "Previous release source manifest changed")
    abc_approval = pinned("PREVIOUS_RELEASE_APPROVAL.json", PREVIOUS_APPROVAL_SHA256,
                          "Previous release approval changed")
    abc_changed = {name for name in abc if abc[name] != baseline.get(name)}
    if (set(abc) != set(baseline) or abc_changed != HISTORICAL_APPROVED_FILES
            or abc_approval.get("approved_corrections") != ["A", "B", "C"]
            or set(abc_approval.get("changed_core_files", {})) != abc_changed):
        raise ValueError("Historical PID17224 two-file A/B/C scope changed")
    for name in abc_changed:
        if abc_approval["changed_core_files"][name] != {"baseline_sha256": baseline[name], "release_sha256": abc[name]}:
            raise ValueError("Historical PID17224 approved hash mismatch: " + name)
    previous = pinned("PID19996_SOURCE_SHA256.json", PID19996_SOURCE_MANIFEST_SHA256,
                      "PID19996 source manifest changed")
    prior_approval = pinned("PID19996_APPROVAL.json", PID19996_APPROVAL_SHA256,
                           "PID19996 approval changed")
    if set(previous) != set(abc) | PID19996_ADDED_CORE_FILES:
        raise ValueError("Historical PID19996 source file set changed")
    prior_changed = {name for name in abc if previous[name] != abc[name]}
    if (prior_changed != PID19996_CHANGED_CORE_FILES
            or prior_approval.get("previous_package_sha256") != PID17224_PACKAGE_SHA256
            or prior_approval.get("approved_corrections") != APPROVED_CORRECTIONS[:7]
            or set(prior_approval.get("changed_core_files", {})) != prior_changed
            or set(prior_approval.get("added_core_files", {})) != PID19996_ADDED_CORE_FILES):
        raise ValueError("Historical PID19996 approved scope changed")
    for name, hashes in prior_approval["changed_core_files"].items():
        if hashes != {"baseline_sha256": abc[name], "release_sha256": previous[name]}:
            raise ValueError("Historical PID19996 approved hash mismatch: " + name)
    for name, digest in prior_approval["added_core_files"].items():
        if digest != previous[name]:
            raise ValueError("Historical PID19996 added helper hash mismatch: " + name)
    pid19996 = previous
    previous = pinned("PID4596_SOURCE_SHA256.json", PID4596_SOURCE_MANIFEST_SHA256,
                      "PID4596 source manifest changed")
    repair_approval = pinned("PID4596_APPROVAL.json", PID4596_APPROVAL_SHA256,
                             "PID4596 approval changed")
    repair_changed = {name for name in pid19996 if previous.get(name) != pid19996[name]}
    if (set(previous) != set(pid19996) or repair_changed != PID4596_CHANGED_CORE_FILES
            or repair_approval.get("previous_package_sha256") != PID19996_PACKAGE_SHA256
            or repair_approval.get("approved_corrections") != APPROVED_CORRECTIONS[:8]
            or set(repair_approval.get("changed_core_files", {})) != repair_changed
            or repair_approval.get("added_core_files") != {}):
        raise ValueError("Historical PID4596 runtime repair scope changed")
    for name, hashes in repair_approval["changed_core_files"].items():
        if hashes != {"baseline_sha256": pid19996[name], "release_sha256": previous[name]}:
            raise ValueError("Historical PID4596 approved hash mismatch: " + name)
    pid4596 = previous
    previous = pinned("PID17588_SOURCE_SHA256.json", PID17588_SOURCE_MANIFEST_SHA256,
                      "PID17588 source manifest changed")
    scout_approval = pinned("PID17588_APPROVAL.json", PID17588_APPROVAL_SHA256,
                            "PID17588 approval changed")
    scout_changed = {name for name in pid4596 if previous.get(name) != pid4596[name]}
    if (set(previous) != set(pid4596) or scout_changed != PID17588_CHANGED_CORE_FILES
            or scout_approval.get("previous_package_sha256") != PID4596_PACKAGE_SHA256
            or scout_approval.get("approved_corrections") != APPROVED_CORRECTIONS[:9]
            or set(scout_approval.get("changed_core_files", {})) != scout_changed
            or scout_approval.get("added_core_files") != {}):
        raise ValueError("Historical PID17588 late-scout repair scope changed")
    for name, hashes in scout_approval["changed_core_files"].items():
        if hashes != {"baseline_sha256": pid4596[name], "release_sha256": previous[name]}:
            raise ValueError("Historical PID17588 approved hash mismatch: " + name)
    pid17588 = previous
    previous = pinned("PID15184_SOURCE_SHA256.json", PID15184_SOURCE_MANIFEST_SHA256,
                      "PID15184 source manifest changed")
    parent_approval = pinned("PID15184_APPROVAL.json", PID15184_APPROVAL_SHA256,
                             "PID15184 approval changed")
    parent_changed = {name for name in pid17588 if previous.get(name) != pid17588[name]}
    if (set(previous) != set(pid17588) or parent_changed != PID15184_CHANGED_CORE_FILES
            or parent_approval.get("previous_package_sha256") != PID17588_PACKAGE_SHA256
            or parent_approval.get("approved_corrections") != APPROVED_CORRECTIONS[:10]
            or set(parent_approval.get("changed_core_files", {})) != parent_changed
            or parent_approval.get("added_core_files") != {}):
        raise ValueError("Historical PID15184 current-parent calibration scope changed")
    for name, hashes in parent_approval["changed_core_files"].items():
        if hashes != {"baseline_sha256": pid17588[name], "release_sha256": previous[name]}:
            raise ValueError("Historical PID15184 approved hash mismatch: " + name)
    pid15184 = previous
    previous = pinned("PID4824_SOURCE_SHA256.json", PID4824_SOURCE_MANIFEST_SHA256,
                      "PID4824 source manifest changed")
    recovery_approval = pinned("PID4824_APPROVAL.json", PID4824_APPROVAL_SHA256,
                               "PID4824 approval changed")
    recovery_changed = {name for name in pid15184 if previous.get(name) != pid15184[name]}
    if (set(previous) != set(pid15184) or recovery_changed != PID4824_CHANGED_CORE_FILES
            or recovery_approval.get("previous_package_sha256") != PID15184_PACKAGE_SHA256
            or recovery_approval.get("approved_corrections") != APPROVED_CORRECTIONS[:12]
            or set(recovery_approval.get("changed_core_files", {})) != recovery_changed
            or recovery_approval.get("added_core_files") != {}):
        raise ValueError("Historical PID4824 recovery/floor repair scope changed")
    for name, hashes in recovery_approval["changed_core_files"].items():
        if hashes != {"baseline_sha256": pid15184[name], "release_sha256": previous[name]}:
            raise ValueError("Historical PID4824 approved hash mismatch: " + name)
    pid3904 = pinned("PID3904_SOURCE_SHA256.json", PID3904_SOURCE_MANIFEST_SHA256,
                     "Captured PID3904 immediate source manifest changed")
    pid3904_approval = pinned("PID3904_APPROVAL.json", PID3904_APPROVAL_SHA256,
                              "Captured PID3904 immediate approval record changed")
    pid14048_changed = {name for name in previous if pid3904.get(name) != previous[name]}
    if (set(pid3904) != set(previous)
            or pid14048_changed != PID14048_CHANGED_CORE_FILES
            or pid3904_approval.get("approved_corrections") != APPROVED_CORRECTIONS[:-2]
            or set(pid3904_approval.get("changed_core_files", {})) != pid14048_changed
            or pid3904_approval.get("added_core_files") != {}):
        raise ValueError("Captured PID3904 historical correction scope changed")
    for name, hashes in pid3904_approval["changed_core_files"].items():
        if hashes != {"baseline_sha256": previous[name], "release_sha256": pid3904[name]}:
            raise ValueError("Captured PID3904 historical hash mismatch: " + name)
    previous = pid3904
    current = current or json.loads((root / "SOURCE_SHA256.json").read_text(encoding="utf-8"))
    if set(current) != set(previous) | APPROVED_ADDED_CORE_FILES:
        raise ValueError("Opportunity-First source set differs from its approved scope")
    changed = {name for name in previous if current[name] != previous[name]}
    if changed != APPROVED_CHANGED_CORE_FILES:
        raise ValueError("Core changes differ from approved Opportunity-First scope: " + ", ".join(sorted(changed)))
    approval = json.loads((root / "APPROVED_STRATEGY_CHANGES.json").read_text(encoding="utf-8"))
    if (approval.get("release_id") != RELEASE_ID
            or approval.get("baseline_package_sha256") != BASELINE_PACKAGE_SHA256
            or approval.get("previous_package_sha256") != PREVIOUS_PACKAGE_SHA256
            or approval.get("approved_corrections") != APPROVED_CORRECTIONS
            or set(approval.get("changed_core_files", {})) != changed
            or set(approval.get("added_core_files", {})) != APPROVED_ADDED_CORE_FILES
            or approval.get("previous_source_manifest") != "PID3904_SOURCE_SHA256.json"
            or approval.get("previous_source_manifest_sha256") != PID3904_SOURCE_MANIFEST_SHA256):
        raise ValueError("Opportunity-First approval record does not describe this release")
    for name, hashes in approval["changed_core_files"].items():
        if hashes != {"baseline_sha256": previous[name], "release_sha256": current[name]}:
            raise ValueError("Approved correction hash mismatch: " + name)
    for name, digest in approval["added_core_files"].items():
        if digest != current[name]:
            raise ValueError("Approved Opportunity-First helper hash mismatch: " + name)
    return {"baseline_files": len(baseline), "previous_files": len(previous),
            "historical_changed_files": sorted(abc_changed),
            "pid19996_changed_files": sorted(prior_changed),
            "pid19996_added_files": sorted(PID19996_ADDED_CORE_FILES),
            "pid4596_changed_files": sorted(repair_changed),
            "pid17588_changed_files": sorted(scout_changed),
            "pid15184_changed_files": sorted(parent_changed),
            "pid4824_changed_files": sorted(recovery_changed),
            "pid14048_changed_files": sorted(pid14048_changed),
            "immediate_previous_source": "PID3904_SOURCE_SHA256.json",
            "changed_files": sorted(changed), "added_files": sorted(APPROVED_ADDED_CORE_FILES),
            "unchanged_files": len(previous)-len(changed)}


def check_dependencies() -> dict[str, str]:
    from websockets.sync.client import connect
    import websockets
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

    required = {"additional_headers", "ping_interval", "ping_timeout", "open_timeout", "close_timeout", "max_queue"}
    if not required.issubset(inspect.signature(connect).parameters):
        raise RuntimeError("Existing websockets sync client lacks the required API; run the explicit dependency installer")
    if not callable(websockets.connect) or not callable(serialization.load_pem_private_key):
        raise RuntimeError("Required market-data dependency API is unavailable")
    # Resolve the signing primitives offline without loading any operator key.
    if not all((hashes.SHA256, padding.PSS, padding.MGF1, Ed25519PrivateKey, RSAPrivateKey)):
        raise RuntimeError("Required signing primitives are unavailable")
    return {name: importlib.metadata.version(name) for name in sorted(THIRD_PARTY_IMPORTS)}


def check_loaded_core_modules() -> None:
    allowed = {module_name(name) for name in CORE_FILES}
    forbidden = [name for name in sys.modules if name.startswith("strategy_core.") and name not in allowed]
    if forbidden:
        raise ValueError("Unpackaged or legacy strategy module was imported: " + ", ".join(sorted(forbidden)))


def iter_tests(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from iter_tests(test)
        else:
            yield test


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true", help="Validate package, dependencies and imports; do not run tests")
    parser.add_argument("--require-manifest", action="store_true", help="Require and verify an extracted delivery manifest")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--workers", type=int, default=1,
                        help="Run isolated test modules with this many subprocess workers")
    args = parser.parse_args(argv)
    if args.workers < 1 or args.workers > 8:
        parser.error("--workers must be between 1 and 8")
    root = Path(__file__).resolve().parent
    try:
        if sys.version_info < (3, 10):
            raise RuntimeError("Python 3.10 or newer is required; validation targets Python 3.12 and 3.14")
        audit_package_files(root)
        has_manifest = verify_manifest(root, required=args.require_manifest)
        frozen_count = verify_frozen_source(root)
        versions = check_dependencies()
        # Imports only: constructors/start functions are not called here.
        for relative in CORE_FILES:
            importlib.import_module(module_name(relative))
        importlib.import_module("TOOL_RACK_PAPER")
        importlib.import_module("TOOL_RACK_EXPORT")
        check_loaded_core_modules()
        print("Tool Rack PAPER | offline package and execution checks", flush=True)
        print(f"Release: {RELEASE_ID} | Nautilus included | recommended 45-minute recorded PAPER run, then normal held-position drain", flush=True)
        print(f"Python {sys.version.split()[0]} | " + " | ".join(f"{name} {version}" for name, version in versions.items()), flush=True)
        print(f"Strict whitelist: {len(PACKAGE_FILES)} files; bundle manifest: {'verified' if has_manifest else 'source checkout'}", flush=True)
        print(f"Sealed release source: {frozen_count}/{frozen_count} files verified; {len(APPROVED_CHANGED_CORE_FILES)} approved changed files, {len(APPROVED_ADDED_CORE_FILES)} added helper; historical A/B/C, PID19996, PID4596, PID17588, PID15184 and PID4824 identity preserved.", flush=True)
        different = [name for name, version in versions.items() if version != INSTALLER_VERSIONS[name]]
        if different:
            print("Existing dependency APIs passed; versions differ from installer pins: " + ", ".join(different), flush=True)
        if args.preflight_only:
            print("PREFLIGHT PASSED. No feed, credentials, orders or test run was started.", flush=True)
            return 0
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for module in TEST_MODULES:
            tests = loader.loadTestsFromName(module)
            if tests.countTestCases() == 0:
                raise RuntimeError("Mandatory test module is empty: " + module)
            suite.addTests(tests)
        methods = {test.id().rsplit(".", 1)[-1] for test in iter_tests(suite)}
        missing = MANDATORY_TEST_METHODS - methods
        if missing:
            raise RuntimeError("Real PAPER execution tests are missing: " + ", ".join(sorted(missing)))
        total_tests = suite.countTestCases()
        print(f"Running {total_tests} tests in {len(TEST_MODULES)} isolated modules.", flush=True)
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONUTF8"] = "1"
        module_counts = [(index, module, loader.loadTestsFromName(module).countTestCases())
                         for index, module in enumerate(TEST_MODULES, 1)]

        def run_module(item):
            index, module, count = item
            command = [sys.executable, "-B", "-m", "unittest"]
            if not args.verbose:
                command.append("-q")
            command.append(module)
            try:
                checked = subprocess.run(command, cwd=root, env=environment, text=True,
                    encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    timeout=180, check=False)
                return index, module, count, checked.returncode, checked.stdout
            except subprocess.TimeoutExpired as exc:
                output = exc.stdout if isinstance(exc.stdout, str) else ""
                return index, module, count, 124, output + "\nMODULE TIMEOUT AFTER 180 SECONDS"

        completed_tests = 0
        completed_modules = 0
        if args.workers == 1:
            results = (run_module(item) for item in module_counts)
            for index, module, count, returncode, output in results:
                if returncode != 0:
                    print(f"CHECK FAILED in {module} ({index}/{len(TEST_MODULES)}).", flush=True)
                    print(output, flush=True)
                    return 1
                completed_tests += count
                completed_modules += 1
                if args.verbose or completed_modules % 10 == 0 or completed_modules == len(TEST_MODULES):
                    print(f"  passed {completed_modules}/{len(TEST_MODULES)} modules · {completed_tests}/{total_tests} tests", flush=True)
        else:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {executor.submit(run_module, item): item for item in module_counts}
                for future in as_completed(futures):
                    index, module, count, returncode, output = future.result()
                    if returncode != 0:
                        for pending in futures:
                            pending.cancel()
                        print(f"CHECK FAILED in {module} ({index}/{len(TEST_MODULES)}).", flush=True)
                        print(output, flush=True)
                        return 1
                    completed_tests += count
                    completed_modules += 1
                    if args.verbose or completed_modules % 10 == 0 or completed_modules == len(TEST_MODULES):
                        print(f"  passed {completed_modules}/{len(TEST_MODULES)} modules · {completed_tests}/{total_tests} tests", flush=True)
        check_loaded_core_modules()
        with tempfile.TemporaryDirectory(prefix="tachyos_mountain_construct_") as tmp:
            construct = subprocess.run(
                [sys.executable, "-B", "CONSTRUCT_MOUNTAIN_ONLY.py", "--output", tmp],
                cwd=root, env=environment, text=True, encoding="utf-8",
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
            if construct.returncode != 0:
                print("CHECK FAILED in Mountain-only Construct.", flush=True)
                print(construct.stdout, flush=True)
                return 1
            report = json.loads((Path(tmp) / "SUMMARY.json").read_text(encoding="utf-8"))
            if report.get("failed") or report.get("passed") != report.get("total"):
                raise RuntimeError("Mountain-only Construct did not pass every current control")
            print(f"Mountain-only Construct: {report['passed']}/{report['total']} plotted controls passed.", flush=True)
        authority = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_EMA9_AUTHORITY.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        if authority.returncode != 0:
            print("CHECK FAILED in EMA9 Authority Construct.", flush=True)
            print(authority.stdout, flush=True)
            return 1
        print(authority.stdout.strip(), flush=True)
        advisory = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_TOOL_ADVISORY_AUTHORITY.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        if advisory.returncode != 0:
            print("CHECK FAILED in Tool Advisory Authority Construct.", flush=True)
            print(advisory.stdout, flush=True)
            return 1
        print(advisory.stdout.strip(), flush=True)
        positive = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID13560_POSITIVE_CONTROLS.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        if positive.returncode != 0:
            print("CHECK FAILED in PID13560 Positive Control Construct.", flush=True)
            print(positive.stdout, flush=True)
            return 1
        print(positive.stdout.strip(), flush=True)
        sprout = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID7812_SPROUT_PROMOTION.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        if sprout.returncode != 0:
            print("CHECK FAILED in PID7812 Sprout Promotion Construct.", flush=True)
            print(sprout.stdout, flush=True)
            return 1
        print(sprout.stdout.strip(), flush=True)
        pid14312 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID14312_ARC_SELECTION_CUSTODY.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        if pid14312.returncode != 0:
            print("CHECK FAILED in PID14312 Arc Selection / Custody Construct.", flush=True)
            print(pid14312.stdout, flush=True)
            return 1
        print(pid14312.stdout.strip(), flush=True)
        pid7412 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID7412_DIRECTIONAL_TRANSFER.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        if pid7412.returncode != 0:
            print("CHECK FAILED in PID7412 Directional Transfer / Quote Echo Construct.", flush=True)
            print(pid7412.stdout, flush=True)
            return 1
        print(pid7412.stdout.strip(), flush=True)
        pid8552 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID8552_RAIL_WICK_CUSTODY.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        if pid8552.returncode != 0:
            print("CHECK FAILED in PID8552 Rail Wick / Whole-Lot Construct.", flush=True)
            print(pid8552.stdout, flush=True)
            return 1
        print(pid8552.stdout.strip(), flush=True)
        pid17744 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID17744_RETURN_BRIEFINGS.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        if pid17744.returncode != 0:
            print("CHECK FAILED in PID17744 Entry and Navigator Construct.", flush=True)
            print(pid17744.stdout, flush=True)
            return 1
        print(pid17744.stdout.strip(), flush=True)
        dual = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_DUAL_LANE_MAIN_TACTICAL.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        if dual.returncode != 0 or "DUAL LANE CONSTRUCT PASS: 14/14" not in dual.stdout:
            print("CHECK FAILED in dual-lane independent MAIN / TACTICAL Construct.", flush=True)
            print(dual.stdout, flush=True)
            return 1
        print(dual.stdout.strip(), flush=True)
        inherited = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID15740_INHERITED_UP_RAIL.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False)
        if inherited.returncode != 0 or "PID15740 CONSTRUCT PASS: 8/8" not in inherited.stdout:
            print("CHECK FAILED in PID15740 Inherited UP Rail Construct.", flush=True)
            print(inherited.stdout, flush=True)
            return 1
        print(inherited.stdout.strip(), flush=True)
        pid17224 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID17224_APPROVED_CORRECTIONS.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60, check=False)
        if pid17224.returncode != 0 or "PID17224 APPROVED CORRECTIONS CONSTRUCT PASS" not in pid17224.stdout:
            print("CHECK FAILED in PID17224 approved corrections Construct.", flush=True)
            print(pid17224.stdout, flush=True)
            return 1
        print(pid17224.stdout.strip(), flush=True)
        pid19996 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID19996_RAIL_VALUE.py"],
            cwd=root, env=environment, text=True, encoding="utf-8", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=180, check=False)
        print(pid19996.stdout, end="", flush=True)
        if pid19996.returncode != 0 or "PID19996 RAIL VALUE CONSTRUCT PASS" not in pid19996.stdout:
            print("CHECK FAILED in PID19996 rail value Construct.", flush=True)
            return 1
        pid4596 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID4596_RUNTIME_REPAIR.py"],
            cwd=root, env=environment, text=True, encoding="utf-8", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=180, check=False)
        print(pid4596.stdout, end="", flush=True)
        if pid4596.returncode != 0 or "PID4596 RUNTIME REPAIR CONSTRUCT PASS" not in pid4596.stdout:
            print("CHECK FAILED in PID4596 runtime repair Construct.", flush=True)
            return 1
        pid17588 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID17588_LATE_SCOUT.py"],
            cwd=root, env=environment, text=True, encoding="utf-8", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=180, check=False)
        print(pid17588.stdout, end="", flush=True)
        if pid17588.returncode != 0 or "PID17588 LATE SCOUT CONSTRUCT PASS" not in pid17588.stdout:
            print("CHECK FAILED in PID17588 late-scout Construct.", flush=True)
            return 1
        pid15184 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID15184_CURRENT_PARENT_CALIBRATION.py"],
            cwd=root, env=environment, text=True, encoding="utf-8", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=180, check=False)
        print(pid15184.stdout, end="", flush=True)
        if pid15184.returncode != 0 or "PID15184 CURRENT PARENT CALIBRATION CONSTRUCT PASS" not in pid15184.stdout:
            print("CHECK FAILED in PID15184 current-parent calibration Construct.", flush=True)
            return 1
        recovery4824 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID4824_RECOVERY_IDENTITY.py"],
            cwd=root, env=environment, text=True, encoding="utf-8", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=180, check=False)
        print(recovery4824.stdout, end="", flush=True)
        if recovery4824.returncode != 0 or "PID4824 RECOVERY IDENTITY CONSTRUCT PASS" not in recovery4824.stdout:
            print("CHECK FAILED in PID4824 recovery identity Construct.", flush=True)
            return 1
        floor4824 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID4824_FLOOR_AUTHORITY.py"],
            cwd=root, env=environment, text=True, encoding="utf-8", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=180, check=False)
        print(floor4824.stdout, end="", flush=True)
        if floor4824.returncode != 0 or "PID4824 FLOOR AUTHORITY CONSTRUCT PASS" not in floor4824.stdout:
            print("CHECK FAILED in PID4824 floor authority Construct.", flush=True)
            return 1
        sprout10656 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID10656_SPROUT_HEIST.py"],
            cwd=root, text=True, encoding="utf-8", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=180, check=False)
        print(sprout10656.stdout, end="", flush=True)
        if sprout10656.returncode != 0 or "PID10656 SPROUT HEIST CONSTRUCT PASS" not in sprout10656.stdout:
            print("CHECK FAILED in PID10656 fresh-sprout Heist Construct.", flush=True)
            return 1
        patterns10656 = subprocess.run(
            [sys.executable, "-B", "RUN_PID10656_LOOKING_GLASS_CONSTRUCT.py"],
            cwd=root, text=True, encoding="utf-8", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=180, check=False)
        print(patterns10656.stdout, end="", flush=True)
        if patterns10656.returncode != 0 or "PID10656_LOOKING_GLASS_CONSTRUCT_PASS" not in patterns10656.stdout:
            print("CHECK FAILED in PID10656 Looking Glass Construct.", flush=True)
            return 1
        pid14048 = subprocess.run(
            [sys.executable, "-B", "CONSTRUCT_PID14048_QUOTE_VALUE_STALL.py"],
            cwd=root, env=environment, text=True, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45, check=False)
        print(pid14048.stdout.strip(), flush=True)
        if pid14048.returncode or "PID14048 QUOTE VALUE AND STALL CONSTRUCT PASS" not in pid14048.stdout:
            print("CHECK FAILED in PID14048 chronological Quote/Exit Construct.", flush=True)
            return 1
        print(f"CHECK PASSED: {completed_tests} current tests + Mountain-only + EMA9 Authority + Tool Advisory Authority + PID13560 Positive Control + PID7812 Sprout Promotion + PID14312 Arc Selection/Custody + PID7412 Directional Transfer/Quote Echo + PID8552 Rail Wick Custody + PID17744 Return/Navigator + Dual Lane Main/Tactical + PID15740 Inherited UP Rail + PID17224 Approved Corrections + PID19996 Rail Value + PID4596 Runtime Repair + PID17588 Late Scout + PID15184 Current Parent Calibration + PID4824 Recovery Identity + PID4824 Floor Authority + PID10656 Fresh Sprout Heist + PID10656 Looking Glass Constructs. No live market session or venue order was started.", flush=True)
        return 0
    except Exception as exc:
        print(f"CHECK FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        print("Extract the whole PAPER bundle. For missing/incompatible packages, run 03_INSTALL_TOOL_RACK_DEPENDENCIES.cmd explicitly.", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
