"""RG User Service — profiles, preferences, org settings, dashboard, activity log."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import engine, Base
from .routers import (
    preferences_router,
    users_router,
    settings_router,
    dashboard_router,
    orgs_router,
    activity_router,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="RG User Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("User Service started — tables ensured")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "user_service"}


@app.get("/")
async def root():
    return {"service": "user_service", "version": "2.0.0"}


@app.get("/api/v1/status")
async def status():
    return {"service": "user_service", "status": "active", "version": "2.0.0"}


app.include_router(preferences_router)
app.include_router(users_router)
app.include_router(settings_router)
app.include_router(dashboard_router)
app.include_router(orgs_router)
app.include_router(activity_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)
