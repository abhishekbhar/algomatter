"""Hosted strategy CRUD API.

Endpoints:
    POST   /api/v1/hosted-strategies                          Create strategy
    GET    /api/v1/hosted-strategies                          List strategies
    GET    /api/v1/hosted-strategies/{id}                     Get strategy
    PUT    /api/v1/hosted-strategies/{id}                     Update strategy
    DELETE /api/v1/hosted-strategies/{id}                     Delete strategy
    POST   /api/v1/hosted-strategies/{id}/upload              Upload code file
    GET    /api/v1/hosted-strategies/{id}/versions             List versions
    GET    /api/v1/hosted-strategies/{id}/versions/{version}   Get version
    POST   /api/v1/hosted-strategies/{id}/versions/{version}/restore  Restore version
    GET    /api/v1/strategy-templates                         List templates
"""

from __future__ import annotations

import ast
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, get_tenant_session
from app.db.models import StrategyCode, StrategyCodeVersion
from app.hosted_strategies.schemas import (
    CreateStrategyRequest,
    StrategyResponse,
    StrategyVersionResponse,
    TemplateResponse,
    UpdateStrategyRequest,
)
from app.hosted_strategies.templates import TEMPLATES

router = APIRouter(prefix="/api/v1/hosted-strategies", tags=["hosted-strategies"])
template_router = APIRouter(prefix="/api/v1/strategy-templates", tags=["strategy-templates"])

MAX_UPLOAD_SIZE = 100 * 1024  # 100 KB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(sc: StrategyCode) -> StrategyResponse:
    return StrategyResponse(
        id=sc.id,
        name=sc.name,
        description=sc.description,
        code=sc.code,
        version=sc.version,
        entrypoint=sc.entrypoint,
        created_at=sc.created_at.isoformat() if sc.created_at else "",
        updated_at=sc.updated_at.isoformat() if sc.updated_at else "",
    )


def _create_version(sc: StrategyCode, tenant_id: uuid.UUID) -> StrategyCodeVersion:
    return StrategyCodeVersion(
        tenant_id=tenant_id,
        strategy_code_id=sc.id,
        version=sc.version,
        code=sc.code,
    )


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_strategy(
    body: CreateStrategyRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    sc = StrategyCode(
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        code=body.code,
        entrypoint=body.entrypoint,
        version=1,
    )
    session.add(sc)
    await session.flush()  # populate sc.id before creating version

    version = _create_version(sc, tenant_id)
    session.add(version)
    await session.commit()
    await session.refresh(sc)

    return _to_response(sc)


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyCode)
        .where(StrategyCode.tenant_id == tenant_id)
        .order_by(StrategyCode.updated_at.desc())
    )
    rows = result.scalars().all()
    return [_to_response(sc) for sc in rows]


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyCode).where(
            StrategyCode.id == strategy_id,
            StrategyCode.tenant_id == tenant_id,
        )
    )
    sc = result.scalar_one_or_none()
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hosted strategy not found",
        )
    return _to_response(sc)


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: uuid.UUID,
    body: UpdateStrategyRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyCode).where(
            StrategyCode.id == strategy_id,
            StrategyCode.tenant_id == tenant_id,
        )
    )
    sc = result.scalar_one_or_none()
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hosted strategy not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    code_changed = "code" in update_data and update_data["code"] != sc.code

    for field, value in update_data.items():
        setattr(sc, field, value)

    if code_changed:
        sc.version += 1
        version = _create_version(sc, tenant_id)
        session.add(version)

    sc.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(sc)

    return _to_response(sc)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyCode).where(
            StrategyCode.id == strategy_id,
            StrategyCode.tenant_id == tenant_id,
        )
    )
    sc = result.scalar_one_or_none()
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hosted strategy not found",
        )
    await session.delete(sc)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------


@router.post("/{strategy_id}/upload", response_model=StrategyResponse)
async def upload_strategy_file(
    strategy_id: uuid.UUID,
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyCode).where(
            StrategyCode.id == strategy_id,
            StrategyCode.tenant_id == tenant_id,
        )
    )
    sc = result.scalar_one_or_none()
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hosted strategy not found",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum size of {MAX_UPLOAD_SIZE // 1024}KB",
        )

    code_text = content.decode("utf-8")

    # Validate that the file contains valid Python
    try:
        ast.parse(code_text)
    except SyntaxError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Python syntax: {exc}",
        )

    sc.code = code_text
    sc.version += 1
    sc.updated_at = datetime.now(UTC)

    version = _create_version(sc, tenant_id)
    session.add(version)
    await session.commit()
    await session.refresh(sc)

    return _to_response(sc)


# ---------------------------------------------------------------------------
# Versioning endpoints
# ---------------------------------------------------------------------------


@router.get("/{strategy_id}/versions", response_model=list[StrategyVersionResponse])
async def list_versions(
    strategy_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    # Verify strategy exists and belongs to tenant
    result = await session.execute(
        select(StrategyCode).where(
            StrategyCode.id == strategy_id,
            StrategyCode.tenant_id == tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hosted strategy not found",
        )

    result = await session.execute(
        select(StrategyCodeVersion)
        .where(
            StrategyCodeVersion.strategy_code_id == strategy_id,
            StrategyCodeVersion.tenant_id == tenant_id,
        )
        .order_by(StrategyCodeVersion.version.desc())
    )
    versions = result.scalars().all()
    return [
        StrategyVersionResponse(
            id=v.id,
            version=v.version,
            code=v.code,
            created_at=v.created_at.isoformat() if v.created_at else "",
        )
        for v in versions
    ]


@router.get(
    "/{strategy_id}/versions/{version_number}",
    response_model=StrategyVersionResponse,
)
async def get_version(
    strategy_id: uuid.UUID,
    version_number: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])
    result = await session.execute(
        select(StrategyCodeVersion).where(
            StrategyCodeVersion.strategy_code_id == strategy_id,
            StrategyCodeVersion.tenant_id == tenant_id,
            StrategyCodeVersion.version == version_number,
        )
    )
    v = result.scalar_one_or_none()
    if not v:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )
    return StrategyVersionResponse(
        id=v.id,
        version=v.version,
        code=v.code,
        created_at=v.created_at.isoformat() if v.created_at else "",
    )


@router.post(
    "/{strategy_id}/versions/{version_number}/restore",
    response_model=StrategyResponse,
)
async def restore_version(
    strategy_id: uuid.UUID,
    version_number: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_tenant_session),
):
    tenant_id = uuid.UUID(current_user["user_id"])

    # Fetch the strategy
    result = await session.execute(
        select(StrategyCode).where(
            StrategyCode.id == strategy_id,
            StrategyCode.tenant_id == tenant_id,
        )
    )
    sc = result.scalar_one_or_none()
    if not sc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Hosted strategy not found",
        )

    # Fetch the old version
    result = await session.execute(
        select(StrategyCodeVersion).where(
            StrategyCodeVersion.strategy_code_id == strategy_id,
            StrategyCodeVersion.tenant_id == tenant_id,
            StrategyCodeVersion.version == version_number,
        )
    )
    old_version = result.scalar_one_or_none()
    if not old_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    # Copy old version's code to current and bump version
    sc.code = old_version.code
    sc.version += 1
    sc.updated_at = datetime.now(UTC)

    new_version = _create_version(sc, tenant_id)
    session.add(new_version)
    await session.commit()
    await session.refresh(sc)

    return _to_response(sc)


# ---------------------------------------------------------------------------
# Templates (no auth required)
# ---------------------------------------------------------------------------


@template_router.get("", response_model=list[TemplateResponse])
async def list_templates():
    return [
        TemplateResponse(
            name=t["name"],
            description=t["description"],
            code=t["code"],
            params=t["params"],
        )
        for t in TEMPLATES
    ]
