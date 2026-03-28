import uuid

from pydantic import BaseModel, Field


class CreateStrategyRequest(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    code: str
    entrypoint: str = "Strategy"


class UpdateStrategyRequest(BaseModel):
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    code: str | None = None
    entrypoint: str | None = None


class StrategyResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    code: str
    version: int
    entrypoint: str
    created_at: str
    updated_at: str


class StrategyVersionResponse(BaseModel):
    id: uuid.UUID
    version: int
    code: str
    created_at: str


class TemplateResponse(BaseModel):
    name: str
    description: str
    code: str
    params: dict
