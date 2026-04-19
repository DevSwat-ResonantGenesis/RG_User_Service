from .preferences import router as preferences_router
from .users import router as users_router
from .settings import router as settings_router
from .dashboard import router as dashboard_router
from .orgs import router as orgs_router
from .activity import router as activity_router

__all__ = [
    "preferences_router",
    "users_router",
    "settings_router",
    "dashboard_router",
    "orgs_router",
    "activity_router",
]
