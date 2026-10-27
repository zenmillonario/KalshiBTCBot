"""Pure public BTC observation parser and independent 1m-close EMA reconstruction.

No account access or network in this module. No Kalshi mark or engine decision.
A sampled Coinbase TRADE price is not an executable contract bid or settlement index.
"""
from __future__ import annotations
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from .common import number, utc, ObserverError, parse_time

PRODUCT = 'BTC-USD'
SEED_BARS = 240
MAX_EVENT_AGE = 3.0
MAX_FUTURE = 2.0
SAMPLE_SECONDS = 1.0
NO_PRICE_GAP = 30.0

class FeedFault(ObserverError):
    """Reason codes only, no remote response text or credentials."""


def positive(x):
    n = number(x)
    if n is None or n <= 0: raise FeedFault('INVALID_POSITIVE_NUMBER')
    return n


def validate_candles(rows, now):
    """Use only a contiguous suffix of actually returned completed minute buckets.

    No missing interval is filled. No OHLC path, historical forecast or swing is
    invented. Old-prefix holes are disclosed; newest bucket must be the previous
    minute. Strict initialization failure stops the companion, not the engine.
    """
    if not isinstance(rows, list) or len(rows) > 1000: raise FeedFault('INVALID_CANDLE_RESPONSE')
    current = int(now // 60) * 60
    bars = {}
    skipped_open = 0
    for r in rows:
        if not isinstance(r, list) or len(r) < 6: raise FeedFault('INVALID_CANDLE_ROW')
        ts = number(r[0])
        if ts is None or ts != int(ts) or int(ts) % 60: raise FeedFault('INVALID_CANDLE_BUCKET')
        ts = int(ts)
        if ts >= current:
            skipped_open += 1
            continue
        lo, hi, op, close = (positive(x) for x in r[1:5])
        volume = number(r[5])
        if volume is None or volume < 0 or not lo <= min(op,close) <= max(op,close) <= hi:
            raise FeedFault('INVALID_CANDLE_OHLC')
        b = (ts, close)
        if ts in bars and bars[ts] != b: raise FeedFault('CONFLICTING_CANDLE_DUPLICATE')
        bars[ts] = b
    end = current - 60
    ordered = []
    while end in bars and len(ordered) < SEED_BARS:
        ordered.append(bars[end]); end -= 60
    ordered.reverse()
    if len(ordered) < 30:
        failure=FeedFault('SEED_NEEDS_30_RECENT_CONTIGUOUS_MINUTES')
        failure.seed_diagnostic={
            'returned_rows':len(rows),'validated_completed_buckets':len(bars),
            'expected_latest_completed_bucket':current-60,
            'latest_returned_completed_bucket':max(bars) if bars else None,
            'required_latest_present':current-60 in bars,
            'contiguous_completed_bars':len(ordered),'first_missing_bucket':end,
            'discarded_open_future_buckets':skipped_open,
            'failure_kind':'LATEST_COMPLETED_MINUTE_MISSING' if current-60 not in bars else
                'GAP_IN_RECENT_SUFFIX' if any(t<end for t in bars) else 'INSUFFICIENT_RETURNED_HISTORY',
        }
        raise failure
    return ordered, {'completed_bars':len(ordered),'first_bucket':ordered[0][0],
        'last_bucket':ordered[-1][0], 'discarded_open_future_buckets':skipped_open,
        'unused_completed_buckets':len(bars)-len(ordered),
        'source':'COINBASE_EXCHANGE_PUBLIC_CANDLES_60S',
        'historical_seed_is_not_forward_observation':True}


def ema(values, period):
    if len(values) < period: return None
    x = sum(values[:period]) / period
    k = 2.0 / (period + 1)
    for v in values[period:]: x += k * (v-x)
    return x


class MinuteEMAs:
    """Independent rolling 240-close SMA-seeded EMA plus provisional live close.

    The formula matches the inspected engine, NOT necessarily its data or output:
    this connection and exchange-time candle boundaries are independent. The
    engine uses its own connection and receipt-time bars. Drift is logged.
    """
    def __init__(self, seed, metadata, epoch):
        self.closed = deque(seed, maxlen=SEED_BARS)
        self.metadata = dict(metadata); self.epoch = epoch
        self.minute = None; self.price = None; self.last_t = None
        self.samples = 0; self.completed_live = 0

    def update(self, t, price):
        price = positive(price)
        if self.last_t is not None and t < self.last_t: raise FeedFault('OUT_OF_ORDER_TRADE_TIME')
        m = int(t // 60)*60
        if self.minute is None:
            if self.closed and m != self.closed[-1][0]+60: raise FeedFault('GAP_BETWEEN_SEED_AND_LIVE')
            self.minute = m
        elif m != self.minute:
            if m != self.minute + 60: raise FeedFault('MISSING_LIVE_MINUTE')
            self.closed.append((self.minute,self.price));self.completed_live+=1
            self.minute=m
        self.price=price;self.last_t=t

    def sample(self,t,received,mono,seq,trade_id):
        vals = [p for _,p in self.closed]+[self.price]
        e9,e30 = ema(vals,9),ema(vals,30)
        if e9 is None or e30 is None: raise FeedFault('EMA_NOT_READY')
        self.samples+=1
        return {'timestamp':utc(t),'btc_price':self.price,'ema9':e9,'ema30':e30,
            'product_id':PRODUCT,'geometry_source':'COINBASE_PUBLIC_TRADES_INDEPENDENT',
            'price_kind':'BTC_TRADE_NOT_CONTRACT_BID', 'exchange_trade_utc':utc(t),
            'received_utc':utc(received),'received_monotonic':mono,
            'exchange_to_receive_seconds':received-t,'connection_epoch':self.epoch,
            'sequence_num':seq,'last_trade_id':trade_id,
            'sample_serial':self.samples,'sample_policy':'LAST_TRADE_IN_RECEIVED_UPDATE_AT_MOST_1HZ',
            'completed_seed_bars':self.metadata['completed_bars'],
            'completed_live_minutes':self.completed_live,'current_minute':self.minute,
            'ema_method':'SMA_SEED_9_30_ROLLING_240_COMPLETED_MINUTE_CLOSES_PLUS_PROVISIONAL',
            'ema_clock':'EXCHANGE_TRADE_TIME','engine_ema_equality_claim':False,
            'seed_metadata':self.metadata}


class TradeStream:
    """Single-channel market_trades connection, contiguous envelope sequence.

    Subscription snapshots are recorded but NEVER interpreted as fresh trades.
    All update trades are parsed before any sample from the batch is produced.
    No synthetic flat sample is emitted on heartbeats or idle polls.
    """
    def __init__(self, seed, metadata, epoch):
        self.epoch=epoch;self.seq=None;self.anchored=False
        self.ids=set();self.id_order=deque();self.last_trade_t=None
        self.last_emitted=None;self.last_receive=None;self.stats=Counter()
        self.bars=MinuteEMAs(seed,metadata,epoch)
        self.last_processed_id=None;self.last_accepted=[]

    def consume(self, message, received, mono):
        self.last_accepted=[]
        if not isinstance(message,dict):raise FeedFault('NON_OBJECT_MESSAGE')
        if message.get('type')=='error':raise FeedFault('PUBLIC_SUBSCRIPTION_ERROR')

        # Coinbase sequence_num is connection-envelope ordering in the observed
        # public stream, not a market_trades-only counter.  Subscription acks and
        # future supported/ignored envelopes can occupy a number between trade
        # envelopes.  Advance the connection sequence before channel filtering so
        # 0 market snapshot -> 1 subscriptions -> 2 market update stays contiguous.
        channel=message.get('channel')
        n=message.get('sequence_num')
        if n is not None:
            if not isinstance(n,int) or isinstance(n,bool) or n<0:raise FeedFault('MISSING_SEQUENCE')
            if self.seq is not None:
                if n<=self.seq:
                    self.stats['duplicate_or_old_envelopes']+=1;return []
                if n!=self.seq+1:raise FeedFault('PUBLIC_SEQUENCE_GAP')
            self.seq=n
        elif channel=='market_trades':
            raise FeedFault('MISSING_SEQUENCE')

        if channel != 'market_trades':
            self.stats['non_trade_envelopes']+=1;return []
        events=message.get('events')
        if not isinstance(events,list):raise FeedFault('MISSING_EVENTS')
        frame_t=parse_time(message.get('timestamp'))
        if frame_t>received+MAX_FUTURE or received-frame_t>MAX_EVENT_AGE:
            raise FeedFault('STALE_OR_FUTURE_ENVELOPE')
        pending=[];snapshot_ids=[];saw_snapshot=False
        for event in events:
            if not isinstance(event,dict):raise FeedFault('INVALID_TRADE_EVENT')
            typ=event.get('type')
            if typ not in ('snapshot','update'):raise FeedFault('UNSUPPORTED_TRADE_EVENT')
            trades=event.get('trades')
            if not isinstance(trades,list):raise FeedFault('MISSING_TRADES')
            if typ=='snapshot':
                saw_snapshot=True
                for r in trades:
                    if isinstance(r,dict) and r.get('product_id')==PRODUCT:
                        snapshot_ids.append(str(r.get('trade_id','')))
                continue
            for r in trades:
                if not isinstance(r,dict):raise FeedFault('INVALID_TRADE_ROW')
                if r.get('product_id')!=PRODUCT:raise FeedFault('WRONG_PRODUCT_ON_SINGLE_PRODUCT_FEED')
                tid=str(r.get('trade_id',''))
                if not tid.isdecimal():raise FeedFault('INVALID_TRADE_ID')
                if tid in self.ids: self.stats['duplicate_trade_ids']+=1;continue
                t=parse_time(r.get('time'));p=positive(r.get('price'));size=number(r.get('size'))
                if size is None or size<0:raise FeedFault('INVALID_TRADE_SIZE')
                if t>received+MAX_FUTURE or t>frame_t+MAX_FUTURE or received-t>MAX_EVENT_AGE:
                    raise FeedFault('STALE_OR_FUTURE_TRADE')
                pending.append((t,int(tid),tid,p,size,str(r.get('side') or '')))
        if not self.anchored and not saw_snapshot:raise FeedFault('UPDATE_BEFORE_SNAPSHOT')
        if self.anchored and saw_snapshot:raise FeedFault('UNEXPECTED_RESNAPSHOT_REANCHOR_REQUIRED')
        if saw_snapshot:
            self.anchored=True;self.stats['snapshot_trades_excluded']+=len(snapshot_ids)
            for tid in snapshot_ids:self._remember(tid)
        self.last_receive=received;self.stats['trade_envelopes']+=1
        pending.sort(key=lambda x:(x[0],x[1]))
        accepted=[]
        for t,_,tid,p,size,side in pending:
            if tid in self.ids:continue
            if self.last_trade_t is not None and t<self.last_trade_t:raise FeedFault('OUT_OF_ORDER_TRADE_TIME')
            # A gap is missing observations, not proof of an exchange outage.
            if self.last_trade_t is not None and t-self.last_trade_t>NO_PRICE_GAP:
                raise FeedFault('NO_PRICE_OBSERVATION_OVER_30S')
            self.bars.update(t,p);self.last_trade_t=t;self.last_processed_id=tid
            self._remember(tid);accepted.append((t,p,size,tid,side));self.stats['accepted_trade_updates']+=1
        self.last_accepted=[{'timestamp_epoch':t,'timestamp':utc(t),'price':p,'size':size,'trade_id':tid,'maker_side':side,
            'connection_epoch':self.epoch,'sequence_num':n,'received_utc':utc(received),'received_monotonic':mono,
            'exchange_to_receive_seconds':received-t,'price_kind':'BTC_TRADE_NOT_CONTRACT_BID'} for t,p,size,tid,side in accepted]
        if not accepted:return []
        t=accepted[-1][0]
        if self.last_emitted is not None and t-self.last_emitted<SAMPLE_SECONDS:return []
        self.last_emitted=t
        s=self.bars.sample(t,received,mono,n,self.last_processed_id)
        s['batch_trade_count']=len(accepted)
        return [s]

    def _remember(self,tid):
        if tid in self.ids:return
        self.ids.add(tid);self.id_order.append(tid)
        while len(self.id_order)>20000:self.ids.discard(self.id_order.popleft())
