"""Qualified Lazarus review, with no execution or independent Commander.

This module observes the existing lot; it never creates an entry or changes a
basis, quantity, floor, opportunity, or contract. Decisions and durable custody
transitions are approved by OneCommander. Missing evidence is not sanctuary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from strategy_core.tools.management import (
    as_side, entry_metadata, mapping, number, physical_management_evidence,
)
from strategy_core.types import Action, MarketSnapshot, Side, ToolIntent
from strategy_core.source_freshness import source_receipt_is_fresh


CUSTODY_STATES = frozenset(("NORMAL", "LAZARUS", "RECOVERED_NORMAL", "PROMOTED_MAIN", "EXIT_PENDING"))


def recent_swing_evidence(rows: Sequence[Mapping[str, Any]], *, now_ts: float) -> dict[str, Any]:
    """Observed 20-minute swing capacity, separate from two-hour context.

    Retains the R15 1200-second/two-transition review defaults. Actual covered
    price/EMA9 spans must be meaningful; a label on a tiny fragment or an old
    completed arc outside this lookback cannot manufacture recovery terrain.
    This is a review input, never a prediction that the held lot will recover.
    """
    recent = [row for row in rows if (number(row.get("epoch_ms")) is not None
              and (now_ts - 1200.0) * 1000 <= float(row["epoch_ms"]) <= now_ts * 1000)]
    groups: list[list[Mapping[str, Any]]] = []
    for row in recent:
        if not row.get("arc_id") or row.get("arc_direction") not in ("UP", "DOWN"):
            continue
        if not groups or groups[-1][-1].get("arc_id") != row.get("arc_id"):
            groups.append([])
        groups[-1].append(row)
    scale = max(1.0, number(recent[-1].get("range60")) or 1.0) if recent else 1.0
    completed = []
    for group in groups[:-1]:
        times = [float(row["epoch_ms"]) / 1000. for row in group]
        prices = [x for x in (number(row.get("btc_price")) for row in group) if x is not None]
        emas = [x for x in (number(row.get("ema9")) for row in group) if x is not None]
        covered = bool(len(group) >= 2 and times[-1] - times[0] >= 30.
                       and all(0 < b-a <= 3. for a, b in zip(times, times[1:])))
        price_span = max(prices) - min(prices) if prices else 0.
        ema_span = max(emas) - min(emas) if emas else 0.
        if covered and (ema_span >= max(2., .12*scale) or price_span >= max(5., .45*scale)):
            completed.append({"arc_id": group[-1]["arc_id"], "direction": group[-1]["arc_direction"],
                "end_ts": times[-1], "observed_span_seconds": times[-1]-times[0],
                "btc_span": price_span, "ema9_span": ema_span})
    completed = completed[-6:]
    directions = [row["direction"] for row in completed]
    current = groups[-1][-1]["arc_direction"] if groups else None
    if current is not None and (not directions or directions[-1] != current):
        directions.append(current)
    transitions = sum(a != b for a, b in zip(directions, directions[1:]))
    return {"active": transitions >= 2, "lookback_seconds": 1200., "observed_ts": now_ts,
            "transitions": transitions, "completed_walls": completed,
            "reason": "RECENT_COVERED_SWING_CAPACITY" if transitions >= 2 else
                      "RECENT_SWING_CAPACITY_NOT_PROVED"}


def value(position: Any, key: str, default: Any = None) -> Any:
    return position.get(key, default) if isinstance(position, Mapping) else getattr(position, key, default)


def independent_entry_denial(intent: ToolIntent, held: Sequence[Any], *, now_ts: float,
                             continuity_generation: int | None = None) -> str | None:
    """Bounded coexistence proof checked at Commander and again at execution.

    The rack proves a real renewed physical mission. This boundary verifies its
    exact lot/mission/time identities; a route, quote, or custody change is not
    that proof. A recovered old lot and its already booked companion may both
    remain open, but a third entry is never admitted by this exception.
    """
    if not held:
        return None
    if len(held) != 1:
        return "RECOVERY_COHORT_CAPACITY_ONE_WOUND_ONE_NEW_MISSION"
    if any(value(p, "custody_state", "NORMAL") != "LAZARUS" or value(p, "exit_required", False)
           for p in held):
        return "CURRENT_CONTRACT_INVENTORY_OWNS_CUSTODY"
    proof = mapping(intent.metadata.get("independent_recovery_mission"))
    mission = str(proof.get("mission_id") or "")
    observed = number(proof.get("observed_ts"))
    if (proof.get("independently_renewed") is not True or not mission
            or str(intent.metadata.get("physical_mission_id") or "") != mission
            or observed is None or not 0 <= now_ts - observed <= 3.0
            or ("source_receipt" in proof or "source_ms" in proof) and not source_receipt_is_fresh(
                proof.get("source_receipt"), now_ts=now_ts, source_ms=proof.get("source_ms"),
                max_age_seconds=3., continuity_generation=proof.get("continuity_generation"))
            or type(proof.get("continuity_generation")) is not int
            or proof["continuity_generation"] < 0):
        return "INDEPENDENT_RENEWED_PHYSICAL_MISSION_REQUIRED"
    if continuity_generation is not None and proof["continuity_generation"] != continuity_generation:
        return "RECOVERY_MISSION_CONTINUITY_PROOF_MISMATCH"
    identifiers = proof.get("detached_position_ids")
    if (not isinstance(identifiers, (list, tuple))
            or set(str(pid) for pid in identifiers) != {str(value(p, "position_id")) for p in held}
            or len(identifiers) != len(held)):
        return "RECOVERY_MISSION_EXACT_DETACHED_LOTS_REQUIRED"
    for p in held:
        old = mapping(value(p, "entry_metadata", {}))
        original_mission = str(old.get("physical_mission_id") or old.get("entry_arc_id") or "")
        if (not original_mission or original_mission == mission
                or value(p, "opportunity_id") == intent.opportunity_id):
            return "DETACHMENT_DOES_NOT_REARM_ORIGINAL_PHYSICAL_MISSION"
    return None


@dataclass
class _Observation:
    opening_bid: float | None = None
    entry_btc: float | None = None
    entry_ema9: float | None = None
    last_quote_time: float | None = None
    last_quote_id: str | None = None
    continuity_generation: int | None = None
    underwater_since: float | None = None
    underwater_low: float | None = None
    reclaim_high: float | None = None
    reclaim_attempt: bool = False
    failed_reclaim: bool = False


class RecoveryTracker:
    """Causal, per-lot continuous-underwater and failed-reclaim observation.

    Stale/missing/partial marks and physical continuity resets break the
    continuous-underwater timer. Every review is in the decision audit; only
    Commander-approved state transitions cause a durable ledger commit.
    """
    def __init__(self) -> None:
        self._observations: dict[str, _Observation] = {}

    def forget(self, position_id: str) -> None:
        self._observations.pop(str(position_id), None)

    def review(self, position: Mapping[str, Any], snapshot: MarketSnapshot,
               intents: Sequence[ToolIntent], mark: Any | None, *,
               detached_slot_available: bool = True) -> dict[str, Any]:
        pid = str(position["position_id"])
        evidence = physical_management_evidence(position, snapshot)
        entry = entry_metadata(position)
        initial = mapping(entry.get("entry_geometry"))
        observed = self._observations.setdefault(pid, _Observation(
            opening_bid=number(entry.get("opening_executable_bid")),
            entry_btc=number(initial.get("btc_price")), entry_ema9=number(initial.get("ema9"))))
        if observed.entry_btc is None:
            observed.entry_btc = evidence["btc"]
        if observed.entry_ema9 is None:
            observed.entry_ema9 = evidence["ema9"]
        bid = number(getattr(mark, "bid", None))
        quoted_at = number(snapshot.metadata.get("quote_observed_ts"))
        quote_id = str(snapshot.metadata.get("quote_id") or "")
        full = getattr(mark, "full_quantity_visible", False) is True
        continuous = bool(full and bid is not None and snapshot.quote_current
            and evidence["physical_current"] and quoted_at is not None
            and 0 <= snapshot.now_ts - quoted_at <= 3.0)
        generation = int(snapshot.metadata.get("geometry_continuity_generation", 0))
        if (not continuous or observed.continuity_generation not in (None, generation)
                or observed.last_quote_time is not None and quoted_at is not None
                and not 0 <= quoted_at - observed.last_quote_time <= 3.0):
            observed.underwater_since = None
            observed.underwater_low = None
            observed.reclaim_high = None
            observed.reclaim_attempt = observed.failed_reclaim = False
        observed.continuity_generation = generation
        basis = number(position.get("entry_price")) or 0.0
        losing = bool(continuous and bid is not None and bid < basis)
        if continuous:
            if observed.opening_bid is None:
                observed.opening_bid = bid
            if quote_id != observed.last_quote_id:
                if losing:
                    if observed.underwater_since is None:
                        observed.underwater_since = max(quoted_at, float(position["entry_time"]))
                    low = observed.underwater_low
                    if low is not None and bid >= low + .01:
                        observed.reclaim_attempt = True
                        observed.reclaim_high = max(observed.reclaim_high or bid, bid)
                    if (observed.reclaim_attempt and observed.reclaim_high is not None
                            and bid <= observed.reclaim_high - .01):
                        observed.failed_reclaim = True
                    observed.underwater_low = bid if low is None else min(low, bid)
                else:
                    observed.underwater_since = None
                    observed.underwater_low = None
                    observed.reclaim_high = None
                    observed.reclaim_attempt = observed.failed_reclaim = False
                observed.last_quote_id = quote_id
                observed.last_quote_time = quoted_at
        age = max(0.0, snapshot.now_ts - float(position["entry_time"]))
        underwater = (max(0.0, quoted_at - observed.underwater_since)
                      if continuous and losing and observed.underwater_since is not None else 0.0)
        sign = 1 if as_side(position.get("side")) is Side.YES else -1
        btc_adverse = ((observed.entry_btc - evidence["btc"]) * sign
                       if observed.entry_btc is not None and evidence["btc"] is not None else None)
        ema_adverse = ((observed.entry_ema9 - evidence["ema9"]) * sign
                       if observed.entry_ema9 is not None and evidence["ema9"] is not None else None)
        decline = observed.opening_bid - bid if observed.opening_bid is not None and bid is not None else None
        developed = bool(losing and (
            decline is not None and decline >= .02 - 1e-9
            or btc_adverse is not None and btc_adverse >= max(3.0, .12 * evidence["range60"])
            or ema_adverse is not None and ema_adverse >= max(.5, .03 * evidence["range60"])))
        failure = next((mapping(intent.metadata.get("mountain_failure_evidence"))
                        for intent in intents if intent.metadata.get("mountain_failure_evidence")), {})
        failed_reclaim = observed.failed_reclaim or failure.get("qualified_persistent_failure") is True
        proposed_exit = any(intent.action is Action.EXIT for intent in intents)
        # A freshly confirmed genuine opposing handoff is not an ordinary
        # aged failed attempt. Custody may not hide the accepted structural exit.
        verified_handoff_exit = any(intent.action is Action.EXIT and
            "CONFIRMED_OPPOSING" in intent.reason for intent in intents)
        hard = bool(evidence["hard_adverse_release"] or evidence["terminal_impossibility"]
                    or verified_handoff_exit)
        state = str(position.get("custody_state") or "NORMAL")
        seconds_left = max(0.0, float(position["close_ts"]) - snapshot.now_ts)
        mature = age >= 60.0 and underwater >= 45.0
        qualified = bool(mature and developed and failed_reclaim
                         and evidence["credible_recovery_terrain"] and not hard
                         and position.get("floor_bid") is None and not position.get("exit_required"))
        next_state, action, reason = state, "NORMAL", "NORMAL_TOOL_CUSTODY_REVIEWED"
        if state == "LAZARUS":
            if hard:
                next_state, action, reason = "EXIT_PENDING", "EXIT", "LAZARUS_HARD_ADVERSE_STRUCTURE"
            elif continuous and bid is not None and bid >= basis and evidence["held_side_supported"]:
                next_state, action, reason = "RECOVERED_NORMAL", "HOLD", "LAZARUS_RECOVERED_WITH_CURRENT_HELD_SUPPORT"
            elif evidence["recovery_terrain_physically_replaced"]:
                next_state, action, reason = "EXIT_PENDING", "EXIT", "LAZARUS_RECOVERY_TERRAIN_PHYSICALLY_REPLACED"
            else:
                action = "HOLD"
                reason = ("LAZARUS_QUOTE_RECOVERY_AWAITS_PHYSICAL_SUPPORT"
                          if continuous and bid is not None and bid >= basis else
                          "LAZARUS_QUALIFIED_RECOVERY_CUSTODY" if evidence["credible_recovery_terrain"] else
                          "LAZARUS_REVIEW_AWAITS_AFFIRMATIVE_PHYSICAL_REPLACEMENT")
        elif state != "EXIT_PENDING" and qualified and (proposed_exit or seconds_left <= 450.0):
            if detached_slot_available:
                next_state, action, reason = "LAZARUS", "HOLD", "LAZARUS_MATURE_WOUND_WITH_CREDIBLE_RECLAIM_TERRAIN"
            else:
                reason = "LAZARUS_CUSTODY_SLOT_ALREADY_OCCUPIED_NORMAL_MANAGEMENT"
        return {
            "position_id": pid, "previous_state": state, "next_state": next_state,
            "action": action, "reason": reason, "reviewed_at": snapshot.now_ts,
            "age_seconds": age, "continuous_underwater_seconds": underwater,
            "opening_executable_bid": observed.opening_bid, "current_executable_bid": bid,
            "full_lot_current": continuous, "developed_loss": developed,
            "post_entry_bid_decline": decline, "post_entry_btc_adverse": btc_adverse,
            "post_entry_ema9_adverse": ema_adverse, "failed_ordinary_reclaim": failed_reclaim,
            "maturity_qualified": mature, "lazarus_qualified": qualified,
            "second_half": seconds_left <= 450.0, "seconds_left": seconds_left,
            "hard_exit": hard, "confirmed_opposing_handoff_exit": verified_handoff_exit,
            "physical": evidence,
        }
