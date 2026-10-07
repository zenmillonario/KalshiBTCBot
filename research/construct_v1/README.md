# Tachys Construct V1 — Neo Dojo

Status: **OFFLINE / SHADOW ONLY. ZERO TRADING AUTHORITY.**

Construct V1 turns frozen Tachys run archives into causal replay lessons.

Core loop:
1. BUILD a historical run into episodes cut at time T.
2. QUIZ Tachys/human using only information available at or before T.
3. Reveal hidden 30s/60s/180s + settlement outcomes.
4. SCORE side/timing decisions.
5. Repeat across archived battles.

The release package also contains a Windows helper that accepts an engine archive ZIP and builds the dojo dataset without starting any live process.

## Causality
Features are last-known-at-or-before the episode cutoff. Future observations live only in the hidden answer key / full forensic dataset. A leakage audit rejects quiz files containing future/label/answer/settlement/outcome fields.

## V1 validated on HF13
- 1,264 cadence episodes at 15-second spacing
- 255 EMA-convergence cases
- 582 crest decisions
- 392 leg-handoff cases
- 651 WIDE/compression cases
- 227 settlement-cushion cases
- 29/29 actual HF13 entries reproduced in entry-centered mode
- leakage audit PASS
- unit tests 5/5 PASS

## Philosophy
- One Command, many senses.
- Win the leg, not just the wiggle.
- Lazarus can rescue a mistake; it cannot certify the mistake as a good entry.
- Play how high it can get, not how high it can stay.

The downloadable V1 package SHA-256 is documented in RELEASE_V1.md.
