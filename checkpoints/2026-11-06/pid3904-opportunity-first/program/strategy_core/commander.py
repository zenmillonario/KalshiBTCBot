from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Any, Mapping

from strategy_core.types import Action, Lane, MarketSnapshot, Side, ToolIntent
from strategy_core.recovery import independent_entry_denial
from strategy_core.position_roles import normal_role_entry_denial, field
from strategy_core.tools.management import (ordinary_profit_hold_reason, strategy_exit_hold_reason,
    TACTICAL_COLLECTION_POLICY, mission_collection_evidence)
from strategy_core.commander_candidates import (MOUNTAIN_ONLY_MODE, physical_entry_candidates,
    current_mountain_terminal, quote_wave_scalp_candidates, historical_extreme_release_candidates,
    edge_heist_candidates, ema9_continuation_precedent, positive_candidate_matches_continuation,
    main_return_matches_established_parent, heist_sprout_fade_ready,
    heist_stalled_edge_earned, OpeningRailValueWatch)
from strategy_core.fade_evidence import qualified_fade_candidates
from strategy_core.custody_evidence import build_custody_evidence
from strategy_core.source_freshness import current_source_is_fresh, current_source_receipt
from strategy_core.opportunity_first import OpportunityBook, main_runway


MOUNTAIN_TOOLS = frozenset(("ALTERNATING_MOUNTAIN", "ROLLING_MOUNTAIN"))
# Operator-authorized 2026-11-01 reactivation.  This is an exact allowlist:
# Release handoff, same-direction Rail continuation/value, and Market Heist.
# Legacy Mountain specialist entry intents and every other tactical/fade family
# remain paused; current Mountain entries continue through Commander-owned
# physical candidates only.
REACTIVATED_SPECIALIST_ENTRY_TOOLS = frozenset(("RELEASE_WATCHER", "RAIL", "MARKET_HEIST"))


def mountain_handoff_denial(
    intent: ToolIntent, outgoing: Mapping[str, Any], *, ticker: str, now_ts: float,
    continuity_generation: int | None = None, geometry_source_ms: float | None = None,
) -> str | None:
    """Validate an exact current tool proposal, without choosing a trade.

    The tool supplies terminal-edge authority. Commander and the passive
    writer independently check its identity and freshness before an ordinary
    Mountain relay may use the unconsumed part of the outgoing sale's book.
    """
    proof = intent.metadata.get("mountain_handoff")
    if (intent.tool not in MOUNTAIN_TOOLS or intent.action not in (Action.ENTER, Action.RELAY)
            or not isinstance(proof, Mapping) or proof.get("outgoing_terminal_qualified") is not True):
        return "CURRENT_TERMINAL_MOUNTAIN_HANDOFF_PROOF_REQUIRED"
    side = outgoing.get("side")
    side = side.value if isinstance(side, Side) else side
    if (outgoing.get("tool") not in MOUNTAIN_TOOLS or intent.side is None
            or intent.side.value == side or side not in ("YES", "NO")
            or str(proof.get("outgoing_position_id")) != str(outgoing.get("position_id"))
            or proof.get("outgoing_opportunity_id") != outgoing.get("opportunity_id")
            or proof.get("ticker") != ticker or outgoing.get("ticker") != ticker):
        return "EXACT_OPPOSITE_MOUNTAIN_HANDOFF_IDENTITY_REQUIRED"
    mission = intent.metadata.get("physical_mission_id")
    edge = intent.metadata.get("edge_id")
    old_mission = (outgoing.get("entry_metadata") or {}).get("physical_mission_id")
    if (not isinstance(mission, str) or not mission or proof.get("physical_mission_id") != mission
            or not isinstance(edge, str) or not edge or proof.get("edge_id") != edge
            or mission == old_mission or intent.opportunity_id == outgoing.get("opportunity_id")):
        return "DISTINCT_CURRENT_MOUNTAIN_HANDOFF_MISSION_REQUIRED"
    try:
        observed = float(proof["observed_at"])
        source_ms = float(proof["source_ms"])
        intent_time = float(intent.source_time)
        close_ts = float(outgoing["close_ts"])
        fresh = (all(math.isfinite(value) for value in (observed, source_ms, intent_time, close_ts))
                 and 0 <= now_ts - observed <= 3.0 and 0 <= now_ts - intent_time <= 3.0
                 and abs(observed * 1000.0 - source_ms) <= .001 and now_ts < close_ts)
    except (KeyError, TypeError, ValueError, OverflowError):
        fresh = False
    if not fresh:
        return "CURRENT_MOUNTAIN_HANDOFF_SOURCE_REQUIRED"
    if (type(proof.get("continuity_generation")) is not int or proof["continuity_generation"] < 0
            or continuity_generation is not None and (type(continuity_generation) is not int
                or continuity_generation < 0 or proof["continuity_generation"] != continuity_generation)
            or geometry_source_ms is not None and (not math.isfinite(geometry_source_ms)
                or abs(source_ms - geometry_source_ms) > .001)):
        return "MOUNTAIN_HANDOFF_CURRENT_CAPTURE_MISMATCH"
    return None


@dataclass(frozen=True)
class CommanderDecision:
    action: Action
    intent: ToolIntent | None
    reason: str
    custody_update: Mapping[str, Any] | None = None
    custody_review: Mapping[str, Any] | None = None


class OneCommander:
    """The single strategic and execution-admission decision boundary.

    Tools are advisers: they measure terrain and propose standardized intents.
    They do not own strategy, veto another adviser, or select the trade.  The
    Commander sees the reviewed candidate set, applies the physical strategy
    constitution, chooses one coherent intent, then enforces objective safety.

    Release ownership is deliberately remembered here, at the strategic
    authority boundary.  A one-sample detector dropout cannot manufacture a
    counter-entry while the same living EMA9 arc remains nonterminal.
    """

    def __init__(self) -> None:
        self._release_chapter_key: tuple[str, str, int | None] | None = None
        self._release_chapter_side: Side | None = None
        self._consumed_physical_missions: set[tuple[str, str]] = set()
        self._opening_rail_value_watch = OpeningRailValueWatch()
        # A quote is considered for price improvement only AFTER the physical
        # mission has independently qualified. Never remember an old contract.
        self._entry_quote_window: dict[str, Any] | None = None
        self._opportunities = OpportunityBook(opening_value_watch=self._opening_rail_value_watch)

    @property
    def opportunity_review(self) -> dict[str, Any]:
        """Current causal WATCH/admission audit, never another executor."""
        return self._opportunities.review

    def _entry_quote_value_wait(self, intent: ToolIntent, snapshot: MarketSnapshot) -> str | None:
        """Bounded Commander-owned value timing at a *verified* ordinary edge.

        A future minimum cannot be known. We only wait when an observed quote
        wave is demonstrably oscillating, the ask is well ABOVE its recent low,
        and the parent-scale edge remains valid on subsequent fresh proposals.
        Never delay Releases, Rails, rollover continuation, exceptional <=20c
        extremes, or a fast expanding EMA9 leg. No stale intent is replayed.
        """
        if intent.side is None or intent.action is not Action.ENTER:
            self._entry_quote_window = None
            return None
        family = str(intent.metadata.get("commander_candidate_family") or "").upper()
        md = snapshot.metadata
        strat = md.get("commander_strategy")
        strat = strat if isinstance(strat, Mapping) else {}
        mountain = md.get("mountain")
        mountain = mountain if isinstance(mountain, Mapping) else {}
        if (not (intent.tool == "MARKET_HEIST" or family in {"MOUNTAIN_EDGE", "EDGE_HEIST"})
                or str(strat.get("owned_territory") or "") not in {"ALTERNATING_MOUNTAIN", "MARKET_HEIST"}
                or mountain.get("strong_active_release") is True
                or md.get("release_in_progress") is True
                or md.get("physical_current") is not True
                or not snapshot.quote_current or not snapshot.entry_allowed):
            self._entry_quote_window = None
            return None
        ask = snapshot.ask_for(intent.side)
        if ask is None or not math.isfinite(ask) or not 0.20 < ask <= 0.40:
            self._entry_quote_window = None
            return None
        wave = md.get("quote_wave")
        wave = wave if isinstance(wave, Mapping) else {}
        sides = wave.get("sides")
        sides = sides if isinstance(sides, Mapping) else {}
        brief = sides.get(intent.side.value)
        brief = brief if isinstance(brief, Mapping) else {}
        series = brief.get("series")
        if not brief.get("available") or not isinstance(series, list):
            self._entry_quote_window = None
            return None
        recent = []
        for point in series:
            if not isinstance(point, Mapping):
                continue
            try:
                t, a = float(point["time"]), float(point["ask"])
            except (TypeError, ValueError, KeyError, OverflowError):
                continue
            if (math.isfinite(t) and math.isfinite(a) and 0 <= snapshot.now_ts - t <= 20
                    and 0 < a < 1 and point.get("quote_id")):
                recent.append((t, a, str(point["quote_id"])))
        if (len({item[2] for item in recent}) < 4
                or not recent or snapshot.now_ts - recent[-1][0] > 1.5
                or abs(recent[-1][1] - ask) > 0.011):
            self._entry_quote_window = None
            return None
        seen_low = min(item[1] for item in recent)
        if ask <= seen_low + 0.025:
            self._entry_quote_window = None
            return None
        # Require an actual quote oscillation, not one old cheap stale tick.
        if max(item[1] for item in recent) - seen_low < 0.045:
            self._entry_quote_window = None
            return None
        generation = md.get("geometry_continuity_generation")
        identity = (snapshot.ticker, intent.side.value,
                    str(intent.metadata.get("physical_mission_id") or intent.opportunity_id or ""),
                    generation)
        if not identity[2]:
            self._entry_quote_window = None
            return None
        active = self._entry_quote_window
        if active is None or active.get("identity") != identity:
            self._entry_quote_window = {"identity": identity, "start_ts": snapshot.now_ts,
                "start_ask": ask, "initial_quote_id": recent[-1][2]}
            return "COMMANDER_EARNED_EDGE_BRIEF_QUOTE_VALUE_WINDOW"
        elapsed = snapshot.now_ts - active["start_ts"]
        if elapsed < 0 or elapsed > 10.0:
            self._entry_quote_window = None
            return None
        if recent[-1][2] == active["initial_quote_id"] and elapsed < 2.5:
            return "COMMANDER_EARNED_EDGE_BRIEF_QUOTE_VALUE_WINDOW"
        if ask <= active["start_ask"] - 0.019 or elapsed >= 2.5:
            self._entry_quote_window = None
            return None
        return "COMMANDER_EARNED_EDGE_BRIEF_QUOTE_VALUE_WINDOW"

    @staticmethod
    def _strategy_context(snapshot: MarketSnapshot) -> Mapping[str, Any]:
        raw = snapshot.metadata.get("commander_strategy")
        return raw if isinstance(raw, Mapping) else {}


    @staticmethod
    def _living_ema9_parent_side(snapshot: MarketSnapshot) -> Side | None:
        """Return the current sovereign EMA9 parent side when it is actually observed.

        Strategy/territory ownership can lag or flicker.  The parent mission context
        and current Mountain parent structure are physical evidence; use them before
        any retained tool owner.
        """
        md = snapshot.metadata
        mission = md.get("mission_context")
        mission = mission if isinstance(mission, Mapping) else {}
        parent = mission.get("parent")
        parent = parent if isinstance(parent, Mapping) else {}
        status = str(parent.get("status") or "").upper()
        side = OneCommander._side_text(parent.get("side"))
        if side in {"YES", "NO"} and status not in {"COMPLETED", "INVALIDATED"}:
            return Side(side)
        mountain = md.get("mountain")
        mountain = mountain if isinstance(mountain, Mapping) else {}
        structure = mountain.get("parent_structure")
        structure = structure if isinstance(structure, Mapping) else {}
        side = OneCommander._side_text(structure.get("parent_side"))
        if side in {"YES", "NO"} and structure.get("parent_terminal_ready") is not True:
            return Side(side)
        side = OneCommander._side_text(mountain.get("owner_side"))
        return Side(side) if side in {"YES", "NO"} else None

    def physical_entry_candidates(self, snapshot: MarketSnapshot) -> tuple[ToolIntent, ...]:
        """Commander-owned candidates derived from current physical evidence.

        This bypasses specialist WAIT starvation without bypassing Commander.
        The returned objects are still only candidates; decide()/decide_entry()
        applies strategy comparison and objective execution safety.
        """
        # Commander-owned Mountain candidates remain the only Mountain entry
        # path.  Operator-authorized Release/Rail/Heist entries arrive through
        # the reviewed adviser set and are admitted only by the exact allowlist
        # in _entry_strategy_denial().
        self._opportunities.observe(snapshot)
        main_rejoin = self._opportunities.main_candidate(snapshot)
        candidates = (tuple(physical_entry_candidates(snapshot, opening_watch=self._opening_rail_value_watch,
                            consumed_missions=self._consumed_physical_missions))
                      + tuple(historical_extreme_release_candidates(snapshot))
                      + tuple(quote_wave_scalp_candidates(snapshot))
                      + tuple(edge_heist_candidates(snapshot))
                      + ((main_rejoin,) if main_rejoin is not None else ()))
        reviewed: list[ToolIntent] = []
        for intent in candidates:
            annotated = self._opportunities.annotate(intent, snapshot,
                confirmed_release=self._confirmed_release_handoff(intent, snapshot))
            proof = annotated.metadata["commander_opportunity"]
            if (proof.get("qualified") is True
                    and (snapshot.ticker, str(intent.metadata.get("physical_mission_id") or ""))
                        not in self._consumed_physical_missions
                    and positive_candidate_matches_continuation(intent, snapshot)):
                reviewed.append(annotated)
        return tuple(reviewed)

    def mark_entry_filled(self, intent: ToolIntent | None, *, ticker: str) -> None:
        """Consume a Commander physical mission only after an actual BOOKED fill.

        Quote refresh, exit, ticker rollover, or custody transfer cannot rearm
        the same physical generation. New geometry produces a new stable
        physical_mission_id.
        """
        if intent is None or intent.action not in (Action.ENTER, Action.RELAY):
            return
        self._opportunities.consume(intent, ticker=ticker)
        mission = intent.metadata.get("physical_mission_id")
        if isinstance(mission, str) and mission:
            self._consumed_physical_missions.add((ticker, mission))
        for opening_mission in self._opening_rail_value_watch.consume(intent, ticker=ticker):
            self._consumed_physical_missions.add((ticker, opening_mission))

    @staticmethod
    def _side_text(value: Any) -> str | None:
        if isinstance(value, Side):
            return value.value
        text = str(value).upper() if value is not None else None
        return text if text in ("YES", "NO") else None

    @staticmethod
    def _release_arc_key(snapshot: MarketSnapshot) -> tuple[str, str, int | None] | None:
        mountain = snapshot.metadata.get("mountain")
        mountain = mountain if isinstance(mountain, Mapping) else {}
        arc_id = mountain.get("current_arc_id") or snapshot.metadata.get("current_arc_id")
        side = OneCommander._side_text(mountain.get("owner_side"))
        generation = snapshot.metadata.get("geometry_continuity_generation")
        if not isinstance(arc_id, str) or not arc_id or side is None:
            return None
        if type(generation) is not int:
            generation = None
        return (arc_id, side, generation)

    @staticmethod
    def _release_terminal(snapshot: MarketSnapshot) -> bool:
        mountain = snapshot.metadata.get("mountain")
        mountain = mountain if isinstance(mountain, Mapping) else {}
        terminal = mountain.get("terminal_evidence")
        terminal = terminal if isinstance(terminal, Mapping) else {}
        return bool(
            mountain.get("terminal_evidence_qualified") is True
            or terminal.get("qualified") is True
            or mountain.get("parent_terminal_ready") is True
        )

    def _effective_release_side(self, snapshot: MarketSnapshot) -> Side | None:
        """Return current/latched Release ownership for the living EMA9 arc.

        The latch is identity-based rather than timer-based: it survives a
        detector flicker only while the exact same arc/side/continuity chapter
        remains alive and no true terminal transition has been observed.
        A new arc, owner-side change, continuity reset, or qualified terminal
        edge retires the old Release chapter.
        """
        key = self._release_arc_key(snapshot)
        current_release = snapshot.metadata.get("release_in_progress") is True
        current_side_text = self._side_text(snapshot.metadata.get("release_candidate_side"))
        current_side = Side(current_side_text) if current_side_text else None

        if key is None:
            self._release_chapter_key = None
            self._release_chapter_side = None
            return current_side if current_release else None

        if self._release_chapter_key is not None and self._release_chapter_key != key:
            self._release_chapter_key = None
            self._release_chapter_side = None

        if current_release and current_side is not None and current_side.value == key[1]:
            self._release_chapter_key = key
            self._release_chapter_side = current_side
            return current_side

        if self._release_terminal(snapshot):
            if self._release_chapter_key == key:
                self._release_chapter_key = None
                self._release_chapter_side = None
            return None

        if self._release_chapter_key == key and self._release_chapter_side is not None:
            return self._release_chapter_side
        return None

    def _confirmed_release_handoff(self, intent: ToolIntent, snapshot: MarketSnapshot) -> bool:
        context = self._strategy_context(snapshot)
        return bool(
            context.get("handoff_confirmed") is True
            and intent.tool == "RELEASE_WATCHER"
            and intent.lane is Lane.HANDOFF
            and intent.action in (Action.ENTER, Action.RELAY)
            and intent.side is not None
        )

    def _resolve_entry_custody(self, intent: ToolIntent, snapshot: MarketSnapshot) -> ToolIntent:
        """Bind confirmed Release admission to its own custody before booking.

        MissionPolicy's conditional contract thesis is advisory. A MIXED
        thesis may describe an already confirmed Release as TACTICAL_RETURN;
        booking that annotation would immediately invoke the renter's final
        minute exit. Commander resolves the purpose and role atomically while
        retaining the original advice and all physical/floor evidence.
        """
        if not self._confirmed_release_handoff(intent, snapshot):
            opportunity = self._opportunities.qualify(intent,snapshot)
            evidence = opportunity.get("evidence") or {}
            runway = evidence.get("return_runway") or {}
            if (opportunity.get("qualified") is not True
                    or opportunity.get("species") != "MOUNTAIN_RETURN"
                    or runway.get("target_kind") != "TACTICAL_FROZEN_EMA9_CONTACT"):
                return intent
            # Local travel feasibility rents one measured return to the
            # entry-time EMA9. It never creates a contract-winning MAIN claim.
            source = opportunity["source_ms"]
            original_mission = intent.metadata.get("mission")
            prior_admission = intent.metadata.get("commander_local_return_custody_admission")
            if (isinstance(prior_admission,Mapping) and prior_admission.get("source_ms") == source
                    and prior_admission.get("frozen_target_btc") == runway["target_btc"]
                    and isinstance(original_mission,Mapping) and original_mission.get("purpose") == "TACTICAL_RETURN"
                    and intent.lane is Lane.TACTICAL and intent.metadata.get("position_role") == "TACTICAL"):
                return intent
            mission = dict(original_mission) if isinstance(original_mission,Mapping) else {}
            mission.update(version="OPPORTUNITY_LOCAL_RETURN_V1",purpose="TACTICAL_RETURN",
                side=intent.side.value,parent_leg_id=opportunity.get("parent_id"),
                swing_id=opportunity.get("physical_opportunity_id") or intent.opportunity_id,
                source_ms=source,continuity_generation=opportunity["continuity_generation"],
                classification="VALIDATED_SMALL_TERMINAL_RETURN",target_kind="SWING_DESTINATION",
                destination={"kind":"EMA9_RETURN","btc":runway["target_btc"],"tolerance":0.0,
                    "reference_source_ms":source,"frozen_at_entry":True},
                collection_policy=TACTICAL_COLLECTION_POLICY)
            receipt = current_source_receipt(snapshot,source,max_age_seconds=3.)
            if receipt is not None:
                mission["source_receipt"] = receipt
            resolved={**intent.metadata,"position_role":"TACTICAL","custody":"BOUNDED_LOCAL_RETURN",
                "mission":mission,"entry_geometry":dict(snapshot.metadata.get("current_geometry") or {}),
                "commander_local_return_custody_admission":{
                    "basis":"LOCAL_TARGET_FEASIBILITY_IS_NOT_SETTLEMENT_OWNERSHIP",
                    "source_ms":source,"original_position_role":intent.metadata.get("position_role"),
                    "original_mission":dict(original_mission) if isinstance(original_mission,Mapping) else None,
                    "frozen_target_btc":runway["target_btc"],"settlement_ownership_claim":False}}
            return replace(intent,lane=Lane.TACTICAL,metadata=resolved)
        meta = intent.metadata
        mission = meta.get("mission")
        tactical_mission = isinstance(mission, Mapping) and mission.get("purpose") == "TACTICAL_RETURN"
        if (meta.get("position_role") == "PRIMARY"
                and meta.get("custody") == "LEVIATHAN_RELEASE" and not tactical_mission):
            return intent
        resolved = dict(meta)
        resolved["commander_release_custody_admission"] = {
            "revision": "PID17224_CONFIRMED_RELEASE_CUSTODY_V1",
            "basis": "CURRENT_CONFIRMED_RELEASE_HANDOFF",
            "advisory_position_role": meta.get("position_role"),
            "advisory_custody": meta.get("custody"),
            "advisory_mission": dict(mission) if isinstance(mission, Mapping) else None,
        }
        resolved["position_role"] = "PRIMARY"
        resolved["custody"] = "LEVIATHAN_RELEASE"
        if tactical_mission:
            destination = mission.get("destination")
            parent_destination = (dict(destination) if isinstance(destination, Mapping)
                                  and destination.get("kind") == "PARENT_TERMINAL"
                                  else {"kind": "PARENT_TERMINAL"})
            resolved["mission"] = {**mission, "purpose": "MAIN_CONTRACT",
                "target_kind": "PARENT_TERMINAL", "destination": parent_destination,
                "collection_policy": "THIRD_DISTINCT_WEAKNESS_V1"}
        return replace(intent, metadata=resolved)

    def _entry_custody_denial(self, intent: ToolIntent, snapshot: MarketSnapshot) -> str | None:
        """Do not buy a fresh renter after its existing mandatory exit begins."""
        if self._confirmed_release_handoff(intent, snapshot):
            return None
        # These two species have separate held-position branches ahead of the
        # generic tactical backstop. Their existing custody is unchanged.
        if intent.metadata.get("commander_candidate_family") in {"EDGE_HEIST", "QUOTE_WAVE_SCALP"}:
            return None
        generic_tactical = bool(str(intent.metadata.get("position_role") or "").upper() == "TACTICAL"
            or intent.reason in {
                "HEIST_OUTER_EDGE_TACTICAL_RENTER", "HEIST_OUTER_EDGE_ALIGNED_WITH_EMA_LEAN",
                "HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED", "HEIST_PARALLEL_STALLED_EDGE_RETURN",
                "COMMANDER_HISTORICAL_EXTREME_RELEASE_PREP_SCOUT",
            })
        if not generic_tactical or snapshot.contract_age_s < 840.0:
            return None
        # The held-position path already promotes a seed with current
        # same-side Release/continuation before consulting the renter timer.
        # Such a seed does not face the immediate generic mandatory exit.
        seed_like = bool(intent.tool == "MARKET_HEIST"
            or intent.metadata.get("commander_candidate_family") == "HISTORICAL_EXTREME_RELEASE_PREP")
        if seed_like:
            release_same = bool(snapshot.metadata.get("release_in_progress") is True
                and self._side_text(snapshot.metadata.get("release_candidate_side")) == intent.side.value)
            continuation = ema9_continuation_precedent(snapshot)
            continuation_same = bool(continuation.get("qualified") is True
                and continuation.get("side") == intent.side.value)
            if release_same or continuation_same:
                return None
        return "COMMANDER_TACTICAL_ENTRY_MANDATORY_EXIT_WINDOW"

    @staticmethod
    def _later_tactical_heist_pause_exemption(intent: ToolIntent, snapshot: MarketSnapshot) -> bool:
        """The calibrated later Heist exception applies to one old pause only.

        The live visit must still be the proposed physical swing. The box's
        rolling history-window ID can change within that same visit, so it is
        current box qualification, not equality of those window IDs, that
        supplies the box evidence. This never grants MAIN or Release authority.
        """
        heist = snapshot.metadata.get("heist")
        heist = heist if isinstance(heist, Mapping) else {}
        visit = heist.get("visit_id") or heist.get("current_visit_id")
        return bool(
            intent.tool == "MARKET_HEIST"
            and intent.lane is Lane.TACTICAL
            and intent.metadata.get("position_role") == "TACTICAL"
            and intent.reason in {
                "HEIST_OUTER_EDGE_TACTICAL_RENTER", "HEIST_OUTER_EDGE_ALIGNED_WITH_EMA_LEAN",
                "HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED", "HEIST_PARALLEL_STALLED_EDGE_RETURN",
            }
            and intent.metadata.get("dual_lane_counterfade_calibrated") is True
            and heist.get("qualified_box") is True
            and isinstance(visit, str) and bool(visit)
            and intent.metadata.get("visit_id") == visit
            and snapshot.metadata.get("release_in_progress") is not True
            and snapshot.metadata.get("release_confirmed_current") is not True
        )

    @staticmethod
    def _same_gap_heist_lower_return_earned(intent: ToolIntent, snapshot: MarketSnapshot) -> bool:
        """PID14156: a recovered lower Heist edge is not an old-child fade.

        A current physical 6/9-second rise on the same side as the continuously
        observed EMA9/EMA30 gap can be a legitimate tactical rebound while the
        most recent *child* is still labelled DOWN. This grants only existing
        Heist TACTICAL entry consideration, never Release, Rail, or MAIN
        custody. Cheapness alone, stale source, an unqualified/inner box,
        or a still-falling edge is not sufficient. Commander remains sole
        decision authority; the tool's existing positive proposal is required.
        """
        if (intent.tool != "MARKET_HEIST" or intent.lane is not Lane.TACTICAL
                or intent.action not in (Action.ENTER, Action.RELAY)
                or intent.side is not Side.YES
                or intent.reason != "HEIST_OUTER_EDGE_TACTICAL_RENTER"):
            return False
        mission = intent.metadata.get("mission")
        mission = mission if isinstance(mission, Mapping) else {}
        geo = snapshot.metadata.get("current_geometry")
        geo = geo if isinstance(geo, Mapping) else {}
        mountain = snapshot.metadata.get("mountain")
        mountain = mountain if isinstance(mountain, Mapping) else {}
        heist = snapshot.metadata.get("heist")
        heist = heist if isinstance(heist, Mapping) else {}
        cross = snapshot.metadata.get("ema9_ema30_cross_context")
        cross = cross if isinstance(cross, Mapping) else {}
        lifecycle = cross.get("gap_lifecycle")
        lifecycle = lifecycle if isinstance(lifecycle, Mapping) else {}
        try:
            source = float(geo["epoch_ms"])
            btc6,btc9,ema6=(float(geo[k]) for k in
                ("btc_change6","btc_change9","ema9_change6"))
            ask = float(snapshot.ask_for(intent.side))
            fresh = (all(math.isfinite(x) for x in (source,btc6,btc9,ema6,ask))
                and math.isclose(source,float(cross["source_ms"]),abs_tol=.01)
                and math.isclose(source,float(mountain["source_ms"]),abs_tol=.01)
                and math.isclose(source,float(mission["source_ms"]),abs_tol=.01)
                and 0 <= snapshot.now_ts-intent.source_time <= 2.0)
        except (KeyError, ValueError, TypeError, OverflowError):
            return False
        return bool(
            fresh and snapshot.metadata.get("physical_current") is True
            and current_source_is_fresh(snapshot,source,max_age_seconds=3.0)
            and snapshot.metadata.get("release_confirmed_current") is not True
            and snapshot.metadata.get("release_in_progress") is not True
            and intent.metadata.get("position_role") == "TACTICAL"
            and mission.get("counter_parent_fade") is True
            and mission.get("neutral_heist_repeatable") is not True
            and lifecycle.get("current_side") == "YES"
            and lifecycle.get("observed_side_residence_continuous") is True
            and float(lifecycle.get("observed_side_residence_seconds") or 0) >= 120
            and mountain.get("owner_side") == "NO"
            and heist.get("qualified_box") is True
            and heist.get("current_zone") == "LOWER"
            and heist.get("at_lower_edge") is True
            and 0 < ask <= 0.20
            and btc6 >= 6.0 and btc9 >= 6.0 and ema6 >= 1.0
        )

    def _tp_entry_denial(self, intent: ToolIntent, snapshot: MarketSnapshot) -> str | None:
        """Use TP as first-class evidence for secondary counter trades.

        No blind clock cutoff is used.  If a qualified fade is currently on the
        adverse side of settlement, the movement required to reach TP must fit
        inside movement this terrain has actually demonstrated (recent
        pullbacks or a repeated Heist box traversal). Primary Release/Rail/
        slow-wide continuation is evaluated by contract ownership elsewhere.
        """
        if intent.action not in (Action.ENTER, Action.RELAY) or intent.side is None:
            return None

        meta = intent.metadata if isinstance(intent.metadata, Mapping) else {}
        if meta.get("qualified_fade") is not True:
            return None
        tp = snapshot.metadata.get("tp_geometry")
        tp = tp if isinstance(tp, Mapping) else {}
        current_target_side = self._side_text(tp.get("observed_target_side"))
        if current_target_side is None or current_target_side == intent.side.value:
            return None
        try:
            required = float(tp.get("required_move_to_target_btc"))
        except (TypeError, ValueError):
            return None
        if not math.isfinite(required) or required <= 0:
            return None
        echo = snapshot.metadata.get("leg_echo")
        echo = echo if isinstance(echo, Mapping) else {}
        demonstrated = None
        try:
            value = float(echo.get("median_pullback_btc"))
            if math.isfinite(value) and value > 0:
                demonstrated = value
        except (TypeError, ValueError):
            pass
        heist = snapshot.metadata.get("heist")
        heist = heist if isinstance(heist, Mapping) else {}
        if heist.get("qualified_box") is True:
            try:
                width = float(heist.get("upper")) - float(heist.get("lower"))
                if math.isfinite(width) and width > 0:
                    demonstrated = max(demonstrated or 0.0, width)
            except (TypeError, ValueError):
                pass
        ownership = str(tp.get("contract_ownership") or "")
        ownership_side = self._side_text(tp.get("contract_ownership_side"))
        if (demonstrated is not None and required > demonstrated
                and ownership == "STARTING_LEG_FAVORED"
                and ownership_side is not None and ownership_side != intent.side.value):
            return "COMMANDER_TP_REQUIRED_MOVE_EXCEEDS_DEMONSTRATED_RETURN"
        return None

    def _entry_strategy_denial(self, intent: ToolIntent, snapshot: MarketSnapshot) -> str | None:
        """Non-negotiable physical restraints applied at the one authority.

        This deliberately duplicates the two most important strategy invariants
        instead of trusting an adviser/lane filter to have applied them.
        """
        if intent.action not in (Action.ENTER, Action.RELAY) or intent.side is None:
            return None

        # Ineligible legacy descriptions never become executable candidates.
        # Name that stable policy denial before asking them for modern source
        # or opportunity proof; every authorized route still passes below.
        if intent.metadata.get("commander_primary_candidate") is not True:
            if MOUNTAIN_ONLY_MODE:
                return "COMMANDER_MOUNTAIN_ONLY_SPECIALIST_ENTRIES_PAUSED"
            if intent.tool in MOUNTAIN_TOOLS:
                return "COMMANDER_LEGACY_MOUNTAIN_SPECIALIST_ENTRY_PAUSED_USE_PRIMARY"
            if intent.tool not in REACTIVATED_SPECIALIST_ENTRY_TOOLS:
                return "COMMANDER_UNAUTHORIZED_SPECIALIST_ENTRY_PAUSED"
            if intent.tool == "RAIL" and intent.reason not in {"RAIL_MAIN_VALUE","RAIL_EMA9_DIP_VALUE"}:
                return "COMMANDER_UNAUTHORIZED_RAIL_ENTRY_REASON"
            if intent.tool == "MARKET_HEIST" and intent.reason not in {
                "HEIST_OUTER_EDGE_ALIGNED_WITH_EMA_LEAN","HEIST_OUTER_EDGE_TACTICAL_RENTER",
                "HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED","HEIST_PARALLEL_STALLED_EDGE_RETURN"}:
                return "COMMANDER_UNAUTHORIZED_HEIST_ENTRY_REASON"

        mission = intent.metadata.get("physical_mission_id")
        if isinstance(mission, str) and (snapshot.ticker, mission) in self._consumed_physical_missions:
            return "COMMANDER_PHYSICAL_MISSION_ALREADY_FILLED"
        if intent.reason == "COMMANDER_OPENING_RAIL_DIP_VALUE_REJOIN":
            evidence = intent.metadata.get("commander_physical_evidence")
            deferred = evidence.get("deferred_mission_id") if isinstance(evidence, Mapping) else None
            if isinstance(deferred, str) and (snapshot.ticker, deferred) in self._consumed_physical_missions:
                return "COMMANDER_PHYSICAL_MISSION_ALREADY_FILLED"

        # A specialist route cannot buy the same early parent dip that caused
        # Commander to defer an earned premium opening.  WAIT retains that
        # parent opportunity for a current cheaper rejoin, without changing
        # any held-position custody or Release/Heist authority.
        self._opening_rail_value_watch.observe(snapshot, (intent,))
        fishing_denial = self._opening_rail_value_watch.entry_denial(intent, snapshot)
        if fishing_denial is not None:
            return fishing_denial

        # Operator-authorized protect-the-house rule is contract-local and
        # applies before route-specific permission. One ordinary win blocks
        # premium (>20c) non-Heist risk; two wins or one +100% gross winner
        # stands down all non-Heist entries until the next contract. A genuine
        # Market Heist remains the explicit exception.
        house = snapshot.metadata.get("contract_house_state")
        house = house if isinstance(house, Mapping) else {}
        house_mode = str(house.get("mode") or "OPEN")
        live_ask = snapshot.ask_for(intent.side)
        easy_true_mountain_edge = bool(
            intent.metadata.get("commander_primary_candidate") is True
            and str(intent.metadata.get("commander_candidate_family") or "") == "MOUNTAIN_EDGE"
            and live_ask is not None and math.isfinite(live_ask) and 0 < live_ask <= 0.20
            and current_mountain_terminal(
                snapshot.metadata.get("mountain")
                if isinstance(snapshot.metadata.get("mountain"), Mapping) else {}
            )
        )
        quote_wave_scalp = bool(intent.metadata.get("commander_primary_candidate") is True
            and str(intent.metadata.get("commander_candidate_family") or "") == "QUOTE_WAVE_SCALP"
            and live_ask is not None and math.isfinite(live_ask) and 0 < live_ask <= 0.08)
        extreme_release_prep = bool(intent.metadata.get("commander_primary_candidate") is True
            and str(intent.metadata.get("commander_candidate_family") or "") == "HISTORICAL_EXTREME_RELEASE_PREP"
            and live_ask is not None and math.isfinite(live_ask) and 0 < live_ask <= 0.15)
        if (house_mode == "PROTECTED" and intent.tool != "MARKET_HEIST"
                and not easy_true_mountain_edge and not quote_wave_scalp and not extreme_release_prep):
            return "COMMANDER_HOUSE_PROTECTED_WAIT_NEXT_CONTRACT"
        if (house_mode == "CAUTION" and intent.tool != "MARKET_HEIST"
                and not quote_wave_scalp and not extreme_release_prep
                and live_ask is not None and math.isfinite(live_ask) and live_ask > 0.20):
            return "COMMANDER_HOUSE_CAUTION_BLOCK_PREMIUM_ENTRY"

        custody_denial = self._entry_custody_denial(intent, snapshot)
        if custody_denial is not None:
            return custody_denial

        if not heist_sprout_fade_ready(intent, snapshot):
            return "COMMANDER_HEIST_FRESH_SPROUT_REQUIRES_CAUSAL_TURN"
        if not heist_stalled_edge_earned(intent, snapshot):
            return "COMMANDER_HEIST_STALLED_EDGE_NEEDS_PHYSICAL_RETURN"

        # Every source, including Commander-native shortcuts, earns the same
        # positive physical species before any legacy family shortcut.  A cheap
        # quote/old label cannot create entry authority.  This is a decision of
        # the one Commander; specialist WAITs remain advisory only.
        opportunity = self._opportunities.qualify(intent, snapshot,
            confirmed_release=self._confirmed_release_handoff(intent, snapshot))
        if opportunity.get("qualified") is not True:
            return str(opportunity.get("reason") or "OPPORTUNITY_NO_POSITIVE_SPECIES")

        if intent.metadata.get("commander_primary_candidate") is True:
            family = str(intent.metadata.get("commander_candidate_family") or "")
            if family not in {"MOUNTAIN_EDGE", "MOUNTAIN_CONTRACT_LEG", "QUOTE_WAVE_SCALP",
                              "HISTORICAL_EXTREME_RELEASE_PREP", "EDGE_HEIST"}:
                return "COMMANDER_MOUNTAIN_ONLY_NONMOUNTAIN_CANDIDATE_PAUSED"
            if not main_return_matches_established_parent(intent, snapshot):
                return "COMMANDER_MAIN_RETURN_ESTABLISHED_PARENT_TRANSFER_REQUIRED"
            return None
        if MOUNTAIN_ONLY_MODE:
            return "COMMANDER_MOUNTAIN_ONLY_SPECIALIST_ENTRIES_PAUSED"
        if intent.tool in MOUNTAIN_TOOLS:
            return "COMMANDER_LEGACY_MOUNTAIN_SPECIALIST_ENTRY_PAUSED_USE_PRIMARY"
        if intent.tool not in REACTIVATED_SPECIALIST_ENTRY_TOOLS:
            return "COMMANDER_UNAUTHORIZED_SPECIALIST_ENTRY_PAUSED"

        # Operator authorization is entry-species-specific, not a blanket
        # permission for every historical intent emitted by an enabled tool.
        # This prevents dormant/legacy reasons from becoming executable merely
        # because Rail, Release, or Heist was reactivated.
        if intent.tool == "RAIL" and intent.reason not in {"RAIL_MAIN_VALUE", "RAIL_EMA9_DIP_VALUE"}:
            return "COMMANDER_UNAUTHORIZED_RAIL_ENTRY_REASON"
        if intent.tool == "MARKET_HEIST" and intent.reason not in {
                "HEIST_OUTER_EDGE_ALIGNED_WITH_EMA_LEAN",
                "HEIST_OUTER_EDGE_TACTICAL_RENTER",
                "HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED",
                "HEIST_PARALLEL_STALLED_EDGE_RETURN",
        }:
            return "COMMANDER_UNAUTHORIZED_HEIST_ENTRY_REASON"
        if intent.tool == "MARKET_HEIST":
            # A fully qualified *later* Heist swing may operate tactically
            # beside a living directional MAIN parent. The first opposing
            # swing is observation only (DualLaneCounterfadeMemory); this
            # exception never overrides a confirmed active Release.
            dual_calibrated = bool(intent.metadata.get("dual_lane_counterfade_calibrated") is True
                and isinstance(snapshot.metadata.get("heist"), Mapping)
                and snapshot.metadata["heist"].get("qualified_box") is True
                and snapshot.metadata.get("release_in_progress") is not True)
            # PID1172 #8: a local box/return cannot countertrade a still-living
            # MATURE/ROLLING directional parent.  This duplicates the Tool Rack
            # suppression at the single authority boundary so a classifier
            # takeover cannot bypass the living EMA9 chapter.
            mountain_now = snapshot.metadata.get("mountain")
            mountain_now = mountain_now if isinstance(mountain_now, Mapping) else {}
            cross_now = snapshot.metadata.get("ema9_ema30_cross_context")
            cross_now = cross_now if isinstance(cross_now, Mapping) else {}
            lifecycle_now = cross_now.get("gap_lifecycle")
            lifecycle_now = lifecycle_now if isinstance(lifecycle_now, Mapping) else {}
            stage_now = str(lifecycle_now.get("stage") or "").upper()
            gap_side_now = str(lifecycle_now.get("current_side") or "").upper()
            owner_side_now = str(mountain_now.get("owner_side") or "").upper()
            motion_now = mountain_now.get("current_motion")
            motion_now = motion_now if isinstance(motion_now, Mapping) else {}
            m30_now = motion_now.get("30")
            m30_now = m30_now if isinstance(m30_now, Mapping) else {}
            try:
                owner_price_rate = float(m30_now.get("owner_price_rate_btc_s"))
                owner_ema9_rate = float(m30_now.get("owner_ema9_rate_btc_s"))
            except (TypeError, ValueError):
                owner_price_rate = owner_ema9_rate = 0.0
            living_directional_parent = bool(
                stage_now in {"MATURE", "ROLLING"}
                and owner_side_now in {"YES", "NO"}
                and gap_side_now == owner_side_now
                and mountain_now.get("terminal_evidence_qualified") is not True
                and m30_now.get("covered") is True
                and owner_price_rate > 0 and owner_ema9_rate > 0
            )
            if living_directional_parent and not dual_calibrated:
                return "COMMANDER_HEIST_BLOCKED_LIVING_DIRECTIONAL_PARENT"
        if intent.tool == "RELEASE_WATCHER":
            if self._confirmed_release_handoff(intent, snapshot):
                return None
            return "COMMANDER_RELEASE_REQUIRES_CONFIRMED_HANDOFF"
        if self._confirmed_release_handoff(intent, snapshot):
            return None

        context = self._strategy_context(snapshot)
        effective_release = self._effective_release_side(snapshot)
        if effective_release is not None and intent.side is not effective_release:
            return "COMMANDER_RELEASE_CHAPTER_OWNS_DIRECTION"
        mission = intent.metadata.get("mission")
        mission = mission if isinstance(mission, Mapping) else {}
        rail_child_value = bool(mission.get("rail_child_arc_value") is True
            and isinstance(intent.metadata.get("rail_child_arc_value"), Mapping))
        if (mission.get("counter_parent_fade") is True
                and mission.get("neutral_heist_repeatable") is not True
                and not rail_child_value
                and not self._later_tactical_heist_pause_exemption(intent, snapshot)
                and not self._same_gap_heist_lower_return_earned(intent, snapshot)):
            return "COMMANDER_TACTICAL_FADES_PAUSED"
        # Legacy RAIL_CHILD_ARC_CHEAP_RIDER is telemetry only.  Rail counter
        # trades must now be synthesized by Commander from a genuine failed
        # excursion/fakeout, never from child age + cheapness.
        if rail_child_value:
            return "COMMANDER_LEGACY_RAIL_CHILD_CHEAP_RIDER_RETIRED"

        # Mountain already answered the only strategic question that matters:
        # is the living EMA9 arc at its current terminal extreme?  Do not run
        # that exact relay through EMA30/Rail, thesis, release, or any other
        # second strategic veto. Objective quote/depth/source safety is checked
        # later in decide().
        if intent.tool in MOUNTAIN_TOOLS:
            earned_mountain_edge = bool(
                intent.reason in ("MOUNTAIN_TERMINAL_EMA9_EDGE_RELAY",
                                  "MOUNTAIN_TERMINAL_EDGE_SUB20_VALUE_RELAY")
                and (intent.metadata.get("terminal_evidence") or {}).get("qualified") is True)
            cheap_hover_edge = bool(
                intent.reason == "MOUNTAIN_CHEAP_HOVER_EDGE_RELAY"
                and intent.metadata.get("cheap_hover_edge") is True)
            small_fast_edge = bool(
                intent.reason == "MOUNTAIN_SMALL_FAST_ARC_EDGE_RELAY"
                and intent.metadata.get("small_fast_arc_edge") is True)
            armed_edge_value = bool(
                intent.reason in ("MOUNTAIN_ARMED_EDGE_SUB20_VALUE_ENTRY",
                                  "MOUNTAIN_WIDE_TOP_PATIENT_VALUE_ENTRY",
                                  "MOUNTAIN_LOW_WIDE_SIDEWAYS_VALUE_ENTRY")
                and (intent.metadata.get("armed_edge_value") or {}).get("edge_id"))
            fast_bridge_edge = bool(
                intent.reason == "MOUNTAIN_FAST_NARROW_EDGE_PREENTRY_BRIDGE"
                and (intent.metadata.get("fast_handoff_bridge") or {}).get("outgoing_position_id")
                and (intent.metadata.get("terminal_evidence") or {}).get("qualified") is True)
            rollover_edge_value = bool(
                intent.reason == "MOUNTAIN_INHERITED_EDGE_CHEAP_ROLLOVER_ENTRY"
                and (intent.metadata.get("rollover_inherited_edge") or {}).get("edge_id"))
            if (earned_mountain_edge or cheap_hover_edge or small_fast_edge
                    or armed_edge_value or rollover_edge_value or fast_bridge_edge):
                # These are all the same earned EMA9-edge mission at different
                # execution moments.  An expensive edge can wait for <=$0.20
                # without needing the crest to remain terminal on the fill tick.
                return None

        mountain = snapshot.metadata.get("mountain")
        mountain = mountain if isinstance(mountain, Mapping) else {}
        mission_context = snapshot.metadata.get("mission_context")
        mission_context = mission_context if isinstance(mission_context, Mapping) else {}
        parent = mission_context.get("parent")
        parent = parent if isinstance(parent, Mapping) else {}

        living_side = (self._side_text(parent.get("side"))
                       or self._side_text(mountain.get("owner_side"))
                       or self._side_text(context.get("owned_side")))
        if mountain.get("strong_active_release") is True and living_side is not None:
            if intent.side.value != living_side:
                return "COMMANDER_BLOCK_COUNTER_EXPANDING_EMA_AWAIT_RELEASE"

        territory = str(context.get("owned_territory") or "")
        rail_owner = self._side_text(context.get("owned_side"))
        if territory in ("UP_RAIL", "DOWN_RAIL") and rail_owner is not None:
            if intent.side.value != rail_owner and not (
                    intent.tool == "MARKET_HEIST"
                    and intent.metadata.get("dual_lane_counterfade_calibrated") is True
                    and snapshot.metadata.get("release_in_progress") is not True
                    and mountain.get("strong_active_release") is not True):
                return "COMMANDER_BLOCK_RAIL_COUNTERFADE_AWAIT_RELEASE"

        # Mountain side comes from the living EMA9 arc. EMA30 location/crossing
        # cannot manufacture a reversal. A full-zone entry requires CURRENT
        # EMA9 terminal evidence at the extreme.
        terminal_cue = bool(
            mountain.get("stall") is True
            or mountain.get("hesitation") is True
            or mountain.get("failed_reextension") is True
            or mountain.get("meaningful_retreat") is True
            # Paired-gap similarity is briefing/location evidence only. It may
            # tell Commander to prepare and fish cheap, but cannot itself turn
            # an outward-expanding EMA9 parent into a paid terminal.
            or mountain.get("comparable_slow_edge") is True
        )
        terminal_now = bool(terminal_cue and (
            mountain.get("terminal_evidence_qualified") is True
            or mountain.get("mature_edge") is True
        ))
        if (territory in ("ALTERNATING_MOUNTAIN", "ROLLING_MOUNTAIN")
                and intent.tool in MOUNTAIN_TOOLS and living_side is not None
                and intent.side.value != living_side and not terminal_now):
            return "COMMANDER_BLOCK_MOUNTAIN_COUNTERLEG_BEFORE_CURRENT_EMA9_TERMINAL"
        return None

    def _entry_rank(self, intent: ToolIntent, snapshot: MarketSnapshot) -> tuple[int, int, str]:
        """Deterministic Commander priority; advisers never arbitrate each other."""
        context = self._strategy_context(snapshot)
        active_tool = str(context.get("active_tool") or "")
        mission = intent.metadata.get("mission")
        mission = mission if isinstance(mission, Mapping) else {}
        purpose = str(mission.get("purpose") or "")
        opportunity = self._opportunities.qualify(intent, snapshot,
            confirmed_release=self._confirmed_release_handoff(intent, snapshot))
        species = opportunity.get("species") if opportunity.get("qualified") is True else None
        if species == "RELEASE_HANDOFF":
            tier = -2
        elif (snapshot.contract_age_s >= 450 and species == "MAIN_EMA9_REJOIN"
                and opportunity.get("side") == opportunity.get("parent_side")):
            tier = -1
        elif intent.metadata.get("dual_lane") == "MAIN":
            tier = 3
        elif intent.metadata.get("commander_primary_candidate") is True:
            family = str(intent.metadata.get("commander_candidate_family") or "")
            tier = 0 if family == "MOUNTAIN_CONTRACT_LEG" else 2 if family == "QUOTE_WAVE_SCALP" else 1
        elif self._confirmed_release_handoff(intent, snapshot):
            tier = 4
        elif intent.tool == active_tool and intent.tool == "RAIL":
            tier = 5
        elif purpose == "ARC_RETURN" or intent.metadata.get("full_arc_return") is True:
            tier = 6
        elif intent.tool == active_tool:
            tier = 7
        elif purpose == "MAIN_CONTRACT":
            tier = 8
        elif intent.tool == "MARKET_HEIST":
            tier = 9
        else:
            tier = 10
        # Prefer the actual owner tool inside a tier, then stable source order/name.
        owner_penalty = 0 if intent.tool == active_tool else 1
        return (tier, owner_penalty, intent.tool)

    def _select_entry_intent(
        self, actionable: list[ToolIntent], snapshot: MarketSnapshot
    ) -> tuple[ToolIntent | None, str | None]:
        allowed: list[ToolIntent] = []
        denials: list[str] = []
        for intent in actionable:
            intent = self._resolve_entry_custody(intent, snapshot)
            denial = self._entry_strategy_denial(intent, snapshot)
            if denial is None:
                allowed.append(intent)
            else:
                denials.append(denial)
        if not allowed:
            return None, denials[0] if denials else "NO_STRATEGY_QUALIFIED_ENTRY"
        allowed.sort(key=lambda item: self._entry_rank(item, snapshot))
        best_rank = self._entry_rank(allowed[0], snapshot)[:2]
        best = [item for item in allowed if self._entry_rank(item, snapshot)[:2] == best_rank]
        if len(best) > 1:
            sides = {item.side for item in best}
            if len(sides) > 1:
                return None, "COMMANDER_CONFLICTING_TOP_PRIORITY_SIDES"
            # Same-side duplicate advisers describe the same physical direction.
            # The stable rank/order picks exactly one executor instruction.
        return best[0], None

    def decide(
        self,
        intents: tuple[ToolIntent, ...] | list[ToolIntent],
        snapshot: MarketSnapshot,
    ) -> CommanderDecision:
        self._opportunities.observe(snapshot)
        decision = self._decide(intents, snapshot)
        if decision.action in (Action.ENTER, Action.RELAY) and decision.intent is not None:
            decision = replace(decision, intent=self._opportunities.annotate(decision.intent, snapshot,
                confirmed_release=self._confirmed_release_handoff(decision.intent, snapshot)))
        self._opportunities.result(snapshot, decision)
        return decision

    def _decide(
        self,
        intents: tuple[ToolIntent, ...] | list[ToolIntent],
        snapshot: MarketSnapshot,
    ) -> CommanderDecision:
        actionable = [
            intent
            for intent in intents
            if intent.action is not Action.WAIT
        ]

        if not actionable:
            opportunity_review = self._opportunities.review
            denied = [row for row in opportunity_review.get("candidates", ())
                      if row.get("qualified") is not True and row.get("reason")]
            wait_reason = (
                str(denied[0]["reason"]) if denied else intents[0].reason
                if intents
                else str(opportunity_review.get("main_alignment", {}).get("reason") or "NO_TOOL_INTENT")
            )
            return CommanderDecision(
                Action.WAIT,
                None,
                wait_reason,
            )

        if len(actionable) > 1:
            if all(intent.action in (Action.ENTER, Action.RELAY) for intent in actionable):
                intent, denial = self._select_entry_intent(actionable, snapshot)
                if intent is None:
                    return CommanderDecision(Action.WAIT, None, denial or "NO_STRATEGY_QUALIFIED_ENTRY")
            else:
                return CommanderDecision(
                    Action.WAIT,
                    None,
                    "CONFLICTING_ACTIONABLE_NONENTRY_INTENTS",
                )
        else:
            intent = actionable[0]

        if intent.action in (Action.ENTER, Action.RELAY):
            intent = self._resolve_entry_custody(intent, snapshot)
            denial = self._entry_strategy_denial(intent, snapshot)
            if denial is not None:
                return CommanderDecision(Action.WAIT, None, denial)
            tp_denial = self._tp_entry_denial(intent, snapshot)
            if tp_denial is not None:
                return CommanderDecision(Action.WAIT, None, tp_denial)

        if intent.action is Action.HOLD:
            return CommanderDecision(Action.HOLD, intent, "COMMANDER_ACCEPTED_TOOL_CUSTODY")

        if intent.action is Action.EXIT:
            return self._exit_decision(intent, snapshot)

        if not snapshot.quote_current:
            return CommanderDecision(
                Action.WAIT,
                None,
                "OBJECTIVE_QUOTE_STALE",
            )

        if not snapshot.depth_available:
            return CommanderDecision(
                Action.WAIT,
                None,
                "OBJECTIVE_DEPTH_UNAVAILABLE",
            )

        if not snapshot.entry_allowed:
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_ENTRY_NOT_ALLOWED")
        if snapshot.metadata.get("physical_current") is False:
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_PHYSICAL_SOURCE_STALE")

        if (
            intent.action in (
                Action.ENTER,
                Action.RELAY,
            )
            and intent.side is not None
        ):
            ask = snapshot.ask_for(
                intent.side
            )
            if ask is None or not math.isfinite(ask) or not 0 < ask < 1:
                return CommanderDecision(
                    Action.WAIT,
                    None,
                    "OBJECTIVE_EXECUTABLE_ASK_UNAVAILABLE",
                )
            # No universal price veto. Price discipline is terrain-specific
            # and carried by the candidate itself: Mountain terminal reversals
            # can demand <=20c while Release/Rail continuation may pay up to the
            # approved ~40-45c range.
            if (
                intent.max_price is not None
                and ask > intent.max_price
            ):
                return CommanderDecision(
                    Action.WAIT,
                    None,
                    "OBJECTIVE_PRICE_MOVED_ABOVE_TOOL_LIMIT",
                )

        if intent.action in (Action.ENTER, Action.RELAY):
            value_wait = self._entry_quote_value_wait(intent, snapshot)
            if value_wait:
                return CommanderDecision(Action.WAIT, None, value_wait)

        return CommanderDecision(
            intent.action,
            intent,
            "COMMANDER_ACCEPTED_TOOL_INTENT",
        )

    @staticmethod
    def _exit_decision(intent: ToolIntent, snapshot: MarketSnapshot) -> CommanderDecision:
        if intent.side is None:
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_HELD_SIDE_MISSING")
        if not snapshot.quote_current:
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_QUOTE_STALE_EXIT_PENDING")
        bid = snapshot.bid_for(intent.side)
        if (not snapshot.can_sell(intent.side) or bid is None or not math.isfinite(bid)
                or not 0 < bid < 1):
            return CommanderDecision(Action.WAIT, None, "OBJECTIVE_HELD_SIDE_BID_UNAVAILABLE_EXIT_PENDING")
        return CommanderDecision(Action.EXIT, intent, "COMMANDER_ACCEPTED_EXACT_HELD_SIDE_EXIT")

    def decide_position(
        self, intents: tuple[ToolIntent, ...] | list[ToolIntent], snapshot: MarketSnapshot,
        position: Mapping[str, Any], *, floor_breached: bool = False,
        stop_requested: bool = False,
        recovery_review: Mapping[str, Any] | None = None,
    ) -> CommanderDecision:
        """The same Commander resolves custody and mandatory objective exits.

        Tools select structural HOLD/EXIT. Qualified developed-loss recovery is
        reviewed here, never by an execution-side sanctuary. Already armed
        floors, accepted hard adverse handoffs and manual stops remain prior.
        """
        review = recovery_review
        if review is not None and (str(review.get("position_id")) != str(position["position_id"])
                or review.get("previous_state") != position.get("custody_state", "NORMAL")
                or review.get("reviewed_at") != snapshot.now_ts):
            return CommanderDecision(Action.WAIT, None, "EXACT_CURRENT_POSITION_RECOVERY_REVIEW_REQUIRED")

        def finish(decision: CommanderDecision, next_state: str | None = None,
                   transition_reason: str | None = None) -> CommanderDecision:
            current = str(position.get("custody_state") or "NORMAL")
            update = None
            if next_state is not None and next_state != current:
                update = {"position_id": str(position["position_id"]), "previous_state": current,
                          "state": next_state, "reason": transition_reason or
                          (decision.intent.reason if decision.intent else decision.reason),
                          "reviewed_at": snapshot.now_ts, "review": review or {}}
            return replace(decision, custody_update=update, custody_review=review)

        side = position.get("side")
        if not isinstance(side, Side):
            side = Side(str(side).upper())
        if position.get("ticker") != snapshot.ticker:
            return finish(CommanderDecision(Action.WAIT, None, "OBJECTIVE_HELD_TICKER_MISMATCH"))
        if snapshot.now_ts >= float(position["close_ts"]):
            return finish(CommanderDecision(Action.WAIT, None, "EXACT_CONTRACT_AWAITING_OFFICIAL_FINALITY"))
        required = floor_breached or bool(position.get("exit_required"))
        if required or stop_requested:
            reason = (str(position.get("exit_reason") or "ALREADY_ARMED_EXECUTABLE_BID_FLOOR")
                      if required else "OPERATOR_PAPER_STOP")
            intent = ToolIntent(tool=str(position["tool"]), territory_id=str(position["territory_id"]),
                lane=Lane(position.get("lane", Lane.MAIN)), side=side, action=Action.EXIT,
                opportunity_id=str(position["opportunity_id"]), max_price=None, size_tier=None,
                reason=reason, source_time=snapshot.now_ts,
                metadata={"ticker": snapshot.ticker, "objective_exit": True})
            return finish(self._exit_decision(intent, snapshot), "EXIT_PENDING", reason)
        if (snapshot.metadata.get("physical_current") is False
                and not snapshot.metadata.get("pending_exit_was_previously_observed")):
            return finish(CommanderDecision(Action.HOLD, None, "PHYSICAL_SOURCE_STALE_CUSTODY_UNCHANGED"))
        # EMA9 sovereignty: ordinary PRIMARY custody cannot outrank the living
        # parent.  If a held PRIMARY is now opposite the currently observed
        # EMA9 parent, release that stale custody so the correct-side mission
        # can be evaluated on the next native quote. Tactical renters/Lazarus
        # remain governed by their own bounded custody.
        living_parent = self._living_ema9_parent_side(snapshot)
        entry_md = position.get("entry_metadata") if isinstance(position.get("entry_metadata"), Mapping) else {}
        seed_family = str(entry_md.get("commander_candidate_family") or "").upper()
        entry_reason = str(position.get("entry_reason") or "").upper()
        physical_evidence = entry_md.get("commander_physical_evidence") if isinstance(entry_md.get("commander_physical_evidence"), Mapping) else {}
        entry_location = str(physical_evidence.get("entry_location") or "").upper()
        transition_age_s = max(0.0, snapshot.now_ts - float(position.get("entry_time") or snapshot.now_ts))
        transition_reason = entry_reason in {
            "COMMANDER_INHERITED_YOUNG_LEG_ROLLOVER_CONTINUATION",
            "COMMANDER_MOUNTAIN_TRUE_EDGE_RETURN",
            "COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN",
            "COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN",
            "HEIST_OUTER_EDGE_TACTICAL_RENTER",
            "HEIST_OUTER_EDGE_ALIGNED_WITH_EMA_LEAN",
            "HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED",
            "HEIST_PARALLEL_STALLED_EDGE_RETURN",
        }
        role = str(position.get("position_role") or entry_md.get("position_role") or "PRIMARY").upper()
        custody_state = str(position.get("custody_state") or "NORMAL").upper()

        # PID14312: transition custody is physical, not a blind 180-second
        # timer.  Once the initial breathing window passes, a return seed may
        # continue only while current evidence still supports that side: the
        # current EMA9 arc has turned with it, TP explicitly favors its bounce,
        # the old parent is turning at the earned edge, or Release/continuation
        # has adopted it.  Unsupported wrong-side positions still exit.
        geometry = snapshot.metadata.get("current_geometry")
        geometry = geometry if isinstance(geometry, Mapping) else {}
        arc_direction = str(geometry.get("arc_direction") or "").upper()
        arc_side = Side.YES if arc_direction == "UP" else Side.NO if arc_direction == "DOWN" else None
        tp = snapshot.metadata.get("tp_geometry")
        tp = tp if isinstance(tp, Mapping) else {}
        tp_side = self._side_text(tp.get("contract_ownership_side"))
        tp_status = str(tp.get("contract_ownership") or "UNRESOLVED").upper()
        mountain_now = snapshot.metadata.get("mountain")
        mountain_now = mountain_now if isinstance(mountain_now, Mapping) else {}
        parent_now = mountain_now.get("parent_structure")
        parent_now = parent_now if isinstance(parent_now, Mapping) else {}
        parent_turning = bool(parent_now.get("parent_turning_or_flat") is True
                              or mountain_now.get("parent_turning_or_flat") is True)
        outgoing_owner = self._side_text(physical_evidence.get("outgoing_owner_side")
                                         or physical_evidence.get("owner_side"))
        release_side = str(snapshot.metadata.get("release_candidate_side") or "").upper()
        continuation = ema9_continuation_precedent(snapshot)
        continuation_same = bool(continuation.get("qualified") is True
                                 and continuation.get("side") == side.value)
        release_same = bool(snapshot.metadata.get("release_in_progress") is True
                            and release_side == side.value)
        # PID18244 #3: an older NO crossing or one DOWN child arc may be
        # useful evidence for a tactical renter. It is not sufficient to
        # graduate that renter to MAIN while the physically current EMA9
        # parent remains UP. Read the native parent scale separately from the
        # local arc (which can temporarily point DOWN during a YES sprout).
        # The existing same-side current Release handoff remains independent.
        native_parent = str(geometry.get("parent_direction") or "").upper()
        native_source_ms = geometry.get("epoch_ms")
        current_native_parent = (
            Side.YES if native_parent == "UP" else
            Side.NO if native_parent == "DOWN" else None
        ) if (snapshot.metadata.get("physical_current") is True
              and current_source_is_fresh(snapshot, native_source_ms,
                                          max_age_seconds=3.0)) else None
        # Only newly verified, causal native frames can *add* this promotion
        # conflict. A retained mission/territory parent can disagree with a
        # present arc and is already handled by existing custody rules; it
        # must not become an extra veto on the historically approved same-side
        # emerging-leg test when no fresh physical native parent is proven.
        parent_opposes_seed = bool(not release_same
            and current_native_parent is not None
            and current_native_parent is not side)
        if parent_opposes_seed:
            continuation_same = False
        if isinstance(entry_md.get("commander_local_return_custody_admission"),Mapping):
            # A local return may graduate only on new current direction/runway
            # proof. Old gap residence or an unconfirmed release watch alone
            # cannot stretch its frozen return destination into MAIN custody.
            release_same = bool(release_same and (
                snapshot.metadata.get("release_confirmed_current") is True
                or self._strategy_context(snapshot).get("handoff_confirmed") is True))
            try:
                sign = 1.0 if side is Side.YES else -1.0
                actual_flow = all(math.isfinite(float(geometry[k])) and sign*float(geometry[k])>0
                    for k in ("btc_change6","btc_change9","btc_change30","ema9_change6","ema9_change30"))
            except (KeyError,TypeError,ValueError,OverflowError):
                actual_flow = False
            continuation_same = bool(continuation_same and current_native_parent is side
                and actual_flow and main_runway(snapshot,side)[0])
        arc_same = arc_side is side
        tp_same = bool(tp_side == side.value
                       and tp_status in {"STARTING_LEG_FAVORED", "BOUNCE_FAVORED"})
        parent_turn_support = bool(parent_turning and outgoing_owner in {"YES", "NO"}
                                   and outgoing_owner != side.value)
        return_support = bool(release_same or continuation_same or arc_same
                              or tp_same or parent_turn_support)
        transition_family = bool(
            seed_family in {"EDGE_HEIST", "QUOTE_WAVE_SCALP", "HISTORICAL_EXTREME_RELEASE_PREP"}
            or seed_family == "MOUNTAIN_CONTRACT_LEG"
            or transition_reason
            or (seed_family == "MOUNTAIN_EDGE" and entry_location in {
                "FRESH_EXTENDED_MOUNTAIN_EXTREME", "ROLLOVER_TERMINAL_RETURN_START",
                "MOUNTAIN_TERMINAL_RETURN", "PARENT_TERMINAL_RETURN",
                "RECENT_LEVEL_MATCH_RETURN"})
        )
        transitional_return = bool(transition_family and (
            transition_age_s <= 180.0
            or (transition_age_s <= 600.0 and return_support)
        ))
        promoted_support = bool(custody_state == "PROMOTED_MAIN" and return_support)
        if (living_parent is not None and role == "PRIMARY" and custody_state != "LAZARUS"
                and side is not living_parent and not transitional_return and not promoted_support):
            intent = ToolIntent(tool="ONE_COMMANDER_CUSTODY", territory_id=str(position["territory_id"]),
                lane=Lane(position.get("lane", Lane.MAIN)), side=side, action=Action.EXIT,
                opportunity_id=str(position["opportunity_id"]), max_price=None, size_tier=None,
                reason="COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT", source_time=snapshot.now_ts,
                metadata={"ticker": snapshot.ticker, "living_ema9_parent_side": living_parent.value,
                          "position_role": role, "objective_exit": False})
            return finish(self._exit_decision(intent, snapshot), "EXIT_PENDING", intent.reason)
        if review is not None and review.get("action") in ("HOLD", "EXIT"):
            recovery_action = Action(review["action"])
            # A floor/partial-sale/manual request was already resolved above.
            # Only this one boundary may replace an ordinary tool exit with
            # qualified custody, or return a supported recovery to its manager.
            if recovery_action is Action.HOLD and review.get("hard_exit"):
                return finish(CommanderDecision(Action.WAIT, None, "CONFLICTING_HARD_EXIT_RECOVERY_REVIEW"))
            template = intents[0] if len(intents) == 1 else None
            intent = ToolIntent(
                tool=template.tool if template else str(position["tool"]),
                territory_id=template.territory_id if template else str(position["territory_id"]),
                lane=template.lane if template else Lane(position.get("lane", Lane.MAIN)),
                side=side, action=recovery_action, opportunity_id=str(position["opportunity_id"]),
                max_price=None, size_tier=None, reason=str(review["reason"]),
                source_time=snapshot.now_ts,
                metadata={**(template.metadata if template else {}),
                          "ticker": snapshot.ticker, "recovery_custody_reviewed": True})
            deferred = (strategy_exit_hold_reason(position, snapshot, intent.reason)
                        if recovery_action is Action.EXIT else None)
            if deferred:
                held = replace(intent, action=Action.HOLD, reason=deferred,
                    metadata={**intent.metadata, "deferred_strategy_exit_reason": intent.reason})
                return finish(CommanderDecision(Action.HOLD, held, deferred))
            accepted = (self._exit_decision(intent, snapshot) if recovery_action is Action.EXIT else
                        CommanderDecision(Action.HOLD, intent, "COMMANDER_ACCEPTED_QUALIFIED_RECOVERY_CUSTODY"))
            return finish(accepted, str(review["next_state"]), str(review["reason"]))
        # PID252: one cheap Heist / Quote-Wave / Extreme-Prep seed may graduate
        # into the same-side Release instead of being sold and repurchased at a
        # worse basis. Promotion changes custody only; it does not create a
        # second position or confirm Release by itself.
        entry_md = position.get("entry_metadata") if isinstance(position.get("entry_metadata"), Mapping) else {}
        seed_family = str(entry_md.get("commander_candidate_family") or "").upper()
        seed_like = bool(str(position.get("tool") or "").upper() == "MARKET_HEIST"
                         or seed_family in {"QUOTE_WAVE_SCALP", "HISTORICAL_EXTREME_RELEASE_PREP", "EDGE_HEIST"})
        already_promoted = custody_state == "PROMOTED_MAIN"
        if seed_like and (release_same or not parent_opposes_seed and (
                continuation_same or already_promoted and return_support)):
            reason = ("COMMANDER_HEIST_SEED_PROMOTED_TO_RELEASE_CUSTODY" if release_same
                      else "COMMANDER_HEIST_SEED_PROMOTED_TO_LIVING_EMA9_CUSTODY")
            promoted = ToolIntent(tool="ONE_COMMANDER_CUSTODY", territory_id="RELEASE_PROMOTED_SEED",
                lane=Lane.MAIN, side=side, action=Action.HOLD,
                opportunity_id=str(position["opportunity_id"]), max_price=None, size_tier=None,
                reason=reason, source_time=snapshot.now_ts,
                metadata={"promoted_from":seed_family or str(position.get("tool") or "HEIST"),
                          "release_side":release_side, "position_role":"PRIMARY",
                          "continuation_precedent":dict(continuation),
                          "floor_policy":{"arm_roi":2.0,"trail_fraction":0.05,"min_age_s":0.0,
                                          "immediate_arm_roi":2.0,"first_arm_from_current_bid":True,
                                          "roi_trail_tiers":[[3.0,0.03],[6.0,0.02]],
                                          "profit_policy_revision":"HEIST_SEED_TO_LIVING_LEG_RUNNER_V2"}})
            next_state = None if already_promoted else "PROMOTED_MAIN"
            return finish(CommanderDecision(Action.HOLD, promoted, promoted.reason), next_state, reason)

        # Edge Heist is a bounded Mountain-edge renter unless the same-side
        # Release/return has already promoted it above. It may collect one or
        # two micro-swings while MAIN is still waiting for full terminal proof.
        if str(entry_md.get("commander_candidate_family") or "") == "EDGE_HEIST":
            edge = entry_md.get("edge_heist") if isinstance(entry_md.get("edge_heist"), Mapping) else {}
            age = snapshot.now_ts - float(position.get("entry_time") or snapshot.now_ts)
            max_hold = float(edge.get("max_hold_s") or 180.0)
            if age >= max_hold:
                intent = ToolIntent(tool="ONE_COMMANDER_CUSTODY", territory_id=str(position["territory_id"]),
                    lane=Lane.TACTICAL, side=side, action=Action.EXIT,
                    opportunity_id=str(position["opportunity_id"]), max_price=None, size_tier=None,
                    reason="EDGE_HEIST_MAX_HOLD_EXIT", source_time=snapshot.now_ts,
                    metadata={"edge_heist": dict(edge), "same_candle_exit_authorized": True})
                return finish(self._exit_decision(intent, snapshot), "EXIT_PENDING", intent.reason)
            held = ToolIntent(tool="ONE_COMMANDER_CUSTODY", territory_id=str(position["territory_id"]),
                lane=Lane.TACTICAL, side=side, action=Action.HOLD,
                opportunity_id=str(position["opportunity_id"]), max_price=None, size_tier=None,
                reason="EDGE_HEIST_AWAIT_SWING_OR_MAIN_PROMOTION", source_time=snapshot.now_ts,
                metadata={"edge_heist": dict(edge)})
            if not isinstance(entry_md.get("commander_local_return_custody_admission"), Mapping):
                return finish(CommanderDecision(Action.HOLD, held, held.reason))

        # Quote-Wave scalp has intentionally bounded tactical custody. Its
        # executable floor may close immediately on a reprice; otherwise it
        # cannot silently become a MAIN/settlement hold.
        entry_md = position.get("entry_metadata") if isinstance(position.get("entry_metadata"), Mapping) else {}
        if str(entry_md.get("commander_candidate_family") or "") == "QUOTE_WAVE_SCALP":
            scalp = entry_md.get("quote_wave_scalp") if isinstance(entry_md.get("quote_wave_scalp"), Mapping) else {}
            age = snapshot.now_ts - float(position.get("entry_time") or snapshot.now_ts)
            max_hold = float(scalp.get("max_hold_s") or 120.0)
            if age >= max_hold:
                intent = ToolIntent(tool="ONE_COMMANDER_CUSTODY", territory_id=str(position["territory_id"]),
                    lane=Lane.TACTICAL, side=side, action=Action.EXIT,
                    opportunity_id=str(position["opportunity_id"]), max_price=None, size_tier=None,
                    reason="QUOTE_WAVE_SCALP_MAX_HOLD_EXIT", source_time=snapshot.now_ts,
                    metadata={"quote_wave_scalp": dict(scalp), "same_candle_exit_authorized": True})
                return finish(self._exit_decision(intent, snapshot), "EXIT_PENDING", intent.reason)
            held = ToolIntent(tool="ONE_COMMANDER_CUSTODY", territory_id=str(position["territory_id"]),
                lane=Lane.TACTICAL, side=side, action=Action.HOLD,
                opportunity_id=str(position["opportunity_id"]), max_price=None, size_tier=None,
                reason="QUOTE_WAVE_SCALP_AWAIT_REPRICE_OR_FLOOR", source_time=snapshot.now_ts,
                metadata={"quote_wave_scalp": dict(scalp)})
            if not isinstance(entry_md.get("commander_local_return_custody_admission"), Mapping):
                return finish(CommanderDecision(Action.HOLD, held, held.reason))

        # Universal tactical-custody backstop. A renter/scout may promote into
        # same-side MAIN/Release above, but otherwise it is never allowed to
        # drift into accidental settlement custody. This applies even when a
        # tactical adviser occupied the PRIMARY role slot because no other MAIN
        # position existed at entry time.
        tactical_reasons = {
            "HEIST_OUTER_EDGE_TACTICAL_RENTER",
            "HEIST_OUTER_EDGE_ALIGNED_WITH_EMA_LEAN",
            "HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED",
            "HEIST_PARALLEL_STALLED_EDGE_RETURN",
            "COMMANDER_HISTORICAL_EXTREME_RELEASE_PREP_SCOUT",
        }
        generic_tactical = bool(custody_state != "PROMOTED_MAIN"
                                and (role == "TACTICAL" or entry_reason in tactical_reasons))
        if generic_tactical:
            age = max(0.0, snapshot.now_ts - float(position.get("entry_time") or snapshot.now_ts))
            max_hold = 120.0 if entry_reason == "COMMANDER_HISTORICAL_EXTREME_RELEASE_PREP_SCOUT" else 180.0
            seconds_left = max(0.0, float(position.get("close_ts") or snapshot.now_ts) - snapshot.now_ts)
            if age >= max_hold or seconds_left <= 60.0:
                reason = ("TACTICAL_MAX_HOLD_EXIT" if age >= max_hold
                          else "TACTICAL_EXIT_BEFORE_SETTLEMENT_WINDOW")
                intent = ToolIntent(tool="ONE_COMMANDER_CUSTODY", territory_id=str(position["territory_id"]),
                    lane=Lane.TACTICAL, side=side, action=Action.EXIT,
                    opportunity_id=str(position["opportunity_id"]), max_price=None, size_tier=None,
                    reason=reason, source_time=snapshot.now_ts,
                    metadata={"position_role":"TACTICAL", "same_candle_exit_authorized":True,
                              "tactical_max_hold_s":max_hold})
                return finish(self._exit_decision(intent, snapshot), "EXIT_PENDING", reason)

        # A Commander-admitted local return retains its purchased destination.
        # Consume the existing source/identity/path/full-lot net collection
        # proof here before generic Mountain custody can override that mission.
        # Floors, stops, recovery, earned promotion and tactical finality above
        # keep their prior authority. A stale or foreign proof grants no sale.
        if (isinstance(entry_md.get("commander_local_return_custody_admission"),Mapping)
                and custody_state in ("NORMAL","RECOVERED_NORMAL")):
            scoped = mission_collection_evidence(position,snapshot)
            qualified = bool(scoped.get("valid") is True and scoped.get("current") is True
                and scoped.get("purpose") == "TACTICAL_RETURN"
                and scoped.get("collection_policy") == TACTICAL_COLLECTION_POLICY
                and scoped.get("collection_qualified") is True)
            reason = str(scoped.get("collection_authority") if qualified else
                scoped.get("collection_hold_reason") or scoped.get("reason") or
                "COMMANDER_LOCAL_RETURN_COLLECTION_UNVERIFIED")
            if scoped.get("collection_policy") != TACTICAL_COLLECTION_POLICY:
                reason = "COMMANDER_LOCAL_RETURN_COLLECTION_POLICY_REQUIRED"
            intent = ToolIntent(tool="ONE_COMMANDER_CUSTODY",territory_id=str(position["territory_id"]),
                lane=Lane.TACTICAL,side=side,action=Action.EXIT if qualified else Action.HOLD,
                opportunity_id=str(position["opportunity_id"]),max_price=None,size_tier=None,
                reason=reason,source_time=snapshot.now_ts,
                metadata={"commander_local_return_collection":scoped,"position_role":"TACTICAL"})
            if qualified:
                return finish(self._exit_decision(intent,snapshot),"EXIT_PENDING",reason)
            return finish(CommanderDecision(Action.HOLD,intent,reason))

        # Strategic custody belongs here, not in the originating tool.  A
        # recovered-normal lot is treated like any other winner; a Lazarus lot
        # stays under the explicit recovery review above until restored.
        custody_state = str(position.get("custody_state") or "NORMAL")
        if custody_state in ("NORMAL", "RECOVERED_NORMAL", "PROMOTED_MAIN"):
            custody = build_custody_evidence(position, snapshot)
            recommendation = custody.get("recommendation")
            if recommendation == "COLLECT":
                intent = ToolIntent(
                    tool="ONE_COMMANDER_CUSTODY", territory_id=str(position["territory_id"]),
                    lane=Lane(position.get("lane", Lane.MAIN)), side=side, action=Action.EXIT,
                    opportunity_id=str(position["opportunity_id"]), max_price=None, size_tier=None,
                    reason=str(custody.get("reason") or "COMMANDER_STRUCTURAL_COLLECTION"),
                    source_time=snapshot.now_ts, metadata={"commander_custody_evidence": custody})
                return finish(self._exit_decision(intent, snapshot), "EXIT_PENDING", intent.reason)
            if recommendation == "HOLD":
                template = intents[0] if len(intents) == 1 else None
                held = ToolIntent(
                    tool="ONE_COMMANDER_CUSTODY", territory_id=str(position["territory_id"]),
                    lane=Lane(position.get("lane", Lane.MAIN)), side=side, action=Action.HOLD,
                    opportunity_id=str(position["opportunity_id"]), max_price=None, size_tier=None,
                    reason=str(custody.get("reason") or "COMMANDER_STRUCTURAL_HOLD"),
                    source_time=snapshot.now_ts, metadata={
                        **(template.metadata if template else {}),
                        "commander_custody_evidence": custody,
                        "tool_management_advice": ({"tool": template.tool, "action": template.action.value, "reason": template.reason} if template else None),
                    })
                return finish(CommanderDecision(Action.HOLD, held, held.reason))

        if not intents:
            return finish(CommanderDecision(Action.HOLD, None, "ORIGINAL_TOOL_CUSTODY_UNAVAILABLE"))
        if len(intents) != 1 or intents[0].action not in (Action.HOLD, Action.EXIT):
            return finish(CommanderDecision(Action.WAIT, None, "CONFLICTING_POSITION_MANAGEMENT_INTENTS"))
        intent = intents[0]
        if intent.side is not side:
            return finish(CommanderDecision(Action.WAIT, None, "OBJECTIVE_EXIT_SIDE_DOES_NOT_MATCH_POSITION"))
        if intent.action is Action.EXIT:
            # Tool exit proposals are advisory. If current Commander custody
            # evidence did not independently establish collection above, keep
            # the position and record the tool's opinion for forensics.
            held = replace(intent, action=Action.HOLD,
                reason="COMMANDER_TOOL_EXIT_ADVISORY_ONLY_UNRESOLVED",
                metadata={**intent.metadata,
                          "tool_management_advice": {"action": "EXIT", "reason": intent.reason},
                          "commander_custody_evidence": build_custody_evidence(position, snapshot)})
            return finish(CommanderDecision(Action.HOLD, held, held.reason))
        return finish(CommanderDecision(Action.HOLD, intent, "COMMANDER_ACCEPTED_TOOL_HOLD"))

    def decide_entry(
        self, intents: tuple[ToolIntent, ...] | list[ToolIntent], snapshot: MarketSnapshot,
        positions: Mapping[str, Any],
    ) -> CommanderDecision:
        self._opportunities.observe(snapshot)
        decision = self._decide_entry(intents, snapshot, positions)
        self._opportunities.result(snapshot, decision, positions)
        return decision

    def _decide_entry(
        self, intents: tuple[ToolIntent, ...] | list[ToolIntent], snapshot: MarketSnapshot,
        positions: Mapping[str, Any],
    ) -> CommanderDecision:
        # One-Commander constitution: adviser WAITs are telemetry only.
        # A specialist may describe a late/deferred preference, but it cannot
        # veto an independently qualified Commander candidate. Any true timing
        # restraint must be encoded in Commander's own physical candidate and
        # strategy checks, not inferred from an adviser WAIT reason.
        held = [position for position in positions.values()
                if (position.get("ticker") if isinstance(position, Mapping) else position.ticker) == snapshot.ticker]
        if held:
            actionable = [intent for intent in intents if intent.action in (Action.ENTER, Action.RELAY)]
            if not actionable:
                return CommanderDecision(Action.WAIT, None, "CURRENT_CONTRACT_INVENTORY_NO_NEW_COMMANDER_CANDIDATE")

            # Commander, not adviser count/order, selects the candidate. Multiple
            # tools describing the market can never become an implicit veto.
            selected, denial = self._select_entry_intent(actionable, snapshot)
            if selected is None:
                return CommanderDecision(Action.WAIT, None, denial or "NO_STRATEGY_QUALIFIED_ENTRY")

            if all(field(p, "custody_state") == "LAZARUS" for p in held):
                generation = snapshot.metadata.get("geometry_continuity_generation", 0)
                try:
                    generation = int(generation)
                except (TypeError, ValueError, OverflowError):
                    generation = 0
                recovery_denial = independent_entry_denial(selected, held, now_ts=snapshot.now_ts,
                    continuity_generation=generation)
                if recovery_denial:
                    return CommanderDecision(Action.WAIT, None, recovery_denial)
            else:
                # Inventory is execution/custody state, not strategy authority.
                # Same-side inventory prevents duplicate spray. Opposite-side
                # inventory must flatten through decide_position() before a
                # corrective handoff can commit, but it cannot choose the side.
                held_sides = {self._side_text(field(p, "side")) for p in held}
                if selected.side.value in held_sides:
                    return CommanderDecision(Action.WAIT, None, "CURRENT_CONTRACT_SAME_SIDE_INVENTORY_NO_DUPLICATE")
                return CommanderDecision(Action.WAIT, None,
                    "CURRENT_CONTRACT_OPPOSITE_INVENTORY_EXIT_PENDING_CORRECTIVE_HANDOFF")
        return self.decide(intents, snapshot)

    def decide_handoff_entry(
        self, intent: ToolIntent, snapshot: MarketSnapshot, positions: Mapping[str, Any], *,
        outgoing: Mapping[str, Any], exit_receipt: Mapping[str, Any],
    ) -> CommanderDecision:
        """Accept the incoming leg only after the exact outgoing lot is flat.

        This is a second explicit decision, after an independently authorized
        EXIT. A partial sale, an old proposal, or a retained Lazarus companion
        cannot be treated as a completed ordinary opposite-side handoff.
        """
        if snapshot.metadata.get("physical_current") is not True:
            return CommanderDecision(Action.WAIT, None, "CURRENT_MOUNTAIN_HANDOFF_SOURCE_REQUIRED")
        try:
            source_ms = float(snapshot.metadata["geometry_last_epoch_ms"])
            generation = snapshot.metadata["geometry_continuity_generation"]
        except (KeyError, TypeError, ValueError, OverflowError):
            return CommanderDecision(Action.WAIT, None, "MOUNTAIN_HANDOFF_CURRENT_CAPTURE_MISMATCH")
        if type(generation) is not int or generation < 0:
            return CommanderDecision(Action.WAIT, None, "MOUNTAIN_HANDOFF_CURRENT_CAPTURE_MISMATCH")
        denial = mountain_handoff_denial(intent, outgoing, ticker=snapshot.ticker,
            now_ts=snapshot.now_ts, continuity_generation=generation, geometry_source_ms=source_ms)
        if denial:
            return CommanderDecision(Action.WAIT, None, denial)
        event = exit_receipt.get("event") or {}
        outgoing_side = outgoing.get("side")
        outgoing_side = outgoing_side.value if isinstance(outgoing_side, Side) else outgoing_side
        if (exit_receipt.get("status") != "EXITED"
                or str(exit_receipt.get("position_id")) != str(outgoing["position_id"])
                or event.get("event") != "EXIT" or event.get("position_qty_after") != 0
                or str(event.get("position_id")) != str(outgoing["position_id"])
                or event.get("side") != outgoing_side
                or event.get("ticker") != snapshot.ticker
                or event.get("quote_id") != snapshot.metadata.get("quote_id")):
            return CommanderDecision(Action.WAIT, None, "MOUNTAIN_HANDOFF_REQUIRES_COMMITTED_FULL_EXIT")
        if any((p.get("ticker") if isinstance(p, Mapping) else p.ticker) == snapshot.ticker
               for p in positions.values()):
            return CommanderDecision(Action.WAIT, None, "MOUNTAIN_HANDOFF_REQUIRES_FLAT_CURRENT_CONTRACT")
        intent = replace(intent, metadata={**intent.metadata, "mountain_handoff_execution": {
            "outgoing_position_id": str(outgoing["position_id"]),
            "exit_command_id": exit_receipt.get("command_id"),
            "exit_journal_seq": exit_receipt.get("journal_seq"),
            "quote_id": event.get("quote_id"), "exit_timestamp": event.get("timestamp"),
        }})
        accepted = self.decide_entry((intent,), snapshot, positions)
        return (replace(accepted, reason="COMMANDER_ACCEPTED_COORDINATED_MOUNTAIN_HANDOFF")
                if accepted.action in (Action.ENTER, Action.RELAY) else accepted)
