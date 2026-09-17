# Tachys V8.3 MID RUN - persistent structural thesis + rejection strength + time-aware management
import os
import time
import base64
import asyncio
import json
import csv
import re
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
LOG_FILE = "tachys_signals_v8_3.csv"
RESULT_LOG_FILE = "tachys_contract_results.csv"
REVERSAL_LOG_FILE = "tachys_reversal_watch.csv"
PAPER_LOG_FILE = "tachys_paper_trades_v8_3.csv"

# Paper money-management experiment. Fixed maximum stake per entry.
PAPER_STAKE = 5.00
A_PLUS_PAPER_STAKE = 10.00

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

# V8.3 thesis continuity / time-aware patience.
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


# Early Impulse Core: small paper-only experiment. This may bypass the hard
# 2-minute observation gate after 30 seconds when BTC displacement is unusually
# coherent. It does NOT use A+ sizing.
EARLY_IMPULSE_MIN_ELAPSED = 30
EARLY_IMPULSE_MAX_ELAPSED = 120
EARLY_IMPULSE_STAKE = 5.00
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
REVERSAL_THRESHOLDS = (200, 250, 300)

# V7.5 OBSERVER LAYER -------------------------------------------------------
# Trading rules remain V7.4. These measurements are intentionally observational
# so the short shakedown can tell us whether Tachys describes the chart correctly
# before they are allowed to influence paper orders.
STRUCTURE_LOG_FILE = "tachys_structure_v8_3.csv"
LAG_LOG_FILE = "tachys_btc_kalshi_lag_v8_3.csv"
EXTENSION_LOG_FILE = "tachys_edge_extension_v8_3.csv"
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
    """V8.3 live extension metrics wrapper.

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

LAG_FIELDS = [
    "timestamp", "ticker", "direction", "btc_start", "yes_start", "no_start",
    "btc_change3_at_trigger", "btc_change6_at_trigger", "btc_change9_at_trigger",
    "btc_change30_at_trigger", "btc_eff30_at_trigger",
    "btc_3s", "yes_3s", "no_3s", "btc_6s", "yes_6s", "no_6s",
    "btc_9s", "yes_9s", "no_9s",
]


def initialize_log():
    files_and_headers = {
        STRUCTURE_LOG_FILE: STRUCTURE_FIELDS,
        LAG_LOG_FILE: LAG_FIELDS,
        EXTENSION_LOG_FILE: [
            "timestamp", "event_id", "ticker", "extension_direction", "counter_side",
            "arm_score", "arm_exhaustion", "start_ask", "limit_price", "yes_ask", "no_ask",
            "status", "reason", "age_seconds", "btc_price", "price_ema9_distance",
            "ema9_ema30_distance", "norm_price_ema9", "norm_ema_gap",
            "current_extension_score", "current_exhaustion_score",
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
            "strategy", "market_regime", "chop_low", "chop_high", "chop_width", "chop_edge",
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
            "cumulative_pnl"
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
            paper_realized_pnl,
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


def chop_sniper_try_enter(ticker, yes_ask, no_ask, close_ts=None):
    """
    Edge-only paper entry:
      lower edge + short-term rejection upward -> YES
      upper edge + short-term rejection downward -> NO
    No middle-of-box entries and only one sniper position at a time.
    """
    global paper_trade_counter, chop_sniper_last_state, chop_sniper_last_box

    ctx = chop_context(close_ts)
    chop_sniper_last_state = "CHOP_SNIPER" if ctx["is_chop"] else "CORE"
    chop_sniper_last_box = (ctx["low"], ctx["high"])

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

def paper_enter(ticker, side, ask, signal):
    global paper_trade_counter

    if paper_positions[side] is not None:
        return
    if time.time() - last_paper_exit_time[side] < PAPER_REENTRY_COOLDOWN:
        return
    if ask <= 0:
        return

    elapsed = signal.get("contract_elapsed_seconds")
    is_early_trade = (
        elapsed is not None
        and OBSERVATION_SECONDS <= float(elapsed) < EARLY_PROFIT_WINDOW_SECONDS
    )
    stake_cap = (
        A_PLUS_PAPER_STAKE
        if signal.get("signal_grade") == "A+"
        else PAPER_STAKE
    )
    qty = int(stake_cap // ask)
    if qty < 1:
        return

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
    }
    paper_positions[side] = position
    contract_trade_ids.setdefault(ticker, []).append(position["trade_id"])
    log_paper_event("ENTRY", position)
    grade = position.get("signal_grade") or position.get("setup_grade")
    print(f"💵 PAPER ${stake_cap:.0f} ENTRY | #{paper_trade_counter} {side} {grade} | {qty} contracts @ {ask:.3f} | cost=${cost:.2f}")


def record_contract_trade(position, exit_bid, pnl, reason):
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

    # V8.3: continuous cross-contract ancestry can anticipate the next arc or
    # continuation at EMA30 before the generic arc label catches up.
    anc = ema9_ancestry_state(now)
    if anc.get("anticipated") == wanted and anc.get("setup") in ("PRE_CROSS_UP", "PRE_CROSS_DOWN", "EMA30_REJECTION_UP", "EMA30_REJECTION_DOWN"):
        return True, anc.get("setup"), arc

    # V8.3: EMA9-to-EMA30 rejection/failed approach may lead price.  Price can
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
        # V8.3: early in the contract we are intentionally more flexible.  A
        # correct anticipated arc can wobble before it develops.
        if seconds_left is not None and seconds_left >= EARLY_FLEX_SECONDS_LEFT:
            required_break_seconds = EARLY_ARC_BREAK_CONFIRM_SECONDS
        elif seconds_left is not None and seconds_left >= MID_FLEX_SECONDS_LEFT:
            required_break_seconds = MID_ARC_BREAK_CONFIRM_SECONDS
        else:
            required_break_seconds = NORMAL_ARC_BREAK_CONFIRM_SECONDS
        structural_failed, structural_thesis = v83_structural_failure(side)
        same_side_valid = structural_thesis.get("state") in ("VALID", "STRONG")
        arc_break_confirmed = (
            arc_relation == "BROKEN"
            and broken_for >= required_break_seconds
            and not same_side_valid
        )
        proven_floor = max(PROVEN_MFE_MIN_FLOOR, peak_roi - PROVEN_MFE_GIVEBACK)

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

        # V8.3: THESIS_INVALIDATED is not allowed to kill an intact EMA9 arc.
        # Existing thesis score can raise concern, but a normal Core exit now
        # needs the EMA9 arc itself to be BROKEN (except emergency/expiry rules).
        if fast_fail:
            reason = "ANTICIPATION_FAST_FAIL"
        elif peak_roi >= PROVEN_MFE_PROTECT and roi <= proven_floor and arc_break_confirmed and not strong_cushion_lock:
            reason = "EMA9_PROTECT_PROVEN"
        elif EMA9_ARC_EXIT_MANAGEMENT and arc_break_confirmed and roi <= THESIS_INVALIDATION_MAX_ROI and peak_roi < PROVEN_MFE_PROTECT and not strong_cushion_lock:
            reason = "EMA9_ARC_BROKEN"
        elif (
            sideways_like
            and seconds_left is not None
            and roi >= sideways_tp
            and not runner_ok
        ):
            reason = sideways_tp_reason
        elif (
            not sideways_like
            and seconds_left is not None
            and seconds_left <= TP_MID_SECONDS_LEFT
            and roi >= LATE_PROFIT_TP_ROI
            and not runner_ok
        ):
            reason = "CORE_LATE_TP_22_5"
        elif position.get("early_trade") and roi >= EARLY_TAKE_PROFIT_ROI:
            reason = "EARLY_TAKE_PROFIT_50"
        elif peak_roi >= TRAIL_ACTIVATE_ROI and roi <= peak_roi - TRAIL_GIVEBACK_ROI:
            reason = "TRAIL_20PTS_AFTER_40"
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


def print_signal(ticker, side, signal, btc_start=None, close_ts=None):
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
        # V7: hard 2-minute observation window. We still log qualifying
        # signals for later analysis, but never open a paper position here.
        signal["early_exception"] = False
        signal["early_exception_reasons"] = "HARD_2MIN_OBSERVE"
        signal["signal_grade"] = "OBSERVE_ONLY"
        log_signal(ticker, side, signal)
        return

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

    # V8.3: ordinary Core entries must fit the live EMA9 arc. Blocked signals
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
            print(f"⏳ V8.3 WAIT | {side} | {ctx_reason} | ask={signal['price']:.3f}")
            return
        signal["early_exception_reasons"] += ";" + ctx_reason

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
        "strategy": "EARLY_IMPULSE_CORE", "market_regime": "IMPULSE",
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


def process_top_of_book(ticker, yes_ask, no_ask, source, btc_start=None, close_ts=None):
    now = time.time()

    # V7.5 observer is independent of V7.4 trading decisions.
    maybe_start_impulse_event(ticker, yes_ask, no_ask, now)
    update_impulse_lag_events(yes_ask, no_ask, now)
    maybe_log_structure(ticker, close_ts, yes_ask, no_ask, now)

    paper_manage.current_close_ts = close_ts
    paper_manage(ticker, yes_ask, no_ask)

    # V7.7 paper experiment: allow a coherent BTC displacement to enter during
    # the old hard observation window. Normal Core rules remain unchanged.
    maybe_early_impulse_core(ticker, yes_ask, no_ask, close_ts, now)

    # V7.1 regime router: when a valid chop regime is present, CORE stops
    # opening new positions and CHOP SNIPER gets the opportunity instead.
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
                print_signal(ticker, side, signal, btc_start, close_ts)


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
        print("90-second strategy history starts fresh on this contract.")
        print("EMA history remains continuous and informational only.")
        print("V7.8: V7.7 paper trading preserved + observer-only Extension / Edge Sniper limit engine.")
        print("Normal Core waits 2 minutes; exceptional Early Impulse Core may paper-enter after 30s.")
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

    print("Bootstrapping BTC 1-minute EMA history from Coinbase...")
    await asyncio.to_thread(bootstrap_btc_history)

    btc_task = asyncio.create_task(btc_price_feed())
    settlement_task = asyncio.create_task(settlement_watcher())

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
        await asyncio.gather(
            btc_task, settlement_task, return_exceptions=True
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())
