"""User preferences CRUD — matches frontend API at /user/preferences.

Gateway routes:
  GET/PUT/PATCH/DELETE /user/preferences  → /preferences
  PATCH /user/preferences/{category}      → /preferences/{category}
  GET/PUT /preferences                    → /preferences  (legacy)
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import UserPreferences
from .helpers import get_user_id, ALL_DEFAULTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesResponse(BaseModel):
    preferences: Dict[str, Any]
    updated_at: Optional[str] = None


class PreferencesUpdate(BaseModel):
    chat: Optional[Dict[str, Any]] = None
    agent: Optional[Dict[str, Any]] = None
    display: Optional[Dict[str, Any]] = None
    notifications: Optional[Dict[str, Any]] = None


async def _get_or_create(user_id: str, session: AsyncSession) -> UserPreferences:
    result = await session.execute(
        select(UserPreferences).where(UserPreferences.user_id == user_id)
    )
    prefs = result.scalar_one_or_none()
    if not prefs:
        prefs = UserPreferences(
            user_id=user_id,
            chat=ALL_DEFAULTS["chat"].copy(),
            agent=ALL_DEFAULTS["agent"].copy(),
            display=ALL_DEFAULTS["display"].copy(),
            notifications=ALL_DEFAULTS["notifications"].copy(),
        )
        session.add(prefs)
        await session.commit()
        await session.refresh(prefs)
    return prefs


def _to_response(prefs: UserPreferences) -> PreferencesResponse:
    return PreferencesResponse(
        preferences={
            "chat": {**ALL_DEFAULTS["chat"], **(prefs.chat or {})},
            "agent": {**ALL_DEFAULTS["agent"], **(prefs.agent or {})},
            "display": {**ALL_DEFAULTS["display"], **(prefs.display or {})},
            "notifications": {**ALL_DEFAULTS["notifications"], **(prefs.notifications or {})},
        },
        updated_at=prefs.updated_at.isoformat() if prefs.updated_at else None,
    )


@router.get("", response_model=PreferencesResponse)
@router.get("/", response_model=PreferencesResponse)
async def get_preferences(request: Request, session: AsyncSession = Depends(get_session)):
    user_id = get_user_id(request)
    prefs = await _get_or_create(user_id, session)
    return _to_response(prefs)


@router.put("", response_model=PreferencesResponse)
@router.put("/", response_model=PreferencesResponse)
async def update_preferences(
    body: PreferencesUpdate, request: Request, session: AsyncSession = Depends(get_session),
):
    user_id = get_user_id(request)
    prefs = await _get_or_create(user_id, session)

    if body.chat is not None:
        prefs.chat = {**(prefs.chat or {}), **body.chat}
    if body.agent is not None:
        prefs.agent = {**(prefs.agent or {}), **body.agent}
    if body.display is not None:
        prefs.display = {**(prefs.display or {}), **body.display}
    if body.notifications is not None:
        prefs.notifications = {**(prefs.notifications or {}), **body.notifications}

    await session.commit()
    await session.refresh(prefs)
    logger.info(f"Updated preferences for user {user_id}")
    return _to_response(prefs)


@router.patch("/{category}")
async def update_preference_category(
    category: str, request: Request, session: AsyncSession = Depends(get_session),
):
    if category not in ("chat", "agent", "display", "notifications"):
        return {"error": f"Unknown category: {category}"}

    user_id = get_user_id(request)
    body = await request.json()
    prefs = await _get_or_create(user_id, session)

    current = getattr(prefs, category) or {}
    setattr(prefs, category, {**current, **body})
    await session.commit()
    await session.refresh(prefs)
    return _to_response(prefs)


@router.delete("")
@router.delete("/")
async def reset_preferences(request: Request, session: AsyncSession = Depends(get_session)):
    user_id = get_user_id(request)
    prefs = await _get_or_create(user_id, session)
    prefs.chat = ALL_DEFAULTS["chat"].copy()
    prefs.agent = ALL_DEFAULTS["agent"].copy()
    prefs.display = ALL_DEFAULTS["display"].copy()
    prefs.notifications = ALL_DEFAULTS["notifications"].copy()
    await session.commit()
    await session.refresh(prefs)
    logger.info(f"Reset preferences for user {user_id}")
    return _to_response(prefs)
