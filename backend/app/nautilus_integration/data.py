"""Convert OHLCV candle dicts to Nautilus Bar objects."""

from __future__ import annotations

from datetime import datetime, timezone

from nautilus_trader.model.data import Bar, BarAggregation, BarSpecification, BarType
from nautilus_trader.model.enums import AggregationSource, PriceType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Price, Quantity

# Mapping from common interval strings to (step, BarAggregation).
_INTERVAL_MAP: dict[str, tuple[int, BarAggregation]] = {
    "1m": (1, BarAggregation.MINUTE),
    "3m": (3, BarAggregation.MINUTE),
    "5m": (5, BarAggregation.MINUTE),
    "15m": (15, BarAggregation.MINUTE),
    "30m": (30, BarAggregation.MINUTE),
    "1h": (1, BarAggregation.HOUR),
    "2h": (2, BarAggregation.HOUR),
    "4h": (4, BarAggregation.HOUR),
    "6h": (6, BarAggregation.HOUR),
    "8h": (8, BarAggregation.HOUR),
    "12h": (12, BarAggregation.HOUR),
    "1d": (1, BarAggregation.DAY),
    "1w": (1, BarAggregation.WEEK),
    "1M": (1, BarAggregation.MONTH),
}


def interval_to_bar_spec(interval: str) -> BarSpecification:
    """Convert a human-readable interval string to a ``BarSpecification``.

    Supported intervals: ``1m``, ``5m``, ``15m``, ``30m``, ``1h``, ``4h``,
    ``1d``, ``1w``, ``1M``, etc.
    """
    key = interval.strip()
    if key not in _INTERVAL_MAP:
        raise ValueError(
            f"Unsupported interval '{interval}'. "
            f"Supported: {sorted(_INTERVAL_MAP.keys())}"
        )
    step, aggregation = _INTERVAL_MAP[key]
    return BarSpecification(
        step=step,
        aggregation=aggregation,
        price_type=PriceType.LAST,
    )


def make_bar_type(
    instrument_id: InstrumentId,
    interval: str,
) -> BarType:
    """Build a ``BarType`` from an instrument ID and interval string."""
    bar_spec = interval_to_bar_spec(interval)
    return BarType(
        instrument_id=instrument_id,
        bar_spec=bar_spec,
        aggregation_source=AggregationSource.EXTERNAL,
    )


def _ts_to_nanos(ts: datetime | float | int) -> int:
    """Convert a timestamp to nanoseconds since epoch.

    Accepts:
    - ``datetime`` objects (timezone-aware or naive, treated as UTC)
    - ``float``/``int`` seconds since epoch
    - ``int`` already in nanoseconds (> 1e15 heuristic)
    """
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return int(ts.timestamp() * 1_000_000_000)
    if isinstance(ts, (int, float)):
        # If the value is large enough to be nanoseconds already, keep it.
        if isinstance(ts, int) and ts > 1_000_000_000_000_000:
            return ts
        return int(float(ts) * 1_000_000_000)
    raise TypeError(f"Unsupported timestamp type: {type(ts)}")


def ohlcv_to_bars(
    candles: list[dict],
    instrument_id: InstrumentId,
    bar_type: BarType,
    price_precision: int = 2,
    volume_precision: int = 8,
) -> list[Bar]:
    """Convert a list of OHLCV candle dicts to Nautilus ``Bar`` objects.

    Each candle dict must have keys: ``timestamp``, ``open``, ``high``,
    ``low``, ``close``, ``volume``.  The ``timestamp`` field can be a
    ``datetime`` object, a Unix timestamp in seconds (float/int), or
    nanoseconds (large int).

    Parameters
    ----------
    candles : list[dict]
        Raw OHLCV data.
    instrument_id : InstrumentId
        The instrument these bars belong to.
    bar_type : BarType
        The bar type specification.
    price_precision : int
        Decimal precision for prices.
    volume_precision : int
        Decimal precision for volume.

    Returns
    -------
    list[Bar]
    """
    bars: list[Bar] = []
    for c in candles:
        ts_ns = _ts_to_nanos(c["timestamp"])
        bar = Bar(
            bar_type=bar_type,
            open=Price(float(c["open"]), precision=price_precision),
            high=Price(float(c["high"]), precision=price_precision),
            low=Price(float(c["low"]), precision=price_precision),
            close=Price(float(c["close"]), precision=price_precision),
            volume=Quantity(float(c["volume"]), precision=volume_precision),
            ts_event=ts_ns,
            ts_init=ts_ns,
        )
        bars.append(bar)
    return bars
