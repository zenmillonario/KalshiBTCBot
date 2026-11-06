from __future__ import annotations

from strategy_core.commander import OneCommander
from strategy_core.paper_execution import PaperPosition
from strategy_core.paper_runtime import ToolRackPaperEngine
from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from tests.tool_rack.test_opportunity_first_commander import parent_snapshot


def snap(*, t=1000.0, yes=.15, no=.85, metadata=None):
    md={"physical_current":True,"geometry_last_epoch_ms":t*1000.0,
        "geometry_continuity_generation":1,"current_geometry":{},"mountain":{},
        "tp_geometry":{"target_between_ema9_ema30":False},"commander_strategy":{}}
    if metadata: md.update(metadata)
    return MarketSnapshot(now_ts=t,ticker="KX-AUTH",contract_age_s=300.0,
        yes_ask=yes,no_ask=no,yes_bid=max(.001,yes-.01),no_bid=max(.001,no-.01),
        yes_sell_allowed=True,no_sell_allowed=True,metadata=md)


def main():
    rows=[]
    c=OneCommander()
    # 1. Wrong-side PRIMARY cannot own custody over living EMA9 parent.
    pos={"position_id":"P-WRONG","ticker":"KX-AUTH","side":Side.YES,"entry_price":.20,
         "entry_time":900.0,"close_ts":1900.0,"tool":"ONE_COMMANDER_PRIMARY",
         "territory_id":"MOUNTAIN_CONTRACT_LEG","opportunity_id":"WRONG","lane":Lane.MAIN,
         "custody_state":"NORMAL","position_role":"PRIMARY","entry_metadata":{"position_role":"PRIMARY"}}
    s=snap(metadata={"mission_context":{"parent":{"id":"P-DOWN","side":"NO","status":"ACTIVE","supported":True}},
                     "commander_strategy":{"owned_side":"YES"},
                     "mountain":{"owner_side":"YES","parent_structure":{"parent_side":"NO","parent_terminal_ready":False}}})
    d=c.decide_position((),s,pos)
    rows.append(("wrong_side_primary_exits", d.action is Action.EXIT and d.intent is not None
                 and d.intent.reason=="COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT", d.reason))

    # 2. Physical parent controls +200% first-floor runway even if stale owner label disagrees.
    p=PaperPosition("P2","KX-AUTH",Side.NO,10,.29,2.9,0.0,900.0,1900.0,
        "ONE_COMMANDER_PRIMARY","MOUNTAIN_CONTRACT_LEG","O2",Lane.MAIN,"Q","R",
        {"floor_policy":{"arm_roi":1.0,"trail_fraction":.05,"min_age_s":0.0,
                         "immediate_arm_roi":1.0,"first_arm_from_current_bid":True,
                         "roi_trail_tiers":[[1.5,.03]]}},None,None,None,False,None,
        position_role="PRIMARY")
    live=snap(yes=.40,no=.60,metadata={"mission_context":{"parent":{"id":"P-DOWN","side":"NO","status":"ACTIVE","supported":True}},
        "commander_strategy":{"owned_side":"YES"},
        "mountain":{"owner_side":"YES","parent_structure":{"parent_side":"NO","parent_terminal_ready":False},
                    "terminal_evidence_qualified":False,"stall":False,"hesitation":False}})
    pol=ToolRackPaperEngine._floor_policy((),p,live)
    rows.append(("physical_parent_extends_floor_to_200", pol is not None and pol.arm_roi==2.0 and pol.immediate_arm_roi==2.0,
                 f"arm={getattr(pol,'arm_roi',None)} immediate={getattr(pol,'immediate_arm_roi',None)}"))

    # 3. A qualified terminal-return seed begins against the old parent by design.
    # It must receive transition custody rather than being killed and re-entered each quote.
    return_pos={"position_id":"P-RETURN","ticker":"KX-AUTH","side":Side.YES,"entry_price":.19,
        "entry_time":999.0,"close_ts":1900.0,"tool":"ONE_COMMANDER_PRIMARY",
        "territory_id":"MOUNTAIN_EDGE","opportunity_id":"RETURN","lane":Lane.MAIN,
        "custody_state":"NORMAL","position_role":"PRIMARY",
        "entry_metadata":{"position_role":"PRIMARY","commander_candidate_family":"MOUNTAIN_EDGE",
                          "commander_physical_evidence":{"entry_location":"FRESH_EXTENDED_MOUNTAIN_EXTREME"}}}
    turn=snap(t=1000,yes=.18,no=.82,metadata={
        "mission_context":{"parent":{"id":"P-DOWN","side":"NO","status":"ACTIVE","supported":True}},
        "commander_strategy":{"owned_side":"NO"},
        "mountain":{"owner_side":"NO","parent_structure":{"parent_side":"NO","parent_terminal_ready":True},
                    "terminal_evidence_qualified":True,"stall":True,"hesitation":True}})
    td=c.decide_position((),turn,return_pos)
    rows.append(("terminal_return_seed_not_killed_by_old_parent", td.action is not Action.EXIT or
                 td.intent is None or td.intent.reason!="COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT", td.reason))

    # 4. Opposite inventory is an exit-pending handoff, not strategic ownership.
    # Explicit synthetic numeric pullback/rejoin qualifies the candidate
    # before this separate inventory rule is exercised. A family label and
    # empty current geometry no longer establish positive admission.
    rejoin=OneCommander()
    for t,price in ((1000.,120.),(1010.,115.)):
        rejoin.decide_entry((),parent_snapshot(t=t,price=price,ask=.30),{})
    current=parent_snapshot(t=1020.,price=118.,ask=.30)
    intent=next(i for i in rejoin.physical_entry_candidates(current)
                if i.reason=="COMMANDER_OPPORTUNITY_MAIN_EMA9_VALUE_REJOIN")
    held={"P":{"position_id":"P","ticker":current.ticker,"side":"NO","custody_state":"NORMAL"}}
    handoff=rejoin.decide_entry((intent,),current,held)
    rows.append(("opposite_inventory_no_veto", handoff.action is Action.WAIT and
                 handoff.reason=="CURRENT_CONTRACT_OPPOSITE_INVENTORY_EXIT_PENDING_CORRECTIVE_HANDOFF", handoff.reason))

    # 5. Inherited rollover continuation gets transition custody while the old
    # parent handoff is still resolving.
    roll={"position_id":"P-ROLL","ticker":"KX-AUTH","side":Side.YES,"entry_price":.51,
        "entry_time":990.0,"close_ts":1900.0,"tool":"ONE_COMMANDER_PRIMARY",
        "territory_id":"MOUNTAIN_CONTRACT_LEG","opportunity_id":"ROLL","lane":Lane.MAIN,
        "custody_state":"NORMAL","position_role":"PRIMARY",
        "entry_reason":"COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION",
        "entry_metadata":{"position_role":"PRIMARY","commander_candidate_family":"MOUNTAIN_CONTRACT_LEG"}}
    rd=c.decide_position((),turn,roll)
    rows.append(("rollover_continuation_transition_custody", not (rd.action is Action.EXIT and rd.intent is not None
                 and rd.intent.reason=="COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT"), rd.reason))

    # 6. A Heist return occupying the primary slot is still a transition seed,
    # not stale strategic custody.
    hp={"position_id":"P-H","ticker":"KX-AUTH","side":Side.YES,"entry_price":.24,
        "entry_time":990.0,"close_ts":1900.0,"tool":"MARKET_HEIST",
        "territory_id":"H","opportunity_id":"H","lane":Lane.TACTICAL,
        "custody_state":"NORMAL","position_role":"PRIMARY",
        "entry_reason":"HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED",
        "entry_metadata":{"position_role":"PRIMARY"}}
    hd=c.decide_position((),turn,hp)
    rows.append(("heist_return_transition_custody", not (hd.action is Action.EXIT and hd.intent is not None
                 and hd.intent.reason=="COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT"), hd.reason))

    # 7. Unpromoted tactical custody is bounded and cannot drift to settlement.
    tp={"position_id":"P-T","ticker":"KX-AUTH","side":Side.NO,"entry_price":.26,
        "entry_time":700.0,"close_ts":1100.0,"tool":"MARKET_HEIST",
        "territory_id":"H","opportunity_id":"T","lane":Lane.TACTICAL,
        "custody_state":"NORMAL","position_role":"TACTICAL",
        "entry_reason":"HEIST_OUTER_EDGE_TACTICAL_RENTER",
        "entry_metadata":{"position_role":"TACTICAL"}}
    tactical=c.decide_position((),snap(t=1000,yes=.70,no=.30,metadata={"mountain":{"owner_side":"YES"}}),tp)
    rows.append(("tactical_custody_bounded", tactical.action is Action.EXIT and tactical.intent is not None
                 and tactical.intent.reason=="TACTICAL_MAX_HOLD_EXIT", tactical.reason))

    passed=sum(ok for _,ok,_ in rows)
    print(f"EMA9 AUTHORITY CONSTRUCT: {passed}/{len(rows)} PASS")
    for name,ok,detail in rows:
        print(("PASS" if ok else "FAIL"), name, detail)
    raise SystemExit(0 if passed==len(rows) else 1)

if __name__ == "__main__":
    main()
