"""Historical EMA9 directional ownership, advisory and causal only.

Use a continuous observed EMA9/EMA30 gap as multi-contract context.
A child's temporary reversal does not retire the larger parent, but a
collapsed gap or affirmative opposite transfer does. Age is evidence of
observed continuity, never an expiry clock or an independent trade trigger.
"""
from __future__ import annotations
import math
from typing import Any, Mapping
from strategy_core.types import MarketSnapshot


def _map(value: Any) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def directional_parent_evidence(snapshot: MarketSnapshot) -> dict[str, Any]:
    """Return a demonstrated with-wind parent, not trading permission.

    Requires existing causal source continuity + a meaningful separated gap,
    not merely two aligned candles or EMA30 direction.  The observed
    15:15-16:45 YES gap and later 17:10 NO gap pass.  A gap collapsing at
    the 16:45-16:50 transfer does not fossilize prior YES ownership.
    """
    md = snapshot.metadata
    cross = _map(md.get('ema9_ema30_cross_context'))
    gap = _map(cross.get('gap_lifecycle'))
    geo = _map(md.get('current_geometry'))
    mountain = _map(md.get('mountain'))
    parent = _map(mountain.get('parent_structure'))
    side = str(gap.get('current_side') or '').upper()
    age = _number(gap.get('age_seconds_since_observed_cross'))
    observed_s = _number(gap.get('observed_side_residence_seconds'))
    observed_start = _number(gap.get('observed_side_residence_start_source_ms'))
    observed_count = _number(gap.get('observed_side_residence_samples')) or 0.
    observed_continuous = gap.get('observed_side_residence_continuous') is True
    observed_qualified = bool(observed_continuous and observed_start is not None
        and observed_count >= 2 and observed_s is not None and observed_s >= 900.)
    stage = str(gap.get('stage') or '').upper()
    abs_gap = _number(gap.get('current_abs_gap_btc'))
    if abs_gap is None:
        abs_gap = abs(_number(geo.get('ema_gap')) or 0.)
    range180 = _number(geo.get('range180')) or 1.
    minimum_gap = max(8., 0.15 * range180)
    terminal = parent.get('parent_terminal_ready') is True
    opposite_release = bool(md.get('release_confirmed_current') is True
        and str(md.get('release_candidate_side') or '').upper() in {'YES','NO'}
        and str(md.get('release_candidate_side')).upper() != side)
    qualified = bool(md.get('physical_current') is True
        and side in {'YES','NO'}
        and (age is not None and age >= 900. or observed_qualified)
        and stage in {'MATURE','ROLLING','INHERITED_OR_UNOBSERVED_CROSS'}
        # No observed cross is not proof that an inherited gap is broken.
        # Only an actually observed cross can make its continuity relevant.
        and (gap.get('observed_cross_on_current_segment') is not True
             or gap.get('continued_on_cross_side') is not False)
        and gap.get('touching_spine') is not True
        and abs_gap >= minimum_gap
        and not opposite_release)
    return {
        'version':'PID15740_OBSERVED_RESIDENCE_PARENT_V2',
        'qualified':qualified,
        'side':side if qualified else None,
        'gap_side':side if side in {'YES','NO'} else None,
        'gap_age_s':age,
        'observed_residence_age_s':observed_s,
        'observed_residence_start_source_ms':observed_start,
        'qualification_age_s':age if age is not None else observed_s,
        'gap_stage':stage,
        'gap_btc':round(abs_gap,4),
        'gap_minimum_btc':round(minimum_gap,4),
        'historical_contracts_observed':round((age if age is not None else observed_s or 0.)/900.,2),
        'terminal_watch':terminal,
        'opposite_release':opposite_release,
        'source_ms':_number(geo.get('epoch_ms')),
        'can_veto':False,
        'creates_entry':False,
        'basis': ('CONTINUOUS_MULTI_CONTRACT_EMA9_GAP' if qualified and age is not None else
                  'OBSERVED_INHERITED_SAME_SIDE_RESIDENCE' if qualified else
                  'NOT_ESTABLISHED_OR_GAP_COLLAPSING'),
    }
