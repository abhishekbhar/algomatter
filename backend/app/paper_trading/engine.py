import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PaperPosition, PaperTrade, PaperTradingSession
from app.webhooks.schemas import StandardSignal


async def execute_paper_trade(
    session: AsyncSession,
    paper_session_id: uuid.UUID,
    tenant_id: uuid.UUID,
    signal: StandardSignal,
    signal_id: uuid.UUID | None = None,
) -> str:
    """Execute a paper trade based on a webhook signal.

    1. Load paper trading session from DB
    2. Use signal.price if provided (or default to Decimal(0))
    3. For BUY: check balance, create PaperPosition, create PaperTrade, deduct balance
    4. For SELL: find matching open position, close it, compute realized PnL,
       create PaperTrade, add proceeds to balance
    5. Update paper_trading_sessions.current_balance
    6. Return "filled" or "rejected"
    """
    result = await session.execute(
        select(PaperTradingSession).where(PaperTradingSession.id == paper_session_id)
    )
    paper_session = result.scalar_one_or_none()
    if paper_session is None or paper_session.status != "active":
        return "rejected"

    if not signal.price or signal.price <= 0:
        return "rejected"
    fill_price = Decimal(str(signal.price))

    if not signal.quantity or signal.quantity <= 0:
        return "rejected"
    quantity = Decimal(str(signal.quantity))

    action = signal.action.upper()

    if action == "BUY":
        cost = fill_price * quantity
        current_balance = Decimal(str(paper_session.current_balance))
        if cost > current_balance:
            return "rejected"

        # Create position
        position = PaperPosition(
            session_id=paper_session_id,
            tenant_id=tenant_id,
            symbol=signal.symbol,
            exchange=signal.exchange,
            side="long",
            quantity=float(quantity),
            avg_entry_price=float(fill_price),
            current_price=float(fill_price),
            unrealized_pnl=0,
        )
        session.add(position)

        # Create trade record
        trade = PaperTrade(
            session_id=paper_session_id,
            tenant_id=tenant_id,
            signal_id=signal_id,
            symbol=signal.symbol,
            exchange=signal.exchange,
            action=action,
            quantity=float(quantity),
            fill_price=float(fill_price),
            commission=0,
            slippage=0,
        )
        session.add(trade)

        # Deduct balance
        paper_session.current_balance = float(current_balance - cost)

        return "filled"

    elif action == "SELL":
        # Find matching open position
        pos_result = await session.execute(
            select(PaperPosition).where(
                PaperPosition.session_id == paper_session_id,
                PaperPosition.symbol == signal.symbol,
                PaperPosition.closed_at.is_(None),
            )
        )
        position = pos_result.scalar_one_or_none()
        if position is None:
            return "rejected"

        # Compute realized PnL
        entry_price = Decimal(str(position.avg_entry_price))
        sell_qty = min(quantity, Decimal(str(position.quantity)))
        realized_pnl = (fill_price - entry_price) * sell_qty

        # Close position
        from datetime import datetime, timezone

        position.closed_at = datetime.now(timezone.utc)
        position.current_price = float(fill_price)
        position.unrealized_pnl = 0

        # Create trade record
        trade = PaperTrade(
            session_id=paper_session_id,
            tenant_id=tenant_id,
            signal_id=signal_id,
            symbol=signal.symbol,
            exchange=signal.exchange,
            action=action,
            quantity=float(sell_qty),
            fill_price=float(fill_price),
            commission=0,
            slippage=0,
            realized_pnl=float(realized_pnl),
        )
        session.add(trade)

        # Add proceeds to balance
        current_balance = Decimal(str(paper_session.current_balance))
        proceeds = fill_price * sell_qty
        paper_session.current_balance = float(current_balance + proceeds)

        return "filled"

    return "rejected"
