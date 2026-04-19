"""User profile CRUD — matches Gateway routes at /users/*.

Gateway routes:
  GET  /users       → /users
  GET  /users/{id}  → /users/{id}
  PUT  /users/{id}  → /users/{id}  (profile update)
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import UserProfile
from .helpers import get_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    timezone: str = "UTC"
    language: str = "en"
    metadata: Dict[str, Any] = {}


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


async def _get_or_create(user_id: str, session: AsyncSession) -> UserProfile:
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        profile = UserProfile(user_id=user_id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    return profile


def _to_response(p: UserProfile) -> ProfileResponse:
    return ProfileResponse(
        id=str(p.id),
        user_id=p.user_id,
        display_name=p.display_name,
        avatar_url=p.avatar_url,
        bio=p.bio,
        timezone=p.timezone,
        language=p.language,
        metadata=p.metadata_ or {},
    )


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(request: Request, session: AsyncSession = Depends(get_session)):
    user_id = get_user_id(request)
    profile = await _get_or_create(user_id, session)
    return _to_response(profile)


@router.get("/{user_id}", response_model=ProfileResponse)
async def get_profile(user_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _to_response(profile)


@router.put("/{user_id}", response_model=ProfileResponse)
async def update_profile(
    user_id: str, body: ProfileUpdate, request: Request,
    session: AsyncSession = Depends(get_session),
):
    caller_id = get_user_id(request)
    if caller_id != user_id:
        role = request.headers.get("x-user-role", "")
        if role not in ("admin", "owner", "superuser"):
            raise HTTPException(status_code=403, detail="Cannot update another user's profile")

    profile = await _get_or_create(user_id, session)

    if body.full_name is not None or body.display_name is not None:
        profile.display_name = body.display_name or body.full_name
    if body.avatar_url is not None:
        profile.avatar_url = body.avatar_url
    if body.bio is not None:
        profile.bio = body.bio
    if body.timezone is not None:
        profile.timezone = body.timezone
    if body.language is not None:
        profile.language = body.language
    if body.metadata is not None:
        profile.metadata_ = {**(profile.metadata_ or {}), **body.metadata}

    await session.commit()
    await session.refresh(profile)
    logger.info(f"Updated profile for user {user_id}")
    return _to_response(profile)
