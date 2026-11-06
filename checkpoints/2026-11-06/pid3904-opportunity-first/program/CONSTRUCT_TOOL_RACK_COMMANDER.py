"""Fast offline OneCommander constitution Construct.

Runs the reconstructed Commander, TP evidence and qualified-fade logic against
small causal scenes that encode the frozen positive/negative strategy controls.
It does not replace the deeper raw-feed Constructs.  Its job is to fail fast
when authority, side, TP, value or custody behavior regresses before a PAPER
bundle is built.

Each case writes JSON evidence plus an SVG showing BTC, EMA9, TP and the actual
Commander entry/exit marker.  Synthetic controls make no venue-fill or profit
claim.
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Mapping

from strategy_core.commander import OneCommander
from strategy_core.fade_evidence import qualified_fade_candidates
from strategy_core.detectors.mountain_geometry import detect_mountain_geometry
from strategy_core.detectors.rail_geometry import detect_rail_geometry
from strategy_core.detectors.release_geometry import build_release_probe, detect_release_for_owner
from strategy_core.tool_rack import ToolRackController
from strategy_core.tp_geometry import build_tp_geometry
from strategy_core.types import Territory
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def snap(*, t: float, btc: float, ema9: float, target: float, yes_ask: float, no_ask: float,
         yes_bid: float | None = None, no_bid: float | None = None,
         contract_age: float = 300.0, meta: Mapping[str, Any] | None = None) -> MarketSnapshot:
    metadata = {
        "physical_current": True,
        "geometry_last_epoch_ms": t * 1000.0,
        "geometry_continuity_generation": 1,
        "current_geometry": {"btc_price": btc, "ema9": ema9},
        "mission_context": {"contract": {"target": target, "remaining_seconds": max(0.0, 900.0-contract_age)}},
        "commander_strategy": {"owned_territory": "UNKNOWN", "owned_side": None, "active_tool": None},
        "tp_geometry": {"target": target, "btc": btc,
                        "observed_target_side": "YES" if btc > target else "NO" if btc < target else "AT_TARGET",
                        "required_move_to_target_btc": abs(btc-target)},
    }
    if meta:
        metadata.update(meta)
    return MarketSnapshot(
        now_ts=t, ticker="KX-CONSTRUCT", contract_age_s=contract_age,
        yes_ask=yes_ask, no_ask=no_ask, yes_bid=yes_bid, no_bid=no_bid,
        yes_sell_allowed=yes_bid is not None, no_sell_allowed=no_bid is not None,
        metadata=metadata,
    )


def decide_entry(snapshot: MarketSnapshot) -> dict[str, Any]:
    commander = OneCommander()
    candidates = commander.physical_entry_candidates(snapshot)
    decision = commander.decide(list(candidates), snapshot)
    return {
        "action": decision.action.value,
        "side": decision.intent.side.value if decision.intent and decision.intent.side else None,
        "reason": decision.reason,
        "candidate_reasons": [i.reason for i in candidates],
        "candidate_families": [i.metadata.get("commander_candidate_family") for i in candidates],
    }


def svg_plot(path: Path, points: list[dict[str, float]], markers: list[dict[str, Any]], title: str) -> None:
    width, height = 920, 360
    left, right, top, bottom = 65, 25, 35, 50
    xs = [p["t"] for p in points]
    ys = [p["btc"] for p in points] + [p["ema9"] for p in points] + [p["tp"] for p in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if xmax == xmin: xmax += 1
    if ymax == ymin: ymax += 1
    pad = (ymax-ymin)*.08
    ymin -= pad; ymax += pad
    def X(x): return left + (x-xmin)/(xmax-xmin)*(width-left-right)
    def Y(y): return top + (ymax-y)/(ymax-ymin)*(height-top-bottom)
    def poly(key): return " ".join(f"{X(p['t']):.1f},{Y(p[key]):.1f}" for p in points)
    body = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            f'<text x="{left}" y="22" font-family="Arial" font-size="16">{html.escape(title)}</text>',
            f'<line x1="{left}" y1="{Y(points[0]["tp"]):.1f}" x2="{width-right}" y2="{Y(points[0]["tp"]):.1f}" stroke="#777" stroke-dasharray="6 5"/>',
            f'<polyline points="{poly("btc")}" fill="none" stroke="#111" stroke-width="2"/>',
            f'<polyline points="{poly("ema9")}" fill="none" stroke="#555" stroke-width="2" stroke-dasharray="4 3"/>']
    for marker in markers:
        x = X(marker["t"]); y = Y(marker["btc"])
        label = html.escape(f"{marker['action']} {marker.get('side') or ''}".strip())
        body += [f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="none" stroke="#000" stroke-width="2"/>',
                 f'<text x="{x+9:.1f}" y="{y-8:.1f}" font-family="Arial" font-size="12">{label}</text>']
    body += [f'<text x="{left}" y="{height-14}" font-family="Arial" font-size="11">BTC solid · EMA9 dashed · TP horizontal · synthetic causal control</text>', '</svg>']
    path.write_text("\n".join(body), encoding="utf-8")


def entry_case(name: str, snapshot: MarketSnapshot, expected_action: str, expected_side: str | None,
               points: list[dict[str, float]]) -> dict[str, Any]:
    actual = decide_entry(snapshot)
    passed = actual["action"] == expected_action and actual["side"] == expected_side
    return {"name": name, "kind": "ENTRY", "expected": {"action": expected_action, "side": expected_side},
            "actual": actual, "pass": passed, "points": points}


def position_case(name: str, snapshot: MarketSnapshot, position: Mapping[str, Any],
                  expected_action: str, *, floor_breached: bool = False) -> dict[str, Any]:
    decision = OneCommander().decide_position([], snapshot, position, floor_breached=floor_breached)
    actual = {"action": decision.action.value, "reason": decision.reason}
    return {"name": name, "kind": "POSITION", "expected": {"action": expected_action},
            "actual": actual, "pass": actual["action"] == expected_action,
            "points": [{"t": snapshot.now_ts-60, "btc": snapshot.metadata["current_geometry"]["btc_price"]-20,
                        "ema9": snapshot.metadata["current_geometry"]["ema9"]-15,
                        "tp": snapshot.metadata["tp_geometry"]["target"]},
                       {"t": snapshot.now_ts, "btc": snapshot.metadata["current_geometry"]["btc_price"],
                        "ema9": snapshot.metadata["current_geometry"]["ema9"],
                        "tp": snapshot.metadata["tp_geometry"]["target"]}]}



def sequence_edge_relay_case() -> dict[str, Any]:
    commander = OneCommander()
    position = {"position_id":"EDGE1","ticker":"KX-CONSTRUCT","territory_id":"T1","opportunity_id":"OLD",
                "tool":"ONE_COMMANDER_PRIMARY","lane":"MAIN","side":Side.YES,"entry_price":.20,
                "close_ts":2600.0,"custody_state":"NORMAL","entry_metadata":{},"floor_bid":None}
    exit_snap = snap(t=2050, btc=150, ema9=146, target=125, yes_ask=.70, no_ask=.30, yes_bid=.68, no_bid=.28,
        meta={"commander_strategy":{"owned_territory":"ROLLING_MOUNTAIN","owned_side":"YES"},
              "mountain":{"owner_side":"YES","terminal_evidence_qualified":True,"edge_id":"EDGE-TOP"},
              "tp_geometry":{"target":125,"btc":150,"observed_target_side":"YES","required_move_to_target_btc":25,
                             "contract_ownership":"BOUNCE_FAVORED","contract_ownership_side":"NO"}})
    exit_decision = commander.decide_position([], exit_snap, position)
    entry_snap = snap(t=2051, btc=149, ema9=146, target=125, yes_ask=.82, no_ask=.18,
        meta={"mountain":{"owner_side":"YES","terminal_evidence_qualified":True,
                           "strong_active_release":False,"edge_id":"EDGE-TOP"},
              "tp_geometry":{"target":125,"btc":149,"observed_target_side":"YES","required_move_to_target_btc":24,
                             "contract_ownership":"BOUNCE_FAVORED","contract_ownership_side":"NO"}})
    candidates = commander.physical_entry_candidates(entry_snap)
    entry_decision = commander.decide(list(candidates), entry_snap)
    actual = {"action":"EXIT_THEN_ENTER" if exit_decision.action is Action.EXIT and entry_decision.action is Action.ENTER else "FAILED_SEQUENCE",
              "exit_reason":exit_decision.reason,"entry_side":entry_decision.intent.side.value if entry_decision.intent and entry_decision.intent.side else None,
              "entry_reason":entry_decision.reason}
    return {"name":"sequential_edge_relay_fresh_quote","kind":"SEQUENCE",
            "expected":{"action":"EXIT_THEN_ENTER","side":"NO"},"actual":actual,
            "pass":actual["action"]=="EXIT_THEN_ENTER" and actual["entry_side"]=="NO",
            "points":[{"t":1990,"btc":140,"ema9":138,"tp":125},{"t":2050,"btc":150,"ema9":146,"tp":125},{"t":2051,"btc":149,"ema9":146,"tp":125}]}

def false_newborn_handoff_case() -> dict[str, Any]:
    commander = OneCommander()
    position = {"position_id":"OLDNO","ticker":"KX-CONSTRUCT","territory_id":"T1","opportunity_id":"OLDNO",
                "tool":"ONE_COMMANDER_PRIMARY","lane":"MAIN","side":Side.NO,"entry_price":.25,
                "close_ts":2700.0,"custody_state":"NORMAL","entry_metadata":{},"floor_bid":None}
    s = snap(t=2150, btc=110, ema9=112, target=130, yes_ask=.26, no_ask=.74, yes_bid=.24, no_bid=.72,
        meta={"commander_strategy":{"owned_territory":"ROLLING_MOUNTAIN","owned_side":"NO"},
              "mountain":{"owner_side":"YES","current_arc_id":"NEWBORN","mature_edge":False,
                           "terminal_evidence_qualified":False},
              "leg_echo":{"side":"NO","live_pullback_count":0,"median_pullback_count":1,
                           "live_current_child":{"side":"YES","duration_s":0}},
              "tp_geometry":{"target":130,"btc":110,"observed_target_side":"NO","required_move_to_target_btc":20,
                             "contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"NO"}})
    held = commander.decide_position([], s, position)
    entries = commander.physical_entry_candidates(s)
    entry = commander.decide(list(entries), s)
    actual={"action":"HOLD_AND_NO_NEW_ENTRY" if held.action is Action.HOLD and entry.action is Action.WAIT else "FAILED_SEQUENCE",
            "hold_reason":held.reason,"entry_reason":entry.reason}
    return {"name":"newborn_child_does_not_force_handoff","kind":"SEQUENCE",
            "expected":{"action":"HOLD_AND_NO_NEW_ENTRY"},"actual":actual,
            "pass":actual["action"]=="HOLD_AND_NO_NEW_ENTRY",
            "points":[{"t":2090,"btc":118,"ema9":116,"tp":130},{"t":2120,"btc":112,"ema9":113,"tp":130},{"t":2150,"btc":110,"ema9":112,"tp":130}]}


def raw_rail_recognition_case(*, shrinking: bool) -> dict[str, Any]:
    from strategy_core.detectors.rail_geometry import detect_rail_geometry
    rows=[]
    for i in range(16):
        ts=1_000_000+i*30_000
        ema30=100.0+i*.20
        gap=(10.0-i*.40) if shrinking else (5.0+i*.25)
        ema9=ema30+gap
        btc=ema9+2.0
        rows.append({"epoch_ms":ts,"btc_price":btc,"ema9":ema9,"ema30":ema30,
                     "struct_slope3m":.08,"struct_slope6m":.07,"struct_slope9m":.06,
                     "ema30_slope3m":.03})
    d=detect_rail_geometry(rows)
    last=rows[-1]
    territory="UP_RAIL" if d.qualified_rail else "UNKNOWN"
    side="YES" if d.qualified_rail else None
    s=snap(t=last["epoch_ms"]/1000.0, btc=last["btc_price"], ema9=last["ema9"],
           target=100.0, yes_ask=.44, no_ask=.56,
           meta={"commander_strategy":{"owned_territory":territory,"owned_side":side,
                                        "active_tool":"RAIL" if d.qualified_rail else None},
                 "leg_echo":{"live_contract_count":1},
                 "rail_geometry_construct":{
                    "qualified":d.qualified_rail,"persistence_seconds":d.persistence_seconds,
                    "gap_start":d.gap_start,"gap_end":d.gap_end,
                    "gap_maintaining_or_expanding":d.gap_maintaining_or_expanding}})
    actual=decide_entry(s)
    expected_action="WAIT" if shrinking else "ENTER"
    expected_side=None if shrinking else "YES"
    return {"name":"raw_rail_shrinking_gap_waits" if shrinking else "raw_half_contract_rail_enters",
            "kind":"RAW_RAIL","expected":{"action":expected_action,"side":expected_side},
            "actual":{**actual,"detector":s.metadata["rail_geometry_construct"]},
            "pass":actual["action"]==expected_action and actual["side"]==expected_side,
            "points":[{"t":r["epoch_ms"]/1000.0,"btc":r["btc_price"],"ema9":r["ema9"],"tp":100.0}
                      for r in rows]}


def raw_rail_fakeout_case() -> dict[str, Any]:
    from strategy_core.counter_observers import build_counter_evidence
    rows=[]
    for i,dist in enumerate((5,7,8,9,10,12,30,20,12,8)):
        rows.append({"epoch_ms":1_000_000+i*30_000,"btc_price":100+dist,"ema9":100})
    base=snap(t=1270.0, btc=108, ema9=100, target=115, yes_ask=.80, no_ask=.20,
              meta={"commander_strategy":{"owned_territory":"UP_RAIL","owned_side":"YES","active_tool":"RAIL"},
                    "leg_echo":{"median_pullback_btc":15.0,"live_contract_count":4},
                    "release_in_progress":False})
    evidence=build_counter_evidence(base, rows=rows, historical_candles=())
    s=snap(t=1270.0, btc=108, ema9=100, target=115, yes_ask=.80, no_ask=.20,
           meta={**base.metadata, **evidence})
    actual=decide_entry(s)
    return {"name":"raw_rail_failed_excursion_renter","kind":"RAW_COUNTER",
            "expected":{"action":"ENTER","side":"NO"},"actual":{**actual,"evidence":evidence["rail_fakeout_evidence"]},
            "pass":actual["action"]=="ENTER" and actual["side"]=="NO",
            "points":[{"t":r["epoch_ms"]/1000.0,"btc":r["btc_price"],"ema9":r["ema9"],"tp":115.0}
                      for r in rows]}


def raw_anomaly_candle_case() -> dict[str, Any]:
    from strategy_core.counter_observers import build_counter_evidence
    prior=[{"open":100+i,"high":104+i,"low":99+i,"close":102+i,"time":700+i*60} for i in range(5)]
    anomaly={"open":105,"high":140,"low":104,"close":136,"time":1000}
    failure={"open":136,"high":138,"low":120,"close":124,"time":1060}
    base=snap(t=1120, btc=124, ema9=118, target=130, yes_ask=.84, no_ask=.16,
              meta={"release_in_progress":False})
    evidence=build_counter_evidence(base, rows=(), historical_candles=prior+[anomaly,failure])
    s=snap(t=1120, btc=124, ema9=118, target=130, yes_ask=.84, no_ask=.16,
           meta={**base.metadata, **evidence})
    actual=decide_entry(s)
    return {"name":"raw_unsupported_xlarge_candle_fade","kind":"RAW_COUNTER",
            "expected":{"action":"ENTER","side":"NO"},"actual":{**actual,"evidence":evidence["anomaly_candle_evidence"]},
            "pass":actual["action"]=="ENTER" and actual["side"]=="NO",
            "points":[{"t":700,"btc":100,"ema9":100,"tp":130},{"t":1000,"btc":136,"ema9":112,"tp":130},
                      {"t":1060,"btc":124,"ema9":118,"tp":130}]}


def pid4756_release_flicker_case(*, down: bool) -> dict[str, Any]:
    fixture=Path(__file__).with_name("tests")/"tool_rack"/"fixtures"/"pid4756_release_flicker_controls.json"
    payload=json.loads(fixture.read_text(encoding="utf-8"))
    lo,hi=(15353,15357) if down else (2830,2834)
    rows=[r for r in payload["controls"] if lo <= r["sequence"] <= hi]
    commander=OneCommander(); decisions=[]
    for row in rows:
        owner=Side(row["owner_side"]); opposite=Side.YES if owner is Side.NO else Side.NO
        s=snap(t=float(row["now_ts"]), btc=100.0, ema9=100.0, target=100.0,
               yes_ask=.05, no_ask=.05,
               meta={"release_in_progress":bool(row["strong_active_release"]),
                     "release_candidate_side":row["owner_side"] if row["strong_active_release"] else None,
                     "commander_strategy":{"owned_territory":"ROLLING_MOUNTAIN","owned_side":row["owner_side"],
                                            "active_tool":"ROLLING_MOUNTAIN"},
                     "mountain":{"current_arc_id":row["arc_id"],"owner_side":row["owner_side"],
                                 "strong_active_release":bool(row["strong_active_release"]),
                                 "terminal_evidence_qualified":bool(row["terminal_evidence_qualified"]),
                                 "mature_edge":bool(row["mature_edge"]),"arc_phase":row["arc_phase"]}})
        commander.physical_entry_candidates(s)
        intent=ToolIntent(tool="ROLLING_MOUNTAIN",territory_id="PID4756",lane=Lane.TACTICAL,
                          side=opposite,action=Action.ENTER,opportunity_id=f"HIST:{row['sequence']}",
                          max_price=.20,size_tier=10.0,reason="HISTORICAL_OPPOSITE_ATTEMPT",
                          source_time=float(row["now_ts"]),metadata={})
        d=commander.decide([intent],s); decisions.append(d)
    last=decisions[-1]
    passed=all(d.action is Action.WAIT for d in decisions) and last.reason=="COMMANDER_RELEASE_CHAPTER_OWNS_DIRECTION"
    return {"name":"pid4756_down_release_flicker_blocked" if down else "pid4756_up_release_flicker_blocked",
            "kind":"HISTORICAL_SEQUENCE","expected":{"action":"WAIT","side":None},
            "actual":{"action":last.action.value,"side":None,"reason":last.reason,
                      "historical_sequences":[r["sequence"] for r in rows]},"pass":passed,
            "points":[{"t":float(r["now_ts"]),"btc":100.0+(i if not down else -i),
                       "ema9":100.0+(i*.7 if not down else -i*.7),"tp":100.0}
                      for i,r in enumerate(rows)]}


def historical_rail_conflict_case(*, name: str, rail_side: Side, rail_ask: float,
                                  bad_side: Side, bad_ask: float, expect_action: str,
                                  expect_side: str | None) -> dict[str, Any]:
    yes_ask = rail_ask if rail_side is Side.YES else bad_ask
    no_ask = rail_ask if rail_side is Side.NO else bad_ask
    territory = "UP_RAIL" if rail_side is Side.YES else "DOWN_RAIL"
    s=snap(t=2300, btc=145 if rail_side is Side.YES else 95,
           ema9=140 if rail_side is Side.YES else 100, target=120,
           yes_ask=yes_ask, no_ask=no_ask,
           meta={"commander_strategy":{"owned_territory":territory,"owned_side":rail_side.value,"active_tool":"RAIL"},
                 "leg_echo":{"live_contract_count":1},
                 "release_in_progress":True,"release_candidate_side":rail_side.value,
                 "mountain":{"current_arc_id":f"HIST-{name}","owner_side":rail_side.value,
                             "strong_active_release":True}})
    commander=OneCommander(); candidates=list(commander.physical_entry_candidates(s))
    bad=ToolIntent(tool="MARKET_HEIST",territory_id="HIST",lane=Lane.TACTICAL,
                   side=bad_side,action=Action.ENTER,opportunity_id=f"BAD:{name}",
                   max_price=bad_ask,size_tier=10.0,reason="HISTORICAL_COUNTER_RAIL_ATTEMPT",
                   source_time=s.now_ts,metadata={"mission":{"counter_parent_fade":True}})
    d=commander.decide(candidates+[bad],s)
    actual={"action":d.action.value,"side":d.intent.side.value if d.intent and d.intent.side else None,
            "reason":d.reason,"candidate_reasons":[x.reason for x in candidates]+[bad.reason]}
    return {"name":name,"kind":"HISTORICAL_CONTROL",
            "expected":{"action":expect_action,"side":expect_side},"actual":actual,
            "pass":actual["action"]==expect_action and actual["side"]==expect_side,
            "points":[{"t":2240,"btc":135 if rail_side is Side.YES else 105,"ema9":132 if rail_side is Side.YES else 108,"tp":120},
                      {"t":2300,"btc":145 if rail_side is Side.YES else 95,"ema9":140 if rail_side is Side.YES else 100,"tp":120}]}


def historical_value_and_mountain_cases() -> list[dict[str, Any]]:
    cases=[]
    # PID7704 #9: aligned NO at .72 was directionally right but value-poor.
    s=snap(t=2400,btc=90,ema9=96,target=120,yes_ask=.28,no_ask=.72,
           meta={"commander_strategy":{"owned_territory":"DOWN_RAIL","owned_side":"NO","active_tool":"RAIL"},
                 "leg_echo":{"live_contract_count":1}})
    cases.append(entry_case("pid7704_9_aligned_but_72c_too_expensive",s,"WAIT",None,
        [{"t":2340,"btc":105,"ema9":108,"tp":120},{"t":2400,"btc":90,"ema9":96,"tp":120}]))
    # Oct31 missed ~00:53 peak: true UP parent edge offered NO around 6.7c.
    s=snap(t=2500,btc=155,ema9=150,target=130,yes_ask=.933,no_ask=.067,
           meta={"mountain":{"owner_side":"YES","current_arc_id":"OCT31-0053",
                             "terminal_evidence_qualified":True,"strong_active_release":False,
                             "edge_id":"OCT31-0053-TOP"}})
    cases.append(entry_case("oct31_0053_true_mountain_peak_067_no",s,"ENTER","NO",
        [{"t":2440,"btc":142,"ema9":140,"tp":130},{"t":2470,"btc":150,"ema9":146,"tp":130},
         {"t":2500,"btc":155,"ema9":150,"tp":130}]))
    # Smooth directional late scene: 4c opposite contract alone is no motive.
    s=snap(t=2600,btc=170,ema9=165,target=120,yes_ask=.96,no_ask=.04,contract_age=825,
           meta={"commander_strategy":{"owned_territory":"ROLLING_MOUNTAIN","owned_side":"YES","active_tool":"ROLLING_MOUNTAIN"},
                 "mountain":{"owner_side":"YES","current_arc_id":"SMOOTH-UP","strong_active_release":True},
                 "release_in_progress":True,"release_candidate_side":"YES",
                 "leg_echo":{"median_pullback_count":0,"median_pullback_btc":8.0}})
    # The release side is too expensive here, so WAIT is correct; 4c NO must not substitute.
    cases.append(entry_case("oct31_smooth_leg_4c_opposite_is_not_motive",s,"WAIT",None,
        [{"t":2540,"btc":150,"ema9":147,"tp":120},{"t":2570,"btc":160,"ema9":155,"tp":120},
         {"t":2600,"btc":170,"ema9":165,"tp":120}]))
    return cases


def pid22736_raw_classification_cases() -> list[dict[str, Any]]:
    """Replay the exact raw geometry around PID22736 trades #1-#5."""
    fixture = Path(__file__).parent / "tests" / "tool_rack" / "fixtures" / "pid22736_geometry.jsonl"
    rows = [json.loads(line) for line in fixture.read_text(encoding="utf-8").splitlines()]
    specs = [
        ("pid22736_1_false_rail_midleg", 1793478732.3156896, 77439.48, .56, .44, Side.NO),
        ("pid22736_2_ema_tp_junction_wait", 1793479151.316993, 77439.48, .78, .23, Side.YES),
        ("pid22736_3_not_slowwide_one_second_hold", 1793479544.2206347, 77435.26, .55, .45, Side.NO),
        ("pid22736_4_down_parent_not_yes_release", 1793479953.1968653, 77435.26, .39, .61, Side.NO),
        ("pid22736_5_expanding_down_not_terminal_yes", 1793480134.8673508, 77435.26, .20, .80, Side.NO),
    ]
    cases = []
    for name, ts, target, yes_ask, no_ask, owner_side in specs:
        causal = [r for r in rows if r["epoch_ms"] <= ts * 1000.0]
        last = causal[-1]
        mountain = detect_mountain_geometry(causal)
        rail = detect_rail_geometry(causal)
        probe = build_release_probe(causal, mountain=mountain)
        release = detect_release_for_owner(
            probe, owner_territory=Territory.ALTERNATING_MOUNTAIN, owner_side=owner_side)
        release_active = ToolRackController._release_in_progress(release.evidence)
        base_meta = {
            "physical_current": True,
            "geometry_last_epoch_ms": last["epoch_ms"],
            "geometry_continuity_generation": 1,
            "current_geometry": last,
            "mission_context": {"contract": {"target": target, "remaining_seconds": 900.0}},
            "commander_strategy": {
                "owned_territory": "ALTERNATING_MOUNTAIN",
                "owned_side": mountain.owner_side.value if mountain.owner_side else None,
                "active_tool": "ALTERNATING_MOUNTAIN",
            },
            "mountain": mountain.tool_metadata(),
            "heist": {"qualified_box": False},
            "release_in_progress": release_active,
            "release_candidate_side": (
                release.evidence.candidate_side.value if release.evidence.candidate_side else None),
            "rail_detector": dict(rail.diagnostics),
            "leg_echo": {},
        }
        pre = MarketSnapshot(
            now_ts=ts, ticker="KX-PID22736", contract_age_s=300,
            yes_ask=yes_ask, no_ask=no_ask, metadata=base_meta)
        tp = build_tp_geometry(pre)
        s = MarketSnapshot(**{**pre.__dict__, "metadata": {**base_meta, "tp_geometry": tp}})
        actual = decide_entry(s)
        detector = {
            "mountain": mountain.qualified_alternating_mountain,
            "rail": rail.qualified_rail,
            "terminal": mountain.diagnostics.get("terminal_evidence_qualified"),
            "release": release_active,
            "tp_junction": tp.get("target_between_ema9_ema30"),
            "parent_extended": mountain.diagnostics.get("parent_structure", {}).get("extended_parent"),
        }
        passed = actual["action"] == "WAIT"
        # Trade #3 also had a one-second stale/release exit.  Re-run custody one
        # second later with the same causal structure; it must HOLD.
        if name.startswith("pid22736_3_"):
            pos = {"position_id":"PID22736-3","ticker":"KX-PID22736","territory_id":"ALTERNATING_MOUNTAIN",
                   "opportunity_id":"COMMANDER:SLOW_WIDE_ROLLOVER:NO:E000A000011",
                   "tool":"ONE_COMMANDER_PRIMARY","lane":"MAIN","side":Side.NO,
                   "entry_price":.45,"entry_time":ts,"close_ts":ts+900,
                   "custody_state":"NORMAL","entry_metadata":{},"floor_bid":None}
            hold = OneCommander().decide_position([], s, pos)
            actual["one_second_custody_action"] = hold.action.value
            actual["one_second_custody_reason"] = hold.reason
            passed = passed and hold.action is Action.HOLD
        actual["detectors"] = detector
        pts = []
        for row in causal[-120::20] or causal[-1:]:
            pts.append({"t":row["epoch_ms"]/1000.0,"btc":float(row["btc_price"]),
                        "ema9":float(row["ema9"]),"tp":target})
        if not pts or pts[-1]["t"] != last["epoch_ms"]/1000.0:
            pts.append({"t":last["epoch_ms"]/1000.0,"btc":float(last["btc_price"]),
                        "ema9":float(last["ema9"]),"tp":target})
        cases.append({"name":name,"kind":"HISTORICAL_RAW_PID22736",
                      "expected":{"action":"WAIT","side":None},"actual":actual,
                      "pass":passed,"points":pts})
    return cases


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    # Fresh release: follow the live leg even while the opposite contract is crushed.
    s = snap(t=1000, btc=101, ema9=100, target=99, yes_ask=.44, no_ask=.05,
             meta={"release_in_progress": True, "release_candidate_side": "YES"})
    cases.append(entry_case("fresh_release_follow_not_cheap_fade", s, "ENTER", "YES",
        [{"t":940,"btc":98,"ema9":98,"tp":99},{"t":970,"btc":99.5,"ema9":99,"tp":99},{"t":1000,"btc":101,"ema9":100,"tp":99}]))

    # True Mountain terminal edge remains a value-at-extreme reversal.
    s = snap(t=1100, btc=120, ema9=117, target=108, yes_ask=.82, no_ask=.18,
             meta={"mountain":{"owner_side":"YES","terminal_evidence_qualified":True,
                               "strong_active_release":False,"edge_id":"M-TOP"},
                   "tp_geometry":{"target":108,"btc":120,"observed_target_side":"YES","required_move_to_target_btc":12,
                                  "contract_ownership":"BOUNCE_FAVORED","contract_ownership_side":"NO"}})
    cases.append(entry_case("mountain_true_peak_return", s, "ENTER", "NO",
        [{"t":1040,"btc":106,"ema9":105,"tp":108},{"t":1070,"btc":116,"ema9":112,"tp":108},{"t":1100,"btc":120,"ema9":117,"tp":108}]))

    # Cheapness alone / first pullback cannot create a fade.
    s = snap(t=1200, btc=130, ema9=126, target=110, yes_ask=.95, no_ask=.05,
             meta={"mountain":{"mature_edge":True,"owner_side":"YES","current_arc_id":"A1"},
                   "leg_echo":{"side":"YES","live_pullback_count":0,"median_pullback_count":0,
                               "live_current_child":{"side":"YES"}}})
    cases.append(entry_case("first_pullback_cheapness_not_motive", s, "WAIT", None,
        [{"t":1140,"btc":120,"ema9":118,"tp":110},{"t":1170,"btc":125,"ema9":122,"tp":110},{"t":1200,"btc":130,"ema9":126,"tp":110}]))

    # Later pullback can become a qualified renter when current extreme is mature.
    s = snap(t=1300, btc=134, ema9=130, target=125, yes_ask=.86, no_ask=.14,
             meta={"mountain":{"mature_edge":True,"owner_side":"YES","current_arc_id":"A3"},
                   "leg_echo":{"side":"YES","live_pullback_count":1,"median_pullback_count":2,
                               "median_pullback_btc":35.0,"live_current_child":{"side":"YES"}},
                   "tp_geometry":{"target":125,"btc":134,"observed_target_side":"YES","required_move_to_target_btc":9,
                                  "contract_ownership":"UNRESOLVED","contract_ownership_side":None}})
    cases.append(entry_case("later_pullback_fade_earned", s, "ENTER", "NO",
        [{"t":1240,"btc":125,"ema9":123,"tp":125},{"t":1270,"btc":129,"ema9":127,"tp":125},{"t":1300,"btc":134,"ema9":130,"tp":125}]))

    # TP impossible late-ish fade: required move exceeds demonstrated pullback.
    s = snap(t=1400, btc=80, ema9=85, target=170, yes_ask=.05, no_ask=.95, contract_age=780,
             meta={"mountain":{"mature_edge":True,"owner_side":"NO","current_arc_id":"D3"},
                   "leg_echo":{"side":"NO","live_pullback_count":2,"median_pullback_count":3,
                               "median_pullback_btc":25.0,"live_current_child":{"side":"NO"}},
                   "tp_geometry":{"target":170,"btc":80,"observed_target_side":"NO","required_move_to_target_btc":90,
                                  "contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"NO"}})
    cases.append(entry_case("tp_required_move_blocks_counter_fade", s, "WAIT", None,
        [{"t":1340,"btc":115,"ema9":112,"tp":170},{"t":1370,"btc":96,"ema9":100,"tp":170},{"t":1400,"btc":80,"ema9":85,"tp":170}]))

    # Repeated Heist range has demonstrated enough movement to permit return.
    s = snap(t=1500, btc=92, ema9=105, target=120, yes_ask=.18, no_ask=.82, contract_age=780,
             meta={"commander_strategy":{"owned_territory":"MARKET_HEIST","owned_side":None,"active_tool":"MARKET_HEIST"},
                   "heist":{"qualified_box":True,"release_confirmed":False,"at_lower_edge":True,
                            "box_id":"B1","visit_id":"V3","lower":90.0,"upper":150.0},
                   "leg_echo":{"median_pullback_btc":20.0},
                   "tp_geometry":{"target":120,"btc":92,"observed_target_side":"NO","required_move_to_target_btc":28,
                                  "contract_ownership":"UNRESOLVED","contract_ownership_side":None}})
    cases.append(entry_case("heist_demonstrated_return_survives", s, "ENTER", "YES",
        [{"t":1440,"btc":145,"ema9":120,"tp":120},{"t":1470,"btc":118,"ema9":119,"tp":120},{"t":1500,"btc":92,"ema9":105,"tp":120}]))

    # Established Rail primary can pay continuation value above Mountain cap.
    s = snap(t=1600, btc=140, ema9=136, target=120, yes_ask=.44, no_ask=.56,
             meta={"commander_strategy":{"owned_territory":"UP_RAIL","owned_side":"YES","active_tool":"RAIL"},
                   "leg_echo":{"live_contract_count":2}})
    cases.append(entry_case("established_rail_primary", s, "ENTER", "YES",
        [{"t":1540,"btc":128,"ema9":126,"tp":120},{"t":1570,"btc":134,"ema9":131,"tp":120},{"t":1600,"btc":140,"ema9":136,"tp":120}]))

    # Slow-wide rollover: starting leg favored and smooth history boards it.
    s = snap(t=1700, btc=145, ema9=140, target=130, yes_ask=.43, no_ask=.57, contract_age=60,
             meta={"mountain":{"owner_side":"YES","current_arc_id":"SW1",
                               "parent_structure":{"parent_id":"P-SW","parent_side":"YES","parent_age_s":700,"extended_parent":True,"prior_long_parent_count":1}},
                   "leg_echo":{"median_pullback_count":0},
                   "rail_detector":{"chapter_consistent":True},
                   "tp_geometry":{"target":130,"btc":145,"observed_target_side":"YES","required_move_to_target_btc":15,
                                  "contract_ownership":"STARTING_LEG_FAVORED","contract_ownership_side":"YES"}})
    cases.append(entry_case("slowwide_starting_leg_favored", s, "ENTER", "YES",
        [{"t":1640,"btc":133,"ema9":132,"tp":130},{"t":1670,"btc":139,"ema9":136,"tp":130},{"t":1700,"btc":145,"ema9":140,"tp":130}]))

    # Custody: developing large leg holds; terminal leg collects; committed floor exits.
    base_pos = {"position_id":"P1","ticker":"KX-CONSTRUCT","territory_id":"T1","opportunity_id":"O1",
                "tool":"ONE_COMMANDER_PRIMARY","lane":"MAIN","side":Side.YES,"entry_price":.20,
                "close_ts":2500.0,"custody_state":"NORMAL","entry_metadata":{},"floor_bid":None}
    s = snap(t=1800, btc=170, ema9=162, target=120, yes_ask=.61, no_ask=.39, yes_bid=.60, no_bid=.38,
             meta={"commander_strategy":{"owned_territory":"UP_RAIL","owned_side":"YES"},
                   "leg_echo":{"comparison_count":4,"comparison_quality":"USEFUL","live_age_ratio":.45,
                               "live_amplitude_ratio":.50,"completed_comparable_legs":[
                                   {"yes_opportunity":{"potential_roi_from_best_observed_basis":2.0}},
                                   {"yes_opportunity":{"potential_roi_from_best_observed_basis":3.0}},
                                   {"yes_opportunity":{"potential_roi_from_best_observed_basis":2.5}}]},
                   "tp_geometry":{"target":120,"btc":170,"observed_target_side":"YES"}})
    cases.append(position_case("large_directional_leg_holds", s, base_pos, "HOLD"))

    s2 = snap(t=1900, btc=176, ema9=170, target=120, yes_ask=.72, no_ask=.28, yes_bid=.70, no_bid=.26,
              meta={"commander_strategy":{"owned_territory":"ROLLING_MOUNTAIN","owned_side":"YES"},
                    "mountain":{"owner_side":"YES","terminal_evidence_qualified":True},
                    "tp_geometry":{"target":120,"btc":176,"observed_target_side":"YES"},
                    "leg_echo":{"comparison_count":4,"live_age_ratio":1.1,"live_amplitude_ratio":1.05}})
    cases.append(position_case("terminal_leg_collects", s2, base_pos, "EXIT"))

    s3 = snap(t=2000, btc=165, ema9=160, target=120, yes_ask=.58, no_ask=.42, yes_bid=.56, no_bid=.40,
              meta={"tp_geometry":{"target":120,"btc":165,"observed_target_side":"YES"}})
    cases.append(position_case("committed_floor_breach_is_objective", s3, base_pos, "EXIT", floor_breached=True))

    # Recovered Lazarus is normal winner custody; it may keep developing.
    recovered = dict(base_pos); recovered["custody_state"] = "RECOVERED_NORMAL"
    s4 = snap(t=2010, btc=168, ema9=163, target=120, yes_ask=.62, no_ask=.38, yes_bid=.60, no_bid=.36,
              meta={"commander_strategy":{"owned_territory":"UP_RAIL","owned_side":"YES"},
                    "leg_echo":{"comparison_count":4,"live_age_ratio":.50,"live_amplitude_ratio":.55,
                                "completed_comparable_legs":[
                                  {"yes_opportunity":{"potential_roi_from_best_observed_basis":2.0}},
                                  {"yes_opportunity":{"potential_roi_from_best_observed_basis":2.4}},
                                  {"yes_opportunity":{"potential_roi_from_best_observed_basis":3.0}}]},
                    "tp_geometry":{"target":120,"btc":168,"observed_target_side":"YES"}})
    cases.append(position_case("recovered_lazarus_can_keep_winning", s4, recovered, "HOLD"))

    # Slow/wide bounce-favored contract should not force inherited continuation.
    s5 = snap(t=2020, btc=105, ema9=108, target=110, yes_ask=.30, no_ask=.70, contract_age=60,
              meta={"mountain":{"owner_side":"NO","current_arc_id":"SW-B",
                                "parent_structure":{"parent_id":"P-SWB","parent_side":"NO","parent_age_s":800,"extended_parent":True,"prior_long_parent_count":1}},
                    "leg_echo":{"median_pullback_count":1},
                    "rail_detector":{"chapter_consistent":True},
                    "tp_geometry":{"target":110,"btc":105,"observed_target_side":"NO","required_move_to_target_btc":5,
                                   "contract_ownership":"BOUNCE_FAVORED","contract_ownership_side":"YES"}})
    cases.append(entry_case("slowwide_bounce_favored_waits_for_turn", s5, "WAIT", None,
        [{"t":1960,"btc":120,"ema9":117,"tp":110},{"t":1990,"btc":111,"ema9":112,"tp":110},{"t":2020,"btc":105,"ema9":108,"tp":110}]))

    cases.append(sequence_edge_relay_case())
    cases.append(false_newborn_handoff_case())
    cases.append(raw_rail_recognition_case(shrinking=False))
    cases.append(raw_rail_recognition_case(shrinking=True))
    cases.append(raw_rail_fakeout_case())
    cases.append(raw_anomaly_candle_case())
    cases.append(pid4756_release_flicker_case(down=False))
    cases.append(pid4756_release_flicker_case(down=True))
    # Saved historical PAPER controls: wrong-way Rail fades must not displace
    # the living Rail/Release; a valid direction can still be rejected on value.
    cases.append(historical_rail_conflict_case(
        name="hf10_4_no43_against_ascending_rail", rail_side=Side.YES, rail_ask=.48,
        bad_side=Side.NO, bad_ask=.43, expect_action="WAIT", expect_side=None))
    cases.append(historical_rail_conflict_case(
        name="hf10_6_yes34_against_descending_rail", rail_side=Side.NO, rail_ask=.44,
        bad_side=Side.YES, bad_ask=.34, expect_action="ENTER", expect_side="NO"))
    cases.extend(historical_value_and_mountain_cases())
    cases.extend(pid22736_raw_classification_cases())
    return cases


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    cases = build_cases()
    failures = []
    index = []
    for case in cases:
        case_dir = args.output / case["name"]
        case_dir.mkdir(parents=True, exist_ok=False)
        write_json(case_dir / "result.json", {k:v for k,v in case.items() if k != "points"})
        markers = []
        actual = case["actual"]
        if actual["action"] in ("ENTER","EXIT"):
            last = case["points"][-1]
            markers.append({"t":last["t"],"btc":last["btc"],"action":actual["action"],"side":actual.get("side")})
        svg_plot(case_dir / "plot.svg", case["points"], markers, case["name"])
        index.append({"name":case["name"],"pass":case["pass"],"expected":case["expected"],"actual":case["actual"]})
        if not case["pass"]: failures.append(case["name"])
        print(json.dumps(index[-1], sort_keys=True), flush=True)
    report = {"kind":"ONE_COMMANDER_CONSTITUTION_CONSTRUCT_V1","synthetic":True,
              "case_count":len(cases),"pass_count":len(cases)-len(failures),"failures":failures,"cases":index}
    write_json(args.output / "report.json", report)
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
