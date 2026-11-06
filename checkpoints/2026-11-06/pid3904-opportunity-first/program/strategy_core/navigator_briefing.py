"""Read-only King's Navigator terrain continuity briefing.

No strategy, candidate, veto, execution, or order authority. Summarizes the
current *observed* historical EMA9 gap and contract TP context for the one
Commander and the Nautilus Briefing panel. A different local territory label
cannot erase an intact multi-contract parent; a historical parent alone is
never a paid entry.
"""
from __future__ import annotations
from typing import Any, Mapping
from strategy_core.directional_parent import directional_parent_evidence
from strategy_core.types import MarketSnapshot


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def navigator_terrain_briefing(snapshot: MarketSnapshot) -> dict[str, Any] | None:
    """Positive, non-executable PREPARE/FISH advice; no negative briefings.

    Historical NO/YES ownership can justify *looking* for same-side value, but
    until contract TP and EMA junction agree, brief PREPARE rather than FISH.
    This distinction is frozen by PID17744 21:30:16 and 21:30:50 controls.
    """
    parent = directional_parent_evidence(snapshot)
    if parent.get('qualified') is not True or parent.get('side') not in ('YES','NO'):
        return None
    tp = _map(snapshot.metadata.get('tp_geometry'))
    tp_side = str(tp.get('contract_ownership_side') or '').upper()
    tp_status = str(tp.get('contract_ownership') or '').upper()
    unresolved = bool(tp.get('target_between_ema9_ema30') is True
        or tp_side != parent['side']
        or tp_status not in ('BOUNCE_FAVORED','STARTING_LEG_FAVORED'))
    state = 'PREPARE' if unresolved else 'FISH'
    reason = ('LONG_PARENT_'+parent['side']+'_TP_OR_JUNCTION_UNRESOLVED'
              if unresolved else 'LONG_PARENT_'+parent['side']+'_FISH_SAME_SIDE_VALUE')
    return {
        'tool':'NAVIGATOR', 'territory_id':'HISTORICAL_EMA9_PARENT',
        'state':state, 'side':parent['side'],
        'max_price':None, 'size_tier':None,
        'reason':reason,
        'opportunity_id':f"NAVIGATOR:{snapshot.ticker}:{parent['side']}",
        'source_time':snapshot.now_ts,
        'evidence':{'long_parent':dict(parent),
                    'tp_ownership_side':tp_side,
                    'tp_ownership_status':tp_status,
                    'tp_ema_junction':bool(tp.get('target_between_ema9_ema30')),
                    'independent_entry_authority':False},
        'execution_authority':False, 'can_veto':False, 'can_order':False,
    }
