"""Mountain policy controls with explicit synthetic and recorded input scopes.

``snap``/``m`` author numeric source-current unit premises. A requested true
terminal includes comparative maturity and a measured retreat; a boolean label
alone is not an admission fixture. Archived PID8868 packets remain unchanged.
PID23072 reconstructs detector evidence from a causal physical-row prefix and
recorded contract values; it is not a native-book execution or P&L replay.
"""
from __future__ import annotations

import bisect
import gzip
import json
import tempfile
import unittest
from copy import deepcopy
from dataclasses import asdict, replace
from types import SimpleNamespace
from pathlib import Path

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import physical_entry_candidates
from strategy_core.detectors.mountain_geometry import detect_mountain_geometry
from strategy_core.paper_execution import FloorPolicy, PaperBook, PaperExecutioner, PriceLevel
from strategy_core.physical_source import ema9_ema30_cross_context
from strategy_core.tool_rack import ToolRackController
from strategy_core.tools.management import floor_policy
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from tests.tool_rack.test_opportunity_first_commander import parent_snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "pid8868_mountain_gate.json"
PID23072_CONTROL_FIXTURE = Path(__file__).parent / "fixtures" / "pid23072_entry_controls.json"
PID23072_PHYSICAL_FIXTURE = Path(__file__).parent / "fixtures" / "pid23072_physical_geometry.jsonl.gz"
_DEFAULT_BID = object()


def snap(*, yes=.5, no=.5, age=300, t=1000.0, ticker="KX-T", close_ts=1900.0,
         mountain=None, tp=None, meta=None, yes_bid=_DEFAULT_BID, no_bid=_DEFAULT_BID):
    """Author a coherent synthetic source packet; never enrich archived rows."""
    mountain = deepcopy(mountain or {})
    owner = mountain.get("owner_side")
    sign = 1.0 if owner != "NO" else -1.0
    direction = "UP" if sign > 0 else "DOWN"
    terminal = mountain.get("terminal_evidence_qualified") is True
    arc_age = float(mountain.get("diagnostics",{}).get("current_age_s") or 120.)
    # Use the shared numeric opportunity premise, then explicitly author this
    # test's parent/child direction, terminal retreat and contract economics.
    base = parent_snapshot(t=t, price=76000., age=age, ask=yes,
                           child="A", direction=direction, child_start=t-arc_age)
    g = deepcopy(base.metadata["current_geometry"])
    motion_sign = -sign if terminal else sign
    g.update(parent_direction=direction, ema9=76000.-sign*5.,
             ema30=76000.-sign*13., ema_gap=sign*8.,
             btc_change6=motion_sign*6., btc_change9=motion_sign*9.,
             btc_change30=motion_sign*12., btc_change60=motion_sign*20.,
             ema9_change6=motion_sign*1.2, ema9_change30=motion_sign*2.4,
             ema9_change60=motion_sign*4., range60=30., range180=60.)
    for horizon in ("30","60"):
        measurement = mountain.get("current_motion",{}).get(horizon,{})
        if "owner_price_rate_btc_s" in measurement:
            g["btc_change"+horizon] = sign*measurement["owner_price_rate_btc_s"]*int(horizon)
        if "owner_ema9_rate_btc_s" in measurement:
            g["ema9_change"+horizon] = sign*measurement["owner_ema9_rate_btc_s"]*int(horizon)
    overrides = deepcopy(meta or {})
    supplied_geometry = overrides.pop("current_geometry",{})
    g.update(supplied_geometry)
    if "btc_price" in supplied_geometry and "ema9" not in supplied_geometry:
        g["ema9"] = g["btc_price"]-sign*5.
    if "ema30" not in supplied_geometry:
        g["ema30"] = g["ema9"]-g["ema_gap"]
    mountain.setdefault("source_ms",g["epoch_ms"])
    mountain.setdefault("current_btc",g["btc_price"])
    mountain.setdefault("current_ema9",g["ema9"])
    mountain.setdefault("current_ema30",g["ema30"])
    mountain.setdefault("retreat_threshold",3.)
    mountain.setdefault("retreat_dollars",6. if terminal else 0.)
    mountain.setdefault("owner_extreme_btc",g["btc_price"]+sign*mountain["retreat_dollars"])
    mountain.setdefault("edge_extreme_ms",(t-20.)*1000.)
    mountain.setdefault("stall",terminal)
    mountain.setdefault("spent_edge",False)
    mountain.setdefault("diagnostics",{}).setdefault("mature_by_comparison",terminal)
    mountain.setdefault("primary_collection_evidence",{
        "comparable_current_leg_mature":terminal,"source_ms":g["epoch_ms"],
        "basis":"SYNTHETIC_COMPARABLE_LEG_MATURITY",
        "observed_duration_s":arc_age,"reference_duration_s":90.,
        "observed_amplitude_btc":20.,"reference_amplitude_btc":15.,
    })
    # Bind authored motion to the same source. Individual tests still control
    # its direction and can demonstrate a still-expanding false terminal.
    for horizon in ("30","60"):
        measurement = mountain.setdefault("current_motion",{}).setdefault(horizon,{
            "owner_price_rate_btc_s":sign*g["btc_change"+horizon]/int(horizon),
            "owner_ema9_rate_btc_s":sign*g["ema9_change"+horizon]/int(horizon)})
        measurement.setdefault("source_ms",g["epoch_ms"])
        measurement.setdefault("covered",True)
        measurement.setdefault("source_continuous",True)
    target_context = deepcopy(tp or {})
    target_context.setdefault("remaining_seconds",900.-age)
    observed = (target_context.get("observed_target_side")
                or target_context.get("contract_ownership_side") or owner or "YES")
    required = float(target_context.get("required_move_to_target_btc",2.))
    if target_context.get("target_between_ema9_ema30") is True:
        target_context.setdefault("target",(g["ema9"]+g["ema30"])/2.)
    else:
        target_context.setdefault("target",g["btc_price"]-(required if observed=="YES" else -required))
    target_context.setdefault("observed_target_side","YES" if g["btc_price"]>=target_context["target"] else "NO")
    target_context.setdefault("required_move_to_target_btc",abs(g["btc_price"]-target_context["target"]))
    md={"physical_current":True,"geometry_last_epoch_ms":t*1000.0,"geometry_continuity_generation":1,
        "current_geometry":g,"mountain":mountain,"tp_geometry":target_context,
        "commander_strategy":{"owned_territory":"ALTERNATING_MOUNTAIN","owned_side":owner,"active_tool":"ALTERNATING_MOUNTAIN"}}
    md.update(overrides)
    if yes_bid is _DEFAULT_BID: yes_bid=max(.001,yes-.01)
    if no_bid is _DEFAULT_BID: no_bid=max(.001,no-.01)
    return MarketSnapshot(now_ts=t,ticker=ticker,contract_age_s=age,yes_ask=yes,no_ask=no,
                          yes_bid=yes_bid,no_bid=no_bid,yes_sell_allowed=yes_bid is not None,
                          no_sell_allowed=no_bid is not None,metadata=md)


def m(side="YES",terminal=False,qualified=True,age=120,rolling=False,edge="E",strong=False,
      mature=None,window=None,parent_age=None,parent_amp=20.0,parent_terminal=False):
    if mature is None: mature=terminal
    if window is None: window=terminal
    return {"qualified_alternating_mountain":qualified,"owner_side":side,"current_arc_id":"A",
            "terminal_evidence_qualified":terminal,"mature_edge":mature,"edge_window_active":window,
            "strong_active_release":strong,"edge_id":edge,
            "parent_structure":{"parent_id":"P","parent_side":side,"parent_age_s":parent_age,
                "parent_amplitude":parent_amp,"parent_terminal_ready":parent_terminal,
                "slow_rolling_parent":rolling,"extended_parent":rolling,"child_arc_count":3 if rolling else 1},
            "diagnostics":{"current_age_s":age}}


def synthetic_terminal_snapshot(*, side=Side.NO, ask=.19, t=1000., age=300.,
                                ticker="SYNTHETIC_MOUNTAIN", edge=None):
    """Source-rich numeric unit premise, never an archived market observation.

    ``side`` is the intended return side. The outgoing 120-second arc has
    reached its stated comparable scale, retreated six BTC dollars from its
    observed extreme, and currently moves toward an already-owned target.
    Three completed synthetic return legs supply independent runway capacity.
    Call the actual Commander to obtain an admitted intent/decision.
    """
    side = Side(side)
    owner = "YES" if side is Side.NO else "NO"
    mountain = m(owner,True,edge=edge or f"A:{int((t-20.)*1000.)}")
    legs = [{"arc_id":f"SYNTHETIC_RETURN_{i}","btc_amplitude_btc":amplitude,
             "duration_s":duration,"average_btc_speed_btc_s":amplitude/duration}
            for i,(amplitude,duration) in enumerate(((40.,160.),(50.,200.),(60.,240.)),1)]
    mountain["return_leg_reference"]={
        "basis":"SYNTHETIC_COMPLETED_RETURN_LEGS","count":3,"legs":legs,
        "median_amplitude_btc":50.,"median_speed_btc_s":.25,
        "max_amplitude_btc":60.,"max_speed_btc_s":.25}
    yes = ask if side is Side.YES else 1.-ask+.01
    no = ask if side is Side.NO else 1.-ask+.01
    return snap(yes=yes,no=no,t=t,age=age,ticker=ticker,mountain=mountain,
                tp={"target_between_ema9_ema30":False,
                    "observed_target_side":side.value,"required_move_to_target_btc":30.})


def fixture_case(name: str) -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"][name]


def fixture_snapshot(name: str) -> MarketSnapshot:
    c=fixture_case(name)
    return MarketSnapshot(now_ts=c["now_ts"],ticker=c["ticker"],contract_age_s=c["contract_age_s"],
        yes_ask=c["yes_ask"],no_ask=c["no_ask"],quote_current=c["quote_current"],
        depth_available=c["depth_available"],metadata=c["metadata"],yes_bid=c["yes_bid"],no_bid=c["no_bid"],
        entry_allowed=c["entry_allowed"],yes_sell_allowed=c["yes_sell_allowed"],no_sell_allowed=c["no_sell_allowed"])


def fixture_intents(name: str) -> list[ToolIntent]:
    rows=[]
    for raw in fixture_case(name).get("adviser_intents") or []:
        rows.append(ToolIntent(tool=raw["tool"],territory_id=raw["territory_id"],lane=Lane(raw["lane"]),
            side=Side(raw["side"]) if raw.get("side") else None,action=Action(raw["action"]),
            opportunity_id=raw.get("opportunity_id"),max_price=raw.get("max_price"),size_tier=raw.get("size_tier"),
            reason=raw["reason"],source_time=raw["source_time"],expires_when=raw.get("expires_when"),
            metadata=raw.get("metadata") or {}))
    return rows


class MountainOnlyResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pid23072_controls = json.loads(PID23072_CONTROL_FIXTURE.read_text(encoding="utf-8"))["controls"]
        with gzip.open(PID23072_PHYSICAL_FIXTURE, "rt", encoding="utf-8") as handle:
            cls.pid23072_physical = [json.loads(line) for line in handle if line.strip()]
        cls.pid23072_epochs = [float(row["epoch_ms"]) for row in cls.pid23072_physical]

    def _pid23072_replay(self, control: dict):
        stop = bisect.bisect_right(self.pid23072_epochs, float(control["source_epoch_ms"]))
        self.assertGreater(stop, 0)
        rows = self.pid23072_physical[:stop]
        current = rows[-1]
        mountain = detect_mountain_geometry(rows).tool_metadata()
        cross = ema9_ema30_cross_context(rows)
        btc = float(current["btc_price"]); target = float(control["target"])
        ema9 = float(current["ema9"]); ema30 = float(current["ema30"])
        tp = {
            "target": target,
            "contract_ownership": control["old_contract_ownership"],
            "contract_ownership_side": control["old_contract_ownership_side"],
            "target_between_ema9_ema30": min(ema9, ema30) <= target <= max(ema9, ema30),
            "required_move_to_target_btc": abs(btc - target),
            "observed_target_side": "YES" if btc >= target else "NO",
            "remaining_seconds": float(control["market_close_ts"]) - float(control["entry_time"]),
            "comparable_parent_amplitude_btc": (mountain.get("parent_structure") or {}).get("parent_amplitude"),
        }
        entry_side = Side(control["side"]); entry_price = float(control["entry_price"])
        yes_ask = entry_price if entry_side is Side.YES else 1.0 - entry_price
        no_ask = entry_price if entry_side is Side.NO else 1.0 - entry_price
        owner = mountain.get("owner_side")
        snapshot = MarketSnapshot(
            now_ts=float(control["entry_time"]), ticker=control["ticker"],
            contract_age_s=float(control["entry_time"]) - float(control["market_open_ts"]),
            yes_ask=yes_ask, no_ask=no_ask, yes_bid=max(.001, yes_ask-.01), no_bid=max(.001, no_ask-.01),
            metadata={
                "physical_current": True, "geometry_last_epoch_ms": float(current["epoch_ms"]),
                "geometry_continuity_generation": 1, "mountain": mountain, "tp_geometry": tp,
                "ema9_ema30_cross_context": cross, "current_geometry": current,
                "commander_strategy": {"owned_territory":"ALTERNATING_MOUNTAIN",
                                       "owned_side":owner,"active_tool":"ALTERNATING_MOUNTAIN"},
            },
        )
        commander = OneCommander(); candidates = commander.physical_entry_candidates(snapshot)
        decision = commander.decide(list(candidates), snapshot)
        return snapshot, mountain, cross, candidates, decision

    def decide(self,s):
        c=OneCommander(); cs=c.physical_entry_candidates(s); return c,cs,c.decide(list(cs),s)

    def test_true_top_under_20_enters_no(self):
        _,_,d=self.decide(snap(yes=.81,no=.19,mountain=m("YES",True),tp={"target_between_ema9_ema30":False}))
        self.assertIs(d.action,Action.ENTER); self.assertIs(d.intent.side,Side.NO)

    def test_true_top_at_20_waits(self):
        _,cs,d=self.decide(snap(yes=.80,no=.20,mountain=m("YES",True),tp={"target_between_ema9_ema30":False}))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_stale_terminal_latch_without_current_window_waits(self):
        _,cs,d=self.decide(snap(yes=.81,no=.19,mountain=m("YES",True,mature=False,window=False),tp={"target_between_ema9_ema30":False}))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_pid8868_partial_top_preserves_factory_species_but_shared_admission_waits(self):
        s=fixture_snapshot("current_terminal_top")
        self.assertFalse(s.metadata["mountain"]["qualified_alternating_mountain"])
        self.assertEqual(s.metadata["commander_strategy"]["owned_territory"],"ALTERNATING_MOUNTAIN")
        c=OneCommander(); primary=physical_entry_candidates(s)
        self.assertEqual(len(primary),1); self.assertIs(primary[0].side,Side.NO)
        self.assertEqual(primary[0].metadata["commander_candidate_family"],"MOUNTAIN_EDGE")
        self.assertNotIn("epoch_ms",s.metadata["current_geometry"])
        self.assertEqual(c.physical_entry_candidates(s),())
        self.assertEqual(c._entry_strategy_denial(primary[0],s),"OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED")
        d=c.decide_entry(list(primary)+fixture_intents("current_terminal_top"),s,{})
        self.assertIs(d.action,Action.WAIT)

    def test_pid8868_stale_cheap_hover_stays_blocked(self):
        s=fixture_snapshot("stale_cheap_hover")
        c=OneCommander(); primary=c.physical_entry_candidates(s)
        self.assertEqual(primary,())
        d=c.decide_entry(fixture_intents("stale_cheap_hover"),s,{})
        self.assertIs(d.action,Action.WAIT)
        self.assertEqual(d.reason,"COMMANDER_LEGACY_MOUNTAIN_SPECIALIST_ENTRY_PAUSED_USE_PRIMARY")

    def test_pid8868_partial_rollover_preserves_factory_species_but_shared_admission_waits(self):
        s=fixture_snapshot("rollover_target_reachable")
        self.assertEqual(s.metadata["tp_geometry"]["contract_ownership"],"UNRESOLVED")
        c=OneCommander(); primary=physical_entry_candidates(s)
        self.assertEqual(len(primary),1); self.assertIs(primary[0].side,Side.NO)
        self.assertEqual(primary[0].metadata["commander_candidate_family"],"MOUNTAIN_CONTRACT_LEG")
        self.assertEqual(primary[0].reason,"COMMANDER_MOUNTAIN_ROLLOVER_TARGET_REACHABLE")
        self.assertNotIn("epoch_ms",s.metadata["current_geometry"])
        self.assertEqual(c.physical_entry_candidates(s),())
        self.assertEqual(c._entry_strategy_denial(primary[0],s),"OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED")
        d=c.decide_entry(list(primary)+fixture_intents("rollover_target_reachable"),s,{})
        self.assertIs(d.action,Action.WAIT)
        self.assertLess(s.no_ask,.40)

    def test_rollover_contract_leg_explicit_tp_under_40_enters(self):
        t={"contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"NO",
           "target_between_ema9_ema30":False,"required_move_to_target_btc":2.0,
           "comparable_parent_amplitude_btc":18.0,"observed_target_side":"YES"}
        mm=m("NO",False,age=500,parent_age=500)
        mm["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":-.10,"owner_ema9_rate_btc_s":.04},
                              "60":{"covered":True,"owner_price_rate_btc_s":-.06,"owner_ema9_rate_btc_s":.03}}
        mm["slowdown"]={"owner_price_retreat_observed":True}; mm["diagnostics"]["phase"]="BUILDING"
        s=snap(yes=.61,no=.39,age=60,mountain=mm,tp=t,
               meta={"current_geometry":{"ema_gap":-8.0,"range60":30.0,"arc_phase":"BUILDING"},
                     "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"SPROUT",
                         "age_seconds_since_observed_cross":300.0,"current_side":"NO",
                         "current_abs_gap_btc":8.0,"gap_expanding_6s":True}}})
        _,_,d=self.decide(s)
        self.assertIs(d.action,Action.ENTER); self.assertIs(d.intent.side,Side.NO)

    def test_inherited_young_leg_first_minute_allows_55c_and_uses_25_tier(self):
        t={"contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"NO",
           "target_between_ema9_ema30":False,"required_move_to_target_btc":2.0,
           "comparable_parent_amplitude_btc":18.0,"observed_target_side":"YES"}
        mm=m("NO",False,age=500,parent_age=500)
        mm["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":.10,"owner_ema9_rate_btc_s":.04},
                              "60":{"covered":True,"owner_price_rate_btc_s":.06,"owner_ema9_rate_btc_s":.03}}
        mm["slowdown"]={"owner_price_retreat_observed":False}; mm["diagnostics"]["phase"]="BUILDING"
        s=snap(yes=.45,no=.55,age=20,mountain=mm,tp=t,
               meta={"current_geometry":{"ema_gap":-8.0,"range60":30.0,"arc_phase":"BUILDING"},
                     "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"SPROUT",
                         "age_seconds_since_observed_cross":300.0,"current_side":"NO",
                         "current_abs_gap_btc":8.0,"gap_expanding_6s":True}}})
        c=OneCommander(); cs=c.physical_entry_candidates(s)
        self.assertEqual(len(cs),1); intent=cs[0]
        self.assertEqual(intent.reason,"COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION")
        self.assertIs(intent.side,Side.NO); self.assertEqual(intent.max_price,.55)
        self.assertEqual(intent.size_tier,25.0)
        d=c.decide_entry(list(cs),s,{})
        self.assertIs(d.action,Action.ENTER); self.assertIs(d.intent.side,Side.NO)

    def test_inherited_young_leg_above_55_waits(self):
        t={"contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"NO",
           "target_between_ema9_ema30":False,"required_move_to_target_btc":2.0,
           "comparable_parent_amplitude_btc":18.0,"observed_target_side":"YES"}
        mm=m("NO",False,age=500,parent_age=500)
        mm["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":.10,"owner_ema9_rate_btc_s":.04},
                              "60":{"covered":True,"owner_price_rate_btc_s":.06,"owner_ema9_rate_btc_s":.03}}
        mm["slowdown"]={"owner_price_retreat_observed":False}; mm["diagnostics"]["phase"]="BUILDING"
        s=snap(yes=.44,no=.56,age=20,mountain=mm,tp=t,
               meta={"current_geometry":{"ema_gap":-8.0,"range60":30.0,"arc_phase":"BUILDING"},
                     "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"SPROUT",
                         "age_seconds_since_observed_cross":300.0,"current_side":"NO",
                         "current_abs_gap_btc":8.0,"gap_expanding_6s":True}}})
        self.assertEqual(OneCommander().physical_entry_candidates(s),())

    def test_extended_current_armed_top_sub20_enters_return_even_without_extreme_timestamp(self):
        mm=m("YES",False,age=700,parent_age=700,rolling=True,mature=True,window=True)
        # PID8552: an aged/cheap top by itself is not a return briefing;
        # this test has a genuine terminal stall, so anticipation remains legal.
        mm["terminal_evidence_qualified"]=True
        mm["stall"]=True
        mm["edge_id"]="TOP8C"
        mm.pop("edge_extreme_ms",None)
        s=snap(yes=.92,no=.08,age=500,mountain=mm,tp={"target_between_ema9_ema30":False})
        # This control intentionally omits the extreme timestamp after the
        # generic synthetic builder. Current compared terminal/window evidence
        # is the premise; do not silently add back the field being tested.
        md=deepcopy(s.metadata); md["mountain"].pop("edge_extreme_ms",None)
        s=replace(s,metadata=md)
        self.assertNotIn("edge_extreme_ms",s.metadata["mountain"])
        c=OneCommander(); cs=c.physical_entry_candidates(s)
        self.assertEqual(len(cs),1); self.assertIs(cs[0].side,Side.NO)
        self.assertEqual(cs[0].reason,"COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN")
        d=c.decide_entry(list(cs),s,{})
        self.assertIs(d.action,Action.ENTER); self.assertIs(d.intent.side,Side.NO)

    def test_same_leg_after_four_minute_rollover_window_waits(self):
        t={"contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"NO",
           "target_between_ema9_ema30":False,"required_move_to_target_btc":2.0,
           "comparable_parent_amplitude_btc":18.0,"observed_target_side":"YES"}
        _,cs,d=self.decide(snap(yes=.65,no=.35,age=241,mountain=m("NO",False,age=500,parent_age=500),tp=t))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_bounce_favored_true_edge_under_40_enters(self):
        t={"contract_ownership":"BOUNCE_FAVORED","contract_ownership_side":"NO","target_between_ema9_ema30":False}
        _,_,d=self.decide(snap(yes=.61,no=.39,mountain=m("YES",True),tp=t))
        self.assertIs(d.action,Action.ENTER); self.assertIs(d.intent.side,Side.NO)

    def test_late_top_far_tp_without_proven_return_runway_waits(self):
        mm=m("YES",True)
        t={"target_between_ema9_ema30":False,"remaining_seconds":250.0,
           "observed_target_side":"YES","required_move_to_target_btc":60.0}
        _,cs,d=self.decide(snap(yes=.90,no=.10,age=650,mountain=mm,tp=t))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_late_top_can_enter_only_when_recent_down_legs_can_reach_tp(self):
        mm=m("YES",True)
        mm["return_leg_reference"]={"count":3,"median_amplitude_btc":50.0,
            "median_duration_s":180.0,"median_speed_btc_s":50.0/180.0}
        t={"target_between_ema9_ema30":False,"remaining_seconds":250.0,
           "observed_target_side":"YES","required_move_to_target_btc":20.0}
        _,cs,d=self.decide(snap(yes=.90,no=.10,age=650,mountain=mm,tp=t))
        self.assertEqual(len(cs),1); self.assertIs(d.action,Action.ENTER); self.assertIs(d.intent.side,Side.NO)
        proof=d.intent.metadata["commander_physical_evidence"]["late_return_runway"]
        self.assertEqual(proof["basis"],"PROVEN_RETURN_LEG_CAN_REACH_TP")

    def test_late_top_far_tp_blocks_even_when_quote_is_extremely_cheap(self):
        mm=m("YES",True)
        mm["return_leg_reference"]={"count":4,"median_amplitude_btc":24.0,
            "median_duration_s":180.0,"median_speed_btc_s":24.0/180.0}
        t={"target_between_ema9_ema30":False,"remaining_seconds":220.0,
           "observed_target_side":"YES","required_move_to_target_btc":45.0}
        _,cs,d=self.decide(snap(yes=.995,no=.005,age=680,mountain=mm,tp=t))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_gap_lifecycle_sprout_developing_mature_rolling_is_descriptive(self):
        rows=[]
        for sec in range(0, 1910, 10):
            # First point is below the spine, then a continuously observed UP cross.
            e30=100.0
            e9=99.0 if sec == 0 else 101.0 + min(sec, 300)/300.0
            rows.append({"epoch_ms":sec*1000.0,"ema9":e9,"ema30":e30,
                         "connection_epoch":1,"arc_id":"A","arc_start_ms":10000.0})
        self.assertEqual(ema9_ema30_cross_context(rows[:31])["gap_lifecycle"]["stage"],"SPROUT")
        self.assertEqual(ema9_ema30_cross_context(rows[:61])["gap_lifecycle"]["stage"],"DEVELOPING")
        self.assertEqual(ema9_ema30_cross_context(rows[:101])["gap_lifecycle"]["stage"],"MATURE")
        self.assertEqual(ema9_ema30_cross_context(rows)["gap_lifecycle"]["stage"],"ROLLING")
        self.assertFalse(ema9_ema30_cross_context(rows)["gap_lifecycle"]["clock_has_trade_authority"])

    def test_sprout_gap_still_expanding_blocks_false_peak_like_trade8(self):
        mm=m("YES",True)
        mm["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":.62,"owner_ema9_rate_btc_s":.24},
                              "60":{"covered":True,"owner_price_rate_btc_s":.31,"owner_ema9_rate_btc_s":.12}}
        cross={"gap_lifecycle":{"stage":"SPROUT","age_seconds_since_observed_cross":210.0,
                                "current_side":"YES","gap_expanding_6s":True}}
        _,cs,d=self.decide(snap(yes=.85,no=.15,mountain=mm,tp={"target_between_ema9_ema30":False},
                                meta={"ema9_ema30_cross_context":cross}))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_sprout_gap_real_causal_turn_can_still_enter_like_trade1(self):
        mm=m("YES",True)
        mm["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":-.20,"owner_ema9_rate_btc_s":-.04},
                              "60":{"covered":True,"owner_price_rate_btc_s":-.08,"owner_ema9_rate_btc_s":.10}}
        cross={"gap_lifecycle":{"stage":"SPROUT","age_seconds_since_observed_cross":210.0,
                                "current_side":"YES","gap_expanding_6s":False}}
        _,cs,d=self.decide(snap(yes=.87,no=.13,mountain=mm,tp={"target_between_ema9_ema30":False},
                                meta={"ema9_ema30_cross_context":cross}))
        self.assertEqual(len(cs),1); self.assertIs(d.action,Action.ENTER); self.assertIs(d.intent.side,Side.NO)
        self.assertEqual(d.intent.metadata["commander_physical_evidence"]["sprout_reversal_proof"]["basis"],
                         "SPROUT_CAUSAL_TURN_PROVED")

    def test_mature_gap_does_not_get_sprout_veto(self):
        mm=m("YES",True)
        cross={"gap_lifecycle":{"stage":"MATURE","age_seconds_since_observed_cross":1100.0,
                                "current_side":"YES","gap_expanding_6s":False}}
        _,cs,d=self.decide(snap(yes=.85,no=.15,mountain=mm,tp={"target_between_ema9_ema30":False},
                                meta={"ema9_ema30_cross_context":cross}))
        self.assertEqual(len(cs),1); self.assertIs(d.action,Action.ENTER)

    def test_continuous_runway_blocks_quiet_regime_even_just_over_five_minutes(self):
        mm=m("YES",True)
        mm["return_leg_reference"]={"count":4,"median_amplitude_btc":40.0,"median_speed_btc_s":.18,
                                     "max_amplitude_btc":52.0,"max_speed_btc_s":.24}
        t={"target_between_ema9_ema30":False,"remaining_seconds":328.0,
           "observed_target_side":"YES","required_move_to_target_btc":68.0}
        _,cs,d=self.decide(snap(yes=.983,no=.017,age=572,mountain=mm,tp=t))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_continuous_runway_allows_late_large_swing_regime(self):
        mm=m("YES",True)
        mm["return_leg_reference"]={"count":4,"median_amplitude_btc":380.0,"median_speed_btc_s":1.7,
                                     "max_amplitude_btc":620.0,"max_speed_btc_s":3.0}
        t={"target_between_ema9_ema30":False,"remaining_seconds":240.0,
           "observed_target_side":"YES","required_move_to_target_btc":250.0}
        _,cs,d=self.decide(snap(yes=.90,no=.10,age=660,mountain=mm,tp=t))
        self.assertEqual(len(cs),1); self.assertIs(d.action,Action.ENTER); self.assertIs(d.intent.side,Side.NO)
        proof=d.intent.metadata["commander_physical_evidence"]["return_runway"]
        self.assertEqual(proof["basis"],"PROVEN_RETURN_LEG_CAN_REACH_TP")
        self.assertGreater(proof["proven_reachable_btc"],250.0)

    def test_rollover_spent_mature_gap_collapsed_to_spine_blocks_trade7_shape(self):
        mm=m("NO",False,age=388,parent_age=388)
        mm["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":-2.09/30.0,"owner_ema9_rate_btc_s":1.46/30.0},
                              "60":{"covered":True,"owner_price_rate_btc_s":-8.81/60.0,"owner_ema9_rate_btc_s":.12/60.0}}
        mm["slowdown"]={"owner_price_retreat_observed":True}; mm["diagnostics"]["phase"]="MATURE"
        t={"contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"NO",
           "target_between_ema9_ema30":False,"required_move_to_target_btc":3.97,
           "comparable_parent_amplitude_btc":50.18,"observed_target_side":"YES"}
        cross={"gap_lifecycle":{"stage":"SPROUT","age_seconds_since_observed_cross":28.75,
                                "current_side":"NO","current_abs_gap_btc":.366,
                                "gap_expanding_6s":False}}
        s=snap(yes=.61,no=.39,age=88,mountain=mm,tp=t,
               meta={"current_geometry":{"ema_gap":-.366,"range60":8.81,"arc_phase":"MATURE"},
                     "ema9_ema30_cross_context":cross})
        _,cs,d=self.decide(s)
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)



    def test_pid3296_trade2_thin_tp_possession_is_not_automatic_runway(self):
        mm=m("YES",True,edge="PID3296-T2")
        # Return side NO is only ~$6 below TP with ~96s remaining. Recent 60s
        # range is larger and the live 6s BTC/EMA9 motion is back toward YES.
        tp={"target_between_ema9_ema30":False,"remaining_seconds":96.482,
            "observed_target_side":"NO","required_move_to_target_btc":6.09,
            "contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"YES"}
        geom={"btc_price":77812.78,"ema_gap":-5.8299,"range60":9.67,"range180":14.58,
              "btc_change6":2.79,"ema9_change6":.558,"btc_change30":-1.42,"btc_change60":-3.17}
        cross={"gap_lifecycle":{"stage":"INHERITED_OR_UNOBSERVED_CROSS","current_side":"NO",
                                "current_abs_gap_btc":5.8299,"continued_on_latest_cross_side":False}}
        _,cs,d=self.decide(snap(yes=.86,no=.15,age=803.5,mountain=mm,tp=tp,
            meta={"current_geometry":geom,"ema9_ema30_cross_context":cross}))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_target_possession_can_still_pass_late_in_fast_directional_regime(self):
        mm=m("YES",True,edge="FAST-POSSESSION")
        tp={"target_between_ema9_ema30":False,"remaining_seconds":96.0,
            "observed_target_side":"NO","required_move_to_target_btc":100.0}
        # A high-volatility chapter: $300 recent minute range, but the current
        # NO move is still extending at ~5 BTC/s and has 36s before the final
        # settlement-average window.  100 + 180 >= 300 only narrowly misses,
        # so use ~6 BTC/s demonstrated to prove robust possession.
        geom={"range60":300.0,"range180":650.0,"btc_change6":-36.0,"ema9_change6":-8.0,
              "btc_change30":-180.0,"btc_change60":-360.0}
        _,cs,d=self.decide(snap(yes=.85,no=.15,age=804,mountain=mm,tp=tp,
            meta={"current_geometry":geom}))
        self.assertEqual(len(cs),1); self.assertIs(d.action,Action.ENTER); self.assertIs(d.intent.side,Side.NO)
        proof=d.intent.metadata["commander_physical_evidence"]["return_runway"]
        self.assertEqual(proof["basis"],"RETURN_SIDE_TARGET_POSSESSION_ROBUST")
        self.assertTrue(proof["causal_hold_or_extension"])

    def test_pid3296_0831_rolling_gap_child_terminal_turn_waits_when_tp_owns_no(self):
        mm=m("NO",True,edge="PID3296-0831")
        mm["return_leg_reference"]={
            "count":4,"basis":"LAST_COMPLETED_OPPOSITE_DIRECTION_PARENT_MOUNTAINS",
            "median_amplitude_btc":36.11,"median_speed_btc_s":.170166,
            "max_amplitude_btc":114.47,"max_speed_btc_s":.241973,
            "legs":[
                {"arc_id":"E32","btc_amplitude_btc":39.35,"duration_s":183.67,"average_btc_speed_btc_s":.214239},
                {"arc_id":"E34","btc_amplitude_btc":114.47,"duration_s":998.80,"average_btc_speed_btc_s":.114607},
                {"arc_id":"E36","btc_amplitude_btc":27.08,"duration_s":214.76,"average_btc_speed_btc_s":.126094},
                {"arc_id":"E38","btc_amplitude_btc":32.87,"duration_s":135.84,"average_btc_speed_btc_s":.241973},
            ]}
        tp={"target_between_ema9_ema30":False,"remaining_seconds":831.15,
            "observed_target_side":"NO","required_move_to_target_btc":35.18,
            "contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"NO"}
        cross={"gap_lifecycle":{"stage":"ROLLING","age_seconds_since_observed_cross":3006.57,
            "current_side":"YES","current_abs_gap_btc":4.6837,"continued_on_latest_cross_side":True,
            "gap_expanding_6s":True,"clock_has_trade_authority":False}}
        geom={"btc_price":77826.62,"ema9":77837.9034,"ema30":77833.2197,"ema_gap":4.6837,
              "range60":22.12,"btc_change6":.01,"ema9_change6":.002,"parent_direction":"DOWN"}
        s=snap(yes=.39,no=.62,age=68.85,mountain=mm,tp=tp,
               meta={"current_geometry":geom,"ema9_ema30_cross_context":cross,
                     "commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"}})
        _,cs,d=self.decide(s)
        self.assertEqual(len(cs),0)
        self.assertIs(d.action,Action.WAIT)
        self.assertEqual(d.reason,"MAIN_NORMAL_SEARCH_BEGINS_AFTER_300S")

    def test_rolling_gap_child_still_advancing_does_not_enter_mid_pullback(self):
        mm=m("NO",True,edge="ROLLING-STILL-DOWN")
        mm["return_leg_reference"]={"count":3,"legs":[
            {"arc_id":"R1","btc_amplitude_btc":80.0,"duration_s":240.0,"average_btc_speed_btc_s":.333},
            {"arc_id":"R2","btc_amplitude_btc":90.0,"duration_s":260.0,"average_btc_speed_btc_s":.346},
            {"arc_id":"R3","btc_amplitude_btc":70.0,"duration_s":220.0,"average_btc_speed_btc_s":.318}],
            "median_amplitude_btc":80.0,"median_speed_btc_s":.333,"max_amplitude_btc":90.0,"max_speed_btc_s":.346}
        tp={"target_between_ema9_ema30":False,"remaining_seconds":700.0,
            "observed_target_side":"NO","required_move_to_target_btc":35.0}
        cross={"gap_lifecycle":{"stage":"ROLLING","age_seconds_since_observed_cross":2200.0,
            "current_side":"YES","current_abs_gap_btc":7.0,"continued_on_latest_cross_side":True}}
        geom={"ema_gap":7.0,"range60":30.0,"btc_change6":-12.0,"ema9_change6":-2.0,"parent_direction":"DOWN"}
        _,cs,d=self.decide(snap(yes=.35,no=.65,age=200,mountain=mm,tp=tp,
            meta={"current_geometry":geom,"ema9_ema30_cross_context":cross,
                  "commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"}}))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_mature_gap_without_current_child_terminal_does_not_gain_clock_authority(self):
        mm=m("NO",False,mature=False,window=False)
        tp={"target_between_ema9_ema30":False,"remaining_seconds":700.0,
            "observed_target_side":"NO","required_move_to_target_btc":30.0}
        cross={"gap_lifecycle":{"stage":"MATURE","age_seconds_since_observed_cross":1200.0,
            "current_side":"YES","current_abs_gap_btc":8.0,"continued_on_latest_cross_side":True}}
        geom={"ema_gap":8.0,"range60":30.0,"btc_change6":1.0,"ema9_change6":.2}
        _,cs,d=self.decide(snap(yes=.30,no=.70,mountain=mm,tp=tp,
            meta={"current_geometry":geom,"ema9_ema30_cross_context":cross,
                  "commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"}}))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_rolling_gap_pullback_still_requires_dynamic_tp_runway(self):
        mm=m("NO",True,edge="ROLLING-NO-RUNWAY")
        mm["return_leg_reference"]={"count":3,"legs":[
            {"arc_id":"Q1","btc_amplitude_btc":40.0,"duration_s":300.0,"average_btc_speed_btc_s":.133},
            {"arc_id":"Q2","btc_amplitude_btc":45.0,"duration_s":320.0,"average_btc_speed_btc_s":.141},
            {"arc_id":"Q3","btc_amplitude_btc":42.0,"duration_s":310.0,"average_btc_speed_btc_s":.135}],
            "median_amplitude_btc":42.0,"median_speed_btc_s":.135,"max_amplitude_btc":45.0,"max_speed_btc_s":.141}
        tp={"target_between_ema9_ema30":False,"remaining_seconds":180.0,
            "observed_target_side":"NO","required_move_to_target_btc":120.0}
        cross={"gap_lifecycle":{"stage":"ROLLING","age_seconds_since_observed_cross":2400.0,
            "current_side":"YES","current_abs_gap_btc":7.0,"continued_on_latest_cross_side":True}}
        geom={"ema_gap":7.0,"range60":30.0,"btc_change6":1.0,"ema9_change6":.2}
        _,cs,d=self.decide(snap(yes=.25,no=.75,mountain=mm,tp=tp,
            meta={"current_geometry":geom,"ema9_ema30_cross_context":cross}))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_rolling_gap_collapsed_to_spine_does_not_create_continuation(self):
        mm=m("NO",True,edge="ROLLING-SPINE")
        mm["return_leg_reference"]={"count":3,"legs":[
            {"arc_id":"S1","btc_amplitude_btc":80.0,"duration_s":240.0,"average_btc_speed_btc_s":.333},
            {"arc_id":"S2","btc_amplitude_btc":90.0,"duration_s":260.0,"average_btc_speed_btc_s":.346},
            {"arc_id":"S3","btc_amplitude_btc":70.0,"duration_s":220.0,"average_btc_speed_btc_s":.318}]}
        tp={"target_between_ema9_ema30":False,"remaining_seconds":700.0,
            "observed_target_side":"NO","required_move_to_target_btc":35.0}
        cross={"gap_lifecycle":{"stage":"ROLLING","age_seconds_since_observed_cross":2400.0,
            "current_side":"YES","current_abs_gap_btc":.4,"continued_on_latest_cross_side":True}}
        geom={"ema_gap":.4,"range60":30.0,"btc_change6":1.0,"ema9_change6":.2}
        _,cs,d=self.decide(snap(yes=.30,no=.70,mountain=mm,tp=tp,
            meta={"current_geometry":geom,"ema9_ema30_cross_context":cross}))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_pid23072_prefix_factory_controls_and_shared_quality_are_distinct(self):
        observed = {}
        for control in self.pid23072_controls:
            snapshot, _, _, candidates, decision = self._pid23072_replay(control)
            raw = physical_entry_candidates(snapshot)
            # Preserve the old detector/factory controls on the exact causal
            # prefix. Their stored ENTER label is not automatic permission
            # under the new independent physical-quality boundary.
            self.assertEqual("ENTER" if raw else "WAIT",control["expected_action"])
            expected = "WAIT" if control["trade_number"] in (9,10) else control["expected_action"]
            observed[control["trade_number"]] = decision.action.value
            self.assertEqual(decision.action.value, expected,
                             msg=f"PID23072 trade #{control['trade_number']} {control['control_label']}")
            if expected == "ENTER":
                self.assertTrue(candidates)
                self.assertIs(decision.intent.side, Side(control["side"]))
            elif control["trade_number"] in (9,10):
                self.assertEqual(decision.reason,"OPPORTUNITY_MOUNTAIN_PARENT_TERMINAL_PROOF_REQUIRED")
        self.assertEqual(observed, {1:"ENTER",2:"WAIT",3:"ENTER",4:"WAIT",5:"ENTER",
                                    6:"WAIT",7:"WAIT",8:"WAIT",9:"WAIT",10:"WAIT"})

    def test_pid23072_trade1_good_edge_has_proven_return_runway(self):
        control = self.pid23072_controls[0]
        _, _, cross, candidates, decision = self._pid23072_replay(control)
        self.assertIs(decision.action, Action.ENTER); self.assertIs(decision.intent.side, Side.NO)
        self.assertEqual(cross["gap_lifecycle"]["stage"], "SPROUT")
        proof = candidates[0].metadata["commander_physical_evidence"]["return_runway"]
        self.assertEqual(proof["basis"], "PROVEN_RETURN_LEG_CAN_REACH_TP")
        self.assertLessEqual(proof["required_total_runway_seconds"], proof["remaining_seconds"])

    def test_pid23072_trade7_new_gap_cannot_masquerade_as_inherited_leg(self):
        control = self.pid23072_controls[6]
        snapshot, mountain, cross, candidates, decision = self._pid23072_replay(control)
        self.assertIs(decision.action, Action.WAIT); self.assertEqual(candidates, ())
        self.assertEqual(cross["gap_lifecycle"]["stage"], "SPROUT")
        gap_age = cross["gap_lifecycle"].get("age_seconds_since_observed_cross")
        self.assertIsNotNone(gap_age)
        self.assertLess(float(gap_age), float(snapshot.contract_age_s) + 2.0)
        self.assertGreater(float((mountain.get("diagnostics") or {}).get("current_age_s") or 0.0),
                           float(snapshot.contract_age_s))

    def test_pid23072_trade8_sprout_is_still_expanding_not_true_peak(self):
        control = self.pid23072_controls[7]
        _, mountain, cross, candidates, decision = self._pid23072_replay(control)
        self.assertIs(decision.action, Action.WAIT); self.assertEqual(candidates, ())
        self.assertTrue(mountain["terminal_evidence_qualified"])  # detector sees local terminal; Commander must reject it
        self.assertEqual(cross["gap_lifecycle"]["stage"], "SPROUT")
        motion = mountain["current_motion"]
        self.assertGreater(float(motion["30"]["owner_price_rate_btc_s"]), 0.0)
        self.assertGreater(float(motion["30"]["owner_ema9_rate_btc_s"]), 0.0)
        self.assertGreater(float(motion["60"]["owner_price_rate_btc_s"]), 0.0)
        self.assertGreater(float(motion["60"]["owner_ema9_rate_btc_s"]), 0.0)

    def test_pid23072_trade9_paired_gap_label_without_current_comparable_maturity_waits(self):
        snapshot, mountain, _, candidates, decision = self._pid23072_replay(self.pid23072_controls[8])
        raw=physical_entry_candidates(snapshot)
        self.assertTrue(any(i.side is Side.YES for i in raw))
        self.assertTrue(mountain["diagnostics"]["mature_by_paired_gap"])
        self.assertFalse(mountain["diagnostics"]["mature_by_comparison"])
        self.assertFalse(mountain["diagnostics"]["mature_by_causal_turn"])
        self.assertEqual(snapshot.metadata["current_geometry"]["btc_change6"],0.)
        self.assertEqual(candidates,())
        self.assertIs(decision.action,Action.WAIT)
        self.assertEqual(decision.reason,"OPPORTUNITY_MOUNTAIN_PARENT_TERMINAL_PROOF_REQUIRED")

    def test_pid23072_trade10_extended_factory_candidate_needs_independent_terminal_proof(self):
        control = self.pid23072_controls[9]
        snapshot, mountain, cross, candidates, decision = self._pid23072_replay(control)
        raw=physical_entry_candidates(snapshot)
        self.assertTrue(raw)
        self.assertEqual(raw[0].reason, "COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN")
        self.assertLessEqual(float(snapshot.ask_for(raw[0].side)), 0.20)
        self.assertTrue((mountain.get("parent_structure") or {}).get("extended_parent"))
        self.assertTrue(mountain["diagnostics"]["mature_by_paired_gap"])
        self.assertFalse(mountain["diagnostics"]["mature_by_comparison"])
        self.assertFalse(mountain["diagnostics"]["mature_by_causal_turn"])
        self.assertEqual(snapshot.metadata["current_geometry"]["btc_change6"],0.)
        self.assertEqual(candidates,())
        self.assertIs(decision.action,Action.WAIT)
        self.assertEqual(decision.reason,"OPPORTUNITY_MOUNTAIN_PARENT_TERMINAL_PROOF_REQUIRED")

    def test_collection_uses_stricter_terminal_than_entry_and_holds_early(self):
        mm=m("NO",True,edge="NEXT:1120000")
        mm["primary_collection_terminal_qualified"]=False
        s=snap(t=1120,age=420,yes=.30,no=.70,yes_bid=.29,no_bid=.69,mountain=mm,
               tp={"target_between_ema9_ema30":False})
        pos={"position_id":"P1","ticker":s.ticker,"territory_id":"M","opportunity_id":"O",
             "tool":"ONE_COMMANDER_PRIMARY","lane":"MAIN","side":Side.NO,"entry_price":.19,
             "entry_time":1000.0,"close_ts":1900.0,"custody_state":"NORMAL",
             "entry_metadata":{"commander_physical_evidence":{"edge_id":"TOP:1000000"}},"floor_bid":None}
        d=OneCommander().decide_position([],s,pos)
        self.assertIs(d.action,Action.HOLD)
        mm2=dict(mm); mm2["primary_collection_terminal_qualified"]=True
        s2=snap(t=1120,age=420,yes=.30,no=.70,yes_bid=.29,no_bid=.69,mountain=mm2,
                tp={"target_between_ema9_ema30":False})
        d2=OneCommander().decide_position([],s2,pos)
        self.assertIs(d2.action,Action.EXIT)

    def test_ema_tp_junction_waits(self):
        _,cs,d=self.decide(snap(yes=.19,no=.19,mountain=m("YES",True),tp={"target_between_ema9_ema30":True}))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_strong_expansion_not_faded(self):
        _,cs,d=self.decide(snap(yes=.19,no=.81,mountain=m("NO",True,strong=True),tp={"target_between_ema9_ema30":False}))
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_nonmountain_has_no_candidates(self):
        s=snap(yes=.1,no=.1,mountain=m("NO",False,qualified=False),tp={},
               meta={"commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"}})
        _,cs,d=self.decide(s)
        self.assertEqual(cs,()); self.assertIs(d.action,Action.WAIT)

    def test_authorized_specialist_needs_a_measured_location_not_only_its_label(self):
        bare=snap(yes=.1,no=.1,mountain=m("NO",False),tp={},
               meta={"commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"}})
        rail=ToolIntent(tool="RAIL",territory_id="R",lane=Lane.MAIN,side=Side.NO,action=Action.ENTER,
                        opportunity_id="R",max_price=.1,size_tier=10,reason="RAIL_MAIN_VALUE",source_time=1000,metadata={})
        denied=OneCommander().decide([rail],bare)
        self.assertIs(denied.action,Action.WAIT)
        self.assertEqual(denied.reason,"OPPORTUNITY_MAIN_PHYSICAL_VALUE_REJOIN_REQUIRED")
        # Explicit synthetic 100-second beginning of a current UP parent:
        # numeric motion, located value, actual favorable target and source.
        s=parent_snapshot(t=1000.,price=120.,age=400.,ask=.1,child_start=900.)
        md=deepcopy(s.metadata)
        md["mission_context"]["parent"].update(origin_ms=900000.,known_ms=900000.)
        md["mountain"]["parent_structure"]["parent_age_s"]=100.
        s=replace(s,metadata=md)
        rail=replace(rail,side=Side.YES)
        d=OneCommander().decide([rail],s)
        self.assertIs(d.action,Action.ENTER)
        self.assertEqual(d.intent.metadata["commander_opportunity"]["species"],"MAIN_EMA9_REJOIN")
        unauthorized=ToolIntent(tool="TACTICAL_FADE",territory_id="F",lane=Lane.TACTICAL,side=Side.NO,
                        action=Action.ENTER,opportunity_id="F",max_price=.1,size_tier=10,reason="FADE",
                        source_time=1000,metadata={})
        blocked=OneCommander().decide([unauthorized],s)
        self.assertIs(blocked.action,Action.WAIT)
        self.assertEqual(blocked.reason,"COMMANDER_UNAUTHORIZED_SPECIALIST_ENTRY_PAUSED")

    def test_candidate_carries_approved_floor(self):
        _,cs,d=self.decide(synthetic_terminal_snapshot())
        self.assertIs(d.action,Action.ENTER)
        p=cs[0].metadata["floor_policy"]
        self.assertEqual(p["arm_roi"],1.0); self.assertEqual(p["trail_fraction"],.05)
        self.assertTrue(p["first_arm_from_current_bid"])
        self.assertIn([1.5,.03],p["roi_trail_tiers"]); self.assertIn([6.0,.02],p["roi_trail_tiers"])


    def test_sideways_no_terrain_uses_only_operator_authorized_3pct_peak_lock(self):
        s=snap(meta={
            "commander_strategy":{"owned_territory":"UNKNOWN","owned_side":None,"active_tool":None},
            "tool_rack":{"owned_territory":"UNKNOWN","owned_side":None},
            "heist":{"qualified_box":False,"diagnostics":{"sideways_enough":True}},
        })
        policy=floor_policy(SimpleNamespace(edge_only_custody=True),position=None,snapshot=s)
        self.assertEqual(policy["trail_fraction"],.03)
        self.assertEqual(policy["roi_trail_tiers"],[[1.0,.03]])
        self.assertEqual(policy["profit_policy_revision"],"OPERATOR_AUTHORIZED_SIDEWAYS_NO_TERRAIN_100_3_V1")

    def test_sideways_no_terrain_120pct_peak_cannot_fall_to_36pct(self):
        ticker="KX-SIDEWAYS-NO-TERRAIN-120"
        enter=synthetic_terminal_snapshot(side=Side.NO,ask=.13,ticker=ticker)
        commander=OneCommander(); candidates=commander.physical_entry_candidates(enter)
        entry_decision=commander.decide_entry(list(candidates),enter,{})
        self.assertIs(entry_decision.action,Action.ENTER)
        flat=snap(t=1010,ticker=ticker,age=310,yes=.70,no=.30,yes_bid=.704,no_bid=.286,
                  mountain=m("NO",False,qualified=False),tp={"target_between_ema9_ema30":False},
                  meta={
                      "commander_strategy":{"owned_territory":"UNKNOWN","owned_side":None,"active_tool":None},
                      "tool_rack":{"owned_territory":"UNKNOWN","owned_side":None},
                      "heist":{"qualified_box":False,"diagnostics":{"sideways_enough":True}},
                  })
        raw=floor_policy(SimpleNamespace(edge_only_custody=True),position=None,snapshot=flat)
        policy=FloorPolicy(arm_roi=raw["arm_roi"],trail_fraction=raw["trail_fraction"],
            min_age_seconds=raw.get("min_age_s",0.0),immediate_arm_roi=raw.get("immediate_arm_roi"),
            first_arm_allowed=raw.get("first_arm_allowed",True),
            first_arm_from_current_bid=raw.get("first_arm_from_current_bid",False),
            roi_trail_tiers=tuple(tuple(x) for x in raw.get("roi_trail_tiers",())))
        entry_book=PaperBook(ticker=ticker,quote_id="ENTRY",observed_ts=1000,exchange_ts=1000,
            yes_bids=(PriceLevel(.87,1000),),no_bids=(PriceLevel(.12,1000),),close_ts=1900,
            current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
            provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                        "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
        with tempfile.TemporaryDirectory() as td, PaperExecutioner(td) as ex:
            receipt=ex.execute(entry_decision,entry_book,now_ts=1000,command_id="ENTRY")
            self.assertEqual(receipt.status,"BOOKED")
            peak=PaperBook(ticker=ticker,quote_id="PEAK120",observed_ts=1010,exchange_ts=1010,
                yes_bids=(PriceLevel(.704,1000),),no_bids=(PriceLevel(.286,1000),),close_ts=1900,
                current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
                provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                            "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
            obs=ex.observe_floors(peak,now_ts=1010,policies={receipt.position_id:policy},position_ids=(receipt.position_id,))[0]
            self.assertFalse(obs.breached)
            self.assertAlmostEqual(ex.positions[receipt.position_id].floor_bid,.27742,places=6)
            protect=PaperBook(ticker=ticker,quote_id="PROTECT",observed_ts=1011,exchange_ts=1011,
                yes_bids=(PriceLevel(.723,1000),),no_bids=(PriceLevel(.277,1000),),close_ts=1900,
                current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
                provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                            "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
            obs=ex.observe_floors(protect,now_ts=1011,policies={receipt.position_id:policy},position_ids=(receipt.position_id,))[0]
            self.assertTrue(obs.breached)
            self.assertEqual(ex.positions[receipt.position_id].exit_reason,"ALREADY_ARMED_EXECUTABLE_BID_FLOOR")

    def test_sideways_flag_does_not_override_an_owned_mountain_terrain(self):
        s=snap(meta={"heist":{"qualified_box":False,"diagnostics":{"sideways_enough":True}}})
        policy=floor_policy(SimpleNamespace(edge_only_custody=True),position=None,snapshot=s)
        self.assertEqual(policy["trail_fraction"],.05)
        self.assertIn([1.5,.03],policy["roi_trail_tiers"])

    def test_operator_authorized_profit_lock_blocks_120pct_peak_from_falling_to_36pct(self):
        ticker="KX-AUTHORIZED-120-FLOOR"
        enter=synthetic_terminal_snapshot(side=Side.NO,ask=.13,ticker=ticker)
        commander=OneCommander(); candidates=commander.physical_entry_candidates(enter)
        entry_decision=commander.decide_entry(list(candidates),enter,{})
        self.assertIs(entry_decision.action,Action.ENTER)
        candidate=entry_decision.intent
        policy_raw=candidate.metadata["floor_policy"]
        policy=FloorPolicy(
            arm_roi=policy_raw["arm_roi"], trail_fraction=policy_raw["trail_fraction"],
            min_age_seconds=policy_raw.get("min_age_s",0.0), immediate_arm_roi=policy_raw.get("immediate_arm_roi"),
            first_arm_allowed=policy_raw.get("first_arm_allowed",True),
            first_arm_from_current_bid=policy_raw.get("first_arm_from_current_bid",False),
            roi_trail_tiers=tuple(tuple(x) for x in policy_raw.get("roi_trail_tiers",())),
        )
        entry_book=PaperBook(ticker=ticker,quote_id="ENTRY",observed_ts=1000,exchange_ts=1000,
            yes_bids=(PriceLevel(.87,1000),),no_bids=(PriceLevel(.12,1000),),close_ts=1900,
            current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
            provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                        "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
        with tempfile.TemporaryDirectory() as td, PaperExecutioner(td) as ex:
            receipt=ex.execute(entry_decision,entry_book,now_ts=1000,command_id="ENTRY")
            self.assertEqual(receipt.status,"BOOKED")
            # Entry is 13c.  A 28.6c executable bid is +120% gross ROI.
            peak=PaperBook(ticker=ticker,quote_id="PEAK120",observed_ts=1010,exchange_ts=1010,
                yes_bids=(PriceLevel(.704,1000),),no_bids=(PriceLevel(.286,1000),),close_ts=1900,
                current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
                provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                            "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
            obs=ex.observe_floors(peak,now_ts=1010,policies={receipt.position_id:policy},position_ids=(receipt.position_id,))[0]
            self.assertFalse(obs.breached)
            self.assertAlmostEqual(ex.positions[receipt.position_id].floor_bid,.2717,places=6)
            # A one-step fall below the authorized 5% peak-bid floor must force
            # protection long before a +36% ROI giveback is possible.
            protected=PaperBook(ticker=ticker,quote_id="PROTECT",observed_ts=1011,exchange_ts=1011,
                yes_bids=(PriceLevel(.72,1000),),no_bids=(PriceLevel(.27,1000),),close_ts=1900,
                current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
                provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                            "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
            obs=ex.observe_floors(protected,now_ts=1011,policies={receipt.position_id:policy},position_ids=(receipt.position_id,))[0]
            self.assertTrue(obs.breached)
            self.assertEqual(ex.positions[receipt.position_id].exit_reason,"ALREADY_ARMED_EXECUTABLE_BID_FLOOR")

    def test_commander_candidate_commits_without_specialist_owner(self):
        c=OneCommander(); s=snap(yes=.81,no=.19,mountain=m("YES",True),tp={"target_between_ema9_ema30":False})
        intent=c.physical_entry_candidates(s)[0]
        rack=ToolRackController(); rack.commit_accepted_intent(intent,s,position_id="P1")
        key=(s.ticker,intent.territory_id,intent.opportunity_id)
        self.assertIn(key,rack._filled_tools); self.assertIsNone(rack._filled_tools[key]); self.assertEqual(rack._position_keys["P1"],key)

    def test_filled_physical_mission_does_not_rearm_on_quote_refresh(self):
        c=OneCommander(); s=snap(yes=.81,no=.19,mountain=m("YES",True,edge="SAME"),tp={"target_between_ema9_ema30":False})
        first=c.physical_entry_candidates(s); self.assertEqual(len(first),1)
        c.mark_entry_filled(first[0],ticker=s.ticker)
        refreshed=snap(yes=.85,no=.15,mountain=m("YES",True,edge="SAME"),tp={"target_between_ema9_ema30":False})
        self.assertEqual(c.physical_entry_candidates(refreshed),())

    def test_same_entry_edge_does_not_immediately_exit(self):
        c=OneCommander(); s=snap(t=1001,yes=.82,no=.18,yes_bid=.81,no_bid=.17,
            mountain=m("NO",True,edge="ENTRY-TOP"),tp={"target_between_ema9_ema30":False})
        pos={"position_id":"P1","ticker":s.ticker,"territory_id":"M","opportunity_id":"O","tool":"ONE_COMMANDER_PRIMARY",
             "lane":"MAIN","side":Side.NO,"entry_price":.19,"entry_time":1000.0,"close_ts":1900.0,"custody_state":"NORMAL",
             "entry_metadata":{"commander_physical_evidence":{"edge_id":"ENTRY-TOP"}},"floor_bid":None}
        d=c.decide_position([],s,pos); self.assertIs(d.action,Action.HOLD)

    def test_stale_exit_latch_without_current_window_holds(self):
        c=OneCommander(); s=snap(t=1120,yes=.30,no=.70,yes_bid=.29,no_bid=.69,
            mountain=m("NO",True,edge="NEXT:1120000",mature=False,window=False),tp={"target_between_ema9_ema30":False})
        pos={"position_id":"P1","ticker":s.ticker,"territory_id":"M","opportunity_id":"O","tool":"ONE_COMMANDER_PRIMARY",
             "lane":"MAIN","side":Side.NO,"entry_price":.19,"entry_time":1000.0,"close_ts":1900.0,"custody_state":"NORMAL",
             "entry_metadata":{"commander_physical_evidence":{"edge_id":"ENTRY-TOP"}},"floor_bid":None}
        d=c.decide_position([],s,pos); self.assertIs(d.action,Action.HOLD)

    def test_next_current_terminal_edge_exits(self):
        c=OneCommander(); s=snap(t=1120,yes=.30,no=.70,yes_bid=.29,no_bid=.69,
            mountain=m("NO",True,edge="NEXT:1120000"),tp={"target_between_ema9_ema30":False})
        pos={"position_id":"P1","ticker":s.ticker,"territory_id":"M","opportunity_id":"O","tool":"ONE_COMMANDER_PRIMARY",
             "lane":"MAIN","side":Side.NO,"entry_price":.19,"entry_time":1000.0,"close_ts":1900.0,"custody_state":"NORMAL",
             "entry_metadata":{"commander_physical_evidence":{"edge_id":"ENTRY-TOP"}},"floor_bid":None}
        d=c.decide_position([],s,pos); self.assertIs(d.action,Action.EXIT)

    def test_pid8868_actual_current_held_no_terminal_triggers_exit(self):
        s=fixture_snapshot("current_terminal_held_no_exit")
        self.assertTrue(s.metadata["mountain"]["terminal_evidence_qualified"])
        pos={"position_id":"P1","ticker":s.ticker,"territory_id":"M","opportunity_id":"O","tool":"ONE_COMMANDER_PRIMARY",
             "lane":"MAIN","side":Side.NO,"entry_price":.17,"entry_time":s.now_ts-300.0,"close_ts":fixture_case("current_terminal_held_no_exit")["close_ts"],
             "custody_state":"NORMAL","entry_metadata":{"commander_physical_evidence":{"edge_id":"OLDER-TOP:1793494300000"}},"floor_bid":None}
        d=OneCommander().decide_position([],s,pos)
        self.assertIs(d.action,Action.EXIT)
        self.assertEqual(d.intent.reason,"COMMANDER_MOUNTAIN_ONLY_HELD_LEG_TERMINAL_EDGE")

    def test_full_paper_entry_hold_exit_is_committed(self):
        ticker="KX-END2END"
        # This tests full-target Mountain custody. A bounded local EMA9
        # return has its separate observed-path/destination collection tests;
        # it must not be made to exit on this generic child terminal alone.
        enter=synthetic_terminal_snapshot(side=Side.NO,ask=.19,t=1000.,age=300.,
                                          ticker=ticker,edge="TOP:1000000")
        c=OneCommander(); enter_candidates=c.physical_entry_candidates(enter)
        enter_decision=c.decide_entry(list(enter_candidates),enter,{})
        self.assertIs(enter_decision.action,Action.ENTER)
        self.assertEqual(enter_decision.intent.metadata["commander_opportunity"]
                         ["evidence"]["return_runway"]["target_kind"],"CONTRACT_TARGET")
        book1=PaperBook(ticker=ticker,quote_id="Q1",observed_ts=1000,exchange_ts=1000,
            yes_bids=(PriceLevel(.81,1000),),no_bids=(PriceLevel(.18,1000),),close_ts=1900,
            current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
            provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                        "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
        with tempfile.TemporaryDirectory() as td, PaperExecutioner(td) as ex:
            rec1=ex.execute(enter_decision,book1,now_ts=1000,command_id="ENTRY")
            self.assertEqual(rec1.status,"BOOKED"); self.assertEqual(len(ex.positions),1)
            p=asdict(next(iter(ex.positions.values())))
            p["side"]=Side(p["side"]); p["lane"]=p["lane"].value

            same=snap(t=1001,ticker=ticker,age=301,yes=.80,no=.21,yes_bid=.79,no_bid=.20,
                      mountain=m("NO",True,edge="TOP:1000000"),
                      tp={"target":76030.,"target_between_ema9_ema30":False},
                      meta={"current_geometry":{"btc_price":75999.,"ema9":76001.,"ema30":76008.}})
            hold=c.decide_position([],same,p); self.assertIs(hold.action,Action.HOLD)

            exit_s=snap(t=1120,ticker=ticker,age=420,yes=.30,no=.70,yes_bid=.29,no_bid=.69,
                        mountain=m("NO",True,edge="BOTTOM:1120000"),
                        tp={"target":76030.,"target_between_ema9_ema30":False},
                        meta={"current_geometry":{"btc_price":75880.,"ema9":75882.,"ema30":75890.}})
            exit_d=c.decide_position([],exit_s,p); self.assertIs(exit_d.action,Action.EXIT)
            book2=PaperBook(ticker=ticker,quote_id="Q2",observed_ts=1120,exchange_ts=1120,
                yes_bids=(PriceLevel(.29,1000),),no_bids=(PriceLevel(.69,1000),),close_ts=1900,
                current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
                provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                            "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
            rec2=ex.execute(exit_d,book2,now_ts=1120,command_id="EXIT",position_id=rec1.position_id)
            self.assertEqual(rec2.status,"EXITED"); self.assertEqual(ex.positions,{})
            self.assertEqual([e["event"] for e in ex.events], ["ENTRY","EXIT"])


if __name__ == "__main__": unittest.main()
