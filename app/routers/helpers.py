"""Shared helpers for User Service routers."""

from fastapi import Request, HTTPException


def get_user_id(request: Request) -> str:
    """Extract user_id from gateway-injected header."""
    user_id = request.headers.get("x-user-id", "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def get_org_id(request: Request) -> str:
    """Extract org_id from gateway-injected header (optional)."""
    return request.headers.get("x-org-id", "").strip()


def get_user_role(request: Request) -> str:
    """Extract user role from gateway-injected header."""
    return request.headers.get("x-user-role", "viewer").strip()


def get_user_plan(request: Request) -> str:
    """Extract plan tier from gateway-injected header."""
    return request.headers.get("x-user-plan", "free").strip()


DEFAULT_CHAT_PREFS = {
    "auto_save": True,
    "show_timestamps": True,
    "show_provider_badges": True,
    "show_validity_scores": False,
    "compact_mode": False,
    "font_size": "medium",
    "input_auto_resize": True,
    "sound_notifications": False,
    "keyboard_shortcuts": True,
    "focus_highlights": True,
    "split_view": False,
    "split_width": 50,
}

DEFAULT_AGENT_PREFS = {
    "selected_agent_hash": None,
    "selected_team_id": None,
    "agent_mode": False,
}

DEFAULT_DISPLAY_PREFS = {
    "theme": "dark",
    "sidebar_collapsed": False,
}

DEFAULT_NOTIFICATION_PREFS = {
    "email_enabled": True,
    "push_enabled": True,
    "digest_frequency": "daily",
}

ALL_DEFAULTS = {
    "chat": DEFAULT_CHAT_PREFS,
    "agent": DEFAULT_AGENT_PREFS,
    "display": DEFAULT_DISPLAY_PREFS,
    "notifications": DEFAULT_NOTIFICATION_PREFS,
}
