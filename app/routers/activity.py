"""Activity log — aggregated user activity feed.

Supports ingestion from other services and read for dashboard.
Ingest endpoints are guarded by X-Internal-Secret header.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import INTERNAL_API_SECRET
from ..db import get_session
from ..models import ActivityLog
from .helpers import get_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/activity", tags=["activity"])


def _verify_internal(request: Request):
    """Reject calls that don't carry the internal API secret."""
    if not INTERNAL_API_SECRET:
        return  # no secret configured = allow (dev mode)
    token = request.headers.get("x-internal-secret", "")
    if token != INTERNAL_API_SECRET:
        raise HTTPException(status_code=403, detail="Internal endpoint — access denied")


class ActivityEntry(BaseModel):
    source: str
    action: str
    detail: Dict[str, Any] = {}
    user_id: Optional[str] = None
    org_id: Optional[str] = None


class ActivityResponse(BaseModel):
    id: str
    user_id: str
    org_id: Optional[str]
    source: str
    action: str
    detail: Dict[str, Any]
    timestamp: str


@router.get("")
@router.get("/")
async def get_activity(
    request: Request,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    source: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    user_id = get_user_id(request)
    q = select(ActivityLog).where(ActivityLog.user_id == user_id)

    if source:
        q = q.where(ActivityLog.source == source)

    q = q.order_by(ActivityLog.timestamp.desc()).offset(offset).limit(limit)
    result = await session.execute(q)
    activities = result.scalars().all()

    return [
        ActivityResponse(
            id=str(a.id),
            user_id=a.user_id,
            org_id=a.org_id,
            source=a.source,
            action=a.action,
            detail=a.detail or {},
            timestamp=a.timestamp.isoformat(),
        )
        for a in activities
    ]


@router.post("/ingest")
async def ingest_activity(
    entry: ActivityEntry, request: Request, session: AsyncSession = Depends(get_session),
):
    """Internal endpoint — other services POST activity events here."""
    _verify_internal(request)
    user_id = entry.user_id or request.headers.get("x-user-id", "unknown")

    log = ActivityLog(
        user_id=user_id,
        org_id=entry.org_id or request.headers.get("x-org-id"),
        source=entry.source,
        action=entry.action,
        detail=entry.detail,
    )
    session.add(log)
    await session.commit()
    return {"status": "ok"}


@router.post("/ingest/batch")
async def ingest_batch(
    request: Request, session: AsyncSession = Depends(get_session),
):
    """Internal endpoint — bulk ingest activity events."""
    _verify_internal(request)
    body = await request.json()
    entries = body.get("entries", [])
    count = 0
    for e in entries:
        log = ActivityLog(
            user_id=e.get("user_id", "unknown"),
            org_id=e.get("org_id"),
            source=e.get("source", "unknown"),
            action=e.get("action", "unknown"),
            detail=e.get("detail", {}),
        )
        session.add(log)
        count += 1

    await session.commit()
    logger.info(f"Ingested {count} activity entries")
    return {"status": "ok", "count": count}
