"""Organization settings — matches Gateway routes at /orgs/*.

Gateway routes:
  GET/POST /orgs         → /orgs
  GET/PUT  /orgs/{path}  → /orgs/{path}
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import OrgSettings
from .helpers import get_user_id, get_user_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/orgs", tags=["orgs"])


class OrgSettingsResponse(BaseModel):
    org_id: str
    name: Optional[str] = None
    slug: Optional[str] = None
    branding: Dict[str, Any] = {}
    feature_flags: Dict[str, Any] = {}
    default_preferences: Dict[str, Any] = {}
    settings: Dict[str, Any] = {}


class OrgSettingsUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    branding: Optional[Dict[str, Any]] = None
    feature_flags: Optional[Dict[str, Any]] = None
    default_preferences: Optional[Dict[str, Any]] = None
    settings: Optional[Dict[str, Any]] = None


async def _get_or_create(org_id: str, session: AsyncSession) -> OrgSettings:
    result = await session.execute(
        select(OrgSettings).where(OrgSettings.org_id == org_id)
    )
    org = result.scalar_one_or_none()
    if not org:
        org = OrgSettings(org_id=org_id)
        session.add(org)
        await session.commit()
        await session.refresh(org)
    return org


def _to_response(o: OrgSettings) -> OrgSettingsResponse:
    return OrgSettingsResponse(
        org_id=o.org_id,
        name=o.name,
        slug=o.slug,
        branding=o.branding or {},
        feature_flags=o.feature_flags or {},
        default_preferences=o.default_preferences or {},
        settings=o.settings or {},
    )


@router.get("")
@router.get("/")
async def list_orgs(request: Request, session: AsyncSession = Depends(get_session)):
    user_id = get_user_id(request)
    # Return all org settings the user can see (placeholder — will filter by membership)
    result = await session.execute(select(OrgSettings).limit(50))
    orgs = result.scalars().all()
    return [_to_response(o) for o in orgs]


@router.get("/{org_id}/settings")
async def get_org_settings(
    org_id: str, session: AsyncSession = Depends(get_session),
):
    org = await _get_or_create(org_id, session)
    return _to_response(org)


@router.put("/{org_id}/settings")
async def update_org_settings(
    org_id: str, body: OrgSettingsUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
):
    role = get_user_role(request)
    if role not in ("admin", "owner", "superuser"):
        raise HTTPException(status_code=403, detail="Only admins can update org settings")

    org = await _get_or_create(org_id, session)

    if body.name is not None:
        org.name = body.name
    if body.slug is not None:
        org.slug = body.slug
    if body.branding is not None:
        org.branding = {**(org.branding or {}), **body.branding}
    if body.feature_flags is not None:
        org.feature_flags = {**(org.feature_flags or {}), **body.feature_flags}
    if body.default_preferences is not None:
        org.default_preferences = {**(org.default_preferences or {}), **body.default_preferences}
    if body.settings is not None:
        org.settings = {**(org.settings or {}), **body.settings}

    await session.commit()
    await session.refresh(org)
    logger.info(f"Updated org settings for {org_id}")
    return _to_response(org)
