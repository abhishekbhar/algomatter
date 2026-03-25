import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateBrokerConnectionRequest(BaseModel):
    broker_type: str
    credentials: dict


class BrokerConnectionResponse(BaseModel):
    id: uuid.UUID
    broker_type: str
    is_active: bool
    connected_at: datetime
    # NO credentials in response
