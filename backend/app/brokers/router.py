import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_tenant_session
from app.brokers.schemas import BrokerConnectionResponse, CreateBrokerConnectionRequest
from app.crypto.encryption import encrypt_credentials
from app.db.models import BrokerConnection

router = APIRouter(prefix="/api/v1/brokers", tags=["brokers"])


@router.post(
    "",
    response_model=BrokerConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_broker_connection(
    body: CreateBrokerConnectionRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    encrypted = encrypt_credentials(tenant_id, body.credentials)

    conn = BrokerConnection(
        tenant_id=tenant_id,
        broker_type=body.broker_type,
        credentials=encrypted,
        is_active=True,
    )
    session.add(conn)
    await session.commit()
    await session.refresh(conn)

    return BrokerConnectionResponse(
        id=conn.id,
        broker_type=conn.broker_type,
        is_active=conn.is_active,
        connected_at=conn.connected_at,
    )


@router.get("", response_model=list[BrokerConnectionResponse])
async def list_broker_connections(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(BrokerConnection).where(BrokerConnection.tenant_id == tenant_id)
    )
    connections = result.scalars().all()
    return [
        BrokerConnectionResponse(
            id=c.id,
            broker_type=c.broker_type,
            is_active=c.is_active,
            connected_at=c.connected_at,
        )
        for c in connections
    ]


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_broker_connection(
    connection_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(BrokerConnection).where(
            BrokerConnection.id == connection_id,
            BrokerConnection.tenant_id == tenant_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Broker connection not found",
        )
    await session.delete(conn)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
