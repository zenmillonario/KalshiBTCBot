from __future__ import annotations

from strategy_core.commander import OneCommander
from strategy_core.commander_candidates import (
    ema9_continuation_precedent, physical_entry_candidates,
    positive_candidate_matches_continuation,
)
from strategy_core.paper_execution import PaperPosition
from strategy_core.paper_runtime import ToolRackPaperEngine
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent


def snap(*, t=1000.0, yes=.40, no=.60, owner="YES", gap_side="NO", stage="SPROUT", stall=False):
    md={
        "physical_current":True,"geometry_last_epoch_ms":t*1000.0,"geometry_continuity_generation":1,
        "current_geometry":{},
        "mountain":{"owner_side":owner,"stall":stall,"hesitation":False,
            "failed_reextension":False,"meaningful_retreat":False,
            "terminal_evidence_qualified":False,"mature_edge":False,"edge_window_active":False,
            "strong_active_release":False,
            "current_motion":{"30":{"covered":True,"owner_price_rate_btc_s":1.1,"owner_ema9_rate_btc_s":.22},
                              "60":{"covered":True,"owner_price_rate_btc_s":.9,"owner_ema9_rate_btc_s":.28}}},
        "ema9_ema30_cross_context":{"current_side":gap_side,
            "current_signed_gap_btc":-11.0 if gap_side=="NO" else 11.0,
            "previous_observed_cross_present":True,"observed_cross_count":4,
            "recent_crossings":[{"direction":owner,"observed_continuously":True},
                                {"direction":gap_side,"observed_continuously":True}],
            "gap_lifecycle":{"stage":stage,"current_side":gap_side,
                "current_abs_gap_btc":11.0,"gap_expanding_6s":True}},
        "tp_geometry":{"target_between_ema9_ema30":False},
        "commander_strategy":{"owned_side":owner,"owned_territory":"MARKET_HEIST"},
    }
    return MarketSnapshot(now_ts=t,ticker="KX-PID7812",contract_age_s=300.0,
        yes_ask=yes,no_ask=no,yes_bid=max(.001,yes-.01),no_bid=max(.001,no-.01),
        yes_sell_allowed=True,no_sell_allowed=True,metadata=md)


def intent(side: Side, *, tool="MARKET_HEIST") -> ToolIntent:
    return ToolIntent(tool=tool,territory_id="H",lane=Lane.TACTICAL,side=side,
        action=Action.ENTER,opportunity_id="C",max_price=.35,size_tier=10.0,
        reason="HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED",source_time=1000.0,
        metadata={"position_role":"TACTICAL"})


def main() -> int:
    rows=[]
    yes=snap()
    ev=ema9_continuation_precedent(yes)
    rows.append(("pid7812_18_yes_cross_precedent", ev.get("qualified") is True and ev.get("side")=="YES", str(ev)))

    pos={"position_id":"18","ticker":"KX-PID7812","side":Side.YES,"entry_price":.40,
         "entry_time":900.0,"close_ts":1900.0,"tool":"MARKET_HEIST","territory_id":"H",
         "opportunity_id":"18","lane":Lane.TACTICAL,"custody_state":"NORMAL",
         "position_role":"PRIMARY","entry_reason":"HEIST_PARALLEL_STALLED_EDGE_RETURN",
         "entry_metadata":{"position_role":"PRIMARY"}}
    d=OneCommander().decide_position((),yes,pos)
    rows.append(("pid7812_18_promotes_to_main", d.action is Action.HOLD and
        d.reason=="COMMANDER_HEIST_SEED_PROMOTED_TO_LIVING_EMA9_CUSTODY" and
        (d.custody_update or {}).get("state")=="PROMOTED_MAIN", d.reason))

    pp=PaperPosition("18","KX-PID7812",Side.YES,25,.40,10.0,0.0,900.0,1900.0,
        "MARKET_HEIST","H","18",Lane.TACTICAL,"Q","HEIST_PARALLEL_STALLED_EDGE_RETURN",
        {"floor_policy":{"arm_roi":.40,"trail_fraction":.03,"min_age_s":0.0,
                         "immediate_arm_roi":.40,"first_arm_from_current_bid":True}},
        .80,None,None,False,None,position_role="PRIMARY")
    pol=ToolRackPaperEngine._floor_policy((),pp,snap(yes=.81,no=.19))
    rows.append(("pid7812_18_old_quick_floor_deferred", pol.arm_roi==2.0 and pol.immediate_arm_roi==2.0,
                 f"arm={pol.arm_roi} immediate={pol.immediate_arm_roi}"))

    rows.append(("pid7812_19_no_briefing_suppressed",
        not positive_candidate_matches_continuation(intent(Side.NO),yes),"NO vs YES precedent"))

    fresh=snap(yes=.90,no=.10,owner="YES",gap_side="YES",stage="SPROUT")
    fresh.metadata["mountain"].update({"qualified":True,"qualified_alternating_mountain":True,
        "current_arc_id":"YES-SPROUT","source_ms":1000000.0,"edge_extreme_ms":990000.0,
        "spent_edge":False,"full_leg_scale_evidence":{"qualified":True},
        "diagnostics":{"current_age_s":500.0}})
    fresh.metadata["mission_context"]={"parent":{"side":"YES","measurements":{"age_seconds":500.0}}}
    raw=physical_entry_candidates(fresh)
    filtered=OneCommander().physical_entry_candidates(fresh)
    # PID8552 moves suppression earlier: no cheap opposite candidate need be
    # constructed at all during a fresh expanding SPROUT.
    rows.append(("pid7812_20_cheap_no_fade_suppressed", raw==() and filtered==(),
                 f"raw={len(raw)} filtered={len(filtered)}"))

    no=snap(owner="NO",gap_side="NO",stage="SPROUT",yes=.15,no=.85)
    rows.append(("mirror_yes_fade_suppressed",
        not positive_candidate_matches_continuation(intent(Side.YES),no),"YES vs NO sprout"))

    release=intent(Side.NO,tool="RELEASE_WATCHER")
    rows.append(("confirmed_opposite_release_can_replace_sprout",
        positive_candidate_matches_continuation(release,yes,confirmed_release_side=Side.NO),"release handoff"))

    weak=snap(stall=True)
    rows.append(("weakness_retires_precedent", ema9_continuation_precedent(weak).get("qualified") is False,
                 str(ema9_continuation_precedent(weak))))

    promoted={**pos,"custody_state":"PROMOTED_MAIN","entry_time":600.0}
    hold=OneCommander().decide_position((),snap(t=1000.0),promoted)
    rows.append(("promoted_seed_survives_old_tactical_timeout",
        hold.action is Action.HOLD and "MAX_HOLD" not in hold.reason,hold.reason))

    passed=sum(ok for _,ok,_ in rows)
    print(f"PID7812 SPROUT PROMOTION CONSTRUCT: {passed}/{len(rows)} PASS")
    for name,ok,detail in rows:
        print(("PASS" if ok else "FAIL"),name,detail)
    return 0 if passed==len(rows) else 1


if __name__=="__main__":
    raise SystemExit(main())
