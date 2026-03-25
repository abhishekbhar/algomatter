import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateStrategyRequest(BaseModel):
    name: str
    broker_connection_id: uuid.UUID | None = None
    mode: str = "paper"
    mapping_template: dict | None = None
    rules: dict = {}


class UpdateStrategyRequest(BaseModel):
    name: str | None = None
    broker_connection_id: uuid.UUID | None = None
    mode: str | None = None
    mapping_template: dict | None = None
    rules: dict | None = None
    is_active: bool | None = None


class StrategyResponse(BaseModel):
    id: uuid.UUID
    name: str
    broker_connection_id: uuid.UUID | None
    mode: str
    mapping_template: dict | None
    rules: dict
    is_active: bool
    created_at: datetime
