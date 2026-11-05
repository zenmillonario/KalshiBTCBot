# Tachyos PID21672 — Migration checkpoint (November 5, 2026)

**Status:** PAPER-only, full Windows 45-minute program with Nautilus. This branch is a forensic/source-delta checkpoint, **not** a replacement for the complete sealed runnable program ZIP. Do not merge into legacy `main` without reconciling historical code. The next chat takes over analysis of the *next* uploaded run.

## Exact run that informed this checkpoint

Run ID: `TOOL_RACK_PAPER_20261105T170438Z_PID21672` (roughly 12:04–12:49 ET, November 5).

- Complete original upload transport reassembled from 7 parts: 605,488,970 bytes, SHA-256 `8cf5be466d24ebc11f62f680602dd629b619708d12b6b727b76939669f1a8364`.
- The captured program matched its source; full original-market replay was **not** executed on the differing local Python interpreter.
- PAPER: starting $1,000.00; ending $992.0250; net **−$7.9750 after $4.7100 fees**; four trades and no open position.
- #1 YES 8.9c → 7.4c = −$2.685. User praised the entry/protective behavior; preserve as a behavioral control but **not** a financial winner.
- #2 NO 37c → 16c = −$5.90. Special inherited Mountain rollover rationale borrowed the 363.52s parent age although the specific EMA9 child arc was only 44.13s old inside a 93.28s contract. It began **after** rollover. New code requires that actual child arc predate the contract.
- #3 NO 27c → 18c = −$10.05. Accepted `RAIL_MAIN_VALUE` MAIN proposal was rewritten as TACTICAL custody, forcing `TACTICAL_MAX_HOLD_EXIT` at 180s despite qualified NO parent. New code preserves MAIN custody only when current source receipt, parent, gap, side, identity, generation and caller lane agree.
- #4 YES 33c → 74c = **+$10.66**. Earned later Heist return with whole-position profit protection. Preserve entry/floor behavior.

## The approved two-file source delta

The two production source changes relative to the captured PID10656 program are in `SOURCE_DELTA.patch` in this folder:

1. `strategy_core/commander_candidates.py`: require current EMA9 child arc age > current contract age + 1 second for special rollover inheritance; parent age remains separate advisory/MAIN context.
2. `strategy_core/mission_policy.py`: preserve PRIMARY custody for an already-briefed RAIL MAIN value intent with current causal source and qualified matching physical parent. This **does not create a trade, bypass price caps, authorize first-minute premium buying, or change floors**. Adviser WAIT remains advisory.

Source SHA-256 after changes:
- commander_candidates.py: `3e2fdf72957b71e0f50967353ae066dd3f3daab83010f7f55a2c9d26211dae05`
- mission_policy.py: `eed85cd2115263147d0a211d0f6c92e95b0e328675c6e1cb509050743a95805f`

The prior PID10656 source seal and approval are retained and pinned separately in the new package. The full program has preflight and frozen-core tests. Check package `PID21672_VALIDATION.json` for independently completed delivery evidence.

## Important pending tactical research (no unapproved live trade)

The user hypothesized an affordable tactical YES rebound near the third contract of a long DOWN Rail when EMA9 is extended and a low target was left from the previous contract. Observe the first cheap valid Heist edge and collect short profits or promote the **same** position to MAIN only after genuine Release. On PID21672, the price actually crossed back above EMA9 **after** rollover; EMA9 stayed below EMA30. First-minute YES ask was around 56–72c, not an affordable <=35c scout. No new premium YES entry was granted.

## Preserve these invariants

- ONE Commander is sole order authority, advisers brief and explain; MAIN/TACTICAL evaluate independently, no adviser veto.
- EMA9 current living parent is dominant; EMA30 is context; consider prior 3–4 contracts, no fake opposite fades of early sprouts.
- First minute WAIT except actually earned inherited leg; small cheap contracts can still stake $25 total; prevent doubling the same losing opportunity in Lazarus.
- Whole-position harvest/late runway rules and profit floors preserved; don't regress the current bright dashed Looking Glass physical-pattern overlay.
- Full input recording/export + small upload parts; full real-market exact replay requires compatible runtime. Synthetic three-way replay cannot establish market profitability.
- No real-money authority.

## Next chat

Receive `00_SEND_FIRST_REVIEW.zip` plus all numbered `01_RUN_PART...` ZIPs from a NEW run. Verify transport hashes and source, audit all entries/exits/misses, compare to parent geometry and Looking Glass projections, and test corrections against recorded cases and historical positive controls. The purpose is better reproducible PAPER performance, not repeating the earlier recording-lab milestones.

This Git branch is isolated from old `main`. **The complete tested Windows application is distributed separately as a sealed ZIP**; this repository checkpoint stores source deltas, provenance and handoff, not the complete current application.
