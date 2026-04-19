"""Settings proxy — handles /settings/* routes from Gateway.

Gateway routes:
  GET/PUT /settings/{path}  → /settings/{path}

This is a thin wrapper that delegates to the correct handler
based on the settings category path.
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from .helpers import get_user_id
from .preferences import _get_or_create, _to_response, ALL_DEFAULTS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/{path:path}")
async def get_settings(
    path: str, request: Request, session: AsyncSession = Depends(get_session),
):
    user_id = get_user_id(request)
    prefs = await _get_or_create(user_id, session)
    resp = _to_response(prefs)

    if path in ("chat", "agent", "display", "notifications"):
        return {path: resp.preferences.get(path, {})}

    return resp.dict()


@router.put("/{path:path}")
@router.post("/{path:path}")
async def update_settings(
    path: str, request: Request, session: AsyncSession = Depends(get_session),
):
    user_id = get_user_id(request)
    body = await request.json()
    prefs = await _get_or_create(user_id, session)

    if path in ("chat", "agent", "display", "notifications"):
        current = getattr(prefs, path) or {}
        setattr(prefs, path, {**current, **body})
        await session.commit()
        await session.refresh(prefs)
        logger.info(f"Updated settings/{path} for user {user_id}")
        return _to_response(prefs)

    return {"error": f"Unknown settings path: {path}"}
