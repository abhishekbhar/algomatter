"""Build Nautilus Trader instruments from symbol strings."""

from __future__ import annotations

import re

from nautilus_trader.model.currencies import Currency
from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Price, Quantity

# Well-known quote currencies ordered longest-first so greedy matching works.
_KNOWN_QUOTES = [
    "USDT", "BUSD", "USDC", "TUSD", "BIDR", "BVND",
    "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF",
    "BTC", "ETH", "BNB", "DAI",
]

_QUOTE_RE = re.compile(r"(" + "|".join(_KNOWN_QUOTES) + r")$")


def _split_symbol(symbol: str) -> tuple[str, str]:
    """Split a concatenated symbol like 'BTCUSDT' into ('BTC', 'USDT').

    Falls back to splitting at the midpoint if no known quote is found.
    """
    m = _QUOTE_RE.search(symbol.upper())
    if m:
        quote = m.group(1)
        base = symbol[: m.start()]
        if base:
            return base.upper(), quote
    # Fallback: split at midpoint
    mid = len(symbol) // 2
    return symbol[:mid].upper(), symbol[mid:].upper()


def build_instrument(
    symbol: str,
    exchange: str,
    price_precision: int = 2,
    size_precision: int = 8,
) -> CurrencyPair:
    """Create a Nautilus ``CurrencyPair`` instrument.

    Parameters
    ----------
    symbol : str
        Concatenated trading pair, e.g. ``"BTCUSDT"``.
    exchange : str
        Venue/exchange name, e.g. ``"BINANCE"``.
    price_precision : int
        Number of decimal places for prices.
    size_precision : int
        Number of decimal places for quantities.

    Returns
    -------
    CurrencyPair
    """
    base_code, quote_code = _split_symbol(symbol)
    venue = Venue(exchange.upper())
    instrument_id = InstrumentId(Symbol(symbol.upper()), venue)

    base_currency = Currency.from_str(base_code)
    quote_currency = Currency.from_str(quote_code)

    price_increment = Price(10 ** (-price_precision), precision=price_precision)
    size_increment = Quantity(10 ** (-size_precision), precision=size_precision)

    return CurrencyPair(
        instrument_id=instrument_id,
        raw_symbol=Symbol(symbol.upper()),
        base_currency=base_currency,
        quote_currency=quote_currency,
        price_precision=price_precision,
        size_precision=size_precision,
        price_increment=price_increment,
        size_increment=size_increment,
        ts_event=0,
        ts_init=0,
    )
