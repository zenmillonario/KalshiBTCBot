"""Authored, causal BTC/quote inputs for the real Tool Rack pipeline.

These are synthetic observations, not PID12448 replay or a profitability model.
Peak/valley windows are fixed from the authored price path before any detector
is run. Production MinuteEMAs and chart ingestion derive EMA/OHLC observations;
no arc identity, territory, qualified edge, thesis or desired order is supplied.
"""
from dataclasses import dataclass
import math

from strategy_core.marketdata.btc_observation import MinuteEMAs, validate_candles
from strategy_core.marketdata.common import utc
from strategy_core.marketdata.kalshi_public import MarketInfo
from strategy_core.paper_execution import PaperBook, PriceLevel
from strategy_core.paper_feed import FeedSnapshot, _ChartHistory, freeze_data


BASE = 1_800_000_000.0


@dataclass(frozen=True)
class ArcScenario:
    name: str = "level_pyramid"
    direction: int = 1
    drift_per_second: float = 0.0
    amplitude: float = 120.0
    leg_seconds: int = 660
    plateau_seconds: int = 120
    prior_cycles: int = 3
    sample_seconds: int = 1
    quote_scale: float = 600.0
    target_offset: float = 60.0
    midpoint_floor: float = .02
    quote_half_spread: float = .01

    def __post_init__(self):
        if (self.direction not in (-1, 1) or self.sample_seconds != 1
                or self.amplitude <= 0 or self.leg_seconds < 60
                or self.plateau_seconds < 0 or self.prior_cycles < 1
                or self.quote_scale <= 0
                or not all(math.isfinite(value) for value in (self.midpoint_floor, self.quote_half_spread))
                or not 0 < self.quote_half_spread < self.midpoint_floor < .5):
            raise ValueError("INVALID_CONSTRUCT_ARC_SCENARIO")

    @property
    def cycle_seconds(self):
        return 2 * (self.leg_seconds + self.plateau_seconds)

    @property
    def current_start(self):
        return self.prior_cycles * self.cycle_seconds

    @property
    def first_edge_zone(self):
        start = self.current_start + self.leg_seconds
        return (start - 60, start + self.plateau_seconds)

    @property
    def second_edge_zone(self):
        start = self.current_start + 2 * self.leg_seconds + self.plateau_seconds
        return (start - 60, start + self.plateau_seconds)

    @property
    def peak_zone(self):
        return self.first_edge_zone if self.direction == 1 else self.second_edge_zone

    @property
    def valley_zone(self):
        return self.second_edge_zone if self.direction == 1 else self.first_edge_zone

    @property
    def end_offset(self):
        return self.current_start + self.cycle_seconds + 120

    def price(self, offset):
        phase = offset % self.cycle_seconds
        leg, pause = self.leg_seconds, self.plateau_seconds
        if phase <= leg:
            wave = -1.0 + 2.0 * phase / leg
        elif phase <= leg + pause:
            wave = 1.0
        elif phase <= 2 * leg + pause:
            wave = 1.0 - 2.0 * (phase - leg - pause) / leg
        else:
            wave = -1.0
        return 80_000.0 + self.drift_per_second * offset + self.direction * self.amplitude * wave

    def contract(self, offset):
        number = math.floor((offset - self.current_start) / 900)
        opened = self.current_start + number * 900
        # The fixed synthetic strike is known at this contract's opening.
        target = self.price(opened) + self.direction * self.target_offset
        ticker = f"KXBTC15M-CONSTRUCT-{self.name}-{number}"
        return MarketInfo(ticker, BASE + opened, BASE + opened + 900, "active",
            target=target, target_source="KALSHI_MARKET_FLOOR_STRIKE")

    def quote_values(self, offset):
        market = self.contract(offset)
        mid = max(self.midpoint_floor, min(1. - self.midpoint_floor,
            .5 + (self.price(offset) - market.target) / self.quote_scale))
        yes_bid = round(mid - self.quote_half_spread, 6)
        no_bid = round(1. - mid - self.quote_half_spread, 6)
        return {"yes_bid": yes_bid, "yes_ask": round(1. - no_bid, 6),
            "no_bid": no_bid, "no_ask": round(1. - yes_bid, 6)}

    def expectations(self):
        return {"source": "AUTHORED_PRICE_PATH_BEFORE_DETECTOR_OUTPUT",
            "synthetic": True, "base_ts": BASE,
            "current_leg_start_offset": self.current_start,
            "peak_zone_offsets": self.peak_zone, "peak_expected_side": "NO",
            "valley_zone_offsets": self.valley_zone, "valley_expected_side": "YES",
            "opening_expected_side": "YES" if self.direction == 1 else "NO",
            "prior_authored_full_cycles": self.prior_cycles,
            "candle_count_each_travel_leg": self.leg_seconds / 60,
            "plateau_candles": self.plateau_seconds / 60,
            "quote_formula": "clip(0.5 + (current BTC - fixed opening strike)/quote_scale, midpoint_floor, 1-midpoint_floor), spread 2*quote_half_spread",
            "quote_scale": self.quote_scale, "target_offset": self.target_offset,
            "midpoint_floor": self.midpoint_floor, "quote_half_spread": self.quote_half_spread,
            "prior_cycles_are_not_assumed_detected_references": True}


@dataclass(frozen=True)
class ArcTape:
    scenario: ArcScenario
    rows: tuple
    completed_bars: tuple

    def history_at(self, offset):
        at = BASE + offset
        return tuple(bar for bar in self.completed_bars
            if bar.get("complete") is True and bar.get("full_minute") is True
            and bar["time"] + 60 <= at and bar["known_at"] <= at)

    def capture(self, offset, previous_offset=None, *, include_prefix=False):
        offset = int(offset)
        if not 0 <= offset <= self.scenario.end_offset:
            raise ValueError("CONSTRUCT_OFFSET_OUTSIDE_AUTHORED_TAPE")
        left = 0 if include_prefix else offset if previous_offset is None else int(previous_offset) + 1
        observed = BASE + offset
        market, q = self.scenario.contract(offset), self.scenario.quote_values(offset)
        book = PaperBook(market.ticker, f"SYNTHETIC:{self.scenario.name}:{offset}", observed, observed,
            (PriceLevel(q["yes_bid"], 1000),), (PriceLevel(q["no_bid"], 1000),), market.close_ts,
            provenance=freeze_data({"synthetic_fixture": True, "sequence_checked": True,
                "snapshot_verified": True, "monotonic_receive_fresh": True,
                "venue_depth_claim": False}))
        return FeedSnapshot(offset, observed, market, book, freeze_data(self.rows[left:offset + 1]),
            freeze_data({"btc_current": True, "book_current": True, "synthetic_fixture": True}))


def build_tape(scenario: ArcScenario) -> ArcTape:
    """Precompute explicit observations; consumers see only each received prefix.

    The candle/EMA machinery first receives 240 minutes of synthetic seed bars,
    then 240 minutes of actual authored forward samples before time zero. This
    supplies coherent completed chart bars without making them physical ticks.
    Only observations at/after zero are offered as forward physical evidence.
    """
    first = -240 * 60
    seed_rows = []
    for opened in range(first - 240 * 60, first, 60):
        values = [scenario.price(second) for second in range(opened, opened + 60)]
        seed_rows.append([BASE + opened, min(values), max(values), values[0], values[-1], 1.])
    seed, metadata = validate_candles(seed_rows, BASE + first)
    model, chart = MinuteEMAs(seed, metadata, 1), _ChartHistory()
    raw = []
    for offset in range(first, scenario.end_offset + 1):
        at, price = BASE + offset, scenario.price(offset)
        serial = offset - first + 1
        model.update(at, price)
        sample = model.sample(at, at, float(serial), serial, str(serial))
        sample.update(epoch_ms=at * 1000, synthetic_fixture=True,
            geometry_source="CONSTRUCT_SYNTHETIC_PRICE_THROUGH_PRODUCTION_MINUTE_EMAS")
        chart.trade({"timestamp_epoch": at, "price": price, "received_monotonic": float(serial),
            "received_utc": utc(at), "trade_id": str(serial), "connection_epoch": 1})
        chart.geometry(sample)
        if offset >= 0:
            raw.append(sample)
    bars = []
    for stamp in sorted(chart.bars):
        bar = dict(chart.bars[stamp])
        if bar.get("complete") is True and bar.get("full_minute") is True:
            # A completed minute becomes available at the following minute,
            # never at its last trade's timestamp inside the still-open bar.
            bar.update(known_at=bar["time"] + 60,
                source="CONSTRUCT_SYNTHETIC_ACCEPTED_TRADES", synthetic_fixture=True)
            bars.append(bar)
    return ArcTape(scenario, tuple(raw), tuple(bars))
