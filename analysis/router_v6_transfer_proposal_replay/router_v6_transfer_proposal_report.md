# Entry Authority Router V6 — Transfer → Proposal Handshake

Scope: the first Hand/Boundary transfer epoch found by V5 for each stale >=9s PULLBACK_WAIT case.

V6 does not assume we can magically fill at the transfer instant. It asks whether the existing V9.5A proposal stream later presented the transfer side during that same transfer epoch.

Acceptance audit uses the already-existing 0.20–0.80 band:
- V9.4G V94G_FIRST_VALID_MIN_ASK = 0.20
- V9.4G V94G_FIRST_VALID_MAX_ASK = 0.80
- legacy MAX_ENTRY_ASK = 0.80

Transfer epochs: 10
Any post-transfer proposal before next transfer/close: 1
Post-transfer proposal inside existing 0.20–0.80 band: 1

Counterfactual economics buy the first accepted-band proposal and hold to settlement with a $10 stake. This still does not model fills, fees, Treasury, stops, or active management.

## By transfer relation

- OPPOSITE_SIDE_REVERSAL_RESET: N=3 proposals=1 accepted=1 settlement=1/1 askAvg=0.620 delayAvg=280.3s $10HoldSum=+6.13
- SAME_SIDE_CONTINUATION_RESET: N=7 proposals=0 accepted=0 settlement=0/0 askAvg=NA delayAvg=NA $10HoldSum=+0.00

## By transfer source

- BOUNDARY_RELEASE: N=7 proposals=1 accepted=1 settlement=1/1 askAvg=0.620 delayAvg=280.3s $10HoldSum=+6.13
- HAND_AUTHORITY_TRANSFER: N=3 proposals=0 accepted=0 settlement=0/0 askAvg=NA delayAvg=NA $10HoldSum=+0.00

## By accepted-proposal delay

- GT90S: N=1 proposals=1 accepted=1 settlement=1/1 askAvg=0.620 delayAvg=280.3s $10HoldSum=+6.13
- NO_ACCEPTED_PROPOSAL: N=9 proposals=0 accepted=0 settlement=0/0 askAvg=NA delayAvg=NA $10HoldSum=+0.00

## By accepted-proposal price

- 55_70C: N=1 proposals=1 accepted=1 settlement=1/1 askAvg=0.620 delayAvg=280.3s $10HoldSum=+6.13
- NO_ACCEPTED_PROPOSAL: N=9 proposals=0 accepted=0 settlement=0/0 askAvg=NA delayAvg=NA $10HoldSum=+0.00

## Government interpretation

- Old opportunity expiration is unchanged.
- Hand/Boundary transfer creates RELEASE_ARMED / a candidate new epoch; it does not itself force an entry.
- The legacy engine remains the proposal generator.
- The router can require a proposal on the transfer side while that transfer epoch is still current.
- The existing value band is audited here as market acceptance, not invented from V5 outcomes.
- A later Hand/Boundary transfer ends the current candidate epoch and starts a new one.
- No V9.5A authority changes.
