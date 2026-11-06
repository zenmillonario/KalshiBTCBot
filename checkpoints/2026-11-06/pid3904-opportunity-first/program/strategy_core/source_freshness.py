"""One bounded source-clock policy, with a separate local receipt clock.

An exchange timestamp is not a local observation timestamp.  The direct feed
already accepts at most two seconds of source-clock lead while requiring a
recent monotonic receipt.  Only that exact captured frame may carry the same
allowance into its physical consumers.  A naked future timestamp, a quote
receipt, or an old context label cannot supply the missing BTC receipt proof.

Legacy nonnegative-age packets retain their existing checks.  New direct-feed
packets carry the receipt below, so a contradictory/stale receipt fails even
when its source timestamp is nonnegative.  No clocks or timestamps are moved.
"""
from __future__ import annotations

import math
from typing import Any, Mapping


RECEIPT_KEY = "physical_source_receipt"
RECEIPT_VERSION = "DIRECT_CURRENT_SOURCE_RECEIPT_V1"
_DIRECT = "DIRECT_BTC_AND_NATIVE_KALSHI"
_MEASUREMENT = "DIRECT_CAUSAL_BTC_EMA9_V2_NATIVE_CURRENT_LEG"
_FEED = "DIRECT_COINBASE_PUBLIC_TRADES"
_FEED_REVISION = "TOOL_RACK_DIRECT_MARKET_DATA_V1"
_MAX_FUTURE_SECONDS = 2.0
_MAX_RECEIVE_SECONDS = 5.0


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _same_source(a: Any, b: Any) -> bool:
    left, right = _number(a), _number(b)
    return left is not None and right is not None and abs(left - right) <= .001


def _generation(value: Any) -> bool:
    return type(value) is int and value >= 0


def capture_source_receipt(metadata: Mapping[str, Any], source_status: Mapping[str, Any], *,
                           captured_at: Any, source_generation: Any) -> dict[str, Any] | None:
    """Carry existing frozen feed evidence into strategy metadata.

    ``captured_at`` is FeedSnapshot.observed_ts, not the later strategy clock.
    The feed's receive age is monotonic and was measured at that capture.
    Synthetic/legacy feeds without this capture protocol get no new allowance.
    """
    status, geometry = _map(source_status), _map(metadata.get("current_geometry"))
    if (status.get("revision") != _FEED_REVISION
            or status.get("geometry_source") != _FEED
            or status.get("captured_together_without_producer_reread") is not True):
        return None
    return {
        "version": RECEIPT_VERSION,
        "source": metadata.get("source"),
        "measurement_source": geometry.get("measurement_source"),
        "source_ms": geometry.get("epoch_ms"),
        "captured_at": captured_at,
        "source_age_seconds_at_capture": status.get("btc_geometry_age_seconds"),
        "receive_age_seconds_at_capture": status.get("btc_geometry_receive_age_seconds"),
        "btc_current_at_capture": status.get("btc_current"),
        "physical_current_at_capture": metadata.get("physical_current"),
        "connection_epoch": status.get("btc_connection_epoch"),
        "geometry_connection_epoch": geometry.get("connection_epoch"),
        "source_sequence": geometry.get("source_sequence"),
        "continuity_generation": metadata.get("geometry_continuity_generation"),
        "source_generation": source_generation,
        "max_source_age_seconds": metadata.get("geometry_max_source_age_seconds"),
        "max_future_skew_seconds": metadata.get("geometry_max_future_skew_seconds"),
    }


def source_receipt_is_fresh(receipt: Any, *, now_ts: Any, source_ms: Any,
                            max_age_seconds: float = 5.0,
                            continuity_generation: Any = None) -> bool:
    """Validate an exact frozen receipt, including at a later filled entry.

    A mission may retain this proof with its original source timestamp.  That
    proves what was current at admission; it does not make it current forever.
    The elapsed local time is added to the captured monotonic receive age.
    """
    proof = _map(receipt)
    now, source, capture, receive, capture_age, ceiling, future, requested = (
        _number(value) for value in (now_ts, source_ms, proof.get("captured_at"),
            proof.get("receive_age_seconds_at_capture"),
            proof.get("source_age_seconds_at_capture"), proof.get("max_source_age_seconds"),
            proof.get("max_future_skew_seconds"), max_age_seconds))
    if (any(value is None for value in (now, source, capture, receive, capture_age,
                                        ceiling, future, requested))
            or proof.get("version") != RECEIPT_VERSION
            or proof.get("source") != _DIRECT or proof.get("measurement_source") != _MEASUREMENT
            or proof.get("btc_current_at_capture") is not True
            or proof.get("physical_current_at_capture") is not True
            or not _same_source(proof.get("source_ms"), source)
            or not _generation(proof.get("continuity_generation"))
            or not _generation(proof.get("source_generation"))
            or not _generation(proof.get("source_sequence"))
            or not _generation(proof.get("connection_epoch"))
            or proof.get("connection_epoch") != proof.get("geometry_connection_epoch")
            or continuity_generation is not None
                and proof.get("continuity_generation") != continuity_generation):
        return False
    if ceiling <= 0 or requested <= 0 or future < 0:
        return False
    allowance = min(future, _MAX_FUTURE_SECONDS)
    elapsed = now - capture
    return bool(0 <= elapsed and 0 <= receive
        and receive + elapsed <= min(ceiling, _MAX_RECEIVE_SECONDS)
        and -allowance <= capture_age <= ceiling
        and abs(capture - source / 1000.0 - capture_age) <= 1e-6
        and -allowance <= now - source / 1000.0 <= min(requested, ceiling))


def current_source_is_fresh(snapshot: Any, source_ms: Any, *,
                            max_age_seconds: float = 5.0) -> bool:
    """Check the current physical source without loosening local quote time."""
    md = _map(snapshot.metadata)
    now, source, requested = (_number(v) for v in (snapshot.now_ts, source_ms, max_age_seconds))
    configured = _number(md.get("geometry_max_source_age_seconds"))
    if now is None or source is None or requested is None or requested <= 0:
        return False
    maximum = min(requested, configured) if configured is not None and configured > 0 else requested
    age = now - source / 1000.0
    if md.get("physical_current") is False or age > maximum:
        return False
    receipt = md.get(RECEIPT_KEY)
    if receipt is None:
        # Existing fixtures/old saved packets have no monotonic receipt proof.
        # They keep their previous nonnegative allowance, never a future one.
        return 0 <= age <= maximum
    geometry = _map(md.get("current_geometry"))
    proof = _map(receipt)
    return bool(md.get("physical_current") is True and md.get("source") == _DIRECT
        and geometry.get("measurement_source") == _MEASUREMENT
        and _generation(md.get("geometry_continuity_generation"))
        and _generation(md.get("source_generation"))
        and _generation(geometry.get("connection_epoch"))
        and _generation(geometry.get("source_sequence"))
        and _same_source(geometry.get("epoch_ms"), source)
        and _same_source(md.get("geometry_last_epoch_ms"), source)
        and geometry.get("connection_epoch") == proof.get("connection_epoch")
        and geometry.get("source_sequence") == proof.get("source_sequence")
        and md.get("source_generation") == proof.get("source_generation")
        and md.get("geometry_continuity_generation") == proof.get("continuity_generation")
        and _number(md.get("geometry_max_source_age_seconds")) == _number(proof.get("max_source_age_seconds"))
        and _number(md.get("geometry_max_future_skew_seconds")) == _number(proof.get("max_future_skew_seconds"))
        and source_receipt_is_fresh(proof, now_ts=now, source_ms=source,
            max_age_seconds=maximum, continuity_generation=md.get("geometry_continuity_generation")))


def current_source_receipt(snapshot: Any, source_ms: Any, *,
                           max_age_seconds: float = 5.0) -> dict[str, Any] | None:
    """Copy a verified receipt into a new entry/role proof, never old history."""
    receipt = _map(snapshot.metadata).get(RECEIPT_KEY)
    return (dict(receipt) if isinstance(receipt, Mapping)
            and current_source_is_fresh(snapshot, source_ms, max_age_seconds=max_age_seconds) else None)
