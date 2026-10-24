# Tachyos R22 PID21520 positive baseline — 2026-10-23

This branch records the exact known-good R22 baseline observed in Windows PAPER run `PAPER_20261024T004619Z_PID21520`.

## Why this is frozen

- Mode: Kalshi PRODUCTION read-only market data / internal PAPER only.
- Run stopped flat through the normal R22 drain.
- 10 entries; 8 winners / 2 losers.
- Gross PAPER P/L: +$69.09. This is one simulated run and is **not** a profitability claim.
- Current/executable native quote states were about 91% of recorded quote states.
- `BOOK_RECEIVE_STALE` fell to 394 from 5,086 in PID19496.
- The PID19496 current-book receiver, reconnect-generation reset, physical Heist edge latch, one-Commander architecture, and hard source-safety controls are therefore preserved as the positive base.

## Exact artifacts

Known-good source package:
`TACHYOS_R22_PID19496_CURRENT_BOOK_PHYSICAL_EDGE_RELEASE_3H_2026-10-23.zip`

SHA-256:
`be7089593cddefaf137c3f98e71abcd073d25cbd4164bea2d8c239c1684b7bc4`

PID21520 compact diagnostic:
`PAPER_20261024T004619Z_PID21520_R22_COMPACT_DIAGNOSTICS_75c8deccf2.zip`

SHA-256:
`2be222c855ff4acf3b6e56817348f95768494b4c5a6fbba91557241c468aceb3`

Exact 165-file R22 engine source-hash manifest SHA-256:
`c3c4712c6644d6c6f16f15ffd5aba9ce98a0cfe9a221c2fb6aa4f0d714a81a14`

A copy of that full source-hash manifest is committed next to this README.

## Baseline controls

Preserve:
- EMA9/NAEVYR sovereignty; EMA30 context.
- One Commander / one executioner.
- Observer42, Navigator, Nautilus, Looking Glass and Shadow AI: zero trading/readiness authority.
- Current-book native receiver and reconnect generation reset.
- 15-second hard exchange-age refusal.
- Physical Heist edge-generation latch; no duplicate same-edge purchase.
- Directional Heist release blocks opposite child fades.
- No arbitrary entry cap/cooldown.
- No new entry unit at $0.74 or higher.
- Existing non-loosening winner floors.

## Important repository note

The pre-existing repository tree is older than this R22 runtime lineage. This branch is therefore an **immutable baseline anchor**, not a claim that the old root tree itself equals PID21520. The exact source identity is the committed 165-file hash manifest plus the package SHA above. Do not overwrite `main` or reinterpret older Git code as current strategy.

The next R22 candidate after this frozen base addresses PID21520 #2 early collection, #7 fakeout continuation, #9 weakening arcs, and missing ordinary EMA9 arc-top participation. Those refinements are intentionally separate from this positive baseline.
