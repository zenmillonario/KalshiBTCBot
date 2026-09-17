import os
import time
import base64
import asyncio
import json
import csv
from datetime import datetime, timezone

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
LOG_FILE = "tachys_signals_v4.csv"
RESULT_LOG_FILE = "tachys_contract_results.csv"
REVERSAL_LOG_FILE = "tachys_reversal_watch.csv"
PAPER_LOG_FILE = "tachys_paper_trades_v4.csv"

# Paper money-management experiment. Fixed maximum stake per entry.
PAPER_STAKE = 5.00
# No fixed +30% take-profit in V4. Winners can run.
PAPER_STOP_LOSS = 0.20          # -20% hard paper stop
TRAIL_ACTIVATE_ROI = 0.40       # start trailing after +40%
TRAIL_GIVEBACK_ROI = 0.20       # exit after 20 percentage-point giveback from peak
PAPER_REENTRY_COOLDOWN = 20
PROFIT_MILESTONES = (0.20, 0.30, 0.40, 0.50, 0.60, 0.75, 0.90, 1.00)

BTC_WS_URL = "wss://advanced-trade-ws.coinbase.com"
BTC_PRODUCT = "BTC-USD"
REVERSAL_THRESHOLDS = (200, 250, 300)

# EMA is still informational only. It is NOT an entry filter.
EMA_FAST_PERIOD = 9
EMA_SLOW_PERIOD = 30

SIDES = ("YES", "NO")

active_target = ""
paper_positions = {"YES": None, "NO": None}
last_paper_exit_time = {"YES": 0.0, "NO": 0.0}
paper_trade_counter = 0
paper_realized_pnl = 0.0


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


def update_btc_ema():
    global btc_ema_9
    global btc_ema_30

    if len(btc_minute_closes) >= EMA_FAST_PERIOD:
        values = [p for _, p in btc_minute_closes[-EMA_FAST_PERIOD:]]
        if btc_ema_9 is None:
            btc_ema_9 = sum(values) / len(values)
        else:
            k = 2 / (EMA_FAST_PERIOD + 1)
            btc_ema_9 = (values[-1] - btc_ema_9) * k + btc_ema_9

    if len(btc_minute_closes) >= EMA_SLOW_PERIOD:
        values = [p for _, p in btc_minute_closes[-EMA_SLOW_PERIOD:]]
        if btc_ema_30 is None:
            btc_ema_30 = sum(values) / len(values)
        else:
            k = 2 / (EMA_SLOW_PERIOD + 1)
            btc_ema_30 = (values[-1] - btc_ema_30) * k + btc_ema_30


def process_btc_price(price, now=None):
    global btc_last_price
    global btc_updates
    global btc_current_minute
    global btc_current_minute_price

    if price is None:
        return
    if now is None:
        now = time.time()

    btc_last_price = price
    btc_updates += 1
    minute_ts = int(now // 60) * 60

    if btc_current_minute is None:
        btc_current_minute = minute_ts
        btc_current_minute_price = price
        return

    if minute_ts == btc_current_minute:
        btc_current_minute_price = price
        return

    btc_minute_closes.append((btc_current_minute, btc_current_minute_price))
    if len(btc_minute_closes) > 120:
        btc_minute_closes.pop(0)

    btc_current_minute = minute_ts
    btc_current_minute_price = price
    update_btc_ema()


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
# CSV LOGGING
# ============================================================

def initialize_log():
    files_and_headers = {
        LOG_FILE: [
            "timestamp", "ticker", "side", "current_ask",
            "ask_90s", "ask_75s", "ask_60s",
            "m90_75", "m90_60",
            "kalshi_ema_9_1m", "kalshi_ema_30_1m",
            "btc_price", "btc_ema_9_1m", "btc_ema_30_1m",
            "btc_ema9_above_ema30", "btc_price_above_ema9",
            "btc_move_from_contract_start", "seconds_to_close", "setup_grade",
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
            "btc_ema_9_1m", "btc_ema_30_1m", "setup_grade", "cumulative_pnl"
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
            position.get("btc_ema_30"), position.get("setup_grade", ""), paper_realized_pnl,
        ])


def paper_enter(ticker, side, ask, signal):
    global paper_trade_counter

    if paper_positions[side] is not None:
        return
    if time.time() - last_paper_exit_time[side] < PAPER_REENTRY_COOLDOWN:
        return
    if ask <= 0:
        return

    qty = int(PAPER_STAKE // ask)
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
        "setup_grade": signal.get("setup_grade", ""), "milestones_hit": set(),
    }
    paper_positions[side] = position
    log_paper_event("ENTRY", position)
    print(f"💵 PAPER $5 ENTRY | #{paper_trade_counter} {side} {position['setup_grade']} | {qty} contracts @ {ask:.3f} | cost=${cost:.2f}")


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

        if roi <= -PAPER_STOP_LOSS:
            reason = "STOP_LOSS_20"
        elif peak_roi >= TRAIL_ACTIVATE_ROI and roi <= peak_roi - TRAIL_GIVEBACK_ROI:
            reason = "TRAIL_20PTS_AFTER_40"

        if reason:
            paper_realized_pnl += pnl
            log_paper_event("EXIT", position, bid, reason)
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

    log_signal(ticker, side, signal)
    paper_enter(ticker, side, signal["price"], signal)

    print()
    print()
    print("=" * 60)
    print(f"🔥 {side} MOMENTUM SIGNAL — {signal.get('setup_grade', '')}")
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

    print()
    print(">>> PAPER CANDIDATE — NO ORDER <<<")
    print("=" * 60)
    print()


# ============================================================
# PRICE PROCESSING
# ============================================================

def process_top_of_book(ticker, yes_ask, no_ask, source, btc_start=None, close_ts=None):
    now = time.time()
    paper_manage(ticker, yes_ask, no_ask)

    for side, price in (("YES", yes_ask), ("NO", no_ask)):
        if price is None:
            continue

        record_price(side, price, now)
        process_minute_price(side, price, now)

        signal = evaluate_strategy(side, price, now)
        if signal is not None:
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
                ],
                "market_tickers": [ticker],
            },
        }

        await ws.send(json.dumps(subscribe))

        print("Subscribed to ticker + orderbook.")
        print("Tracking BOTH YES and NO sides.")
        print("REST top-of-book fallback: 1 update/second.")
        print("90-second strategy history starts fresh on this contract.")
        print("EMA history remains continuous and informational only.")
        print()

        while True:
            # Fast handoff at the actual 15-minute contract close.
            if close_ts is not None and time.time() >= close_ts:
                print()
                print("⏱️ Contract closed — switching immediately.")
                paper_close_contract(ticker, last_yes_ask, last_no_ask)
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
                elif msg_type == "orderbook_delta":
                    orderbook_messages += 1

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

                print(
                    f"\rLIVE | YES={yes_text} | NO={no_text} "
                    f"| BTC={btc_text} | BTC EMA9/30={btc_ema_text} "
                    f"| WS={ws_messages} | REST={rest_polls} "
                    f"| usable={usable_updates} | BTCticks={btc_updates} "
                    f"| PaperPnL=${paper_realized_pnl:+.2f}",
                    end="",
                    flush=True,
                )


# ============================================================
# MAIN LOOP WITH FAST CONTRACT HANDOFF
# ============================================================

async def main():
    initialize_log()

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
