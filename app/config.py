"""Configuration for RG User Service."""

import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://resonant:resonant@shared_postgres:5432/resonant_users",
)

# Internal API secret — services must send this to call /activity/ingest
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

# Cross-service URLs (internal docker network)
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth_service:8000")
BILLING_SERVICE_URL = os.getenv("BILLING_SERVICE_URL", "http://billing_service:8000")
CHAT_SERVICE_URL = os.getenv("CHAT_SERVICE_URL", "http://chat_service:8000")
AGENT_ENGINE_URL = os.getenv("AGENT_ENGINE_URL", "http://agent_engine_service:8000")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://notification_service:8000")
