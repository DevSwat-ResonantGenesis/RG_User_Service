"""Dashboard stats API — aggregated per-user/org metrics.

Pulls data from Auth, Billing, Chat, AgentEngine **in parallel**
and returns tier-appropriate dashboard payloads.

Tiers: free, developer, plus, enterprise, owner
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import (
    AUTH_SERVICE_URL,
    BILLING_SERVICE_URL,
    CHAT_SERVICE_URL,
    AGENT_ENGINE_URL,
)
from ..db import get_session
from ..models import ActivityLog
from .helpers import get_user_id, get_user_plan, get_user_role, get_org_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_HTTP_TIMEOUT = 5.0


async def _fetch_json(client: httpx.AsyncClient, url: str, headers: dict) -> Optional[Dict]:
    try:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"Dashboard fetch failed: {url} → {e}")
    return None


def _forward_headers(request: Request) -> dict:
    return {
        "x-user-id": request.headers.get("x-user-id", ""),
        "x-org-id": request.headers.get("x-org-id", ""),
        "x-user-role": request.headers.get("x-user-role", ""),
        "authorization": request.headers.get("authorization", ""),
    }


@router.get("")
@router.get("/")
async def get_dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    user_id = get_user_id(request)
    plan = get_user_plan(request)
    role = get_user_role(request)
    org_id = get_org_id(request)
    headers = _forward_headers(request)

    sections: Dict[str, Any] = {
        "tier": plan,
        "role": role,
        "org_id": org_id or None,
    }

    # Build all fetch tasks based on tier, then fire them in parallel
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        tasks: Dict[str, Any] = {}

        # All tiers
        tasks["credits"] = _fetch_json(client, f"{BILLING_SERVICE_URL}/billing/credits", headers)
        tasks["chat_stats"] = _fetch_json(client, f"{CHAT_SERVICE_URL}/api/v1/conversations/stats", headers)

        # Developer+
        if plan in ("developer", "plus", "enterprise", "owner"):
            tasks["agent_stats"] = _fetch_json(client, f"{AGENT_ENGINE_URL}/agents/stats", headers)

        # Plus+
        if plan in ("plus", "enterprise", "owner"):
            tasks["usage_breakdown"] = _fetch_json(client, f"{BILLING_SERVICE_URL}/billing/dashboard/me/breakdown", headers)
            tasks["token_history"] = _fetch_json(client, f"{BILLING_SERVICE_URL}/billing/usage/tokens/history?days=30", headers)

        # Enterprise/owner
        if plan in ("enterprise", "owner") or role in ("admin", "owner"):
            tasks["org_members"] = _fetch_json(client, f"{AUTH_SERVICE_URL}/auth/orgs/members", headers)

        # Owner only
        if role == "owner" or plan == "owner":
            tasks["platform_stats"] = _fetch_json(client, f"{AUTH_SERVICE_URL}/admin/stats", headers)

        # DB query for recent activity runs concurrently with HTTP fetches
        async def _get_activity():
            result = await session.execute(
                select(ActivityLog)
                .where(ActivityLog.user_id == user_id)
                .order_by(ActivityLog.timestamp.desc())
                .limit(20)
            )
            return [
                {
                    "source": a.source,
                    "action": a.action,
                    "detail": a.detail,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in result.scalars().all()
            ]

        tasks["recent_activity"] = _get_activity()

        # Fire everything in parallel
        keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for key, result in zip(keys, results):
            if isinstance(result, Exception):
                logger.warning(f"Dashboard section '{key}' failed: {result}")
                sections[key] = None
            else:
                sections[key] = result

    return sections


@router.get("/widgets")
async def get_dashboard_widgets(request: Request):
    """Return the list of dashboard widgets available for this user's tier."""
    plan = get_user_plan(request)
    role = get_user_role(request)

    widgets: List[Dict[str, Any]] = [
        {"id": "credits", "label": "Credits", "tier": "free"},
        {"id": "recent_activity", "label": "Recent Activity", "tier": "free"},
        {"id": "chat_stats", "label": "Chat Stats", "tier": "free"},
    ]

    if plan in ("developer", "plus", "enterprise", "owner"):
        widgets.append({"id": "agent_stats", "label": "Agent Stats", "tier": "developer"})

    if plan in ("plus", "enterprise", "owner"):
        widgets.extend([
            {"id": "usage_breakdown", "label": "Usage Breakdown", "tier": "plus"},
            {"id": "token_history", "label": "Token History (30d)", "tier": "plus"},
        ])

    if plan in ("enterprise", "owner") or role in ("admin", "owner"):
        widgets.append({"id": "org_members", "label": "Organization Members", "tier": "enterprise"})

    if role == "owner" or plan == "owner":
        widgets.append({"id": "platform_stats", "label": "Platform Stats", "tier": "owner"})

    return {"widgets": widgets, "tier": plan, "role": role}
