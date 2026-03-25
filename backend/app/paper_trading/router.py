import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_session
from app.db.models import PaperPosition, PaperTrade, PaperTradingSession, Strategy

router = APIRouter(prefix="/api/v1/paper-trading", tags=["paper-trading"])


class CreateSessionRequest(BaseModel):
    strategy_id: uuid.UUID
    capital: float


# ---- POST /sessions ----
@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    body: CreateSessionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    # Verify strategy belongs to tenant
    result = await session.execute(
        select(Strategy).where(
            Strategy.id == body.strategy_id,
            Strategy.tenant_id == tenant_id,
        )
    )
    strategy = result.scalar_one_or_none()
    if strategy is None:
        raise HTTPException(status_code=404, detail="Strategy not found")

    paper_session = PaperTradingSession(
        tenant_id=tenant_id,
        strategy_id=body.strategy_id,
        initial_capital=body.capital,
        current_balance=body.capital,
        status="active",
    )
    session.add(paper_session)
    await session.commit()
    await session.refresh(paper_session)

    return {
        "id": str(paper_session.id),
        "strategy_id": str(paper_session.strategy_id),
        "initial_capital": str(paper_session.initial_capital),
        "current_balance": str(paper_session.current_balance),
        "status": paper_session.status,
        "started_at": paper_session.started_at.isoformat()
        if paper_session.started_at
        else None,
    }


# ---- GET /sessions ----
@router.get("/sessions")
async def list_sessions(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(PaperTradingSession).where(
            PaperTradingSession.tenant_id == tenant_id
        )
    )
    sessions_list = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "strategy_id": str(s.strategy_id),
            "initial_capital": str(s.initial_capital),
            "current_balance": str(s.current_balance),
            "status": s.status,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "stopped_at": s.stopped_at.isoformat() if s.stopped_at else None,
        }
        for s in sessions_list
    ]


# ---- GET /sessions/{id} ----
@router.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(PaperTradingSession).where(
            PaperTradingSession.id == session_id,
            PaperTradingSession.tenant_id == tenant_id,
        )
    )
    paper_session = result.scalar_one_or_none()
    if paper_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch positions
    pos_result = await session.execute(
        select(PaperPosition).where(PaperPosition.session_id == session_id)
    )
    positions = pos_result.scalars().all()

    # Fetch recent trades (last 50)
    trade_result = await session.execute(
        select(PaperTrade)
        .where(PaperTrade.session_id == session_id)
        .order_by(PaperTrade.executed_at.desc())
        .limit(50)
    )
    trades = trade_result.scalars().all()

    return {
        "id": str(paper_session.id),
        "strategy_id": str(paper_session.strategy_id),
        "initial_capital": str(paper_session.initial_capital),
        "current_balance": str(paper_session.current_balance),
        "status": paper_session.status,
        "started_at": paper_session.started_at.isoformat()
        if paper_session.started_at
        else None,
        "stopped_at": paper_session.stopped_at.isoformat()
        if paper_session.stopped_at
        else None,
        "positions": [
            {
                "id": str(p.id),
                "symbol": p.symbol,
                "exchange": p.exchange,
                "side": p.side,
                "quantity": str(p.quantity),
                "avg_entry_price": str(p.avg_entry_price),
                "current_price": str(p.current_price) if p.current_price else None,
                "unrealized_pnl": str(p.unrealized_pnl)
                if p.unrealized_pnl is not None
                else None,
                "opened_at": p.opened_at.isoformat() if p.opened_at else None,
                "closed_at": p.closed_at.isoformat() if p.closed_at else None,
            }
            for p in positions
        ],
        "trades": [
            {
                "id": str(t.id),
                "symbol": t.symbol,
                "exchange": t.exchange,
                "action": t.action,
                "quantity": str(t.quantity),
                "fill_price": str(t.fill_price),
                "commission": str(t.commission),
                "slippage": str(t.slippage),
                "realized_pnl": str(t.realized_pnl)
                if t.realized_pnl is not None
                else None,
                "executed_at": t.executed_at.isoformat() if t.executed_at else None,
            }
            for t in trades
        ],
    }


# ---- POST /sessions/{id}/stop ----
@router.post("/sessions/{session_id}/stop")
async def stop_session(
    session_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(PaperTradingSession).where(
            PaperTradingSession.id == session_id,
            PaperTradingSession.tenant_id == tenant_id,
        )
    )
    paper_session = result.scalar_one_or_none()
    if paper_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    paper_session.status = "stopped"
    paper_session.stopped_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(paper_session)

    return {
        "id": str(paper_session.id),
        "status": paper_session.status,
        "stopped_at": paper_session.stopped_at.isoformat()
        if paper_session.stopped_at
        else None,
    }
