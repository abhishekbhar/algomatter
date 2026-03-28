"""Async broker factory.

Resolves a broker_type string and credentials dict into an authenticated
BrokerAdapter instance ready for use.
"""

from app.brokers.base import BrokerAdapter
from app.brokers.binance_testnet import BinanceTestnetBroker


async def get_broker(broker_type: str, credentials: dict) -> BrokerAdapter:
    """Create and authenticate a broker adapter by type.

    The SimulatedBroker is not included here — it is only used by
    backtesting and paper trading, which instantiate it directly.
    """
    match broker_type:
        case "binance_testnet":
            broker = BinanceTestnetBroker()
            authenticated = await broker.authenticate(credentials)
            if not authenticated:
                await broker.close()
                raise RuntimeError("Failed to authenticate with Binance testnet")
            return broker
        case "exchange1":
            from app.brokers.exchange1 import Exchange1Broker
            broker = Exchange1Broker()
            authenticated = await broker.authenticate(credentials)
            if not authenticated:
                await broker.close()
                raise RuntimeError("Failed to authenticate with Exchange1")
            return broker
        case _:
            raise ValueError(f"Unknown broker type: {broker_type}")
