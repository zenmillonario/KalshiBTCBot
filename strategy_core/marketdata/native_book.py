"""HF2 causal quote provenance. Stdlib only; no requests, credentials or orders.

A sequence-checked book is necessary for decision authority in this experiment.
Fresh, materially conflicting ticker/REST quotes suspend authority rather than
choosing whichever quote improves P/L. Missing exchange timestamps stay unknown.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import math
from typing import Any

VERSION = '666-HF2-QUOTE-LEDGER'
BOOK_MAX_AGE = 3.0
# PID2328 restoration: exchange-message timestamps are diagnostic only for
# normal native-book authority. Earlier working Tachyos runs used the locally
# received sequence-checked book directly and did not globally pause entries
# because Kalshi's source stamp lagged the workstation clock. Keep this value
# only for diagnostics/tests; it is NOT an entry-authority freshness gate.
BOOK_MAX_EXCHANGE_LAG = 6.0
# Soft diagnostic threshold above. Hard economic authority threshold below.
# Kalshi/native source stamps historically trail this workstation by ~6-7s,
# so 6s must NOT globally pause trading. But a materially backlogged book
# (PID2796 observed ~96s) must never be executable merely because it arrived now.
BOOK_HARD_EXCHANGE_LAG = 15.0
CORROBORATOR_MAX_AGE = 2.0
MAX_EXCHANGE_LAG = 3.0
FUTURE_TOLERANCE = 2.0
MAX_REST_LATENCY = 1.5
MATERIAL_DISAGREEMENT = 0.03
DATA_HALT_SECONDS = 30.0
RESNAPSHOT_INTERVAL = 3.0
D = Decimal

# TIME1: receipt time is not the unknown generation time of a REST quote.
# An untimed REST observation cannot prove contemporaneous disagreement with a
# fresh sequence-checked native book, so it remains diagnostic/advisory only.
# Timestamped corroborators may still veto material disagreement. Sequence,
# identity, freshness, crossed-book and expiry failures remain hard refusals.
QUOTE_POLICY_REVISION = 'R22-DUAL-CLOCK-NATIVE-BOOK-LOCAL-RECEIVE-PLUS-HARD-EXCHANGE-BACKLOG-GATE'
LIVE_PAIR_MAX_EXCHANGE_SKEW = 0.250  # engineering simultaneity tolerance, not fitted P/L
LIVE_PAIR_REASON = 'VALID_LIVE_PAIR_REST_TIME_UNKNOWN'
SIDE_ACTION_REVISION = '666-HF2-SIDE1-HELD-BID'



def number(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError('Missing or boolean number')
    try:
        n = D(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Invalid number') from None
    if not n.is_finite():
        raise ValueError('Nonfinite number')
    return n


def price(value: Any, cents: bool = False) -> Decimal:
    n = number(value) / (100 if cents else 1)
    if not 0 <= n <= 1:
        raise ValueError('Price outside dollar range')
    return n


def quote_fields(msg: dict) -> tuple[float, float, float, float]:
    """YES bid, YES ask, NO bid, NO ask. Never use last trade price as a quote."""
    values = {}
    for field in ('yes_bid', 'yes_ask', 'no_bid', 'no_ask'):
        dollar = field + '_dollars'
        if dollar in msg and msg[dollar] is not None:
            values[field] = price(msg[dollar])
        elif field in msg and msg[field] is not None:
            values[field] = price(msg[field], cents=True)
    for left, right in (('yes_bid', 'no_ask'), ('yes_ask', 'no_bid')):
        if left not in values and right in values:
            values[left] = 1 - values[right]
        if right not in values and left in values:
            values[right] = 1 - values[left]
        if left in values and right in values and abs(values[left] + values[right] - 1) > D('0.0001'):
            raise ValueError('Conflicting explicit binary quotes')
    if len(values) != 4:
        raise ValueError('Incomplete quote; no stale-side merging')
    if values['yes_bid'] > values['yes_ask'] or values['no_bid'] > values['no_ask']:
        raise ValueError('Crossed market')
    return tuple(float(values[x]) for x in ('yes_bid', 'yes_ask', 'no_bid', 'no_ask'))


def exchange_time(msg: dict) -> float | None:
    if 'ts_ms' in msg and msg['ts_ms'] is not None:
        return float(number(msg['ts_ms']) / 1000)
    if 'ts' in msg and msg['ts'] is not None:
        try:
            return float(number(msg['ts']))
        except ValueError:
            pass
    for key in ('time', 'ts'):
        raw = msg.get(key)
        if isinstance(raw, str):
            try:
                dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
                if dt.tzinfo is not None:
                    return dt.timestamp()
            except ValueError:
                pass
    return None


@dataclass(frozen=True)
class Quote:
    quote_id: str
    ticker: str
    source: str
    valid: bool
    reason: str
    observed_wall: float
    observed_mono: float
    exchange_ts: float | None = None
    sid: int | None = None
    seq: int | None = None
    yes_bid: float | None = None
    yes_ask: float | None = None
    no_bid: float | None = None
    no_ask: float | None = None
    yes_levels: tuple[tuple[float, float], ...] = ()
    no_levels: tuple[tuple[float, float], ...] = ()
    close_ts: float | None = None
    generation: int = 0

    # None preserves compatibility with old synthetic Quote construction; the hub
    # always writes explicit side permissions. Missing prices remain None.
    yes_mark_valid: bool | None = None
    no_mark_valid: bool | None = None
    yes_mark_reason: str = ''
    no_mark_reason: str = ''
    market_closed: bool = False
    exchange_time_basis: str = ''

    def can_mark(self, side):
        if side not in ('YES', 'NO'):
            return False
        # An externally invalidated full quote must never inherit cached permissions.
        partial = (self.reason == 'ONE_SIDED_BOOK_NO_EXECUTABLE_BOTH_SIDE_MARK'
                   and bool(self.yes_levels) != bool(self.no_levels))
        if not self.valid and not partial:
            return False
        permission = self.yes_mark_valid if side == 'YES' else self.no_mark_valid
        return (self.valid if permission is None else permission) and self.bid(side) is not None

    def fresh_at(self, wall, mono, allow_closed=False):
        if not 0 <= mono-self.observed_mono <= BOOK_MAX_AGE:
            return False
        # Dual-clock authority: tolerate the historical ~6-7s Kalshi/workstation
        # stamp skew, but never treat a materially backlogged exchange book as
        # current solely because its local receipt is recent. Missing source time
        # remains Unknown rather than fabricated.
        if self.exchange_ts is not None and wall-self.exchange_ts > BOOK_HARD_EXCHANGE_LAG:
            return False
        return allow_closed or (not self.market_closed and (self.close_ts is None or wall < self.close_ts))

    def can_sell(self, side):
        return self.can_mark(side) and not self.market_closed

    def can_buy(self, side):
        # SIDE1 deliberately grants NO one-sided entry authority.
        return self.valid and not self.market_closed and side in ('YES', 'NO') and self.ask(side) is not None

    def mark_reason(self, side):
        if side not in ('YES', 'NO'):
            return 'INVALID_SIDE'
        return (self.yes_mark_reason if side == 'YES' else self.no_mark_reason) or self.reason

    def bid(self, side):
        return self.yes_bid if side == 'YES' else self.no_bid if side == 'NO' else None

    def ask(self, side):
        return self.yes_ask if side == 'YES' else self.no_ask if side == 'NO' else None

    def row(self, now_wall: float, now_mono: float) -> dict:
        fresh=self.fresh_at(now_wall,now_mono)
        receive_age=now_mono-self.observed_mono
        exchange_age=None if self.exchange_ts is None else now_wall-self.exchange_ts
        if not 0 <= receive_age <= BOOK_MAX_AGE:
            freshness_reason='BOOK_RECEIVE_STALE'
        elif exchange_age is not None and exchange_age > BOOK_HARD_EXCHANGE_LAG:
            freshness_reason='BOOK_EXCHANGE_STALE'
        else:
            freshness_reason='QUOTE_NOT_FRESH_AT_PUBLICATION'
        return {
            'quote_id': self.quote_id, 'ticker': self.ticker, 'source': self.source,
            'valid': bool(self.valid and fresh), 'reason': self.reason if fresh else freshness_reason, 'observed_wall': self.observed_wall,
            'receive_age_sec': max(0.0, receive_age),
            'exchange_ts': self.exchange_ts,
            'exchange_age_sec': exchange_age,
            'hard_exchange_lag_limit_sec': BOOK_HARD_EXCHANGE_LAG,
            'exchange_timestamp_known': self.exchange_ts is not None,
            'exchange_time_basis': self.exchange_time_basis,
            'sid': self.sid, 'seq': self.seq, 'generation': self.generation,
            'yes_bid': self.yes_bid, 'yes_ask': self.yes_ask,
            'no_bid': self.no_bid, 'no_ask': self.no_ask, 'close_ts': self.close_ts,
            'side_action_revision': SIDE_ACTION_REVISION, 'entry_allowed': fresh and self.can_buy('YES') and self.can_buy('NO'),
            'yes_mark_valid': fresh and self.can_mark('YES'), 'no_mark_valid': fresh and self.can_mark('NO'),
            'yes_sell_allowed': fresh and self.can_sell('YES'), 'no_sell_allowed': fresh and self.can_sell('NO'),
            'yes_mark_reason': self.mark_reason('YES'), 'no_mark_reason': self.mark_reason('NO'),
            'market_closed': self.market_closed,
            'yes_bid_size': self.yes_levels[0][1] if self.yes_levels else None,
            'no_bid_size': self.no_levels[0][1] if self.no_levels else None,
        }


class QuoteHub:
    """Single-market subscription manager; sequence anchors reset on each connection.

    Sequence policy: contiguous per orderbook sid, the deployment subscribes to
    ONE market. A new snapshot is a new authoritative sequence anchor. A gap,
    backwards sequence, malformed delta or negative resulting depth requires one.
    """
    def __init__(self):
        self.generation = 0
        self.ticker = ''
        self.close_ts = None
        self.sid = self.seq = None
        self.book_ok = False
        self.reason = 'AWAIT_SNAPSHOT'
        self.book = {'yes': {}, 'no': {}}
        self.book_wall = self.book_mono = 0.0
        self.book_exchange = None
        self.book_exchange_time_basis = ''
        self.corroborators = {}
        self.counter = 0
        self.book_counter = 0
        self.last_resnapshot = -math.inf
        self.events = []

    def begin(self, ticker, close_ts, wall, mono):
        self.generation += 1
        self.ticker, self.close_ts = str(ticker), close_ts
        self.sid = self.seq = None
        self.book_ok = False
        self.reason = 'AWAIT_SNAPSHOT'
        self.book = {'yes': {}, 'no': {}}
        self.book_wall, self.book_mono, self.book_exchange = wall, mono, None
        self.book_exchange_time_basis = ''
        self.corroborators = {}
        self.last_resnapshot = -math.inf
        self._event('CONNECTION_BEGIN', wall, ticker=self.ticker, generation=self.generation)

    def reconnect(self, wall, mono, receiver_generation=None):
        """Retire sequence ownership after a native socket reconnect.

        Contract/close identity is preserved, but sid/seq/depth must be re-anchored
        by the first authoritative snapshot from the new receiver generation.
        This prevents an old generation watermark from rejecting a legitimate
        lower sequence snapshot as BACKWARDS_SNAPSHOT.
        """
        self.generation += 1
        self.sid = self.seq = None
        self.book_ok = False
        self.reason = 'AWAIT_SNAPSHOT'
        self.book = {'yes': {}, 'no': {}}
        self.book_wall, self.book_mono, self.book_exchange = wall, mono, None
        self.book_exchange_time_basis = ''
        self.corroborators = {}
        self.last_resnapshot = -math.inf
        self._event('CONNECTION_REBEGIN', wall, ticker=self.ticker,
                    generation=self.generation,
                    receiver_generation=receiver_generation)

    def _event(self, kind, wall, **fields):
        self.events.append({'event': kind, 'wall_ts': wall, **fields})
        # The runtime drains this queue; protect memory if a caller does not.
        if len(self.events) > 2000:
            self.events = self.events[-2000:]

    def drain(self):
        events, self.events = self.events, []
        return events

    @staticmethod
    def _integer(x):
        if isinstance(x, bool) or not isinstance(x, int) or x < 1:
            raise ValueError('Missing sequence/subscription integer')
        return x

    @staticmethod
    def _levels(msg, side):
        key = next((k for k in (side + '_dollars_fp', side + '_dollars', side) if k in msg), None)
        if key is None or msg[key] is None:
            return {}
        rows = msg[key]
        if not isinstance(rows, list):
            raise ValueError('Malformed depth array')
        out = {}
        for row in rows:
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                raise ValueError('Malformed level')
            p, q = price(row[0], cents=(key == side)), number(row[1])
            if q < 0 or p in out:
                raise ValueError('Negative or duplicate snapshot level')
            if q:
                out[p] = q
        return out

    def _bad(self, reason, wall):
        self.book_ok, self.reason = False, reason
        self._event('BOOK_INVALID', wall, reason=reason, ticker=self.ticker,
                    sid=self.sid, seq=self.seq)

    def on_ws(self, data, wall, mono):
        if not isinstance(data, dict):
            return
        kind, msg = data.get('type'), data.get('msg') or {}
        if not isinstance(msg, dict):
            return
        if kind == 'error':
            self._bad('WEBSOCKET_CHANNEL_ERROR', wall)
            return
        if kind == 'subscribed' and msg.get('channel') == 'orderbook_delta':
            try:
                self.sid = self._integer(msg.get('sid'))
            except ValueError:
                pass
            return
        if kind not in ('ticker', 'orderbook_snapshot', 'orderbook_delta'):
            return  # public trade.price is NOT a bid or ask
        if msg.get('market_ticker') != self.ticker:
            self._event('WRONG_TICKER_IGNORED', wall, message_type=kind)
            return
        if kind == 'ticker':
            return self.on_top(msg, 'WS_TICKER', wall, mono)
        try:
            sid, seq = self._integer(data.get('sid')), self._integer(data.get('seq'))
            ts = exchange_time(msg)
            time_basis = 'BOOK_MESSAGE_EXCHANGE_TS' if ts is not None else ''
            if ts is None and data.get('sending_ts_ms') is not None:
                # This timestamp is supplied by Kalshi's WS envelope at
                # network queueing, NOT inferred from the machine clock or
                # invented from an untimed book snapshot. Optional in V2.
                stamp=data['sending_ts_ms']
                if type(stamp) is not int or stamp < 1_600_000_000_000:
                    self._bad('MALFORMED_WS_ENVELOPE_SENDING_TIMESTAMP',wall)
                    return
                ts=stamp/1000.0
                time_basis='WS_ENVELOPE_SENDING_TS'
            exchange_age = None if ts is None else wall-ts
            source_clock_skew = bool(ts is not None and
                (exchange_age > BOOK_MAX_EXCHANGE_LAG or ts - wall > FUTURE_TOLERANCE))
            # Hard backlog refusal is intentionally much looser than the old 6s
            # check. The 6s threshold stays advisory so normal Kalshi/workstation
            # clock skew cannot recreate the false readiness pauses. A known
            # exchange stamp older than 15s is not executable economics.
            if exchange_age is not None and exchange_age > BOOK_HARD_EXCHANGE_LAG:
                self._event('BOOK_EXCHANGE_STALE_REJECTED',wall,ticker=self.ticker,
                            message_type=kind,sid=sid,seq=seq,
                            time_basis=time_basis,age_seconds=round(exchange_age,6),
                            hard_limit_seconds=BOOK_HARD_EXCHANGE_LAG)
                self._bad('BOOK_EXCHANGE_STALE', wall)
                return
            if source_clock_skew:
                # Diagnostic only. PID2328 proved locally current, sequence-advancing
                # native books were being globally paused solely because Kalshi's
                # message timestamp was ~6-7s behind the workstation clock.
                self._event('WS_SOURCE_CLOCK_SKEW_ADVISORY',wall,ticker=self.ticker,
                            message_type=kind,sid=sid,seq=seq,
                            time_basis=time_basis,age_seconds=round(wall-ts,6),
                            diagnostic_lag_seconds=BOOK_MAX_EXCHANGE_LAG,
                            diagnostic_future_seconds=FUTURE_TOLERANCE)
            if kind == 'orderbook_snapshot':
                fresh = {s: self._levels(msg, s) for s in ('yes', 'no')}
                if self.sid == sid and self.seq is not None and seq < self.seq:
                    self._bad('BACKWARDS_SNAPSHOT', wall)
                    return
                # A repeated WS snapshot with the SAME sequence and SAME
                # levels is the same economic quote, not a new entry edge.
                # Contradictory depth at the same source sequence is a
                # provenance failure, not permission to issue a new quote ID.
                if self.book_ok and self.sid == sid and self.seq == seq:
                    if fresh == self.book:
                        self._event('DUPLICATE_SNAPSHOT_IGNORED', wall, sid=sid, seq=seq)
                    else:
                        self._bad('SAME_SEQUENCE_CONTRADICTORY_SNAPSHOT', wall)
                    return
                self.book, self.sid, self.seq = fresh, sid, seq
                self.book_ok, self.reason = True, 'SEQUENCE_ANCHORED'
                self._event('SNAPSHOT_ACCEPTED', wall, ticker=self.ticker, sid=sid, seq=seq,
                            exchange_ts=ts,exchange_time_basis=time_basis)
            else:
                if not self.book_ok or sid != self.sid or self.seq is None:
                    self._bad('DELTA_WITHOUT_VALID_SNAPSHOT', wall)
                    return
                if seq == self.seq:
                    self._event('DUPLICATE_DELTA_IGNORED', wall, sid=sid, seq=seq)
                    return
                if seq != self.seq + 1:
                    self._bad('SEQUENCE_GAP_OR_REORDER', wall)
                    return
                side = msg.get('side')
                if side not in ('yes', 'no'):
                    raise ValueError('Invalid book side')
                p = price(msg['price_dollars']) if 'price_dollars' in msg else price(msg.get('price'), True)
                delta = number(msg.get('delta_fp', msg.get('delta')))
                q = self.book[side].get(p, D(0)) + delta
                if q < 0:
                    self._bad('NEGATIVE_RESULTING_DEPTH', wall)
                    return
                if q == 0:
                    self.book[side].pop(p, None)
                else:
                    self.book[side][p] = q
                self.seq = seq
            self.book_counter += 1
            self.book_wall, self.book_mono, self.book_exchange = wall, mono, ts
            self.book_exchange_time_basis = time_basis
            if self.book['yes'] and self.book['no'] and max(self.book['yes']) + max(self.book['no']) > 1:
                self._bad('CROSSED_BOOK', wall)
            elif source_clock_skew:
                self._event('SOURCE_CLOCK_SKEW_BOOK_ACCEPTED', wall,
                            ticker=self.ticker, sid=sid, seq=seq,
                            exchange_ts=ts, exchange_time_basis=time_basis,
                            age_seconds=round(wall-ts,6))
        except (ValueError, TypeError, KeyError, InvalidOperation):
            self._bad('MALFORMED_BOOK_MESSAGE', wall)

    def on_top(self, msg, source, wall, mono, latency=0.0):
        try:
            ticker = msg.get('market_ticker', msg.get('ticker'))
            if ticker != self.ticker:
                return
            if source == 'REST_MARKET' and (latency < 0 or latency > MAX_REST_LATENCY):
                self._event('TOP_REJECTED', wall, source=source, reason='SLOW_REST_RESPONSE')
                return
            fields = quote_fields(msg)
            ts = exchange_time(msg)
            if ts is not None and (wall - ts > MAX_EXCHANGE_LAG or ts - wall > FUTURE_TOLERANCE):
                self._event('TOP_SOURCE_CLOCK_SKEW_ADVISORY', wall, source=source,
                            age_seconds=round(wall-ts,6))
            self.corroborators[source] = (fields, wall, mono, ts)
            self._event('TOP_OBSERVATION', wall, source=source, ticker=ticker,
                        yes_bid=fields[0], yes_ask=fields[1], no_bid=fields[2], no_ask=fields[3],
                        exchange_ts=ts, request_latency_sec=latency,
                        received_mono=mono, quote_time_known=ts is not None,
                        quote_policy_revision=QUOTE_POLICY_REVISION)
        except (ValueError, KeyError, TypeError):
            self._event('TOP_REJECTED', wall, source=source, reason='MALFORMED_OR_INCOMPLETE')

    def _live_pair_agrees(self, fields, wall, mono):
        """No inference of REST quote age; require independent timestamped WS support.

        'Independent' here means a separate WS message type, NOT a statistically
        independent exchange. No old quote is repriced or silently relabeled fresh.
        """
        item = self.corroborators.get('WS_TICKER')
        if item is None or self.book_exchange is None:
            return False
        other, received, omono, ts = item
        if ts is None or not 0 <= mono - omono <= CORROBORATOR_MAX_AGE:
            return False
        if not -FUTURE_TOLERANCE <= wall - ts <= MAX_EXCHANGE_LAG:
            return False
        if abs(ts - self.book_exchange) > LIVE_PAIR_MAX_EXCHANGE_SKEW + 1e-9:
            return False
        return all(abs(a - b) <= 1e-9 for a, b in zip(fields, other))

    def _one_side_permission(self, side, fields, wall, mono):
        """Called only for an otherwise healthy incomplete book, never for gaps,
        stale/crossed books or a complete book with an existing conflict veto.
        Check only the real native bid and its REAL complementary opposite ask.
        Missing opposite prices, including ticker 0/1 placeholders, are not depth.
        """
        indices = (0, 3) if side == 'YES' else (2, 1)
        if any(fields[i] is None for i in indices):
            return False, 'NO_NATIVE_' + side + '_BID'
        note = 'VALID_' + side + '_BID_ONLY'
        for source, (other, received, omono, ts) in self.corroborators.items():
            if not 0 <= mono - omono <= CORROBORATOR_MAX_AGE:
                continue
            if ts is not None and not -FUTURE_TOLERANCE <= wall - ts <= MAX_EXCHANGE_LAG:
                continue
            if max(abs(fields[i] - other[i]) for i in indices) < MATERIAL_DISAGREEMENT - 1e-9:
                continue
            # Restored early-run authority: corroborators never veto a locally
            # current native sequence book. Keep disagreement visible only.
            note = 'VALID_' + side + '_BID_ONLY_' + source + '_DISAGREEMENT_ADVISORY'
            continue
        return True, note

    def view(self, wall, mono, allow_closed=False) -> Quote:
        self.counter += 1
        yes = tuple((float(p), float(q)) for p, q in sorted(self.book['yes'].items(), reverse=True))
        no = tuple((float(p), float(q)) for p, q in sorted(self.book['no'].items(), reverse=True))
        yb, nb = (yes[0][0] if yes else None), (no[0][0] if no else None)
        ya, na = (float(1 - D(str(nb))) if nb is not None else None), (float(1 - D(str(yb))) if yb is not None else None)
        reason = None
        common_failure = None
        corroboration_note = None
        if not self.book_ok:
            common_failure = self.reason
        elif mono - self.book_mono > BOOK_MAX_AGE or mono < self.book_mono:
            common_failure = 'BOOK_RECEIVE_STALE'
        elif self.book_exchange is not None and wall-self.book_exchange > BOOK_HARD_EXCHANGE_LAG:
            common_failure = 'BOOK_EXCHANGE_STALE'
        closed = self.close_ts is not None and wall >= self.close_ts
        reason = common_failure
        if reason is None:
            if not yes or not no:
                reason = 'ONE_SIDED_BOOK_NO_EXECUTABLE_BOTH_SIDE_MARK'
            elif not allow_closed and closed:
                reason = 'CONTRACT_CLOSED'
        if reason is None:
            fields = (yb, ya, nb, na)
            for source, (other, received, omono, ts) in self.corroborators.items():
                if 0 <= mono - omono <= CORROBORATOR_MAX_AGE:
                    if ts is None or -FUTURE_TOLERANCE <= wall - ts <= MAX_EXCHANGE_LAG:
                        if max(abs(a-b) for a, b in zip(fields, other)) >= MATERIAL_DISAGREEMENT - 1e-9:
                            corroboration_note = 'VALID_NATIVE_BOOK_' + source + '_DISAGREEMENT_ADVISORY'
                            self._event('CORROBORATOR_DISAGREEMENT_ADVISORY', wall,
                                        source=source, ticker=self.ticker,
                                        native_quote=(yb,ya,nb,na), corroborator_quote=other)
                            continue
        permissions = {}
        fields = (yb, ya, nb, na)
        for side in ('YES', 'NO'):
            if common_failure or (closed and not allow_closed):
                permissions[side] = (False, common_failure or 'CONTRACT_CLOSED')
            elif reason is None:
                permissions[side] = (True, corroboration_note or 'VALID')
            elif not yes or not no:
                permissions[side] = self._one_side_permission(side, fields, wall, mono)
            else:
                permissions[side] = (False, reason)
        # Stable quote identity is bound to the actual sequence-checked
        # *book update*, NEVER to the number of times the dashboard reads it.
        # `counter` remains for resnapshot request IDs and diagnostics only.
        return Quote(f'Q{self.generation}:{self.sid}:{self.seq}:{self.book_counter}', self.ticker,
                     'WS_SEQUENCE_CHECKED_BOOK', reason is None, reason or corroboration_note or 'VALID',
                     self.book_wall, self.book_mono, self.book_exchange, self.sid, self.seq,
                     yb, ya, nb, na, yes, no, self.close_ts, self.generation,
                     permissions['YES'][0], permissions['NO'][0],
                     permissions['YES'][1], permissions['NO'][1], closed,
                     self.book_exchange_time_basis)

    def resnapshot_request(self, wall, mono):
        q = self.view(wall, mono)
        if q.valid or self.sid is None or mono - self.last_resnapshot < RESNAPSHOT_INTERVAL:
            return None
        if self.close_ts is not None and wall >= self.close_ts:
            return None
        self.last_resnapshot = mono
        self._event('RESNAPSHOT_REQUESTED', wall, ticker=self.ticker, reason=q.reason)
        return {'id': 100000 + self.counter, 'cmd': 'update_subscription', 'params': {
            'sids': [self.sid], 'market_tickers': [self.ticker], 'action': 'get_snapshot'}}
