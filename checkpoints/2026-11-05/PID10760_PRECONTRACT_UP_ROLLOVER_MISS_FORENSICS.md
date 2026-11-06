# TACHYOS — PID10760 verified pre-contract UP leg miss, November 5, 2026

**Forensic note only; no changed strategy, PAPER release, or original-engine replay.** Preserve frozen one Commander, independent MAIN/TACTICAL, native EMA9 parent authority, EMA30 spine-only, existing whole-lot protection, custody/risk, and Nautilus.

## Recording / release provenance
- Run: `TOOL_RACK_PAPER_20261106T024325Z_PID10760`, from verified `TACHYOS_PID14156_HEIST_HANDOFF_PATIENT_MOUNTAIN_45M_PAPER_20261105`; `commander.py` SHA `476d5b8682c5ab2946dbea617ba7495521ff7f6f0e0d62ede21c6cb35c42151d`, `commander_candidates.py` SHA `2c09ab892d9aead4d53c07f60cdbea97c09f8b27bf1c8359eeadd040a99252ca`.
- All seven raw numbered parts individually SHA-256 verified; exact 601,531,000-byte source archive SHA-256 `f676cdc8b44688f92382972c489dbb2eb745096ab1f8a6216493e7b00a61a0ff`, 399 ZIP members, CRC PASS, **67/67** sealed source hashes PASS.
- Capture 7,607/7,607, zero dropped, ready for replay but exact replay **NOT performed**. Three whole-lot trades, cash $1,000→$984.33, net **−$15.67 PAPER**, fees $4.01. No live orders, no counterfactual profits.
- Detailed companion conversation report `PID10760_PRECONTRACT_UP_AND_THREE_TRADES_FORENSICS.md` SHA-256 `235ab31f67300c4fd0a83436a24ea30dbeccfe148fab8496472035ce4cf5c353`; source-bound extracted evidence `PID10760_SOURCE_BOUND_FORENSIC_EVIDENCE.json` SHA `b5e025b4052dcf1a20c846fd4eaf1bdc7a1ffc4bec4c3409359f48974ebc27e8`.

## Verified additional user observation — missed UP leg before trade #1
- User spotted UP movement beginning **before 21:45 rollover**; BTC directional rise observable in run from late 21:44, although the system started observing 21:43:28 and had **not** physically established an inherited native EMA9 UP parent at 21:45. Do not invent earlier parent history.
- 21:45:00–21:45:17 ET: **six** discovery polls `NO_CURRENT_OPEN_KXBTC15M_MARKET`. New `KXBTC15M-26NOV052200-00` discovered **21:45:20.531** (+20.5s); rollover recorded at 21:45:20.669. First new ticker YES ask $0.49 at ~21:45:21.
- **21:45:30:** YES ask $0.53, BTC60 +$25.22, EMA9_60 +$5.41, TP YES `STARTING_LEG_FAVORED`, but actual native parent `NONE`. Current EMA9 UP child arc age ~15.6s vs contract age ~30s. **21:45:45:** YES ask $0.56, BTC60 +$49.93, EMA9_60 +$10.36, parent NONE. **21:46:00:** BTC60 +$58.54, EMA9_60 +$12.08, YES ask ~$0.61. **21:46:27:** native parent finally UP, YES ask ~$0.62.
- No positive MAIN YES continuation candidate was proposed in the early new contract. Repeated candidate reason: `MOUNTAIN_EDGE_ONLY_NO_MIDLEG_ALIGNED_ENTRY`. Existing `commander_candidates.py` opening exception requires historical-flow qualification, TP concurrence, <=$0.55 quote and `opening_arc_age > contract_age + 1`; recorded child-arc age was *younger* than contract after rollover, even though BTC price had risen into the new contract. This is an **inherited-parent ancestry / newborn child-arc / delayed market discovery / positive candidate-admission** deficit, not blanket first-minute permission.
- 21:49:45 #1 NO $.18 purchased while BTC60 **+$64.10**, EMA9 gap **+$42.01**, parent UP and YES ask ~$0.83. Original first-class Commander reason `COMMANDER_RECENT_LEVEL_MATCH_SUB20_RETURN`. NO exited $.14 at 21:53:57 for **−$7.71** via `COMMANDER_EXIT_PRIMARY_OPPOSES_LIVING_EMA9_PARENT`. Avoid cheap fades on living UP parent without true rejection, but preserve prior PID18244 #6 positive upper-extreme NO winner.

## Other original trades and follow-up
- #2 22:01:09 **TACTICAL NO $.35** upper Heist edge, parent UP / gap +$24.28, BTC30 +$75.18. Closed **22:04:10, $.29, −$2.44**, exactly `TACTICAL_MAX_HOLD_EXIT` ~181s with still-UP parent. Same ticker later showed NO top bids **$0.78 at 22:12** and **$0.999 near 22:14**, available top-of-book quantities above 27; a real later opportunity, NOT an alternative executed fill. Plan independently earned TACTICAL→MAIN handoff or re-entry after physical DOWN transfer, not unconditional longer hold.
- #3 22:20:57 **PRIMARY YES $.31** during native DOWN parent / EMA9 gap **−$63.55**, 9s BTC −$10.91, current DOWN child arc ~14 seconds old. `COMMANDER_MOUNTAIN_BOUNCE_OWNS_CONTRACT` admitted because TP said `BOUNCE_FAVORED YES`, though required move to target **$66.11** exceeded comparable parent amplitude **$37.04**, with target in EMA junction. Sold 22:22:45 at $.15, **−$5.52**, `LAZARUS_HARD_ADVERSE_STRUCTURE`. Need source-bound false-bounce/target-feasibility negative control, preserving physically earned parent-scale bottoms.

## Recommended order for next authorized engineering change
1. Positive **inherited UP across rollover** scenario with causal parent ancestry across local child reset; ask and first-minute caps intact; retain PID15740 strong continuation positive + cold/unproven/stale negatives.
2. Validate market discovery +20.5s open delay separately from strategy authority.
3. Protect true mature extreme #6 and dynamic TACTICAL winner floors; prevent #1 false top and #3 wrong-parent false bounce.
4. Evaluate later #2 transition to DOWN release for valid re-entry/handoff; retain 180s exit as safety when no parent transfer is presently earned.
5. Before next 45m Windows PAPER ZIP: selected source negative/positive regressions, complete extracted test/historical Construct gate, capture, Looking Glass JS, synthetic recorder/replay, manifest/source hashes, independent audit. No hindsight ledger.

**Nothing here certifies a new strategy or a repaired run.**
