from pydantic import BaseModel
from decimal import Decimal
from typing import Optional


class StandardSignal(BaseModel):
    symbol: str
    exchange: str
    action: str  # BUY, SELL
    quantity: Decimal
    order_type: str  # MARKET, LIMIT, SL
    price: Optional[Decimal] = None
    trigger_price: Optional[Decimal] = None
    product_type: str  # INTRADAY, DELIVERY, FUTURES

    # Futures-specific settings (ignored for spot orders)
    leverage: Optional[int] = None          # e.g. 20 → "20X"
    position_model: Optional[str] = None    # "isolated" or "cross"
    take_profit: Optional[Decimal] = None   # TP price
    stop_loss: Optional[Decimal] = None     # SL price
