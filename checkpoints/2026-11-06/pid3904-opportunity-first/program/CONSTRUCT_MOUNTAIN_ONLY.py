"""Opportunity-first Mountain Construct with explicit evidence scopes.

Shared admission cases combine Commander physical candidates with advisers and
call the same decide_entry boundary used by PAPER. Synthetic cases author
numeric current-source geometry, comparative maturity, measured retreat and
return references. A boolean label alone is not a positive entry premise.

Historical sources are read unchanged:
* PID8868 partial wrappers preserve their original physical-factory positives,
  while shared admission honestly WAITs for missing current-source proof.
* PID23072 rebuilds detectors from a causal geometry prefix and recorded
  contract values with a reconstructed price control. It is not a native-book
  replay. The old factory controls remain checked separately. Shared positives
  #1/#3/#5 survive; #9/#10 WAIT for independent parent terminal proof, and the
  other negative controls remain WAIT.
* PID2672 partial junction/Rail controls retain specialist classification and
  their price boundaries without claiming complete shared admission evidence.
* PID3216 detector and source-clock controls keep their original scope. A feed
  clock allowance does not grant shared entry without its required provenance.

The gate retains price/runway, stale-edge, outward-sprout, gap-context,
same-entry-edge, house, hierarchy, held-terminal and raw negative controls.
A specialist WAIT is advisory: a qualified Commander opportunity still enters.
Floor controls use actually admitted synthetic candidates and unchanged
executable-bid policy. The end-to-end PAPER ENTRY -> HOLD -> EXIT is committed
through PaperExecutioner, including both receipts and the final flat position.
Every control retains its chart. No result is a replacement historical P&L.

No network, no venue orders, no live PAPER session.
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import html
import json
import tempfile
from copy import deepcopy
from dataclasses import asdict, replace
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import physical_entry_candidates as factory_candidates
from strategy_core.detectors.mountain_geometry import detect_mountain_geometry
from strategy_core.paper_execution import FloorPolicy, PaperBook, PaperExecutioner, PriceLevel
from strategy_core.looking_glass import build_looking_glass
from strategy_core.mission_context import MissionContext
from strategy_core.mission_policy import MissionPolicy
from strategy_core.paper_runtime import ToolRackPaperEngine
from strategy_core.router import PhysicalEvidence
from strategy_core.tool_rack import ToolRackController
from strategy_core.physical_source import DirectPhysicalSource, PhysicalConfig, ema9_ema30_cross_context
from strategy_core.tp_geometry import build_tp_geometry
from strategy_core.types import Action, Lane, MarketSnapshot, Side, Territory, ToolIntent
from strategy_core.tools.heist import MarketHeistTool
from strategy_core.tools.management import floor_policy
from strategy_core.tools.rail import RailTool
from strategy_core.tools.release import ReleaseEvidence
from tests.tool_rack.test_mountain_only_reset import (
    snap as numeric_unit_snapshot, synthetic_terminal_snapshot,
)
from tests.tool_rack.test_opportunity_first_commander import (
    real_heist_snapshot, heist_intent as numeric_heist_intent,
)

ROOT = Path(__file__).parent
PID8868_FIXTURE = ROOT / "tests" / "tool_rack" / "fixtures" / "pid8868_mountain_gate.json"
PID23072_CONTROL_FIXTURE = ROOT / "tests" / "tool_rack" / "fixtures" / "pid23072_entry_controls.json"
PID23072_PHYSICAL_FIXTURE = ROOT / "tests" / "tool_rack" / "fixtures" / "pid23072_physical_geometry.jsonl.gz"
PID3216_HOVER_FIXTURE = ROOT / "tests" / "tool_rack" / "fixtures" / "pid3216_160950_ultra_geometry.jsonl.gz"


def snap(*, t=1000.0, btc=100.0, ema9=100.0, ema30=100.0, target=100.0,
         yes_ask=.50, no_ask=.50, yes_bid=None, no_bid=None, contract_age=300.0,
         mountain=None, tp=None, meta=None, ticker="KX-MOUNTAIN-CONSTRUCT"):
    """Explicit numeric synthetic premise; never used to enrich raw fixtures.

    A requested terminal includes a same-source observed retreat and comparable
    maturity. Authored return-reference summaries get distinct synthetic legs;
    historical controls use their separate immutable source loaders below.
    """
    overrides=deepcopy(meta or {})
    m=deepcopy(overrides.pop("mountain",mountain or {}))
    g={"btc_price":btc,"ema9":ema9,"ema30":ema30,"ema_gap":ema9-ema30,
       "arc_id":m.get("current_arc_id") or "SYNTHETIC_ARC"}
    g.update(overrides.pop("current_geometry",{}))
    arc_age=float((m.get("diagnostics") or {}).get("current_age_s") or 120.)
    g.setdefault("arc_known_ms",(t-arc_age)*1000.)
    if m.get("terminal_evidence_qualified") is True:
        reference=m.get("return_leg_reference")
        if reference is None:
            reference=deepcopy(synthetic_terminal_snapshot().metadata["mountain"]["return_leg_reference"])
            m["return_leg_reference"]=reference
        elif not reference.get("legs") and reference.get("median_amplitude_btc") and reference.get("median_speed_btc_s"):
            amplitude=float(reference["median_amplitude_btc"])
            speed=float(reference["median_speed_btc_s"])
            reference["legs"]=[{"arc_id":f"SYNTHETIC_CONSTRUCT_RETURN_{i}",
                "btc_amplitude_btc":amplitude*factor,"duration_s":amplitude*factor/speed,
                "average_btc_speed_btc_s":speed} for i,factor in enumerate((.8,1.,1.2),1)]
            reference["count"]=3
            reference["basis"]="EXPLICIT_SYNTHETIC_COMPLETED_RETURN_LEGS"
    target_context=deepcopy(overrides.pop("tp_geometry",tp or {}))
    target_context.setdefault("target",target)
    target_context.setdefault("remaining_seconds",max(0.,900.-contract_age))
    overrides["current_geometry"]=g
    overrides["construct_input_scope"]="EXPLICIT_NUMERIC_SYNTHETIC"
    return numeric_unit_snapshot(yes=yes_ask,no=no_ask,age=contract_age,t=t,
        ticker=ticker,mountain=m,tp=target_context,meta=overrides,
        yes_bid=max(.001,yes_ask-.01) if yes_bid is None else yes_bid,
        no_bid=max(.001,no_ask-.01) if no_bid is None else no_bid)


def decision(s, advisers=()):
    c=OneCommander()
    primary=c.physical_entry_candidates(s)
    combined=list(primary)+list(advisers)
    d=c.decide_entry(combined,s,{})
    return c,primary,d


def entry_result(name,s,action,side,points,advisers=(),*,factory_action=None,factory_side=None,scope=None):
    c,cs,d=decision(s,advisers)
    actual={"action":d.action.value,"side":d.intent.side.value if d.intent and d.intent.side else None,
            "reason":d.reason,
            "selected_primary":bool(d.intent and d.intent.metadata.get("commander_primary_candidate")),
            "candidates":[{"family":i.metadata.get("commander_candidate_family"),"side":i.side.value if i.side else None,
                           "max_price":i.max_price,"reason":i.reason,
                           "location":(i.metadata.get("commander_physical_evidence") or {}).get("entry_location")}
                          for i in cs]}
    expected={"action":action,"side":side}
    passed=actual["action"]==action and actual["side"]==side
    if factory_action is not None:
        native=factory_candidates(s)
        observed="ENTER" if native else "WAIT"
        sides=sorted({i.side.value for i in native if i.side is not None})
        actual.update(physical_factory_action=observed,physical_factory_sides=sides)
        expected.update(physical_factory_action=factory_action,physical_factory_side=factory_side)
        passed=passed and observed==factory_action and (factory_side is None or factory_side in sides)
    return {"name":name,"kind":"ENTRY","input_scope":scope or "EXPLICIT_NUMERIC_SYNTHETIC",
            "expected":expected,"actual":actual,"pass":passed,"points":points}


def position_result(name,s,pos,action,points):
    d=OneCommander().decide_position([],s,pos)
    actual={"action":d.action.value,"reason":d.reason}
    return {"name":name,"kind":"POSITION","expected":{"action":action},"actual":actual,
            "pass":actual["action"]==action,"points":points}


def mountain(*,side="YES",arc="A",terminal=False,strong=False,qualified=True,current_age=120.0,
             edge="EDGE",rolling=False,mature=None,window=None,parent_age=None,parent_amp=20.0,parent_terminal=False):
    if mature is None: mature=terminal
    if window is None: window=terminal
    parent={"parent_id":"P","parent_side":side,"parent_age_s":parent_age,"parent_amplitude":parent_amp,
            "parent_terminal_ready":parent_terminal,"slow_rolling_parent":rolling,"extended_parent":rolling,
            "child_arc_count":3 if rolling else 1}
    return {"qualified_alternating_mountain":qualified,"owner_side":side,"current_arc_id":arc,
            "terminal_evidence_qualified":terminal,"mature_edge":mature,"edge_window_active":window,
            "strong_active_release":strong,"edge_id":edge,"parent_structure":parent,
            "diagnostics":{"current_age_s":current_age}}


def tp(*,ownership="UNRESOLVED",side=None,junction=False,target=100,btc=100,comparable=20.0,observed=None):
    if observed is None:
        observed="YES" if btc>=target else "NO"
    return {"target":target,"btc":btc,"contract_ownership":ownership,"contract_ownership_side":side,
            "target_between_ema9_ema30":junction,"required_move_to_target_btc":abs(btc-target),
            "comparable_parent_amplitude_btc":comparable,"observed_target_side":observed}


def pts(values,target=100):
    return [{"t":i,"btc":b,"ema9":e,"tp":target} for i,(b,e) in enumerate(values)]




def pid3216_source_skew_case():
    src=DirectPhysicalSource(physical_config=PhysicalConfig(max_future_skew_seconds=2.0))
    raw={"epoch_ms":101.30*1000.0,"btc_price":1000.0,"ema9":999.0,"ema30":998.0,
         "connection_epoch":1,"sequence_num":1}
    frame=src.observe([raw],now_ts=100.0)
    actual={"current":frame.current,"geometry_age_seconds":frame.metadata.get("geometry_age_seconds"),
            "max_future_skew_seconds":frame.metadata.get("geometry_max_future_skew_seconds")}
    return {"name":"pid3216_small_negative_source_skew_remains_current","kind":"SOURCE",
            "expected":{"current":True},"actual":actual,"pass":frame.current is True,
            "points":pts([(1000,999)],1000)}


def _pid3216_hover_history(*,plateau=True):
    rows=[]; t=0
    specs=[("A1","UP",180,1000),("A2","DOWN",190,1040),("A3","UP",170,1005),
           ("A4","DOWN",180,1045),("A5","UP",200,1010),("A6","DOWN",170,1050)]
    for arc_id,direction,duration,base in specs:
        sign=1 if direction=="UP" else -1
        for age in range(0,duration+1,5):
            e9=base+sign*40*age/duration
            rows.append({"arc_id":arc_id,"arc_direction":direction,"epoch_ms":t+age*1000,
                         "arc_age_sec":age,"btc_price":e9,"ema9":e9,"ema30":e9-sign*10,
                         "arc_phase":"ROLLING" if age==duration else "BUILDING",
                         "arc_amplitude":abs(e9-base),"arc_prominence_threshold":5.0,"range60":40.0,
                         "struct_slope3m":sign*1.0,"struct_slope6m":sign*1.2})
        t+=(duration+5)*1000
    for age in range(0,101,5):
        adv=min(age,60) if plateau else age
        e9=1010+8*adv/60; btc=1030+10*adv/60
        rows.append({"arc_id":"A7","arc_direction":"UP","epoch_ms":t+age*1000,
                     "arc_age_sec":age,"btc_price":btc,"ema9":e9,"ema30":e9-28,
                     "arc_phase":"MATURE" if age>=70 else "BUILDING",
                     "arc_amplitude":e9-1010,"arc_prominence_threshold":5.0,"range60":20.0,
                     "struct_slope3m":1.0,"struct_slope6m":1.2})
    return rows


def pid3216_hover_case(*,plateau=True):
    out=detect_mountain_geometry(_pid3216_hover_history(plateau=plateau))
    expected_terminal=plateau
    actual={"mature_by_comparison":out.diagnostics.get("mature_by_comparison"),
            "mature_by_causal_hover":out.diagnostics.get("mature_by_causal_hover"),
            "edge_window_active":out.edge_window_active,"stall":out.stall,
            "terminal":out.diagnostics.get("terminal_evidence_qualified")}
    name=("pid3216_hover_can_prove_terminal_before_duration_maturity" if plateau
          else "pid3216_still_advancing_parent_cannot_use_hover_maturity")
    passed=(actual["mature_by_comparison"] is False
            and actual["mature_by_causal_hover"] is expected_terminal
            and actual["terminal"] is expected_terminal)
    return {"name":name,"kind":"DETECTOR","expected":{"terminal":expected_terminal},
            "actual":actual,"pass":passed,"points":pts([(1030,1010),(1040,1018),(1040 if plateau else 1046.7,1018 if plateau else 1023.3)],1040)}




def pid3216_actual_ultra_hover_case():
    with gzip.open(PID3216_HOVER_FIXTURE,"rt",encoding="utf-8") as handle:
        rows=[json.loads(line) for line in handle if line.strip()]
    out=detect_mountain_geometry(rows)
    m30=(out.diagnostics.get("current_motion") or {}).get("30") or {}
    actual={"current_arc_id":out.current_arc_id,"mature_by_comparison":out.diagnostics.get("mature_by_comparison"),
            "mature_by_causal_hover":out.diagnostics.get("mature_by_causal_hover"),
            "mature_edge":out.mature_edge,"edge_window_active":out.edge_window_active,"stall":out.stall,
            "terminal":out.diagnostics.get("terminal_evidence_qualified"),
            "owner_price_rate_30s":m30.get("owner_price_rate_btc_s"),
            "owner_ema9_rate_30s":m30.get("owner_ema9_rate_btc_s")}
    passed=(actual["current_arc_id"]=="G000A000008" and actual["mature_by_comparison"] is False
            and actual["mature_by_causal_hover"] is True and actual["mature_edge"] is True
            and actual["edge_window_active"] is True and actual["stall"] is True
            and actual["terminal"] is True and actual["owner_price_rate_30s"]==0.0
            and actual["owner_ema9_rate_30s"]==0.0)
    last=rows[-1]
    return {"name":"pid3216_actual_ultra_160950_hover_terminal","kind":"DETECTOR",
            "expected":{"terminal":True,"mature_by_comparison":False},"actual":actual,"pass":passed,
            "points":pts([(float(last["btc_price"]),float(last["ema9"]))],77794.24)}


def fixture_case(name):
    return json.loads(PID8868_FIXTURE.read_text(encoding="utf-8"))["cases"][name]


def fixture_snapshot(name):
    c=fixture_case(name)
    return MarketSnapshot(now_ts=c["now_ts"],ticker=c["ticker"],contract_age_s=c["contract_age_s"],
        yes_ask=c["yes_ask"],no_ask=c["no_ask"],quote_current=c["quote_current"],depth_available=c["depth_available"],
        metadata=c["metadata"],yes_bid=c["yes_bid"],no_bid=c["no_bid"],entry_allowed=c["entry_allowed"],
        yes_sell_allowed=c["yes_sell_allowed"],no_sell_allowed=c["no_sell_allowed"])


def fixture_intents(name):
    out=[]
    for raw in fixture_case(name).get("adviser_intents") or []:
        out.append(ToolIntent(tool=raw["tool"],territory_id=raw["territory_id"],lane=Lane(raw["lane"]),
            side=Side(raw["side"]) if raw.get("side") else None,action=Action(raw["action"]),
            opportunity_id=raw.get("opportunity_id"),max_price=raw.get("max_price"),size_tier=raw.get("size_tier"),
            reason=raw["reason"],source_time=raw["source_time"],expires_when=raw.get("expires_when"),
            metadata=raw.get("metadata") or {}))
    return out


def pid8868_cases():
    out=[]
    top=fixture_snapshot("current_terminal_top")
    cg=top.metadata.get("current_geometry") or {}; tpg=top.metadata.get("tp_geometry") or {}
    out.append(entry_result("pid8868_partial_top_preserves_factory_no_but_shared_waits",top,"WAIT",None,
        pts([(float(cg.get("btc_price") or 0),float(cg.get("ema9") or 0))],float(tpg.get("target") or 0)),
        fixture_intents("current_terminal_top"),factory_action="ENTER",factory_side="NO",
        scope="IMMUTABLE_PARTIAL_RECORDED_WRAPPER_WITHOUT_CURRENT_SOURCE_PROOF"))

    stale=fixture_snapshot("stale_cheap_hover")
    cg=stale.metadata.get("current_geometry") or {}; tpg=stale.metadata.get("tp_geometry") or {}
    out.append(entry_result("pid8868_stale_cheap_hover_remains_wait",stale,"WAIT",None,
        pts([(float(cg.get("btc_price") or 0),float(cg.get("ema9") or 0))],float(tpg.get("target") or 0)),
        fixture_intents("stale_cheap_hover"),factory_action="WAIT",
        scope="IMMUTABLE_PARTIAL_RECORDED_WRAPPER_WITHOUT_CURRENT_SOURCE_PROOF"))

    roll=fixture_snapshot("rollover_target_reachable")
    cg=roll.metadata.get("current_geometry") or {}; tpg=roll.metadata.get("tp_geometry") or {}
    out.append(entry_result("pid8868_partial_rollover_preserves_factory_no38_but_shared_waits",roll,"WAIT",None,
        pts([(float(cg.get("btc_price") or 0),float(cg.get("ema9") or 0))],float(tpg.get("target") or 0)),
        fixture_intents("rollover_target_reachable"),factory_action="ENTER",factory_side="NO",
        scope="IMMUTABLE_PARTIAL_RECORDED_WRAPPER_WITHOUT_CURRENT_SOURCE_PROOF"))

    ex=fixture_snapshot("current_terminal_held_no_exit")
    pos={"position_id":"P-PID8868","ticker":ex.ticker,"territory_id":"M","opportunity_id":"O",
         "tool":"ONE_COMMANDER_PRIMARY","lane":"MAIN","side":Side.NO,"entry_price":.17,
         "entry_time":ex.now_ts-300.0,"close_ts":fixture_case("current_terminal_held_no_exit")["close_ts"],
         "custody_state":"NORMAL","entry_metadata":{"commander_physical_evidence":{"edge_id":"OLDER-TOP:1793494300000"}},
         "floor_bid":None}
    cg=ex.metadata.get("current_geometry") or {}; tpg=ex.metadata.get("tp_geometry") or {}
    out.append(position_result("pid8868_actual_current_no_terminal_exits",ex,pos,"EXIT",
        pts([(float(cg.get("btc_price") or 0),float(cg.get("ema9") or 0))],float(tpg.get("target") or 0))))
    return out



def pid23072_cases():
    fixture = json.loads(PID23072_CONTROL_FIXTURE.read_text(encoding="utf-8"))
    controls = fixture["controls"]
    with gzip.open(PID23072_PHYSICAL_FIXTURE, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    epochs = [float(row["epoch_ms"]) for row in rows]
    out = []
    for control in controls:
        stop = bisect.bisect_right(epochs, float(control["source_epoch_ms"]))
        if stop <= 0:
            raise RuntimeError(f"PID23072 trade #{control['trade_number']} has no causal source history")
        history = rows[:stop]
        current = history[-1]
        mg = detect_mountain_geometry(history).tool_metadata()
        cross = ema9_ema30_cross_context(history)
        btc = float(current["btc_price"]); target = float(control["target"])
        ema9 = float(current["ema9"]); ema30 = float(current["ema30"])
        tpg = {
            "target": target,
            "contract_ownership": control["old_contract_ownership"],
            "contract_ownership_side": control["old_contract_ownership_side"],
            "target_between_ema9_ema30": min(ema9, ema30) <= target <= max(ema9, ema30),
            "required_move_to_target_btc": abs(btc - target),
            "observed_target_side": "YES" if btc >= target else "NO",
            "remaining_seconds": float(control["market_close_ts"]) - float(control["entry_time"]),
            "comparable_parent_amplitude_btc": (mg.get("parent_structure") or {}).get("parent_amplitude"),
        }
        entry_side = Side(control["side"]); entry_price = float(control["entry_price"])
        yes_ask = entry_price if entry_side is Side.YES else 1.0 - entry_price
        no_ask = entry_price if entry_side is Side.NO else 1.0 - entry_price
        owner = mg.get("owner_side")
        snapshot = MarketSnapshot(
            now_ts=float(control["entry_time"]), ticker=control["ticker"],
            contract_age_s=float(control["entry_time"]) - float(control["market_open_ts"]),
            yes_ask=yes_ask, no_ask=no_ask, yes_bid=max(.001, yes_ask-.01), no_bid=max(.001, no_ask-.01),
            metadata={
                "physical_current": True, "geometry_last_epoch_ms": float(current["epoch_ms"]),
                "geometry_continuity_generation": 1, "mountain": mg, "tp_geometry": tpg,
                "ema9_ema30_cross_context": cross, "current_geometry": current,
                "commander_strategy": {"owned_territory":"ALTERNATING_MOUNTAIN",
                                       "owned_side":owner,"active_tool":"ALTERNATING_MOUNTAIN"},
            },
        )
        native=factory_candidates(snapshot)
        commander = OneCommander(); candidates = commander.physical_entry_candidates(snapshot)
        d = commander.decide(list(candidates), snapshot)
        actual = {
            "action": d.action.value,
            "side": d.intent.side.value if d.intent and d.intent.side else None,
            "reason": d.reason,
            "gap_stage": ((cross.get("gap_lifecycle") or {}).get("stage")),
            "gap_age_s": ((cross.get("gap_lifecycle") or {}).get("age_seconds_since_observed_cross")),
            "mountain_owner": mg.get("owner_side"),
            "mountain_phase": (mg.get("diagnostics") or {}).get("phase"),
            "terminal": mg.get("terminal_evidence_qualified"),
            "return_leg_count": len((mg.get("return_leg_reference") or {}).get("legs") or []),
            "candidate_families": [i.metadata.get("commander_candidate_family") for i in candidates],
            "physical_factory_action": "ENTER" if native else "WAIT",
            "shared_quality_reason": d.reason,
        }
        # The sealed historical factory labels remain a separate control.
        # #9/#10 lack independent terminal maturity under the new shared gate.
        expected_action="WAIT" if control["trade_number"] in (9,10) else control["expected_action"]
        expected_side = control["side"] if expected_action == "ENTER" else None
        passed = (actual["action"] == expected_action and actual["side"] == expected_side
                  and actual["physical_factory_action"] == control["expected_action"])
        if control["trade_number"] in (9,10):
            passed = passed and d.reason == "OPPORTUNITY_MOUNTAIN_PARENT_TERMINAL_PROOF_REQUIRED"
        tail = history[max(0, len(history)-80):]
        points = [{"t":i,"btc":float(row["btc_price"]),"ema9":float(row["ema9"]),"tp":target}
                  for i,row in enumerate(tail)]
        out.append({
            "name": f"pid23072_trade{control['trade_number']}_causal_prefix_factory_and_shared_quality",
            "kind": "CAUSAL_PHYSICAL_PREFIX_CLASSIFICATION",
            "input_scope": "RECORDED_GEOMETRY_PREFIX_AND_CONTRACT_VALUES_WITH_RECONSTRUCTED_PRICE_CONTROL_NOT_NATIVE_BOOK_REPLAY",
            "historical_factory_control_label": control["control_label"],
            "expected": {"action":expected_action,"side":expected_side,
                         "physical_factory_action":control["expected_action"]},
            "actual": actual,
            "pass": passed,
            "points": points,
        })
    return out


def operator_authorized_profit_floor_case():
    ticker = "KX-AUTHORIZED-120-FLOOR-CONSTRUCT"
    enter = synthetic_terminal_snapshot(side=Side.NO,ask=.13,t=1000.,age=300.,ticker=ticker)
    commander = OneCommander()
    accepted = commander.decide_entry(commander.physical_entry_candidates(enter),enter,{})
    if accepted.action is not Action.ENTER:
        raise RuntimeError(f"Explicit synthetic floor premise was not admitted: {accepted}")
    candidate = accepted.intent
    raw = candidate.metadata["floor_policy"]
    policy = FloorPolicy(
        arm_roi=raw["arm_roi"], trail_fraction=raw["trail_fraction"],
        min_age_seconds=raw.get("min_age_s",0.0), immediate_arm_roi=raw.get("immediate_arm_roi"),
        first_arm_allowed=raw.get("first_arm_allowed",True),
        first_arm_from_current_bid=raw.get("first_arm_from_current_bid",False),
        roi_trail_tiers=tuple(tuple(x) for x in raw.get("roi_trail_tiers",())),
    )
    entry_book = PaperBook(ticker=ticker,quote_id="ENTRY",observed_ts=1000,exchange_ts=1000,
        yes_bids=(PriceLevel(.87,1000),),no_bids=(PriceLevel(.12,1000),),close_ts=1900,
        current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
        provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                    "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
    actual={"entry":None,"floor_at_120pct_peak":None,"breach_below_floor":None}
    ok=True
    with tempfile.TemporaryDirectory() as td, PaperExecutioner(td) as ex:
        receipt=ex.execute(accepted,entry_book,now_ts=1000,command_id="ENTRY")
        actual["entry"]=receipt.status; ok = receipt.status == "BOOKED"
        peak=PaperBook(ticker=ticker,quote_id="PEAK120",observed_ts=1010,exchange_ts=1010,
            yes_bids=(PriceLevel(.704,1000),),no_bids=(PriceLevel(.286,1000),),close_ts=1900,
            current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
            provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                        "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
        obs=ex.observe_floors(peak,now_ts=1010,policies={receipt.position_id:policy},position_ids=(receipt.position_id,))[0]
        actual["floor_at_120pct_peak"] = ex.positions[receipt.position_id].floor_bid
        ok = ok and not obs.breached and abs(float(actual["floor_at_120pct_peak"]) - .2717) < 1e-9
        protect=PaperBook(ticker=ticker,quote_id="PROTECT",observed_ts=1011,exchange_ts=1011,
            yes_bids=(PriceLevel(.72,1000),),no_bids=(PriceLevel(.27,1000),),close_ts=1900,
            current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
            provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                        "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
        obs=ex.observe_floors(protect,now_ts=1011,policies={receipt.position_id:policy},position_ids=(receipt.position_id,))[0]
        actual["breach_below_floor"] = obs.breached
        ok = ok and obs.breached
    return {"name":"operator_authorized_120pct_profit_lock_blocks_giveback","kind":"FLOOR_EXECUTION",
            "expected":{"entry":"BOOKED","floor_at_120pct_peak":.2717,"breach_below_floor":True},
            "actual":actual,"pass":ok,"points":pts([(130,128),(118,116),(102,104),(100,102)],115)}


def sideways_no_terrain_3pct_floor_case():
    ticker = "KX-SIDEWAYS-NO-TERRAIN-120-CONSTRUCT"
    enter = synthetic_terminal_snapshot(side=Side.NO,ask=.13,t=1000.,age=300.,ticker=ticker)
    commander = OneCommander()
    accepted = commander.decide_entry(commander.physical_entry_candidates(enter),enter,{})
    if accepted.action is not Action.ENTER:
        raise RuntimeError(f"Explicit synthetic floor premise was not admitted: {accepted}")
    candidate = accepted.intent
    flat = snap(t=1010,ticker=ticker,contract_age=310,yes_ask=.70,no_ask=.30,yes_bid=.704,no_bid=.286,
                mountain=mountain(side="NO",terminal=False,edge="FLAT"),
                tp={"target_between_ema9_ema30":False},
                meta={
                    "commander_strategy":{"owned_territory":"UNKNOWN","owned_side":None,"active_tool":None},
                    "tool_rack":{"owned_territory":"UNKNOWN","owned_side":None},
                    "heist":{"qualified_box":False,"diagnostics":{"sideways_enough":True}},
                })
    raw = floor_policy(SimpleNamespace(edge_only_custody=True),position=None,snapshot=flat)
    policy = FloorPolicy(
        arm_roi=raw["arm_roi"], trail_fraction=raw["trail_fraction"],
        min_age_seconds=raw.get("min_age_s",0.0), immediate_arm_roi=raw.get("immediate_arm_roi"),
        first_arm_allowed=raw.get("first_arm_allowed",True),
        first_arm_from_current_bid=raw.get("first_arm_from_current_bid",False),
        roi_trail_tiers=tuple(tuple(x) for x in raw.get("roi_trail_tiers",())),
    )
    entry_book = PaperBook(ticker=ticker,quote_id="ENTRY",observed_ts=1000,exchange_ts=1000,
        yes_bids=(PriceLevel(.87,1000),),no_bids=(PriceLevel(.12,1000),),close_ts=1900,
        current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
        provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                    "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
    actual={"entry":None,"policy_revision":raw.get("profit_policy_revision"),
            "floor_at_120pct_peak":None,"breach_below_floor":None}
    ok=True
    with tempfile.TemporaryDirectory() as td, PaperExecutioner(td) as ex:
        receipt=ex.execute(accepted,entry_book,now_ts=1000,command_id="ENTRY")
        actual["entry"]=receipt.status; ok = receipt.status == "BOOKED"
        peak=PaperBook(ticker=ticker,quote_id="PEAK120",observed_ts=1010,exchange_ts=1010,
            yes_bids=(PriceLevel(.704,1000),),no_bids=(PriceLevel(.286,1000),),close_ts=1900,
            current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
            provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                        "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
        obs=ex.observe_floors(peak,now_ts=1010,policies={receipt.position_id:policy},position_ids=(receipt.position_id,))[0]
        actual["floor_at_120pct_peak"] = ex.positions[receipt.position_id].floor_bid
        ok = ok and not obs.breached and abs(float(actual["floor_at_120pct_peak"]) - .27742) < 1e-9
        protect=PaperBook(ticker=ticker,quote_id="PROTECT",observed_ts=1011,exchange_ts=1011,
            yes_bids=(PriceLevel(.723,1000),),no_bids=(PriceLevel(.277,1000),),close_ts=1900,
            current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
            provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                        "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
        obs=ex.observe_floors(protect,now_ts=1011,policies={receipt.position_id:policy},position_ids=(receipt.position_id,))[0]
        actual["breach_below_floor"] = obs.breached
        ok = ok and obs.breached and raw.get("roi_trail_tiers") == [[1.0,.03]]
    return {"name":"sideways_no_terrain_120pct_uses_3pct_peak_lock","kind":"FLOOR_EXECUTION",
            "expected":{"entry":"BOOKED","policy_revision":"OPERATOR_AUTHORIZED_SIDEWAYS_NO_TERRAIN_100_3_V1",
                        "floor_at_120pct_peak":.27742,"breach_below_floor":True},
            "actual":actual,"pass":ok,"points":pts([(130,128),(118,116),(102,104),(100,102)],115)}


def pid22736_cases():
    fixture=ROOT/"tests"/"tool_rack"/"fixtures"/"pid22736_geometry.jsonl"
    rows=[json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines()]
    specs=[
        ("pid22736_1_false_rail_midleg_wait",1793478732.3156896,77439.48,.56,.44),
        ("pid22736_2_ema_tp_junction_wait",1793479151.316993,77439.48,.78,.23),
        ("pid22736_3_no_midleg_45c_wait",1793479544.2206347,77435.26,.55,.45),
        ("pid22736_4_down_parent_no_yes39",1793479953.1968653,77435.26,.39,.61),
        ("pid22736_5_expanding_down_no_yes20",1793480134.8673508,77435.26,.20,.80),
    ]
    out=[]
    for name,ts,target,ya,na in specs:
        causal=[r for r in rows if r["epoch_ms"]<=ts*1000]
        last=causal[-1]; det=detect_mountain_geometry(causal); md=det.tool_metadata()
        pre=MarketSnapshot(now_ts=ts,ticker="KX-PID22736",contract_age_s=300,yes_ask=ya,no_ask=na,
                           metadata={"physical_current":True,"geometry_last_epoch_ms":last["epoch_ms"],
                                     "geometry_continuity_generation":1,"current_geometry":last,
                                     "mission_context":{"contract":{"target":target,"remaining_seconds":600}},
                                     "commander_strategy":{"owned_territory":"ALTERNATING_MOUNTAIN",
                                                           "owned_side":md.get("owner_side"),"active_tool":"ALTERNATING_MOUNTAIN"},
                                     "mountain":md})
        tpg=build_tp_geometry(pre)
        s=MarketSnapshot(**{**pre.__dict__,"metadata":{**pre.metadata,"tp_geometry":tpg}})
        p=[]
        for row in causal[-140::20] or causal[-1:]:
            p.append({"t":row["epoch_ms"]/1000,"btc":float(row["btc_price"]),"ema9":float(row["ema9"]),"tp":target})
        out.append(entry_result(name,s,"WAIT",None,p))
    return out


def execution_case():
    ticker="KX-CONSTRUCT-END2END"
    c=OneCommander()
    top=synthetic_terminal_snapshot(side=Side.NO,ask=.19,t=1000.,age=300.,
                                    ticker=ticker,edge="TOP:1000000")
    primary=c.physical_entry_candidates(top); enter=c.decide_entry(list(primary),top,{})
    actual={"entry_decision":enter.action.value,"entry_receipt":None,"same_edge":None,
            "exit_decision":None,"exit_receipt":None,"events":[]}
    ok=enter.action is Action.ENTER
    if ok:
        book1=PaperBook(ticker=ticker,quote_id="Q1",observed_ts=1000,exchange_ts=1000,
            yes_bids=(PriceLevel(.81,1000),),no_bids=(PriceLevel(.18,1000),),close_ts=1900,
            current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
            provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                        "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
        with tempfile.TemporaryDirectory() as td, PaperExecutioner(td) as ex:
            rec1=ex.execute(enter,book1,now_ts=1000,command_id="ENTRY")
            actual["entry_receipt"]=rec1.status; ok = ok and rec1.status=="BOOKED" and len(ex.positions)==1
            if ex.positions:
                p=asdict(next(iter(ex.positions.values()))); p["side"]=Side(p["side"]); p["lane"]=p["lane"].value
                same=snap(t=1001,ticker=ticker,btc=75999,ema9=76001,ema30=76008,target=76030,
                    yes_ask=.80,no_ask=.21,yes_bid=.79,no_bid=.20,contract_age=301,
                    mountain=mountain(side="NO",terminal=True,edge="TOP:1000000"),tp=tp(target=76030,btc=75999))
                hold=c.decide_position([],same,p); actual["same_edge"]=hold.action.value; ok = ok and hold.action is Action.HOLD
                bottom=snap(t=1120,ticker=ticker,btc=75880,ema9=75882,ema30=75890,target=76030,
                    yes_ask=.30,no_ask=.70,yes_bid=.29,no_bid=.69,contract_age=420,
                    mountain=mountain(side="NO",terminal=True,edge="BOTTOM:1120000"),tp=tp(target=76030,btc=75880))
                exit_d=c.decide_position([],bottom,p); actual["exit_decision"]=exit_d.action.value; ok = ok and exit_d.action is Action.EXIT
                book2=PaperBook(ticker=ticker,quote_id="Q2",observed_ts=1120,exchange_ts=1120,
                    yes_bids=(PriceLevel(.29,1000),),no_bids=(PriceLevel(.69,1000),),close_ts=1900,
                    current=True,entry_allowed=True,yes_sell_allowed=True,no_sell_allowed=True,
                    provenance={"sequence_checked":True,"snapshot_verified":True,"monotonic_receive_fresh":True,
                                "receive_age_seconds":0.0,"exchange_timestamp_known":True,"exchange_age_seconds":0.0})
                rec2=ex.execute(exit_d,book2,now_ts=1120,command_id="EXIT",position_id=rec1.position_id)
                actual["exit_receipt"]=rec2.status; actual["events"]=[e["event"] for e in ex.events]
                ok = ok and rec2.status=="EXITED" and not ex.positions and actual["events"]==["ENTRY","EXIT"]
    return {"name":"paper_execution_entry_hold_exit_committed","kind":"EXECUTION",
            "expected":{"entry":"BOOKED","same_edge":"HOLD","exit":"EXITED","events":["ENTRY","EXIT"]},
            "actual":actual,"pass":ok,"points":pts([(76000,75995),(75999,76001),(75880,75882)],76030)}


def prehalf_detector_case():
    # Synthetic alternating history: completed UP arcs are ~180-200s / 20 units.
    # Current UP arc is only 70s / 8 units (< half on both dimensions) and may
    # visibly hesitate; it must not be promoted to a peak.
    def r(arc_id,direction,epoch_ms,age,btc,phase,amplitude):
        sign=1 if direction=="UP" else -1
        return {"arc_id":arc_id,"arc_direction":direction,"epoch_ms":epoch_ms,"arc_age_sec":age,
                "btc_price":btc,"ema9":btc-sign*20,"ema30":btc-sign*30,"arc_phase":phase,
                "arc_amplitude":amplitude,"arc_prominence_threshold":5.0,"range60":100.0,
                "struct_slope3m":sign*1.0,"struct_slope6m":sign*1.2}
    def completed(arc_id,direction,start_ms,duration,base):
        sign=1 if direction=="UP" else -1
        out=[]
        for age in range(0,duration+1,5):
            item=r(arc_id,direction,start_ms+age*1000,age,base+sign*40*age/duration,
                   "ROLLING" if age==duration else "BUILDING",20.0)
            item["ema9"]=base+sign*40*age/duration
            out.append(item)
        return out
    rows=[]; t=0
    specs=[("A1","UP",180,1000),("A2","DOWN",190,1040),("A3","UP",170,1005),
           ("A4","DOWN",180,1045),("A5","UP",200,1010),("A6","DOWN",170,1050)]
    for arc_id,direction,duration,base in specs:
        rows.extend(completed(arc_id,direction,t,duration,base)); t+=(duration+5)*1000
    # Five-second current observations with arc_amplitude never above 8.
    for age in range(0,71,5):
        btc=1015 + min(age,60)*(7/60)
        amp=min(8.0,age*(8/70))
        item=r("A7","UP",t+age*1000,age,btc,"CREST_FORMING" if age>=60 else "BUILDING",amp)
        item["ema9"]=995 + .18*age
        rows.append(item)
    det=detect_mountain_geometry(rows); scale=det.diagnostics.get("scale_progress") or {}
    actual={"mature_edge":det.mature_edge,"terminal":det.diagnostics.get("terminal_evidence_qualified"),
            "duration_ratio":scale.get("duration_ratio_to_comparable_mean"),
            "amplitude_ratio":scale.get("amplitude_ratio_to_comparable_mean"),
            "prehalf_scale_veto":scale.get("prehalf_scale_veto")}
    ok=(actual["prehalf_scale_veto"] is True and actual["mature_edge"] is False and actual["terminal"] is False
        and actual["duration_ratio"] is not None and actual["duration_ratio"]<.5
        and actual["amplitude_ratio"] is not None and actual["amplitude_ratio"]<.5)
    return {"name":"prehalf_previous_arc_scale_not_peak","kind":"DETECTOR",
            "expected":{"mature_edge":False,"terminal":False,"prehalf_scale_veto":True},
            "actual":actual,"pass":ok,"points":pts([(1015,995),(1022,1005),(1022,1007)],1000)}



def pid2672_history_layer_skew_case():
    market={"ticker":"KXBTC15M-PID2672-SKEW","time":101.3,"close_ts":1000.0,"target":100.0,
            "btc":101.0,"e9":100.5,"e30":99.5,"fresh":True}
    lg=build_looking_glass(market,now_ts=100.0)
    row={"epoch_ms":101300.0,"btc_price":101.0,"ema9":100.5,"ema30":99.5,
         "arc_id":"A","arc_direction":"UP","arc_phase":"BUILDING","arc_age_sec":10.0,
         "arc_amplitude":1.0,"arc_prominence_threshold":1.0}
    ctx=MissionContext().observe({"current_geometry":row,"physical_current":True,"geometry_continuity_generation":0},
         ticker="KXBTC15M-PID2672-SKEW",open_ts=0.0,close_ts=900.0,target=100.0,now_ts=100.0,
         rows=[row],historical_candles=[])
    ok=(lg.get("status")!="STALE" and ctx.get("current") is True)
    return {"name":"pid2672_history_layers_accept_authorized_negative_clock_skew","kind":"SOURCE",
            "expected":{"looking_glass":"CURRENT","mission_context_current":True},
            "actual":{"looking_glass_status":lg.get("status"),"mission_context_current":ctx.get("current"),
                      "source_ms":ctx.get("source_ms")},"pass":ok,"points":pts([(101,100.5)],100)}


def pid2672_paired_gap_prepare_case():
    rows=[]
    for age in range(0,31,5):
        e9=100.0+age*.2
        rows.append({"arc_id":"PID2672-PAIR","arc_direction":"UP","epoch_ms":100000.0+age*1000.0,
                     "arc_age_sec":age,"btc_price":e9+10.0,"ema9":e9,"ema30":e9-20.0,
                     "arc_phase":"MATURE","arc_amplitude":age*.2,"arc_prominence_threshold":2.0,
                     "range60":20.0,"struct_slope3m":1.0,"struct_slope6m":1.2})
    paired={"eligible":True,"reference_count":2,"references":[],"matches":[{}],"selected_match":{},
            "current_pair":{},"current_slowdown":{"observed":True},"steep_observed":False,
            "gap_relative_tolerance":.18,"steepness_formula":"CONSTRUCT","shape_age_height_prerequisites":False,
            "measurement_calibration":"CONSTRUCT"}
    with patch("strategy_core.detectors.mountain_geometry._paired_gap_evidence",return_value=paired):
        out=detect_mountain_geometry(rows)
    actual={"mature_edge":out.mature_edge,"edge_window_active":out.edge_window_active,"stall":out.stall,
            "terminal":out.diagnostics.get("terminal_evidence_qualified"),
            "prepare_alert":out.diagnostics.get("paired_gap_prepare_alert"),
            "trade_authority":out.diagnostics.get("paired_gap_trade_authority")}
    ok=(actual["mature_edge"] is True and actual["edge_window_active"] is True and actual["prepare_alert"] is True
        and actual["trade_authority"] is False and actual["terminal"] is False)
    return {"name":"pid2672_paired_gap_is_briefing_prepare_not_paid_terminal","kind":"DETECTOR",
            "expected":{"prepare_alert":True,"trade_authority":False,"terminal":False},
            "actual":actual,"pass":ok,"points":pts([(110,100),(114,103),(116,106)],100)}


def _pid2672_tp_junction_snapshot(seconds_left):
    m={"qualified_alternating_mountain":True,"owner_side":"YES","current_arc_id":"G000A000059",
       "edge_id":"G000A000059:1793577901336","terminal_evidence_qualified":True,"mature_edge":True,
       "edge_window_active":True,"stall":True,"meaningful_retreat":True,"failed_reextension":False,
       "strong_active_release":False,"parent_structure":{"parent_id":"E000A000015","parent_side":"YES",
       "parent_age_s":1057.0,"parent_amplitude":134.1,"parent_terminal_ready":True,"parent_turning_or_flat":True,
       "slow_rolling_parent":False,"extended_parent":True,"child_arc_count":12},
       "diagnostics":{"current_age_s":10.3},
       "return_leg_reference":{"count":4,"median_amplitude_btc":26.06,"median_speed_btc_s":.316,
       "max_amplitude_btc":37.66,"max_speed_btc_s":.369}}
    return MarketSnapshot(now_ts=1793577902.27,ticker="KXBTC15M-PID2672-JUNCTION",
        contract_age_s=900.0-seconds_left,yes_ask=.85,no_ask=.16,yes_bid=.84,no_bid=.15,
        metadata={"physical_current":True,"geometry_last_epoch_ms":1793577902401.1,
          "current_geometry":{"btc_price":78323.15,"ema9":78296.06,"ema30":78211.13},
          "commander_strategy":{"owned_territory":"ALTERNATING_MOUNTAIN","owned_side":"YES","active_tool":"ALTERNATING_MOUNTAIN"},
          "mountain":m,"tp_geometry":{"target":78240.38,"btc":78323.15,"observed_target_side":"YES",
          "required_move_to_target_btc":82.77,"remaining_seconds":seconds_left,"contract_ownership":"BOUNCE_FAVORED",
          "contract_ownership_side":"NO","comparable_parent_amplitude_btc":237.138,"target_between_ema9_ema30":True}})


def pid2672_tp_junction_case(*,late=False):
    sl=299.0 if late else 597.73
    s=_pid2672_tp_junction_snapshot(sl)
    # This archived-style wrapper has neither current geometry epoch nor
    # continuity/receipt provenance. Keep its native species rule visible,
    # but do not invent missing current-source proof for shared admission.
    intents=factory_candidates(s)
    shared=OneCommander().decide_entry(intents,s,{})
    if late:
        actual={"candidate_count":len(intents),"seconds_left":sl,"shared_action":shared.action.value}
        ok=(len(intents)==0 and shared.action is Action.WAIT)
        return {"name":"pid2672_tp_junction_remains_hard_late","kind":"ENTRY",
                "expected":{"action":"WAIT"},"actual":actual,"pass":ok,
                "points":pts([(78260,78250),(78323,78296)],78240.38)}
    i=intents[0] if intents else None
    ev=((i.metadata.get("commander_physical_evidence") or {}) if i else {})
    j=ev.get("tp_junction_policy") or {}
    actual={"physical_factory_action":i.action.value if i else "WAIT","factory_side":i.side.value if i and i.side else None,
            "reason":i.reason if i else None,"junction_basis":j.get("basis"),"runway_override":j.get("runway_override")}
    actual.update(action=shared.action.value,shared_reason=shared.reason)
    ok=(i is not None and i.action is Action.ENTER and i.side is Side.NO
        and j.get("basis")=="TP_JUNCTION_ADVISORY_EARLY_BOUNCE_FAVORED_PARENT_SCALE" and j.get("runway_override") is True
        and shared.action is Action.WAIT and shared.reason=="OPPORTUNITY_CURRENT_SOURCE_PROOF_REQUIRED")
    return {"name":"pid2672_partial_junction_preserves_factory_bounce_but_shared_waits","kind":"PARTIAL_SOURCE_CLASSIFICATION",
            "input_scope":"UNCHANGED_PARTIAL_WRAPPER_WITHOUT_CURRENT_SOURCE_PROOF",
            "expected":{"action":"WAIT","physical_factory_action":"ENTER","factory_side":"NO"},"actual":actual,"pass":ok,
            "points":pts([(78260,78250),(78323,78296)],78240.38)}


def pid2672_rail_ema9_dip_case(*,ask=.20):
    now=1793582215.81
    s=MarketSnapshot(now_ts=now,ticker="KXBTC15M-PID2672-RAIL",contract_age_s=95.0,
        yes_ask=ask,no_ask=.81,yes_bid=.19,no_bid=.80,metadata={
        "source":"DIRECT_BTC_AND_NATIVE_KALSHI",
        "current_geometry":{"btc_price":78212.50,"ema9":78257.24,"ema30":78158.25,
                            "arc_direction":"DOWN","parent_direction":"UP","btc_change30":-27.19,"ema9_change30":-5.44},
        "mountain":{"parent_structure":{"parent_side":"YES","parent_age_s":937.4,
                    "parent_terminal_ready":False,"slow_rolling_parent":True}},
        "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"MATURE","current_side":"YES",
                    "continued_on_latest_cross_side":True,"age_seconds_since_observed_cross":900.08}},
        "mission_context":{"contract":{"target":78300.0,"history_status":"READY",
                    "reference_window":{"completed_prior_contracts":2}}}})
    rail=RailTool(territory_id="UP_RAIL_PID2672",side=Side.YES,activated_at=now-30.0)
    i=list(rail.on_activate(s))[0]
    actual={"action":i.action.value,"side":i.side.value if i.side else None,"reason":i.reason,"max_price":i.max_price}
    if ask < .40:
        ok=(i.action is Action.ENTER and i.side is Side.YES and i.reason=="RAIL_EMA9_DIP_VALUE" and abs((i.max_price or 0)-.399)<1e-9)
        name=("pid2672_established_up_rail_ema9_dip_yes20_enters" if ask<=.20
              else "pid2672_rail_ema9_dip_yes21_enters_under_authorized_hard_cap")
        expected={"action":"ENTER","side":"YES"}
    else:
        ok=(i.action is Action.WAIT and "ABOVE_MAX_0.399" in i.reason)
        name="pid2672_rail_ema9_dip_yes40_waits"; expected={"action":"WAIT"}
    shared=OneCommander().decide_entry([i],s,{})
    actual.update(specialist_action=actual["action"],specialist_side=actual["side"],
                  side=None,action=shared.action.value,shared_reason=shared.reason)
    expected={"specialist_action":expected["action"],"action":"WAIT"}
    ok=ok and shared.action is Action.WAIT
    return {"name":name+"_specialist_only_shared_waits","kind":"SPECIALIST_CLASSIFICATION_WITH_SHARED_WAIT",
            "input_scope":"UNCHANGED_PARTIAL_WRAPPER_WITHOUT_CURRENT_SOURCE_PROOF",
            "expected":expected,"actual":actual,"pass":ok,
            "points":pts([(78290,78275),(78213,78257)],78300)}


def _authorized_heist_meta(*, zone, btc6, ema6, qualified=False, release=False,
                           lower_visits=1, upper_visits=1, centers=1, t=1000.0):
    return {
        "release_in_progress": release,
        "current_geometry":{"epoch_ms":t*1000.0,"btc_change6":btc6,"ema9_change6":ema6,
                            "ema_gap":1.0,"range180":80.0,"ema30_slope3m":1.0},
        "heist":{"qualified_box":qualified,"at_upper_edge":zone=="UPPER","at_lower_edge":zone=="LOWER",
                 "current_zone":zone,"box_id":"B1","visit_id":"L1" if zone=="LOWER" else "U1" if zone=="UPPER" else None,
                 "lower":100.0,"upper":140.0,"edge_tolerance":5.0,
                 "lower_visits":lower_visits,"upper_visits":upper_visits,"center_traversals":centers,
                 "repeatability_proof":{"observed_span_s":360.0},
                 "diagnostics":{"heist_environment":True,"parallel_emas":True,"minimum_box_range":20.0}},
        "mountain":{"owner_side":"YES","parent_structure":{"parent_terminal_ready":True,
                    "extended_parent":False,"slow_rolling_parent":False}},
        "tp_geometry":{"target_between_ema9_ema30":False,"observed_target_side":"YES",
                       "remaining_seconds":600.0,"required_move_to_target_btc":10.0},
    }


def authorized_heist_overlay_case():
    rack=ToolRackController()
    first=snap(t=1000,yes_ask=.19,no_ask=.81,meta=_authorized_heist_meta(
        zone="LOWER",btc6=-3,ema6=-1,qualified=False,t=1000))
    r1=rack.observe(PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES),first)
    second=snap(t=1001,yes_ask=.19,no_ask=.81,meta=_authorized_heist_meta(
        zone="INNER",btc6=3,ema6=1,qualified=False,t=1001))
    r2=rack.observe(PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES),second)
    entry=next((i for i in r2.commander_intents if i.tool=="MARKET_HEIST" and i.action is Action.ENTER),None)
    actual={"owner":r2.owned_territory.value,"armed_overlay":"MARKET_HEIST" in r1.active_overlays,
            "entry":entry.action.value if entry else "WAIT","side":entry.side.value if entry and entry.side else None,
            "reason":entry.reason if entry else None}
    ok=(r1.owned_territory is Territory.ALTERNATING_MOUNTAIN and actual["armed_overlay"]
        and entry is not None and entry.side is Side.YES
        and entry.reason=="HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED")
    return {"name":"authorized_parallel_heist_overlay_survives_mountain_and_enters_return","kind":"HEIST_OVERLAY",
            "expected":{"owner":"ALTERNATING_MOUNTAIN","entry":"ENTER","side":"YES"},"actual":actual,"pass":ok,
            "points":pts([(110,105),(100,102),(106,104)],105)}


def authorized_heist_primary_flicker_case():
    rack=ToolRackController()
    first=snap(t=1000,yes_ask=.19,no_ask=.81,meta=_authorized_heist_meta(
        zone="LOWER",btc6=-3,ema6=-1,qualified=True,t=1000))
    rack.observe(PhysicalEvidence(qualified_heist=True,ema9_direction=Side.YES),first)
    second=snap(t=1001,yes_ask=.19,no_ask=.81,meta=_authorized_heist_meta(
        zone="INNER",btc6=3,ema6=1,qualified=False,t=1001))
    r=rack.observe(PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES),second)
    entry=next((i for i in r.commander_intents if i.tool=="MARKET_HEIST" and i.action is Action.ENTER),None)
    actual={"owner":r.owned_territory.value,"ownership_reason":r.ownership_reason,
            "entry":entry.action.value if entry else "WAIT","side":entry.side.value if entry and entry.side else None}
    ok=(r.owned_territory is Territory.MARKET_HEIST
        and r.ownership_reason=="HEIST_ARMED_RETURN_PERSISTS_THROUGH_CLASSIFIER_FLICKER"
        and entry is not None and entry.side is Side.YES)
    return {"name":"authorized_heist_arm_survives_classifier_flicker","kind":"HEIST_OVERLAY",
            "expected":{"owner":"MARKET_HEIST","entry":"ENTER","side":"YES"},"actual":actual,"pass":ok,
            "points":pts([(110,105),(100,102),(106,104)],105)}


def authorized_release_overlay_case():
    rack=ToolRackController()
    rack.observe(PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES),
                 snap(t=1000,yes_ask=.85,no_ask=.15,meta={"mountain":{"owner_side":"YES"}}))
    second=snap(t=1001,yes_ask=.85,no_ask=.15,meta={"mountain":{"owner_side":"YES"},
                "current_geometry":{"epoch_ms":1001000.0}})
    ev=PhysicalEvidence(alternating_mountain=True,mountain_direction=Side.YES,
        release_candidate_side=Side.NO,release_boundary_break=True,release_directional_expansion=True,
        release_old_owner_failed_reextension=True)
    r=rack.observe(ev,second)
    rel=next((i for i in r.commander_intents if i.tool=="RELEASE_WATCHER" and i.action is Action.RELAY),None)
    actual={"handoff_confirmed":r.handoff_confirmed,"action":rel.action.value if rel else "WAIT",
            "side":rel.side.value if rel and rel.side else None}
    ok=(r.handoff_confirmed and rel is not None and rel.side is Side.NO)
    return {"name":"authorized_confirmed_release_overlay_books_handoff","kind":"RELEASE",
            "expected":{"action":"RELAY","side":"NO"},"actual":actual,"pass":ok,
            "points":pts([(110,108),(105,106),(97,101)],100)}


def authorized_three_cycle_pop_case():
    rack=ToolRackController(); ctx=None
    for idx,ticker in enumerate(("KX-A","KX-B","KX-C","KX-D")):
        md=_authorized_heist_meta(zone="INNER",btc6=0,ema6=0,qualified=True,
                                  lower_visits=2,upper_visits=2,centers=2,t=1000+idx)
        ctx=rack._update_heist_cycle_context(snap(ticker=ticker,t=1000+idx,meta=md))
    actual=dict(ctx or {})
    ok=(actual.get("consecutive_completed_pattern_contracts")==3 and actual.get("pop_prep") is True
        and actual.get("entry_authority") is False)
    return {"name":"authorized_three_heist_contracts_prepare_fourth_for_pop","kind":"BRIEFING",
            "expected":{"consecutive_completed_pattern_contracts":3,"pop_prep":True,"entry_authority":False},
            "actual":actual,"pass":ok,"points":pts([(100,100),(104,102),(100,100),(108,106)],100)}


def authorized_rollover_terminal_return_case(*, price=.49):
    mm=mountain(side="YES",terminal=True,edge="ROLLOVER-TERMINAL",current_age=120,parent_age=120,parent_amp=40)
    tpg={"contract_ownership":"BOUNCE_FAVORED","contract_ownership_side":"NO",
         "target_between_ema9_ema30":False,"observed_target_side":"YES",
         "required_move_to_target_btc":10.0,"remaining_seconds":880.0}
    s=snap(t=2000,contract_age=20,btc=110,ema9=108,ema30=100,target=100,
           yes_ask=1-price,no_ask=price,mountain=mm,tp=tpg)
    intents=OneCommander().physical_entry_candidates(s); i=intents[0] if intents else None
    actual={"action":i.action.value if i else "WAIT","side":i.side.value if i and i.side else None,
            "reason":i.reason if i else None,"max_price":i.max_price if i else None,
            "floor_policy":dict(i.metadata.get("floor_policy") or {}) if i else {}}
    should_enter=price < .50
    ok=(i is not None and i.side is Side.NO and i.reason=="COMMANDER_ROLLOVER_TERMINAL_RETURN_START"
        and actual["floor_policy"].get("immediate_arm_roi")==.40
        and actual["floor_policy"].get("trail_fraction")==.03) if should_enter else i is None
    return {"name":f"authorized_rollover_terminal_return_no_{int(round(price*100)):02d}","kind":"ENTRY",
            "expected":{"action":"ENTER" if should_enter else "WAIT","side":"NO" if should_enter else None},
            "actual":actual,"pass":ok,"points":pts([(112,109),(110,108)],100)}


def authorized_inherited_young_leg_rollover_continuation_case(*, price=.52):
    mm=mountain(side="YES",terminal=False,edge="ROLLOVER-CONTINUATION",current_age=500,parent_age=500,parent_amp=60)
    mm["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":.10,"owner_ema9_rate_btc_s":.04},
                          "60":{"covered":True,"owner_price_rate_btc_s":.06,"owner_ema9_rate_btc_s":.03}}
    mm["slowdown"]={"owner_price_retreat_observed":False}
    mm["diagnostics"]["phase"]="BUILDING"
    tpg={"contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"YES",
         "target_between_ema9_ema30":False,"observed_target_side":"YES",
         "required_move_to_target_btc":10.0,"remaining_seconds":880.0,
         "comparable_parent_amplitude_btc":60.0}
    meta={"current_geometry":{"ema_gap":12.0,"range60":40.0,"arc_phase":"BUILDING"},
          "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"SPROUT",
              "age_seconds_since_observed_cross":300.0,"current_side":"YES",
              "current_abs_gap_btc":12.0,"gap_expanding_6s":True}}}
    s=snap(t=2000,contract_age=20,btc=110,ema9=108,ema30=100,target=100,
           yes_ask=price,no_ask=1-price,mountain=mm,tp=tpg,meta=meta)
    intents=OneCommander().physical_entry_candidates(s); i=intents[0] if intents else None
    should_enter=price <= .55
    actual={"action":i.action.value if i else "WAIT","side":i.side.value if i and i.side else None,
            "reason":i.reason if i else None,"max_price":i.max_price if i else None,
            "size_tier":i.size_tier if i else None}
    ok=(i is not None and i.side is Side.YES and i.max_price==.55 and i.size_tier==25.0
        and i.reason=="COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION") if should_enter else i is None
    return {"name":f"authorized_inherited_young_leg_rollover_yes_{int(round(price*100)):02d}","kind":"ENTRY",
            "expected":{"action":"ENTER" if should_enter else "WAIT","side":"YES" if should_enter else None},
            "actual":actual,"pass":ok,"points":pts([(98,99),(104,102),(110,108)],100)}


def authorized_extended_top_sub20_return_case():
    mm=mountain(side="YES",terminal=False,edge="TOP-8C",current_age=700,parent_age=700,parent_amp=80,
                rolling=True,mature=True,window=True)
    # PID8552: a cheap aged peak alone is not permission; this control
    # represents an actually observed, qualified stalled terminal top.
    mm["terminal_evidence_qualified"]=True
    mm["stall"]=True
    mm.pop("edge_extreme_ms",None)
    s=snap(t=2600,contract_age=500,btc=120,ema9=118,ema30=105,target=100,
           yes_ask=.92,no_ask=.08,mountain=mm,tp={"target_between_ema9_ema30":False})
    intents=OneCommander().physical_entry_candidates(s); i=intents[0] if intents else None
    actual={"action":i.action.value if i else "WAIT","side":i.side.value if i and i.side else None,
            "reason":i.reason if i else None,"max_price":i.max_price if i else None}
    ok=(i is not None and i.side is Side.NO
        and i.reason=="COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN")
    return {"name":"authorized_extended_top_no_08_return_must_fire","kind":"ENTRY",
            "expected":{"action":"ENTER","side":"NO"},"actual":actual,"pass":ok,
            "points":pts([(100,103),(114,112),(120,118)],100)}


def authorized_quick_heist_floor_case():
    tool=MarketHeistTool(territory_id="H")
    list(tool.on_market_event(snap(t=1000,ticker="KX-HEIST-FLOOR",yes_ask=.19,no_ask=.81,
        meta=_authorized_heist_meta(zone="LOWER",btc6=-3,ema6=-1,t=1000))))
    i=list(tool.on_market_event(snap(t=1001,ticker="KX-HEIST-FLOOR",yes_ask=.19,no_ask=.81,
        meta=_authorized_heist_meta(zone="INNER",btc6=3,ema6=1,t=1001))))[0]
    raw=i.metadata.get("floor_policy") or {}
    # The specialist supplies the unchanged floor schedule. A separately
    # authored bilateral numeric box supplies shared admission authority.
    positive=real_heist_snapshot(t=1001.,age=300.)
    positive=replace(positive,ticker="KX-HEIST-FLOOR",yes_ask=.19,no_ask=.82,
                     yes_bid=.18,no_bid=.81)
    current=numeric_heist_intent(positive)
    current=replace(current,metadata={**current.metadata,"floor_policy":deepcopy(raw)})
    accepted=OneCommander().decide_entry([current],positive,{})
    if accepted.action is not Action.ENTER:
        raise RuntimeError(f"Explicit repeated-Heist floor premise was not admitted: {accepted}")
    policy=FloorPolicy(arm_roi=raw["arm_roi"],trail_fraction=raw["trail_fraction"],
        min_age_seconds=raw.get("min_age_s",0.0),immediate_arm_roi=raw.get("immediate_arm_roi"),
        first_arm_allowed=raw.get("first_arm_allowed",True),
        first_arm_from_current_bid=raw.get("first_arm_from_current_bid",False),
        roi_trail_tiers=tuple(tuple(x) for x in raw.get("roi_trail_tiers",())))
    actual={"entry":None,"floor_at_40pct":None,"revision":raw.get("profit_policy_revision")}; ok=True
    with tempfile.TemporaryDirectory() as td, PaperExecutioner(td) as ex:
        b=PaperBook("KX-HEIST-FLOOR","Q1",1001,1001,(PriceLevel(.18,1000),),(PriceLevel(.81,1000),),1900)
        receipt=ex.execute(accepted,b,now_ts=1001,command_id="E1")
        actual["entry"]=receipt.status; ok=receipt.status=="BOOKED"
        peak=PaperBook("KX-HEIST-FLOOR","Q2",1002,1002,(PriceLevel(.27,1000),),(PriceLevel(.72,1000),),1900)
        obs=ex.observe_floors(peak,now_ts=1002,policies={receipt.position_id:policy},position_ids=(receipt.position_id,))[0]
        actual["floor_at_40pct"]=obs.floor_bid
        ok=ok and obs.armed and abs((obs.floor_bid or 0)-.2619)<1e-9
    return {"name":"authorized_quick_heist_40pct_arms_3pct_peak_lock","kind":"FLOOR_EXECUTION",
            "expected":{"entry":"BOOKED","floor_at_40pct":.2619},"actual":actual,"pass":ok,
            "points":pts([(100,100),(104,103),(101,102)],100)}


def authorized_house_protection_case():
    engine=ToolRackPaperEngine.__new__(ToolRackPaperEngine)
    engine.executor=SimpleNamespace(events=[
        {"ticker":"KX-HOUSE","event":"EXIT","position_id":"1","gross_pnl":5,"cost":10},
        {"ticker":"KX-HOUSE","event":"EXIT","position_id":"2","gross_pnl":1,"cost":10},
    ])
    state=engine._contract_house_state("KX-HOUSE")
    s=snap(ticker="KX-HOUSE",yes_ask=.19,meta={"contract_house_state":state,
        "commander_strategy":{"owned_territory":"MARKET_HEIST","active_tool":"MARKET_HEIST"}})
    mountain_intent=ToolIntent(tool="ONE_COMMANDER_PRIMARY",territory_id="MOUNTAIN_EDGE",lane=Lane.MAIN,
        side=Side.YES,action=Action.ENTER,opportunity_id="M",max_price=.19,size_tier=10,
        reason="COMMANDER_MOUNTAIN_TRUE_EDGE_RETURN",source_time=s.now_ts,
        metadata={"commander_primary_candidate":True,"commander_candidate_family":"MOUNTAIN_EDGE"})
    heist_intent=ToolIntent(tool="MARKET_HEIST",territory_id="H",lane=Lane.TACTICAL,side=Side.YES,
        action=Action.ENTER,opportunity_id="H",max_price=.20,size_tier=10,
        reason="HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED",source_time=s.now_ts,
        metadata={"parallel_return_entry":True})
    good_heist=real_heist_snapshot(t=s.now_ts,age=s.contract_age_s)
    good_heist=replace(good_heist,ticker=s.ticker,yes_ask=.19,yes_bid=.18,
        metadata={**good_heist.metadata,"contract_house_state":state,
                  "commander_strategy":{"owned_territory":"MARKET_HEIST","active_tool":"MARKET_HEIST"}})
    d1=OneCommander().decide([mountain_intent],s); d2=OneCommander().decide([heist_intent],good_heist)
    actual={"house_mode":state.get("mode"),"mountain":d1.action.value,"mountain_reason":d1.reason,
            "heist":d2.action.value,"heist_side":d2.intent.side.value if d2.intent and d2.intent.side else None}
    ok=(state.get("mode")=="PROTECTED" and d1.action is Action.WAIT
        and d1.reason=="COMMANDER_HOUSE_PROTECTED_WAIT_NEXT_CONTRACT"
        and d2.action is Action.ENTER and d2.intent.side is Side.YES)
    return {"name":"authorized_house_protection_stands_down_nonheist_but_keeps_good_heist","kind":"HOUSE",
            "expected":{"house_mode":"PROTECTED","mountain":"WAIT","heist":"ENTER"},
            "actual":actual,"pass":ok,"points":pts([(100,100),(103,102),(101,101)],100)}


def authorized_high_profit_peak_hover_skim_case():
    mm=mountain(side="NO",terminal=False,edge="SKIM-HIGH")
    mm.update({"stall":True,"hesitation":False,"strong_active_release":False})
    s=snap(t=1200,ticker="KX-SKIM",yes_ask=.15,no_ask=.87,yes_bid=.14,no_bid=.86,
        mountain=mm,tp={"target_between_ema9_ema30":False},meta={
            "paper_exit_mark":{"current":True,"full_quantity_visible":True,"full_lot_bid":.86},
            "release_in_progress":False,
            "commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"}})
    pos={"position_id":"P1","ticker":"KX-SKIM","territory_id":"MOUNTAIN_CONTRACT_LEG",
         "opportunity_id":"O1","tool":"ONE_COMMANDER_PRIMARY","lane":"MAIN","side":Side.NO,
         "entry_price":.39,"entry_time":1000.0,"close_ts":1900.0,"custody_state":"NORMAL",
         "entry_metadata":{"commander_candidate_family":"MOUNTAIN_CONTRACT_LEG"},
         "peak_bid":.86,"protected_peak_bid":.86,"floor_bid":.817,"trail_fraction":.05}
    d=OneCommander().decide_position([],s,pos)
    actual={"action":d.action.value,"reason":d.intent.reason if d.intent else d.reason}
    ok=d.action is Action.EXIT and actual["reason"]=="COMMANDER_HIGH_PROFIT_PEAK_HOVER_COLLECT"
    return {"name":"authorized_120pct_exact_peak_hover_skims_before_floor","kind":"POSITION",
            "expected":{"action":"EXIT","reason":"COMMANDER_HIGH_PROFIT_PEAK_HOVER_COLLECT"},
            "actual":actual,"pass":ok,"points":pts([(100,100),(96,98),(94,96)],100)}

def authorized_heist_overlay_blocks_competing_quick_mountain_case():
    mm=mountain(side="YES",terminal=True,edge="QUICK-OVERLAP")
    s=snap(btc=110,ema9=108,ema30=100,target=100,yes_ask=.81,no_ask=.19,mountain=mm,
        tp={"target_between_ema9_ema30":False,"remaining_seconds":600.0},
        meta={"commander_strategy":{"owned_territory":"ALTERNATING_MOUNTAIN","owned_side":"YES",
              "active_tool":"ALTERNATING_MOUNTAIN","active_overlays":["MARKET_HEIST"]}})
    intents=OneCommander().physical_entry_candidates(s)
    actual={"candidate_count":len(intents)}; ok=len(intents)==0
    return {"name":"authorized_heist_overlay_owns_quick_return_not_competing_mountain","kind":"HIERARCHY",
            "expected":{"candidate_count":0},"actual":actual,"pass":ok,
            "points":pts([(110,108),(107,106),(109,107)],100)}


def pid1172_house_true_edge_case():
    m=mountain(side="YES",terminal=True,edge="PID1172-HOUSE")
    s=snap(btc=120,ema9=118,ema30=110,target=100,yes_ask=.85,no_ask=.15,
        mountain=m,tp=tp(target=100,btc=120),meta={"contract_house_state":{"mode":"PROTECTED"}})
    return entry_result("pid1172_house_protected_sub20_true_edge_still_enters",s,"ENTER","NO",
        pts([(112,110),(120,118)],100))


def pid1172_late_defer_case():
    m=mountain(side="NO",terminal=True,edge="PID1172-LATE")
    s=snap(contract_age=735,btc=80,ema9=82,ema30=90,target=100,yes_ask=.14,no_ask=.86,
        mountain=m,tp=tp(target=100,btc=80,comparable=20,observed="NO"))
    defer=ToolIntent(tool="ALTERNATING_MOUNTAIN",territory_id="M",lane=Lane.MAIN,side=Side.YES,
        action=Action.WAIT,opportunity_id=None,max_price=.20,size_tier=None,
        reason="MOUNTAIN_LATE_EDGE_DEFER_TO_NEXT_CONTRACT_CHEAP_VALUE",source_time=s.now_ts)
    return entry_result("pid1172_adviser_defer_does_not_veto_qualified_commander_return",s,"ENTER","YES",
        pts([(100,96),(88,86),(80,82)],100),(defer,))


def pid1172_far_tp_outlier_case():
    m=mountain(side="YES",terminal=True,edge="PID1172-OUTLIER")
    m["return_leg_reference"]={"count":3,"median_amplitude_btc":62.0,"median_speed_btc_s":.35,
        "max_amplitude_btc":533.0,"max_speed_btc_s":1.5,"legs":[
            {"arc_id":"A","btc_amplitude_btc":60.0,"duration_s":180.0,"average_btc_speed_btc_s":.333},
            {"arc_id":"B","btc_amplitude_btc":62.0,"duration_s":180.0,"average_btc_speed_btc_s":.344},
            {"arc_id":"C","btc_amplitude_btc":533.0,"duration_s":400.0,"average_btc_speed_btc_s":1.3325}]}
    t={"target_between_ema9_ema30":False,"observed_target_side":"YES",
       "required_move_to_target_btc":195.0,"remaining_seconds":600.0,
       "contract_ownership":"UNRESOLVED"}
    s=snap(contract_age=300,btc=295,ema9=290,ema30=250,target=100,yes_ask=.88,no_ask=.12,mountain=m,tp=t)
    return entry_result("pid1172_far_tp_single_outlier_does_not_authorize_return",s,"WAIT",None,
        pts([(250,245),(295,290)],100))


def pid1172_rail_price_case():
    md={"current_geometry":{"btc_price":105.0,"ema9":110.0,"ema30":100.0,"arc_direction":"DOWN",
                            "parent_direction":"UP"},
        "mountain":{"parent_structure":{"parent_side":"YES","parent_terminal_ready":False}},
        "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"MATURE","current_side":"YES"}}}
    s=MarketSnapshot(now_ts=1400,ticker="KX-R",contract_age_s=400,yes_ask=.399,no_ask=.601,
        yes_bid=.398,no_bid=.60,metadata=md)
    intent=list(RailTool(territory_id="R",side=Side.YES,activated_at=1000).on_market_event(s))[0]
    actual={"action":intent.action.value,"side":intent.side.value if intent.side else None,
            "reason":intent.reason,"max_price":intent.max_price}
    ok=intent.action is Action.ENTER and intent.reason=="RAIL_EMA9_DIP_VALUE" and abs((intent.max_price or 0)-.399)<1e-9
    capped=replace(s,yes_ask=.40)
    blocked=list(RailTool(territory_id="R",side=Side.YES,activated_at=1000).on_market_event(capped))[0]
    shared=OneCommander().decide_entry([intent],s,{})
    actual.update(specialist_action=actual["action"],specialist_side=actual["side"],
                  side=None,action=shared.action.value,
                  hard_cap_action=blocked.action.value,hard_cap_reason=blocked.reason,
                  shared_reason=shared.reason)
    ok=ok and blocked.action is Action.WAIT and "ABOVE_MAX_0.399" in blocked.reason and shared.action is Action.WAIT
    return {"name":"pid1172_rail_399_not_400_classification_and_shared_source_wait","kind":"SPECIALIST_CLASSIFICATION_WITH_SHARED_WAIT",
            "input_scope":"UNCHANGED_PARTIAL_WRAPPER_WITHOUT_CURRENT_SOURCE_PROOF",
            "expected":{"action":"WAIT","specialist_action":"ENTER","max_price":.399,
                        "hard_cap_action":"WAIT"},"actual":actual,"pass":ok,
            "points":pts([(115,112),(105,110)],100)}


def pid1172_release_gap_guard_case():
    rack=ToolRackController(); rack._owned_territory=Territory.ALTERNATING_MOUNTAIN; rack._owned_side=Side.NO
    s=snap(meta={"ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"ROLLING","current_side":"NO"}},
                 "heist_cycle_context":{"pop_prep":False}})
    e=ReleaseEvidence(candidate_side=Side.YES,boundary_break=True,directional_expansion=True,
        old_owner_failed_reextension=True,new_side_residence=False)
    guarded,diag=rack._release_entry_evidence_guard(e,s,latched=False)
    actual={"confirmed":guarded.confirmed,"basis":diag.get("basis")}
    return {"name":"pid1172_local_bounce_cannot_release_intact_rolling_opposite_gap","kind":"RELEASE",
            "expected":{"confirmed":False},"actual":actual,"pass":guarded.confirmed is False,
            "points":pts([(110,108),(108,106)],100)}


def pid1172_heist_directional_parent_case():
    md={"mountain":{"owner_side":"NO","terminal_evidence_qualified":False,
        "current_motion":{"30":{"covered":True,"owner_price_rate_btc_s":.4,"owner_ema9_rate_btc_s":.2}},
        "parent_structure":{"parent_terminal_ready":False,"extended_parent":False,"slow_rolling_parent":False}},
        "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"ROLLING","current_side":"NO"}},
        "commander_strategy":{"owned_territory":"MARKET_HEIST","active_tool":"MARKET_HEIST"}}
    s=snap(yes_ask=.19,no_ask=.81,mountain=md["mountain"],meta=md)
    h=ToolIntent(tool="MARKET_HEIST",territory_id="H",lane=Lane.TACTICAL,side=Side.YES,
        action=Action.ENTER,opportunity_id="H",max_price=.20,size_tier=10,
        reason="HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED",source_time=s.now_ts,
        metadata={"parallel_return_entry":True})
    d=OneCommander().decide([h],s)
    actual={"action":d.action.value,"reason":d.reason}
    return {"name":"pid1172_heist_cannot_countertrade_living_rolling_parent","kind":"HEIST",
            "expected":{"action":"WAIT"},"actual":actual,"pass":d.action is Action.WAIT,
            "points":pts([(110,108),(100,102)],100)}

def build_cases():
    cases=[]
    cases.append(entry_result("true_top_no_19c",snap(btc=130,ema9=128,ema30=120,target=115,yes_ask=.81,no_ask=.19,
        mountain=mountain(side="YES",terminal=True,edge="TOP1"),tp=tp(target=115,btc=130)),"ENTER","NO",pts([(110,108),(120,116),(130,128)],115)))
    cases.append(entry_result("true_top_no_20c_wait",snap(btc=130,ema9=128,ema30=120,target=115,yes_ask=.80,no_ask=.20,
        mountain=mountain(side="YES",terminal=True,edge="TOP2"),tp=tp(target=115,btc=130)),"WAIT",None,pts([(110,108),(120,116),(130,128)],115)))
    cases.append(entry_result("true_bottom_yes_19c",snap(btc=80,ema9=82,ema30=90,target=88,yes_ask=.19,no_ask=.81,
        mountain=mountain(side="NO",terminal=True,edge="BOT1"),tp=tp(target=88,btc=80)),"ENTER","YES",pts([(100,98),(90,91),(80,82)],88)))
    cases.append(entry_result("stale_edge_latch_no_entry",snap(btc=130,ema9=128,ema30=120,target=115,yes_ask=.81,no_ask=.19,
        mountain=mountain(side="YES",terminal=True,mature=False,window=False,edge="OLD"),tp=tp(target=115,btc=130)),"WAIT",None,pts([(110,108),(130,128)],115)))

    # #2/#4/#6/#10 control: cheap late top is still WAIT when TP is farther
    # than recent return legs can cover before settlement.
    late_far=mountain(side="YES",terminal=True,edge="LATE-FAR")
    late_far["return_leg_reference"]={"count":4,"median_amplitude_btc":24.0,
        "median_duration_s":180.0,"median_speed_btc_s":24.0/180.0}
    cases.append(entry_result("late_top_tp_far_below_no_return_runway_wait",
        snap(contract_age=680,btc=145,ema9=142,ema30=132,target=100,yes_ask=.995,no_ask=.005,
             mountain=late_far,tp=tp(target=100,btc=145)),"WAIT",None,
        pts([(118,116),(132,129),(145,142)],100)))

    late_ok=mountain(side="YES",terminal=True,edge="LATE-REACH")
    late_ok["return_leg_reference"]={"count":3,"median_amplitude_btc":50.0,
        "median_duration_s":180.0,"median_speed_btc_s":50.0/180.0}
    cases.append(entry_result("late_top_only_when_recent_return_legs_can_reach_tp",
        snap(contract_age=650,btc=120,ema9=118,ema30=110,target=100,yes_ask=.90,no_ask=.10,
             mountain=late_ok,tp=tp(target=100,btc=120)),"ENTER","NO",
        pts([(108,106),(115,112),(120,118)],100)))

    quiet=mountain(side="YES",terminal=True,edge="QUIET-328")
    quiet["return_leg_reference"]={"count":4,"median_amplitude_btc":40.0,"median_speed_btc_s":.18,
                                   "max_amplitude_btc":52.0,"max_speed_btc_s":.24}
    cases.append(entry_result("quiet_regime_328s_left_tp68_away_wait",
        snap(contract_age=572,btc=168,ema9=162,ema30=150,target=100,yes_ask=.983,no_ask=.017,
             mountain=quiet,tp=tp(target=100,btc=168)),"WAIT",None,
        pts([(142,140),(155,151),(168,162)],100)))

    fast=mountain(side="YES",terminal=True,edge="FAST-240")
    fast["return_leg_reference"]={"count":4,"median_amplitude_btc":380.0,"median_speed_btc_s":1.7,
                                  "max_amplitude_btc":620.0,"max_speed_btc_s":3.0}
    cases.append(entry_result("fast_regime_240s_left_tp250_away_can_enter",
        snap(contract_age=660,btc=350,ema9=330,ema30=260,target=100,yes_ask=.90,no_ask=.10,
             mountain=fast,tp=tp(target=100,btc=350)),"ENTER","NO",
        pts([(180,170),(280,250),(350,330)],100)))

    sprout_bad=mountain(side="YES",terminal=True,edge="SPROUT-BAD")
    sprout_bad["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":.62,"owner_ema9_rate_btc_s":.24},
                                  "60":{"covered":True,"owner_price_rate_btc_s":.31,"owner_ema9_rate_btc_s":.12}}
    sprout_bad_meta={"ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"SPROUT",
        "age_seconds_since_observed_cross":13.0,"current_side":"YES","current_abs_gap_btc":3.0,"gap_expanding_6s":True}}}
    cases.append(entry_result("sprout_expanding_false_peak_wait",
        snap(btc=130,ema9=120,ema30=117,target=100,yes_ask=.85,no_ask=.15,mountain=sprout_bad,
             tp=tp(target=100,btc=130),meta=sprout_bad_meta),"WAIT",None,pts([(112,110),(122,115),(130,120)],100)))

    sprout_good=mountain(side="YES",terminal=True,edge="SPROUT-GOOD")
    sprout_good["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":-.20,"owner_ema9_rate_btc_s":-.04},
                                   "60":{"covered":True,"owner_price_rate_btc_s":-.08,"owner_ema9_rate_btc_s":.10}}
    sprout_good_meta={"ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"SPROUT",
        "age_seconds_since_observed_cross":113.0,"current_side":"YES","current_abs_gap_btc":11.4,"gap_expanding_6s":False}}}
    cases.append(entry_result("sprout_real_causal_turn_can_enter",
        snap(btc=130,ema9=128,ema30=117,target=100,yes_ask=.87,no_ask=.13,mountain=sprout_good,
             tp=tp(target=100,btc=130),meta=sprout_good_meta),"ENTER","NO",pts([(120,119),(132,129),(130,128)],100)))

    cases.append(prehalf_detector_case())

    cases.append(entry_result("true_bottom_bounce_owns_contract_yes39",snap(btc=80,ema9=82,ema30=90,target=84,yes_ask=.39,no_ask=.61,
        mountain=mountain(side="NO",terminal=True,edge="BOT-WIN"),tp=tp(ownership="BOUNCE_FAVORED",side="YES",target=84,btc=80)),"ENTER","YES",pts([(96,94),(86,88),(80,82)],84)))
    cases.append(entry_result("true_top_bounce_owns_contract_no39",snap(btc=130,ema9=128,ema30=120,target=125,yes_ask=.61,no_ask=.39,
        mountain=mountain(side="YES",terminal=True,edge="TOP-WIN"),tp=tp(ownership="BOUNCE_FAVORED",side="NO",target=125,btc=130)),"ENTER","NO",pts([(118,116),(126,123),(130,128)],125)))
    cases.append(entry_result("true_top_bounce_owns_contract_no40_wait",snap(btc=130,ema9=128,ema30=120,target=125,yes_ask=.60,no_ask=.40,
        mountain=mountain(side="YES",terminal=True,edge="TOP-WIN2"),tp=tp(ownership="BOUNCE_FAVORED",side="NO",target=125,btc=130)),"WAIT",None,pts([(118,116),(126,123),(130,128)],125)))

    md=mountain(side="NO",terminal=False,arc="INHERITED-DOWN",current_age=500,parent_age=500,parent_amp=20)
    md["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":-.10,"owner_ema9_rate_btc_s":.04},
                          "60":{"covered":True,"owner_price_rate_btc_s":-.06,"owner_ema9_rate_btc_s":.03}}
    md["slowdown"]={"owner_price_retreat_observed":True}; md["diagnostics"]["phase"]="BUILDING"
    inherited_no_meta={"current_geometry":{"ema_gap":-8.0,"range60":30.0,"arc_phase":"BUILDING"},
        "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"SPROUT","age_seconds_since_observed_cross":300.0,
            "current_side":"NO","current_abs_gap_btc":8.0,"gap_expanding_6s":True}}}
    cases.append(entry_result("rollover_starting_down_leg_no39",snap(contract_age=60,btc=92,ema9=95,ema30=102,target=100,yes_ask=.61,no_ask=.39,
        mountain=md,tp=tp(ownership="STARTING_LEG_FAVORED",side="NO",target=100,btc=92),meta=inherited_no_meta),"ENTER","NO",pts([(110,108),(101,102),(92,95)],100)))
    cases.append(entry_result("rollover_starting_down_leg_no40_now_allowed_by_55c_opening_continuation",snap(contract_age=60,btc=92,ema9=95,ema30=102,target=100,yes_ask=.60,no_ask=.40,
        mountain=md,tp=tp(ownership="STARTING_LEG_FAVORED",side="NO",target=100,btc=92),meta=inherited_no_meta),"ENTER","NO",pts([(110,108),(101,102),(92,95)],100)))
    cases.append(entry_result("same_down_leg_after_four_minutes_wait",snap(contract_age=241,btc=92,ema9=95,ema30=102,target=100,yes_ask=.65,no_ask=.35,
        mountain=md,tp=tp(ownership="STARTING_LEG_FAVORED",side="NO",target=100,btc=92),meta=inherited_no_meta),"WAIT",None,pts([(110,108),(101,102),(92,95)],100)))

    spent=mountain(side="NO",terminal=False,arc="OLD-DOWN-NEW-GAP",current_age=388,parent_age=388,parent_amp=50)
    spent["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":-2.09/30.0,"owner_ema9_rate_btc_s":1.46/30.0},
                             "60":{"covered":True,"owner_price_rate_btc_s":-8.81/60.0,"owner_ema9_rate_btc_s":.12/60.0}}
    spent["slowdown"]={"owner_price_retreat_observed":True}; spent["diagnostics"]["phase"]="MATURE"
    spent_meta={"current_geometry":{"ema_gap":-.366,"range60":8.81,"arc_phase":"MATURE"},
        "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"SPROUT","age_seconds_since_observed_cross":28.75,
            "current_side":"NO","current_abs_gap_btc":.366,"gap_expanding_6s":False}}}
    cases.append(entry_result("new_no_gap_sprouted_after_rollover_is_not_inherited_trade7_wait",
        snap(contract_age=88,btc=96,ema9=95,ema30=95.366,target=100,yes_ask=.61,no_ask=.39,mountain=spent,
             tp=tp(ownership="STARTING_LEG_FAVORED",side="NO",target=100,btc=96),meta=spent_meta),"WAIT",None,
        pts([(110,108),(94,94),(96,95)],100)))

    rm=mountain(side="YES",terminal=False,arc="ROLL-UP",current_age=1900,parent_age=1900,qualified=False,rolling=True)
    rm["current_motion"]={"30":{"covered":True,"owner_price_rate_btc_s":.12,"owner_ema9_rate_btc_s":.05},
                          "60":{"covered":True,"owner_price_rate_btc_s":.10,"owner_ema9_rate_btc_s":.04}}
    rm["slowdown"]={"owner_price_retreat_observed":False}; rm["diagnostics"]["phase"]="ROLLING"
    rolling_meta={"current_geometry":{"ema_gap":12.0,"range60":35.0,"arc_phase":"ROLLING"},
        "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"ROLLING","age_seconds_since_observed_cross":1900.0,
            "current_side":"YES","current_abs_gap_btc":12.0,"gap_expanding_6s":True}}}
    cases.append(entry_result("rolling_mountain_rollover_yes38",snap(contract_age=80,btc=108,ema9=106,ema30=101,target=103,yes_ask=.38,no_ask=.62,
        mountain=rm,tp=tp(ownership="STARTING_LEG_FAVORED",side="YES",target=103,btc=108),meta=rolling_meta),"ENTER","YES",pts([(96,97),(102,101),(108,106)],103)))

    # PID3296 starvation correction: a persistent YES gap is the parent context
    # while a local NO child reaches a true terminal and turns back up.  This
    # route must survive a dormant DOWN_RAIL label and a DOWN EMA30 slope, but
    # still requires <40c value and demonstrated settlement runway.
    rg=mountain(side="NO",terminal=True,edge="PID3296-0831")
    rg["return_leg_reference"]={"count":4,"basis":"LAST_COMPLETED_OPPOSITE_DIRECTION_PARENT_MOUNTAINS",
        "median_amplitude_btc":36.11,"median_speed_btc_s":.170166,"max_amplitude_btc":114.47,"max_speed_btc_s":.241973,
        "legs":[{"arc_id":"E32","btc_amplitude_btc":39.35,"duration_s":183.67,"average_btc_speed_btc_s":.214239},
                {"arc_id":"E34","btc_amplitude_btc":114.47,"duration_s":998.8,"average_btc_speed_btc_s":.114607},
                {"arc_id":"E36","btc_amplitude_btc":27.08,"duration_s":214.76,"average_btc_speed_btc_s":.126094},
                {"arc_id":"E38","btc_amplitude_btc":32.87,"duration_s":135.84,"average_btc_speed_btc_s":.241973}]}
    rg_meta={"current_geometry":{"btc_price":77826.62,"ema9":77837.9034,"ema30":77833.2197,"ema_gap":4.6837,
                                   "range60":22.12,"btc_change6":.01,"ema9_change6":.002,"parent_direction":"DOWN"},
             "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"ROLLING","age_seconds_since_observed_cross":3006.57,
                 "current_side":"YES","current_abs_gap_btc":4.6837,"continued_on_latest_cross_side":True,
                 "gap_expanding_6s":True,"clock_has_trade_authority":False}},
             "commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"}}
    rg_tp={"target_between_ema9_ema30":False,"remaining_seconds":831.15,"observed_target_side":"NO",
           "required_move_to_target_btc":35.18,"contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"NO"}
    cases.append(entry_result("pid3296_0831_rolling_gap_child_terminal_turn_yes39",
        snap(contract_age=68.85,btc=77826.62,ema9=77837.9034,ema30=77833.2197,target=77861.8,
             yes_ask=.39,no_ask=.62,mountain=rg,tp=rg_tp,meta=rg_meta),"WAIT",None,
        pts([(77840,77843),(77824,77838),(77827,77838)],77861.8)))

    rg_bad=mountain(side="NO",terminal=True,edge="ROLLING-STILL-DOWN")
    rg_bad["return_leg_reference"]={"count":3,"legs":[
        {"arc_id":"R1","btc_amplitude_btc":80.0,"duration_s":240.0,"average_btc_speed_btc_s":.333},
        {"arc_id":"R2","btc_amplitude_btc":90.0,"duration_s":260.0,"average_btc_speed_btc_s":.346},
        {"arc_id":"R3","btc_amplitude_btc":70.0,"duration_s":220.0,"average_btc_speed_btc_s":.318}]}
    bad_meta={"current_geometry":{"ema_gap":7.0,"range60":30.0,"btc_change6":-12.0,"ema9_change6":-2.0,"parent_direction":"DOWN"},
              "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"ROLLING","age_seconds_since_observed_cross":2200.0,
                  "current_side":"YES","current_abs_gap_btc":7.0,"continued_on_latest_cross_side":True}},
              "commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"}}
    cases.append(entry_result("rolling_gap_child_still_advancing_wait",
        snap(contract_age=200,btc=90,ema9=92,ema30=85,target=100,yes_ask=.35,no_ask=.65,mountain=rg_bad,
             tp={"target_between_ema9_ema30":False,"remaining_seconds":700.0,"observed_target_side":"NO",
                 "required_move_to_target_btc":35.0},meta=bad_meta),"WAIT",None,pts([(105,104),(96,98),(90,92)],100)))

    # PID3296 #2: only ~$6 of NO TP margin with ~96s left while the live 6s
    # BTC+EMA9 motion has turned back toward YES.  Being on the target side is
    # not automatic settlement ownership.
    thin=mountain(side="YES",terminal=True,edge="PID3296-T2")
    thin_meta={"current_geometry":{"btc_price":77812.78,"ema_gap":-5.8299,"range60":9.67,"range180":14.58,
                                    "btc_change6":2.79,"ema9_change6":.558,"btc_change30":-1.42,"btc_change60":-3.17},
               "ema9_ema30_cross_context":{"gap_lifecycle":{"stage":"INHERITED_OR_UNOBSERVED_CROSS",
                   "current_side":"NO","current_abs_gap_btc":5.8299,"continued_on_latest_cross_side":False}}}
    cases.append(entry_result("pid3296_thin_tp_possession_no15_wait",
        snap(contract_age=803.5,btc=77812.78,ema9=77818.0,ema30=77823.8,target=77818.87,yes_ask=.86,no_ask=.15,
             mountain=thin,tp={"target_between_ema9_ema30":False,"remaining_seconds":96.482,"observed_target_side":"NO",
                 "required_move_to_target_btc":6.09,"contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"YES"},
             meta=thin_meta),"WAIT",None,pts([(77820,77821),(77810,77817),(77813,77818)],77818.87)))

    fast_hold=mountain(side="YES",terminal=True,edge="FAST-POSSESSION")
    fast_meta={"current_geometry":{"range60":300.0,"range180":650.0,"btc_change6":-36.0,"ema9_change6":-8.0,
                                    "btc_change30":-180.0,"btc_change60":-360.0}}
    cases.append(entry_result("fast_regime_late_target_possession_can_still_enter",
        snap(contract_age=804,btc=9900,ema9=9920,ema30=10000,target=10000,yes_ask=.85,no_ask=.15,mountain=fast_hold,
             tp={"target_between_ema9_ema30":False,"remaining_seconds":96.0,"observed_target_side":"NO",
                 "required_move_to_target_btc":100.0},meta=fast_meta),"ENTER","NO",
        pts([(10300,10200),(10100,10040),(9900,9920)],10000)))

    cases.append(authorized_heist_overlay_case())
    cases.append(authorized_heist_primary_flicker_case())
    cases.append(authorized_release_overlay_case())
    cases.append(authorized_three_cycle_pop_case())
    cases.append(authorized_rollover_terminal_return_case(price=.49))
    cases.append(authorized_rollover_terminal_return_case(price=.50))
    cases.append(authorized_inherited_young_leg_rollover_continuation_case(price=.52))
    cases.append(authorized_inherited_young_leg_rollover_continuation_case(price=.55))
    cases.append(authorized_extended_top_sub20_return_case())
    cases.append(authorized_quick_heist_floor_case())
    cases.append(authorized_house_protection_case())
    cases.append(authorized_high_profit_peak_hover_skim_case())
    cases.append(authorized_heist_overlay_blocks_competing_quick_mountain_case())

    cases.append(pid1172_house_true_edge_case())
    cases.append(pid1172_late_defer_case())
    cases.append(pid1172_far_tp_outlier_case())
    cases.append(pid1172_rail_price_case())
    cases.append(pid1172_release_gap_guard_case())
    cases.append(pid1172_heist_directional_parent_case())

    cases.append(pid3216_source_skew_case())
    cases.append(pid3216_actual_ultra_hover_case())
    cases.append(pid3216_hover_case(plateau=True))
    cases.append(pid3216_hover_case(plateau=False))

    cases.append(pid2672_history_layer_skew_case())
    cases.append(pid2672_paired_gap_prepare_case())
    cases.append(pid2672_tp_junction_case(late=False))
    cases.append(pid2672_tp_junction_case(late=True))
    cases.append(pid2672_rail_ema9_dip_case(ask=.20))
    cases.append(pid2672_rail_ema9_dip_case(ask=.21))

    cases.append(entry_result("ema9_ema30_tp_junction_wait",snap(btc=100,ema9=100.2,ema30=99.8,target=100,yes_ask=.19,no_ask=.19,
        mountain=mountain(side="YES",terminal=True,edge="J"),tp=tp(junction=True,target=100,btc=100)),"WAIT",None,pts([(99,99.5),(100,100),(100,100.2)],100)))
    cases.append(entry_result("expanding_down_no_yes19_fade",snap(btc=85,ema9=88,ema30=96,target=92,yes_ask=.19,no_ask=.81,
        mountain=mountain(side="NO",terminal=True,strong=True,edge="EXP"),tp=tp(target=92,btc=85)),"WAIT",None,pts([(100,98),(92,94),(85,88)],92)))
    cases.append(entry_result("nonmountain_context_paused",snap(btc=90,ema9=92,ema30=98,target=100,yes_ask=.10,no_ask=.90,
        mountain={"qualified_alternating_mountain":False,"owner_side":"NO","parent_structure":{}},tp=tp(target=100,btc=90),
        meta={"commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"}}),"WAIT",None,pts([(105,103),(98,99),(90,92)],100)))

    s=snap(btc=90,ema9=92,ema30=98,target=100,yes_ask=.10,no_ask=.10,mountain=mountain(side="NO",terminal=False),tp=tp(target=100,btc=90))
    intent=ToolIntent(tool="RAIL",territory_id="R",lane=Lane.MAIN,side=Side.NO,action=Action.ENTER,
                      opportunity_id="R",max_price=.10,size_tier=10,reason="LEGACY_RAIL",source_time=s.now_ts,metadata={})
    cases.append(entry_result("specialist_rail_entry_paused",s,"WAIT",None,pts([(105,103),(98,99),(90,92)],100),(intent,)))

    pos={"position_id":"P1","ticker":"KX-MOUNTAIN-CONSTRUCT","territory_id":"M","opportunity_id":"O","tool":"ONE_COMMANDER_PRIMARY",
         "lane":"MAIN","side":Side.NO,"entry_price":.19,"entry_time":1000.0,"close_ts":1900.0,"custody_state":"NORMAL",
         "entry_metadata":{"commander_physical_evidence":{"edge_id":"ENTRY-TOP"}},"floor_bid":None}
    s_same=snap(t=1001,btc=129,ema9=127,ema30=120,target=115,yes_ask=.82,no_ask=.18,yes_bid=.81,no_bid=.17,
        mountain=mountain(side="NO",terminal=True,edge="ENTRY-TOP"),tp=tp(target=115,btc=129))
    cases.append(position_result("same_edge_one_second_hold",s_same,pos,"HOLD",pts([(130,128),(129,127)],115)))
    s_stale=snap(t=1120,btc=100,ema9=102,ema30=108,target=115,yes_ask=.30,no_ask=.70,yes_bid=.29,no_bid=.69,
        mountain=mountain(side="NO",terminal=True,mature=False,window=False,edge="NEXT:1120000"),tp=tp(target=115,btc=100))
    cases.append(position_result("stale_exit_latch_holds",s_stale,pos,"HOLD",pts([(129,127),(100,102)],115)))
    early_collection=mountain(side="NO",terminal=True,edge="NEXT:1110000")
    early_collection["primary_collection_terminal_qualified"]=False
    s_early=snap(t=1110,btc=106,ema9=107,ema30=110,target=115,yes_ask=.35,no_ask=.65,yes_bid=.34,no_bid=.64,
        mountain=early_collection,tp=tp(target=115,btc=106))
    cases.append(position_result("entry_grade_terminal_does_not_cut_winner_early",s_early,pos,"HOLD",
        pts([(129,127),(116,116),(106,107)],115)))
    s_next_m=mountain(side="NO",terminal=True,edge="NEXT:1120000")
    s_next_m["primary_collection_terminal_qualified"]=True
    s_next=snap(t=1120,btc=100,ema9=102,ema30=108,target=115,yes_ask=.30,no_ask=.70,yes_bid=.29,no_bid=.69,
        mountain=s_next_m,tp=tp(target=115,btc=100))
    cases.append(position_result("next_true_terminal_edge_exit",s_next,pos,"EXIT",pts([(129,127),(112,114),(100,102)],115)))

    cases.extend(pid8868_cases())
    cases.extend(pid23072_cases())
    cases.append(operator_authorized_profit_floor_case())
    cases.append(sideways_no_terrain_3pct_floor_case())
    cases.append(execution_case())
    cases.extend(pid22736_cases())
    return cases


def svg(path:Path,case):
    points=case["points"] or [{"t":0,"btc":0,"ema9":0,"tp":0}]
    width,height=920,330; l,r,t,b=60,20,35,45
    xs=[p["t"] for p in points]; ys=[p["btc"] for p in points]+[p["ema9"] for p in points]+[p["tp"] for p in points]
    xmin,xmax=min(xs),max(xs); ymin,ymax=min(ys),max(ys)
    if xmax==xmin:xmax+=1
    if ymax==ymin:ymax+=1
    pad=(ymax-ymin)*.08 or 1; ymin-=pad;ymax+=pad
    X=lambda x:l+(x-xmin)/(xmax-xmin)*(width-l-r); Y=lambda y:t+(ymax-y)/(ymax-ymin)*(height-t-b)
    poly=lambda key:" ".join(f"{X(p['t']):.1f},{Y(p[key]):.1f}" for p in points)
    actual=case["actual"]; label=f"{actual.get('action') or actual.get('entry_receipt') or ''} {actual.get('side') or ''}".strip()
    last=points[-1]
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         '<rect width="100%" height="100%" fill="white"/>',
         f'<text x="{l}" y="22" font-family="Arial" font-size="15">{html.escape(case["name"])}</text>',
         f'<line x1="{l}" y1="{Y(last["tp"]):.1f}" x2="{width-r}" y2="{Y(last["tp"]):.1f}" stroke="#777" stroke-dasharray="5 4"/>',
         f'<polyline points="{poly("btc")}" fill="none" stroke="#111" stroke-width="2"/>',
         f'<polyline points="{poly("ema9")}" fill="none" stroke="#666" stroke-width="2" stroke-dasharray="4 3"/>',
         f'<circle cx="{X(last["t"]):.1f}" cy="{Y(last["btc"]):.1f}" r="6" fill="none" stroke="#000" stroke-width="2"/>',
         f'<text x="{X(last["t"])-150:.1f}" y="{Y(last["btc"])-10:.1f}" font-family="Arial" font-size="12">{html.escape(label)}</text>',
         f'<text x="{l}" y="{height-13}" font-family="Arial" font-size="11">BTC solid · EMA9 dashed · TP horizontal · expected {html.escape(str(case["expected"]))}</text>',
         '</svg>']
    path.write_text("\n".join(out),encoding="utf-8")


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",default="MOUNTAIN_ONLY_CONSTRUCT_RESULTS"); args=ap.parse_args()
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    cases=build_cases()
    for c in cases:
        (out/f"{c['name']}.json").write_text(json.dumps({k:v for k,v in c.items() if k!="points"},indent=2,default=str)+"\n",encoding="utf-8")
        svg(out/f"{c['name']}.svg",c)
    summary={
        "construct":"OPPORTUNITY_FIRST_MOUNTAIN_V12_SOURCE_SCOPED",
        "total":len(cases),"passed":sum(c["pass"] for c in cases),
        "failed":[c["name"] for c in cases if not c["pass"]],
        "required_controls":[c["name"] for c in cases],
        "evidence_scope":{
            "synthetic":"Explicit numeric source, comparative maturity, retreat, return references and authored native quotes; no historical fill claim.",
            "pid8868":"Immutable partial wrappers: preserve factory classification, shared source gate WAIT; held-terminal control retained.",
            "pid23072":"Causal geometry prefixes and recorded contract values with reconstructed price controls; not native-book admission/execution replay. Shared positives 1/3/5, other entries WAIT; old factory matrix checked separately.",
            "pid2672":"Partial junction/Rail wrappers retain lower-level species and caps; missing provenance cannot authorize shared entry.",
            "execution":"Synthetic candidates actually admitted by OneCommander and committed through PaperExecutioner; current-bid floor schedule and final flat state verified.",
            "outcomes":"No substitute historical P&L, invented original receipt, or new venue order.",
        },
        "cases":[{k:v for k,v in c.items() if k!="points"} for c in cases],
    }
    (out/"SUMMARY.json").write_text(json.dumps(summary,indent=2,default=str)+"\n",encoding="utf-8")
    print(f"OPPORTUNITY-FIRST MOUNTAIN CONSTRUCT: {summary['passed']}/{summary['total']} PASS")
    for c in cases:
        print(("PASS" if c["pass"] else "FAIL"),c["name"],"expected",c["expected"],"actual",c["actual"])
    return 0 if not summary["failed"] else 1

if __name__=="__main__": raise SystemExit(main())
