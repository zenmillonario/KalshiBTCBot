# Tool Rack Commander Kernel PAPER handoff — 2026-10-29

This build is a structural correction, not another fade threshold patch.

## Why the previous build could repeat the same mistake

The previous source said that tools owned strategy inside their territory and that Commander only resolved already-selected intents. In practice an entry could be transformed or discarded by Tool -> MissionPolicy -> role selection -> LaneResolver before Commander saw it. At the same time, a full-arc Mountain candidate explicitly bypassed the `strong_active_release` fade restraint, and `rail.json` declared `opposite_fades: false` without loading or enforcing that switch.

That combination can produce both observed symptoms: starvation of a valid same-direction Rail entry and admission of the one trade that should not occur, an opposite fade against a living expanding EMA9 parent.

## New authority path

1. Detectors and tools measure physical evidence and propose intents.
2. MissionPolicy annotates purpose/economics but is not the final strategy authority.
3. ToolRack keeps the legacy lane-resolved output for diagnostics and also publishes the complete reviewed adviser candidate set.
4. PAPER runtime sends the complete reviewed set to **OneCommander**.
5. OneCommander deterministically chooses one coherent entry, applies the physical strategy constitution, then applies quote/depth/execution safety.
6. One passive PAPER executioner books only the accepted Commander instruction.

No specialist gets account/order authority. LaneResolver remains observable as a shadow comparison but cannot silently starve the PAPER strategy before Commander compares candidates.

## Hard strategy constitution in this build

- **Never counter-fade `strong_active_release`.** This includes a geometrically qualified/full-parent arc. A full-arc label is not proof that active expansion ended.
- **Rail `opposite_fades: false` is live.** While Rail owns, compatible Mountain/Heist opposite fades are not generated. The only opposite transfer path is a confirmed ReleaseWatcher HANDOFF.
- **Commander independently rechecks both restraints.** Even if an adviser regresses later and proposes the forbidden trade, Commander refuses it.
- **Physical Rail continuation outranks advisory contract thesis.** If the current physical parent is the Rail side, continuation is supported, the current value location qualifies, and exact target/history provenance is complete, a conflicting conditional/history directional thesis cannot veto the Rail MAIN entry. Missing history or target still waits.
- **Full mountain peak/valley entries remain valid after expansion is no longer active.** The correction does not require a cosmetic EMA curl or a 40% tactical forecast for a real whole-parent return.
- **No mid-leg Mountain permission was added.** `mid_leg_entries: false` is now an actual loaded runtime switch.

## Previously decorative JSON controls now wired

`rail.opposite_fades`, `rail.rollover_creates_new_slice`, `mountain.mid_leg_entries`, `mountain.strong_active_release_defers_fade`, `heist.release_ends_box_immediately`, `release.first_slowdown_confirms_release`, `release.requires_boundary_break`, and `release.requires_directional_expansion` are loaded into runtime tool configs and used by behavior.

## Validation boundary

The supplied archive is PAPER only. The uploaded source archive did not contain the stopped run's complete decision journal, so this correction does not pretend to reconstruct the exact losing fill from runtime telemetry. The static path that allowed that behavior was found directly in source and has exact regression tests. A fresh Windows PAPER run is still the required behavioral validation before any real-money discussion.
