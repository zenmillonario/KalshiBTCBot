# Tachyos R13-H11 — Zero-Entry One-Hour PAPER Forensics

**Read-only audit, prepared October 15, 2026 (UTC) from user-supplied engine and exact-session companion ZIPs.** This is an observation and source-path analysis, **not** a patch, alternative-order simulation, or permission to run live.

## 1. Identity and outcome

- Runtime session: `D20261014_222252_PID30928`, run folder `666_lab_20261014_222250_781739_PID30928`.
- Source build: `V9.5D-666-REASSEMBLED-R13`; R13-H11 PAPER-only; source manifest `source_commit=4c9ea57184ddd087100077115ea04f2a631ae341` is a historical base label, **not** evidence of an H11 Git commit.
- Start ~22:22:52 Eastern Oct 14; stop ~23:22:53 Eastern (60 minutes). `SMOKE_TIME_LIMIT`, `STOPPED`, `checkpoint_health=OK`, no open positions.
- **0 entries / 0 exits / $0.00 realized PAPER gross**, `canonical_trade_events=0`; empty trade ledger (header-only `tachys_paper_trades_v9_2_6.csv`), no `tachys_canonical_trade_events_hf2.csv` because the first recorded trade event never happened.
- All 79 frozen source files match the SHA-256 hashes in the launcher manifest (CRLF/LF normalized where specified). Both uploaded ZIPs pass member CRC. They refer to the same engine audit and reference session.
- The combined archive includes **engine + Observer42 + Navigator**; it does **not** include archived Nautilus UI status/logs. The earlier user's Nautilus screenshot shows the viewer was open, but cannot by itself certify continuous UI coverage.
- Observer42 attached ~22:22:55 ET, finished after the engine with `REFERENCE_SESSION_STOPPED`, account access false, engine writes false. Navigator is source-matched, shadow-only. 13 `EMA30_LONGVIEW_5M` messages were logged by Command.
- HF2 quote health was generally available; end-of-run quote valid. Run statistics include 4,297 accepted decision ticks, 2,241 rejected ticks, 2,848 canonical quote publications, and zero position-safety exits. Rejects may occur for routine quote invalidity; do not disable HF2 quote safety.
- Four completed contracts (22:30, 22:45, 23:00, 23:15 ET) each produced explicit `CONTRACT_NO_ENTRY_LOGGED`. The initial 22:30 contract was joined in progress, and the 23:30 contract remained incomplete at run stop.
- Source output volume was ~1.325 GB/hour on E:, including a 902 MB detailed decision stream. That detailed stream is **not inside the engine audit ZIP**; only its stats were exported. The source snapshot, the 215 MB Command CSV and 115 MB quote provenance compressed stream were exported.

## 2. Decision accounting — distinguish decision rows from unique opportunities

| Item | Observations |
|---|---:|
| `REASSEMBLED_DECISION` rows | 1,172 |
| Final WAIT | 752 |
| Final ARM | 420 |
| Final ENTRY / PAPER fill | **0 / 0** |
| Detailed decisions with complete authority frame | 1,165 |
| Upstream `shadow.decision.stage=ENTRY_ELIGIBLE` | **522** |
| Final WAIT among those 522 | 469 |
| Final ARM among those 522 | 53 |
| `PLAN_CREATED` / `PLAN_ARMED` / `PLAN_READY` | 92 / 92 / 25 |
| `PLAN_READY_REVOKED` | 22 |
| Upstream entry-eligible with candidate ask <=$0.50 | 118 |
| Upstream entry-eligible with candidate ask <=$0.30 | 75 |

Repeated polls of the same physical proposal are **not independent missed trades**. The H11 hard territory review marked 1,122 frames `NOT_ENTRY_ELIGIBLE` (a no-op), and only 35 as directly rejected by that reviewer. Thus the principal block is not simply the new hard-entry review's 35 explicit rejections. Pre-existing physical admission, value, side, PT/time, and safety restrictions still prevent final execution.

Most common final reasons, repeated decision evaluations:

- 242 `FRESH_ENTRY_REMAINING_PAYOFF_BELOW_MEANINGFUL_CAPACITY`: frequently justified when entry is expensive; **keep universal return/payoff economics**.
- 215 `CURRENT_ARC_SLOWDOWN_NEXT_LEG`: early next-leg attention remained ARM.
- 112 `HARD_MECHANICAL_SAFETY`: must be diagnosed with native quote timestamps, **never bypassed**.
- 84 `EARLY_PRESENTATION_OPPOSES_HEALTHY_CURRENT_LEG`.
- 69 `EMA9_PREMIUM_UNRESOLVED_EMA30_CONTACT_WAIT`.
- 65 `OPPOSING_PHYSICAL_CANDIDATE_NOT_YET_QUALIFIED`.
- 50 `HEIST_RELEASE_PRESENTS_TO_MOUNTAIN`.
- 38 `SAME_PHYSICAL_MISSION_FIRST_CAUSAL_PRICE_LOST` and 34 `PHYSICAL_MOTIVE_VALID_BUT_FIRST_CAUSAL_PRICE_LOST`.
- 32 `TIME_PT_MOVEMENT_CAPACITY_INSUFFICIENT_FOR_THIS_CONTRACT`.

These can overlap in causal chains and should not be added together as unique blocked trades.

## 3. Verified territory authority regression

### Quantitative contradiction

The R13 `r13_hard_territory.mode` in the 1,165 complete decisions was:

- **`MARKET_HEIST_ACTIVE`: 884 (75.9%)**
- `MARKET_HEIST_WATCH`: 272 (23.3%)
- `MOUNTAIN_SAME_SIDE_BELOW_EMA30`: **9 (0.8%)**

At the same time, the older original Heist source had `status=RELEASED` in **818** frames, including **722** of R13's 884 `MARKET_HEIST_ACTIVE` frames. All 884 newly active Heist frames had `boundary_source=NATIVE_WIDE_FROZEN_EDGE` (a broad legacy WIDE zone); the new Heist detector's `source_native_box=True` appeared in only **3** of the 1,165 final decisions.

The new Heist's `early_ema_escape_confirmed` was **false on every complete decision**. `RELEASE_PENDING` also appeared on none. In effect, the new Heist remained sovereign throughout market movements that Navigator and the legacy source recognized as expanding and released.

Navigator's independent shadow recap attributes **66.4%** of time to HIGH/LOW Mountain realms, **21.1%** to EMA30 approach, and only **11.3%** to intertwined Heist (plus 1.2% flat). These labels are produced by different algorithms and are not direct ground truth, but this is a strong regime-mismatch control rather than a cosmetic terminology difference.

The R13 hard territorial owner was NO in **1,004** of the 1,165 complete decisions, YES in only 158. Its owner disagreed with the immediate reported `current_leg.side` in **540** samples; such disagreements can be legitimate tactical children, but should not persist without an explicit physical transfer sequence and traceable reason.

### Source-path explanation (read from the actual frozen ZIP)

- `tachys_r13_market_heist.py:163-171`: `native_wide` can independently trigger `sideways_candidate`, even without a new local flat Heist box or sufficient local turning history.
- `tachys_r13_market_heist.py:193-196`: when that happens, the broad WIDE `low/high` becomes the **frozen Heist boundary**.
- `tachys_r13_market_heist.py:228-250,320-323`: an old same-ticker 50%-plus quote excursion can mark the Heist ACTIVE despite a different current arc or absence of a payable current matched edge. This is historical evidence of movement, not necessarily proof that a local box currently owns the battlefield.
- `tachys_r13_market_heist.py:288-302`: the physical release test requires current leg + wall agreement, the **EMA9 already on the corresponding side of EMA30**, healthy extension, departure beyond the frozen broad box, and sufficiently large instantaneous EMA9/EMA30 gap widening. That can delay or prevent retirement of a same-side mountain forming under/over EMA30.
- `tachys_r13_hard_territory.py:343-395`: if new Heist returns an active/verified status it takes over `self.mode`; while its mode starts `MARKET_HEIST_`, the Mountain observer is supplied `heist_active=True` and the Mountain cannot become current territory. This turns the broad Heist latch into a **Mountain admission starvation mechanism**.
- `tachys_reassembled_command_v1.py:912-917`: the final R13 review is a one-way filter; it cannot create an otherwise absent/ARM candidate. Correct principle, but it means merely loosening the R13 review cannot resolve upstream missing entries.

**Priority:** separate *wide historical context* from *genuinely active, locally bounded Heist* and retire Heist promptly on observed EMA9/price expansion even if EMA9 has not yet crossed EMA30. Reconcile MAIN/NEXT/candle physical permission at the single existing Command boundary. Do not add a parallel commander, invent trades, or weaken mandatory safety.

## 4. Causal opportunity anchors from the exact-session Navigator and Command

The following are retrospective **first observed source-valid ask to later source-valid held-side bid** comparisons, within one ticker. They are not simultaneous locked quotes, confirmed lot-sized fills, guaranteed profit or proof the original entry was knowably qualified.

| Approx. Eastern (Oct 14) | Observed physical arc | First eligible ask to later bid | Bid excursion | Contemporary Command problem |
|---|---|---|---:|---|
| 22:39:13–22:40:03 | A00003 DOWN | NO $0.037 → $0.060 | +62.2% | Near first ask, same-side proposal ARM `PRIMARY_OPPOSES_FRESH_PHYSICAL_CANDIDATE`; current R13 mode was Heist ACTIVE although legacy Heist was RELEASED. Absolute payoff and fees still need examination. |
| 22:46:22–22:48:25 | A00005 DOWN | NO $0.39 → $0.71 | +82.1% | Around first ask, final Command presented YES / Heist WATCH, not a qualified NO. Side-handoff timing requires stateful replay. |
| **22:51:04–22:58:10** | **A00008 UP** | **YES $0.32 → $0.998** | **+211.9%** | Nearby YES candidates around $0.32–$0.35 stayed ARM (`CURRENT_ARC_SLOWDOWN_NEXT_LEG` / `NEXT_PLAY_NOT_SUPPORTED_BY_CURRENT_LEG`), while R13 remained Heist ACTIVE with legacy Heist RELEASED. Major positive opportunity-control, not automatic permission at the retrospective low. |
| 23:07:20–23:07:55 | A00010 UP | YES $0.047 → $0.13 | +176.6% | At initial quote, Command WAIT `EARLY_PRESENTATION_OPPOSES_HEALTHY_CURRENT_LEG` under lingering NO owner; further processing included mandatory quote-safety WAIT. |
| 23:15:40–23:17:05 | A00012 UP | YES $0.38 → $0.64 | +68.4% | New contract in first-minute price discovery. A valid first-minute inherited breakout exception would require additional then-known evidence; do not retroactively force an entry. |

Also present but normally **above** the regular $0.50 entry ceiling: A00002 YES $0.54→$0.98 (+81.5%) and A00009 NO $0.57→$0.961 (+68.6%). Both would need the exceptional verified breakout/drop rule to qualify as actual purchases. An opportunity in a quote table does not prove that exception.

Navigator found **11 completed arcs**, four cross-contract; median observed arc-specific executable bid excursion **68.6%**, based on its qualifying sample, not a generalized predictive success rate.

## 5. Additional module evidence

- EMA30 Long-View five-minute reporter: 13 published measurements, showing the reporting layer operated. Its performance as a predictor cannot be judged from zero positions.
- Early Dragon opposite return-test: 19 source samples marked physically qualified, **zero** actual paid test; late third-arc test qualified **zero** original decision frames (26 WATCH, 17 ABSTAIN). Inspect missing branch eligibility and naturally absent setups separately.
- H11 two-candle preservation: 29 observations with action `PRESERVE_LEG_THROUGH_TWO_CANDLES`, but zero live positions, so its exit-protection effect remains untested.
- Leg clock: 771 samples reported prior reference timing available and 394 lacked reliable two-arc timing. Its maturity model requires temporal validation across continuous arc generations.
- No 150%-winner harvest, hard-profit-floor, settlement position management, or same-side twin lifecycle can be judged from this zero-trade run. Twin booking remains disabled by design.
- H11 `at least one entry per contract` was an **objective**, not a mandate to force purchases. All four completed contracts missed it. Preserve the prohibition on unsafe/uneconomic forced entries, while urgently repairing legitimate edge admissions.

## 6. Recommended controlled repair & acceptance, before another hour

1. **Heist retirement and territory identity (P0).** Reproduce the original source timeline around A00005/A00008/A00009 using as-of candles, EMA9+EMA30, source Heist BOXED/RELEASED and R13 frozen edges. Local Heist should not dominate an expanding Mountain solely because a prior WIDE band or old 50%-quote markout existed. Verify same-side Mountain formation **before** EMA9 crosses EMA30.
2. **Continuous parent/current-leg reconciliation (P0).** At each significant arc, distinguish broad inherited parent, genuinely current EMA9 physical mountain, and permissible independent tactical child. Demonstrate succession without unilateral Future/WIDE promotion or stale old-parent veto. Include 22:46 NO and 22:51 YES candidate sequences.
3. **Single admission chronology (P0).** Re-run actual PAPER Command and position inventory on a continuous native quote/book stream; preserve HF2 source/receive age, 35% minimum capacity, $0.50 usual price ceiling, $0.50–$0.70 exceptional requirement, no cheapness-as-motive, and confirmed Heist *edge*, not middle. Verify valid as-of bargain admissions rather than manually forcing historical winners.
4. **Predeclared positive and negative controls.** Compare 22:51 YES continuation and 23:07 YES counterleg against similarly cheap false-turn frames. Do not fit thresholds on the subsequently observed $0.998 or $0.13 bid. Test third-arc two-previous-shape and before/after rollover as-of behavior.
5. **Safety / lifecycle (P0).** Retain one-engine startup and 79-source identity pins, strict HF2 native quote safety and hard executable-bid stop. Verify a real first entry can create the canonical ledger and Nautilus reconciles it; test end-of-hour archiving with open inventory and exact sidecar references.
6. **First corrected release test:** run a short continuous candidate-owned offline replay against the original hour until the selected physically qualified entries and major false-positive negatives behave as expected. **Only then** promote a new supervised one-hour PAPER pilot. Do not treat unit-test counts as profitability validation.

**Conclusion:** operational endurance passed; entry participation failed. The central source-backed fault is overpersistent Heist ownership from broad WIDE and strong retirement constraints, compounded by upstream ARM/wait gates. Removing the profit-capacity, opening-discovery, stale-quote or hard-floor rules would be a dangerous and unjustified response.

### Evidence included/omitted

Original supplied archives: `666_lab_20261014_222250_781739_PID30928_audit_20261015T032322Z_518a3dd4.zip` and `666_lab_20261014_222250_781739_PID30928_R13_ALL_COMPONENTS_20261015T032421Z_58fff9eb.zip`. They have engine frozen source and canonical trade/quote/decision CSVs, source fingerprints, Observer42 original reports and Navigator War Tour. The detailed 902 MB decision snapshot stream and continuous Nautilus viewer export are **not** inside these ZIPs. All unobserved or not-lot-validated fills remain **unknown**, not profits.