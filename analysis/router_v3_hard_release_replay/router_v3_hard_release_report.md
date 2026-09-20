# Entry Authority Router V3 — Hard Release Replay

Hard release is intentionally stricter than local arc continuation.

Counted evidence:
- Failed-Regen CONFIRMED_RELEASE
- Crest RELEASE_CONFIRMED
- directional BOUNDARY_RELEASE
- true Hand authority transfer
- War Council ACT_IMMEDIATELY / ACT_FIRST_VALID

Missing telemetry is UNKNOWN, not negative evidence.

All entries: 188
Stale >=9s entries: 97
Stale >=9s PULLBACK_WAIT entries: 28

## Stale >=9s: hard release order

- NO_HARD_RELEASE_SEEN: N=33 P&L=$-36.20 settlement=21/31
- OPPOSITE_HARD_RELEASE_FIRST: N=33 P&L=$-46.79 settlement=19/33
- SAME_HARD_RELEASE_FIRST: N=31 P&L=$-40.94 settlement=18/30

## Stale >=9s PULLBACK_WAIT: hard release order

- NO_HARD_RELEASE_SEEN: N=12 P&L=$-23.99 settlement=8/11
- OPPOSITE_HARD_RELEASE_FIRST: N=5 P&L=$-12.89 settlement=3/5
- SAME_HARD_RELEASE_FIRST: N=11 P&L=$+3.09 settlement=8/11

## Stale >=9s PULLBACK_WAIT: first same hard release source

- (blank): N=16 P&L=$-39.97 settlement=10/15
- BOUNDARY_RELEASE: N=3 P&L=$+0.42 settlement=3/3
- CREST_RELEASE_CONFIRMED: N=2 P&L=$+5.47 settlement=1/2
- FAILED_REGEN_CONFIRMED: N=2 P&L=$-2.82 settlement=1/2
- HAND_AUTHORITY_TRANSFER: N=3 P&L=$+8.25 settlement=3/3
- WAR_COUNCIL_RELEASE: N=2 P&L=$-5.14 settlement=1/2

## Stale >=9s PULLBACK_WAIT: same hard release within 30s

- 0: N=27 P&L=$-38.34 settlement=18/26
- 1: N=1 P&L=$+4.54 settlement=1/1

## Coverage source count

- 5: N=188 P&L=$-74.00 settlement=114/184

## Interpretation discipline

- A local EMA arc resuming in the same direction is not counted as authority transfer.
- A hard release after the historical entry is counterfactual evidence that waiting may have had a structural endpoint.
- This still does not simulate fill price or management after waiting.
- Runs with partial telemetry must not be treated as if absent events were disproven.
- No V3 result changes V9.5A authority.
