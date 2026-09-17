# V9.2.5 LONG-RUN + MULTI-TIMEFRAME OBSERVER: pass current YES/NO asks into print_signal so the V9.2 structural entry gate cannot raise NameError.
# Tachys V9 EXPIRY OBSERVER - V8.8 trading preserved + high-resolution final-90s research
# PAPER ONLY. V9 adds observer telemetry only; it does NOT add live orders or change V8.8 entries/exits.
# PAPER ONLY. BTC structure remains continuous across 15-minute Kalshi contracts.
import os
import time
import base64
import asyncio
import json
import csv
import re
import traceback
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
import websockets
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

API_KEY_ID = os.getenv("KALSHI_API_KEY_ID")
PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH")

API_BASE = "https://external-api.kalshi.com/trade-api/v2"
REST_URL = f"{API_BASE}/markets"
WS_URL = "wss://external-api-ws.kalshi.com/trade-api/ws/v2"

SERIES = "KXBTC15M"

# Two paper-entry grades. CONFIRMED preserves the V3 rules exactly.
EARLY_ENTRY_ASK = 0.40
CONFIRMED_ENTRY_ASK = 0.50
MAX_ENTRY_ASK = 0.80

EARLY_MOM_90_75 = 0.01
EARLY_MOM_90_60 = 0.03
CONFIRMED_MOM_90_75 = 0.02
CONFIRMED_MOM_90_60 = 0.05

HISTORY_SECONDS = 300
RECONNECT_DELAY = 1
REST_POLL_SECONDS = 1.0
WS_RECV_TIMEOUT = 0.50
STATUS_SECONDS = 15

# New schema because signals now include YES/NO side.
LOG_FILE = "tachys_signals_v9_2_5.csv"
RESULT_LOG_FILE = "tachys_contract_results_v9_2_5.csv"
REVERSAL_LOG_FILE = "tachys_reversal_watch_v9_2_5.csv"
PAPER_LOG_FILE = "tachys_paper_trades_v9_2_5.csv"

# Paper money-management experiment. Fixed maximum stake per entry.
PAPER_STAKE = 10.00
A_PLUS_PAPER_STAKE = 15.00

# V7.1 experimental CHOP SNIPER regime (paper only).
# The sniper uses a larger paper allocation because it is intentionally
# selective: one position at a time, only near a measured chop edge.
CHOP_SNIPER_STAKE = 15.00
CHOP_SNIPER_TP_ROI = 0.35
CHOP_SNIPER_COOLDOWN = 45
CHOP_EFFICIENCY_MAX = 0.35
CHOP_MIN_RANGE_60S = 20.0
CHOP_MIN_RANGE_180S = 35.0
CHOP_EDGE_FRACTION = 0.25
CHOP_REJECTION_MOVE_10S = 2.0
CHOP_SNIPER_MIN_SECONDS_LEFT = 180
CHOP_BREAKOUT_EFFICIENCY = 0.60
CHOP_BREAKOUT_BUFFER_FRACTION = 0.15
CHOP_BREAKOUT_MIN_MOVE_30S = 15.0
CHOP_SNIPER_EMERGENCY_STOP = 0.75
CHOP_SNIPER_LATE_EXIT_SECONDS = 90

# V7.3: actual market structure matters. Low efficiency alone is not chop.
STRUCTURE_LOOKBACK_SECONDS = 180
STRUCTURE_BUCKET_SECONDS = 30
STRUCTURE_MIN_STEP = 3.0
CHOP_MIN_DIRECTION_FLIPS = 2

# Late + far from target was a destructive combination in V7.2.
LATE_DISTANCE_FILTER_SECONDS = 300
LATE_MAX_TARGET_DISTANCE_ABS = 50.0
VERY_LATE_DISTANCE_FILTER_SECONDS = 180
VERY_LATE_MAX_TARGET_DISTANCE_ABS = 30.0

# V7.4 Sniper quality gate: don't call a far-away directional move a chop edge.
# Permit when target distance is within either a fixed $60 cushion or 1.5x the
# recent 60-second BTC range (whichever is more permissive).
SNIPER_MAX_TARGET_DISTANCE_ABS = 60.0
SNIPER_MAX_RANGE_MULTIPLE = 1.50

# V7.4 time-sensitive profit ladder.
TP_NORMAL_SECONDS_LEFT = 300      # >5m
TP_MID_SECONDS_LEFT = 180         # 3-5m
CORE_SIDEWAYS_TP_MID_ROI = 0.30
LATE_PROFIT_TP_ROI = 0.225        # <3m: bank around +22.5%

# Trades that have already shown +20% get recovery room while >5m remain.
PROVEN_RECOVERY_MIN_SECONDS_LEFT = 300

# V7 contract phases. A 15-minute contract starts with a HARD 2-minute
# observation window. From minute 2 to minute 4, only stronger A/A+ signals
# may enter; weaker EARLY/CONFIRMED grades are logged but blocked. Trades
# entered from minute 2 through minute 10 bank +50% immediately so profit can
# be recycled into a fresh setup later in the same contract.
OBSERVATION_SECONDS = 120          # first 2:00: data gathering only
STRONG_ONLY_WINDOW_SECONDS = 240   # 2:00-4:00: A/A+ entries only
EARLY_PROFIT_WINDOW_SECONDS = 600  # entries from 2:00-10:00 use +50% take-profit
EXPIRY_MODE_SECONDS = 60           # final 1:00
EARLY_TAKE_PROFIT_ROI = 0.50       # bank +50% on early trades
EARLY_MIN_BTC_NET_MOVE_60S = 30.0
EARLY_MIN_TREND_EFFICIENCY = 0.55
EARLY_MIN_MOM_90_75 = 0.03
EARLY_MIN_MOM_90_60 = 0.06
# V5: the old fixed -20% stop is no longer the primary exit.
# Early in the contract, give the thesis room. Late in the contract,
# time + target relationship matter more. A deep emergency stop remains
# only as a paper-risk guardrail while we collect data.
EMERGENCY_STOP_LOSS = 0.60
LATE_RISK_WINDOW_SECONDS = 300
LATE_TARGET_STOP_ROI = -0.20
TRAIL_ACTIVATE_ROI = 0.40       # start trailing after +40%
TRAIL_GIVEBACK_ROI = 0.20       # exit after 20 percentage-point giveback from peak

# V7.2: extend chop-style management into CORE when the BTC path is
# sideways / approaching chop. These are paper-only experimental rules.
CORE_SIDEWAYS_EFF_MAX = 0.55
CORE_SIDEWAYS_TP_ROI = 0.35
CORE_SIDEWAYS_TP_MIN_SECONDS_LEFT = 300   # use quick +35% bank while >5m remains
EARLY_RECOVERY_SECONDS_LEFT = 600         # >10m left = give a bad early trade more time
EARLY_CORE_EMERGENCY_STOP = 0.80          # general early paper guardrail
EARLY_SIDEWAYS_EMERGENCY_STOP = 0.85      # extra room in sideways/chop-like structure
PAPER_REENTRY_COOLDOWN = 20
PROFIT_MILESTONES = (0.20, 0.30, 0.40, 0.50, 0.60, 0.75, 0.90, 1.00)

# V7.7 promoted paper intelligence ------------------------------------------
# Protect trades that already proved themselves instead of allowing +30% MFE
# to decay into the old -60% emergency stop. Protection only activates when
# current local/EMA evidence says the original thesis is weakening.
PROVEN_MFE_PROTECT = 0.30
PROVEN_MFE_GIVEBACK = 0.22
PROVEN_MFE_MIN_FLOOR = 0.08
THESIS_INVALIDATION_MAX_ROI = 0.00

# V7.9 EMA9 ARC INTEGRATION -------------------------------------------------
# Short-run experiment: existing Core signal still discovers the opportunity,
# but EMA9 shape now gates ordinary Core entries and helps decide whether a
# Core thesis is truly broken. Chop Sniper remains ACTIVE for this test.
EMA9_ARC_ENTRY_GATE = True
EMA9_ARC_EXIT_MANAGEMENT = True
EMA9_ARC_RUNNER_OVERRIDE = True
EMA9_ARC_MIN_SLOPE = 2.0
EMA9_ARC_CURVATURE_TURN = 1.5
EMA9_ARC_COIL_GAP_RANGE_FRAC = 0.18
EMA9_ARC_EXTENDED_GAP_RANGE_FRAC = 0.70
EMA9_ARC_EXTENDED_PRICE_RANGE_FRAC = 0.85
EMA9_ARC_RUNNER_MIN_CUSHION60 = 1.00
EMA9_ARC_RUNNER_MIN_SECONDS_LEFT = 120
EMA9_ARC_HARD_EXPIRY_SECONDS = 90
EMA9_ARC_BREAK_CONFIRM_SECONDS = 9   # 3-6-9 persistence: do not exit on a one-tick arc wobble
EMA9_ARC_ROLL_MIN_CURVATURE = 1.5  # rolling old arc may arm the opposite side before EMA9/30 cross
CHOP_ARC_AWARE_DIRECTION = True

# V8.1 mid-run: anticipate -> fast-fail -> confirm -> ride.
ANTICIPATION_FAST_FAIL_SECONDS = 18
ANTICIPATION_FAIL_ROI = -0.08
ANTICIPATION_CONFIRM_ROI = 0.10
ANTICIPATION_CONFIRM_SECONDS = 18
LATE_ARC_PULLBACK_WAIT_RANGE_FRAC = 0.55
OPPOSITE_EDGE_BLOCK_SCORE = 86
OPPOSITE_EDGE_BLOCK_EXHAUSTION_MIN = 30
PROVEN_TARGET_CUSHION_DOLLARS = 150.0
PROVEN_TARGET_CUSHION_SECONDS = 180
PROVEN_TARGET_CUSHION_MAX_SECONDS = 420
PROVEN_CUSHION_BREAK_CONFIRM_SECONDS = 18
REENTRY_CHURN_COOLDOWN = 18

# V8.5 thesis continuity / time-aware patience.
EARLY_FLEX_SECONDS_LEFT = 720      # 12-15m: structurally valid ideas get maximum room
MID_FLEX_SECONDS_LEFT = 540        # 9-12m: still patient
EARLY_ARC_BREAK_CONFIRM_SECONDS = 54
MID_ARC_BREAK_CONFIRM_SECONDS = 36
NORMAL_ARC_BREAK_CONFIRM_SECONDS = 18
STRUCTURAL_FAST_FAIL_MOMENTUM = 20.0
THESIS_CONSISTENCY_GRACE_SECONDS = 36
REJECTION_LOOKBACK_MINUTES = 36
REJECTION_NEAR30_RANGE_FRAC = 0.38
REJECTION_MIN_CURVATURE = 0.8
WEAK_REJECTION_RATIO = 0.72

# V8.5 overnight: continuous-market early access, parent authority, swirl discipline,
# and SNIP->RIDE management. Paper trading only.
V84_EARLY_ACCESS_WINDOW_SECONDS = 180
V84_EARLY_ACCESS_MIN_THESIS_SCORE = 4
V84_COUNTERTREND_EXTENSION_SCORE = 78
V84_COUNTERTREND_EXHAUSTION_SCORE = 45
V84_COUNTERTREND_MIN_369_MOVE = 9.0
V84_SWIRL_GAP_RANGE_FRAC = 0.32
V84_SWIRL_EFFICIENCY_MAX = 0.48
V84_SWIRL_SNIP_TP = 0.225
V84_SWIRL_LOCK_MFE = 0.20
V84_SWIRL_GIVEBACK = 0.10
V84_SWIRL_MIN_FLOOR = 0.10
V84_POST_FAIL_SWIRL_COOLDOWN = 54
V84_STRONG_PARENT_SCORE = 4
V84_FLASH_LOG_ONLY = True

# V8.5 forensic-driven controls
V85_PARENT_VETO_DIFF = 4
V85_COUNTERTREND_REENTRY_LOCK_SECONDS = 54
V85_COUNTERTREND_STRONG_EXHAUSTION = 55
V85_STRUCTURAL_STOP_ROI = -0.25
V85_STRUCTURAL_STOP_MIN_AGE = 18
V85_FLASH_MIN_TARGET_DISTANCE = 12.0
V85_FLASH_MIN_369_ACCEL = 9.0
V85_FLASH_LOG_INTERVAL = 1.0

# V8.6 surgical changes -------------------------------------------------------
# 1) Retire the old Chop Sniper from paper P&L. Chop telemetry remains live,
#    but Core is no longer blocked and no Chop Sniper paper order is opened.
CHOP_SNIPER_PAPER_ENABLED = False

# 2) EMA9 arc break must show actual deterioration, not just a label wobble.
V86_ARC_BREAK_MIN_EVIDENCE = 3
V86_ARC_BREAK_MIN_SLOPE = 2.0
V86_ARC_BREAK_MIN_CURVATURE = 1.5

# 3) Bird-in-hand protection. Reaching 17/20/23% does NOT force an immediate
#    exit; it raises a ratcheting floor so a good repricing wave is not donated.
BIRD_17_TRIGGER = 0.17
BIRD_17_FLOOR = 0.10
BIRD_20_TRIGGER = 0.20
BIRD_20_FLOOR = 0.12
BIRD_23_TRIGGER = 0.23
BIRD_23_FLOOR = 0.15
FLASH_LOG_FILE = "tachys_flash_v9_2_5.csv"

# V8.7 continuous-contract handoff.
ROLLOVER_WATCH_SECONDS = 90
ROLLOVER_STATE_TTL_SECONDS = 150
ROLLOVER_HANDOFF_ENTRY_WINDOW = 60
ROLLOVER_MIN_SCORE = 4
ROLLOVER_MAX_ASK = 0.80
ROLLOVER_MIN_ASK = 0.30
ROLLOVER_NEW_TARGET_RANGE_FRAC = 0.50
rollover_handoff_state = {"side": None, "score": 0, "ts": 0.0, "why": ""}
rollover_handoff_used_ticker = None

# V8.8 anticipation / anti-chase / fresh-reentry controls ----------------------
# Countertrend pullbacks are allowed BEFORE a full EMA9/30 cross when a mature
# move is stretched and EMA9 curvature/momentum begins to deteriorate.
V88_EXHAUSTION_PULLBACK_MIN_EXTENSION = 68
V88_EXHAUSTION_PULLBACK_MIN_EXHAUSTION = 28
V88_EXHAUSTION_PULLBACK_MIN_CURVATURE = 0.8
V88_EXHAUSTION_PULLBACK_MIN_TARGET_CUSHION = 12.0

# If Tachys saw a cheaper blocked candidate, do not chase it materially higher
# unless the structural evidence has improved.
V88_BLOCK_MEMORY_TTL = 180
V88_MAX_CHASE_CENTS = 0.06
V88_CHASE_STRONGER_EVIDENCE_DELTA = 3

# After a losing same-side trade, demand a genuinely new structural event,
# materially stronger thesis, or a better price before re-entry.
V88_SAME_SIDE_REENTRY_LOCK = 54
V88_REENTRY_BETTER_PRICE_CENTS = 0.05
V88_REENTRY_SCORE_DELTA = 2

v88_blocked_candidate = {}   # (ticker, side) -> {ask, ts, thesis_score, setup}
v88_last_loss = {"YES": None, "NO": None}

# V9 EXPIRY RESEARCH LAYER ----------------------------------------------------
# OBSERVER ONLY: captures the last 90 seconds at sub-second resolution so we
# can study Stability, target Flips / BTC->Kalshi lag, and False Breaks without
# changing any V8.8 paper-trading decision.
EXPIRY_OBSERVER_WINDOW = 90.0
EXPIRY_SNAPSHOT_INTERVAL = 0.50
EXPIRY_EVENT_HORIZONS = (1, 3, 6, 9, 15, 30)
EXPIRY_STABILITY_MIN_HOLD = 15.0
EXPIRY_STABILITY_COOLDOWN = 9.0
EXPIRY_FLIP_EVENT_COOLDOWN = 0.75
EXPIRY_FAKEOUT_WINDOW = 30.0
EXPIRY_SNAPSHOT_LOG_FILE = "tachys_expiry_snapshots_v9_2_5.csv"
EXPIRY_EVENT_LOG_FILE = "tachys_expiry_events_v9_2_5.csv"

expiry_observer_state = {}  # ticker -> rolling target/crossing state
expiry_active_events = []   # finalized after 1/3/6/9/15/30s samples
expiry_event_counter = 0

# V9.2 STRUCTURAL MANAGER -------------------------------------------------
# V9.1 perception is now allowed to influence PAPER MANAGEMENT. The legacy
# percentages remain as alarms, not unconditional exits.
V92_MANAGER_ENABLED = True
V92_PROTECT_MFE = 0.17
V92_PROTECT_GIVEBACK_STRONG = 0.24   # strong structure gets room
V92_PROTECT_GIVEBACK_HOLD = 0.18
V92_PROTECT_GIVEBACK_WEAK = 0.10
V92_TARGET_ACCEPT_REQUIRED = True
V92_SQUEEZE_MIN_MFE = 0.20
V92_SQUEEZE_MIN_SECONDS = 75
V92_SQUEEZE_MIN_SCORE = 6
V92_STRUCTURAL_EXIT_MIN_AGE = 12

# V9.2.2 entry shock/chase guard ------------------------------------------------
# A structural thesis may be correct while the immediate entry is terrible.
# If Kalshi has already repriced sharply in our favor AND BTC is now snapping
# back against that side on the 6/9-second tape, wait for a fresh test instead
# of paying the local extreme.
V922_SHOCK_LOOKBACK_SECONDS = 15
V922_SHOCK_ASK_JUMP = 0.09
V922_MIN_COMPLETED_SIDE_MOVE_30S = 9.0
V922_MIN_COUNTER_SNAP_6S = 4.0
V922_MIN_COUNTER_SNAP_9S = 4.0

# V9.2.3 same-contract directional mutex / controlled flip.
# Tachys may hold only ONE directional side of a given 15-minute contract.
# An opposite signal becomes a FLIP_CANDIDATE; the existing position must
# close first, then the new side must survive a short confirmation delay.
V923_FLIP_CONFIRM_SECONDS = 6.0
V923_FLIP_CANDIDATE_TTL = 60.0

# V9.2.3 proven-winner hard floor.
# Structure still controls how far winners may run, but once a trade has
# demonstrated meaningful edge it is no longer allowed to become a large loser.
# These are emergency floors, not take-profit targets.
V923_PROVEN_20_FLOOR = 0.00
V923_PROVEN_30_FLOOR = 0.05
V923_PROVEN_50_FLOOR = 0.15

# V9.2.4 adaptive proven-trade manager.
# A healthy SQUEEZE keeps the wide leash.  Protection tightens only when
# BTC structure deteriorates, so strong runners such as V9.2.3 trade #18
# are not clipped merely because they reached a profit milestone.
V924_PROVEN_ARM_MFE = 0.17
V924_WEAK_GIVEBACK = 0.09
V924_INVALIDATE_GIVEBACK = 0.06
V924_COLLAPSE_GIVEBACK = 0.07
V924_MIN_LOCK_17 = 0.04
V924_MIN_LOCK_20 = 0.07
V924_MIN_LOCK_30 = 0.12
V924_MIN_LOCK_50 = 0.20
V924_PROTECT_CONFIRM_SECONDS = 1.5

# V9.1 STRUCTURAL PERCEPTION / LEGACY AUDIT -------------------------------
# OBSERVER FIRST. These measurements do not place, resize, or cancel paper
# positions. They describe the market in the same sequence-oriented language
# used during manual chart review, then audit legacy entries/exits against it.
V91_PERCEPTION_LOG_FILE = "tachys_structural_perception_v9_2_5.csv"
V91_EVENT_LOG_FILE = "tachys_structural_events_v9_2_5.csv"
V91_AUDIT_LOG_FILE = "tachys_legacy_audit_v9_2_5.csv"
V91_SAMPLE_INTERVAL = 1.0
V91_EVENT_HORIZONS = (3, 6, 9, 15, 30, 60, 90)
V91_EVENT_COOLDOWN = 6.0
V91_FAKEOUT_MAX_AGE = 30.0
V91_ACCEPT_MIN_HOLD = 9.0
V91_TARGET_CLUSTER_DOLLARS = 6.0
V91_EMA_CLUSTER_DOLLARS = 4.0
V91_GAP_COLLAPSE_MIN = 0.35
V91_PULLBACK_EMA30_BUFFER_FRAC = 0.20
V91_PULLBACK_MAX_STRIDE_FRAC = 0.65

v91_history = []
v91_last_sample_ts = 0.0
v91_event_counter = 0
v91_active_events = []
v91_last_event_ts = {}
v91_interaction_state = {}

# Runtime memory for failed countertrend attempts and FLASH observer.
v85_last_failed_countertrend = {"YES": 0.0, "NO": 0.0}
v85_last_flash_log_ts = 0.0


# Early Impulse Core: small paper-only experiment. This may bypass the hard
# 2-minute observation gate after 30 seconds when BTC displacement is unusually
# coherent. It does NOT use A+ sizing.
EARLY_IMPULSE_MIN_ELAPSED = 30
EARLY_IMPULSE_MAX_ELAPSED = 120
EARLY_IMPULSE_STAKE = 10.00
EARLY_IMPULSE_MIN_SCORE = 4
EARLY_IMPULSE_MIN_MOVE_30S = 35.0
EARLY_IMPULSE_MIN_EFF30 = 0.72
EARLY_IMPULSE_MIN_ASK = 0.30
EARLY_IMPULSE_MAX_ASK = 0.80
EARLY_IMPULSE_COOLDOWN = 36
ET = ZoneInfo("America/New_York")

BTC_WS_URL = "wss://advanced-trade-ws.coinbase.com"
BTC_PRODUCT = "BTC-USD"
BTC_CANDLES_URL = f"https://api.exchange.coinbase.com/products/{BTC_PRODUCT}/candles"

# V9.2.5 multi-timeframe context — OBSERVER ONLY.
# 5m ~= recent-day context; 30m ~= roughly six-day / "5-day chart" context.
# This layer logs regime and EMA geometry but does NOT alter entries/exits.
MTF_LOG_FILE = "tachys_multitimeframe_v9_2_5.csv"
MTF_REFRESH_SECONDS = 60
MTF_PRINT_SECONDS = 300
MTF_5M_GRANULARITY = 300
MTF_30M_GRANULARITY = 1800
mtf_last_print_ts = 0.0
mtf_last_state = {"5m": None, "30m": None}
REVERSAL_THRESHOLDS = (200, 250, 300)

# V7.5 OBSERVER LAYER -------------------------------------------------------
# Trading rules remain V7.4. These measurements are intentionally observational
# so the short shakedown can tell us whether Tachys describes the chart correctly
# before they are allowed to influence paper orders.
STRUCTURE_LOG_FILE = "tachys_structure_v9_2_5.csv"
LAG_LOG_FILE = "tachys_btc_kalshi_lag_v9_2_5.csv"
EXTENSION_LOG_FILE = "tachys_edge_extension_v9_2_5.csv"
CHOP_SHADOW_LOG_FILE = "tachys_chop_shadow_v9_2_5.csv"
chop_shadow_position = None
chop_shadow_last_exit = 0.0
CHOP_SHADOW_ENABLED = True
BTC_HISTORY_CANDLES = 240          # 4h buffer; analysis focuses on rolling 3h
MACRO_LOOKBACK_CANDLES = 180       # 3 hours of 1-minute candles
FORMATION_LOOKBACK_CANDLES = 9     # 3-6-9 framework
FORMATION_PRIOR_CANDLES = 9
OBSERVER_LOG_SECONDS = 3.0
LEVEL2_DEPTH_LEVELS = 5
FLOW_WINDOWS = (3, 6, 9)
IMPULSE_COOLDOWN_SECONDS = 30
IMPULSE_MIN_MOVE_9S = 18.0
IMPULSE_MIN_MOVE_30S = 30.0
IMPULSE_MIN_EFFICIENCY_30S = 0.60
IMPULSE_LAG_HORIZONS = (3, 6, 9)

# V7.8 observer-only Extension / Edge Sniper engine. These values do NOT place
# paper positions and do not alter V7.7 Core/Chop/Early-Impulse trading.
EXTENSION_ARM_SCORE = 72
EXTENSION_EXTREME_SCORE = 86
EXTENSION_LIMIT_TTL = 63          # 3-6-9 rhythm; simulated resting limit only
EXTENSION_REARM_COOLDOWN = 36
EXTENSION_MIN_RANGE60 = 30.0

# EMA is still informational only. It is NOT an entry filter.
EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 30

SIDES = ("YES", "NO")

active_target = ""
paper_positions = {"YES": None, "NO": None}
last_paper_exit_time = {"YES": 0.0, "NO": 0.0}
paper_trade_counter = 0
paper_realized_pnl = 0.0

# V9.2.3: one pending opposite-side flip candidate at a time.
v923_flip_candidate = {"ticker": None, "from_side": None, "to_side": None, "armed_ts": 0.0}
chop_sniper_last_exit_time = 0.0
chop_sniper_last_state = "CORE"
chop_sniper_last_box = (None, None)
contract_trade_ids = {}
contract_trade_records = {}
btc_tick_history = []
btc_trade_volume_history = []
btc_current_minute_ohlc = None
btc_current_minute_volume = 0.0
btc_completed_candles = []

# V7.5 observer state
kalshi_book = {"yes": {}, "no": {}}
kalshi_trade_flow = []
observer_last_log_time = 0.0
formation_event_counter = 0
active_formation_event = None
last_formation_event = None
last_impulse_event_time = 0.0
impulse_events = []
last_yes_ask_observer = None
last_no_ask_observer = None
edge_limit_watch = None
edge_limit_last_end = 0.0
edge_limit_counter = 0


# ============================================================
# AUTH
# ============================================================

def load_private_key():
    with open(PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(
            f.read(),
            password=None,
        )


def create_signature(private_key):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + "GET" + "/trade-api/ws/v2"

    signature = private_key.sign(
        message.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )

    return timestamp, base64.b64encode(signature).decode()


# ============================================================
# MARKET HELPERS
# ============================================================

def iso_to_timestamp(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).timestamp()
    except (ValueError, TypeError):
        return None


def get_current_market():
    """
    Choose the KXBTC15M market whose close time is the nearest one
    still in the future. This prevents getting stuck on an old/open
    listing when several 15-minute markets are returned.
    """
    params = {
        "series_ticker": SERIES,
        "status": "open",
        "limit": 100,
    }

    response = requests.get(
        REST_URL,
        params=params,
        timeout=10,
    )
    response.raise_for_status()

    markets = response.json().get("markets", [])
    if not markets:
        return None

    now = time.time()
    future_markets = []

    for market in markets:
        close_ts = iso_to_timestamp(market.get("close_time"))
        if close_ts is not None and close_ts > now:
            future_markets.append((close_ts, market))

    if not future_markets:
        return None

    future_markets.sort(key=lambda item: item[0])
    return future_markets[0][1]


def get_market_snapshot(ticker):
    response = requests.get(
        f"{REST_URL}/{ticker}",
        timeout=5,
    )
    response.raise_for_status()
    return response.json().get("market", {})


def to_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def extract_top_of_book(source):
    """
    Return (yes_ask, no_ask).

    Prefer explicit ask fields. If an ask is absent, reconstruct it
    from the opposite-side bid, which is valid for a binary market:
      YES ask = 1 - NO bid
      NO ask  = 1 - YES bid
    """
    if not isinstance(source, dict):
        return None, None

    yes_ask = to_float(source.get("yes_ask_dollars"))
    no_ask = to_float(source.get("no_ask_dollars"))
    yes_bid = to_float(source.get("yes_bid_dollars"))
    no_bid = to_float(source.get("no_bid_dollars"))

    if yes_ask is None and no_bid is not None:
        yes_ask = max(0.0, min(1.0, 1.0 - no_bid))

    if no_ask is None and yes_bid is not None:
        no_ask = max(0.0, min(1.0, 1.0 - yes_bid))

    return yes_ask, no_ask


# ============================================================
# BTC/USD FEED + 1-MINUTE EMA ENGINE
# ============================================================

btc_last_price = None
btc_connected = False
btc_updates = 0

btc_minute_closes = []
btc_current_minute = None
btc_current_minute_price = None
btc_ema_9 = None
btc_ema_30 = None

pending_settlements = set()
logged_settlements = set()


def _ema_from_values(values, period):
    """Standard EMA seeded by the SMA of the first `period` closes."""
    if len(values) < period:
        return None
    ema = sum(values[:period]) / period
    k = 2 / (period + 1)
    for value in values[period:]:
        ema = (value - ema) * k + ema
    return ema


def update_btc_ema(include_live_candle=True):
    """
    Recompute BTC EMA from the historical 1-minute close series.

    When include_live_candle=True, append the current forming candle's latest
    price as its provisional close. This mirrors how charting platforms show
    a live EMA that moves during the current 1-minute candle.
    """
    global btc_ema_9
    global btc_ema_30

    values = [p for _, p in btc_minute_closes]
    if include_live_candle and btc_current_minute_price is not None:
        values = values + [btc_current_minute_price]

    btc_ema_9 = _ema_from_values(values, EMA_FAST_PERIOD)
    btc_ema_30 = _ema_from_values(values, EMA_SLOW_PERIOD)


def bootstrap_btc_history():
    """Load historical Coinbase 1-minute candles before the live feed starts."""
    global btc_minute_closes
    global btc_completed_candles

    try:
        response = requests.get(
            BTC_CANDLES_URL,
            params={"granularity": 60},
            headers={"User-Agent": "Tachys/7.5"},
            timeout=10,
        )
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("Unexpected Coinbase candle response")

        current_minute = int(time.time() // 60) * 60
        parsed = []
        for row in rows:
            if not isinstance(row, list) or len(row) < 6:
                continue
            ts = int(row[0])
            if ts >= current_minute:
                continue  # never seed from the still-forming candle
            parsed.append({
                "minute": ts,
                "low": float(row[1]),
                "high": float(row[2]),
                "open": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })

        parsed.sort(key=lambda c: c["minute"])
        parsed = parsed[-BTC_HISTORY_CANDLES:]
        if len(parsed) < EMA_SLOW_PERIOD:
            raise ValueError(f"Only {len(parsed)} completed candles returned")

        btc_minute_closes = [(c["minute"], c["close"]) for c in parsed]
        btc_completed_candles = list(parsed)
        update_btc_ema(include_live_candle=False)
        print(
            f"BTC EMA bootstrap: {len(parsed)} completed 1m candles loaded "
            f"| EMA9=${btc_ema_9:,.2f} | EMA30=${btc_ema_30:,.2f}"
        )
        return True
    except Exception as exc:
        print(f"⚠️ BTC EMA bootstrap failed: {exc}")
        print("EMA will warm from live candles; EMA-based grades are less reliable until then.")
        return False


def process_btc_price(price, now=None):
    global btc_last_price
    global btc_updates
    global btc_current_minute
    global btc_current_minute_price
    global btc_current_minute_ohlc
    global btc_current_minute_volume

    if price is None:
        return
    if now is None:
        now = time.time()

    btc_last_price = price
    btc_updates += 1
    btc_tick_history.append((now, price))
    cutoff = now - 600
    while btc_tick_history and btc_tick_history[0][0] < cutoff:
        btc_tick_history.pop(0)

    minute_ts = int(now // 60) * 60

    if btc_current_minute is None:
        btc_current_minute = minute_ts
        btc_current_minute_price = price
        btc_current_minute_ohlc = {"open": price, "high": price, "low": price, "close": price}
        update_btc_ema(include_live_candle=True)
        return

    if minute_ts == btc_current_minute:
        btc_current_minute_price = price
        if btc_current_minute_ohlc is None:
            btc_current_minute_ohlc = {"open": price, "high": price, "low": price, "close": price}
        else:
            btc_current_minute_ohlc["high"] = max(btc_current_minute_ohlc["high"], price)
            btc_current_minute_ohlc["low"] = min(btc_current_minute_ohlc["low"], price)
            btc_current_minute_ohlc["close"] = price
        update_btc_ema(include_live_candle=True)
        return

    btc_minute_closes.append((btc_current_minute, btc_current_minute_price))
    if len(btc_minute_closes) > BTC_HISTORY_CANDLES:
        btc_minute_closes.pop(0)

    if btc_current_minute_ohlc is not None:
        candle = dict(btc_current_minute_ohlc)
        candle["minute"] = btc_current_minute
        candle["volume"] = btc_current_minute_volume
        btc_completed_candles.append(candle)
        if len(btc_completed_candles) > BTC_HISTORY_CANDLES:
            btc_completed_candles.pop(0)

    btc_current_minute = minute_ts
    btc_current_minute_price = price
    btc_current_minute_ohlc = {"open": price, "high": price, "low": price, "close": price}
    btc_current_minute_volume = 0.0
    update_btc_ema(include_live_candle=True)


def process_btc_trade_volume(size, now=None):
    global btc_current_minute_volume
    if size is None:
        return
    if now is None:
        now = time.time()
    btc_current_minute_volume += max(0.0, float(size))
    btc_trade_volume_history.append((now, float(size)))
    cutoff = now - 600
    while btc_trade_volume_history and btc_trade_volume_history[0][0] < cutoff:
        btc_trade_volume_history.pop(0)


def extract_coinbase_trades(data):
    trades = []
    if not isinstance(data, dict):
        return trades
    for event in data.get("events", []) or []:
        if not isinstance(event, dict):
            continue
        for trade in event.get("trades", []) or []:
            if not isinstance(trade, dict) or trade.get("product_id") != BTC_PRODUCT:
                continue
            price = to_float(trade.get("price"))
            size = to_float(trade.get("size"))
            if price is not None:
                trades.append((price, size))
    return trades


def btc_range(seconds, now=None):
    if now is None:
        now = time.time()
    vals = [p for ts, p in btc_tick_history if ts >= now - seconds]
    return (max(vals) - min(vals)) if len(vals) >= 2 else None


def btc_change(seconds, now=None):
    """Net BTC move over the requested lookback."""
    if now is None:
        now = time.time()
    vals = [(ts, p) for ts, p in btc_tick_history if ts >= now - seconds]
    if len(vals) < 2:
        return None
    return vals[-1][1] - vals[0][1]


def btc_trend_efficiency(seconds=60, bucket_seconds=5, now=None):
    """
    Directional efficiency of BTC over a recent window.
    1.0 is nearly straight-line movement; values near 0 are choppy.
    Uses 5-second buckets so individual exchange ticks do not dominate.
    """
    if now is None:
        now = time.time()
    pts = [(ts, p) for ts, p in btc_tick_history if ts >= now - seconds]
    if len(pts) < 3:
        return None

    buckets = {}
    for ts, price in pts:
        key = int(ts // bucket_seconds)
        buckets[key] = price
    sampled = [buckets[k] for k in sorted(buckets)]
    if len(sampled) < 3:
        return None

    path = sum(abs(sampled[i] - sampled[i-1]) for i in range(1, len(sampled)))
    if path <= 0:
        return 0.0
    return abs(sampled[-1] - sampled[0]) / path


def contract_phase(close_ts, now=None):
    if now is None:
        now = time.time()
    if close_ts is None:
        return "CORE", None, None
    seconds_left = max(0.0, close_ts - now)
    elapsed = max(0.0, 900.0 - seconds_left)
    if elapsed < OBSERVATION_SECONDS:
        return "OBSERVE", seconds_left, elapsed
    if seconds_left <= EXPIRY_MODE_SECONDS:
        return "EXPIRY", seconds_left, elapsed
    return "CORE", seconds_left, elapsed


def current_candle_range():
    if not btc_current_minute_ohlc:
        return None
    return btc_current_minute_ohlc["high"] - btc_current_minute_ohlc["low"]


def recent_avg_candle_range(n=5):
    vals = [c["high"] - c["low"] for c in btc_completed_candles[-n:]]
    return (sum(vals) / len(vals)) if vals else None


def recent_volume_ratio(n=5):
    vols = [c.get("volume", 0.0) for c in btc_completed_candles[-n:] if c.get("volume", 0.0) > 0]
    if not vols or btc_current_minute_volume <= 0:
        return None
    avg = sum(vols) / len(vols)
    return (btc_current_minute_volume / avg) if avg > 0 else None


def parse_target_price(text):
    if not text:
        return None
    m = re.search(r"\$?([0-9]{2,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]{4,}(?:\.[0-9]+)?)", str(text))
    if not m:
        return None
    return to_float(m.group(1).replace(",", ""))


def session_context(now=None):
    if now is None:
        now = time.time()
    dt = datetime.fromtimestamp(now, ET)
    hour = dt.hour
    session = "OVERNIGHT" if hour < 7 else "DAYTIME"
    daypart = "OVERNIGHT" if hour < 6 else "MORNING" if hour < 12 else "AFTERNOON" if hour < 18 else "EVENING"
    return session, daypart, hour


def extract_coinbase_price(data):
    if not isinstance(data, dict):
        return None

    for event in data.get("events", []) or []:
        if not isinstance(event, dict):
            continue
        for ticker in event.get("tickers", []) or []:
            if not isinstance(ticker, dict):
                continue
            if ticker.get("product_id") == BTC_PRODUCT:
                price = to_float(ticker.get("price"))
                if price is not None:
                    return price
    return None


async def btc_price_feed():
    global btc_connected

    while True:
        try:
            async with websockets.connect(
                BTC_WS_URL,
                ping_interval=20,
                ping_timeout=None,
                close_timeout=10,
            ) as ws:
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "product_ids": [BTC_PRODUCT],
                    "channel": "ticker",
                }))
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "product_ids": [BTC_PRODUCT],
                    "channel": "market_trades",
                }))
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "channel": "heartbeats",
                }))

                btc_connected = True
                print("BTC/USD feed connected.")

                while True:
                    message = await ws.recv()
                    data = json.loads(message)
                    price = extract_coinbase_price(data)
                    if price is not None:
                        process_btc_price(price)
                    for trade_price, trade_size in extract_coinbase_trades(data):
                        process_btc_price(trade_price)
                        if trade_size is not None:
                            process_btc_trade_volume(trade_size)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            btc_connected = False
            print()
            print("⚠️ BTC feed error:", e)
            await asyncio.sleep(2)



# ============================================================
# V9.2.5 MULTI-TIMEFRAME REGIME OBSERVER — NO TRADE AUTHORITY
# ============================================================

def _mtf_fetch_candles(granularity):
    response = requests.get(
        BTC_CANDLES_URL,
        params={"granularity": granularity},
        headers={"User-Agent": "Tachys/9.2.5"},
        timeout=10,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("Unexpected Coinbase higher-timeframe candle response")
    out = []
    now_bucket = int(time.time() // granularity) * granularity
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        ts = int(row[0])
        if ts >= now_bucket:
            continue
        out.append({
            "ts": ts,
            "low": float(row[1]),
            "high": float(row[2]),
            "open": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        })
    out.sort(key=lambda x: x["ts"])
    return out


def _mtf_regime(candles):
    if len(candles) < 35:
        return {
            "regime": "WARMING", "ema9": None, "ema30": None,
            "gap": None, "gap_norm": None, "slope9": None, "slope30": None,
            "range12": None, "range36": None, "eff12": None, "location": None,
        }

    closes = [c["close"] for c in candles]
    e9s = _ema_series(closes, 9)
    e30s = _ema_series(closes, 30)
    e9, e30 = e9s[-1], e30s[-1]
    gap = None if e9 is None or e30 is None else e9 - e30

    recent12 = candles[-12:]
    recent36 = candles[-36:] if len(candles) >= 36 else candles
    range12 = max(c["high"] for c in recent12) - min(c["low"] for c in recent12)
    range36 = max(c["high"] for c in recent36) - min(c["low"] for c in recent36)

    slope9 = _safe_slope([x for x in e9s[-6:] if x is not None])
    slope30 = _safe_slope([x for x in e30s[-6:] if x is not None])

    path = sum(abs(closes[i] - closes[i-1]) for i in range(max(1, len(closes)-12), len(closes)))
    net = abs(closes[-1] - closes[-12])
    eff12 = (net / path) if path > 0 else 0.0

    avg_bar_range = sum(c["high"] - c["low"] for c in recent12) / len(recent12)
    gap_norm = abs(gap) / max(1.0, avg_bar_range) if gap is not None else None

    high36 = max(c["high"] for c in recent36)
    low36 = min(c["low"] for c in recent36)
    span36 = max(1.0, high36 - low36)
    location_value = (closes[-1] - low36) / span36
    location = "LOW" if location_value < 0.33 else "HIGH" if location_value > 0.67 else "MID"

    # Regime intentionally conservative: this is descriptive telemetry only.
    if gap_norm is not None and gap_norm >= 0.75 and eff12 >= 0.45:
        direction = "UP" if gap > 0 else "DOWN"
        regime = f"EXPANSION_{direction}"
    elif gap_norm is not None and gap_norm <= 0.25 and eff12 <= 0.30:
        regime = "COMPRESSION"
    elif eff12 <= 0.25:
        regime = "RANGE"
    else:
        direction = "UP" if (gap or 0) > 0 else "DOWN"
        regime = f"TRANSITION_{direction}"

    return {
        "regime": regime, "ema9": e9, "ema30": e30, "gap": gap,
        "gap_norm": gap_norm, "slope9": slope9, "slope30": slope30,
        "range12": range12, "range36": range36, "eff12": eff12,
        "location": location,
    }


def _mtf_log_row(now, state5, state30):
    exists = os.path.exists(MTF_LOG_FILE)
    with open(MTF_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow([
                "timestamp", "btc_price",
                "regime_5m", "ema9_5m", "ema30_5m", "gap_5m", "gap_norm_5m",
                "slope9_5m", "slope30_5m", "range12_5m", "range36_5m", "eff12_5m", "location_5m",
                "regime_30m", "ema9_30m", "ema30_30m", "gap_30m", "gap_norm_30m",
                "slope9_30m", "slope30_30m", "range12_30m", "range36_30m", "eff12_30m", "location_30m",
            ])
        writer.writerow([
            datetime.fromtimestamp(now, ET).strftime("%Y-%m-%d %H:%M:%S"),
            btc_last_price,
            state5["regime"], state5["ema9"], state5["ema30"], state5["gap"], state5["gap_norm"],
            state5["slope9"], state5["slope30"], state5["range12"], state5["range36"], state5["eff12"], state5["location"],
            state30["regime"], state30["ema9"], state30["ema30"], state30["gap"], state30["gap_norm"],
            state30["slope9"], state30["slope30"], state30["range12"], state30["range36"], state30["eff12"], state30["location"],
        ])


async def multitimeframe_observer():
    global mtf_last_print_ts, mtf_last_state
    while True:
        try:
            c5, c30 = await asyncio.gather(
                asyncio.to_thread(_mtf_fetch_candles, MTF_5M_GRANULARITY),
                asyncio.to_thread(_mtf_fetch_candles, MTF_30M_GRANULARITY),
            )
            state5 = _mtf_regime(c5)
            state30 = _mtf_regime(c30)
            now = time.time()
            _mtf_log_row(now, state5, state30)

            changed = (
                state5["regime"] != mtf_last_state.get("5m")
                or state30["regime"] != mtf_last_state.get("30m")
            )
            if changed or now - mtf_last_print_ts >= MTF_PRINT_SECONDS:
                print(
                    "🗺️ MTF OBSERVER | "
                    f"5m={state5['regime']} loc={state5['location']} "
                    f"E9/30={state5['ema9']:.0f}/{state5['ema30']:.0f} "
                    f"| 30m={state30['regime']} loc={state30['location']} "
                    f"E9/30={state30['ema9']:.0f}/{state30['ema30']:.0f}"
                )
                mtf_last_print_ts = now
                mtf_last_state = {"5m": state5["regime"], "30m": state30["regime"]}

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            print(f"⚠️ MTF observer error: {exc}")
            traceback.print_exc()

        await asyncio.sleep(MTF_REFRESH_SECONDS)



# ============================================================
# SIDE PRICE HISTORY
# ============================================================

price_history = {
    "YES": [],
    "NO": [],
}


def reset_contract_history():
    for side in SIDES:
        price_history[side] = []


def record_price(side, price, now=None):
    if price is None:
        return

    if now is None:
        now = time.time()

    history = price_history[side]
    history.append((now, price))

    cutoff = now - HISTORY_SECONDS
    while history and history[0][0] < cutoff:
        history.pop(0)


def get_price_at(side, seconds_ago, now=None):
    history = price_history[side]
    if not history:
        return None

    if now is None:
        now = time.time()

    target = now - seconds_ago
    closest = min(
        history,
        key=lambda item: abs(item[0] - target),
    )

    distance = abs(closest[0] - target)
    if distance > 3:
        return None

    return closest[1]


# ============================================================
# 1-MINUTE EMA ENGINE — INFORMATIONAL ONLY
# ============================================================

# Kept continuous across contract handoffs as requested.
minute_closes = {
    "YES": [],
    "NO": [],
}
current_minute = {
    "YES": None,
    "NO": None,
}
current_minute_price = {
    "YES": None,
    "NO": None,
}
ema_9 = {
    "YES": None,
    "NO": None,
}
ema_30 = {
    "YES": None,
    "NO": None,
}


def calculate_sma(values):
    if not values:
        return None
    return sum(values) / len(values)


def update_ema(side):
    closes = minute_closes[side]

    if len(closes) >= EMA_FAST_PERIOD:
        fast_values = [
            price
            for _, price in closes[-EMA_FAST_PERIOD:]
        ]

        if ema_9[side] is None:
            ema_9[side] = calculate_sma(fast_values)
        else:
            multiplier = 2 / (EMA_FAST_PERIOD + 1)
            ema_9[side] = (
                (fast_values[-1] - ema_9[side]) * multiplier
                + ema_9[side]
            )

    if len(closes) >= EMA_SLOW_PERIOD:
        slow_values = [
            price
            for _, price in closes[-EMA_SLOW_PERIOD:]
        ]

        if ema_30[side] is None:
            ema_30[side] = calculate_sma(slow_values)
        else:
            multiplier = 2 / (EMA_SLOW_PERIOD + 1)
            ema_30[side] = (
                (slow_values[-1] - ema_30[side]) * multiplier
                + ema_30[side]
            )


def process_minute_price(side, price, now=None):
    if price is None:
        return

    if now is None:
        now = time.time()

    minute_timestamp = int(now // 60) * 60

    if current_minute[side] is None:
        current_minute[side] = minute_timestamp
        current_minute_price[side] = price
        return

    if minute_timestamp == current_minute[side]:
        current_minute_price[side] = price
        return

    minute_closes[side].append(
        (
            current_minute[side],
            current_minute_price[side],
        )
    )

    if len(minute_closes[side]) > 60:
        minute_closes[side].pop(0)

    current_minute[side] = minute_timestamp
    current_minute_price[side] = price
    update_ema(side)


def get_ema_values(side):
    return ema_9[side], ema_30[side]


# ============================================================
# V7.5 STRUCTURE + LEVEL-2 + BTC->KALSHI LAG OBSERVER
# ============================================================

def _safe_slope(values):
    """Least-squares slope per sample without numpy."""
    if values is None or len(values) < 2:
        return None
    n = len(values)
    sx = n * (n - 1) / 2.0
    sxx = (n - 1) * n * (2 * n - 1) / 6.0
    sy = sum(values)
    sxy = sum(i * v for i, v in enumerate(values))
    den = n * sxx - sx * sx
    return (n * sxy - sx * sy) / den if den else 0.0


def _ema_series(values, period):
    if len(values) < period:
        return [None] * len(values)
    out = [None] * len(values)
    ema = sum(values[:period]) / period
    out[period - 1] = ema
    k = 2.0 / (period + 1)
    for i in range(period, len(values)):
        ema = (values[i] - ema) * k + ema
        out[i] = ema
    return out


def observer_candles():
    """Completed candles plus the current forming minute, capped to the macro window."""
    candles = [dict(c) for c in btc_completed_candles[-MACRO_LOOKBACK_CANDLES:]]
    if btc_current_minute_ohlc is not None and btc_current_minute is not None:
        live = dict(btc_current_minute_ohlc)
        live["minute"] = btc_current_minute
        live["volume"] = btc_current_minute_volume
        candles.append(live)
    return candles[-MACRO_LOOKBACK_CANDLES:]


def macro_leg_state(candles):
    """V7.7 parent leg: reset ancestry on a confirmed EMA9/30 structural turn.

    V7.6 used the absolute high/low of the whole rolling window, which made the
    parent state lag and stay LATE. Here the most recent sustained EMA9/30 cross
    can start a new parent leg. If no confirmed cross exists, fall back to the
    rolling-extreme ancestry method.
    """
    if len(candles) < 30:
        return {"direction": "WARMING", "distance": None, "age_min": None, "start_price": None, "end_price": None,
                "maturity": "WARMING", "reset_reason": "WARMING"}
    closes = [c["close"] for c in candles]
    e9 = _ema_series(closes, EMA_FAST_PERIOD)
    e30 = _ema_series(closes, EMA_SLOW_PERIOD)

    reset_i = None
    reset_dir = None
    # Require three consecutive bars on the new side of the slow EMA to avoid
    # treating a one-candle touch as a new ancestry. Search newest first.
    for i in range(len(candles) - 3, EMA_SLOW_PERIOD, -1):
        if any(e9[j] is None or e30[j] is None for j in range(i-1, i+3)):
            continue
        prev_gap = e9[i-1] - e30[i-1]
        gaps = [e9[j] - e30[j] for j in range(i, i+3)]
        if prev_gap <= 0 and all(g > 0 for g in gaps) and all(closes[j] >= e30[j] for j in range(i, i+3)):
            reset_i, reset_dir = i, "UP"
            break
        if prev_gap >= 0 and all(g < 0 for g in gaps) and all(closes[j] <= e30[j] for j in range(i, i+3)):
            reset_i, reset_dir = i, "DOWN"
            break

    if reset_i is not None:
        direction = reset_dir
        start_i = reset_i
        start_price = closes[start_i]
        end_price = closes[-1]
        distance = end_price - start_price
        reset_reason = "EMA9_30_STRUCTURAL_RESET"
    else:
        lows = [c["low"] for c in candles]
        highs = [c["high"] for c in candles]
        i_low = min(range(len(lows)), key=lows.__getitem__)
        i_high = max(range(len(highs)), key=highs.__getitem__)
        if i_low < i_high:
            direction = "UP"; start_i = i_low; start_price = lows[i_low]; end_price = highs[i_high]
        else:
            direction = "DOWN"; start_i = i_high; start_price = highs[i_high]; end_price = lows[i_low]
        distance = end_price - start_price
        reset_reason = "ROLLING_EXTREME_FALLBACK"

    age_min = max(0.0, (candles[-1]["minute"] - candles[start_i]["minute"]) / 60.0)
    maturity = "EARLY" if age_min < 30 else "MID" if age_min < 90 else "LATE"
    return {
        "direction": direction, "distance": distance, "age_min": age_min,
        "start_price": start_price, "end_price": end_price, "start_index": start_i,
        "maturity": maturity, "reset_reason": reset_reason,
    }


def ema_stretch_state(candles):
    if len(candles) < EMA_SLOW_PERIOD:
        return {}
    closes = [c["close"] for c in candles]
    e9 = _ema_series(closes, EMA_FAST_PERIOD)
    e30 = _ema_series(closes, EMA_SLOW_PERIOD)
    i = len(closes) - 1
    if e9[i] is None:
        return {}
    side = "ABOVE" if closes[i] > e9[i] else "BELOW" if closes[i] < e9[i] else "ON"
    duration = 0
    max_abs_stretch = 0.0
    crossings = 0
    last_rel = None
    start = max(0, i - MACRO_LOOKBACK_CANDLES + 1)
    for j in range(start, i + 1):
        if e9[j] is None:
            continue
        rel = 1 if closes[j] > e9[j] else -1 if closes[j] < e9[j] else 0
        max_abs_stretch = max(max_abs_stretch, abs(closes[j] - e9[j]))
        if last_rel is not None and rel and last_rel and rel != last_rel:
            crossings += 1
        if rel:
            last_rel = rel
    wanted = 1 if side == "ABOVE" else -1 if side == "BELOW" else 0
    if wanted:
        for j in range(i, -1, -1):
            if e9[j] is None:
                break
            rel = 1 if closes[j] > e9[j] else -1 if closes[j] < e9[j] else 0
            if rel != wanted:
                break
            duration += 1
    slope9 = _safe_slope([x for x in e9[-6:] if x is not None])
    slope30 = _safe_slope([x for x in e30[-6:] if x is not None])
    gap = (e9[i] - e30[i]) if e30[i] is not None else None
    prev_gap = None
    if len(e9) >= 4 and e9[-4] is not None and e30[-4] is not None:
        prev_gap = e9[-4] - e30[-4]
    gap_state = "UNKNOWN"
    if gap is not None and prev_gap is not None:
        gap_state = "EXPANDING" if abs(gap) > abs(prev_gap) + 1 else "COMPRESSING" if abs(gap) < abs(prev_gap) - 1 else "FLAT"
    return {
        "side": side, "duration_min": duration, "distance": closes[i] - e9[i],
        "max_abs_stretch": max_abs_stretch, "ema9_slope6": slope9,
        "ema30_slope6": slope30, "ema_gap": gap, "ema_gap_state": gap_state,
        "crossings": crossings,
    }


def _clamp100(x):
    return max(0, min(100, int(round(x))))


def formation_state(candles, macro):
    """V7.6 observer: geometry + parent/local separation + compression/release lifecycle."""
    need = FORMATION_LOOKBACK_CANDLES + FORMATION_PRIOR_CANDLES
    if len(candles) < need:
        return {}
    recent = candles[-FORMATION_LOOKBACK_CANDLES:]
    prior = candles[-need:-FORMATION_LOOKBACK_CANDLES]
    highs = [c["high"] for c in recent]
    lows = [c["low"] for c in recent]
    closes = [c["close"] for c in candles]
    recent_range = max(highs) - min(lows)
    prior_range = max(c["high"] for c in prior) - min(c["low"] for c in prior)
    contraction = recent_range / prior_range if prior_range > 0 else None
    high_slope = _safe_slope(highs)
    low_slope = _safe_slope(lows)
    geometry = "RANGE"
    if high_slope is not None and low_slope is not None:
        if high_slope < -1.0 and low_slope > 1.0:
            geometry = "SYMMETRIC_TRIANGLE"
        elif abs(high_slope) <= 1.5 and low_slope > 1.0:
            geometry = "ASCENDING_TRIANGLE"
        elif high_slope < -1.0 and abs(low_slope) <= 1.5:
            geometry = "DESCENDING_TRIANGLE"
        elif high_slope > 1.0 and low_slope > 1.0:
            geometry = "RISING_CHANNEL"
        elif high_slope < -1.0 and low_slope < -1.0:
            geometry = "FALLING_CHANNEL"

    base = candles[-(FORMATION_LOOKBACK_CANDLES + 1):-1]
    prev_high = max(c["high"] for c in base)
    prev_low = min(c["low"] for c in base)
    current = candles[-1]["close"]
    breakout = "NONE"
    if current > prev_high:
        breakout = "UP"
    elif current < prev_low:
        breakout = "DOWN"
    failure = "NONE"
    for back in (1, 2, 3):
        if len(candles) < FORMATION_LOOKBACK_CANDLES + back + 1:
            continue
        idx = -1 - back
        base2 = candles[-(FORMATION_LOOKBACK_CANDLES + back + 1):idx]
        if len(base2) < FORMATION_LOOKBACK_CANDLES:
            continue
        bh = max(c["high"] for c in base2[-FORMATION_LOOKBACK_CANDLES:])
        bl = min(c["low"] for c in base2[-FORMATION_LOOKBACK_CANDLES:])
        old_close = candles[idx]["close"]
        if old_close > bh and current <= bh:
            failure = "FAILED_UP"; break
        if old_close < bl and current >= bl:
            failure = "FAILED_DOWN"; break

    stretch = ema_stretch_state(candles)
    # Compression score combines range contraction, converging swing slopes and EMA-gap compression.
    score = 0.0
    if contraction is not None:
        score += max(0.0, min(55.0, (1.0 - contraction) * 100.0))
    if high_slope is not None and low_slope is not None:
        if high_slope <= 0 <= low_slope:
            score += 25.0
        elif abs(high_slope - low_slope) <= 2.0:
            score += 12.0
    if stretch.get("ema_gap_state") == "COMPRESSING":
        score += 20.0
    compression_score = _clamp100(score)

    # Local regime describes what is happening now inside the parent leg.
    net3 = closes[-1] - closes[-4] if len(closes) >= 4 else 0.0
    avg_range9 = sum(c["high"] - c["low"] for c in recent) / max(1, len(recent))
    parent_dir = macro.get("direction") if macro else "WARMING"
    local_regime = "MIXED"
    if breakout != "NONE" and abs(net3) >= max(15.0, avg_range9 * 1.25):
        local_regime = "RELEASE"
    elif compression_score >= 60:
        local_regime = "COMPRESSION"
    elif abs(net3) >= max(25.0, avg_range9 * 1.8):
        local_regime = "IMPULSE"
    else:
        local_dir = "UP" if net3 > 5 else "DOWN" if net3 < -5 else "FLAT"
        if parent_dir in ("UP", "DOWN") and local_dir not in ("FLAT", parent_dir):
            local_regime = "PULLBACK"
        elif failure != "NONE":
            local_regime = "REVERSAL"
        elif local_dir == parent_dir:
            local_regime = "TREND"
        else:
            local_regime = "MIXED"

    if failure != "NONE":
        form_maturity = "FAILED"
    elif breakout != "NONE":
        form_maturity = "BREAKING"
    elif compression_score >= 75:
        form_maturity = "APEX"
    else:
        form_maturity = "FORMING"

    # Generation counts discrete compression episodes in the most recent 60 minutes, not forever since macro start.
    generation = 0
    segment = candles[-60:]
    in_comp = False
    for i in range(18, len(segment) + 1, 3):
        a = segment[i-18:i-9]
        b = segment[i-9:i]
        if len(a) < 9 or len(b) < 9:
            continue
        ra = max(c["high"] for c in a) - min(c["low"] for c in a)
        rb = max(c["high"] for c in b) - min(c["low"] for c in b)
        comp = ra > 0 and rb / ra <= 0.72
        if comp and not in_comp:
            generation += 1
        in_comp = comp
    generation = max(1, generation) if compression_score >= 45 or breakout != "NONE" or failure != "NONE" else 0

    # Impulse score is separate from compression score.
    move9 = closes[-1] - closes[-10] if len(closes) >= 10 else 0.0
    impulse_score = _clamp100(min(60.0, abs(move9) / max(1.0, avg_range9) * 15.0) + (25 if breakout != "NONE" else 0) + (15 if stretch.get("ema_gap_state") == "EXPANDING" else 0))
    return {
        "geometry": geometry, "range9": recent_range, "prior_range9": prior_range,
        "contraction_ratio": contraction, "high_slope": high_slope, "low_slope": low_slope,
        "breakout": breakout, "failure": failure, "generation": generation,
        "maturity": form_maturity, "compression_score": compression_score,
        "local_regime": local_regime, "impulse_score_geom": impulse_score,
    }


def update_formation_event(form, now=None):
    """Assign one ID to a developing compression/breakout/failure lifecycle."""
    global formation_event_counter, active_formation_event, last_formation_event
    if now is None:
        now = time.time()
    score = form.get("compression_score") or 0
    maturity = form.get("maturity") or "FORMING"
    qualifies = score >= 55 or maturity in ("APEX", "BREAKING", "FAILED")
    if active_formation_event is None and qualifies:
        formation_event_counter += 1
        active_formation_event = {
            "id": f"F{formation_event_counter:03d}", "start": now,
            "last": now, "peak_compression": score,
        }
    elif active_formation_event is not None:
        active_formation_event["last"] = now
        active_formation_event["peak_compression"] = max(active_formation_event.get("peak_compression", 0), score)
        # Close only after the event has actually released/failed and compression has relaxed.
        age = now - active_formation_event["start"]
        if age >= 30 and maturity in ("BREAKING", "FAILED") and score < 45:
            last_formation_event = dict(active_formation_event)
            last_formation_event["end"] = now
            active_formation_event = None
    ev = active_formation_event or last_formation_event
    if ev is None:
        return None, None
    return ev.get("id"), (now - ev.get("start", now)) / 60.0

def reset_kalshi_observer_book():
    kalshi_book["yes"].clear()
    kalshi_book["no"].clear()


def process_orderbook_message(data):
    """Maintain native YES/NO bid books from Kalshi snapshot + deltas."""
    if not isinstance(data, dict):
        return
    typ = data.get("type")
    msg = data.get("msg", {}) or {}
    if typ == "orderbook_snapshot":
        reset_kalshi_observer_book()
        for side, key in (("yes", "yes_dollars_fp"), ("no", "no_dollars_fp")):
            rows = msg.get(key) or msg.get(key.replace("_fp", "")) or []
            for row in rows:
                if not isinstance(row, (list, tuple)) or len(row) < 2:
                    continue
                p, q = to_float(row[0]), to_float(row[1])
                if p is not None and q is not None and q > 0:
                    kalshi_book[side][round(p, 4)] = q
    elif typ == "orderbook_delta":
        side = str(msg.get("side", "")).lower()
        p = to_float(msg.get("price_dollars"))
        d = to_float(msg.get("delta_fp"))
        if side in kalshi_book and p is not None and d is not None:
            p = round(p, 4)
            new_q = kalshi_book[side].get(p, 0.0) + d
            if new_q <= 1e-9:
                kalshi_book[side].pop(p, None)
            else:
                kalshi_book[side][p] = new_q


def process_kalshi_trade_message(data):
    if not isinstance(data, dict) or data.get("type") != "trade":
        return
    msg = data.get("msg", {}) or {}
    side = str(msg.get("taker_outcome_side") or msg.get("taker_side") or "").lower()
    count = to_float(msg.get("count_fp"))
    if side not in ("yes", "no") or count is None:
        return
    now = time.time()
    kalshi_trade_flow.append((now, side, count))
    cutoff = now - 30
    while kalshi_trade_flow and kalshi_trade_flow[0][0] < cutoff:
        kalshi_trade_flow.pop(0)


def level2_snapshot(now=None):
    if now is None:
        now = time.time()
    yes_levels = sorted(kalshi_book["yes"].items(), reverse=True)[:LEVEL2_DEPTH_LEVELS]
    no_levels = sorted(kalshi_book["no"].items(), reverse=True)[:LEVEL2_DEPTH_LEVELS]
    yes_depth = sum(q for _, q in yes_levels)
    no_depth = sum(q for _, q in no_levels)
    total = yes_depth + no_depth
    imbalance = (yes_depth - no_depth) / total if total > 0 else None
    yes_bid = yes_levels[0][0] if yes_levels else None
    yes_bid_size = yes_levels[0][1] if yes_levels else None
    yes_ask = 1.0 - no_levels[0][0] if no_levels else None
    yes_ask_size = no_levels[0][1] if no_levels else None
    microprice = None
    if None not in (yes_bid, yes_bid_size, yes_ask, yes_ask_size) and yes_bid_size + yes_ask_size > 0:
        microprice = (yes_ask * yes_bid_size + yes_bid * yes_ask_size) / (yes_bid_size + yes_ask_size)
    flows = {}
    for w in FLOW_WINDOWS:
        y = sum(q for ts, s, q in kalshi_trade_flow if ts >= now - w and s == "yes")
        n = sum(q for ts, s, q in kalshi_trade_flow if ts >= now - w and s == "no")
        denom = y + n
        flows[w] = (y - n) / denom if denom > 0 else 0.0
    return {
        "yes_bid": yes_bid, "yes_ask": yes_ask, "yes_bid_size": yes_bid_size,
        "yes_ask_size": yes_ask_size, "yes_depth5": yes_depth, "no_depth5": no_depth,
        "book_imbalance": imbalance, "microprice": microprice,
        "flow3": flows.get(3), "flow6": flows.get(6), "flow9": flows.get(9),
    }


def impulse_observer_state(now=None):
    if now is None:
        now = time.time()
    ch3, ch6, ch9 = btc_change(3, now), btc_change(6, now), btc_change(9, now)
    ch30, ch60 = btc_change(30, now), btc_change(60, now)
    eff30 = btc_trend_efficiency(30, 3, now)
    r60 = btc_range(60, now)
    direction = "NONE"
    score = 0
    if ch9 is not None and abs(ch9) >= IMPULSE_MIN_MOVE_9S:
        score += 1
    if ch30 is not None and abs(ch30) >= IMPULSE_MIN_MOVE_30S:
        score += 1
    if eff30 is not None and eff30 >= IMPULSE_MIN_EFFICIENCY_30S:
        score += 1
    if ch9 is not None and ch30 is not None and ch9 * ch30 > 0:
        score += 1
    if score >= 3 and ch30 is not None:
        direction = "UP" if ch30 > 0 else "DOWN"
    return {
        "direction": direction, "score": score, "ch3": ch3, "ch6": ch6,
        "ch9": ch9, "ch30": ch30, "ch60": ch60, "eff30": eff30, "range60": r60,
    }


def maybe_start_impulse_event(ticker, yes_ask, no_ask, now=None):
    global last_impulse_event_time
    if now is None:
        now = time.time()
    state = impulse_observer_state(now)
    if state["direction"] == "NONE" or now - last_impulse_event_time < IMPULSE_COOLDOWN_SECONDS:
        return
    last_impulse_event_time = now
    impulse_events.append({
        "ticker": ticker, "start": now, "direction": state["direction"],
        "btc_start": btc_last_price, "yes_start": yes_ask, "no_start": no_ask,
        "state": state, "samples": {},
    })


def update_impulse_lag_events(yes_ask, no_ask, now=None):
    if now is None:
        now = time.time()
    finished = []
    for ev in impulse_events:
        age = now - ev["start"]
        for h in IMPULSE_LAG_HORIZONS:
            if age >= h and h not in ev["samples"]:
                ev["samples"][h] = {
                    "btc": btc_last_price, "yes": yes_ask, "no": no_ask,
                }
        if all(h in ev["samples"] for h in IMPULSE_LAG_HORIZONS):
            with open(LAG_LOG_FILE, "a", newline="", encoding="utf-8") as f:
                s = ev["state"]
                row = [
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ev["start"])),
                    ev["ticker"], ev["direction"], ev["btc_start"], ev["yes_start"], ev["no_start"],
                    s.get("ch3"), s.get("ch6"), s.get("ch9"), s.get("ch30"), s.get("eff30"),
                ]
                for h in IMPULSE_LAG_HORIZONS:
                    sample = ev["samples"][h]
                    row.extend([sample["btc"], sample["yes"], sample["no"]])
                csv.writer(f).writerow(row)
            finished.append(ev)
    for ev in finished:
        if ev in impulse_events:
            impulse_events.remove(ev)


def extension_observer_state(candles, now=None):
    """Observer-only double-extension model: Price->EMA9 plus EMA9->EMA30.

    Distances are normalized by the live 60-second BTC range so the same logic
    can later transfer across volatility regimes. A high score ARMS a possible
    counter-move; it is never itself a reversal entry signal.
    """
    if now is None:
        now = time.time()
    if len(candles) < EMA_SLOW_PERIOD or btc_last_price is None:
        return {}
    closes = [c["close"] for c in candles]
    e9s = _ema_series(closes, EMA_FAST_PERIOD)
    e30s = _ema_series(closes, EMA_SLOW_PERIOD)
    e9, e30 = e9s[-1], e30s[-1]
    if e9 is None or e30 is None:
        return {}
    d1 = btc_last_price - e9
    d2 = e9 - e30
    r60 = max(EXTENSION_MIN_RANGE60, btc_range(60, now) or 0.0)
    n1, n2 = abs(d1) / r60, abs(d2) / r60
    same_dir = (d1 > 0 and d2 > 0) or (d1 < 0 and d2 < 0)
    direction = "UP" if d1 > 0 and d2 > 0 else "DOWN" if d1 < 0 and d2 < 0 else "MIXED"

    # Double extension is deliberately harder to score than a single price spike.
    # 1.0x of 60s range in each layer is already substantial; 1.5x+ is extreme.
    layer1 = min(50.0, n1 / 1.5 * 50.0)
    layer2 = min(50.0, n2 / 1.5 * 50.0)
    score = _clamp100(layer1 + layer2) if same_dir else _clamp100(min(layer1, layer2) * 0.60)

    ch3 = btc_change(3, now); ch6 = btc_change(6, now); ch9 = btc_change(9, now)
    vel = [x for x in (ch3, ch6, ch9) if x is not None]
    signed = (1 if direction == "UP" else -1 if direction == "DOWN" else 0)
    confirming = sum(1 for x in vel if signed and x * signed > 0)
    fading = sum(1 for x in vel if signed and x * signed <= 0)
    stretch_state = ema_stretch_state(candles)
    gap_state = stretch_state.get("ema_gap_state", "UNKNOWN")
    slope9 = stretch_state.get("ema9_slope6")
    slope30 = stretch_state.get("ema30_slope6")

    exhaustion = 0
    if same_dir and score >= EXTENSION_ARM_SCORE:
        exhaustion += 25 if fading >= 2 else 10 if fading == 1 else 0
        exhaustion += 25 if gap_state in ("FLAT", "COMPRESSING") else 0
        if slope9 is not None and slope30 is not None and signed:
            if slope9 * signed <= slope30 * signed:
                exhaustion += 20
        # Price still extended but 3s move has stopped confirming = useful edge clue.
        if ch3 is not None and signed and ch3 * signed <= 0:
            exhaustion += 20
        exhaustion += 10 if score >= EXTENSION_EXTREME_SCORE else 0
    exhaustion = _clamp100(exhaustion)
    armed = same_dir and score >= EXTENSION_ARM_SCORE
    counter_side = "NO" if direction == "UP" else "YES" if direction == "DOWN" else None
    return {
        "price_ema9_distance": d1, "ema9_ema30_distance": d2,
        "norm_price_ema9": n1, "norm_ema_gap": n2,
        "double_extension_score": score, "extension_direction": direction,
        "exhaustion_score": exhaustion, "edge_sniper_armed": armed,
        "edge_counter_side": counter_side, "extension_confirming_369": confirming,
        "extension_fading_369": fading,
    }


def extension_metrics(now=None):
    """V8.5 live extension metrics wrapper.

    V8.1 referenced extension_metrics() from the REST/context path but never
    defined it. Keep one canonical calculation so WS and REST decisions see
    the same extension/exhaustion state.
    """
    return extension_observer_state(observer_candles(), time.time() if now is None else now) or {}


def update_edge_limit_observer(ticker, yes_ask, no_ask, ext, now=None):
    """Simulate a patient Edge-Sniper resting limit. Observer only: never trades.

    The candidate price is deliberately below the current counter-side ask. We
    record FILLED, NO_FILL, or CANCELLED so future tuning includes missed orders
    instead of pretending every signal received a fill.
    """
    global edge_limit_watch, edge_limit_last_end, edge_limit_counter
    if now is None:
        now = time.time()

    def log_event(w, status, reason):
        with open(EXTENSION_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)), w["id"], ticker,
                w["direction"], w["side"], w["score"], w["exhaustion"], w["start_ask"],
                w["limit"], yes_ask, no_ask, status, reason, now-w["start"], btc_last_price,
                ext.get("price_ema9_distance"), ext.get("ema9_ema30_distance"),
                ext.get("norm_price_ema9"), ext.get("norm_ema_gap"), ext.get("double_extension_score"),
                ext.get("exhaustion_score"),
            ])

    if edge_limit_watch is not None:
        w = edge_limit_watch
        ask = yes_ask if w["side"] == "YES" else no_ask
        age = now - w["start"]
        if ask is not None and ask <= w["limit"]:
            log_event(w, "FILLED", "LIMIT_TOUCHED")
            edge_limit_watch = None; edge_limit_last_end = now
        elif age >= EXTENSION_LIMIT_TTL:
            log_event(w, "NO_FILL", "TTL_63S")
            edge_limit_watch = None; edge_limit_last_end = now
        elif (not ext.get("edge_sniper_armed")) or ext.get("extension_direction") != w["direction"]:
            log_event(w, "CANCELLED", "EXTENSION_BROKE")
            edge_limit_watch = None; edge_limit_last_end = now

    if edge_limit_watch is None and ext.get("edge_sniper_armed") and now-edge_limit_last_end >= EXTENSION_REARM_COOLDOWN:
        side = ext.get("edge_counter_side")
        ask = yes_ask if side == "YES" else no_ask
        if side and ask is not None and 0.06 <= ask <= 0.94:
            score = ext.get("double_extension_score", 0)
            # Patient discount: 3c when armed, 6c when extreme, 9c when extreme+exhausting.
            discount = 0.03
            if score >= EXTENSION_EXTREME_SCORE: discount = 0.06
            if score >= EXTENSION_EXTREME_SCORE and ext.get("exhaustion_score", 0) >= 50: discount = 0.09
            limit = max(0.01, round(ask - discount, 3))
            edge_limit_counter += 1
            edge_limit_watch = {"id": f"E{edge_limit_counter:04d}", "start": now,
                                "direction": ext.get("extension_direction"), "side": side,
                                "score": score, "exhaustion": ext.get("exhaustion_score", 0),
                                "start_ask": ask, "limit": limit}
            log_event(edge_limit_watch, "PLACED", f"DISCOUNT_{int(discount*100)}C")
    return edge_limit_watch


def structure_snapshot(ticker, close_ts, yes_ask, no_ask, now=None):
    if now is None:
        now = time.time()
    candles = observer_candles()
    macro = macro_leg_state(candles)
    stretch = ema_stretch_state(candles)
    form = formation_state(candles, macro)
    l2 = level2_snapshot(now)
    impulse = impulse_observer_state(now)
    extension = extension_observer_state(candles, now)
    edge_watch = update_edge_limit_observer(ticker, yes_ask, no_ask, extension, now)
    phase, sec_left, elapsed = contract_phase(close_ts, now)
    target = parse_target_price(active_target)
    target_dist = btc_last_price - target if btc_last_price is not None and target is not None else None
    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "ticker": ticker,
        "btc_price": btc_last_price, "target_price": target, "target_distance": target_dist,
        "seconds_left": sec_left, "contract_elapsed": elapsed, "phase": phase,
        "macro_direction": macro.get("direction"), "macro_distance": macro.get("distance"),
        "macro_age_min": macro.get("age_min"), "macro_start_price": macro.get("start_price"),
        "macro_end_price": macro.get("end_price"), "parent_maturity": macro.get("maturity"),
        "ema9_side": stretch.get("side"), "ema9_duration_min": stretch.get("duration_min"),
        "ema9_distance": stretch.get("distance"), "ema9_max_stretch": stretch.get("max_abs_stretch"),
        "ema9_slope6": stretch.get("ema9_slope6"), "ema30_slope6": stretch.get("ema30_slope6"),
        "ema_gap": stretch.get("ema_gap"), "ema_gap_state": stretch.get("ema_gap_state"),
        "ema9_crossings_3h": stretch.get("crossings"),
        "formation": form.get("geometry"), "formation_generation": form.get("generation"),
        "formation_maturity": form.get("maturity"), "local_regime": form.get("local_regime"),
        "compression_score": form.get("compression_score"), "formation_impulse_score": form.get("impulse_score_geom"),
        "contraction_ratio": form.get("contraction_ratio"),
        "formation_range9": form.get("range9"), "formation_prior_range9": form.get("prior_range9"),
        "high_slope9": form.get("high_slope"), "low_slope9": form.get("low_slope"),
        "breakout": form.get("breakout"), "breakout_failure": form.get("failure"),
        "impulse_direction": impulse.get("direction"), "impulse_score": impulse.get("score"),
        "btc_change3": impulse.get("ch3"), "btc_change6": impulse.get("ch6"),
        "btc_change9": impulse.get("ch9"), "btc_change30": impulse.get("ch30"),
        "btc_change60": impulse.get("ch60"), "btc_eff30": impulse.get("eff30"),
        "btc_range60": impulse.get("range60"),
        "yes_ask": yes_ask, "no_ask": no_ask,
        "l2_yes_bid": l2.get("yes_bid"), "l2_yes_ask": l2.get("yes_ask"),
        "l2_yes_bid_size": l2.get("yes_bid_size"), "l2_yes_ask_size": l2.get("yes_ask_size"),
        "l2_yes_depth5": l2.get("yes_depth5"), "l2_no_depth5": l2.get("no_depth5"),
        "l2_book_imbalance": l2.get("book_imbalance"), "l2_microprice": l2.get("microprice"),
        "flow3": l2.get("flow3"), "flow6": l2.get("flow6"), "flow9": l2.get("flow9"),
        "price_ema9_distance": extension.get("price_ema9_distance"),
        "ema9_ema30_distance": extension.get("ema9_ema30_distance"),
        "norm_price_ema9": extension.get("norm_price_ema9"), "norm_ema_gap": extension.get("norm_ema_gap"),
        "double_extension_score": extension.get("double_extension_score"),
        "extension_direction": extension.get("extension_direction"), "exhaustion_score": extension.get("exhaustion_score"),
        "edge_sniper_armed": extension.get("edge_sniper_armed"), "edge_counter_side": extension.get("edge_counter_side"),
        "extension_confirming_369": extension.get("extension_confirming_369"), "extension_fading_369": extension.get("extension_fading_369"),
        "edge_limit_id": edge_watch.get("id") if edge_watch else None, "edge_limit_side": edge_watch.get("side") if edge_watch else None,
        "edge_limit_price": edge_watch.get("limit") if edge_watch else None,
        "v83_thesis_yes": v83_structural_thesis("YES", now).get("state"),
        "v83_thesis_yes_score": v83_structural_thesis("YES", now).get("score"),
        "v83_thesis_no": v83_structural_thesis("NO", now).get("state"),
        "v83_thesis_no_score": v83_structural_thesis("NO", now).get("score"),
        "v83_rejection_state": v83_rejection_quality(now).get("state"),
        "v83_rejection_strength": v83_rejection_quality(now).get("strength"),
        "v83_rejection_tests": v83_rejection_quality(now).get("tests"),
        "v83_rebound_ratio": v83_rejection_quality(now).get("rebound_ratio"),
    }


def maybe_log_structure(ticker, close_ts, yes_ask, no_ask, now=None):
    global observer_last_log_time
    if now is None:
        now = time.time()
    if now - observer_last_log_time < OBSERVER_LOG_SECONDS:
        return
    observer_last_log_time = now
    snap = structure_snapshot(ticker, close_ts, yes_ask, no_ask, now)
    form_for_event = formation_state(observer_candles(), macro_leg_state(observer_candles()))
    event_id, event_age = update_formation_event(form_for_event, now)
    snap["formation_event_id"] = event_id
    snap["formation_event_age_min"] = event_age
    fields = STRUCTURE_FIELDS
    with open(STRUCTURE_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([snap.get(k, "") for k in fields])


# ============================================================
# CSV LOGGING
# ============================================================

STRUCTURE_FIELDS = [
    "timestamp", "ticker", "btc_price", "target_price", "target_distance",
    "seconds_left", "contract_elapsed", "phase",
    "macro_direction", "macro_distance", "macro_age_min", "macro_start_price", "macro_end_price", "parent_maturity",
    "ema9_side", "ema9_duration_min", "ema9_distance", "ema9_max_stretch",
    "ema9_slope6", "ema30_slope6", "ema_gap", "ema_gap_state", "ema9_crossings_3h",
    "formation", "formation_generation", "formation_maturity", "local_regime",
    "compression_score", "formation_impulse_score", "formation_event_id", "formation_event_age_min", "contraction_ratio",
    "formation_range9", "formation_prior_range9", "high_slope9", "low_slope9",
    "breakout", "breakout_failure",
    "impulse_direction", "impulse_score", "btc_change3", "btc_change6", "btc_change9",
    "btc_change30", "btc_change60", "btc_eff30", "btc_range60",
    "yes_ask", "no_ask", "l2_yes_bid", "l2_yes_ask", "l2_yes_bid_size", "l2_yes_ask_size",
    "l2_yes_depth5", "l2_no_depth5", "l2_book_imbalance", "l2_microprice", "flow3", "flow6", "flow9",
    "price_ema9_distance", "ema9_ema30_distance", "norm_price_ema9", "norm_ema_gap",
    "double_extension_score", "extension_direction", "exhaustion_score", "edge_sniper_armed", "edge_counter_side",
    "extension_confirming_369", "extension_fading_369", "edge_limit_id", "edge_limit_side", "edge_limit_price",
    "v83_thesis_yes", "v83_thesis_yes_score", "v83_thesis_no", "v83_thesis_no_score",
    "v83_rejection_state", "v83_rejection_strength", "v83_rejection_tests", "v83_rebound_ratio",
]

EXPIRY_SNAPSHOT_FIELDS = [
    "epoch_ms", "timestamp", "ticker", "seconds_left", "btc_price", "target_price", "target_distance",
    "target_side", "yes_ask", "no_ask", "btc_ema9", "btc_ema30", "target_ema_position", "ordering",
    "structural_side", "target_to_ema9", "target_to_ema30", "price_to_ema9", "price_to_ema30",
    "target_distance_norm60", "ema9_slope6", "ema30_slope6", "ema_gap", "ema_gap_state",
    "ema9_arc_stage", "ema9_arc_direction", "ema9_curvature",
    "btc_change3", "btc_change6", "btc_change9", "btc_change15", "btc_change30", "btc_change60",
    "btc_range30", "btc_range60", "btc_eff30", "btc_eff60", "crossed_now", "hold_seconds",
    "cross_count_30", "cross_count_60", "cross_count_90", "last_cross_spacing", "avg_cross_spacing_90",
    "cross_spacing_trend",
]

EXPIRY_EVENT_FIELDS = [
    "timestamp", "event_id", "ticker", "event_kind", "status", "reason", "seconds_left_start",
    "side_start", "btc_start", "target", "distance_start", "yes_start", "no_start", "ema9_start", "ema30_start",
    "target_ema_position", "ordering", "structural_side", "ema9_slope6", "ema30_slope6", "ema9_curvature",
    "btc_change3", "btc_change6", "btc_change9", "btc_range60", "cross_count_30", "cross_count_60",
    "cross_count_90", "last_cross_spacing", "avg_cross_spacing_90", "cross_spacing_trend", "hold_seconds",
    "reversed_within_30s", "reversal_age_seconds",
]
for _h in EXPIRY_EVENT_HORIZONS:
    EXPIRY_EVENT_FIELDS.extend([f"btc_{_h}s", f"dist_{_h}s", f"yes_{_h}s", f"no_{_h}s", f"side_{_h}s"])

LAG_FIELDS = [
    "timestamp", "ticker", "direction", "btc_start", "yes_start", "no_start",
    "btc_change3_at_trigger", "btc_change6_at_trigger", "btc_change9_at_trigger",
    "btc_change30_at_trigger", "btc_eff30_at_trigger",
    "btc_3s", "yes_3s", "no_3s", "btc_6s", "yes_6s", "no_6s",
    "btc_9s", "yes_9s", "no_9s",
]


def initialize_log():
    files_and_headers = {
        EXPIRY_SNAPSHOT_LOG_FILE: EXPIRY_SNAPSHOT_FIELDS,
        EXPIRY_EVENT_LOG_FILE: EXPIRY_EVENT_FIELDS,
        STRUCTURE_LOG_FILE: STRUCTURE_FIELDS,
        LAG_LOG_FILE: LAG_FIELDS,
        EXTENSION_LOG_FILE: [
            "timestamp", "event_id", "ticker", "extension_direction", "counter_side",
            "arm_score", "arm_exhaustion", "start_ask", "limit_price", "yes_ask", "no_ask",
            "status", "reason", "age_seconds", "btc_price", "price_ema9_distance",
            "ema9_ema30_distance", "norm_price_ema9", "norm_ema_gap",
            "current_extension_score", "current_exhaustion_score",
        ],
        CHOP_SHADOW_LOG_FILE: [
            "timestamp", "event", "ticker", "side", "entry_ask", "current_ask",
            "roi_pct", "mfe_pct", "mae_pct", "reason", "seconds_left",
            "btc_price", "target_price", "target_distance", "ema9", "ema30",
            "arc_stage", "arc_direction", "chop_edge", "chop_low", "chop_high",
            "range60", "eff60", "thesis_advantage", "candidate_grade"
        ],
        FLASH_LOG_FILE: [
            "timestamp", "ticker", "candidate_side", "condition", "btc_price",
            "target_price", "target_distance", "seconds_left", "yes_ask", "no_ask",
            "btc_change_3s", "btc_change_6s", "btc_change_9s", "btc_range_60s",
            "ema9", "ema30", "own_thesis_score", "opposite_thesis_score",
            "thesis_advantage"
        ],
        LOG_FILE: [
            "timestamp", "ticker", "side", "current_ask",
            "ask_90s", "ask_75s", "ask_60s",
            "m90_75", "m90_60",
            "kalshi_ema_9_1m", "kalshi_ema_30_1m",
            "btc_price", "btc_ema_9_1m", "btc_ema_30_1m",
            "btc_ema9_above_ema30", "btc_price_above_ema9",
            "btc_move_from_contract_start", "seconds_to_close", "setup_grade",
            "signal_grade", "a_plus_score", "a_plus_reasons", "session", "daypart", "et_hour",
            "target_price", "target_distance", "favorable_cushion",
            "btc_range_30s", "btc_range_60s", "btc_range_180s",
            "btc_current_1m_range", "btc_avg_5m_candle_range", "btc_volume_ratio",
            "contract_phase", "contract_elapsed_seconds", "btc_change_60s",
            "btc_trend_efficiency_60s", "early_exception", "early_exception_reasons",
            "strategy", "market_regime", "chop_low", "chop_high", "chop_width", "chop_edge", "trade_intent",
        ],
        RESULT_LOG_FILE: [
            "timestamp", "ticker", "result", "settlement_time"
        ],
        REVERSAL_LOG_FILE: [
            "timestamp", "ticker", "btc_start", "btc_now",
            "btc_move", "threshold", "seconds_to_close",
            "suggested_next_side"
        ],
        PAPER_LOG_FILE: [
            "timestamp", "event", "trade_id", "ticker", "side",
            "qty", "entry_ask", "exit_bid", "cost", "value",
            "pnl", "roi_pct", "reason", "mfe_pct", "mae_pct",
            "seconds_to_close", "target", "btc_price",
            "btc_ema_9_1m", "btc_ema_30_1m", "setup_grade", "signal_grade",
            "stake_cap", "session", "daypart", "et_hour", "target_price", "target_distance",
            "favorable_cushion", "btc_range_30s", "btc_range_60s", "btc_range_180s",
            "btc_current_1m_range", "btc_avg_5m_candle_range", "btc_volume_ratio",
            "contract_phase", "contract_elapsed_seconds", "btc_change_60s",
            "btc_trend_efficiency_60s", "early_exception", "early_exception_reasons",
            "strategy", "market_regime", "chop_low", "chop_high", "chop_width", "chop_edge",
            "trade_intent", "cumulative_pnl"
        ],
    }

    for path, header in files_and_headers.items():
        if os.path.exists(path):
            continue
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)


def log_signal(ticker, side, signal):
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            ticker, side,
            signal["price"], signal["price_90"],
            signal["price_75"], signal["price_60"],
            signal["m90_75"], signal["m90_60"],
            signal.get("ema_9"), signal.get("ema_30"),
            signal.get("btc_price"), signal.get("btc_ema_9"),
            signal.get("btc_ema_30"),
            signal.get("btc_ema9_above_ema30", ""),
            signal.get("btc_price_above_ema9", ""),
            signal.get("btc_move_from_contract_start"),
            signal.get("seconds_to_close"), signal.get("setup_grade", ""),
            signal.get("signal_grade", ""), signal.get("a_plus_score", ""),
            signal.get("a_plus_reasons", ""), signal.get("session", ""),
            signal.get("daypart", ""), signal.get("et_hour", ""),
            signal.get("target_price"), signal.get("target_distance"),
            signal.get("favorable_cushion"), signal.get("btc_range_30s"),
            signal.get("btc_range_60s"), signal.get("btc_range_180s"),
            signal.get("btc_current_1m_range"), signal.get("btc_avg_5m_candle_range"),
            signal.get("btc_volume_ratio"), signal.get("contract_phase", ""),
            signal.get("contract_elapsed_seconds"), signal.get("btc_change_60s"),
            signal.get("btc_trend_efficiency_60s"), signal.get("early_exception", ""),
            signal.get("early_exception_reasons", ""),
            signal.get("strategy", "CORE"), signal.get("market_regime", ""),
            signal.get("chop_low"), signal.get("chop_high"), signal.get("chop_width"), signal.get("chop_edge", ""),
            signal.get("trade_intent", ""),
        ])


def log_reversal_watch(ticker, btc_start, btc_now, move, threshold, seconds_to_close):
    next_side = "NO" if move > 0 else "YES"
    with open(REVERSAL_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            ticker, btc_start, btc_now, move, threshold,
            round(seconds_to_close, 1), next_side,
        ])


def log_settlement(ticker, result, settlement_time):
    if ticker in logged_settlements:
        return
    with open(RESULT_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"),
            ticker, result, settlement_time or "",
        ])
    logged_settlements.add(ticker)


def log_paper_event(event, position, exit_bid=None, reason=""):
    global paper_realized_pnl

    value = ""
    pnl = ""
    roi_pct = ""
    if exit_bid is not None:
        value = position["qty"] * exit_bid
        pnl = value - position["cost"]
        roi_pct = (pnl / position["cost"] * 100) if position["cost"] else 0.0

    with open(PAPER_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"), event, position["trade_id"],
            position["ticker"], position["side"], position["qty"],
            position["entry_ask"], exit_bid if exit_bid is not None else "",
            position["cost"], value, pnl, roi_pct, reason,
            position.get("mfe_pct", 0.0), position.get("mae_pct", 0.0),
            position.get("seconds_to_close"), position.get("target", ""),
            position.get("btc_price"), position.get("btc_ema_9"),
            position.get("btc_ema_30"), position.get("setup_grade", ""),
            position.get("signal_grade", ""), position.get("stake_cap"),
            position.get("session", ""), position.get("daypart", ""), position.get("et_hour", ""),
            position.get("target_price"), position.get("target_distance"),
            position.get("favorable_cushion"), position.get("btc_range_30s"),
            position.get("btc_range_60s"), position.get("btc_range_180s"),
            position.get("btc_current_1m_range"), position.get("btc_avg_5m_candle_range"),
            position.get("btc_volume_ratio"), position.get("contract_phase", ""),
            position.get("contract_elapsed_seconds"), position.get("btc_change_60s"),
            position.get("btc_trend_efficiency_60s"), position.get("early_exception", ""),
            position.get("early_exception_reasons", ""),
            position.get("strategy", "CORE"), position.get("market_regime", ""),
            position.get("chop_low"), position.get("chop_high"), position.get("chop_width"), position.get("chop_edge", ""),
            position.get("trade_intent", ""), paper_realized_pnl,
        ])


def chop_box(seconds=180, now=None):
    """Rolling BTC chop box from live Coinbase ticks."""
    if now is None:
        now = time.time()
    vals = [p for ts, p in btc_tick_history if ts >= now - seconds]
    if len(vals) < 3:
        return None, None, None
    low, high = min(vals), max(vals)
    return low, high, high - low


def btc_structure(now=None):
    """Detect persistent HH/HL, LL/LH, or a genuine oscillating range."""
    if now is None:
        now = time.time()
    start = now - STRUCTURE_LOOKBACK_SECONDS
    pts = [(ts, p) for ts, p in btc_tick_history if ts >= start]
    if len(pts) < 8:
        return "UNKNOWN", 0

    buckets = []
    t = start
    while t < now:
        vals = [p for ts, p in pts if t <= ts < t + STRUCTURE_BUCKET_SECONDS]
        if vals:
            buckets.append((min(vals), max(vals), vals[-1]))
        t += STRUCTURE_BUCKET_SECONDS

    if len(buckets) < 4:
        return "UNKNOWN", 0

    recent = buckets[-4:]
    highs = [b[1] for b in recent]
    lows = [b[0] for b in recent]
    up = sum(
        highs[i] >= highs[i-1] + STRUCTURE_MIN_STEP and
        lows[i] >= lows[i-1] - STRUCTURE_MIN_STEP
        for i in range(1, len(recent))
    )
    down = sum(
        lows[i] <= lows[i-1] - STRUCTURE_MIN_STEP and
        highs[i] <= highs[i-1] + STRUCTURE_MIN_STEP
        for i in range(1, len(recent))
    )

    closes = [b[2] for b in buckets]
    diffs = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    dirs = [1 if d > STRUCTURE_MIN_STEP else -1 if d < -STRUCTURE_MIN_STEP else 0 for d in diffs]
    dirs = [d for d in dirs if d]
    flips = sum(dirs[i] != dirs[i-1] for i in range(1, len(dirs)))

    if up >= 2 and up > down:
        return "UPTREND", flips
    if down >= 2 and down > up:
        return "DOWNTREND", flips
    return "RANGE", flips


def sniper_distance_ok(target_distance, range60):
    """Reject Sniper setups that are too far from the Kalshi target."""
    if target_distance is None:
        return False
    fixed_limit = SNIPER_MAX_TARGET_DISTANCE_ABS
    dynamic_limit = (
        float(range60) * SNIPER_MAX_RANGE_MULTIPLE
        if range60 is not None else 0.0
    )
    allowed = max(fixed_limit, dynamic_limit)
    return abs(float(target_distance)) <= allowed


def late_distance_ok(seconds_left, target_distance):
    if seconds_left is None or target_distance is None:
        return True
    dist = abs(float(target_distance))
    if float(seconds_left) <= VERY_LATE_DISTANCE_FILTER_SECONDS:
        return dist <= VERY_LATE_MAX_TARGET_DISTANCE_ABS
    if float(seconds_left) <= LATE_DISTANCE_FILTER_SECONDS:
        return dist <= LATE_MAX_TARGET_DISTANCE_ABS
    return True

def chop_context(close_ts=None, now=None):
    """
    Detect a tradable oscillating regime and locate BTC inside its rolling box.
    CHOP_SNIPER is deliberately disabled in the first 2 minutes and with less
    than 3 minutes remaining, leaving the final minute to EXPIRY EDGE logic.
    """
    if now is None:
        now = time.time()
    phase, seconds_left, elapsed = contract_phase(close_ts, now)
    eff60 = btc_trend_efficiency(60, 5, now)
    r60 = btc_range(60, now)
    low, high, width = chop_box(180, now)

    eligible_time = (
        elapsed is not None and elapsed >= OBSERVATION_SECONDS
        and seconds_left is not None and seconds_left >= CHOP_SNIPER_MIN_SECONDS_LEFT
    )
    structure, direction_flips = btc_structure(now)
    is_chop = (
        eligible_time
        and eff60 is not None and eff60 <= CHOP_EFFICIENCY_MAX
        and r60 is not None and r60 >= CHOP_MIN_RANGE_60S
        and width is not None and width >= CHOP_MIN_RANGE_180S
        and structure not in ("UPTREND", "DOWNTREND")
        and direction_flips >= CHOP_MIN_DIRECTION_FLIPS
    )

    edge = "MIDDLE"
    if width is not None and width > 0 and btc_last_price is not None:
        pos = (btc_last_price - low) / width
        if pos <= CHOP_EDGE_FRACTION:
            edge = "LOWER"
        elif pos >= 1.0 - CHOP_EDGE_FRACTION:
            edge = "UPPER"

    return {
        "is_chop": bool(is_chop), "phase": phase, "seconds_left": seconds_left,
        "elapsed": elapsed, "eff60": eff60, "range60": r60,
        "low": low, "high": high, "width": width, "edge": edge,
        "structure": structure, "direction_flips": direction_flips,
    }



def v87_chop_shadow_observer(ticker, yes_ask, no_ask, close_ts=None):
    """Observer-only Chop/Edge strategy.

    Runs the current chop + EMA9 + parent-thesis logic, opens a *shadow*
    position, and manages it with V8.6/V8.7-style profit protection.
    It never touches paper_positions, trade counters, or PaperPnL.
    """
    global chop_shadow_position, chop_shadow_last_exit
    if not CHOP_SHADOW_ENABLED:
        return

    now = time.time()
    ctx = chop_context(close_ts)

    def write_shadow(event, side="", entry=None, current=None, roi=None, mfe=None, mae=None,
                     reason="", thesis_adv=None, grade=""):
        target = parse_target_price(active_target)
        dist = (btc_last_price - target) if (btc_last_price is not None and target is not None) else None
        arc = ema9_arc_state(now)
        with open(CHOP_SHADOW_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                time.strftime("%Y-%m-%d %H:%M:%S"), event, ticker, side,
                entry, current, None if roi is None else roi*100,
                None if mfe is None else mfe*100, None if mae is None else mae*100,
                reason, ctx.get("seconds_left"), btc_last_price, target, dist,
                btc_ema_9, btc_ema_30, arc.get("stage"), arc.get("direction"),
                ctx.get("edge"), ctx.get("low"), ctx.get("high"), ctx.get("range60"),
                ctx.get("eff60"), thesis_adv, grade
            ])

    # Manage an existing shadow position first.
    if chop_shadow_position is not None:
        p = chop_shadow_position
        side = p["side"]
        ask = yes_ask if side == "YES" else no_ask
        if ask is None or ask <= 0:
            return
        roi = (ask - p["entry"]) / p["entry"]
        p["mfe"] = max(p["mfe"], roi)
        p["mae"] = min(p["mae"], roi)

        arc_relation, arc = ema9_arc_relation(side, now)
        thesis_adv, own_thesis, opp_thesis = v85_thesis_advantage(side, now)
        reason = None

        # Use the same bird hierarchy as V8.6.
        bird_floor = None
        if p["mfe"] >= BIRD_23_TRIGGER:
            bird_floor = BIRD_23_FLOOR
        elif p["mfe"] >= BIRD_20_TRIGGER:
            bird_floor = BIRD_20_FLOOR
        elif p["mfe"] >= BIRD_17_TRIGGER:
            bird_floor = BIRD_17_FLOOR

        # In actual tight chop, harvest 22.5% unless EMA structure is still
        # clearly healthy enough to test "hold the bird" behavior.
        structure_alive = (
            arc_relation == "HEALTHY"
            and arc.get("stage") in ("BUILDING", "RELEASE", "EXPANDING", "LOADED_COIL")
        )
        if roi >= V84_SWIRL_SNIP_TP and not structure_alive:
            reason = "SHADOW_TP_22_5"
        elif bird_floor is not None and roi <= bird_floor and not structure_alive:
            reason = f"SHADOW_BIRD_FLOOR_{int(bird_floor*100)}"
        elif (
            thesis_adv <= -V85_PARENT_VETO_DIFF
            and own_thesis.get("state") == "FAILED"
            and opp_thesis.get("state") == "STRONG"
            and roi <= 0
        ):
            reason = "SHADOW_THESIS_FAILED"
        elif ctx.get("seconds_left") is not None and ctx["seconds_left"] <= 60 and roi > 0:
            reason = "SHADOW_LATE_BANK"
        elif ctx.get("seconds_left") is not None and ctx["seconds_left"] <= 20:
            reason = "SHADOW_EXPIRY_CLOSE"

        if reason:
            write_shadow("EXIT", side, p["entry"], ask, roi, p["mfe"], p["mae"],
                         reason, thesis_adv, p.get("grade",""))
            print(
                f"👁️ CHOP SHADOW EXIT | {side} {p['entry']:.3f}->{ask:.3f} "
                f"| ROI={roi*100:+.1f}% | MFE={p['mfe']*100:+.1f}% | {reason}"
            )
            chop_shadow_position = None
            chop_shadow_last_exit = now
        return

    # No shadow position: run full candidate logic.
    if not ctx.get("is_chop"):
        return
    if now - chop_shadow_last_exit < CHOP_SNIPER_COOLDOWN:
        return
    if ctx.get("edge") == "MIDDLE":
        return

    ch10 = btc_change(10, now)
    if ch10 is None:
        return

    if ctx["edge"] == "LOWER" and ch10 >= CHOP_REJECTION_MOVE_10S:
        side, ask = "YES", yes_ask
    elif ctx["edge"] == "UPPER" and ch10 <= -CHOP_REJECTION_MOVE_10S:
        side, ask = "NO", no_ask
    else:
        return

    # Current EMA9 arc-aware direction logic.
    if CHOP_ARC_AWARE_DIRECTION:
        arc = ema9_arc_state(now)
        astage, adir = arc.get("stage"), arc.get("direction")
        desired = None
        if astage in ("RELEASE", "BUILDING", "EXPANDING", "LOADED_COIL"):
            desired = "YES" if adir == "UP" else "NO" if adir == "DOWN" else None
        elif astage == "ROLLING":
            desired = "NO" if adir == "UP" else "YES" if adir == "DOWN" else None
        elif astage in ("MATURE", "EXTENDED"):
            curv = arc.get("curvature") or 0.0
            if adir == "UP" and curv <= -EMA9_ARC_CURVATURE_TURN:
                desired = "NO"
            elif adir == "DOWN" and curv >= EMA9_ARC_CURVATURE_TURN:
                desired = "YES"
            else:
                return
        elif astage == "DEAD_COIL":
            return
        if desired is not None and desired != side:
            side = desired
            ask = yes_ask if side == "YES" else no_ask

    if ask is None or ask <= 0 or ask > MAX_ENTRY_ASK:
        return

    thesis_adv, own_thesis, opp_thesis = v85_thesis_advantage(side, now)
    if thesis_adv <= -V85_PARENT_VETO_DIFF:
        reversal_ok, _ = v85_countertrend_exception_ok(side, now)
        if not reversal_ok:
            return

    target = parse_target_price(active_target)
    dist = (btc_last_price - target) if (btc_last_price is not None and target is not None) else None
    if not late_distance_ok(ctx["seconds_left"], dist):
        return
    if not sniper_distance_ok(dist, ctx.get("range60")):
        return

    structure_now, _ = btc_structure(now)
    if (side == "NO" and structure_now == "UPTREND") or (side == "YES" and structure_now == "DOWNTREND"):
        return

    arc = ema9_arc_state(now)
    grade = "A+ SHADOW" if abs(thesis_adv) >= V85_PARENT_VETO_DIFF and thesis_adv > 0 else "A SHADOW"
    chop_shadow_position = {
        "ticker": ticker, "side": side, "entry": ask, "ts": now,
        "mfe": 0.0, "mae": 0.0, "grade": grade
    }
    write_shadow("ENTRY", side, ask, ask, 0.0, 0.0, 0.0,
                 "EDGE_CHOP_OBSERVER", thesis_adv, grade)
    print(
        f"👁️ CHOP SHADOW ENTRY | {side} @ {ask:.3f} | {grade} "
        f"| {ctx['edge']} EDGE | arc={arc.get('stage')}/{arc.get('direction')} "
        f"| thesisΔ={thesis_adv:+d} | NO PAPER ORDER"
    )


def chop_sniper_try_enter(ticker, yes_ask, no_ask, close_ts=None):
    """
    Edge-only paper entry:
      lower edge + short-term rejection upward -> YES
      upper edge + short-term rejection downward -> NO
    No middle-of-box entries and only one sniper position at a time.
    """
    global paper_trade_counter, chop_sniper_last_state, chop_sniper_last_box

    ctx = chop_context(close_ts)
    chop_sniper_last_state = "CHOP_OBSERVER" if ctx["is_chop"] else "CORE"
    chop_sniper_last_box = (ctx["low"], ctx["high"])

    # V8.6: old Chop Sniper is observer-only. We still classify/log chop, but
    # it cannot create a paper position and it cannot block ordinary Core.
    if not CHOP_SNIPER_PAPER_ENABLED:
        return False

    if not ctx["is_chop"]:
        return False
    if any(p is not None for p in paper_positions.values()):
        return True
    if time.time() - chop_sniper_last_exit_time < CHOP_SNIPER_COOLDOWN:
        return True
    if ctx["edge"] == "MIDDLE":
        return True

    ch10 = btc_change(10)
    if ch10 is None:
        return True

    if ctx["edge"] == "LOWER" and ch10 >= CHOP_REJECTION_MOVE_10S:
        side, ask = "YES", yes_ask
    elif ctx["edge"] == "UPPER" and ch10 <= -CHOP_REJECTION_MOVE_10S:
        side, ask = "NO", no_ask
    else:
        return True

    # V8.1: Chop still decides WHEN an edge is interesting, but EMA9 arc
    # lifecycle can decide WHICH SIDE is sensible. Follow young arcs; fade a
    # confirmed rollover. Do not chase a merely mature/extended arc.
    if CHOP_ARC_AWARE_DIRECTION:
        arc = ema9_arc_state()
        astage, adir = arc.get("stage"), arc.get("direction")
        desired = None
        if astage in ("RELEASE", "BUILDING", "EXPANDING", "LOADED_COIL"):
            desired = "YES" if adir == "UP" else "NO" if adir == "DOWN" else None
        elif astage == "ROLLING":
            desired = "NO" if adir == "UP" else "YES" if adir == "DOWN" else None
        elif astage in ("MATURE", "EXTENDED"):
            # At the top/middle of an old arc, only fade once curvature is
            # actually turning; otherwise wait instead of blindly chasing.
            curv = arc.get("curvature") or 0.0
            if adir == "UP" and curv <= -EMA9_ARC_CURVATURE_TURN:
                desired = "NO"
            elif adir == "DOWN" and curv >= EMA9_ARC_CURVATURE_TURN:
                desired = "YES"
            else:
                return True
        elif astage == "DEAD_COIL":
            return True
        if desired is not None and desired != side:
            side = desired
            ask = yes_ask if side == "YES" else no_ask

    # V8.5 forensic result: Chop was the weak sleeve when fading a strong
    # continuous parent. Block large thesis conflicts unless real exhaustion
    # evidence exists, and prevent immediate repeat fades after a failed one.
    thesis_diff, own_thesis, opp_thesis = v85_thesis_advantage(side)
    if thesis_diff <= -V85_PARENT_VETO_DIFF:
        reversal_ok, reversal_reason = v85_countertrend_exception_ok(side)
        lock_ok, lock_reason = v85_countertrend_reentry_ok(side)
        if not reversal_ok or not lock_ok:
            return True

    if ask is None or ask <= 0 or ask > MAX_ENTRY_ASK:
        return True

    target_price_now = parse_target_price(active_target)
    target_distance_now = (
        btc_last_price - target_price_now
        if btc_last_price is not None and target_price_now is not None else None
    )
    if not late_distance_ok(ctx["seconds_left"], target_distance_now):
        return True

    if not sniper_distance_ok(target_distance_now, ctx.get("range60")):
        return True

    # Never fade an active staircase trend just because efficiency is low.
    structure_now, _ = btc_structure()
    if (side == "NO" and structure_now == "UPTREND") or (
        side == "YES" and structure_now == "DOWNTREND"
    ):
        return True

    qty = int(CHOP_SNIPER_STAKE // ask)
    if qty < 1:
        return True

    paper_trade_counter += 1
    cost = qty * ask
    target_price = parse_target_price(active_target)
    target_distance = (
        btc_last_price - target_price
        if btc_last_price is not None and target_price is not None else None
    )
    favorable = target_distance if side == "YES" else (-target_distance if target_distance is not None else None)
    session, daypart, et_hour = session_context()

    position = {
        "trade_id": paper_trade_counter, "ticker": ticker, "side": side,
        "qty": qty, "entry_ask": ask, "cost": cost, "entry_time": time.time(),
        "mfe_pct": 0.0, "mae_pct": 0.0, "seconds_to_close": ctx["seconds_left"],
        "target": active_target, "btc_price": btc_last_price,
        "btc_ema_9": btc_ema_9, "btc_ema_30": btc_ema_30,
        "setup_grade": "CHOP_EDGE", "signal_grade": "SNIPER",
        "stake_cap": CHOP_SNIPER_STAKE, "session": session, "daypart": daypart, "et_hour": et_hour,
        "target_price": target_price, "target_distance": target_distance, "favorable_cushion": favorable,
        "btc_range_30s": btc_range(30), "btc_range_60s": ctx["range60"],
        "btc_range_180s": ctx["width"], "btc_current_1m_range": current_candle_range(),
        "btc_avg_5m_candle_range": recent_avg_candle_range(5),
        "btc_volume_ratio": recent_volume_ratio(5), "contract_phase": "CHOP_SNIPER",
        "contract_elapsed_seconds": ctx["elapsed"], "btc_change_60s": btc_change(60),
        "btc_trend_efficiency_60s": ctx["eff60"], "early_exception": False,
        "early_exception_reasons": "", "early_trade": False, "milestones_hit": set(),
        "strategy": "CHOP_SNIPER", "market_regime": "CHOP",
        "chop_low": ctx["low"], "chop_high": ctx["high"], "chop_width": ctx["width"],
        "chop_edge": ctx["edge"],
        "trade_intent": "SNIP",
        "v85_thesis_advantage_entry": thesis_diff,
        "v85_countertrend_entry": thesis_diff <= -V85_PARENT_VETO_DIFF,
    }
    paper_positions[side] = position
    contract_trade_ids.setdefault(ticker, []).append(position["trade_id"])
    log_paper_event("ENTRY", position)
    print()
    print(
        f"🎯 CHOP SNIPER $15 ENTRY | #{paper_trade_counter} {side} "
        f"| {qty} @ {ask:.3f} | box=${ctx['low']:,.0f}-${ctx['high']:,.0f} "
        f"| {ctx['edge']} EDGE | BTC10={ch10:+.1f}"
    )
    return True


def v923_mutex_entry_ok(ticker, side, now=None):
    """Enforce one directional thesis per Kalshi contract.

    If the opposite side is open in the same ticker, arm a FLIP_CANDIDATE and
    block the new entry.  After the old side closes, require a short confirmation
    delay before the opposite side may enter.  This prevents accidental hedging
    and same-tick YES<->NO ping-pong.
    """
    global v923_flip_candidate
    now = time.time() if now is None else now
    opposite = "NO" if side == "YES" else "YES"
    opp_pos = paper_positions.get(opposite)

    if opp_pos is not None and opp_pos.get("ticker") == ticker:
        prior = v923_flip_candidate
        if (
            prior.get("ticker") != ticker
            or prior.get("from_side") != opposite
            or prior.get("to_side") != side
        ):
            v923_flip_candidate = {
                "ticker": ticker,
                "from_side": opposite,
                "to_side": side,
                "armed_ts": now,
            }
            print(
                f"🔄 V9.2.3 FLIP CANDIDATE | {opposite} -> {side} "
                f"| same contract {ticker} | waiting for {opposite} exit"
            )
        return False, f"V923_MUTEX_{opposite}_OPEN"

    cand = v923_flip_candidate
    if cand.get("ticker") == ticker and cand.get("to_side") == side:
        age = now - float(cand.get("armed_ts") or 0.0)
        if age > V923_FLIP_CANDIDATE_TTL:
            v923_flip_candidate = {"ticker": None, "from_side": None, "to_side": None, "armed_ts": 0.0}
            return True, "V923_FLIP_EXPIRED_FRESH_SIGNAL"

        from_side = cand.get("from_side")
        since_exit = now - float(last_paper_exit_time.get(from_side, 0.0) or 0.0)
        if since_exit < V923_FLIP_CONFIRM_SECONDS:
            return False, f"V923_FLIP_CONFIRM_WAIT_{since_exit:.1f}s"

        # Old side is gone and the opposite signal survived the confirmation gap.
        v923_flip_candidate = {"ticker": None, "from_side": None, "to_side": None, "armed_ts": 0.0}
        print(f"✅ V9.2.3 CONTROLLED FLIP READY | {from_side} -> {side} | {ticker}")
        return True, "V923_CONTROLLED_FLIP_READY"

    return True, "V923_MUTEX_CLEAR"


def paper_enter(ticker, side, ask, signal):
    global paper_trade_counter

    mutex_ok, mutex_reason = v923_mutex_entry_ok(ticker, side, time.time())
    if not mutex_ok:
        signal["early_exception_reasons"] = (
            (signal.get("early_exception_reasons") or "")
            + (";" if signal.get("early_exception_reasons") else "")
            + mutex_reason
        )
        return False

    if paper_positions[side] is not None:
        return False
    if time.time() - last_paper_exit_time[side] < PAPER_REENTRY_COOLDOWN:
        return False
    if ask <= 0:
        return False

    elapsed = signal.get("contract_elapsed_seconds")
    is_early_trade = (
        elapsed is not None
        and 0 <= float(elapsed) < EARLY_PROFIT_WINDOW_SECONDS
    )
    stake_cap = (
        A_PLUS_PAPER_STAKE
        if signal.get("signal_grade") == "A+"
        else PAPER_STAKE
    )
    qty = int(stake_cap // ask)
    if qty < 1:
        return False

    paper_trade_counter += 1
    cost = qty * ask
    position = {
        "trade_id": paper_trade_counter, "ticker": ticker, "side": side,
        "qty": qty, "entry_ask": ask, "cost": cost, "entry_time": time.time(),
        "mfe_pct": 0.0, "mae_pct": 0.0,
        "seconds_to_close": signal.get("seconds_to_close"),
        "target": active_target, "btc_price": signal.get("btc_price"),
        "btc_ema_9": signal.get("btc_ema_9"), "btc_ema_30": signal.get("btc_ema_30"),
        "setup_grade": signal.get("setup_grade", ""), "signal_grade": signal.get("signal_grade", ""),
        "stake_cap": stake_cap, "session": signal.get("session", ""),
        "daypart": signal.get("daypart", ""), "et_hour": signal.get("et_hour", ""),
        "target_price": signal.get("target_price"), "target_distance": signal.get("target_distance"),
        "favorable_cushion": signal.get("favorable_cushion"),
        "btc_range_30s": signal.get("btc_range_30s"), "btc_range_60s": signal.get("btc_range_60s"),
        "btc_range_180s": signal.get("btc_range_180s"),
        "btc_current_1m_range": signal.get("btc_current_1m_range"),
        "btc_avg_5m_candle_range": signal.get("btc_avg_5m_candle_range"),
        "btc_volume_ratio": signal.get("btc_volume_ratio"),
        "contract_phase": signal.get("contract_phase", ""),
        "contract_elapsed_seconds": signal.get("contract_elapsed_seconds"),
        "btc_change_60s": signal.get("btc_change_60s"),
        "btc_trend_efficiency_60s": signal.get("btc_trend_efficiency_60s"),
        "early_exception": signal.get("early_exception", False),
        "early_exception_reasons": signal.get("early_exception_reasons", ""),
        "early_trade": signal.get("early_trade", is_early_trade),
        "milestones_hit": set(),
        "strategy": signal.get("strategy", "CORE"),
        "market_regime": signal.get("market_regime", "CORE"),
        "chop_low": signal.get("chop_low"), "chop_high": signal.get("chop_high"),
        "chop_width": signal.get("chop_width"), "chop_edge": signal.get("chop_edge", ""),
        "ema9_arc_entry_stage": signal.get("ema9_arc_stage", ""),
        "ema9_arc_entry_direction": signal.get("ema9_arc_direction", ""),
        "ema9_arc_broken_since": None,
        "trade_intent": signal.get("trade_intent") or v85_trade_intent(side, signal),
        "v85_thesis_advantage_entry": v85_thesis_advantage(side)[0],
        "v85_countertrend_entry": v85_thesis_advantage(side)[0] <= -V85_PARENT_VETO_DIFF,
    }
    paper_positions[side] = position
    contract_trade_ids.setdefault(ticker, []).append(position["trade_id"])
    log_paper_event("ENTRY", position)
    _yes = ask if side == "YES" else None
    _no = ask if side == "NO" else None
    v91_legacy_audit("ENTRY", position, yes_ask=_yes, no_ask=_no, reason="LEGACY_ENTRY")
    grade = position.get("signal_grade") or position.get("setup_grade")
    print(f"💵 PAPER ${stake_cap:.0f} ENTRY | #{paper_trade_counter} {side} {grade} | {qty} contracts @ {ask:.3f} | cost=${cost:.2f}")
    return True


def record_contract_trade(position, exit_bid, pnl, reason):
    # V9.1 observer-only legacy audit. Reconstruct top-of-book side loosely from
    # the exit bid; missing opposite ask is left blank rather than invented.
    if position.get("side") == "YES":
        _yes_ask, _no_ask = None, (1.0-exit_bid if exit_bid is not None else None)
    else:
        _yes_ask, _no_ask = (1.0-exit_bid if exit_bid is not None else None), None
    v91_legacy_audit("EXIT", position, yes_ask=_yes_ask, no_ask=_no_ask, exit_bid=exit_bid, pnl=pnl, reason=reason)
    # V8.8: central loss memory for fresh-thesis re-entry protection.
    if pnl < 0:
        side = position.get("side")
        if side in ("YES", "NO"):
            try:
                adv = v85_thesis_advantage(side)[0]
            except Exception:
                adv = 0
            try:
                arc = ema9_arc_state()
                arc_stage = arc.get("stage", "")
                arc_direction = arc.get("direction", "")
            except Exception:
                arc_stage, arc_direction = "", ""
            v88_last_loss[side] = {
                "ts": time.time(),
                "entry_ask": position.get("entry_ask"),
                "exit_bid": exit_bid,
                "thesis_adv": adv,
                "arc_stage": arc_stage,
                "arc_direction": arc_direction,
                "reason": reason,
            }

    contract_trade_records.setdefault(position["ticker"], []).append({
        "trade_id": position["trade_id"],
        "side": position["side"],
        "grade": position.get("signal_grade") or position.get("setup_grade", ""),
        "entry": position["entry_ask"],
        "exit": exit_bid,
        "pnl": pnl,
        "reason": reason,
        "mfe_pct": position.get("mfe_pct", 0.0),
        "mae_pct": position.get("mae_pct", 0.0),
        "stake_cap": position.get("stake_cap", PAPER_STAKE),
    })


def print_contract_summary(ticker):
    trades = contract_trade_records.get(ticker, [])
    print()
    print("=" * 68)
    print("📊 CONTRACT SUMMARY")
    print("=" * 68)
    print("Ticker:", ticker)
    if not trades:
        print("Trades: 0 | Contract P&L: $+0.00")
        print(f"Running P&L: ${paper_realized_pnl:+.2f}")
        print("=" * 68)
        return

    for t in trades:
        print(
            f"#{t['trade_id']:>3} | {t['side']:<3} | {t['grade']:<9} "
            f"| {t['entry']:.3f} -> {t['exit']:.3f} "
            f"| P&L=${t['pnl']:+.2f} | peak={t['mfe_pct']:+.1f}% "
            f"| {t['reason']}"
        )
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    subtotal = sum(t["pnl"] for t in trades)
    print("-" * 68)
    print(f"Trades: {len(trades)} | Wins: {wins} | Losses: {losses}")
    print(f"Contract P&L: ${subtotal:+.2f}")
    print(f"Running P&L:  ${paper_realized_pnl:+.2f}")
    print("=" * 68)


def copilot_snapshot(close_ts, yes_ask, no_ask):
    """Compact live decision-support view. Observational only; paper trading remains rule-driven."""
    now = time.time()
    phase, seconds_left, elapsed = contract_phase(close_ts, now)
    target = parse_target_price(active_target)
    dist = (btc_last_price - target) if btc_last_price is not None and target is not None else None
    ch60 = btc_change(60, now)
    eff60 = btc_trend_efficiency(60, 5, now)
    r60 = btc_range(60, now)
    vr = recent_volume_ratio(5)

    if btc_ema_9 is None or btc_ema_30 is None:
        ema_state = "WARMING"
    elif btc_ema_9 > btc_ema_30:
        ema_state = "YES"
    elif btc_ema_9 < btc_ema_30:
        ema_state = "NO"
    else:
        ema_state = "FLAT"

    # Simple market-state label: efficiency says whether recent BTC movement is
    # directional or back-and-forth; range prevents tiny drift from looking strong.
    if eff60 is None or r60 is None:
        state = "WARMING"
    elif eff60 < 0.35:
        state = "CHOP"
    elif eff60 >= 0.60 and r60 >= 30:
        state = "TREND"
    else:
        state = "MIXED"

    # Final minute is not a normal momentum-entry phase. Surface an expiry edge
    # only when BTC has a meaningful target cushion, recent movement is not aimed
    # hard back through the target, and the Kalshi side is still priced below 90c.
    edge = "NONE"
    if seconds_left is not None and seconds_left <= EXPIRY_MODE_SECONDS and dist is not None:
        velocity = ch60 or 0.0
        cushion_floor = max(25.0, (r60 or 0.0) * 0.50)
        if dist >= cushion_floor and velocity > -max(20.0, abs(dist) * 0.50) and yes_ask is not None and yes_ask < 0.90:
            edge = "YES"
        elif dist <= -cushion_floor and velocity < max(20.0, abs(dist) * 0.50) and no_ask is not None and no_ask < 0.90:
            edge = "NO"

    if phase == "OBSERVE":
        action = "WATCH"
    elif seconds_left is not None and seconds_left <= EXPIRY_MODE_SECONDS:
        action = f"EXPIRY EDGE {edge}" if edge != "NONE" else "NO NEW TRADE"
    elif state == "CHOP":
        ctx = chop_context(close_ts, now)
        cooldown_left = max(0, int(CHOP_SNIPER_COOLDOWN - (time.time() - chop_sniper_last_exit_time)))
        if ctx["is_chop"]:
            if cooldown_left > 0:
                action = f"CHOP SNIPER REST {cooldown_left}s"
            elif ctx["edge"] in ("LOWER", "UPPER"):
                action = f"CHOP SNIPER {ctx['edge']} EDGE"
            else:
                action = "CHOP SNIPER WAIT MIDDLE"
        else:
            action = "CAUTION / CHOP"
    elif state == "TREND":
        action = f"TREND {ema_state}" if ema_state in ("YES", "NO") else "TREND"
    else:
        action = "SELECTIVE"

    def fmt(v, spec):
        return format(v, spec) if v is not None else "---"

    # V7.6 compact parent/local observer labels for live visual comparison.
    obs_candles = observer_candles()
    obs_macro = macro_leg_state(obs_candles)
    obs_stretch = ema_stretch_state(obs_candles)
    obs_form = formation_state(obs_candles, obs_macro)
    obs_impulse = impulse_observer_state(now)
    obs_l2 = level2_snapshot(now)

    left = f"{seconds_left:4.0f}s" if seconds_left is not None else "---"
    return (
        f"COPILOT | {action} | {state} | left={left} | "
        f"targetΔ={fmt(dist, '+.0f')} | BTC60={fmt(ch60, '+.0f')} "
        f"range60={fmt(r60, '.0f')} eff={fmt(eff60, '.2f')} "
        f"EMA={ema_state} vol={fmt(vr, '.2f')}x"
        + (
            f" | box={fmt(chop_sniper_last_box[0], '.0f')}-{fmt(chop_sniper_last_box[1], '.0f')}"
            if state == "CHOP" and chop_sniper_last_box[0] is not None else ""
        )
        + f" | PARENT={obs_macro.get('direction','---')}/{obs_macro.get('maturity','---')} {fmt(obs_macro.get('distance'), '+.0f')}"
        + f" | LOCAL={obs_form.get('local_regime','---')}"
        + f" | F={obs_form.get('geometry','---')} G{obs_form.get('generation','-')}/{obs_form.get('maturity','---')} C{obs_form.get('compression_score',0)}"
        + f" | E9={obs_stretch.get('side','---')} {fmt(obs_stretch.get('distance'), '+.0f')}"
        + (lambda a: f" | ARC={a.get('stage','---')}/{a.get('direction','---')} k={fmt(a.get('curvature'), '+.1f')}")(ema9_arc_state(now))
        + f" | IMP={obs_impulse.get('direction','NONE')}/{obs_impulse.get('score',0)}"
        + f" | L2={fmt(obs_l2.get('book_imbalance'), '+.2f')} F3/6/9={fmt(obs_l2.get('flow3'), '+.2f')}/{fmt(obs_l2.get('flow6'), '+.2f')}/{fmt(obs_l2.get('flow9'), '+.2f')}"
    )


def ema9_arc_state(now=None):
    """Classify the live EMA9 shape around EMA30 for V8.1 paper decisions.

    This is intentionally simple and auditable for the 1-2 hour experiment.
    Direction comes from EMA9-vs-EMA30 geometry; stage comes from gap size,
    slope, curvature and recent compression/expansion.
    """
    if now is None:
        now = time.time()
    candles = observer_candles()
    if len(candles) < EMA_SLOW_PERIOD + 12:
        return {"stage": "WARMING", "direction": "NONE", "health": "UNKNOWN"}

    closes = [c["close"] for c in candles]
    e9 = _ema_series(closes, EMA_FAST_PERIOD)
    e30 = _ema_series(closes, EMA_SLOW_PERIOD)
    i = len(closes) - 1
    if e9[i] is None or e30[i] is None:
        return {"stage": "WARMING", "direction": "NONE", "health": "UNKNOWN"}

    gap = e9[i] - e30[i]
    price_gap = closes[i] - e9[i]
    slope_now = _safe_slope([x for x in e9[-6:] if x is not None]) or 0.0
    prior_slice = [x for x in e9[-12:-6] if x is not None]
    slope_prev = _safe_slope(prior_slice) if len(prior_slice) >= 2 else slope_now
    slope_prev = slope_prev or 0.0
    curvature = slope_now - slope_prev
    slope30 = _safe_slope([x for x in e30[-6:] if x is not None]) or 0.0
    r60 = btc_range(60, now) or 1.0

    # Recent EMA9/30 crossing count, using the last 9 candles.
    rels = []
    for j in range(max(0, len(closes)-9), len(closes)):
        if e9[j] is None or e30[j] is None:
            continue
        rels.append(1 if e9[j] > e30[j] else -1 if e9[j] < e30[j] else 0)
    crosses = sum(1 for a,b in zip(rels, rels[1:]) if a and b and a != b)

    prev_gap = None
    if len(e9) >= 4 and e9[-4] is not None and e30[-4] is not None:
        prev_gap = e9[-4] - e30[-4]
    expanding = prev_gap is not None and abs(gap) > abs(prev_gap) + 1.0
    contracting = prev_gap is not None and abs(gap) < abs(prev_gap) - 1.0

    direction = "UP" if gap > 0 else "DOWN" if gap < 0 else ("UP" if slope_now > 0 else "DOWN" if slope_now < 0 else "NONE")
    dir_sign = 1 if direction == "UP" else -1 if direction == "DOWN" else 0
    slope_favorable = dir_sign != 0 and slope_now * dir_sign >= EMA9_ARC_MIN_SLOPE
    curve_against = dir_sign != 0 and curvature * dir_sign <= -EMA9_ARC_CURVATURE_TURN
    price_aligned = dir_sign != 0 and price_gap * dir_sign >= 0

    norm_gap = abs(gap) / max(1.0, r60)
    norm_price = abs(price_gap) / max(1.0, r60)
    coil = norm_gap <= EMA9_ARC_COIL_GAP_RANGE_FRAC or crosses >= 2
    extended = norm_gap >= EMA9_ARC_EXTENDED_GAP_RANGE_FRAC and norm_price >= EMA9_ARC_EXTENDED_PRICE_RANGE_FRAC

    if coil:
        # A coil becomes loaded when EMA9 is already curling decisively out.
        if abs(slope_now) >= EMA9_ARC_MIN_SLOPE and abs(curvature) >= EMA9_ARC_CURVATURE_TURN and price_aligned:
            stage = "LOADED_COIL"
        else:
            stage = "DEAD_COIL"
    elif curve_against and (contracting or not price_aligned):
        stage = "ROLLING"
    elif extended:
        stage = "EXTENDED"
    elif expanding and slope_favorable:
        # Small/moderate gap peeling away from EMA30 = release/building; larger gap = expansion.
        if norm_gap < 0.30:
            stage = "RELEASE"
        elif norm_gap < 0.60:
            stage = "BUILDING"
        else:
            stage = "EXPANDING"
    elif slope_favorable and price_aligned:
        stage = "MATURE"
    elif contracting:
        stage = "ROLLING"
    else:
        stage = "MATURE"

    return {
        "stage": stage, "direction": direction, "gap": gap, "price_gap": price_gap,
        "slope9": slope_now, "slope30": slope30, "curvature": curvature,
        "norm_gap": norm_gap, "norm_price_gap": norm_price, "crosses9": crosses,
        "expanding": expanding, "contracting": contracting, "price_aligned": price_aligned,
    }


def v86_arc_break_evidence(side, arc):
    """Count independent signs that the trade-side EMA9 arc has actually failed."""
    wanted = 1 if side == "YES" else -1
    opposite = "DOWN" if side == "YES" else "UP"
    score = 0
    reasons = []
    direction = arc.get("direction")
    slope9 = arc.get("slope9") or 0.0
    curvature = arc.get("curvature") or 0.0
    price_gap = arc.get("price_gap") or 0.0
    stage = arc.get("stage")

    if direction == opposite:
        score += 1; reasons.append("OPPOSITE_GAP")
    if slope9 * wanted <= -V86_ARC_BREAK_MIN_SLOPE:
        score += 1; reasons.append("SLOPE_FLIPPED")
    if price_gap * wanted < 0:
        score += 1; reasons.append("PRICE_LOST_E9")
    if curvature * wanted <= -V86_ARC_BREAK_MIN_CURVATURE:
        score += 1; reasons.append("CURVATURE_ROLLED")
    if stage == "ROLLING":
        score += 1; reasons.append("ROLLING")
    if direction == opposite and arc.get("expanding"):
        score += 1; reasons.append("OPPOSITE_EXPANDING")
    return score, reasons

def ema9_arc_relation(side, now=None):
    arc = ema9_arc_state(now)
    wanted = "UP" if side == "YES" else "DOWN"
    opposite = "DOWN" if wanted == "UP" else "UP"
    stage = arc.get("stage")
    direction = arc.get("direction")
    if stage == "WARMING":
        return "UNKNOWN", arc
    if direction == opposite and stage in ("RELEASE", "BUILDING", "EXPANDING", "EXTENDED"):
        return "BROKEN", arc
    if direction == wanted and stage in ("RELEASE", "BUILDING", "EXPANDING", "EXTENDED"):
        return "HEALTHY", arc
    if direction == wanted and stage == "MATURE":
        return "AGING", arc
    if stage == "ROLLING":
        return "WEAKENING" if direction == wanted else "BROKEN", arc
    if stage == "LOADED_COIL" and direction == wanted:
        return "HEALTHY", arc
    if stage == "DEAD_COIL":
        return "NEUTRAL", arc
    return "NEUTRAL", arc


def ema9_ancestry_state(now=None):
    """Continuous BTC EMA ancestry; deliberately independent of Kalshi ticker boundaries.

    Returns the most recent established EMA9/30 side, approach/rejection state,
    and whether current curvature is anticipating a cross before it is complete.
    """
    now = time.time() if now is None else now
    candles = observer_candles()
    if len(candles) < EMA_SLOW_PERIOD + 12:
        return {"ancestry": "NONE", "setup": "WARMING"}
    closes = [c["close"] for c in candles]
    e9 = _ema_series(closes, EMA_FAST_PERIOD); e30 = _ema_series(closes, EMA_SLOW_PERIOD)
    i = len(closes)-1
    if e9[i] is None or e30[i] is None:
        return {"ancestry": "NONE", "setup": "WARMING"}
    gaps=[(e9[j]-e30[j]) if e9[j] is not None and e30[j] is not None else None for j in range(len(closes))]
    # Established ancestry = most recent 3-bar persistence on one side. This survives contract rollover.
    ancestry="UP" if gaps[i] and gaps[i]>0 else "DOWN" if gaps[i] and gaps[i]<0 else "NONE"
    for j in range(i, max(EMA_SLOW_PERIOD, i-45), -1):
        vals=gaps[max(0,j-2):j+1]
        if len(vals)==3 and all(v is not None and v>0 for v in vals): ancestry="UP"; break
        if len(vals)==3 and all(v is not None and v<0 for v in vals): ancestry="DOWN"; break
    arc=ema9_arc_state(now)
    gap=arc.get("gap") or 0.0; curv=arc.get("curvature") or 0.0; slope9=arc.get("slope9") or 0.0
    r60=max(1.0, btc_range(60,now) or 1.0)
    near30=abs(gap) <= 0.30*r60
    price30=closes[i]-e30[i]
    setup="CONTINUATION"
    anticipated="NONE"
    # Failed recapture/retest of EMA30: continuation entry near the structural reference.
    if ancestry=="DOWN" and near30 and price30 <= 0.35*r60 and (curv < -0.8 or slope9 < 0):
        setup="EMA30_REJECTION_DOWN"; anticipated="DOWN"
    elif ancestry=="UP" and near30 and price30 >= -0.35*r60 and (curv > 0.8 or slope9 > 0):
        setup="EMA30_REJECTION_UP"; anticipated="UP"
    # Pre-cross anticipation: curvature and price lead while EMA9 is still on old side.
    if gap > 0 and near30 and curv <= -EMA9_ARC_ROLL_MIN_CURVATURE and closes[i] <= e9[i]:
        setup="PRE_CROSS_DOWN"; anticipated="DOWN"
    elif gap < 0 and near30 and curv >= EMA9_ARC_ROLL_MIN_CURVATURE and closes[i] >= e9[i]:
        setup="PRE_CROSS_UP"; anticipated="UP"
    return {"ancestry":ancestry,"setup":setup,"anticipated":anticipated,"near30":near30,"gap":gap,"price30":price30}


def v83_rejection_quality(now=None):
    """Estimate whether the current EMA30 rejection is strong, weak/fakeout, or pending.

    This intentionally follows EMA9 vs EMA30 more than raw price location. Price may
    briefly cross EMA30; what matters is whether EMA9 reaches/establishes across it,
    how curvature behaves, and whether separation after prior tests is shrinking.
    """
    now = time.time() if now is None else now
    candles = observer_candles()
    if len(candles) < EMA_SLOW_PERIOD + 15:
        return {"state":"WARMING","direction":"NONE","strength":0.0,"tests":0}
    closes=[c["close"] for c in candles]
    e9=_ema_series(closes, EMA_FAST_PERIOD); e30=_ema_series(closes, EMA_SLOW_PERIOD)
    i=len(closes)-1
    if e9[i] is None or e30[i] is None:
        return {"state":"WARMING","direction":"NONE","strength":0.0,"tests":0}
    r60=max(1.0, btc_range(60, now) or 1.0)
    gap=e9[i]-e30[i]
    arc=ema9_arc_state(now)
    curv=arc.get("curvature") or 0.0
    slope9=arc.get("slope9") or 0.0
    slope30=(e30[i]-e30[max(0,i-6)]) if e30[max(0,i-6)] is not None else 0.0

    # Count recent near-EMA30 approaches and measure the best separation achieved
    # after each approach. This is a lightweight ancestry measure across contracts.
    bars=min(len(closes)-1, REJECTION_LOOKBACK_MINUTES)
    near=[]
    for j in range(max(EMA_SLOW_PERIOD, i-bars), i+1):
        if e9[j] is None or e30[j] is None: continue
        # normalize against current 60s range; robust enough for observer/paper use.
        if abs(e9[j]-e30[j]) <= REJECTION_NEAR30_RANGE_FRAC*r60:
            if not near or j-near[-1] >= 3:
                near.append(j)
    strengths=[]
    for j in near[:-1]:
        end=min(i, j+6)
        vals=[abs(e9[k]-e30[k]) for k in range(j,end+1) if e9[k] is not None and e30[k] is not None]
        if vals: strengths.append(max(vals))
    current_strength=abs(gap)
    previous=max(strengths[-1:], default=None) if strengths else None
    ratio=(current_strength/previous) if previous and previous>0 else None

    direction="UP" if gap>0 else "DOWN" if gap<0 else "NONE"
    state="NEUTRAL"; strength=50.0
    # Rising EMA30 + EMA9 still above it = bullish rejection candidate even if price pierces 30.
    if gap>0 and slope30>0:
        strength=50 + min(25, max(0,curv)*5) + min(15,max(0,slope9)*1.5)
        if ratio is not None and ratio < WEAK_REJECTION_RATIO:
            state="WEAK_UP_REJECTION"; strength-=20
        elif curv >= REJECTION_MIN_CURVATURE or slope9>0:
            state="EMA30_REJECTION_UP"
        else:
            state="REJECTION_UP_PENDING"
    elif gap<0 and slope30<0:
        strength=50 + min(25, max(0,-curv)*5) + min(15,max(0,-slope9)*1.5)
        if ratio is not None and ratio < WEAK_REJECTION_RATIO:
            state="WEAK_DOWN_REJECTION"; strength-=20
        elif curv <= -REJECTION_MIN_CURVATURE or slope9<0:
            state="EMA30_REJECTION_DOWN"
        else:
            state="REJECTION_DOWN_PENDING"
    return {"state":state,"direction":direction,"strength":max(0,min(100,strength)),
            "tests":len(near),"rebound_ratio":ratio,"ema30_slope6":slope30,
            "gap":gap,"curvature":curv,"price30":closes[i]-e30[i]}


def v83_structural_thesis(side, now=None):
    """Persistent trade thesis independent of Kalshi ticker and individual position."""
    now=time.time() if now is None else now
    wanted="UP" if side=="YES" else "DOWN"
    opposite="DOWN" if wanted=="UP" else "UP"
    anc=ema9_ancestry_state(now)
    arc=ema9_arc_state(now)
    rej=v83_rejection_quality(now)
    impulse=impulse_observer_state(now)
    score=0
    reasons=[]
    if anc.get("ancestry")==wanted: score+=2; reasons.append("ANCESTRY")
    if anc.get("anticipated")==wanted: score+=3; reasons.append(anc.get("setup","ANTICIPATED"))
    if arc.get("direction")==wanted and arc.get("stage") in ("RELEASE","BUILDING","EXPANDING","LOADED_COIL","EXTENDED"): score+=2; reasons.append("ARC")
    if rej.get("state")==f"EMA30_REJECTION_{wanted}": score+=3; reasons.append("EMA30_REJECTION")
    if rej.get("state")==f"WEAK_{opposite}_REJECTION": score+=2; reasons.append("OPPOSITE_REJECTION_WEAK")
    impdir=impulse.get("direction")
    if impdir==wanted: score+=1; reasons.append("IMPULSE")
    if anc.get("anticipated")==opposite: score-=3
    if arc.get("direction")==opposite and arc.get("stage") in ("RELEASE","BUILDING","EXPANDING"): score-=3
    if rej.get("state")==f"EMA30_REJECTION_{opposite}": score-=3
    if impdir==opposite and (abs(impulse.get("ch9") or 0)>=STRUCTURAL_FAST_FAIL_MOMENTUM): score-=1
    state="STRONG" if score>=4 else "VALID" if score>=2 else "MIXED" if score>=0 else "FAILED"
    return {"state":state,"score":score,"reasons":"|".join(reasons),"ancestry":anc,"arc":arc,"rejection":rej}


def v83_structural_failure(side, now=None):
    th=v83_structural_thesis(side, now)
    return th.get("state")=="FAILED", th




def v85_thesis_advantage(side, now=None):
    """Own structural thesis score minus opposite-side score."""
    now = time.time() if now is None else now
    own = v83_structural_thesis(side, now)
    other_side = "NO" if side == "YES" else "YES"
    opp = v83_structural_thesis(other_side, now)
    return (own.get("score", 0) - opp.get("score", 0), own, opp)


def v88_exhaustion_pullback_ok(side, signal=None, now=None):
    """Early countertrend pullback: anticipate a tradable retracement, not a full trend reversal."""
    now = time.time() if now is None else now
    signal = signal or {}
    wanted = "UP" if side == "YES" else "DOWN"
    wanted_sign = 1 if wanted == "UP" else -1
    arc = ema9_arc_state(now)
    ext = extension_metrics(now)
    anc = ema9_ancestry_state(now)

    score = ext.get("double_extension_score") or 0
    exhaustion = ext.get("exhaustion_score") or 0
    counter = ext.get("edge_counter_side")
    curv = arc.get("curvature") or 0.0
    slope9 = arc.get("slope9") or 0.0
    ch3 = btc_change(3, now) or 0.0
    ch6 = btc_change(6, now) or 0.0
    ch9 = btc_change(9, now) or 0.0

    # Counter-side must match the proposed trade. We want curvature/micro-momentum
    # starting to turn, while the old arc is mature/extended/rolling.
    old_move_mature = arc.get("stage") in ("MATURE", "EXTENDED", "ROLLING")
    curvature_turn = curv * wanted_sign >= V88_EXHAUSTION_PULLBACK_MIN_CURVATURE
    micro_turn = max(ch3*wanted_sign, ch6*wanted_sign, ch9*wanted_sign) >= 3.0
    slope_weakening = slope9 * wanted_sign >= -1.0

    target = signal.get("target_price")
    if target is None:
        target = parse_target_price(active_target)
    dist = signal.get("target_distance")
    if dist is None and target is not None and btc_last_price is not None:
        dist = btc_last_price - target

    # For NO after a long UP run, BTC may still be above target; for YES after a
    # long DOWN run it may still be below. That cushion is desirable, not a veto.
    cushion_ok = False
    if dist is not None:
        cushion_ok = (side == "NO" and dist >= V88_EXHAUSTION_PULLBACK_MIN_TARGET_CUSHION) or \
                     (side == "YES" and dist <= -V88_EXHAUSTION_PULLBACK_MIN_TARGET_CUSHION)

    ok = (
        counter == side
        and score >= V88_EXHAUSTION_PULLBACK_MIN_EXTENSION
        and exhaustion >= V88_EXHAUSTION_PULLBACK_MIN_EXHAUSTION
        and old_move_mature
        and cushion_ok
        and (curvature_turn or (micro_turn and slope_weakening) or anc.get("anticipated") == wanted)
    )
    why = (
        f"EXHAUSTION_PULLBACK_S{score:.0f}_E{exhaustion:.0f}_"
        f"C{curv:+.1f}_D{(dist if dist is not None else 0):+.0f}"
    )
    return ok, why


def v88_remember_blocked_candidate(ticker, side, ask, thesis_score, setup, now=None):
    now = time.time() if now is None else now
    if not ticker or ask is None:
        return
    key = (ticker, side)
    old = v88_blocked_candidate.get(key)
    # Keep the cheapest observed candidate because that is the opportunity cost
    # against which a later chase should be judged.
    if old is None or now - old.get("ts", 0) > V88_BLOCK_MEMORY_TTL or ask < old.get("ask", 9):
        v88_blocked_candidate[key] = {
            "ask": float(ask), "ts": now, "thesis_score": thesis_score, "setup": setup
        }


def v88_chase_ok(ticker, side, ask, thesis_score, now=None):
    now = time.time() if now is None else now
    rec = v88_blocked_candidate.get((ticker, side))
    if not rec or now - rec.get("ts", 0) > V88_BLOCK_MEMORY_TTL:
        return True, "NO_BLOCK_MEMORY"
    chase = float(ask) - rec.get("ask", float(ask))
    stronger = thesis_score - rec.get("thesis_score", thesis_score)
    if chase > V88_MAX_CHASE_CENTS and stronger < V88_CHASE_STRONGER_EVIDENCE_DELTA:
        return False, f"NO_CHASE_MISSED_{rec['ask']:.3f}_NOW_{ask:.3f}_D{chase:.3f}_S{stronger:+d}"
    return True, f"CHASE_OK_D{chase:.3f}_S{stronger:+d}"



def v922_shock_chase_ok(side, ask, now=None):
    """Block a late local-extreme entry after a fast repricing + counter snap.

    Example caught by this rule:
      NO ask jumps roughly .52 -> .66 after BTC already falls ~$18,
      then BTC rebounds +$7 over 6 seconds.  The bearish structural thesis can
      still be valid, but .66 is no longer a good trigger; wait for a new test.
    """
    now = time.time() if now is None else now
    if ask is None:
        return True, "SHOCK_GUARD_NO_ASK"

    hist = [
        (ts, px) for ts, px in price_history.get(side, [])
        if ts >= now - V922_SHOCK_LOOKBACK_SECONDS and px is not None
    ]
    if len(hist) < 2:
        return True, "SHOCK_GUARD_WARMING"

    recent_low = min(px for _, px in hist)
    ask_jump = float(ask) - float(recent_low)

    wanted_sign = 1.0 if side == "YES" else -1.0
    ch6 = btc_change(6, now)
    ch9 = btc_change(9, now)
    ch30 = btc_change(30, now)

    completed_side_move = 0.0 if ch30 is None else ch30 * wanted_sign
    counter6 = 0.0 if ch6 is None else -(ch6 * wanted_sign)
    counter9 = 0.0 if ch9 is None else -(ch9 * wanted_sign)

    shocked = (
        ask_jump >= V922_SHOCK_ASK_JUMP
        and completed_side_move >= V922_MIN_COMPLETED_SIDE_MOVE_30S
        and (
            counter6 >= V922_MIN_COUNTER_SNAP_6S
            or counter9 >= V922_MIN_COUNTER_SNAP_9S
        )
    )
    if shocked:
        return False, (
            f"V922_WAIT_POST_SHOCK_{side}_"
            f"ASKJUMP{ask_jump:.2f}_M30{completed_side_move:+.1f}_"
            f"COUNTER6{counter6:+.1f}_COUNTER9{counter9:+.1f}"
        )
    return True, (
        f"V922_SHOCK_OK_J{ask_jump:.2f}_M30{completed_side_move:+.1f}_"
        f"C6{counter6:+.1f}_C9{counter9:+.1f}"
    )


def v88_same_side_reentry_ok(side, ask, thesis_adv, now=None):
    now = time.time() if now is None else now
    rec = v88_last_loss.get(side)
    if not rec:
        return True, "NO_PRIOR_LOSS"
    age = now - rec.get("ts", 0)
    if age >= V88_SAME_SIDE_REENTRY_LOCK:
        return True, "LOSS_LOCK_CLEAR"

    better_price = rec.get("entry_ask") is not None and ask <= rec["entry_ask"] - V88_REENTRY_BETTER_PRICE_CENTS
    stronger = thesis_adv >= rec.get("thesis_adv", thesis_adv) + V88_REENTRY_SCORE_DELTA
    arc = ema9_arc_state(now)
    new_event = (
        arc.get("stage") in ("RELEASE", "BUILDING")
        and (arc.get("stage") != rec.get("arc_stage") or arc.get("direction") != rec.get("arc_direction"))
    )
    if better_price or stronger or new_event:
        tag = "BETTER_PRICE" if better_price else "STRONGER_THESIS" if stronger else "NEW_ARC_EVENT"
        return True, f"FRESH_REENTRY_{tag}"
    return False, f"STALE_REENTRY_LOCK_{max(0, V88_SAME_SIDE_REENTRY_LOCK-age):.0f}s"


def v85_countertrend_exception_ok(side, now=None):
    """Higher bar for fading a strong parent than the ordinary reversal observer."""
    now = time.time() if now is None else now
    ok, reason = v84_countertrend_reversal_ok(side, now)
    if not ok:
        pullback_ok, pullback_reason = v88_exhaustion_pullback_ok(side, None, now)
        if pullback_ok:
            return True, pullback_reason
        return False, reason
    ext = extension_metrics(now)
    anc = ema9_ancestry_state(now)
    exhaustion = ext.get("exhaustion_score") or 0
    wanted = "UP" if side == "YES" else "DOWN"
    # Either explicit continuous ancestry is already anticipating the turn,
    # or exhaustion must be materially stronger than the normal observer gate.
    if anc.get("anticipated") == wanted:
        return True, f"ANCESTRY_EXCEPTION_{anc.get('setup','TURN')}"
    if exhaustion >= V85_COUNTERTREND_STRONG_EXHAUSTION:
        return True, f"STRONG_EXHAUSTION_{exhaustion:.0f}"
    return False, f"REVERSAL_TOO_WEAK_E{exhaustion:.0f}"


def v85_countertrend_reentry_ok(side, now=None):
    """After a failed fade, do not fire the same fade again without new proof."""
    now = time.time() if now is None else now
    last = v85_last_failed_countertrend.get(side, 0.0)
    age = now - last
    if age >= V85_COUNTERTREND_REENTRY_LOCK_SECONDS:
        return True, "LOCK_CLEAR"
    ok, why = v85_countertrend_exception_ok(side, now)
    if ok:
        return True, f"NEW_EVIDENCE_{why}"
    return False, f"COUNTERTREND_REENTRY_LOCK_{max(0, V85_COUNTERTREND_REENTRY_LOCK_SECONDS-age):.0f}s"


def v85_trade_intent(side, signal=None, now=None):
    """Label why the position exists so later reviews judge it by the right objective."""
    now = time.time() if now is None else now
    signal = signal or {}
    if signal.get("strategy") == "EARLY_IMPULSE_CORE":
        return "EARLY_IMPULSE"
    seconds_left = signal.get("seconds_to_close")
    if seconds_left is not None and seconds_left <= EXPIRY_MODE_SECONDS:
        return "EXPIRY"
    if signal.get("v81_anticipation") or "EXHAUSTION_PULLBACK" in (signal.get("early_exception_reasons") or ""):
        return "ANTICIPATION"
    if v84_swirl_state(now):
        return "SNIP"
    rel, arc = ema9_arc_relation(side, now)
    if rel == "HEALTHY" and arc.get("stage") in ("RELEASE", "BUILDING", "EXPANDING"):
        return "ARC_RIDER"
    return "CORE"


def _v9_num(x, default=None):
    try:
        return float(x) if x is not None else default
    except (TypeError, ValueError):
        return default


def v9_target_geometry(target=None, now=None):
    """Observer-only geometry of BTC target relative to EMA9/EMA30."""
    now = time.time() if now is None else now
    target = parse_target_price(active_target) if target is None else target
    price = btc_last_price
    e9, e30 = btc_ema_9, btc_ema_30
    if target is None or price is None or e9 is None or e30 is None:
        return {"target_ema_position": "WARMING", "target_side": "ON"}

    eps = 0.25
    if target > max(e9, e30) + eps:
        pos = "ABOVE_BOTH"
    elif target < min(e9, e30) - eps:
        pos = "BELOW_BOTH"
    else:
        pos = "BETWEEN_EMAS"

    side = "YES" if price > target else "NO" if price < target else "ON"
    candles = observer_candles()
    stretch = ema_stretch_state(candles)
    arc = ema9_arc_state(now)
    r60 = btc_range(60, now) or 0.0
    dist = price - target

    # A compact ordering string makes later grouping easy without assuming
    # any one ordering is bullish/bearish in advance.
    ordered = sorted(((price, "P"), (e9, "9"), (e30, "30"), (target, "T")), reverse=True)
    ordering = ">".join(label for _, label in ordered)

    # "support" here is descriptive only: it says the fast/slow averages are
    # already on the same favorable side of target as current price.
    if price > target and e9 > target and e30 > target:
        structural_side = "YES_FULL"
    elif price < target and e9 < target and e30 < target:
        structural_side = "NO_FULL"
    elif (e9-target) * (e30-target) <= 0:
        structural_side = "TARGET_SANDWICH"
    else:
        structural_side = "MIXED"

    return {
        "target_ema_position": pos,
        "target_side": side,
        "ordering": ordering,
        "structural_side": structural_side,
        "target_to_ema9": target - e9,
        "target_to_ema30": target - e30,
        "price_to_ema9": price - e9,
        "price_to_ema30": price - e30,
        "target_distance_norm60": (dist / r60) if r60 > 0 else None,
        "ema9_slope6": stretch.get("ema9_slope6"),
        "ema30_slope6": stretch.get("ema30_slope6"),
        "ema_gap": stretch.get("ema_gap"),
        "ema_gap_state": stretch.get("ema_gap_state"),
        "ema9_arc_stage": arc.get("stage"),
        "ema9_arc_direction": arc.get("direction"),
        "ema9_curvature": arc.get("curvature"),
    }


def _v9_cross_stats(crossings, now):
    ages = [now-ts for ts in crossings]
    c30 = sum(1 for a in ages if a <= 30)
    c60 = sum(1 for a in ages if a <= 60)
    c90 = sum(1 for a in ages if a <= 90)
    recent = [ts for ts in crossings if now-ts <= 90]
    spacings = [b-a for a,b in zip(recent, recent[1:])]
    return {
        "cross_count_30": c30,
        "cross_count_60": c60,
        "cross_count_90": c90,
        "last_cross_spacing": spacings[-1] if spacings else None,
        "avg_cross_spacing_90": (sum(spacings)/len(spacings)) if spacings else None,
        "cross_spacing_trend": (
            "EXPANDING" if len(spacings) >= 2 and spacings[-1] > spacings[-2] * 1.20
            else "COMPRESSING" if len(spacings) >= 2 and spacings[-1] < spacings[-2] * 0.80
            else "STABLE" if len(spacings) >= 2 else "NA"
        ),
    }


def _v9_expiry_snapshot(ticker, yes_ask, no_ask, close_ts, now):
    target = parse_target_price(active_target)
    if target is None or btc_last_price is None:
        return None
    sec_left = max(0.0, close_ts-now) if isinstance(close_ts, (int,float)) else None
    if sec_left is None or sec_left > EXPIRY_OBSERVER_WINDOW:
        return None

    st = expiry_observer_state.setdefault(ticker, {
        "last_side": None, "last_cross_ts": None, "crossings": [],
        "last_snapshot_ts": 0.0, "last_stability_ts": 0.0,
        "last_flip_ts": 0.0, "last_dist": None,
    })
    dist = btc_last_price-target
    side = "YES" if dist > 0 else "NO" if dist < 0 else "ON"
    prev_side = st.get("last_side")
    crossed = prev_side in ("YES","NO") and side in ("YES","NO") and side != prev_side
    if crossed:
        st["last_cross_ts"] = now
        st["crossings"].append(now)
        st["crossings"] = [x for x in st["crossings"] if now-x <= 180]
    if side in ("YES","NO"):
        st["last_side"] = side

    hold_s = (now-st["last_cross_ts"]) if st.get("last_cross_ts") is not None else None
    geom = v9_target_geometry(target, now)
    crosses = _v9_cross_stats(st.get("crossings", []), now)
    snap = {
        "epoch_ms": int(now*1000),
        "timestamp": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "ticker": ticker,
        "seconds_left": sec_left,
        "btc_price": btc_last_price,
        "target_price": target,
        "target_distance": dist,
        "target_side": side,
        "yes_ask": yes_ask, "no_ask": no_ask,
        "btc_ema9": btc_ema_9, "btc_ema30": btc_ema_30,
        "target_ema_position": geom.get("target_ema_position"),
        "ordering": geom.get("ordering"),
        "structural_side": geom.get("structural_side"),
        "target_to_ema9": geom.get("target_to_ema9"),
        "target_to_ema30": geom.get("target_to_ema30"),
        "price_to_ema9": geom.get("price_to_ema9"),
        "price_to_ema30": geom.get("price_to_ema30"),
        "target_distance_norm60": geom.get("target_distance_norm60"),
        "ema9_slope6": geom.get("ema9_slope6"),
        "ema30_slope6": geom.get("ema30_slope6"),
        "ema_gap": geom.get("ema_gap"),
        "ema_gap_state": geom.get("ema_gap_state"),
        "ema9_arc_stage": geom.get("ema9_arc_stage"),
        "ema9_arc_direction": geom.get("ema9_arc_direction"),
        "ema9_curvature": geom.get("ema9_curvature"),
        "btc_change3": btc_change(3,now), "btc_change6": btc_change(6,now),
        "btc_change9": btc_change(9,now), "btc_change15": btc_change(15,now),
        "btc_change30": btc_change(30,now), "btc_change60": btc_change(60,now),
        "btc_range30": btc_range(30,now), "btc_range60": btc_range(60,now),
        "btc_eff30": btc_trend_efficiency(30,3,now),
        "btc_eff60": btc_trend_efficiency(60,5,now),
        "crossed_now": int(crossed),
        "hold_seconds": hold_s,
        **crosses,
    }
    st["last_dist"] = dist
    return snap


def _v9_start_expiry_event(kind, snap, now, reason=""):
    global expiry_event_counter
    expiry_event_counter += 1
    ev = {
        "id": f"X{expiry_event_counter:05d}", "kind": kind, "start": now,
        "ticker": snap["ticker"], "reason": reason, "start_snap": dict(snap),
        "samples": {}, "reversed": False, "reversal_age": None,
    }
    expiry_active_events.append(ev)
    return ev


def _v9_write_expiry_event(ev, status="COMPLETE"):
    s = ev["start_snap"]
    row = [
        s.get("timestamp"), ev.get("id"), ev.get("ticker"), ev.get("kind"), status, ev.get("reason"),
        s.get("seconds_left"), s.get("target_side"), s.get("btc_price"), s.get("target_price"),
        s.get("target_distance"), s.get("yes_ask"), s.get("no_ask"),
        s.get("btc_ema9"), s.get("btc_ema30"), s.get("target_ema_position"), s.get("ordering"),
        s.get("structural_side"), s.get("ema9_slope6"), s.get("ema30_slope6"),
        s.get("ema9_curvature"), s.get("btc_change3"), s.get("btc_change6"), s.get("btc_change9"),
        s.get("btc_range60"), s.get("cross_count_30"), s.get("cross_count_60"),
        s.get("cross_count_90"), s.get("last_cross_spacing"), s.get("avg_cross_spacing_90"),
        s.get("cross_spacing_trend"), s.get("hold_seconds"), int(bool(ev.get("reversed"))), ev.get("reversal_age"),
    ]
    for h in EXPIRY_EVENT_HORIZONS:
        x = ev["samples"].get(h,{})
        row.extend([x.get("btc"), x.get("dist"), x.get("yes"), x.get("no"), x.get("side")])
    with open(EXPIRY_EVENT_LOG_FILE,"a",newline="",encoding="utf-8") as f:
        csv.writer(f).writerow(row)


def _v9_update_expiry_events(snap, now):
    finished=[]
    for ev in list(expiry_active_events):
        if ev.get("ticker") != snap.get("ticker"):
            continue
        age=now-ev["start"]
        for h in EXPIRY_EVENT_HORIZONS:
            if age >= h and h not in ev["samples"]:
                ev["samples"][h] = {
                    "btc": snap.get("btc_price"), "dist": snap.get("target_distance"),
                    "yes": snap.get("yes_ask"), "no": snap.get("no_ask"), "side": snap.get("target_side")
                }
        start_side=ev["start_snap"].get("target_side")
        if (not ev.get("reversed") and start_side in ("YES","NO") and
                snap.get("target_side") in ("YES","NO") and snap.get("target_side") != start_side and
                age <= EXPIRY_FAKEOUT_WINDOW):
            ev["reversed"] = True
            ev["reversal_age"] = round(age,3)
        # Finalize after 30s, or at expiry if less than 30s remained at trigger.
        need=min(max(EXPIRY_EVENT_HORIZONS), max(0.5, ev["start_snap"].get("seconds_left") or 30.0))
        if age >= need or (snap.get("seconds_left") is not None and snap["seconds_left"] <= 0.25):
            _v9_write_expiry_event(ev, "COMPLETE")
            finished.append(ev)
    for ev in finished:
        if ev in expiry_active_events:
            expiry_active_events.remove(ev)


def v9_expiry_observer(ticker, yes_ask, no_ask, close_ts=None, now=None):
    """High-resolution final-90s observer: STABILITY, FLIP_LAG, FALSE_BREAK research."""
    now=time.time() if now is None else now
    snap=_v9_expiry_snapshot(ticker,yes_ask,no_ask,close_ts,now)
    if not snap:
        return
    st=expiry_observer_state[ticker]

    # Snapshot at 2 Hz. This is deliberately richer than the normal 3s structure log.
    if now-st.get("last_snapshot_ts",0.0) >= EXPIRY_SNAPSHOT_INTERVAL:
        with open(EXPIRY_SNAPSHOT_LOG_FILE,"a",newline="",encoding="utf-8") as f:
            csv.writer(f).writerow([snap.get(k,"") for k in EXPIRY_SNAPSHOT_FIELDS])
        st["last_snapshot_ts"]=now

    # Every genuine target-side flip gets an event. No directional threshold is
    # imposed here because the goal is to discover which flips matter later.
    if snap.get("crossed_now") and now-st.get("last_flip_ts",0.0) >= EXPIRY_FLIP_EVENT_COOLDOWN:
        _v9_start_expiry_event("FLIP_LAG",snap,now,"BTC_TARGET_CROSS")
        st["last_flip_ts"]=now

    # Stability is a different edge: the market has held one side while time decays.
    hold=snap.get("hold_seconds")
    r60=snap.get("btc_range60") or 0.0
    cushion=max(8.0,0.15*r60)
    if (hold is not None and hold >= EXPIRY_STABILITY_MIN_HOLD and
        abs(snap.get("target_distance") or 0.0) >= cushion and
        now-st.get("last_stability_ts",0.0) >= EXPIRY_STABILITY_COOLDOWN):
        _v9_start_expiry_event("STABILITY",snap,now,f"HOLD_{hold:.1f}s_CUSHION_{cushion:.1f}")
        st["last_stability_ts"]=now

    _v9_update_expiry_events(snap,now)


def _v91_append(path, fields, data):
    """Append a dict row with a header on first use."""
    new = not os.path.exists(path) or os.path.getsize(path) == 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(fields)
        w.writerow([data.get(k, "") for k in fields])


def _v91_nearest_sample(seconds_ago, now):
    if not v91_history:
        return None
    target_ts = now - seconds_ago
    return min(v91_history, key=lambda x: abs(x["ts"] - target_ts))


def _v91_signed(side, x):
    if x is None:
        return None
    return x if side == "YES" else -x


def v91_structural_snapshot(ticker, yes_ask, no_ask, close_ts=None, now=None):
    """Sequence-aware market description. Observer only."""
    now = time.time() if now is None else now
    target = parse_target_price(active_target)
    if target is None or btc_last_price is None or btc_ema_9 is None or btc_ema_30 is None:
        return None

    candles = observer_candles()
    macro = macro_leg_state(candles)
    form = formation_state(candles, macro)
    arc = ema9_arc_state(now)
    stretch = ema_stretch_state(candles)
    geom = v9_target_geometry(target, now)
    r60 = max(1.0, btc_range(60, now) or 1.0)
    r180 = max(r60, btc_range(180, now) or r60)
    sec_left = max(0.0, close_ts-now) if isinstance(close_ts,(int,float)) else None
    gap = btc_ema_9 - btc_ema_30

    # Maintain a short high-resolution history for gap velocity / curvature.
    sample = {"ts": now, "btc": btc_last_price, "e9": btc_ema_9, "e30": btc_ema_30,
              "gap": gap, "target": target, "yes": yes_ask, "no": no_ask}
    if not v91_history or now-v91_history[-1]["ts"] >= 0.45:
        v91_history.append(sample)
        cutoff = now - 240.0
        while v91_history and v91_history[0]["ts"] < cutoff:
            v91_history.pop(0)

    prev6 = _v91_nearest_sample(6, now)
    prev9 = _v91_nearest_sample(9, now)
    prev30 = _v91_nearest_sample(30, now)
    prev60 = _v91_nearest_sample(60, now)
    def delta(prev, key):
        return (sample[key]-prev[key]) if prev and prev.get(key) is not None else None
    gap_d6, gap_d9, gap_d30, gap_d60 = (delta(prev6,"gap"),delta(prev9,"gap"),delta(prev30,"gap"),delta(prev60,"gap"))
    e30_d30 = delta(prev30,"e30")
    e9_d9 = delta(prev9,"e9")

    # Convergence uses absolute gap. A positive value means the two EMAs are
    # moving closer together; negative means separation is expanding.
    abs_gap_prev30 = abs(prev30["gap"]) if prev30 else None
    convergence30 = (abs_gap_prev30-abs(gap)) if abs_gap_prev30 is not None else None
    convergence_ratio30 = (convergence30/max(1.0,abs_gap_prev30)) if abs_gap_prev30 is not None else None
    if convergence_ratio30 is None:
        gap_motion = "WARMING"
    elif convergence_ratio30 >= V91_GAP_COLLAPSE_MIN:
        gap_motion = "COLLAPSING_FAST"
    elif convergence_ratio30 >= 0.12:
        gap_motion = "CONVERGING"
    elif convergence_ratio30 <= -0.20:
        gap_motion = "EXPANDING_FAST"
    elif convergence_ratio30 < -0.05:
        gap_motion = "EXPANDING"
    else:
        gap_motion = "STABLE"

    # Target interaction / acceptance state.
    ist = v91_interaction_state.setdefault(ticker, {
        "target_side": None, "target_cross_ts": None, "target_origin": None,
        "target_max_pen": 0.0, "ema9_side": None, "ema9_cross_ts": None,
        "ema30_side": None, "ema30_cross_ts": None, "last_target_reject_ts": 0.0,
    })
    target_dist = btc_last_price-target
    target_side = "YES" if target_dist > 0 else "NO" if target_dist < 0 else "ON"
    target_event = "NONE"
    if target_side in ("YES","NO"):
        if ist["target_side"] in ("YES","NO") and target_side != ist["target_side"]:
            age = now-ist["target_cross_ts"] if ist.get("target_cross_ts") else None
            prev_origin = ist.get("target_origin")
            if age is not None and age <= V91_FAKEOUT_MAX_AGE:
                target_event = "TARGET_FALSE_BREAK_RECLAIM"
                ist["last_target_reject_ts"] = now
            else:
                target_event = "TARGET_CROSS"
            ist["target_cross_ts"] = now
            ist["target_origin"] = target_side
            ist["target_max_pen"] = abs(target_dist)
        elif ist["target_side"] is None:
            ist["target_cross_ts"] = now
            ist["target_origin"] = target_side
            ist["target_max_pen"] = abs(target_dist)
        else:
            ist["target_max_pen"] = max(ist.get("target_max_pen",0.0), abs(target_dist))
        ist["target_side"] = target_side
    target_hold = now-ist["target_cross_ts"] if ist.get("target_cross_ts") else 0.0
    if target_event == "NONE" and target_hold >= V91_ACCEPT_MIN_HOLD and target_side in ("YES","NO"):
        target_event = f"TARGET_ACCEPTED_{target_side}"

    # EMA interaction state: crossings are attempts; sustained holds are acceptance.
    def interaction(label, level):
        dist = btc_last_price-level
        side = "ABOVE" if dist > 0 else "BELOW" if dist < 0 else "ON"
        skey, tkey = f"{label}_side", f"{label}_cross_ts"
        event = "NONE"
        old = ist.get(skey)
        if old in ("ABOVE","BELOW") and side in ("ABOVE","BELOW") and side != old:
            event = f"{label.upper()}_CROSS_{side}"
            ist[tkey] = now
        elif old is None:
            ist[tkey] = now
        ist[skey] = side
        hold = now-ist.get(tkey,now)
        if event == "NONE" and hold >= V91_ACCEPT_MIN_HOLD:
            event = f"{label.upper()}_ACCEPTED_{side}"
        return side, hold, event
    e9_side,e9_hold,e9_event = interaction("ema9",btc_ema_9)
    e30_side,e30_hold,e30_event = interaction("ema30",btc_ema_30)

    # Pullback quality: seek temporary weakness inside an intact parent structure.
    macro_dir = macro.get("direction")
    slope30 = stretch.get("ema30_slope6") or 0.0
    parent_distance = macro.get("distance") or 0.0
    parent_abs_norm = abs(parent_distance)/r180
    pullback = "NONE"
    if macro_dir == "UP" and gap > 0 and slope30 > 0:
        depth = max(0.0, btc_ema_9-btc_last_price)
        if btc_last_price <= btc_ema_9 + 0.10*r60 and btc_last_price >= btc_ema_30 - V91_PULLBACK_EMA30_BUFFER_FRAC*r60:
            pullback = "YES_HEALTHY_DIP" if depth <= V91_PULLBACK_MAX_STRIDE_FRAC*r60 else "YES_DEEP_DIP"
    elif macro_dir == "DOWN" and gap < 0 and slope30 < 0:
        depth = max(0.0, btc_last_price-btc_ema_9)
        if btc_last_price >= btc_ema_9 - 0.10*r60 and btc_last_price <= btc_ema_30 + V91_PULLBACK_EMA30_BUFFER_FRAC*r60:
            pullback = "NO_HEALTHY_BOUNCE" if depth <= V91_PULLBACK_MAX_STRIDE_FRAC*r60 else "NO_DEEP_BOUNCE"

    # Structural scores deliberately mix state AND change-of-state. They are for
    # audit/research, not live orders in V9.1.
    def score_side(side):
        sign = 1 if side == "YES" else -1
        score = 0
        why=[]
        if target_dist*sign > 0: score += 2; why.append("price_target")
        if (btc_last_price-btc_ema_9)*sign > 0: score += 2; why.append("price_ema9")
        if gap*sign > 0: score += 2; why.append("ema_order")
        if (btc_ema_30-target)*sign > 0: score += 2; why.append("ema30_target")
        if slope30*sign > 0: score += 2; why.append("ema30_slope")
        if macro_dir == ("UP" if side=="YES" else "DOWN"): score += 1; why.append("parent")
        if gap_motion in ("EXPANDING","EXPANDING_FAST") and gap*sign > 0: score += 2; why.append("gap_expand")
        if gap_motion in ("CONVERGING","COLLAPSING_FAST") and gap*sign > 0: score -= 2; why.append("gap_collapse")
        # Mature parent + collapsing gap is an early reversal warning.
        if parent_abs_norm >= 1.25 and gap_motion == "COLLAPSING_FAST" and gap*sign > 0:
            score -= 2; why.append("mature_collapse")
        # Accepted target/EMA territory deserves more authority than a momentary cross.
        if target_hold >= V91_ACCEPT_MIN_HOLD and target_dist*sign > 0: score += 1; why.append("target_accept")
        if e30_hold >= V91_ACCEPT_MIN_HOLD and (btc_last_price-btc_ema_30)*sign > 0: score += 1; why.append("ema30_accept")
        return score,";".join(why)
    yes_score,yes_why=score_side("YES")
    no_score,no_why=score_side("NO")
    advantage=yes_score-no_score
    structural_bias = "YES" if advantage >= 3 else "NO" if advantage <= -3 else "NEUTRAL"

    # Price displacement vs structural displacement: large price move with little
    # structural migration is a fakeout candidate; modest price move with strong
    # structural migration is a quiet regime-change candidate.
    ch30=btc_change(30,now) or 0.0
    ch60=btc_change(60,now) or 0.0
    price_disp=min(100.0,100.0*max(abs(ch30)/r60,abs(ch60)/max(r60,1.0)))
    structure_components=0
    structure_components += 25 if e9_event.startswith("EMA9_CROSS") else 0
    structure_components += 30 if e30_event.startswith("EMA30_CROSS") else 0
    structure_components += 20 if gap_motion == "COLLAPSING_FAST" else 0
    structure_components += 15 if target_event.startswith("TARGET_ACCEPTED") else 0
    structure_components += 10 if abs(slope30) >= 1.0 else 0
    structural_disp=min(100,structure_components)
    fakeout_candidate = price_disp >= 60 and structural_disp <= 35
    quiet_regime_change = price_disp <= 50 and structural_disp >= 55

    # Holding authority is separate from entry desirability.
    hold_yes = "STRONG" if yes_score >= 8 else "HOLD" if yes_score >= 4 else "WEAK" if yes_score >= 1 else "INVALIDATE"
    hold_no = "STRONG" if no_score >= 8 else "HOLD" if no_score >= 4 else "WEAK" if no_score >= 1 else "INVALIDATE"

    return {
        "timestamp": datetime.fromtimestamp(now,timezone.utc).isoformat(), "epoch_ms": int(now*1000),
        "ticker": ticker, "seconds_left": sec_left, "btc_price": btc_last_price, "target_price": target,
        "yes_ask": yes_ask, "no_ask": no_ask, "btc_ema9": btc_ema_9, "btc_ema30": btc_ema_30,
        "target_distance": target_dist, "target_side": target_side, "target_hold_s": target_hold,
        "target_event": target_event, "target_ema_position": geom.get("target_ema_position"),
        "ordering": geom.get("ordering"), "structural_side": geom.get("structural_side"),
        "target_to_ema9": target-btc_ema_9, "target_to_ema30": target-btc_ema_30,
        "ema_gap": gap, "gap_motion": gap_motion, "gap_convergence30": convergence30,
        "gap_convergence_ratio30": convergence_ratio30, "gap_delta6": gap_d6, "gap_delta9": gap_d9,
        "gap_delta30": gap_d30, "gap_delta60": gap_d60, "ema9_delta9": e9_d9, "ema30_delta30": e30_d30,
        "ema9_side": e9_side, "ema9_hold_s": e9_hold, "ema9_event": e9_event,
        "ema30_side": e30_side, "ema30_hold_s": e30_hold, "ema30_event": e30_event,
        "ema9_arc_stage": arc.get("stage"), "ema9_arc_direction": arc.get("direction"),
        "ema9_curvature": arc.get("curvature"), "ema30_slope6": slope30,
        "macro_direction": macro_dir, "parent_maturity": macro.get("maturity"),
        "parent_distance": parent_distance, "parent_distance_norm180": parent_abs_norm,
        "formation": form.get("geometry"), "local_regime": form.get("local_regime"),
        "pullback_state": pullback, "btc_change30": ch30, "btc_change60": ch60,
        "btc_range60": r60, "btc_range180": r180, "price_displacement_score": round(price_disp,1),
        "structural_displacement_score": structural_disp, "fakeout_candidate": int(fakeout_candidate),
        "quiet_regime_change": int(quiet_regime_change), "yes_structural_score": yes_score,
        "no_structural_score": no_score, "structural_advantage": advantage, "structural_bias": structural_bias,
        "yes_hold_authority": hold_yes, "no_hold_authority": hold_no, "yes_why": yes_why, "no_why": no_why,
    }


V91_PERCEPTION_FIELDS = [
    "timestamp","epoch_ms","ticker","seconds_left","btc_price","target_price","yes_ask","no_ask",
    "btc_ema9","btc_ema30","target_distance","target_side","target_hold_s","target_event",
    "target_ema_position","ordering","structural_side","target_to_ema9","target_to_ema30",
    "ema_gap","gap_motion","gap_convergence30","gap_convergence_ratio30","gap_delta6","gap_delta9",
    "gap_delta30","gap_delta60","ema9_delta9","ema30_delta30","ema9_side","ema9_hold_s","ema9_event",
    "ema30_side","ema30_hold_s","ema30_event","ema9_arc_stage","ema9_arc_direction","ema9_curvature",
    "ema30_slope6","macro_direction","parent_maturity","parent_distance","parent_distance_norm180",
    "formation","local_regime","pullback_state","btc_change30","btc_change60","btc_range60","btc_range180",
    "price_displacement_score","structural_displacement_score","fakeout_candidate","quiet_regime_change",
    "yes_structural_score","no_structural_score","structural_advantage","structural_bias",
    "yes_hold_authority","no_hold_authority","yes_why","no_why"
]

V91_AUDIT_FIELDS = [
    "timestamp","event","trade_id","ticker","trade_side","legacy_reason","entry_ask","exit_bid","pnl",
    "btc_price","target_price","target_distance","yes_ask","no_ask","structural_bias","trade_side_score",
    "opposite_score","hold_authority","gap_motion","ema_gap","ema30_slope6","target_event","target_hold_s",
    "pullback_state","fakeout_candidate","price_displacement_score","structural_displacement_score","ordering",
    "structural_side","comment"
]

V91_EVENT_FIELDS = [
    "timestamp","event_id","ticker","kind","side","reason","seconds_left","btc_price","target_price",
    "target_distance","yes_ask","no_ask","structural_bias","yes_score","no_score","gap_motion","ema_gap",
    "ema30_slope6","target_event","pullback_state","fakeout_candidate","price_displacement_score",
    "structural_displacement_score","ordering"
] + [f"btc_{h}s" for h in V91_EVENT_HORIZONS] + [f"yes_{h}s" for h in V91_EVENT_HORIZONS] + [f"no_{h}s" for h in V91_EVENT_HORIZONS]


def _v91_start_event(kind, side, reason, snap, now):
    global v91_event_counter
    key=(snap.get("ticker"),kind,side)
    if now-v91_last_event_ts.get(key,0.0) < V91_EVENT_COOLDOWN:
        return
    v91_event_counter += 1
    v91_last_event_ts[key]=now
    v91_active_events.append({"id":f"S{v91_event_counter:05d}","start":now,"kind":kind,"side":side,
                              "reason":reason,"snap":dict(snap),"samples":{}})


def _v91_update_events(ticker, yes_ask, no_ask, now):
    done=[]
    for ev in v91_active_events:
        if ev["snap"].get("ticker") != ticker:
            continue
        age=now-ev["start"]
        for h in V91_EVENT_HORIZONS:
            if age >= h and h not in ev["samples"]:
                ev["samples"][h]={"btc":btc_last_price,"yes":yes_ask,"no":no_ask}
        if age >= max(V91_EVENT_HORIZONS):
            s=ev["snap"]
            row={
                "timestamp":s.get("timestamp"),"event_id":ev["id"],"ticker":ticker,"kind":ev["kind"],
                "side":ev["side"],"reason":ev["reason"],"seconds_left":s.get("seconds_left"),
                "btc_price":s.get("btc_price"),"target_price":s.get("target_price"),"target_distance":s.get("target_distance"),
                "yes_ask":s.get("yes_ask"),"no_ask":s.get("no_ask"),"structural_bias":s.get("structural_bias"),
                "yes_score":s.get("yes_structural_score"),"no_score":s.get("no_structural_score"),
                "gap_motion":s.get("gap_motion"),"ema_gap":s.get("ema_gap"),"ema30_slope6":s.get("ema30_slope6"),
                "target_event":s.get("target_event"),"pullback_state":s.get("pullback_state"),
                "fakeout_candidate":s.get("fakeout_candidate"),"price_displacement_score":s.get("price_displacement_score"),
                "structural_displacement_score":s.get("structural_displacement_score"),"ordering":s.get("ordering")}
            for h in V91_EVENT_HORIZONS:
                x=ev["samples"].get(h,{})
                row[f"btc_{h}s"]=x.get("btc"); row[f"yes_{h}s"]=x.get("yes"); row[f"no_{h}s"]=x.get("no")
            _v91_append(V91_EVENT_LOG_FILE,V91_EVENT_FIELDS,row)
            done.append(ev)
    for ev in done:
        if ev in v91_active_events: v91_active_events.remove(ev)


def v91_perception_observer(ticker, yes_ask, no_ask, close_ts=None, now=None):
    global v91_last_sample_ts
    now=time.time() if now is None else now
    snap=v91_structural_snapshot(ticker,yes_ask,no_ask,close_ts,now)
    if not snap:
        return None
    _v91_update_events(ticker,yes_ask,no_ask,now)
    if now-v91_last_sample_ts >= V91_SAMPLE_INTERVAL:
        _v91_append(V91_PERCEPTION_LOG_FILE,V91_PERCEPTION_FIELDS,snap)
        v91_last_sample_ts=now

    # Research events based on today's manually identified failure modes.
    if snap.get("pullback_state") == "YES_HEALTHY_DIP":
        _v91_start_event("PULLBACK_ENTRY_WINDOW","YES","THESIS_ON_STRENGTH_ENTRY_ON_WEAKNESS",snap,now)
    elif snap.get("pullback_state") == "NO_HEALTHY_BOUNCE":
        _v91_start_event("PULLBACK_ENTRY_WINDOW","NO","THESIS_ON_STRENGTH_ENTRY_ON_WEAKNESS",snap,now)
    if snap.get("gap_motion") == "COLLAPSING_FAST" and abs(snap.get("parent_distance_norm180") or 0) >= 1.25:
        old_side="YES" if (snap.get("ema_gap") or 0)>0 else "NO"
        _v91_start_event("MATURE_GAP_COLLAPSE","NO" if old_side=="YES" else "YES","PRE_CROSS_REVERSAL_WARNING",snap,now)
    if snap.get("fakeout_candidate"):
        _v91_start_event("PRICE_STRUCTURE_DIVERGENCE",snap.get("target_side"),"HIGH_PRICE_LOW_STRUCTURE",snap,now)
    if snap.get("target_event") == "TARGET_FALSE_BREAK_RECLAIM":
        _v91_start_event("TARGET_FALSE_BREAK",snap.get("target_side"),"CROSS_RECLAIM_WITHIN_30S",snap,now)
    return snap


def v91_legacy_audit(event, position, yes_ask=None, no_ask=None, exit_bid=None, pnl=None, reason=""):
    """Snapshot structural opinion at a legacy ENTRY or EXIT. Observer only."""
    try:
        close_ts=getattr(paper_manage,"current_close_ts",None)
        snap=v91_structural_snapshot(position.get("ticker",""),yes_ask,no_ask,close_ts,time.time())
        if not snap:
            return
        side=position.get("side")
        own=snap.get("yes_structural_score") if side=="YES" else snap.get("no_structural_score")
        opp=snap.get("no_structural_score") if side=="YES" else snap.get("yes_structural_score")
        hold=snap.get("yes_hold_authority") if side=="YES" else snap.get("no_hold_authority")
        comment=""
        if event=="EXIT" and reason.startswith("BIRD") and hold in ("HOLD","STRONG"):
            comment="LEGACY_BIRD_VS_STRUCTURAL_HOLD_DISAGREEMENT"
        elif event=="EXIT" and reason=="LATE_TARGET_INVALIDATION" and snap.get("target_event") in ("TARGET_CROSS","TARGET_FALSE_BREAK_RECLAIM"):
            comment="TARGET_ATTEMPT_NOT_YET_ACCEPTANCE"
        elif event=="ENTRY" and snap.get("gap_motion")=="COLLAPSING_FAST" and own is not None and opp is not None and own<=opp:
            comment="ENTRY_AGAINST_COLLAPSING_EMA_STRUCTURE"
        elif event=="ENTRY" and snap.get("pullback_state") in ("YES_HEALTHY_DIP","NO_HEALTHY_BOUNCE"):
            comment="ENTRY_INSIDE_STRUCTURAL_PULLBACK_WINDOW"
        row={"timestamp":snap.get("timestamp"),"event":event,"trade_id":position.get("trade_id"),
             "ticker":position.get("ticker"),"trade_side":side,"legacy_reason":reason,"entry_ask":position.get("entry_ask"),
             "exit_bid":exit_bid,"pnl":pnl,"btc_price":snap.get("btc_price"),"target_price":snap.get("target_price"),
             "target_distance":snap.get("target_distance"),"yes_ask":yes_ask,"no_ask":no_ask,"structural_bias":snap.get("structural_bias"),
             "trade_side_score":own,"opposite_score":opp,"hold_authority":hold,"gap_motion":snap.get("gap_motion"),
             "ema_gap":snap.get("ema_gap"),"ema30_slope6":snap.get("ema30_slope6"),"target_event":snap.get("target_event"),
             "target_hold_s":snap.get("target_hold_s"),"pullback_state":snap.get("pullback_state"),
             "fakeout_candidate":snap.get("fakeout_candidate"),"price_displacement_score":snap.get("price_displacement_score"),
             "structural_displacement_score":snap.get("structural_displacement_score"),"ordering":snap.get("ordering"),
             "structural_side":snap.get("structural_side"),"comment":comment}
        _v91_append(V91_AUDIT_LOG_FILE,V91_AUDIT_FIELDS,row)
    except Exception as exc:
        # Observer must never interfere with paper trading.
        print(f"⚠️ V9.2 AUDIT observer error: {exc}")


def v85_flash_observer(ticker, yes_ask, no_ask, close_ts=None, now=None):
    """Observer-only latency snapshot. No paper order is created here."""
    global v85_last_flash_log_ts
    now = time.time() if now is None else now
    if now - v85_last_flash_log_ts < V85_FLASH_LOG_INTERVAL:
        return
    target = parse_target_price(active_target)
    if target is None or btc_last_price is None:
        return

    distance = btc_last_price - target
    ch3 = btc_change(3, now) or 0.0
    ch6 = btc_change(6, now) or 0.0
    ch9 = btc_change(9, now) or 0.0
    seconds_left = max(0.0, close_ts - now) if isinstance(close_ts, (int, float)) else None

    side = "YES" if distance > 0 else "NO" if distance < 0 else None
    if side is None:
        return
    sign = 1 if side == "YES" else -1
    accel = max(ch3 * sign, ch6 * sign, ch9 * sign)

    if abs(distance) < V85_FLASH_MIN_TARGET_DISTANCE or accel < V85_FLASH_MIN_369_ACCEL:
        return

    advantage, own, opp = v85_thesis_advantage(side, now)
    condition = "FLASH_CANDIDATE"
    if seconds_left is not None and seconds_left <= 180:
        condition = "FLASH_EXPIRY_CANDIDATE"

    with open(FLASH_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            time.strftime("%Y-%m-%d %H:%M:%S"), ticker, side, condition,
            btc_last_price, target, distance, seconds_left,
            yes_ask, no_ask, ch3, ch6, ch9, btc_range(60, now),
            btc_ema_9, btc_ema_30, own.get("score", 0), opp.get("score", 0),
            advantage,
        ])
    v85_last_flash_log_ts = now


def v84_swirl_state(now=None):
    """True when EMA9/EMA30 are tight and BTC path is inefficient/tangled."""
    now = time.time() if now is None else now
    arc = ema9_arc_state(now)
    r60 = btc_range(60, now)
    eff60 = btc_trend_efficiency(60, 5, now)
    gap = abs(arc.get("gap") or 0.0)
    if not r60 or r60 <= 0:
        return False
    tight = gap <= V84_SWIRL_GAP_RANGE_FRAC * r60
    slow_path = eff60 is not None and eff60 <= V84_SWIRL_EFFICIENCY_MAX
    return bool(tight and slow_path)


def v84_countertrend_reversal_ok(side, now=None):
    """Require actual exhaustion/turn evidence before fading a strong parent arc."""
    now = time.time() if now is None else now
    wanted = "UP" if side == "YES" else "DOWN"
    wanted_sign = 1 if wanted == "UP" else -1
    arc = ema9_arc_state(now)
    ext = extension_metrics(now)
    imp = impulse_observer_state(now)
    anc = ema9_ancestry_state(now)

    # Explicit ancestry anticipation is valid evidence.
    if anc.get("anticipated") == wanted:
        return True, f"ANCESTRY_{anc.get('setup','TURN')}"

    # Extension by itself is NOT exhaustion. Require extension + exhaustion +
    # short-horizon momentum/curvature beginning to turn toward the proposed side.
    score = ext.get("double_extension_score") or 0
    exhaustion = ext.get("exhaustion_score") or 0
    counter = ext.get("edge_counter_side")
    curv = arc.get("curvature") or 0.0
    ch3 = btc_change(3, now) or 0.0
    ch6 = btc_change(6, now) or 0.0
    ch9 = btc_change(9, now) or 0.0
    momentum_turn = max(ch3*wanted_sign, ch6*wanted_sign, ch9*wanted_sign) >= V84_COUNTERTREND_MIN_369_MOVE
    curvature_turn = curv * wanted_sign >= EMA9_ARC_CURVATURE_TURN

    if (
        counter == side
        and score >= V84_COUNTERTREND_EXTENSION_SCORE
        and exhaustion >= V84_COUNTERTREND_EXHAUSTION_SCORE
        and (momentum_turn or curvature_turn)
    ):
        return True, f"EXHAUSTION_TURN_S{score:.0f}_E{exhaustion:.0f}"
    return False, f"NO_REVERSAL_PROOF_S{score:.0f}_E{exhaustion:.0f}"


def v84_early_access_allowed(side, now=None):
    """Allow first-minutes trading only when inherited BTC structure is already strong."""
    now = time.time() if now is None else now
    th = v83_structural_thesis(side, now)
    arc = ema9_arc_state(now)
    anc = ema9_ancestry_state(now)
    wanted = "UP" if side == "YES" else "DOWN"

    # Strong inherited thesis / active continuation.
    if th.get("state") == "STRONG" and th.get("score", 0) >= V84_EARLY_ACCESS_MIN_THESIS_SCORE:
        if arc.get("direction") == wanted or anc.get("anticipated") == wanted or anc.get("ancestry") == wanted:
            return True, f"EARLY_INHERITED_{wanted}_S{th.get('score',0)}"

    # Countertrend early access only with actual reversal proof.
    ok, why = v84_countertrend_reversal_ok(side, now)
    if ok:
        return True, f"EARLY_REVERSAL_{why}"
    return False, f"EARLY_OBSERVE_{th.get('state')}_S{th.get('score',0)}"


def v83_entry_context(side, signal, now=None):
    """Cross-talk between Core, EMA9 geometry and extension observer.
    Returns (allow_now, reason, anticipation). Late stretched continuation waits
    for a pullback; strong opposite extension blocks chasing.
    """
    now = time.time() if now is None else now
    arc = ema9_arc_state(now)
    stage, direction = arc.get("stage"), arc.get("direction")
    wanted = "UP" if side == "YES" else "DOWN"
    ancestry = ema9_ancestry_state(now)
    anticipation = (stage == "ROLLING" and direction not in (wanted, "NONE")) or ancestry.get("anticipated") == wanted
    rejection = v83_rejection_quality(now)
    opposite = "DOWN" if wanted == "UP" else "UP"

    # V8.5 parent authority: a tiny local bounce cannot override a strong
    # continuous parent thesis unless actual reversal/exhaustion evidence exists.
    own_thesis = v83_structural_thesis(side, now)
    opposite_side = "NO" if side == "YES" else "YES"
    opp_thesis = v83_structural_thesis(opposite_side, now)
    thesis_diff = own_thesis.get("score",0) - opp_thesis.get("score",0)
    ticker = signal.get("_ticker")
    ask_now = signal.get("price")

    if thesis_diff <= -V85_PARENT_VETO_DIFF:
        reversal_ok, reversal_reason = v85_countertrend_exception_ok(side, now)
        if not reversal_ok:
            # V8.8: a mature stretched parent can be faded for a pullback before
            # full reversal confirmation. This is deliberately a short-leash trade.
            reversal_ok, reversal_reason = v88_exhaustion_pullback_ok(side, signal, now)
        lock_ok, lock_reason = v85_countertrend_reentry_ok(side, now)
        if not reversal_ok:
            v88_remember_blocked_candidate(ticker, side, ask_now, own_thesis.get("score",0), reversal_reason, now)
            return False, f"BLOCK_PARENT_DIFF_{thesis_diff}_{opposite}_{reversal_reason}", anticipation
        if not lock_ok:
            return False, lock_reason, anticipation
        if reversal_reason.startswith("EXHAUSTION_PULLBACK"):
            anticipation = True

    # V8.8 anti-chase: if we previously rejected a materially cheaper candidate,
    # demand substantially stronger evidence before paying up.
    chase_ok, chase_reason = v88_chase_ok(ticker, side, ask_now, own_thesis.get("score",0), now)
    if not chase_ok:
        return False, chase_reason, anticipation

    # V9.2.2: structural direction is not enough to justify paying the end of a
    # fast repricing burst.  If BTC is already snapping back against the side,
    # wait for a fresh dip/bounce/release test.
    shock_ok, shock_reason = v922_shock_chase_ok(side, ask_now, now)
    if not shock_ok:
        v88_remember_blocked_candidate(ticker, side, ask_now, own_thesis.get("score",0), shock_reason, now)
        return False, shock_reason, anticipation

    # V8.8 same-side loss reset: stale conditions are not a new trade.
    re_ok, re_reason = v88_same_side_reentry_ok(side, ask_now, thesis_diff, now)
    if not re_ok:
        return False, re_reason, anticipation

    # A live EMA9 failure/rejection toward the opposite side has priority over
    # a local momentum chase. Price itself may cross EMA30 temporarily.
    if rejection.get("state") == f"EMA30_REJECTION_{opposite}" and rejection.get("strength",0) >= 60:
        return False, f"WAIT_OPPOSITE_EMA30_REJECTION_{opposite}_S{rejection.get('strength',0):.0f}", anticipation
    # Repeated weaker rejection = support/resistance is being consumed; do not
    # chase the old continuation side while the parent structure is weakening.
    if rejection.get("state") == f"WEAK_{wanted}_REJECTION":
        return False, f"WAIT_WEAK_REJECTION_{wanted}_T{rejection.get('tests',0)}", anticipation

    ext = extension_metrics(now)
    counter = ext.get("edge_counter_side")
    score = ext.get("double_extension_score") or 0
    exhaustion = ext.get("exhaustion_score") or 0
    if counter and counter != side and score >= OPPOSITE_EDGE_BLOCK_SCORE and exhaustion >= OPPOSITE_EDGE_BLOCK_EXHAUSTION_MIN:
        return False, f"WAIT_OPPOSITE_EDGE_{counter}_S{score:.0f}_E{exhaustion:.0f}", anticipation

    r60 = btc_range(60)
    price_gap = abs(arc.get("price_gap") or 0.0)
    # Never chase a vertical continuation merely because the arc is young.
    # If price is already stretched from EMA9, wait for the pullback/retest.
    if direction == wanted and r60 and price_gap >= r60 * LATE_ARC_PULLBACK_WAIT_RANGE_FRAC and not anticipation:
        return False, f"WAIT_PULLBACK_{stage}_{direction}_PG{price_gap:.0f}", anticipation
    return True, f"V83_CONTEXT_{ancestry.get('setup','OK')}", anticipation


def ema9_arc_entry_allowed(side, signal, now=None):
    relation, arc = ema9_arc_relation(side, now)
    stage = arc.get("stage")
    direction = arc.get("direction")
    wanted = "UP" if side == "YES" else "DOWN"
    opposite = "DOWN" if wanted == "UP" else "UP"
    wanted_sign = 1 if wanted == "UP" else -1

    # Preferred continuation: enter with a developing/releasing EMA9 arc.
    if relation == "HEALTHY" and stage in ("RELEASE", "BUILDING", "EXPANDING", "LOADED_COIL"):
        return True, f"EMA9_{stage}_{direction}", arc

    # Critical V8.1 transition: the end of one arc can be the beginning of the
    # opposite trade BEFORE EMA9 crosses EMA30. Example: mature UP arc curls
    # down -> NO may arm while EMA9 is still above EMA30.
    if stage == "ROLLING" and direction != wanted:
        curvature = arc.get("curvature") or 0.0
        price_gap = arc.get("price_gap") or 0.0
        slope9 = arc.get("slope9") or 0.0
        turn_toward_wanted = curvature * wanted_sign >= EMA9_ARC_ROLL_MIN_CURVATURE
        price_leading_turn = price_gap * wanted_sign >= 0
        slope_already_turned = slope9 * wanted_sign >= EMA9_ARC_MIN_SLOPE
        if turn_toward_wanted and (price_leading_turn or slope_already_turned):
            return True, f"EMA9_ROLLOVER_TO_{wanted}", arc

    # V8.8: mature/extended parent move can offer a countertrend pullback BEFORE
    # EMA9 crosses EMA30. This is anticipation, not proof of a full reversal.
    pullback_ok, pullback_reason = v88_exhaustion_pullback_ok(side, signal, now)
    if pullback_ok:
        return True, pullback_reason, arc

    # V8.5: continuous cross-contract ancestry can anticipate the next arc or
    # continuation at EMA30 before the generic arc label catches up.
    anc = ema9_ancestry_state(now)
    if anc.get("anticipated") == wanted and anc.get("setup") in ("PRE_CROSS_UP", "PRE_CROSS_DOWN", "EMA30_REJECTION_UP", "EMA30_REJECTION_DOWN"):
        return True, anc.get("setup"), arc

    # V8.5: EMA9-to-EMA30 rejection/failed approach may lead price.  Price can
    # temporarily be on the wrong side of EMA30; EMA9 structure gets priority.
    rej = v83_rejection_quality(now)
    if rej.get("state") == f"EMA30_REJECTION_{wanted}" and rej.get("strength",0) >= 60:
        return True, f"EMA30_REJECTION_{wanted}_S{rej.get('strength',0):.0f}", arc
    if rej.get("state") == f"WEAK_{opposite}_REJECTION" and rej.get("strength",0) >= 30:
        return True, f"FADE_WEAK_{opposite}_REJECTION_TO_{wanted}", arc

    # EXTENDED continuation can still work, but demand a stronger existing signal.
    if relation == "HEALTHY" and stage == "EXTENDED" and signal.get("signal_grade") in ("A", "A+"):
        return True, f"EMA9_EXTENDED_CONFIRMED_{direction}", arc
    return False, f"EMA9_BLOCK_{stage}_{direction}_{relation}", arc


def thesis_health(side, now=None):
    """Paper-only V7.7 thesis health from parent/local/EMA evidence.

    Returns STRONG / NEUTRAL / WEAK / INVALIDATED plus context. Parent direction
    is context, not a veto: local reversal and EMA behavior carry more weight.
    """
    if now is None:
        now = time.time()
    candles = observer_candles()
    macro = macro_leg_state(candles)
    stretch = ema_stretch_state(candles)
    form = formation_state(candles, macro)
    impulse = impulse_observer_state(now)
    wanted = "UP" if side == "YES" else "DOWN"
    opposite = "DOWN" if wanted == "UP" else "UP"
    score = 0
    reasons = []
    if macro.get("direction") == wanted:
        score += 1; reasons.append("parent_aligned")
    elif macro.get("direction") == opposite:
        score -= 1; reasons.append("parent_counter")
    ema_side = stretch.get("side")
    if (wanted == "UP" and ema_side == "ABOVE") or (wanted == "DOWN" and ema_side == "BELOW"):
        score += 1; reasons.append("ema9_support")
    elif ema_side in ("ABOVE", "BELOW"):
        score -= 1; reasons.append("ema9_against")
    local = form.get("local_regime")
    if local in ("TREND", "RELEASE", "IMPULSE"):
        net = btc_change(30, now) or 0.0
        if (wanted == "UP" and net > 0) or (wanted == "DOWN" and net < 0):
            score += 2; reasons.append("local_impulse_support")
        elif abs(net) >= 15:
            score -= 2; reasons.append("local_impulse_against")
    if form.get("failure") == ("FAILED_DOWN" if wanted == "UP" else "FAILED_UP"):
        score += 1; reasons.append("failed_break_support")
    if form.get("failure") == ("FAILED_UP" if wanted == "UP" else "FAILED_DOWN"):
        score -= 2; reasons.append("failed_break_against")
    if impulse.get("direction") == wanted:
        score += 2; reasons.append("impulse_support")
    elif impulse.get("direction") == opposite:
        score -= 2; reasons.append("impulse_against")
    health = "STRONG" if score >= 3 else "NEUTRAL" if score >= 0 else "WEAK" if score >= -2 else "INVALIDATED"
    return health, score, reasons, macro, form, stretch


def paper_manage(ticker, yes_ask, no_ask):
    global paper_realized_pnl

    bids = {
        "YES": (1.0 - no_ask) if no_ask is not None else None,
        "NO": (1.0 - yes_ask) if yes_ask is not None else None,
    }

    for side in SIDES:
        position = paper_positions[side]
        bid = bids[side]
        if position is None or bid is None or position["ticker"] != ticker:
            continue

        value = position["qty"] * bid
        pnl = value - position["cost"]
        roi = pnl / position["cost"] if position["cost"] else 0.0
        position["mfe_pct"] = max(position["mfe_pct"], roi * 100)
        position["mae_pct"] = min(position["mae_pct"], roi * 100)

        # Record profit milestones without forcing an exit.
        for milestone in PROFIT_MILESTONES:
            if roi >= milestone and milestone not in position["milestones_hit"]:
                position["milestones_hit"].add(milestone)
                label = f"HIT_{int(milestone * 100)}PCT"
                log_paper_event("MILESTONE", position, bid, label)
                print(f"📈 PAPER MILESTONE | #{position['trade_id']} {side} | +{int(milestone * 100)}% reached | current P&L=${pnl:+.2f}")

        reason = None
        peak_roi = position["mfe_pct"] / 100.0
        seconds_left = None
        # current_close_ts is injected by process_top_of_book as a timestamp directly.
        if isinstance(getattr(paper_manage, "current_close_ts", None), (int, float)):
            seconds_left = max(0.0, paper_manage.current_close_ts - time.time())
        position["seconds_to_close"] = seconds_left if seconds_left is not None else position.get("seconds_to_close")

        target_price = parse_target_price(active_target)
        if btc_last_price is not None and target_price is not None:
            target_distance = btc_last_price - target_price
            favorable_cushion = target_distance if side == "YES" else -target_distance
            position["target_price"] = target_price
            position["target_distance"] = target_distance
            position["favorable_cushion"] = favorable_cushion
        else:
            favorable_cushion = None

        # V7.1 CHOP SNIPER management is intentionally different from CORE.
        # It gets room to oscillate; exits are based on profit, structural
        # breakout, late loss of recovery time, or a deep paper guardrail.
        if position.get("strategy") == "CHOP_SNIPER":
            low = position.get("chop_low")
            high = position.get("chop_high")
            width = position.get("chop_width") or 0.0
            eff60_now = btc_trend_efficiency(60, 5)
            ch30_now = btc_change(30)
            breakout_buffer = max(10.0, width * CHOP_BREAKOUT_BUFFER_FRACTION)

            structural_break = False
            if btc_last_price is not None and low is not None and high is not None:
                if side == "YES":
                    structural_break = (
                        btc_last_price < low - breakout_buffer
                        and eff60_now is not None and eff60_now >= CHOP_BREAKOUT_EFFICIENCY
                        and ch30_now is not None and ch30_now <= -CHOP_BREAKOUT_MIN_MOVE_30S
                    )
                else:
                    structural_break = (
                        btc_last_price > high + breakout_buffer
                        and eff60_now is not None and eff60_now >= CHOP_BREAKOUT_EFFICIENCY
                        and ch30_now is not None and ch30_now >= CHOP_BREAKOUT_MIN_MOVE_30S
                    )

            sniper_tp = CHOP_SNIPER_TP_ROI
            sniper_tp_reason = "CHOP_SNIPER_TP_35"
            if seconds_left is not None:
                if seconds_left <= TP_MID_SECONDS_LEFT:
                    sniper_tp = LATE_PROFIT_TP_ROI
                    sniper_tp_reason = "CHOP_SNIPER_LATE_TP_22_5"
                elif seconds_left <= TP_NORMAL_SECONDS_LEFT:
                    sniper_tp = CORE_SIDEWAYS_TP_MID_ROI
                    sniper_tp_reason = "CHOP_SNIPER_MID_TP_30"

            if roi >= sniper_tp:
                reason = sniper_tp_reason
            elif structural_break:
                reason = "CHOP_SNIPER_STRUCTURE_BREAK"
            elif seconds_left is not None and seconds_left <= CHOP_SNIPER_LATE_EXIT_SECONDS and roi < 0:
                reason = "CHOP_SNIPER_TIME_EXIT"
            elif roi <= -CHOP_SNIPER_EMERGENCY_STOP:
                reason = "CHOP_SNIPER_EMERGENCY_75"

            if reason:
                global chop_sniper_last_exit_time
                if pnl < 0 and position.get("v85_countertrend_entry"):
                    v85_last_failed_countertrend[side] = time.time()
                paper_realized_pnl += pnl
                log_paper_event("EXIT", position, bid, reason)
                record_contract_trade(position, bid, pnl, reason)
                print(
                    f"💰 CHOP SNIPER EXIT | #{position['trade_id']} {side} @ {bid:.3f} "
                    f"| {reason} | peak={peak_roi*100:.1f}% | P&L=${pnl:+.2f} "
                    f"| total=${paper_realized_pnl:+.2f}"
                )
                paper_positions[side] = None
                last_paper_exit_time[side] = time.time()
                chop_sniper_last_exit_time = time.time()
            continue

        # V7.2 CORE management:
        # 1) If CORE starts behaving sideways/choppy, bank +35% while there is
        #    still >5m left rather than waiting for +50% or a large giveback.
        # 2) With >10m left, give losing trades substantially more recovery
        #    room, especially in sideways/chop-like structure.
        # 3) Clean directional CORE keeps the established V7 management.
        eff60_now = btc_trend_efficiency(60, 5)
        r60_now = btc_range(60)
        r180_now = btc_range(180)
        sideways_like = (
            eff60_now is not None
            and eff60_now <= CORE_SIDEWAYS_EFF_MAX
            and r60_now is not None
            and r180_now is not None
        )

        sideways_tp = CORE_SIDEWAYS_TP_ROI
        sideways_tp_reason = "CORE_SIDEWAYS_TP_35"
        if seconds_left is not None:
            if seconds_left <= TP_MID_SECONDS_LEFT:
                sideways_tp = LATE_PROFIT_TP_ROI
                sideways_tp_reason = "CORE_LATE_TP_22_5"
            elif seconds_left <= TP_NORMAL_SECONDS_LEFT:
                sideways_tp = CORE_SIDEWAYS_TP_MID_ROI
                sideways_tp_reason = "CORE_SIDEWAYS_MID_TP_30"

        health, health_score, health_reasons, health_macro, health_form, health_stretch = thesis_health(side)
        arc_relation, arc = ema9_arc_relation(side)
        arc_stage = arc.get("stage", "WARMING")
        # Require a sustained EMA9 break before a normal arc-driven exit. This
        # prevents entry -> immediate exit from a transient curvature wobble.
        if arc_relation == "BROKEN":
            if position.get("ema9_arc_broken_since") is None:
                position["ema9_arc_broken_since"] = time.time()
        else:
            position["ema9_arc_broken_since"] = None
        broken_for = 0.0 if position.get("ema9_arc_broken_since") is None else time.time() - position["ema9_arc_broken_since"]
        # V8.5: early in the contract we are intentionally more flexible.  A
        # correct anticipated arc can wobble before it develops.
        if seconds_left is not None and seconds_left >= EARLY_FLEX_SECONDS_LEFT:
            required_break_seconds = EARLY_ARC_BREAK_CONFIRM_SECONDS
        elif seconds_left is not None and seconds_left >= MID_FLEX_SECONDS_LEFT:
            required_break_seconds = MID_ARC_BREAK_CONFIRM_SECONDS
        else:
            required_break_seconds = NORMAL_ARC_BREAK_CONFIRM_SECONDS
        structural_failed, structural_thesis = v83_structural_failure(side)
        same_side_valid = structural_thesis.get("state") in ("VALID", "STRONG")
        arc_break_score, arc_break_reasons = v86_arc_break_evidence(side, arc)
        arc_break_confirmed = (
            arc_relation == "BROKEN"
            and broken_for >= required_break_seconds
            and arc_break_score >= V86_ARC_BREAK_MIN_EVIDENCE
            and not same_side_valid
        )
        proven_floor = max(PROVEN_MFE_MIN_FLOOR, peak_roi - PROVEN_MFE_GIVEBACK)

        # V9.2 structural manager.  Percent P&L is context; BTC structure has
        # authority.  This is intentionally asymmetric: a healthy thesis gets
        # room, while a deteriorating proven winner is protected aggressively.
        v92_snap = v91_structural_snapshot(ticker, yes_ask, no_ask, getattr(paper_manage, "current_close_ts", None), time.time()) if V92_MANAGER_ENABLED else None
        if v92_snap:
            v92_own_score = v92_snap.get("yes_structural_score") if side == "YES" else v92_snap.get("no_structural_score")
            v92_opp_score = v92_snap.get("no_structural_score") if side == "YES" else v92_snap.get("yes_structural_score")
            v92_hold = v92_snap.get("yes_hold_authority") if side == "YES" else v92_snap.get("no_hold_authority")
            v92_target_event = v92_snap.get("target_event") or "NONE"
            v92_gap_motion = v92_snap.get("gap_motion") or "WARMING"
            v92_ordering = v92_snap.get("ordering") or ""
            v92_target_side = v92_snap.get("target_side")
            v92_ema30_side = v92_snap.get("ema30_side")
            v92_ema30_event = v92_snap.get("ema30_event") or "NONE"
        else:
            v92_own_score = v92_opp_score = None
            v92_hold = "UNKNOWN"
            v92_target_event = v92_gap_motion = v92_ordering = ""
            v92_target_side = v92_ema30_side = None
            v92_ema30_event = "NONE"

        wanted_target_side = side
        opposite_target_side = "NO" if side == "YES" else "YES"
        target_accepted_against = v92_target_event == f"TARGET_ACCEPTED_{opposite_target_side}"
        ema30_accepted_against = (
            (side == "YES" and v92_ema30_event == "EMA30_ACCEPTED_BELOW") or
            (side == "NO" and v92_ema30_event == "EMA30_ACCEPTED_ABOVE")
        )
        target_favorable_now = v92_target_side == wanted_target_side
        score_advantage = None if v92_own_score is None or v92_opp_score is None else v92_own_score - v92_opp_score
        structure_strong = v92_hold == "STRONG" and (score_advantage is None or score_advantage >= 2)
        structure_healthy = v92_hold in ("STRONG", "HOLD") and not target_accepted_against and not ema30_accepted_against
        structure_weak = v92_hold in ("WEAK", "INVALIDATE") or (score_advantage is not None and score_advantage <= -2)
        structure_broken = (v92_hold == "INVALIDATE" and (target_accepted_against or ema30_accepted_against or (score_advantage is not None and score_advantage <= -4)))

        # State label is logged to console only on transition.
        if structure_strong and target_favorable_now and peak_roi >= V92_SQUEEZE_MIN_MFE and (seconds_left is None or seconds_left >= V92_SQUEEZE_MIN_SECONDS):
            v92_state = "SQUEEZE"
        elif structure_healthy:
            v92_state = "HOLD"
        elif structure_weak and not structure_broken:
            v92_state = "PROTECT"
        else:
            v92_state = "EXIT" if structure_broken else "HOLD"
        if position.get("v92_manager_state") != v92_state:
            position["v92_manager_state"] = v92_state
            print(f"🧠 V9.2 MANAGER | #{position['trade_id']} {side} | {v92_state} | hold={v92_hold} score={v92_own_score}/{v92_opp_score} target={v92_target_event} gap={v92_gap_motion}")

        # V9.2.4 ADAPTIVE PROVEN MANAGER
        # Once MFE proves the trade, profit percentage becomes a ratchet only
        # when structural perception weakens. Healthy SQUEEZE/HOLD remains free
        # to run.  COLLAPSING_FAST is treated as an early warning rather than
        # waiting for the quote to fall through the old hard floor.
        v924_proven = peak_roi >= V924_PROVEN_ARM_MFE
        v924_collapsing = v92_gap_motion in ("COLLAPSING", "COLLAPSING_FAST")
        v924_deteriorating = (
            v924_proven
            and (
                structure_weak
                or v924_collapsing
                or target_accepted_against
                or ema30_accepted_against
                or (score_advantage is not None and score_advantage <= 0)
            )
            and not structure_strong
        )

        if peak_roi >= 0.50:
            v924_min_lock = V924_MIN_LOCK_50
        elif peak_roi >= 0.30:
            v924_min_lock = V924_MIN_LOCK_30
        elif peak_roi >= 0.20:
            v924_min_lock = V924_MIN_LOCK_20
        elif peak_roi >= V924_PROVEN_ARM_MFE:
            v924_min_lock = V924_MIN_LOCK_17
        else:
            v924_min_lock = None

        if v924_deteriorating:
            if v92_hold == "INVALIDATE" or target_accepted_against or ema30_accepted_against:
                v924_giveback = V924_INVALIDATE_GIVEBACK
            elif v924_collapsing:
                v924_giveback = V924_COLLAPSE_GIVEBACK
            else:
                v924_giveback = V924_WEAK_GIVEBACK
            v924_dynamic_floor = max(v924_min_lock, peak_roi - v924_giveback)
        else:
            v924_dynamic_floor = None

        if v924_deteriorating:
            if position.get("v924_protect_since") is None:
                position["v924_protect_since"] = time.time()
                print(
                    f"🛡️ V9.2.4 PROVEN PROTECT ARMED | #{position['trade_id']} {side} "
                    f"| peak={peak_roi:.1%} floor={v924_dynamic_floor:.1%} "
                    f"| hold={v92_hold} score={v92_own_score}/{v92_opp_score} gap={v92_gap_motion}"
                )
        else:
            position["v924_protect_since"] = None

        v924_protect_age = (
            0.0 if position.get("v924_protect_since") is None
            else time.time() - position["v924_protect_since"]
        )

        # V8.6 bird-in-hand ratchet: protect useful 17/20/23% waves without
        # forcing an immediate take-profit. The floor only activates after the
        # corresponding peak has actually been seen.
        bird_floor = None
        bird_label = None
        if peak_roi >= BIRD_23_TRIGGER:
            bird_floor, bird_label = BIRD_23_FLOOR, "BIRD_IN_HAND_23_TO_15"
        elif peak_roi >= BIRD_20_TRIGGER:
            bird_floor, bird_label = BIRD_20_FLOOR, "BIRD_IN_HAND_20_TO_12"
        elif peak_roi >= BIRD_17_TRIGGER:
            bird_floor, bird_label = BIRD_17_FLOOR, "BIRD_IN_HAND_17_TO_10"

        # Favorable cushion normalized to recent volatility. Used only to decide
        # whether a healthy EMA9 arc deserves to keep running through a normal TP.
        cushion60 = None
        if favorable_cushion is not None and r60_now not in (None, 0):
            cushion60 = favorable_cushion / max(1.0, r60_now)
        runner_ok = (
            EMA9_ARC_RUNNER_OVERRIDE
            and arc_relation == "HEALTHY"
            and arc_stage in ("RELEASE", "BUILDING", "EXPANDING")
            and seconds_left is not None
            and seconds_left > EMA9_ARC_RUNNER_MIN_SECONDS_LEFT
            and (cushion60 is None or cushion60 >= EMA9_ARC_RUNNER_MIN_CUSHION60)
        )

        # V8.1 lifecycle: anticipation gets a short leash; once proven, ordinary
        # EMA9 noise must not throw away the new arc.
        entry_age = time.time() - position.get("v81_entry_ts", position.get("entry_ts", time.time()))
        if not position.get("v81_confirmed") and (roi >= ANTICIPATION_CONFIRM_ROI or entry_age >= ANTICIPATION_CONFIRM_SECONDS and arc_relation == "HEALTHY"):
            position["v81_confirmed"] = True
        fast_fail = (
            position.get("v81_anticipation") and not position.get("v81_confirmed")
            and entry_age <= ANTICIPATION_FAST_FAIL_SECONDS and roi <= ANTICIPATION_FAIL_ROI
            and structural_failed
        )
        cushion_lock = (
            favorable_cushion is not None and favorable_cushion >= PROVEN_TARGET_CUSHION_DOLLARS
            and seconds_left is not None and PROVEN_TARGET_CUSHION_SECONDS <= seconds_left <= PROVEN_TARGET_CUSHION_MAX_SECONDS
        )
        if cushion_lock and position.get("v81_cushion_lock_since") is None:
            position["v81_cushion_lock_since"] = time.time()
        elif not cushion_lock:
            position["v81_cushion_lock_since"] = None
        cushion_locked_for = 0.0 if position.get("v81_cushion_lock_since") is None else time.time() - position["v81_cushion_lock_since"]
        strong_cushion_lock = cushion_lock and cushion_locked_for >= 3.0

        # V8.5: THESIS_INVALIDATED is not allowed to kill an intact EMA9 arc.
        # Existing thesis score can raise concern, but a normal Core exit now
        # needs the EMA9 arc itself to be BROKEN (except emergency/expiry rules).
        swirl_now = v84_swirl_state()

        # V8.5 intent is dynamic: a cheap snipe can earn promotion to an arc
        # rider only after EMA9/30 actually separate into a healthy release.
        if (
            position.get("trade_intent") in ("SNIP", "ANTICIPATION", "CORE")
            and not swirl_now
            and arc_relation == "HEALTHY"
            and arc_stage in ("RELEASE", "BUILDING", "EXPANDING")
        ):
            position["trade_intent"] = "ARC_RIDER"

        thesis_diff_now, own_thesis_now, opp_thesis_now = v85_thesis_advantage(side)
        strongly_wrong_now = (
            thesis_diff_now <= -V85_PARENT_VETO_DIFF
            and own_thesis_now.get("state") == "FAILED"
            and opp_thesis_now.get("state") == "STRONG"
        )
        structural_stop = (
            entry_age >= V85_STRUCTURAL_STOP_MIN_AGE
            and roi <= V85_STRUCTURAL_STOP_ROI
            and strongly_wrong_now
            and not strong_cushion_lock
        )

        # V9.2.3: a trade that has already demonstrated substantial edge may
        # keep running while structure is healthy, but it may not be donated
        # back into a large loss.  This is deliberately much looser than the
        # old Bird floors: +20% only protects roughly breakeven; +30% protects
        # +5%; +50% protects +15%.
        v923_proven_floor = None
        if peak_roi >= 0.50:
            v923_proven_floor = V923_PROVEN_50_FLOOR
        elif peak_roi >= 0.30:
            v923_proven_floor = V923_PROVEN_30_FLOOR
        elif peak_roi >= 0.20:
            v923_proven_floor = V923_PROVEN_20_FLOOR

        if fast_fail:
            reason = "ANTICIPATION_FAST_FAIL"
        elif (
            v924_dynamic_floor is not None
            and roi <= v924_dynamic_floor
            and v924_protect_age >= V924_PROTECT_CONFIRM_SECONDS
            and not strong_cushion_lock
        ):
            reason = "V924_ADAPTIVE_PROVEN_PROTECT"
        elif (
            v923_proven_floor is not None
            and roi <= v923_proven_floor
            and entry_age >= 3.0
        ):
            reason = "V923_PROVEN_HARD_FLOOR"
        elif structural_stop and (not V92_MANAGER_ENABLED or structure_broken):
            reason = "V92_STRUCTURAL_INVALIDATION"
        elif (
            swirl_now
            and peak_roi >= V84_SWIRL_LOCK_MFE
            and roi <= max(V84_SWIRL_MIN_FLOOR, peak_roi - V84_SWIRL_GIVEBACK)
        ):
            # In tight EMA9/30 swirl, don't turn a proven snipe into a loser.
            reason = "CORE_SWIRL_PROFIT_LOCK"
        elif swirl_now and roi >= V84_SWIRL_SNIP_TP:
            reason = "CORE_SWIRL_SNIP_TP_22_5"
        elif bird_floor is not None and roi <= bird_floor and (not V92_MANAGER_ENABLED or structure_weak):
            # V9.2: Bird is an alarm.  It may execute only when BTC structure
            # agrees that the thesis is weakening.
            reason = "V92_PROTECT_" + bird_label
        elif (
            V92_MANAGER_ENABLED
            and entry_age >= V92_STRUCTURAL_EXIT_MIN_AGE
            and structure_broken
            and not strong_cushion_lock
        ):
            reason = "V92_STRUCTURE_BROKEN"
        elif (
            V92_MANAGER_ENABLED
            and peak_roi >= V92_PROTECT_MFE
            and structure_weak
            and roi <= peak_roi - (V92_PROTECT_GIVEBACK_WEAK if v92_hold in ("WEAK","INVALIDATE") else V92_PROTECT_GIVEBACK_HOLD)
            and not strong_cushion_lock
        ):
            reason = "V92_PROTECT_WINNER_DIVERGENCE"
        elif peak_roi >= PROVEN_MFE_PROTECT and roi <= proven_floor and arc_break_confirmed and not strong_cushion_lock and (not V92_MANAGER_ENABLED or structure_weak):
            reason = "EMA9_PROTECT_PROVEN"
        elif (
            EMA9_ARC_EXIT_MANAGEMENT
            and arc_break_confirmed
            and roi <= THESIS_INVALIDATION_MAX_ROI
            and peak_roi < PROVEN_MFE_PROTECT
            and not strong_cushion_lock
            and not same_side_valid
        ):
            reason = "EMA9_ARC_BROKEN"
        elif (
            sideways_like
            and seconds_left is not None
            and roi >= sideways_tp
            and not runner_ok
            and (not V92_MANAGER_ENABLED or not structure_healthy)
        ):
            reason = sideways_tp_reason
        elif (
            not sideways_like
            and seconds_left is not None
            and seconds_left <= TP_MID_SECONDS_LEFT
            and roi >= LATE_PROFIT_TP_ROI
            and not runner_ok
            and (not V92_MANAGER_ENABLED or not structure_healthy)
        ):
            reason = "CORE_LATE_TP_22_5"
        elif position.get("early_trade") and roi >= EARLY_TAKE_PROFIT_ROI:
            reason = "EARLY_TAKE_PROFIT_50"
        elif peak_roi >= TRAIL_ACTIVATE_ROI and roi <= peak_roi - TRAIL_GIVEBACK_ROI and (not V92_MANAGER_ENABLED or structure_weak):
            reason = "V92_STRUCTURAL_TRAIL_AFTER_40"
        elif (
            peak_roi >= 0.20
            and roi <= -0.05
            and not (
                seconds_left is not None
                and seconds_left > PROVEN_RECOVERY_MIN_SECONDS_LEFT
            )
        ):
            # In sideways/chop-like CORE, don't force an early exit merely
            # because a previously positive trade dips below zero; allow the
            # expected rotation time while sufficient contract time remains.
            reason = "PROTECT_PROVEN_TRADE"
        elif (
            seconds_left is not None
            and seconds_left <= LATE_RISK_WINDOW_SECONDS
            and roi <= LATE_TARGET_STOP_ROI
            and favorable_cushion is not None
            and favorable_cushion < 0
            and peak_roi < 0.20
            and (not V92_MANAGER_ENABLED or target_accepted_against or ema30_accepted_against)
            and (
                not EMA9_ARC_EXIT_MANAGEMENT
                or arc_relation in ("BROKEN", "WEAKENING")
                or seconds_left <= EMA9_ARC_HARD_EXPIRY_SECONDS
            )
        ):
            reason = "LATE_TARGET_INVALIDATION"
        else:
            # Dynamic early guardrail. The previous fixed -60% exit was often
            # too early when 10+ minutes remained and price later rotated back.
            if seconds_left is not None and seconds_left >= EARLY_RECOVERY_SECONDS_LEFT:
                emergency_limit = (
                    EARLY_SIDEWAYS_EMERGENCY_STOP if sideways_like
                    else EARLY_CORE_EMERGENCY_STOP
                )
                if roi <= -emergency_limit:
                    reason = (
                        "EARLY_SIDEWAYS_EMERGENCY_85"
                        if sideways_like else "EARLY_EMERGENCY_80"
                    )
            elif roi <= -EMERGENCY_STOP_LOSS:
                reason = "EMERGENCY_STOP_60"

        if reason:
            if pnl < 0 and position.get("v85_countertrend_entry"):
                v85_last_failed_countertrend[side] = time.time()
            paper_realized_pnl += pnl
            log_paper_event("EXIT", position, bid, reason)
            record_contract_trade(position, bid, pnl, reason)
            print(f"💰 PAPER EXIT | #{position['trade_id']} {side} @ {bid:.3f} | {reason} | peak={peak_roi*100:.1f}% | P&L=${pnl:+.2f} | total=${paper_realized_pnl:+.2f}")
            paper_positions[side] = None
            last_paper_exit_time[side] = time.time()


def paper_close_contract(ticker, yes_ask, no_ask):
    global paper_realized_pnl
    bids = {
        "YES": (1.0 - no_ask) if no_ask is not None else None,
        "NO": (1.0 - yes_ask) if yes_ask is not None else None,
    }
    for side in SIDES:
        position = paper_positions[side]
        if position is None or position["ticker"] != ticker:
            continue
        bid = bids[side]
        if bid is None:
            continue
        value = position["qty"] * bid
        pnl = value - position["cost"]
        paper_realized_pnl += pnl
        log_paper_event("EXIT", position, bid, "CONTRACT_CLOSE")
        record_contract_trade(position, bid, pnl, "CONTRACT_CLOSE")
        print(f"💰 PAPER CLOSE | #{position['trade_id']} {side} @ {bid:.3f} | P&L=${pnl:+.2f} | total=${paper_realized_pnl:+.2f}")
        paper_positions[side] = None
        last_paper_exit_time[side] = time.time()


async def settlement_watcher():
    while True:
        try:
            for ticker in list(pending_settlements):
                try:
                    market = await asyncio.to_thread(get_market_snapshot, ticker)
                    result = str(market.get("result", "")).lower()
                    if result in ("yes", "no"):
                        log_settlement(
                            ticker,
                            result.upper(),
                            market.get("settlement_ts") or market.get("settled_time"),
                        )
                        pending_settlements.discard(ticker)
                except Exception:
                    pass
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            raise


# ============================================================
# STRATEGY — SAME RULES, NOW APPLIED TO YES AND NO
# ============================================================

def evaluate_strategy(side, current_price, now=None):
    p90 = get_price_at(side, 90, now)
    p75 = get_price_at(side, 75, now)
    p60 = get_price_at(side, 60, now)

    if p90 is None or p75 is None or p60 is None:
        return None

    m90_75 = p75 - p90
    m90_60 = p60 - p90
    ema9, ema30 = get_ema_values(side)

    if current_price < EARLY_ENTRY_ASK or current_price > MAX_ENTRY_ASK:
        return None

    # Continuation is required for both grades.
    if current_price <= p75 or current_price <= p60:
        return None

    confirmed = (
        current_price >= CONFIRMED_ENTRY_ASK
        and m90_75 >= CONFIRMED_MOM_90_75
        and m90_60 >= CONFIRMED_MOM_90_60
    )
    early = (
        m90_75 >= EARLY_MOM_90_75
        and m90_60 >= EARLY_MOM_90_60
    )

    if not confirmed and not early:
        return None

    return {
        "price": current_price,
        "price_90": p90,
        "price_75": p75,
        "price_60": p60,
        "m90_75": m90_75,
        "m90_60": m90_60,
        "ema_9": ema9,
        "ema_30": ema30,
        "setup_grade": "CONFIRMED" if confirmed else "EARLY",
    }


def early_exception_check(side, signal):
    """Strict escape hatch during the first four minutes."""
    reasons = []
    if signal.get("setup_grade") != "CONFIRMED":
        return False, reasons

    ema9v = signal.get("btc_ema_9")
    ema30v = signal.get("btc_ema_30")
    price = signal.get("btc_price")
    if ema9v is None or ema30v is None or price is None:
        return False, reasons

    ema_aligned = (ema9v > ema30v) if side == "YES" else (ema9v < ema30v)
    price_aligned = (price > ema9v) if side == "YES" else (price < ema9v)
    if not ema_aligned or not price_aligned:
        return False, reasons
    reasons.extend(["ema9_30_aligned", "btc_vs_ema9_aligned"])

    ch60 = signal.get("btc_change_60s")
    eff = signal.get("btc_trend_efficiency_60s")
    if ch60 is None or eff is None:
        return False, reasons
    directional_move = ch60 if side == "YES" else -ch60
    if directional_move < EARLY_MIN_BTC_NET_MOVE_60S:
        return False, reasons
    reasons.append(f"btc60_dir_{directional_move:.0f}")
    if eff < EARLY_MIN_TREND_EFFICIENCY:
        return False, reasons
    reasons.append(f"trend_eff_{eff:.2f}")

    if signal.get("m90_75", 0) < EARLY_MIN_MOM_90_75:
        return False, reasons
    if signal.get("m90_60", 0) < EARLY_MIN_MOM_90_60:
        return False, reasons
    reasons.append("strong_kalshi_momentum")
    return True, reasons


def enrich_signal_context(side, signal, close_ts=None):
    now = time.time()
    session, daypart, et_hour = session_context(now)
    target_price = parse_target_price(active_target)
    target_distance = None
    favorable_cushion = None
    if btc_last_price is not None and target_price is not None:
        target_distance = btc_last_price - target_price
        favorable_cushion = target_distance if side == "YES" else -target_distance

    r30 = btc_range(30, now)
    r60 = btc_range(60, now)
    r180 = btc_range(180, now)
    c1 = current_candle_range()
    avg5 = recent_avg_candle_range(5)
    vr = recent_volume_ratio(5)
    phase, seconds_left, elapsed = contract_phase(close_ts, now)
    ch60 = btc_change(60, now)
    eff60 = btc_trend_efficiency(60, 5, now)

    ema_aligned = None
    price_ema_aligned = None
    if btc_ema_9 is not None and btc_ema_30 is not None:
        ema_aligned = (btc_ema_9 > btc_ema_30) if side == "YES" else (btc_ema_9 < btc_ema_30)
    if btc_last_price is not None and btc_ema_9 is not None:
        price_ema_aligned = (btc_last_price > btc_ema_9) if side == "YES" else (btc_last_price < btc_ema_9)

    score = 0
    reasons = []
    if signal.get("setup_grade") == "CONFIRMED":
        score += 2
        reasons.append("confirmed")
    if ema_aligned:
        score += 2
        reasons.append("ema9_30_aligned")
    if price_ema_aligned:
        score += 1
        reasons.append("btc_vs_ema9_aligned")
    if signal.get("m90_75", 0) >= 0.04:
        score += 1
        reasons.append("strong_90_75")
    if signal.get("m90_60", 0) >= 0.08:
        score += 1
        reasons.append("strong_90_60")
    if favorable_cushion is not None and favorable_cushion > 0:
        score += 1
        reasons.append("target_side_favorable")

    signal_grade = "A+" if score >= 6 else ("A" if score >= 4 else signal.get("setup_grade", ""))
    # A+ sizing is never granted during the observation phase.
    if phase == "OBSERVE" and signal_grade == "A+":
        signal_grade = "A"

    signal.update({
        "signal_grade": signal_grade,
        "a_plus_score": score,
        "a_plus_reasons": ";".join(reasons),
        "session": session,
        "daypart": daypart,
        "et_hour": et_hour,
        "target_price": target_price,
        "target_distance": target_distance,
        "favorable_cushion": favorable_cushion,
        "btc_range_30s": r30,
        "btc_range_60s": r60,
        "btc_range_180s": r180,
        "btc_current_1m_range": c1,
        "btc_avg_5m_candle_range": avg5,
        "btc_volume_ratio": vr,
        "contract_phase": phase,
        "contract_elapsed_seconds": elapsed,
        "btc_change_60s": ch60,
        "btc_trend_efficiency_60s": eff60,
        "early_exception": False,
        "early_exception_reasons": "",
    })
    return signal

# ============================================================
# SIGNAL DISPLAY
# ============================================================

last_signal_time = {
    "YES": 0,
    "NO": 0,
}
last_signal_signature = {
    "YES": None,
    "NO": None,
}


def print_signal(ticker, side, signal, btc_start=None, close_ts=None, yes_ask=None, no_ask=None):
    now = time.time()

    signature = (
        round(signal["price"], 2),
        round(signal["m90_75"], 2),
        round(signal["m90_60"], 2),
    )

    if signature == last_signal_signature[side]:
        return

    if now - last_signal_time[side] < 5:
        return

    last_signal_time[side] = now
    last_signal_signature[side] = signature

    now_wall = time.time()
    signal["btc_price"] = btc_last_price
    signal["btc_ema_9"] = btc_ema_9
    signal["btc_ema_30"] = btc_ema_30
    signal["btc_ema9_above_ema30"] = (
        "YES" if btc_ema_9 is not None and btc_ema_30 is not None and btc_ema_9 > btc_ema_30
        else "NO" if btc_ema_9 is not None and btc_ema_30 is not None
        else ""
    )
    signal["btc_price_above_ema9"] = (
        "YES" if btc_last_price is not None and btc_ema_9 is not None and btc_last_price > btc_ema_9
        else "NO" if btc_last_price is not None and btc_ema_9 is not None
        else ""
    )
    signal["btc_move_from_contract_start"] = (
        btc_last_price - btc_start
        if btc_last_price is not None and btc_start is not None
        else None
    )
    signal["seconds_to_close"] = (
        max(0.0, close_ts - now_wall) if close_ts is not None else None
    )
    enrich_signal_context(side, signal, close_ts)

    phase = signal.get("contract_phase", "CORE")
    if phase == "OBSERVE":
        # V8.5: the contract is new; the BTC market is not. Permit an early
        # trade when continuous ancestry already gives a strong inherited thesis.
        early_ok, early_reason = v84_early_access_allowed(side, now)
        if not early_ok:
            signal["early_exception"] = False
            signal["early_exception_reasons"] = early_reason
            signal["signal_grade"] = "OBSERVE_ONLY"
            log_signal(ticker, side, signal)
            return
        signal["early_exception"] = True
        signal["early_exception_reasons"] = early_reason
        signal["signal_grade"] = "A" if signal.get("signal_grade") == "OBSERVE_ONLY" else signal.get("signal_grade")

    elapsed = signal.get("contract_elapsed_seconds")
    seconds_left_sig = signal.get("seconds_to_close")

    # V7.3: block ordinary late entries when BTC is already too far from the
    # target for the proposed side to be a sensible short-horizon trade.
    if not late_distance_ok(seconds_left_sig, signal.get("target_distance")):
        signal["early_exception_reasons"] = "BLOCK_LATE_FAR_FROM_TARGET"
        log_signal(ticker, side, signal)
        return

    if seconds_left_sig is not None and float(seconds_left_sig) <= EXPIRY_MODE_SECONDS:
        # V7: final minute is edge-only, never ordinary momentum trading.
        target = signal.get("target_price")
        dist = signal.get("target_distance")
        r60 = signal.get("btc_range_60s")
        ch60 = signal.get("btc_change_60s") or 0.0
        cushion_floor = max(25.0, (r60 or 0.0) * 0.50)
        expiry_edge = False
        if dist is not None:
            if side == "YES":
                expiry_edge = dist >= cushion_floor and ch60 > -max(20.0, abs(dist) * 0.50) and signal["price"] < 0.90
            else:
                expiry_edge = dist <= -cushion_floor and ch60 < max(20.0, abs(dist) * 0.50) and signal["price"] < 0.90
        if not expiry_edge:
            signal["early_exception_reasons"] = "BLOCK_FINAL_MINUTE_NO_EDGE"
            log_signal(ticker, side, signal)
            return
        signal["early_exception_reasons"] = "FINAL_MINUTE_EXPIRY_EDGE"

    if (
        elapsed is not None
        and OBSERVATION_SECONDS <= float(elapsed) < STRONG_ONLY_WINDOW_SECONDS
        and signal.get("signal_grade") not in ("A", "A+")
    ):
        # V7: minute 2-4 is tradable only for stronger A/A+ setups.
        # We keep weaker signals in the CSV so this filter can be audited.
        signal["early_exception_reasons"] = "BLOCK_2_4_WEAK_GRADE"
        log_signal(ticker, side, signal)
        return

    # V8.8: attach ticker for blocked-price/chase memory.
    signal["_ticker"] = ticker

    # V8.5: ordinary Core entries must fit the live EMA9 arc. Blocked signals
    # remain in the signal CSV as shadow candidates for counterfactual review.
    if EMA9_ARC_ENTRY_GATE:
        allowed, arc_reason, arc = ema9_arc_entry_allowed(side, signal, now)
        signal["ema9_arc_stage"] = arc.get("stage")
        signal["ema9_arc_direction"] = arc.get("direction")
        if not allowed:
            signal["early_exception_reasons"] = arc_reason
            log_signal(ticker, side, signal)
            print(f"👁️ EMA9 SHADOW CORE | {side} blocked | {arc_reason} | ask={signal['price']:.3f}")
            return
        signal["early_exception_reasons"] = (signal.get("early_exception_reasons") or "") + (";" if signal.get("early_exception_reasons") else "") + arc_reason

        ctx_ok, ctx_reason, anticipation = v83_entry_context(side, signal, now)
        signal["v81_anticipation"] = anticipation
        if not ctx_ok:
            signal["early_exception_reasons"] += ";" + ctx_reason
            log_signal(ticker, side, signal)
            print(f"⏳ V8.5 WAIT | {side} | {ctx_reason} | ask={signal['price']:.3f}")
            return
        signal["early_exception_reasons"] += ";" + ctx_reason

    signal["trade_intent"] = v85_trade_intent(side, signal, now)

    # V9.2 ARM -> TEST -> TRIGGER gate.  Existing signal logic ARMS the idea;
    # structural perception must not show a mature collapsing continuation.
    # Inherited early trends need either a healthy dip/bounce test or accepted
    # territory before they are allowed to TRIGGER.
    if V92_MANAGER_ENABLED:
        v92_entry_snap = v91_structural_snapshot(ticker, yes_ask, no_ask, getattr(paper_manage, "current_close_ts", None), now)
        if v92_entry_snap:
            own = v92_entry_snap.get("yes_structural_score") if side == "YES" else v92_entry_snap.get("no_structural_score")
            opp = v92_entry_snap.get("no_structural_score") if side == "YES" else v92_entry_snap.get("yes_structural_score")
            gap = v92_entry_snap.get("ema_gap") or 0.0
            old_side = "YES" if gap > 0 else "NO" if gap < 0 else None
            mature_collapse = (
                old_side == side
                and v92_entry_snap.get("gap_motion") == "COLLAPSING_FAST"
                and abs(v92_entry_snap.get("parent_distance_norm180") or 0.0) >= 1.25
                and own is not None and opp is not None and own <= opp + 1
            )
            inherited = "EARLY_INHERITED_" in (signal.get("early_exception_reasons") or "")
            wanted_pullback = "YES_HEALTHY_DIP" if side == "YES" else "NO_HEALTHY_BOUNCE"
            accepted_target = v92_entry_snap.get("target_event") == f"TARGET_ACCEPTED_{side}"
            accepted_ema30 = (
                (side == "YES" and v92_entry_snap.get("ema30_event") == "EMA30_ACCEPTED_ABOVE") or
                (side == "NO" and v92_entry_snap.get("ema30_event") == "EMA30_ACCEPTED_BELOW")
            )
            test_passed = v92_entry_snap.get("pullback_state") == wanted_pullback or (accepted_target and accepted_ema30)
            if mature_collapse:
                signal["early_exception_reasons"] = (signal.get("early_exception_reasons") or "") + ";V92_ARM_BLOCK_MATURE_GAP_COLLAPSE"
                log_signal(ticker, side, signal)
                print(f"🛑 V9.2 ARM | {side} blocked | mature parent + collapsing EMA gap | score={own}/{opp}")
                return
            if inherited and not test_passed:
                signal["early_exception_reasons"] = (signal.get("early_exception_reasons") or "") + ";V92_WAIT_TEST_INHERITED"
                log_signal(ticker, side, signal)
                print(f"🧪 V9.2 TEST | {side} inherited trend armed, waiting for pullback/reclaim acceptance")
                return
            signal["early_exception_reasons"] = (signal.get("early_exception_reasons") or "") + ";V92_TRIGGER_STRUCTURAL_TEST"

    log_signal(ticker, side, signal)
    paper_enter(ticker, side, signal["price"], signal)
    if paper_positions.get(side) is not None:
        paper_positions[side]["v81_anticipation"] = bool(signal.get("v81_anticipation"))
        paper_positions[side]["v81_entry_ts"] = time.time()
        paper_positions[side]["v81_confirmed"] = False
        paper_positions[side]["v81_entry_arc"] = signal.get("ema9_arc_stage")

    print()
    print()
    print("=" * 60)
    print(f"🔥 {side} MOMENTUM SIGNAL — {signal.get('signal_grade') or signal.get('setup_grade', '')}")
    print("=" * 60)
    print("TICKER      :", ticker)
    print("SIDE        :", side)
    print(f"CURRENT ASK : {signal['price']:.3f}")
    print(f"90s ASK     : {signal['price_90']:.3f}")
    print(f"75s ASK     : {signal['price_75']:.3f}")
    print(f"60s ASK     : {signal['price_60']:.3f}")
    print()
    print(f"90→75 MOM   : {signal['m90_75']:+.3f}")
    print(f"90→60 MOM   : {signal['m90_60']:+.3f}")
    print()

    if signal["ema_9"] is not None:
        print(f"1M EMA 9    : {signal['ema_9']:.3f}")
    else:
        print("1M EMA 9    : warming up")

    if signal["ema_30"] is not None:
        print(f"1M EMA 30   : {signal['ema_30']:.3f}")
    else:
        print("1M EMA 30   : warming up")

    if signal["ema_9"] is not None and signal["ema_30"] is not None:
        trend = (
            "9 EMA ABOVE 30 EMA"
            if signal["ema_9"] > signal["ema_30"]
            else "9 EMA BELOW 30 EMA"
        )
        print("EMA TREND   :", trend)

    if btc_last_price is not None:
        print(f"BTC/USD     : ${btc_last_price:,.2f}")
    if btc_ema_9 is not None:
        print(f"BTC EMA 9   : ${btc_ema_9:,.2f}")
    if btc_ema_30 is not None:
        print(f"BTC EMA 30  : ${btc_ema_30:,.2f}")

    print(f"SESSION     : {signal.get('session', '')} / {signal.get('daypart', '')} ET hour {signal.get('et_hour', '')}")
    print(f"PHASE       : {signal.get('contract_phase', '')} | elapsed={signal.get('contract_elapsed_seconds') or 0:.0f}s")
    if signal.get("early_exception"):
        print(f"EARLY WHY   : {signal.get('early_exception_reasons', '')}")
    print(f"GRADE       : {signal.get('signal_grade', '')} | score={signal.get('a_plus_score', '')}")
    if signal.get("a_plus_reasons"):
        print(f"GRADE WHY   : {signal.get('a_plus_reasons')}")
    if signal.get("target_price") is not None:
        print(f"TARGET      : ${signal['target_price']:,.2f}")
        print(f"BTC-TARGET  : ${signal['target_distance']:+,.2f} | favorable cushion={signal['favorable_cushion']:+,.2f}")
    if signal.get("btc_range_60s") is not None:
        print(f"BTC RANGE   : 30s=${signal.get('btc_range_30s') or 0:.0f} | 60s=${signal.get('btc_range_60s') or 0:.0f} | 3m=${signal.get('btc_range_180s') or 0:.0f}")
    if signal.get("btc_change_60s") is not None:
        print(f"BTC TREND   : 60s net=${signal.get('btc_change_60s'):+.0f} | efficiency={signal.get('btc_trend_efficiency_60s') or 0:.2f}")
    if signal.get("btc_current_1m_range") is not None:
        print(f"1M CANDLE   : ${signal['btc_current_1m_range']:.0f} | avg5=${signal.get('btc_avg_5m_candle_range') or 0:.0f}")
    if signal.get("btc_volume_ratio") is not None:
        print(f"VOLUME      : {signal['btc_volume_ratio']:.2f}x current minute vs recent")

    print()
    print(">>> PAPER CANDIDATE — NO ORDER <<<")
    print("=" * 60)
    print()


# ============================================================
# PRICE PROCESSING
# ============================================================

last_early_impulse_entry_time = 0.0

def maybe_early_impulse_core(ticker, yes_ask, no_ask, close_ts, now=None):
    """V7.7 paper-only displacement entry during the old 0-2m hard gate."""
    global last_early_impulse_entry_time
    if now is None:
        now = time.time()
    if close_ts is None:
        return False
    seconds_left = max(0.0, close_ts - now)
    elapsed = 900.0 - seconds_left
    if not (EARLY_IMPULSE_MIN_ELAPSED <= elapsed < EARLY_IMPULSE_MAX_ELAPSED):
        return False
    if now - last_early_impulse_entry_time < EARLY_IMPULSE_COOLDOWN:
        return False
    imp = impulse_observer_state(now)
    if imp.get("direction") == "NONE" or imp.get("score", 0) < EARLY_IMPULSE_MIN_SCORE:
        return False
    if abs(imp.get("ch30") or 0.0) < EARLY_IMPULSE_MIN_MOVE_30S or (imp.get("eff30") or 0.0) < EARLY_IMPULSE_MIN_EFF30:
        return False
    side = "YES" if imp["direction"] == "UP" else "NO"
    ask = yes_ask if side == "YES" else no_ask
    if ask is None or not (EARLY_IMPULSE_MIN_ASK <= ask <= EARLY_IMPULSE_MAX_ASK):
        return False
    if paper_positions[side] is not None or time.time() - last_paper_exit_time[side] < PAPER_REENTRY_COOLDOWN:
        return False
    target_price = parse_target_price(active_target)
    target_distance = btc_last_price - target_price if btc_last_price is not None and target_price is not None else None
    favorable = target_distance if side == "YES" else (-target_distance if target_distance is not None else None)
    session, daypart, et_hour = session_context()
    signal = {
        "price": ask, "setup_grade": "IMPULSE", "signal_grade": "IMPULSE",
        "seconds_to_close": seconds_left, "btc_price": btc_last_price,
        "btc_ema_9": btc_ema_9, "btc_ema_30": btc_ema_30,
        "session": session, "daypart": daypart, "et_hour": et_hour,
        "target_price": target_price, "target_distance": target_distance, "favorable_cushion": favorable,
        "btc_range_30s": btc_range(30), "btc_range_60s": btc_range(60), "btc_range_180s": btc_range(180),
        "btc_current_1m_range": current_candle_range(), "btc_avg_5m_candle_range": recent_avg_candle_range(5),
        "btc_volume_ratio": recent_volume_ratio(5), "contract_phase": "EARLY_IMPULSE",
        "contract_elapsed_seconds": elapsed, "btc_change_60s": btc_change(60),
        "btc_trend_efficiency_60s": btc_trend_efficiency(60, 5),
        "strategy": "EARLY_IMPULSE_CORE", "trade_intent": "EARLY_IMPULSE", "market_regime": "IMPULSE",
        "early_exception": True, "early_exception_reasons": f"EARLY_IMPULSE_{imp['direction']}_S{imp['score']}", "early_trade": True,
        "chop_low": None, "chop_high": None, "chop_width": None, "chop_edge": "",
    }
    paper_enter(ticker, side, ask, signal)
    pos = paper_positions.get(side)
    if pos is not None and pos.get("ticker") == ticker:
        pos["early_exception"] = True
        pos["early_exception_reasons"] = f"EARLY_IMPULSE_{imp['direction']}_S{imp['score']}"
        pos["early_trade"] = True
        pos["stake_cap"] = EARLY_IMPULSE_STAKE
        last_early_impulse_entry_time = now
        print(f"⚡ EARLY IMPULSE CORE | {side} @ {ask:.3f} | elapsed={elapsed:.0f}s | BTC30={imp.get('ch30',0):+.1f} | eff30={imp.get('eff30',0):.2f}")
        return True
    return False


def v87_update_rollover_watch(close_ts, now=None):
    """Arm a directional handoff when the EMA9 arc rolls before expiry."""
    global rollover_handoff_state
    now = time.time() if now is None else now
    if close_ts is None or btc_last_price is None or btc_ema_9 is None or btc_ema_30 is None:
        return
    left = close_ts - now
    if not (0 < left <= ROLLOVER_WATCH_SECONDS):
        return

    arc = ema9_arc_state(now)
    anc = ema9_ancestry_state(now)
    ch3, ch6, ch9 = btc_change(3, now) or 0.0, btc_change(6, now) or 0.0, btc_change(9, now) or 0.0
    target = parse_target_price(active_target)
    r60 = btc_range(60) or 1.0
    dist = (btc_last_price - target) if target is not None else None
    side, score, reasons = None, 0, []
    stage, direction = arc.get("stage"), arc.get("direction")
    curvature = arc.get("curvature") or 0.0

    if stage == "ROLLING" and direction == "UP":
        side = "NO"; score += 2; reasons.append("ARC_UP_ROLLING")
        if curvature < 0: score += 1; reasons.append("CURV_DOWN")
        if min(ch3, ch6, ch9) < -3: score += 1; reasons.append("369_DOWN")
    elif stage == "ROLLING" and direction == "DOWN":
        side = "YES"; score += 2; reasons.append("ARC_DOWN_ROLLING")
        if curvature > 0: score += 1; reasons.append("CURV_UP")
        if max(ch3, ch6, ch9) > 3: score += 1; reasons.append("369_UP")
    elif anc.get("anticipated") in ("UP", "DOWN"):
        side = "YES" if anc.get("anticipated") == "UP" else "NO"
        score += 2; reasons.append("ANCESTRY_"+anc.get("anticipated"))

    if side is None:
        return
    if side == "NO" and btc_last_price < btc_ema_9:
        score += 1; reasons.append("PRICE_BELOW_E9")
    if side == "YES" and btc_last_price > btc_ema_9:
        score += 1; reasons.append("PRICE_ABOVE_E9")
    if dist is not None and abs(dist) <= max(20.0, 0.50 * r60):
        score += 1; reasons.append("TARGET_NEAR")

    if score >= ROLLOVER_MIN_SCORE:
        rollover_handoff_state = {"side": side, "score": score, "ts": now, "why": ",".join(reasons)}


def v87_try_handoff_entry(ticker, yes_ask, no_ask, close_ts, now=None):
    """Selective first-minute A+ entry from a prior-contract rollover thesis."""
    global rollover_handoff_used_ticker
    now = time.time() if now is None else now
    st = rollover_handoff_state
    if not st.get("side") or now - st.get("ts", 0) > ROLLOVER_STATE_TTL_SECONDS:
        return False
    if rollover_handoff_used_ticker == ticker or close_ts is None:
        return False
    elapsed = 900.0 - max(0.0, close_ts - now)
    if not (0 <= elapsed <= ROLLOVER_HANDOFF_ENTRY_WINDOW):
        return False

    side = st["side"]
    ask = yes_ask if side == "YES" else no_ask
    if ask is None or not (ROLLOVER_MIN_ASK <= ask <= ROLLOVER_MAX_ASK):
        return False
    if paper_positions[side] is not None or now - last_paper_exit_time[side] < PAPER_REENTRY_COOLDOWN:
        return False

    target = parse_target_price(active_target)
    if target is None or btc_last_price is None:
        return False
    dist = btc_last_price - target
    favorable = dist if side == "YES" else -dist
    r60 = btc_range(60) or 1.0
    if favorable < -max(20.0, ROLLOVER_NEW_TARGET_RANGE_FRAC * r60):
        return False

    th = v83_structural_thesis(side, now)
    arc_relation, arc = ema9_arc_relation(side)
    if th.get("state") not in ("VALID", "STRONG") and arc_relation == "BROKEN":
        return False

    session, daypart, et_hour = session_context()
    signal = {
        "price": ask, "setup_grade": "HANDOFF", "signal_grade": "A+",
        "a_plus_score": st.get("score", 0),
        "a_plus_reasons": "CONTINUATION_HANDOFF_A+;" + st.get("why", ""),
        "seconds_to_close": max(0.0, close_ts-now), "btc_price": btc_last_price,
        "btc_ema_9": btc_ema_9, "btc_ema_30": btc_ema_30,
        "session": session, "daypart": daypart, "et_hour": et_hour,
        "target_price": target, "target_distance": dist, "favorable_cushion": favorable,
        "btc_range_30s": btc_range(30), "btc_range_60s": r60, "btc_range_180s": btc_range(180),
        "btc_current_1m_range": current_candle_range(), "btc_avg_5m_candle_range": recent_avg_candle_range(5),
        "btc_volume_ratio": recent_volume_ratio(5), "contract_phase": "CONTINUATION_HANDOFF",
        "contract_elapsed_seconds": elapsed, "btc_change_60s": btc_change(60),
        "btc_trend_efficiency_60s": btc_trend_efficiency(60,5),
        "early_exception": True, "early_exception_reasons": "CONTINUATION_HANDOFF_A+;" + st.get("why",""),
        "early_trade": True, "strategy": "CONTINUATION_HANDOFF", "trade_intent": "ARC_RIDER",
        "market_regime": "HANDOFF", "chop_low": None, "chop_high": None, "chop_width": None, "chop_edge": "",
    }
    paper_enter(ticker, side, ask, signal)
    if paper_positions.get(side) is not None and paper_positions[side].get("ticker") == ticker:
        rollover_handoff_used_ticker = ticker
        paper_positions[side]["v81_anticipation"] = True
        paper_positions[side]["v81_entry_ts"] = now
        paper_positions[side]["v81_confirmed"] = False
        print(f"🔁 CONTINUATION HANDOFF A+ $15 | {side} @ {ask:.3f} | score={st.get('score')} | {st.get('why')} | newTargetΔ={dist:+.0f}")
        return True
    return False


def process_top_of_book(ticker, yes_ask, no_ask, source, btc_start=None, close_ts=None):
    now = time.time()

    # V7.5 observer is independent of V7.4 trading decisions.
    maybe_start_impulse_event(ticker, yes_ask, no_ask, now)
    update_impulse_lag_events(yes_ask, no_ask, now)
    maybe_log_structure(ticker, close_ts, yes_ask, no_ask, now)
    v85_flash_observer(ticker, yes_ask, no_ask, close_ts, now)
    v9_expiry_observer(ticker, yes_ask, no_ask, close_ts, now)
    v91_perception_observer(ticker, yes_ask, no_ask, close_ts, now)

    paper_manage.current_close_ts = close_ts
    paper_manage(ticker, yes_ask, no_ask)

    # V8.7 continuous handoff: watch the dying arc before expiry and carry it.
    v87_chop_shadow_observer(ticker, yes_ask, no_ask, close_ts)
    v87_update_rollover_watch(close_ts, now)
    v87_try_handoff_entry(ticker, yes_ask, no_ask, close_ts, now)

    # V7.7 paper experiment: allow a coherent BTC displacement to enter during
    # the old hard observation window. Normal Core rules remain unchanged.
    maybe_early_impulse_core(ticker, yes_ask, no_ask, close_ts, now)

    # V8.6: Chop is still classified for telemetry, but old Chop Sniper is
    # observer-only; chop_mode therefore stays False and Core is not blocked.
    chop_mode = chop_sniper_try_enter(ticker, yes_ask, no_ask, close_ts)

    for side, price in (("YES", yes_ask), ("NO", no_ask)):
        if price is None:
            continue

        record_price(side, price, now)
        process_minute_price(side, price, now)

        signal = evaluate_strategy(side, price, now)
        if signal is not None:
            if chop_mode:
                signal["btc_price"] = btc_last_price
                signal["btc_ema_9"] = btc_ema_9
                signal["btc_ema_30"] = btc_ema_30
                enrich_signal_context(side, signal, close_ts)
                ctx = chop_context(close_ts, now)
                signal["strategy"] = "CORE_BLOCKED_BY_CHOP"
                signal["market_regime"] = "CHOP"
                signal["chop_low"] = ctx["low"]
                signal["chop_high"] = ctx["high"]
                signal["chop_width"] = ctx["width"]
                signal["chop_edge"] = ctx["edge"]
                signal["early_exception_reasons"] = "BLOCK_CORE_CHOP_SNIPER_ACTIVE"
                log_signal(ticker, side, signal)
            else:
                signal["strategy"] = "CORE"
                signal["market_regime"] = "CORE"
                print_signal(ticker, side, signal, btc_start, close_ts, yes_ask, no_ask)


# ============================================================
# WEBSOCKET + REST FALLBACK
# ============================================================

async def listen_to_market(market):
    global active_target
    ticker = market["ticker"]
    close_ts = iso_to_timestamp(market.get("close_time"))
    active_target = market.get("yes_sub_title", "") or ""
    last_yes_ask, last_no_ask = extract_top_of_book(market)

    # 90/75/60-second history must start fresh for each new contract.
    reset_contract_history()
    reset_kalshi_observer_book()
    btc_start_price = btc_last_price
    reversal_flags = set()

    private_key = load_private_key()
    timestamp, signature = create_signature(private_key)

    headers = {
        "KALSHI-ACCESS-KEY": API_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
    }

    print()
    print("=" * 60)
    print("CURRENT BTC 15-MINUTE CONTRACT")
    print("=" * 60)
    print("Ticker:", ticker)
    print("Title:", market.get("title", ""))
    print("Target:", active_target)
    print(
        "YES:",
        market.get("yes_bid_dollars"),
        "/",
        market.get("yes_ask_dollars"),
    )
    print(
        "NO:",
        market.get("no_bid_dollars"),
        "/",
        market.get("no_ask_dollars"),
    )
    print("Closes:", market.get("close_time", ""))
    if btc_start_price is not None:
        print(f"BTC start: ${btc_start_price:,.2f}")
    else:
        print("BTC start: waiting for BTC/USD feed")
    print("=" * 60)
    print()

    ws_messages = 0
    ticker_messages = 0
    orderbook_messages = 0
    rest_polls = 0
    usable_updates = 0

    last_rest_poll = 0.0
    last_status = time.monotonic()

    async with websockets.connect(
        WS_URL,
        additional_headers=headers,
        ping_interval=10,
        ping_timeout=None,
        close_timeout=10,
    ) as ws:
        print("CONNECTED TO KALSHI")
        print()

        subscribe = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": [
                    "ticker",
                    "orderbook_delta",
                    "trade",
                ],
                "market_tickers": [ticker],
            },
        }

        await ws.send(json.dumps(subscribe))

        print("Subscribed to ticker + orderbook + public trades.")
        print("Tracking BOTH YES and NO sides.")
        print("REST top-of-book fallback: 1 update/second.")
        print("90-second Kalshi strategy history starts fresh on this contract; BTC structural ancestry remains continuous.")
        print("EMA history remains continuous and informational only.")
        print("V8.7 LONG RUN: $10 standard / $15 A+ paper sizing; Edge/Chop runs as SHADOW observer only.")
        print("V8.7 handoff: late EMA9 rollover can carry across the boundary for a selective first-minute A+ entry.")
        print("V8.5 keeps first-minute access when inherited BTC ancestry is strong; parent-thesis veto blocks weak countertrend fades.")
        print("V7.7 trading rules unchanged. Extension engine measures Price-EMA9-EMA30 double stretch and simulates resting counter-side limits.")
        print("Edge limit events are OBSERVER-ONLY: PLACED / FILLED / NO_FILL / CANCELLED; no Edge orders enter paper P&L.")
        print()

        while True:
            # Fast handoff at the actual 15-minute contract close.
            if close_ts is not None and time.time() >= close_ts:
                print()
                print("⏱️ Contract closed — switching immediately.")
                paper_close_contract(ticker, last_yes_ask, last_no_ask)
                print_contract_summary(ticker)
                pending_settlements.add(ticker)
                return

            data = None

            try:
                message = await asyncio.wait_for(
                    ws.recv(),
                    timeout=WS_RECV_TIMEOUT,
                )
                data = json.loads(message)
                ws_messages += 1

                msg_type = data.get("type", "")
                if msg_type == "ticker":
                    ticker_messages += 1
                elif msg_type in ("orderbook_delta", "orderbook_snapshot"):
                    orderbook_messages += 1
                    process_orderbook_message(data)
                elif msg_type == "trade":
                    process_kalshi_trade_message(data)

                msg = data.get("msg", {})
                if isinstance(msg, dict):
                    yes_ask, no_ask = extract_top_of_book(msg)

                    if yes_ask is not None or no_ask is not None:
                        if yes_ask is not None:
                            last_yes_ask = yes_ask
                        if no_ask is not None:
                            last_no_ask = no_ask
                        usable_updates += 1
                        process_top_of_book(
                            ticker,
                            yes_ask,
                            no_ask,
                            "WS",
                            btc_start_price,
                            close_ts,
                        )

            except asyncio.TimeoutError:
                pass

            except websockets.exceptions.ConnectionClosed as e:
                print()
                print()
                print("⚠️ WebSocket disconnected.")
                print("Code:", e.code)
                return

            except Exception as e:
                print()
                print("⚠️ WebSocket error:", e)
                traceback.print_exc()

            # Reliable 1-second top-of-book sampling. This prevents the
            # strategy from freezing when the websocket has no usable ASK.
            now_mono = time.monotonic()
            if now_mono - last_rest_poll >= REST_POLL_SECONDS:
                last_rest_poll = now_mono

                try:
                    snapshot = await asyncio.to_thread(
                        get_market_snapshot,
                        ticker,
                    )
                    rest_polls += 1

                    yes_ask, no_ask = extract_top_of_book(snapshot)

                    refreshed_target = snapshot.get("yes_sub_title", "") or ""
                    if refreshed_target and refreshed_target != active_target:
                        old_target = active_target or "TBD"
                        active_target = refreshed_target
                        print()
                        print(f"🎯 TARGET UPDATED | {old_target} -> {active_target}")

                    if yes_ask is not None or no_ask is not None:
                        if yes_ask is not None:
                            last_yes_ask = yes_ask
                        if no_ask is not None:
                            last_no_ask = no_ask
                        usable_updates += 1
                        process_top_of_book(
                            ticker,
                            yes_ask,
                            no_ask,
                            "REST",
                            btc_start_price,
                            close_ts,
                        )

                except Exception as e:
                    print()
                    print("⚠️ REST snapshot error:", e)
                    traceback.print_exc()

            # Late-contract BTC displacement experiment.
            if (
                close_ts is not None
                and btc_start_price is not None
                and btc_last_price is not None
            ):
                seconds_left = max(0.0, close_ts - time.time())
                btc_move = btc_last_price - btc_start_price
                if seconds_left <= 300:
                    for threshold in REVERSAL_THRESHOLDS:
                        key = threshold
                        if abs(btc_move) >= threshold and key not in reversal_flags:
                            reversal_flags.add(key)
                            log_reversal_watch(
                                ticker, btc_start_price, btc_last_price,
                                btc_move, threshold, seconds_left,
                            )
                            next_side = "NO" if btc_move > 0 else "YES"
                            print()
                            print(
                                f"⚡ REVERSAL WATCH | BTC move={btc_move:+.2f} "
                                f"| {seconds_left:.0f}s left | next side={next_side}"
                            )

            # Heartbeat so silence never looks like a frozen bot again.
            if now_mono - last_status >= STATUS_SECONDS:
                last_status = now_mono

                yes_now = (
                    price_history["YES"][-1][1]
                    if price_history["YES"]
                    else None
                )
                no_now = (
                    price_history["NO"][-1][1]
                    if price_history["NO"]
                    else None
                )

                yes_text = f"{yes_now:.3f}" if yes_now is not None else "---"
                no_text = f"{no_now:.3f}" if no_now is not None else "---"

                btc_text = f"${btc_last_price:,.2f}" if btc_last_price is not None else "---"
                btc_ema_text = (
                    f"{btc_ema_9:,.0f}/{btc_ema_30:,.0f}"
                    if btc_ema_9 is not None and btc_ema_30 is not None
                    else "warming"
                )

                phase_now, sec_left_now, elapsed_now = contract_phase(close_ts)
                live_line = (
                    f"LIVE | {phase_now} | YES={yes_text} | NO={no_text} "
                    f"| BTC={btc_text} | BTC EMA9/30={btc_ema_text} "
                    f"| WS={ws_messages} | REST={rest_polls} "
                    f"| usable={usable_updates} | BTCticks={btc_updates} "
                    f"| PaperPnL=${paper_realized_pnl:+.2f}"
                )
                copilot_line = copilot_snapshot(close_ts, yes_now, no_now)
                print("\r" + live_line + " " * 8)
                print(copilot_line + " " * 8, end="\033[F", flush=True)


# ============================================================
# MAIN LOOP WITH FAST CONTRACT HANDOFF
# ============================================================

async def main():
    initialize_log()

    print("Tachys V9.2.5 Long Run — V9.2.4 trading + observer-only 5m/30m regime context.")
    print("Bootstrapping BTC 1-minute EMA history from Coinbase...")
    await asyncio.to_thread(bootstrap_btc_history)

    btc_task = asyncio.create_task(btc_price_feed())
    settlement_task = asyncio.create_task(settlement_watcher())
    mtf_task = asyncio.create_task(multitimeframe_observer())

    try:
        while True:
            try:
                print()
                print("Searching for current KXBTC15M market...")

                market = await asyncio.to_thread(get_current_market)

                if market is None:
                    print("No active future KXBTC15M market found.")
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue

                await listen_to_market(market)
                await asyncio.sleep(0.25)

            except Exception as e:
                print()
                print()
                print("⚠️ MAIN LOOP ERROR:", e)
                print(f"Reconnecting in {RECONNECT_DELAY} second(s)...")
                await asyncio.sleep(RECONNECT_DELAY)

    finally:
        btc_task.cancel()
        settlement_task.cancel()
        mtf_task.cancel()
        await asyncio.gather(
            btc_task, settlement_task, mtf_task, return_exceptions=True
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
