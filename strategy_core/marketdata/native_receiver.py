"""R22 dedicated Kalshi native WebSocket receiver.

The network thread owns the socket and continuously drains Kalshi independently
from Commander / journal / dashboard work.  Order-book traffic is folded inside
the receiver into the newest sequence-valid immutable book state.  The trading
thread consumes that current state when it is ready; it never has to replay a
multi-second queue of historical deltas just because Commander was busy.

A sequence gap, malformed book or explicit reconnect retires the receiver-side
book and requires a fresh authoritative snapshot.  Advisory ticker/trade traffic
may be coalesced/dropped when the consumer is busy, but that telemetry backlog
never invalidates a current sequence-valid economic book.
"""
from __future__ import annotations

from collections import deque
from decimal import Decimal, InvalidOperation
import json
import queue
import threading
import time
from typing import Any, Dict, Optional



RECEIVER_REVISION = 'TOOL-RACK-NATIVE-RECEIVER-1'
DEFAULT_MAX_BACKLOG_SECONDS = 2.0  # telemetry retention diagnostic, not book authority
DEFAULT_MAX_MESSAGES = 4096
DEFAULT_RECV_POLL_SECONDS = 0.05
DEFAULT_RECONNECT_DELAY = 0.10
D = Decimal


class NativeReceiverEmpty(Exception):
    pass


class _ReconnectNow(Exception):
    pass


def _number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('missing number')
    try:
        out = D(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('invalid number') from None
    if not out.is_finite():
        raise ValueError('nonfinite number')
    return out


def _price(value, *, cents=False):
    out = _number(value) / (100 if cents else 1)
    if not D(0) <= out <= D(1):
        raise ValueError('price outside binary range')
    return out


def _integer(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError('invalid sid/seq')
    return value


def _levels(msg, side):
    key = next((k for k in (side + '_dollars_fp', side + '_dollars', side) if k in msg), None)
    if key is None or msg[key] is None:
        return {}
    rows = msg[key]
    if not isinstance(rows, list):
        raise ValueError('malformed depth array')
    out = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValueError('malformed depth level')
        p, q = _price(row[0], cents=(key == side)), _number(row[1])
        if q < 0 or p in out:
            raise ValueError('negative or duplicate depth')
        if q:
            out[p] = q
    return out


def _source_timestamp_ms(data, msg):
    stamp = msg.get('ts_ms')
    if isinstance(stamp, int) and stamp >= 1_600_000_000_000:
        return stamp
    stamp = data.get('sending_ts_ms')
    if isinstance(stamp, int) and stamp >= 1_600_000_000_000:
        return stamp
    raw = msg.get('ts')
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 1_600_000_000:
        return int(float(raw) * 1000.0)
    return None


class NativeWsReceiver:
    """Continuously drain one Kalshi WS subscription in a dedicated thread."""

    def __init__(self, url: str, headers: Dict[str, str], subscribe: Dict[str, Any], *,
                 ticker: str,
                 max_backlog_seconds: float = DEFAULT_MAX_BACKLOG_SECONDS,
                 max_messages: int = DEFAULT_MAX_MESSAGES,
                 recv_poll_seconds: float = DEFAULT_RECV_POLL_SECONDS,
                 reconnect_delay: float = DEFAULT_RECONNECT_DELAY,
                 connect_factory=None, headers_factory=None):
        self.url = str(url)
        self.headers = dict(headers)
        self.headers_factory = headers_factory
        self.subscribe = dict(subscribe)
        self.ticker = str(ticker)
        self.max_backlog_seconds = float(max_backlog_seconds)
        self.max_messages = int(max_messages)
        self.recv_poll_seconds = float(recv_poll_seconds)
        self.reconnect_delay = float(reconnect_delay)
        if connect_factory is None:
            from websockets.sync.client import connect as connect_factory
        self._connect = connect_factory

        self._cv = threading.Condition()
        self._items = deque()  # receiver events + non-book telemetry only
        self._control = queue.SimpleQueue()
        self._stop = threading.Event()
        self._connected = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._generation = 0
        self._reconnects = 0
        self._backlog_drops = 0  # retained compatibility; economic book is never age-dropped
        self._telemetry_drops = 0
        self._messages_received = 0
        self._book_messages_received = 0
        self._last_error = None

        self._book_sid = None
        self._book_seq = None
        self._book_ok = False
        self._book = {'yes': {}, 'no': {}}
        self._book_received_wall = 0.0
        self._book_received_mono = 0.0
        self._book_source_ms = None
        self._book_version = 0
        self._book_published_version = 0
        self._book_invalidations = 0
        self._deltas_before_snapshot = 0

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run,
                                        name='ToolRack-Kalshi-Native-Receiver',
                                        daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 3.0):
        self._stop.set()
        self._control.put({'cmd': 'stop'})
        with self._cv:
            self._cv.notify_all()
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=max(0.0, float(timeout)))

    def wait_connected(self, timeout: float = 10.0) -> bool:
        return self._connected.wait(timeout=max(0.0, float(timeout)))

    def send_json(self, payload: Dict[str, Any]):
        if isinstance(payload, dict):
            self._control.put({'cmd': 'send', 'payload': dict(payload)})

    def _reset_fold_locked(self):
        self._book_sid = None
        self._book_seq = None
        self._book_ok = False
        self._book = {'yes': {}, 'no': {}}
        self._book_received_wall = 0.0
        self._book_received_mono = 0.0
        self._book_source_ms = None
        self._book_version += 1
        self._book_published_version = self._book_version

    def force_reconnect(self, reason: str):
        reason = str(reason or 'FORCED_RECONNECT')
        with self._cv:
            dropped = sum(1 for x in self._items if x.get('kind') == 'message')
            self._items.clear()
            self._reset_fold_locked()
            self._items.append(self._event_item('FORCED_RECONNECT', reason=reason,
                                                dropped_messages=dropped))
            self._cv.notify_all()
        self._control.put({'cmd': 'reconnect', 'reason': reason})

    def _book_item_locked(self):
        if not self._book_ok or self._book_version <= self._book_published_version:
            return None
        msg = {
            'market_ticker': self.ticker,
            'yes_dollars_fp': [[str(p), str(q)] for p, q in sorted(self._book['yes'].items(), reverse=True)],
            'no_dollars_fp': [[str(p), str(q)] for p, q in sorted(self._book['no'].items(), reverse=True)],
        }
        data = {
            'type': 'orderbook_snapshot',
            'sid': self._book_sid,
            'seq': self._book_seq,
            'msg': msg,
        }
        if self._book_source_ms is not None:
            data['sending_ts_ms'] = int(self._book_source_ms)
        return {
            'kind': 'message',
            'generation': self._generation,
            'received_wall': self._book_received_wall,
            'received_mono': self._book_received_mono,
            'data': data,
            'folded_current_book': True,
            'folded_book_version': self._book_version,
        }

    def drain_nowait(self, max_items: int = 8192):
        """Return current economic book plus bounded advisory messages/events.

        Thousands of native deltas can arrive while Commander is busy, but only
        one newest sequence-valid full book is materialized for the consumer.
        """
        limit = max(1, int(max_items))
        with self._cv:
            out = []
            while self._items and len(out) < max(0, limit - 1):
                out.append(self._items.popleft())
            book_item = self._book_item_locked()
            if book_item is not None and len(out) < limit:
                out.append(book_item)
                self._book_published_version = self._book_version
            # Preserve receipt order between receiver events/telemetry and the
            # synthesized current-book snapshot.
            out.sort(key=lambda x: float(x.get('received_mono') or 0.0))
            return out

    def get_nowait(self):
        batch = self.drain_nowait(1)
        return batch[0] if batch else None

    def get(self, timeout: float = 0.0):
        deadline = time.monotonic() + max(0.0, float(timeout))
        with self._cv:
            while not self._items and not (
                    self._book_ok and self._book_version > self._book_published_version):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise NativeReceiverEmpty()
                self._cv.wait(remaining)
        batch = self.drain_nowait(1)
        if not batch:
            raise NativeReceiverEmpty()
        return batch[0]

    def snapshot(self):
        with self._cv:
            now = time.monotonic()
            telemetry = [x for x in self._items if x.get('kind') == 'message']
            telemetry_age = (max(0.0, now - float(telemetry[0]['received_mono']))
                             if telemetry else 0.0)
            book_pending = bool(self._book_ok and self._book_version > self._book_published_version)
            book_age = (max(0.0, now - self._book_received_mono)
                        if self._book_ok and self._book_received_mono else 0.0)
            return {
                'revision': RECEIVER_REVISION,
                'connected': self._connected.is_set(),
                'generation': self._generation,
                'pending_messages': len(telemetry) + (1 if book_pending else 0),
                'oldest_pending_age_sec': round(book_age if book_pending else 0.0, 6),
                'telemetry_pending_messages': len(telemetry),
                'telemetry_oldest_pending_age_sec': round(telemetry_age, 6),
                'current_book_valid': self._book_ok,
                'current_book_sid': self._book_sid,
                'current_book_seq': self._book_seq,
                'current_book_receive_age_sec': round(book_age, 6),
                'book_updates_folded': self._book_messages_received,
                'book_invalidations': self._book_invalidations,
                'deltas_before_snapshot': self._deltas_before_snapshot,
                'messages_received': self._messages_received,
                'reconnects': self._reconnects,
                'backlog_drops': self._backlog_drops,
                'telemetry_drops': self._telemetry_drops,
                'last_error': self._last_error,
            }

    def _event_item(self, event: str, **fields):
        return {
            'kind': 'receiver',
            'event': str(event),
            'ticker': self.ticker,
            'received_wall': time.time(),
            'received_mono': time.monotonic(),
            'generation': self._generation,
            **fields,
        }

    def _push_event(self, event: str, **fields):
        with self._cv:
            self._items.append(self._event_item(event, **fields))
            self._cv.notify_all()

    def _invalidate_fold_locked(self, reason, *, sid=None, seq=None):
        self._book_ok = False
        self._book = {'yes': {}, 'no': {}}
        self._book_sid = None
        self._book_seq = None
        self._book_source_ms = None
        self._book_received_wall = 0.0
        self._book_received_mono = 0.0
        self._book_version += 1
        self._book_published_version = self._book_version
        self._book_invalidations += 1
        self._items.append(self._event_item('BOOK_FOLD_INVALID', reason=str(reason), sid=sid, seq=seq))

    def _fold_orderbook_locked(self, data, wall, mono):
        kind = data.get('type')
        msg = data.get('msg') or {}
        if not isinstance(msg, dict) or msg.get('market_ticker') != self.ticker:
            return 'ignored'
        sid, seq = _integer(data.get('sid')), _integer(data.get('seq'))
        source_ms = _source_timestamp_ms(data, msg)
        if kind == 'orderbook_snapshot':
            fresh = {side: _levels(msg, side) for side in ('yes', 'no')}
            if self._book_ok:
                if sid != self._book_sid or seq < self._book_seq:
                    self._invalidate_fold_locked('BACKWARDS_OR_FOREIGN_SNAPSHOT', sid=sid, seq=seq)
                    return 'invalid'
                if seq == self._book_seq:
                    if fresh == self._book:
                        return 'duplicate'
                    self._invalidate_fold_locked('SAME_SEQUENCE_CONTRADICTORY_SNAPSHOT', sid=sid, seq=seq)
                    return 'invalid'
            self._book = fresh
            self._book_sid, self._book_seq = sid, seq
            self._book_ok = True
        elif kind == 'orderbook_delta':
            if not self._book_ok:
                self._deltas_before_snapshot += 1
                return 'await_snapshot'
            if sid != self._book_sid:
                self._invalidate_fold_locked('WRONG_SID_DELTA', sid=sid, seq=seq)
                return 'invalid'
            if seq == self._book_seq:
                return 'duplicate'
            if seq != self._book_seq + 1:
                self._invalidate_fold_locked('SEQUENCE_GAP_OR_REORDER', sid=sid, seq=seq)
                return 'invalid'
            side = msg.get('side')
            if side not in ('yes', 'no'):
                self._invalidate_fold_locked('INVALID_BOOK_SIDE', sid=sid, seq=seq)
                return 'invalid'
            p = (_price(msg['price_dollars']) if 'price_dollars' in msg
                 else _price(msg.get('price'), cents=True))
            delta = _number(msg.get('delta_fp', msg.get('delta')))
            quantity = self._book[side].get(p, D(0)) + delta
            if quantity < 0:
                self._invalidate_fold_locked('NEGATIVE_RESULTING_DEPTH', sid=sid, seq=seq)
                return 'invalid'
            if quantity == 0:
                self._book[side].pop(p, None)
            else:
                self._book[side][p] = quantity
            self._book_seq = seq
        else:
            return 'ignored'
        if (self._book['yes'] and self._book['no'] and
                max(self._book['yes']) + max(self._book['no']) > D(1)):
            self._invalidate_fold_locked('CROSSED_BOOK', sid=sid, seq=seq)
            return 'invalid'
        self._book_received_wall = wall
        self._book_received_mono = mono
        self._book_source_ms = source_ms
        self._book_messages_received += 1
        self._book_version += 1
        return 'accepted'

    def _trim_telemetry_locked(self, mono):
        # Advisory trade/ticker backlog must never make the economic book stale.
        while True:
            idx = next((i for i, x in enumerate(self._items) if x.get('kind') == 'message'), None)
            if idx is None:
                return
            item = self._items[idx]
            pending = sum(1 for x in self._items if x.get('kind') == 'message')
            age = max(0.0, mono - float(item.get('received_mono') or mono))
            if pending < self.max_messages and age <= self.max_backlog_seconds:
                return
            del self._items[idx]
            self._telemetry_drops += 1

    def _enqueue_message(self, data, wall: float, mono: float):
        reconnect = False
        with self._cv:
            self._messages_received += 1
            kind = data.get('type') if isinstance(data, dict) else None
            if kind in ('orderbook_snapshot', 'orderbook_delta'):
                try:
                    result = self._fold_orderbook_locked(data, wall, mono)
                except (ValueError, TypeError, KeyError, InvalidOperation):
                    self._invalidate_fold_locked('MALFORMED_BOOK_MESSAGE')
                    result = 'invalid'
                reconnect = result == 'invalid'
            else:
                # Keep only the newest pending ticker. Public trades remain
                # bounded advisory telemetry and may be dropped under consumer
                # pressure without touching book authority.
                if kind == 'ticker':
                    self._items = deque(x for x in self._items if not (
                        x.get('kind') == 'message' and
                        isinstance(x.get('data'), dict) and x['data'].get('type') == 'ticker'))
                self._items.append({
                    'kind': 'message',
                    'generation': self._generation,
                    'received_wall': wall,
                    'received_mono': mono,
                    'data': data,
                })
                self._trim_telemetry_locked(mono)
            self._cv.notify_all()
        if reconnect:
            raise _ReconnectNow()

    def _drain_control(self, ws):
        while True:
            try:
                cmd = self._control.get_nowait()
            except queue.Empty:
                return
            kind = cmd.get('cmd')
            if kind == 'stop':
                raise _ReconnectNow()
            if kind == 'reconnect':
                raise _ReconnectNow()
            if kind == 'send':
                payload = cmd.get('payload')
                if isinstance(payload, dict):
                    ws.send(json.dumps(payload))

    def _run(self):
        while not self._stop.is_set():
            try:
                connect_headers = (self.headers_factory() if callable(self.headers_factory)
                                   else dict(self.headers))
                with self._connect(
                    self.url,
                    additional_headers=connect_headers,
                    ping_interval=10,
                    ping_timeout=None,
                    open_timeout=5,
                    close_timeout=2,
                    max_size=1_000_000,
                    max_queue=512,
                ) as ws:
                    with self._cv:
                        self._generation += 1
                        if self._generation > 1:
                            self._reconnects += 1
                        self._reset_fold_locked()
                    ws.send(json.dumps(self.subscribe))
                    self._connected.set()
                    self._push_event('CONNECTED', reconnect=bool(self._generation > 1))
                    while not self._stop.is_set():
                        self._drain_control(ws)
                        try:
                            message = ws.recv(timeout=self.recv_poll_seconds)
                        except TimeoutError:
                            continue
                        wall, mono = time.time(), time.monotonic()
                        data = json.loads(message)
                        self._enqueue_message(data, wall, mono)
            except _ReconnectNow:
                self._connected.clear()
                if self._stop.is_set():
                    break
                self._stop.wait(self.reconnect_delay)
                continue
            except Exception as exc:
                self._connected.clear()
                self._last_error = type(exc).__name__
                self._push_event('DISCONNECTED', error=self._last_error)
                if self._stop.is_set():
                    break
                self._stop.wait(self.reconnect_delay)
        self._connected.clear()
        self._push_event('STOPPED')
