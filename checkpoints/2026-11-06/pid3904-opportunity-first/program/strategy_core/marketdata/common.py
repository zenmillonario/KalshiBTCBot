"""Isolated numeric/time helpers used by the public BTC parser.

No import from an engine, Commander, observer application, or run directory.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any


class ObserverError(RuntimeError):
    pass


def number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def parse_time(value: Any) -> float:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        result = parsed.timestamp()
        if not math.isfinite(result):
            raise ValueError
        return result
    except (TypeError, ValueError, OverflowError):
        raise ObserverError("SOURCE_TIMESTAMP_MISSING_OR_INVALID") from None
