from __future__ import annotations
import ast
from ea1_transform import apply_ea1_shadow

HELPERS = r"""
def _tp_border():
    try:return dict(getattr(core,'v94g_latest_border',{}) or {})
    except Exception:return {}

def _tp_write(ticker,side,ask,territory,ruling,reason,staff,rec):
    b=_tp_border()
    _write('tachys_territory_authority_v9_5d.csv',
      ['timestamp','run_id','session_id','event','ticker','side','ask','territory','ruling','reason','staff',
       'border_state','border_location','border_hand','border_lean','border_efficiency',
       'yard_score','battlefield','parent_direction','parent_phase','parent_health','parent_runway',
       'price_leg','relation','leg_state','target_height','timing'],
      {'event':'ENTRY_COURT','ticker':ticker,'side':side,'ask':ask,'territory':territory,'ruling':ruling,'reason':reason,'staff':staff,
       'border_state':b.get('territory_state'),'border_location':b.get('location'),'border_hand':b.get('hand_authority'),
       'border_lean':b.get('chop_lean'),'border_efficiency':b.get('trend_efficiency'),
       'yard_score':rec.get('yard_score'),'battlefield':rec.get('battlefield_class'),
       'parent_direction':rec.get('parent_arc_direction'),'parent_phase':rec.get('parent_arc_phase'),
       'parent_health':rec.get('parent_arc_health'),'parent_runway':rec.get('parent_runway_state'),
       'price_leg':rec.get('price_micro_state'),'relation':rec.get('entry_parent_relation'),
       'leg_state':rec.get('leg_state'),'target_height':rec.get('target_height'),'timing':rec.get('timing_shadow')})

def _tp_signed_target(side,height):
    h=_f(height)
    return None if h is None else h*_sign(side)

def _tp_release(side,rec,border):
    fav=_tp_signed_target(side,rec.get('target_height'))
    rel=str(rec.get('entry_parent_relation') or '')
    phase=str(rec.get('parent_arc_phase') or '')
    health=str(rec.get('parent_arc_health') or '')
    runway=str(rec.get('parent_runway_state') or '')
    leg=str(rec.get('leg_state') or '')
    eff=_f(border.get('trend_efficiency'),0.0) or 0.0
    hand=str(border.get('hand_authority') or '')
    lean=str(border.get('chop_lean') or '')
    aligned=(rel=='ALIGNED_PARENT')
    parent_release=aligned and phase=='EXPANDING' and health=='STRENGTHENING' and runway=='OPEN' and fav is not None and fav>0
    leg_release=aligned and leg=='EXPANSION' and fav is not None and fav>0
    momentum_release=aligned and eff>=0.75 and fav is not None and fav>=30.0 and (hand==side or lean==side)
    boundary_release=str(border.get('territory_state') or '')=='BOUNDARY_RELEASE' and str(border.get('release_side') or '')==side
    return parent_release or leg_release or momentum_release or boundary_release

def _tp_decide(side,ask,rec):
    rec=rec or {}; b=_tp_border()
    bstate=str(b.get('territory_state') or '')
    tight=bstate in ('CHURN_ACTIVE','CHURN_RESOLVING')
    battlefield=str(rec.get('battlefield_class') or '')
    staff_side='PARENT_GEOMETRY+MOTION_CELL+ENTRY_TIMING+TARGET_TUBE'
    staff_tight='TERRAIN_COMMAND+MASTER_OF_BORDERS+MOTION_CELL+TRANSITION_CELL+TARGET_TUBE'
    if tight:
        if _tp_release(side,rec,b):
            return True,'TIGHT_RELEASE','STRUCTURAL_RELEASE_EARNED',staff_tight
        return False,'TIGHT_TRANSITION','LOCAL_EDGE_AUTHORITY_OWNS_FIELD',staff_tight
    if battlefield=='CLEAN_TERRITORY':
        return True,'CLEAN_SLOPE','CLEAN_SLOPE_INHERITED_AUTHORITY','PARENT_GEOMETRY+MOTION_CELL+LEG_GEOMETRY'
    if _tp_release(side,rec,b):
        return True,'CLEAN_SLOPE','STRUCTURAL_RELEASE_EARNED','PARENT_GEOMETRY+MOTION_CELL+LEG_GEOMETRY'

    rel=str(rec.get('entry_parent_relation') or '')
    micro=str(rec.get('price_micro_state') or '')
    runway=str(rec.get('parent_runway_state') or '')
    health=str(rec.get('parent_arc_health') or '')
    phase=str(rec.get('parent_arc_phase') or '')
    timing=str(rec.get('timing_shadow') or '')
    leg=str(rec.get('leg_state') or '')
    arc_phase=str(rec.get('price_arc_phase') or '')
    rem=_f(rec.get('price_remaining_capacity'))
    fav=_tp_signed_target(side,rec.get('target_height'))
    price=_f(ask)

    if rel=='UNKNOWN':
        return False,'SIDEWAYS_ARC','WAIT_FOR_EMA9_PARENT',staff_side
    if rel=='OPPOSES_PARENT':
        return False,'SIDEWAYS_ARC','FOLLOW_EMA9_PARENT_OR_USE_EDGE_AUTHORITY',staff_side
    if timing=='WAIT_NEW_ARC_SHADOW' and leg!='EXPANSION':
        return False,'SIDEWAYS_ARC','WAIT_NEW_PRICE_ARC',staff_side

    # Parent-aligned pullbacks are valuable, but only after the child counter-leg
    # is mature enough to offer a resumption entry.  V1 wrongly treated any
    # COUNTER_PARENT sample as permission (#4).
    if rel=='ALIGNED_PARENT' and micro=='COUNTER_PARENT':
        mature_counter=(
            rem is not None and rem<=0.12
            and arc_phase in ('PEAK_TROUGH_BUILD','RETURN_TO_EMA9')
            and (fav is None or fav>=-30.0)
        )
        if mature_counter:
            return True,'SIDEWAYS_ARC','COUNTERSWING_MATURE_RESUMPTION_WINDOW',staff_side
        return False,'SIDEWAYS_ARC','COUNTERSWING_NOT_MATURE_YET',staff_side

    if rel=='ALIGNED_PARENT' and micro=='WITH_PARENT' and runway=='LOW':
        if leg=='EXPANSION' and fav is not None and fav>0:
            return True,'SIDEWAYS_ARC','TARGET_FAVORABLE_EXPANSION',staff_side
        if price is not None and price>=0.40:
            return False,'SIDEWAYS_ARC','EXPENSIVE_LOW_PARENT_RUNWAY_CHASE',staff_side

    return True,'SIDEWAYS_ARC','SIDEWAYS_ARC_PARENT_ALIGNED',staff_side


def _tp_profit_vault(supervisor,ticker,side,position,yes_ask,no_ask,now):
    if position.get('_v95d_profit_vault_done'):
        return False
    entry=_f(position.get('entry_ask')); bid=_bid(side,yes_ask,no_ask)
    qty=int(float(position.get('qty') or 0)); cost=_f(position.get('cost'),0.0) or 0.0
    if entry in (None,0) or bid is None or qty<2 or cost<=0:
        return False
    roi=((bid-entry)/entry)*100.0
    tid=str(position.get('trade_id') or '')
    rec=(getattr(supervisor,'winner_state',{}) or {}).get(tid) or {}
    peak=max(_f(position.get('mfe_pct'),0.0) or 0.0,_f(rec.get('last_mfe'),0.0) or 0.0,roi)
    if peak<90.0 or roi<90.0:
        return False

    shadow_rec=(getattr(execution_shadow,'trades',{}) or {}).get(tid) or {}
    entry_t=_f(shadow_rec.get('entry_ts'))
    if entry_t is None:
        entry_t=_f(position.get('entry_time'),now) or now
    age=max(0.0,now-entry_t)
    max_gross=((1.0/entry)-1.0)*100.0
    candidate_type=None
    if max_gross>=100.0 and peak>=50.0:
        if age<=60.0:
            candidate_type='FLASH'
        elif age<=180.0 and peak/max(age,1.0)>=0.20:
            candidate_type='SUSTAINED'

    fraction=0.25 if candidate_type else 0.60
    sell_qty=max(1,int(round(qty*fraction)))
    sell_qty=min(sell_qty,qty-1)
    if sell_qty<=0:
        return False
    cost_basis=cost*(sell_qty/qty)
    gross=sell_qty*bid-cost_basis
    fee_est=exshadow.estimated_taker_fee(sell_qty,bid)
    net_est=gross-fee_est
    l2={}
    try:l2=execution_shadow._walk(side,'SELL',sell_qty,yes_ask,no_ask)
    except Exception:l2={}

    core.paper_realized_pnl+=gross
    partial=dict(position)
    partial['qty']=sell_qty
    partial['cost']=cost_basis
    try:core.log_paper_event('PARTIAL_EXIT',partial,bid,'V95D_PROFIT_VAULT')
    except Exception:pass
    position['qty']=qty-sell_qty
    position['cost']=cost-cost_basis
    position['_v95d_profit_vault_done']=True
    position['_v95d_profit_vault_qty']=sell_qty
    position['_v95d_profit_vault_bid']=bid
    position['_v95d_profit_vault_gross_pnl']=gross
    position['_v95d_profit_vault_candidate_type']=candidate_type or 'ORDINARY_HIGH_WINNER'
    try:
        if tid in execution_shadow.trades:
            execution_shadow.trades[tid]['qty']=int(position['qty'])
    except Exception:
        pass

    _write('tachys_profit_vault_v9_5d.csv',
      ['timestamp','run_id','session_id','event','trade_id','ticker','side','entry_ask','vault_bid','peak_pct',
       'current_roi_pct','position_age_sec','candidate_type','original_qty','sold_qty','runner_qty','vault_fraction',
       'cost_basis_sold','gross_pnl','estimated_exit_fee','estimated_net_pnl','l2_filled_qty','l2_vwap','l2_fill_ratio','reason'],
      {'event':'PROFIT_VAULT','trade_id':position.get('trade_id'),'ticker':ticker,'side':side,'entry_ask':entry,
       'vault_bid':bid,'peak_pct':peak,'current_roi_pct':roi,'position_age_sec':age,
       'candidate_type':candidate_type or 'ORDINARY_HIGH_WINNER','original_qty':qty,'sold_qty':sell_qty,
       'runner_qty':position['qty'],'vault_fraction':fraction,'cost_basis_sold':cost_basis,'gross_pnl':gross,
       'estimated_exit_fee':fee_est,'estimated_net_pnl':net_est,'l2_filled_qty':l2.get('filled_qty'),
       'l2_vwap':l2.get('vwap'),'l2_fill_ratio':l2.get('fill_ratio'),
       'reason':'LEVIATHAN_CANDIDATE_LIGHT_VAULT' if candidate_type else 'ORDINARY_HIGH_WINNER_BANK_60'})
    label=candidate_type or 'ORDINARY'
    print(f'🏦 PROFIT VAULT | #{tid} {side} | ROI={roi:.1f}% peak={peak:.1f}% | sold {sell_qty}/{qty} @ {bid:.3f} | runner={position["qty"]} | {label}')
    return True

def _tp_parent_strong_against(side,now):
    p=_ea1_parent_context(now)
    against=(p.get('direction')=='UP' and side=='NO') or (p.get('direction')=='DOWN' and side=='YES')
    return bool(against and p.get('health')=='STRENGTHENING' and p.get('phase') in ('BUILDING','EXPANDING'))

def _tp_edge_try(ticker,yes_ask,no_ask,close_ts=None):
    now=time.time(); border=_tp_border()
    if str(border.get('territory_state') or '') not in ('CHURN_ACTIVE','CHURN_RESOLVING'):
        return False
    ctx=c.brain.last_context if (c.brain.last_context or {}).get('ticker')==ticker else {}
    if not ctx:return True
    metrics=dict(ctx.get('metrics') or {}); target=dict(ctx.get('target') or {})
    height=_f(target.get('height')); r60=max(1.0,_f(metrics.get('r60'),1.0) or 1.0)
    loc=str(border.get('location') or '')
    hand=str(border.get('hand_authority') or '')
    lean=str(border.get('chop_lean') or '')
    asks={'YES':_f(yes_ask),'NO':_f(no_ask)}
    vals_by_side={}
    for s in ('YES','NO'):
        vals=[(_f(metrics.get('ch'+str(n)),0.0) or 0.0)*_sign(s) for n in (3,6,9)]
        vals_by_side[s]=(vals,sum(v>=1.5 for v in vals))
    candidate=None; intent=None; why=None

    # Prodigal return: lower wall -> YES home, upper wall -> NO home.
    edge_side='YES' if loc in ('LOWER_EDGE','LOWER_THIRD') else 'NO' if loc in ('UPPER_EDGE','UPPER_THIRD') else None
    if edge_side:
        ask=asks.get(edge_side); fav=_tp_signed_target(edge_side,height)
        vals,confirms=vals_by_side[edge_side]
        cap=0.60 if loc in ('LOWER_EDGE','UPPER_EDGE') else 0.55
        support=(hand==edge_side) or (lean==edge_side)
        third_support=(loc in ('LOWER_EDGE','UPPER_EDGE')) or (hand==edge_side and (lean==edge_side or confirms>=2))
        target_ok=(fav is not None and fav>=-30.0)
        strong_against=_tp_parent_strong_against(edge_side,now)
        strong_override=bool(strong_against and fav is not None and fav>=0.0 and hand==edge_side and confirms>=2)
        if ask is not None and 0<ask<=cap and support and third_support and target_ok and (not strong_against or strong_override):
            candidate=edge_side; intent='EDGE_RETURN'; why=f'{loc}_RETURN_HAND_{hand}_LEAN_{lean}_STRONG_OVERRIDE_{int(strong_override)}'

    # Cheap target repricing lane: permits the sub-.25 convex opportunity even
    # when the box location is not a textbook return wall (#15 type).
    if candidate is None and height is not None and abs(height)<=max(75.0,1.75*r60):
        cheap=[s for s in ('YES','NO') if asks.get(s) is not None and 0<asks[s]<=0.25]
        for s in cheap:
            vals,confirms=vals_by_side[s]
            support=(hand==s) or (lean==s and confirms>=2)
            if support and not _tp_parent_strong_against(s,now):
                candidate=s; intent='CHEAP_TARGET_RETURN'; why=f'CHEAP_TARGET_{loc}_HAND_{hand}_LEAN_{lean}'
                break

    if candidate is None:return True
    ask=asks[candidate]
    # No duplicate same-side position, but an opposite position may coexist:
    # this is the local counter-leg authority the old Campaign monopoly blocked.
    same=(getattr(core,'paper_positions',{}) or {}).get(candidate)
    if isinstance(same,dict) and str(same.get('ticker') or '')==str(ticker):return True

    sig={'price':ask,'setup_grade':'CONFIRMED','signal_grade':'A+',
         'strategy':'V95D_TERRITORY_EDGE','market_regime':'TIGHT_TRANSITION','trade_intent':intent,
         'seconds_to_close':_f(ctx.get('seconds_left')),'target_distance':height,
         'btc_change_60s':_f(metrics.get('ch60')),'btc_trend_efficiency_60s':_f(metrics.get('eff60')),
         'early_exception':False,'early_trade':False,'territory_edge_reason':why}
    entered=bool(core.paper_enter(ticker,candidate,ask,sig))
    if entered: print(f'🏠 PRODIGAL RETURN | {candidate} @ {ask:.3f} | {loc} | target={height:+.1f} | {why}')
    return True
"""

def apply_territory_paper(source:str)->str:
    source=apply_ea1_shadow(source)
    if 'def _tp_border()' in source:return source
    anchor='\n\nclass ChurnController:\n'
    if anchor not in source:raise RuntimeError('territory helper anchor missing')
    source=source.replace(anchor,HELPERS+anchor,1)

    # PAPER-04: Campaign is strategic memory/context, not tactical sovereignty.
    # Remove the old CAMPAIGN_*_STICKY hard veto before the entry wrapper is built.
    sticky_old="""        # Normal tactical entries must follow the campaign.
        if self.campaign_side in ("YES", "NO") and side != self.campaign_side:
            # A fresh high-conviction prearm gets controlled leap-of-faith authority.
            if is_prearm:
                ctx = c.brain.last_context or {}
                metrics = dict(ctx.get("metrics") or {})
                align = self._alignment_369(side, metrics)
                score_lead = int(c.brain.last_scores.get(side, 0)) - int(c.brain.last_scores.get(_opposite(side), 0))
                if align >= 2 and score_lead >= 0:
                    return True, "FRESH_PREARM_OVERRIDE", True
            return False, f"CAMPAIGN_{self.campaign_side}_STICKY", False

        return True, f"CAMPAIGN_{self.campaign_side}_ALIGNED", is_prearm
"""
    sticky_new="""        # Campaign remains strategic context only. Local tactical authority is
        # decided downstream by Territory + EMA9 Parent Leg + Price Leg + Target.
        if self.campaign_side in ("YES", "NO") and side != self.campaign_side:
            if is_prearm:
                ctx = c.brain.last_context or {}
                metrics = dict(ctx.get("metrics") or {})
                align = self._alignment_369(side, metrics)
                score_lead = int(c.brain.last_scores.get(side, 0)) - int(c.brain.last_scores.get(_opposite(side), 0))
                if align >= 2 and score_lead >= 0:
                    return True, "FRESH_PREARM_OVERRIDE", True
            return True, f"CAMPAIGN_{self.campaign_side}_CONTEXT_ONLY", is_prearm

        return True, f"CAMPAIGN_{self.campaign_side}_ALIGNED", is_prearm
"""
    if sticky_old not in source:raise RuntimeError('campaign sticky block anchor missing')
    source=source.replace(sticky_old,sticky_new,1)

    # Local edge authority is deliberately narrower than a global opposite
    # Campaign bypass. The campaign itself no longer vetoes opposite tactical
    # legs; all candidates still pass through the local Territory/Price-Leg court.
    old_gate="""        try:
            allowed, reason, prearm_override = supervisor.entry_allowed(ticker, side, signal, now)
        except Exception as exc:
            print(f"⚠️ V9.5D entry court error; blocking experimental entry: {exc}")
            return False

        if not allowed:
            print(f"🧱 V9.5D ENTRY BLOCK | {side} @ {float(ask):.3f} | {reason}")
            return False
"""
    new_gate="""        territory_edge = (
            str(signal.get("strategy") or "") == "V95D_TERRITORY_EDGE"
            and str(signal.get("trade_intent") or "") in ("EDGE_RETURN","CHEAP_TARGET_RETURN")
        )
        if territory_edge:
            allowed, reason, prearm_override = True, "TERRITORY_LOCAL_EDGE_AUTHORITY", False
        else:
            try:
                allowed, reason, prearm_override = supervisor.entry_allowed(ticker, side, signal, now)
            except Exception as exc:
                print(f"⚠️ V9.5D entry court error; blocking experimental entry: {exc}")
                return False

        if not allowed:
            print(f"🧱 V9.5D ENTRY BLOCK | {side} @ {float(ask):.3f} | {reason}")
            return False
"""
    if old_gate not in source:raise RuntimeError('campaign gate anchor missing')
    source=source.replace(old_gate,new_gate,1)

    old_eval="""        ea1_shadow = _ea1_eval_entry(ticker, side, ask, signal, now, ctx)

        # A new main entry can wait while a smaller opposing tactical sleeve
"""
    new_eval="""        ea1_shadow = _ea1_eval_entry(ticker, side, ask, signal, now, ctx)
        if territory_edge:
            tp_ok,tp_territory,tp_reason,tp_staff=True,'TIGHT_TRANSITION','QUALIFIED_LOCAL_EDGE_ENTRY','TERRAIN_COMMAND+MASTER_OF_BORDERS+MOTION_CELL+TARGET_TUBE'
        else:
            tp_ok,tp_territory,tp_reason,tp_staff=_tp_decide(side,ask,ea1_shadow)
        _tp_write(ticker,side,ask,tp_territory,'ALLOW' if tp_ok else 'WAIT',tp_reason,tp_staff,ea1_shadow or {})
        if not tp_ok:
            _ea1_result(ea1_shadow,False,ticker,side,ask)
            return False

        # A new main entry can wait while a smaller opposing tactical sleeve
"""
    if old_eval not in source:raise RuntimeError('territory entry anchor missing')
    source=source.replace(old_eval,new_eval,1)

    old_parallel="""        parallel = (
            isinstance(opp_pos, dict)
            and str(opp_pos.get("ticker") or "") == str(ticker)
            and (supervisor.campaign_side == side or prearm_override)
        )
"""
    new_parallel="""        parallel = (
            isinstance(opp_pos, dict)
            and str(opp_pos.get("ticker") or "") == str(ticker)
            and (tp_ok or prearm_override or territory_edge)
        )
"""
    if old_parallel not in source:raise RuntimeError('parallel transition anchor missing')
    source=source.replace(old_parallel,new_parallel,1)

    old_hook="""    core.paper_enter = paper_enter_wrapper

    # 5) Exit Court wraps the already-installed V9.5C manager.
"""
    new_hook="""    core.paper_enter = paper_enter_wrapper
    core.chop_sniper_try_enter = _tp_edge_try

    # 5) Exit Court wraps the already-installed V9.5C manager.
"""
    if old_hook not in source:raise RuntimeError('territory edge hook anchor missing')
    source=source.replace(old_hook,new_hook,1)
    manage_anchor="""        # Ordinary inherited exits become proposals. Hard emergency exits remain live.
"""
    manage_new="""        # Winner Expansion Profit Vault: bank part of a high-ROI winner once,
        # then leave the remaining contracts under the existing structural runner/exit court.
        for vault_side, vault_pos in positions:
            if (getattr(core, "paper_positions", {}) or {}).get(vault_side) is vault_pos:
                try:
                    _tp_profit_vault(supervisor,ticker,vault_side,vault_pos,yes_ask,no_ask,now)
                except Exception as exc:
                    print(f"⚠️ PROFIT VAULT error for {vault_side}: {exc}")

        # Ordinary inherited exits become proposals. Hard emergency exits remain live.
"""
    if manage_anchor not in source:raise RuntimeError('profit vault manage anchor missing')
    source=source.replace(manage_anchor,manage_new,1)

    # PAPER-ONLY DATA HOLD: keep frozen HF2 runtime source untouched, but replace
    # only its 30-second "kill the whole experiment" watchdog in memory.
    # Entries and price-dependent exits remain paused until quotes recover.
    data_hold_anchor="""    install_v95d_hooks()
    import tachys_666_runtime_hf2 as hf2
    hf2.install(core, execution_shadow, supervisor, side_policy={k: globals()[k] for k in hf2.SIDE_POLICY_KEYS})
"""
    data_hold_new="""    install_v95d_hooks()
    import tachys_666_runtime_hf2 as hf2

    def _tp_data_hold_watchdog(self, q, mono):
        live = {}
        prior = dict(getattr(self, "bad_positions", {}) or {})
        max_age = 0.0
        for side, p in self.core.paper_positions.items():
            if not isinstance(p, dict):
                continue
            key = (str(p.get("ticker")), str(p.get("trade_id")), str(side))
            available = (q is not None and q.ticker == p.get("ticker") and q.can_sell(side))
            if available:
                continue
            self.side_manager.pause(p)
            since = self.bad_positions.get(key)
            if since is None:
                since = self.bad_since if not self.bad_positions and self.bad_since is not None else mono
            live[key] = since
            max_age = max(max_age, max(0.0, mono - since))

        self.bad_positions = live
        self.bad_since = min(live.values()) if live else None

        if live and max_age >= hf2.DATA_HALT_SECONDS:
            last = float(getattr(self, "_tp_data_hold_warn_mono", -1e30) or -1e30)
            if mono - last >= 15.0:
                self._tp_data_hold_warn_mono = mono
                print(f"HF2 DATA HOLD | OPEN POSITIONS UNRESOLVED | age={max_age:.1f}s | entries/exits requiring price remain PAUSED")
        elif prior and not live:
            print("HF2 DATA HOLD | RECOVERED | usable held-side quote restored; normal quote authority resumes")

    hf2.Runtime.watchdog_step = _tp_data_hold_watchdog
    hf2.install(core, execution_shadow, supervisor, side_policy={k: globals()[k] for k in hf2.SIDE_POLICY_KEYS})
"""
    if data_hold_anchor not in source:raise RuntimeError('data hold runtime hook anchor missing')
    source=source.replace(data_hold_anchor,data_hold_new,1)

    ast.parse(source);return source
