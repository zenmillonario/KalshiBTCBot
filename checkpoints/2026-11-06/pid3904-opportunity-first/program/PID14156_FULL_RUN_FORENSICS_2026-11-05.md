# TACHYOS — PID14156 source-bound full-run forensics

**Reviewed:** November 5, 2026, US Eastern Standard Time (UTC−05:00).  
**Scope:** Original recorded Windows **PAPER** session, not an exact engine replay, counterfactual ledger, or live-market outcome. No strategy code was changed in this forensic review. This is the successor run to the verified `PID19616_ENTRY_QUALITY_45M_PAPER` release, not the older PID19616/PID18244 trade ledger.

## 1. Provenance and accounting

- Original run ID: `TOOL_RACK_PAPER_20261106T002757Z_PID14156`.
- Seven numbered uploads reassembled by concatenating **raw `archive_chunk.bin` payloads**, never the outer ZIP containers; each part matches its published SHA-256.
- Fully reconstructed original ZIP: **650,678,961 bytes**, **411 members**; SHA-256 **`5ee2434582df7924a19c507c82df62d098316ab20e74ec1cd5eb8f35b7bab5f4`**. ZIP CRC/integrity check passed.
- **67/67 bundled sealed strategy/source hashes** verified unchanged, including `commander.py` SHA `a48d2f2f4136d3fef288229506dc9882ba719ad6d8e4eef4291a94d6939751b2` and `commander_candidates.py` SHA `6310feef2261a347a9141d66ba2062065cdbb093f59e5fd6e10955b30616e4ab`.
- Recorder: **8,116 attempted / 8,116 written / zero dropped**; `complete=true`, `replay_ready=true`; **actual exact replay NOT performed**.
- Full original PAPER ledger: **$1,000.00 → $948.4650**, gross **−$46.7250**, modeled fees **$4.81**, net **−$51.5350**. Four closed whole-lot positions; **zero unresolved inventory**, `PAPER_ENTRY_WINDOW_COMPLETE_FLAT`. No real venue orders.

| New-run trade | Entry ET → exit ET | Side / modeled fill | Qty | Realized net | Reason |
|---|---|---|---:|---:|---|
| **#1** | 19:34:18 → 19:37:18 | NO $0.270 → $0.180 | 35 | **−$4.01** | Heist parallel return; 180s tactical hold expiration |
| **#2** | 19:38:50 → 19:41:34 | NO $0.160 → $0.030 | 147 | **−$20.80** | Commander fresh Mountain extreme; Lazarus hard adverse structure |
| **#3** | 20:03:24 → 20:10:37 | YES $0.400 → $0.320 | 23 | **−$2.59** | Heist renter; after MAIN promotion, later held-leg terminal exit |
| **#4** | 20:11:38 → 20:14:01 | YES $0.130 → $0.005 | 181 | **−$24.135** | Commander recent-level return; Lazarus hard adverse structure |

### Cross-trade finding

**All four entries were on the opposite side of the *contemporary signed EMA9−EMA30 gap***: #1 and #2 were NO during a positive YES gap; #3 and #4 were YES during a negative NO gap. That does **not** mean every valid Heist renter must align with EMA30; it means this run showed no filled same-gap-side directional entry, while the bot repeatedly accepted cheap counter-arc proposals.

## 2. #1 NO — a six-second twitch was called a Heist return

- Recorded 19:34:18 physical: BTC **$76,188.24**, EMA9 **$76,126.82**, EMA30 **$76,073.54** (gap **+$53.28 / YES**); BTC +$18.66 over 30s and +$40.70 over 60s, while EMA9 was still developing an UP leg.
- Heist `HEIST_PARALLEL_OUTER_EXCURSION_RETURN_CONFIRMED` admitted NO $0.27 after just **BTC −$1.45 and EMA9 −$0.29 over six seconds**, even though the source-bound *nine-second* BTC reading in entry metadata was **+$6.16** and the 30s reading **+$27.19**. On a still-UP 167-second arc, this is insufficient evidence of a parent-scale top.
- It peaked at NO $0.29 but exited $0.18 on `TACTICAL_MAX_HOLD_EXIT`, net −$4.01. A valid genuine Heist upper-edge remains possible in other physical conditions; the regression is **treating a tiny wobble as a proved return**.

## 3. #2 NO — fresh micro extreme mistaken for an earned parent top

- At 19:38:50: BTC **$76,196.01**, EMA9 **$76,168.02**, EMA30 **$76,102.31** (gap **+$65.71 / YES**). The short BTC6/BTC9 movement was negative, but the longer gap/parent remained UP.
- Entry `COMMANDER_EXTENDED_MOUNTAIN_NEW_EXTREME_SUB20_RETURN`: **$25-tier** NO at $0.16; 147 contracts. Source 
  `strategy_core/commander_candidates.py` priority fast-return branch. Its triggering *local* arc age was **12.49 seconds**, with a so-called “fresh extreme” only **2.21 seconds old** and an amplitude **$9.69**. Bundled `full_leg_scale_evidence` and `completed_minute_parent_reference` were **empty dictionaries**. The recorded `mountain.mature_edge` was **false** at that instant.
- The heuristic conflated parent age / availability of some extreme timestamp with actual **parent-scale terminal maturity**. It accepted a weak early counter-UP NO before the remaining parent had exhausted its rise; NO exited at $0.03 for **−$20.80**.
- Preserve the **prior PID18244 #6 NO $0.0877 → $0.35**, where near-upper-level evidence and actual 6s/9s declining physical momentum supported a strong genuine return. Do **not** disable all anticipatory sub-$0.20 Mountain entries.

## 4. 19:50:11 — critical missed lower-edge Heist YES

The 19:45–20:00 contract had **no entries** while the engine often classified MARKET_HEIST. A decisive positive-briefing sequence is visible in the *same-source Commander decisions*:

| Source decision | Current physical condition | Native YES ask | Heist / Commander response |
|---|---|---:|---|
| **seq 4250, 19:50:01** | BTC ~$76,084; sharp DOWN excursion, EMA9 still above EMA30, lower Heist box edge | **$0.11** | Heist **proposed YES ENTER**; Commander `COMMANDER_TACTICAL_FADES_PAUSED`. At this earliest point a confirmation of the bottom was not yet established. |
| **seq 4285, 19:50:11** | BTC **$76,103.35**; BTC6 **+$14.57**, BTC9 **+$11.78**, EMA9 6s **+$2.914**; signed EMA gap **positive YES**, but short Mountain owner still NO | **$0.13** | Heist still **proposed YES ENTER**, qualified box + lower edge; Commander **still paused** it as counter-parent fade. |
| **seq 4329, 19:50:24** | Price pulled back ~$76,087, Heist lower zone still valid, gap still YES | **$0.11** | YES proposed again; same pause. |
| **seq 4345, 19:50:29** | Return accelerated: BTC6 **+$31.54**, BTC9 **+$29.68**, EMA9 6s **+$6.308** | **$0.14** | Price left `LOWER` for `INNER`; Heist opportunity vanished and Commander got `NO_TOOL_INTENT`. |
| **seq 4375, 19:50:37** | EMA9 local arc now UP; BTC ~$76,130 | **$0.15** | No fresh Heist lower-edge entry proposal. |
| **seq 4390, 19:50:41** | BTC ~$76,150, price around Heist `CENTER` | **$0.18** | No Heist entry; Mountain still WAIT. |

**Causal diagnosis:** Heist identified the lower edge and actually proposed YES while the **larger signed EMA9 gap remained YES**. The local Mountain owner was NO because the immediate child arc was falling, and its mission labelled the YES proposal `counter_parent_fade=true`, `neutral_heist_repeatable=false`. The Commander paused it. Once a stronger YES turn appeared, the live box zone became `INNER` and the candidate disappeared. The independent lane was therefore **briefing positively but not receiving usable Commander admission/edge persistence**.

The later native YES ask traded higher (e.g. around $0.40 at 19:52 and $0.50 around 19:53), showing a meaningful recorded quote move in the *same* contract, but **no hypothetical fill, executable whole-lot exit, or profit is claimed**. The useful positive control is **seq 4285: verified lower edge + same-gap-side YES + 6/9-second physical rebound + $0.13 ask**, not the precise realized bottom.

**Candidate repair concept, not implemented:** preserve a brief, bounded *Heist lower-edge echo* through the first earned return, and distinguish a short-lived DOWN child from the larger persistent YES parent. Under the single Commander, this may permit **TACTICAL YES** as a real lower-edge rotation at value; promote to MAIN only if the current EMA9 parent truly becomes and remains YES. Do not bypass current source/quote/depth/runway safety or blindly buy while price is still falling.

## 5. #3 YES — late/expensive against a newly developing DOWN EMA9 sprout, then floor custody problem

- At **20:03:24**, a fresh signed EMA gap was **−$1.39 / NO**; current DOWN EMA9 arc was EXPANDING, BTC was **$32.85 below EMA9**, BTC30 **−$12.47**, BTC60 **−$27.91**, EMA9 30s **−$8.66**. A six-second BTC +$5.82 microbounce was insufficient to establish a new YES parent.
- Nevertheless, Heist allowed `HEIST_OUTER_EDGE_TACTICAL_RENTER` **YES $0.40**, with a $0.40 ceiling in a lower-box zone. This was expensive relative to the later observed lower-edge return prices and did not match the user's desired patient support test.
- The **same contract later** showed native YES asks around **$0.16 at 20:04:56–20:05:00** near a much deeper low (~$76,026), followed by a substantial short-term return. These are historical quotes only, NOT an authorization to buy at the exact low or proof of a missed fill.
- Exit management is a **separate** problem: at approximately **20:05:53**, the TACTICAL YES was promoted into MAIN release custody. Subsequent Commander `HOLD` decisions supplied the runner floor policy **+200% gross initial arming**, despite the original tactical entry policy of **+40% / 3% trail**. Actual executor peak YES bid later recorded **$0.73** against $0.40 entry (**+82.5% gross mark**, no proven hypothetical whole-lot sale), below the runner's +200% arming threshold. Floor remained **unarmed**, and the entire 23-contract lot exited at **$0.32** for **−$2.59 net** at 20:10:37.
- Do not rewrite the recorded loser as a winner. A longer-hold/promoted-lot policy needs to reconcile **retained tactical protection**, truly earned Release custody and prior positive full-lot floor controls. A promotion must not silently erase a previously earned or available protection tier.

## 6. #4 YES — old level-match on an actively developing NO parent, while Heist warned about runway

- At **20:11:38**, BTC **$76,102.23**, EMA9 **$76,164.13**, EMA30 **$76,173.23**, gap **−$9.10 / NO**; BTC 60s **−$49.28**, 9s **−$10.96**, EMA9 60s **−$20.19**. Only BTC6 **+$0.74** and EMA9 6s **+$0.148** hinted at a short pause.
- Commander nevertheless took **181 YES at $0.13**, approximately a $25-tier commitment, using `COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN`. Its cited support reference was **$76,083.12 from 19:50**, **1,298 seconds (21.6 minutes)** earlier, at distance **+$19.11**. This passes the recently introduced generic **$20 minimum proximity** but fails the larger question: did the old level survive newer downward price structure? **A fresher low ~$76,023.74 had formed around 20:05.** An old broken level should not automatically confer defended-support status without new rejection/reclaim proof.
- The code labels the return `rejection_proven=true` because it accepts **any** of several weak cues (including a single `stall`/`hesitation`/`meaningful_retreat`) as an alternative to a sustained short-horizon turn. A durable NO-side 9s/30s/60s physical move was in progress.
- **Cross-lane contradiction in the same source frame (seq 7868):** The Heist lane's YES lower-edge candidate was at `WAIT / HEIST_LATE_DYNAMIC_TP_RUNWAY_BLOCK`, while MAIN Commander *independently* admitted the more expensive/larger YES level-match. An adviser WAIT is not a veto, but the first-class MAIN entry needs its **own positive TP/runway proof** rather than bypassing this physical risk with `runway_veto_authority=false`.
- Recorded exit **$0.005** at 20:14:01, **−$24.135 net**. Fix the entry's positive quality criteria first, without moving the old low or pretending a counterfactual loss was avoidable with certainty.

## 7. Why the bot seemed to trade only fades

The source bundle confirms **all four filled entries opposed the current signed EMA9 gap**, even though the user requested independently evaluating MAIN (with directional flow) and TACTICAL (genuine Heist edge) under ONE Commander.

- The ordinary MAIN `COMMANDER_DIRECTIONAL_PARENT_PULLBACK_REJOIN` path is constrained to established historical-flow provenance, qualifying TP ownership, near-EMA9 value and causal rejoining. It did not emit an eligible positive entry at the 19:50 turn. These quality constraints should be preserved and assessed, not simply removed wholesale.
- The independent TACTICAL Heist **did** identify the 19:50 lower-edge YES but the Commander declined it due to short-parent classification; the edge was not retained into the confirmation/rejoin window.
- Special first-class MAIN Mountain `FRESH_EXTENDED_MOUNTAIN_EXTREME` and `RECENT_LEVEL_MATCH` return paths *did* fire early/late for opposite-side proposals. This produces an **entry-species imbalance**: permissive counter-entry shortcuts with a starved positive directional/Heist edge admission path.
- Source continuity did reset during other parts of the run. **The decisive 19:50 frames were current and on one source connection epoch**, so the missed YES there is not explained away by a stale quote/feed or the archive/export failure.

## 8. Recommended narrowly scoped regression set before any new PAPER release

1. **Positive / PID14156 seq 4285:** lower Heist box, YES signed gap, physically emerging YES return, current quote ≤$0.20; allow the single Commander to *evaluate* a valid tactical candidate without blanket `counter_parent_fade` classification originating solely from the short DOWN child. Check realistic TP/exit runway, not an assumed winning settlement.
2. **Negative / seq 4250:** lower edge but BTC6/EMA9 sharply DOWN at that exact instant; cheap YES alone must not force an entry. Entry may await the next actually observed bounce, while preserving bounded edge memory.
3. **Negative / #1:** counter-UP NO on tiny six-second wobble while 9s and 30s remain UP; require a stronger earned upper rejection. Protect genuine tight repeated Heist rotations from earlier runs.
4. **Negative / #2:** micro 12.5-second arc and 2.2-second fresh extreme cannot masquerade as a fully mature parent top; require actual parent-scale terminal/rejection evidence for the $25 primary Mountain fast return. **Preserve PID18244 #6 NO $0.0877→$0.35 as a positive control.**
5. **Negative / #3 entry:** premium $0.40 lower-edge YES against expanding fresh NO gap before proper lower return; protect earlier genuine YES/NO Heist edge trades. Separately test custody promotion retaining earned whole-lot tactical floors without choking a confirmed Release runner.
6. **Negative / #4:** a 21-minute-old level broken by a newer extreme plus weak 6s pause cannot alone justify a $25 YES return against an expanding NO parent, especially with limited target runway. Preserve the historical close upper-level $25 Mountain winner and first-minute inherited parent controls.
7. **Cross-lane consistency:** HEAD-to-head current-source TP/parent review at seq 7868: Heist late runway WAIT versus MAIN large fresh position. The final Commander must positively establish entry runway; no independent adviser veto is added.
8. **No regression:** prior PID21672 #4 protected whole-lot winner; PID18244 #2/#5 genuine tactical rotations and #6 exceptional upper-edge Mountain; PID17588 strong inherited opening, one Commander, independent MAIN/TACTICAL, EMA9 sovereignty, EMA30 spine only, Lazarus, first-minute discipline, PAPER-only execution and Nautilus Looking Glass.

## 9. Status / audit restrictions

- This report is a **source-bound forensic explanation** with original real-time recorded decisions and quotes. It is **not** an original-engine exact replay or a validated new policy.
- **No strategy source edited, no new Windows run ZIP published** during this forensic intake. A future patch should run recorded source-bound positive and negative tests first, the full isolated historical suite and Constructs second, and only then the entire extracted-package Windows/PAPER/replay and integrity gates. Do not infer hypothetical future performance or substitute a snapshot screenshot for entry authority.
- Machine-readable decisive frames and per-trade ledger details are in `PID14156_SOURCE_BOUND_EVIDENCE_2026-11-05.json`.
