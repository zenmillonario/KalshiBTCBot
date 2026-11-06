from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from strategy_core.commander import OneCommander
from strategy_core.lane_resolver import LaneResolver
from strategy_core.mission_policy import MissionPolicy
from strategy_core.tool_rack import _positive_briefing
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from tests.tool_rack.test_mountain_only_reset import synthetic_terminal_snapshot
from tests.tool_rack.test_opportunity_first_commander import real_heist_snapshot
from tests.tool_rack.test_authorized_reactivation import snap as synthetic_release_snapshot


def snap(*, yes=.15, no=.15, metadata=None, entry_allowed=True, quote_current=True, depth_available=True):
    md={
        "physical_current": True,
        "geometry_last_epoch_ms": 1_000_000.0,
        "geometry_continuity_generation": 1,
        "current_geometry": {},
        "mountain": {},
        "tp_geometry": {"target_between_ema9_ema30": False},
    }
    if metadata:
        md.update(metadata)
    return MarketSnapshot(now_ts=1000.0,ticker="KX-CONSTRUCT",contract_age_s=300.0,
        yes_ask=yes,no_ask=no,yes_bid=max(.001,yes-.01),no_bid=max(.001,no-.01),
        entry_allowed=entry_allowed,quote_current=quote_current,depth_available=depth_available,
        metadata=md)


def commander_edge(side=Side.YES, price=.20):
    return ToolIntent(tool="ONE_COMMANDER_PRIMARY",territory_id="MOUNTAIN_EDGE",lane=Lane.MAIN,
        side=side,action=Action.ENTER,opportunity_id="CMD_EDGE",max_price=price,size_tier=15,
        reason="COMMANDER_LEVEL_MATCH_RETURN",source_time=1000.0,metadata={
            "commander_primary_candidate":True,"commander_candidate_family":"MOUNTAIN_EDGE",
            "commander_physical_evidence":{"entry_location":"RECENT_LEVEL_MATCH_RETURN"}})


def wait(tool, reason, side=Side.YES, lane=Lane.MAIN):
    return ToolIntent(tool=tool,territory_id=f"{tool}:OBS",lane=lane,side=side,action=Action.WAIT,
        opportunity_id=None,max_price=None,size_tier=None,reason=reason,source_time=1000.0,
        metadata={"authority":"ADVISORY_ONLY"})


def actionable(tool, reason, side, price, lane=Lane.TACTICAL, metadata=None):
    return ToolIntent(tool=tool,territory_id=f"{tool}:ENTRY",lane=lane,side=side,action=Action.ENTER,
        opportunity_id=f"{tool}:{side.value}",max_price=price,size_tier=10,reason=reason,
        source_time=1000.0,metadata=metadata or {})


def check(label, condition, detail=""):
    if not condition:
        raise AssertionError(f"FAIL {label}: {detail}")
    print(f"PASS | {label}")


def admitted(decision, proposal):
    """Admission may attach proof/custody, but not change order economics."""
    intent=decision.intent
    return (decision.action in (Action.ENTER,Action.RELAY) and intent is not None
        and all(getattr(intent,key)==getattr(proposal,key)
                for key in ("tool","territory_id","side","opportunity_id","max_price","size_tier","source_time"))
        and intent.metadata.get("commander_opportunity",{}).get("qualified") is True)


def main():
    c=OneCommander()
    # Numeric synthetic terminal/repeated-range/transfer premises below are
    # authored mechanics controls, never enriched archived observations.
    s=synthetic_terminal_snapshot(side=Side.YES,ask=.15,ticker="KX-CONSTRUCT")
    edge=next(i for i in c.physical_entry_candidates(s) if i.side is Side.YES)

    # Each active specialist can say WAIT and still cannot veto the Commander's
    # independently qualified physical entry.
    tool_waits=[
        ("MOUNTAIN", wait("ALTERNATING_MOUNTAIN","MOUNTAIN_WAIT_FOR_TERMINAL_EMA9_EDGE_NEVER_MIDDLE")),
        ("MARKET_HEIST", wait("MARKET_HEIST","HEIST_PARALLEL_EXCURSION_ARMED_AWAIT_RETURN",lane=Lane.TACTICAL)),
        ("RAIL", wait("RAIL","RAIL_LATE_DYNAMIC_TP_RUNWAY_BLOCK")),
        ("RELEASE", wait("RELEASE_WATCHER","RELEASE_OWNER_RETAINED_NEW_ENTRY_PROOF_NOT_CURRENT",lane=Lane.HANDOFF)),
    ]
    for name,w in tool_waits:
        d=c.decide_entry([w,edge],s,{})
        check(f"{name} WAIT is telemetry only", admitted(d,edge), d.reason)

    # All specialist waits at once still cannot starve Commander.
    d=c.decide_entry([w for _,w in tool_waits]+[edge],s,{})
    check("ALL SPECIALIST WAITs cannot form a committee veto", admitted(d,edge), d.reason)

    # MissionPolicy may dislike an actionable proposal, but review must preserve
    # the action; its opinion is metadata only.
    raw=actionable("MARKET_HEIST","HEIST_OUTER_EDGE_TACTICAL_RENTER",Side.YES,.20,
        metadata={"mission_context":{"current":True}})
    reviewed=MissionPolicy().review(raw,s)
    check("MissionPolicy cannot mutate action", reviewed.action is Action.ENTER,
          str(reviewed.metadata.get("mission_policy_advice")))

    # LaneResolver may produce a legacy shadow WAIT/suppression result, but the
    # full adviser set + Commander candidate is what decides execution.
    resolver=LaneResolver()
    shadow=resolver.resolve(primary=(wait("ALTERNATING_MOUNTAIN","MOUNTAIN_WAIT_FOR_TERMINAL_EMA9_EDGE_NEVER_MIDDLE"),),
        overlays=(wait("RELEASE_WATCHER","RELEASE_OWNER_RETAINED_NEW_ENTRY_PROOF_NOT_CURRENT",lane=Lane.HANDOFF),),
        handoff_confirmed=True)
    d=c.decide_entry([edge],s,{})
    check("LaneResolver is diagnostic only", shadow.reason.startswith("CONFIRMED_HANDOFF") and d.action is Action.ENTER,
          shadow.reason)

    # Multiple actionable advisers are ranked by Commander, not turned into a
    # veto because more than one tool spoke.
    heist=actionable("MARKET_HEIST","HEIST_OUTER_EDGE_TACTICAL_RENTER",Side.YES,.20,
        metadata={"mission":{"neutral_heist_repeatable":True}})
    rail=actionable("RAIL","RAIL_MAIN_VALUE",Side.YES,.35,lane=Lane.MAIN)
    s2=replace(real_heist_snapshot(),yes_ask=.15,yes_bid=.14)
    d=c.decide_entry([heist,rail],s2,{})
    check("Multiple adviser entries retain a physically qualified choice", admitted(d,heist), d.reason)

    # Confirmed Release remains an actionable candidate, but Release WAIT is not authority.
    release=actionable("RELEASE_WATCHER","RELEASE_CONFIRMED_LEVIATHAN_HANDOFF",Side.YES,.20,lane=Lane.HANDOFF,
        metadata={"release_entry_proof":{"qualified":True,"observed_at":1000.,
            "candidate_side":"YES","boundary_break":True,"directional_expansion":True,
            "new_side_residence":True}})
    original_release=deepcopy(release)
    s3=synthetic_release_snapshot(yes=.15,no=.85,metadata={
        "commander_strategy":{"handoff_confirmed":True},"release_candidate_side":"YES"})
    d=c.decide_entry([wait("RELEASE_WATCHER","RELEASE_OWNER_RETAINED_NEW_ENTRY_PROOF_NOT_CURRENT",lane=Lane.HANDOFF),release],s3,{})
    # PID17224 A resolves Release custody before booking. Compare every intent
    # field and all original metadata, allowing only the authorized custody
    # additions for this unchanged empty-mission fixture. Python object
    # identity must not prohibit that resolution or replace physical identity.
    check("Release actionable handoff is evaluated; Release WAIT is ignored",
          admitted(d,release) and d.reason=="COMMANDER_ACCEPTED_TOOL_INTENT"
          and d.intent.metadata.get("position_role")=="PRIMARY"
          and d.intent.metadata.get("custody")=="LEVIATHAN_RELEASE"
          and d.intent.metadata.get("commander_release_custody_admission",{}).get("basis")=="CURRENT_CONFIRMED_RELEASE_HANDOFF"
          and release==original_release, d.reason)

    # Commander-owned Quote-Wave and Edge-Heist tactical paths also remain
    # independent of specialist WAIT telemetry.
    quote_wave=ToolIntent(tool="ONE_COMMANDER_PRIMARY",territory_id="QUOTE_WAVE_SCALP",lane=Lane.TACTICAL,
        side=Side.YES,action=Action.ENTER,opportunity_id="QW",max_price=.08,size_tier=10,
        reason="COMMANDER_QUOTE_WAVE_SCALP",source_time=1000.0,metadata={
            "commander_primary_candidate":True,"commander_candidate_family":"QUOTE_WAVE_SCALP"})
    qs=replace(real_heist_snapshot(),yes_ask=.07,yes_bid=.06)
    d=c.decide_entry([w for _,w in tool_waits]+[quote_wave],qs,{})
    check("Qualified QUOTE_WAVE path cannot be vetoed by specialist WAITs", admitted(d,quote_wave), d.reason)

    edge_heist=ToolIntent(tool="ONE_COMMANDER_PRIMARY",territory_id="EDGE_HEIST",lane=Lane.TACTICAL,
        side=Side.NO,action=Action.ENTER,opportunity_id="EH",max_price=.35,size_tier=10,
        reason="COMMANDER_EDGE_HEIST_RETURN",source_time=1000.0,metadata={
            "commander_primary_candidate":True,"commander_candidate_family":"EDGE_HEIST"})
    hs=real_heist_snapshot(price=109.);hm=deepcopy(hs.metadata)
    hm['heist'].update(at_lower_edge=False,at_upper_edge=True,current_zone='UPPER',visit_id='UPPER2')
    hm['current_geometry'].update(ema9=105.,ema30=103.,btc_change6=-2.,btc_change9=-3.,ema9_change6=-.4)
    hs=replace(hs,yes_ask=.75,no_ask=.25,yes_bid=.74,no_bid=.24,metadata=hm)
    d=c.decide_entry([w for _,w in tool_waits]+[edge_heist],hs,{})
    check("Qualified EDGE_HEIST path cannot be vetoed by specialist WAITs", admitted(d,edge_heist), d.reason)


    # Positive briefing translation: advisers stay quiet until they have
    # something useful to tell the General. These records are advisory only.
    mountain_brief=_positive_briefing(wait("ALTERNATING_MOUNTAIN","MOUNTAIN_EDGE_ARMED_AWAIT_SUB20_PULLBACK",Side.NO))
    check("MOUNTAIN emits FISH briefing", mountain_brief is not None and mountain_brief.get("state")=="FISH" and mountain_brief.get("side")=="NO")
    heist_brief=_positive_briefing(wait("MARKET_HEIST","HEIST_PARALLEL_EXCURSION_ARMED_AWAIT_RETURN",Side.YES,lane=Lane.TACTICAL))
    check("MARKET_HEIST emits PREPARE briefing", heist_brief is not None and heist_brief.get("state")=="PREPARE" and heist_brief.get("side")=="YES")
    rail_brief=_positive_briefing(actionable("RAIL","RAIL_MAIN_VALUE",Side.NO,.35,lane=Lane.MAIN))
    check("RAIL emits ENTRY_WINDOW briefing", rail_brief is not None and rail_brief.get("state")=="ENTRY_WINDOW" and rail_brief.get("side")=="NO")
    release_wait=wait("RELEASE_WATCHER","RELEASE_CONFIRMED_BUT_PRICE_ABOVE_SOFT_VALUE",Side.YES,lane=Lane.HANDOFF)
    release_brief=_positive_briefing(replace(release_wait,max_price=.30))
    check("RELEASE emits FISH briefing", release_brief is not None and release_brief.get("state")=="FISH" and release_brief.get("side")=="YES")
    qbrief=_positive_briefing(quote_wave)
    check("QUOTE_WAVE emits ENTRY_WINDOW briefing", qbrief is not None and qbrief.get("state")=="ENTRY_WINDOW")
    ehbrief=_positive_briefing(edge_heist)
    check("EDGE_HEIST emits ENTRY_WINDOW briefing", ehbrief is not None and ehbrief.get("state")=="ENTRY_WINDOW")

    # Objective safety remains independent after Commander qualification.
    d=c.decide_entry([edge],replace(s,quote_current=False),{})
    check("Objective stale quote still blocks", d.action is Action.WAIT and d.reason=="OBJECTIVE_QUOTE_STALE", d.reason)
    d=c.decide_entry([edge],replace(s,depth_available=False),{})
    check("Objective missing depth still blocks", d.action is Action.WAIT and d.reason=="OBJECTIVE_DEPTH_UNAVAILABLE", d.reason)
    d=c.decide_entry([edge],replace(s,entry_allowed=False),{})
    check("Objective entry-disabled still blocks", d.action is Action.WAIT and d.reason=="OBJECTIVE_ENTRY_NOT_ALLOWED", d.reason)

    print("PASS | TOOL ADVISORY AUTHORITY CONSTRUCT | 19/19 controls")


if __name__ == "__main__":
    main()
