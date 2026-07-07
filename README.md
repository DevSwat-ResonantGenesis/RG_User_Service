# RG User Service

> **Part of the [ResonantGenesis](https://resonant.dev-swat.com) platform** — User profiles, preferences, org settings, dashboard stats, and activity log.

[![Status: Production](https://img.shields.io/badge/Status-Production-brightgreen.svg)]()
[![License: RG Source Available](https://img.shields.io/badge/License-RG%20Source%20Available-blue.svg)](LICENSE.txt)

---

## What This Service Does

The User Service is the **"how you look & behave"** layer of the platform. It sits between three architectural boundaries:

| Service | Owns | Example |
|---|---|---|
| **RG_Auth** | Identity & security | "Who are you?" — login, JWT, MFA, roles, org memberships |
| **RG_Billing** | Money & credits | "What do you pay?" — subscriptions, credits, usage metering |
| **RG_User_Service** (this) | Profile, preferences, dashboard | "How do you look & behave?" — display name, theme, dashboard widgets |

Without this service, user preferences exist **only in browser localStorage** and are lost if the user switches devices or clears their browser. This service persists them server-side.

---

## Responsibilities

### 1. User Profile (`/users`)
Extended profile data that Auth doesn't own — display name, avatar, bio, timezone, language.
- Auto-creates a profile row on first request (no manual signup step needed).
- `user_id` references the same UUID from `RG_Auth.users.id`.

### 2. User Preferences (`/preferences`)
Per-user settings for the entire frontend experience:
- **Chat**: auto-save, timestamps, provider badges, validity scores, compact mode, font size, sound, keyboard shortcuts
- **Agent**: selected agent hash, team ID, agent mode toggle
- **Display**: theme (dark/light), sidebar collapsed state
- **Notifications**: email enabled, push enabled, digest frequency

The frontend (`ORG_Frontend`) calls `GET /user/preferences` on page load. If the backend is unreachable, it falls back to a localStorage cache. All writes go to both the backend and localStorage simultaneously.

### 3. Org-Scoped Settings (`/orgs`)
Per-organization configuration for multi-tenant support:
- **Branding**: org logo, colors, custom domain (JSONB)
- **Feature flags**: enable/disable features per org (JSONB)
- **Default preferences**: org-wide defaults applied to new members (JSONB)
- Only users with role `admin` or `owner` can modify org settings.

### 4. Dashboard Stats API (`/dashboard`)
Aggregated dashboard data that changes based on the user's **plan tier** and **role**:

| Widget | Free | Developer | Plus | Enterprise | Owner |
|---|---|---|---|---|---|
| Credits & balance | ✅ | ✅ | ✅ | ✅ | ✅ |
| Recent activity feed | ✅ | ✅ | ✅ | ✅ | ✅ |
| Chat conversation stats | ✅ | ✅ | ✅ | ✅ | ✅ |
| Agent stats | — | ✅ | ✅ | ✅ | ✅ |
| Usage breakdown chart | — | — | ✅ | ✅ | ✅ |
| Token history (30d) | — | — | ✅ | ✅ | ✅ |
| Org member management | — | — | — | ✅ | ✅ |
| Platform-wide stats | — | — | — | — | ✅ |

The dashboard router makes **internal HTTP calls** to other services using `asyncio.gather()` — all fetches + the DB query run **in parallel**, so latency = slowest single service, not sum of all.

### 5. Activity Log (`/activity`)
Centralized activity feed aggregated from all services:
- **Sources**: `auth` (logins), `billing` (credit usage), `chat` (messages), `agent_engine` (agent runs)
- Other services push events via `POST /activity/ingest` (internal, **guarded by `X-Internal-Secret` header**).
- Supports batch ingestion via `POST /activity/ingest/batch` (same guard).
- When `INTERNAL_API_SECRET` env var is set, callers must send `X-Internal-Secret: <value>` or get 403.

---

## Architecture & Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ORG_Frontend (React)                        │
│                                                                     │
│  useUserPreferences.ts ──→ GET/PUT /user/preferences                │
│  NewUserDashboard.tsx  ──→ GET /dashboard                           │
│  Profile tab           ──→ PUT /users/{id}                          │
│  Settings pages        ──→ GET/PUT /settings/{path}                 │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ HTTPS (resonant.dev-swat.com)
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       RG_Gateway (FastAPI proxy)                    │
│                                                                     │
│  /user/preferences/*  ──proxy──→  user_service:8000/preferences/*   │
│  /users/*             ──proxy──→  user_service:8000/users/*          │
│  /settings/*          ──proxy──→  user_service:8000/settings/*       │
│  /preferences/*       ──proxy──→  user_service:8000/preferences/*    │
│  /orgs/*              ──proxy──→  user_service:8000/orgs/*            │
│  /admin/*             ──proxy──→  user_service:8000/admin/*           │
│                                                                     │
│  Injects headers: x-user-id, x-org-id, x-user-role, x-user-plan   │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ Docker internal network
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    RG_User_Service (this service)                    │
│                         Port 8000                                   │
│                                                                     │
│  routers/preferences.py  ── /preferences      (CRUD)                │
│  routers/users.py        ── /users             (profile CRUD)       │
│  routers/settings.py     ── /settings/{path}   (delegates to prefs) │
│  routers/dashboard.py    ── /dashboard          (tier-aware stats)  │
│  routers/orgs.py         ── /orgs              (org settings)       │
│  routers/activity.py     ── /activity          (log feed + ingest)  │
│                                                                     │
│  Dashboard router fetches from:                                     │
│    ├── RG_Auth         (auth_service:8000)    → login stats, orgs   │
│    ├── RG_Billing      (billing_service:8000) → credits, usage      │
│    ├── RG_Chat         (chat_service:8000)    → conversation stats  │
│    └── RG_Agent_Engine (agent_engine:8000)    → agent run stats     │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│              PostgreSQL (DigitalOcean Managed Database)              │
│              resonant-db / defaultdb                                │
│                                                                     │
│  Tables (auto-created on startup):                                  │
│    user_profiles      — 1 row per user                              │
│    user_preferences   — 1 row per user (JSONB columns)              │
│    org_settings       — 1 row per organization                      │
│    activity_log       — append-only event log                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Dependencies & Connections

### Upstream (who calls this service)

| Caller | How | What it calls |
|---|---|---|
| **ORG_Frontend** | Via Gateway HTTPS proxy | `/user/preferences`, `/users/{id}`, `/settings/*`, `/dashboard` |
| **RG_Gateway** | HTTP proxy on Docker network | All routes — adds `x-user-id`, `x-org-id`, `x-user-role`, `x-user-plan` headers |

### Downstream (what this service calls)

| Service | URL (Docker internal) | Why |
|---|---|---|
| **RG_Auth** | `http://auth_service:8000` | Dashboard: login stats, org member list, platform stats (owner) |
| **RG_Billing** | `http://billing_service:8000` | Dashboard: credits, usage breakdown, token history |
| **RG_Chat** | `http://chat_service:8000` | Dashboard: conversation count, chat stats |
| **RG_Agent_Engine** | `http://agent_engine_service:8000` | Dashboard: agent run stats (developer+ tiers) |
| **PostgreSQL** | `DATABASE_URL` env var | All persistent data (profiles, preferences, org settings, activity log) |

### Services that push TO this service (internal)

| Service | Endpoint | What they push |
|---|---|---|
| **RG_Auth** | `POST /activity/ingest` | Login events, MFA events |
| **RG_Billing** | `POST /activity/ingest` | Credit usage, subscription changes |
| **RG_Chat** | `POST /activity/ingest` | Message counts, conversation events |
| **RG_Agent_Engine** | `POST /activity/ingest` | Agent execution events |

### No dependency on

| Service | Why |
|---|---|
| **RG_Memory** | Memory is per-conversation, not per-user-profile |
| **RG_TrainingNet_Mining** | Mining is standalone, doesn't affect user dashboard yet |
| **RG_DSID_Blockchain** | Chain data is accessed through its own dashboard |
| **RG_IDE / RG_Axtention_IDE** | IDE has its own session, doesn't call user service |

---

## Database Schema

### `user_profiles`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Auto-generated |
| `user_id` | String(64) | **FK reference to RG_Auth `users.id`** (unique) |
| `display_name` | String(255) | Nullable |
| `avatar_url` | String(1024) | Nullable |
| `bio` | Text | Nullable |
| `timezone` | String(64) | Default: "UTC" |
| `language` | String(16) | Default: "en" |
| `metadata` | JSONB | Extensible key-value store |
| `created_at` | Timestamp | Auto |
| `updated_at` | Timestamp | Auto |

### `user_preferences`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Auto-generated |
| `user_id` | String(64) | **FK reference to RG_Auth `users.id`** (unique) |
| `chat` | JSONB | `{auto_save, show_timestamps, font_size, ...}` |
| `agent` | JSONB | `{selected_agent_hash, agent_mode, ...}` |
| `display` | JSONB | `{theme, sidebar_collapsed}` |
| `notifications` | JSONB | `{email_enabled, push_enabled, digest_frequency}` |
| `created_at` | Timestamp | Auto |
| `updated_at` | Timestamp | Auto |

### `org_settings`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Auto-generated |
| `org_id` | String(64) | **FK reference to RG_Auth `organizations.id`** (unique) |
| `name` | String(255) | Org display name |
| `slug` | String(128) | URL slug |
| `branding` | JSONB | `{logo_url, primary_color, ...}` |
| `feature_flags` | JSONB | `{enable_agents, enable_mining, ...}` |
| `default_preferences` | JSONB | Org-wide defaults for new users |
| `settings` | JSONB | General org config |
| `created_at` | Timestamp | Auto |
| `updated_at` | Timestamp | Auto |

### `activity_log`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Auto-generated |
| `user_id` | String(64) | Who did it |
| `org_id` | String(64) | In which org (nullable) |
| `source` | String(32) | `auth`, `billing`, `chat`, `agent_engine` |
| `action` | String(128) | `login`, `credit_used`, `message_sent`, `agent_run` |
| `detail` | JSONB | Event-specific payload |
| `timestamp` | Timestamp | Auto, indexed with user_id |

---

## API Routes

### Preferences (`/preferences`)
| Method | Path | Description |
|---|---|---|
| GET | `/preferences` | Get all preferences (auto-creates with defaults if none exist) |
| PUT | `/preferences` | Update preferences (merge with existing) |
| PATCH | `/preferences/{category}` | Update single category: `chat`, `agent`, `display`, `notifications` |
| DELETE | `/preferences` | Reset all preferences to defaults |

### Users (`/users`)
| Method | Path | Description |
|---|---|---|
| GET | `/users/me` | Get current user's profile (from `x-user-id` header) |
| GET | `/users/{user_id}` | Get profile by user ID |
| PUT | `/users/{user_id}` | Update profile (only self or admin/owner) |

### Settings (`/settings`)
| Method | Path | Description |
|---|---|---|
| GET | `/settings/{path}` | Get settings by category name |
| PUT/POST | `/settings/{path}` | Update settings by category name |

### Dashboard (`/dashboard`)
| Method | Path | Description |
|---|---|---|
| GET | `/dashboard` | Tier-aware aggregated stats (calls Auth, Billing, Chat, AgentEngine) |
| GET | `/dashboard/widgets` | List of available widgets for current user's tier |

### Organizations (`/orgs`)
| Method | Path | Description |
|---|---|---|
| GET | `/orgs` | List all org settings |
| GET | `/orgs/{org_id}/settings` | Get settings for specific org |
| PUT | `/orgs/{org_id}/settings` | Update org settings (admin/owner only) |

### Activity (`/activity`)
| Method | Path | Description |
|---|---|---|
| GET | `/activity` | Get activity log (supports `?limit=`, `?offset=`, `?source=` filters) |
| POST | `/activity/ingest` | Internal: ingest single event (requires `X-Internal-Secret` header) |
| POST | `/activity/ingest/batch` | Internal: bulk ingest events (requires `X-Internal-Secret` header) |

### System
| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/` | Service info |
| GET | `/api/v1/status` | Status endpoint |

---

## Gateway Header Contract

The Gateway injects these headers on every proxied request. This service reads them to identify the user without needing its own auth:

| Header | Source | Example | Used by |
|---|---|---|---|
| `x-user-id` | Gateway (from JWT) | `a1b2c3d4-...` | All routers — identifies the user |
| `x-org-id` | Gateway (from JWT) | `org-uuid-...` | Dashboard, org settings |
| `x-user-role` | Gateway (from JWT/org membership) | `owner`, `admin`, `viewer` | Dashboard tier gating, org settings write permission |
| `x-user-plan` | Gateway (from Billing lookup) | `free`, `developer`, `plus`, `enterprise` | Dashboard widget visibility |
| `authorization` | Client (JWT Bearer token) | `Bearer eyJ...` | Forwarded to downstream services |

---

## File Structure

```
RG_User_Service/
├── Dockerfile                    # Python 3.11-slim, pip install, uvicorn
├── LICENSE.txt
├── README.md                     # This file
├── requirements.txt              # fastapi, uvicorn, sqlalchemy, asyncpg, httpx, pydantic
├── alembic.ini                   # Alembic config (uses DATABASE_URL env override)
├── alembic/
│   ├── env.py                    # Async migration runner
│   ├── script.py.mako            # Migration template
│   └── versions/
│       └── 001_initial_schema.py # Baseline migration (4 tables)
└── app/
    ├── __init__.py
    ├── config.py                 # DATABASE_URL + cross-service URLs (env vars)
    ├── db.py                     # Async SQLAlchemy engine, session factory, Base
    ├── main.py                   # FastAPI app, startup (create tables), mount all routers
    ├── models.py                 # 4 tables: user_profiles, user_preferences, org_settings, activity_log
    └── routers/
        ├── __init__.py           # Re-exports all routers
        ├── helpers.py            # get_user_id(), get_org_id(), get_user_role(), get_user_plan(), default prefs
        ├── preferences.py        # /preferences — CRUD, auto-create, merge-on-update
        ├── users.py              # /users — profile CRUD, auto-create on first GET
        ├── settings.py           # /settings/{path} — thin wrapper delegating to preferences
        ├── dashboard.py          # /dashboard — tier-aware aggregation from 4 services
        ├── orgs.py               # /orgs — org settings CRUD, admin-gated writes
        └── activity.py           # /activity — log feed + ingest endpoints
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...shared_postgres.../resonant_users` | Primary database connection |
| `AUTH_SERVICE_URL` | `http://auth_service:8000` | RG_Auth service URL (dashboard fetches) |
| `BILLING_SERVICE_URL` | `http://billing_service:8000` | RG_Billing service URL (dashboard fetches) |
| `CHAT_SERVICE_URL` | `http://chat_service:8000` | RG_Chat service URL (dashboard fetches) |
| `AGENT_ENGINE_URL` | `http://agent_engine_service:8000` | RG_Agent_Engine service URL (dashboard fetches) |
| `NOTIFICATION_SERVICE_URL` | `http://notification_service:8000` | RG_Notifications (reserved for future use) |
| `INTERNAL_API_SECRET` | *(empty = allow all)* | Shared secret for `/activity/ingest` endpoints. Set in production! |

---

## Deployment

- **Container name**: `user_service`
- **Port**: 8000
- **Server path**: `/home/deploy/RG_User_Service`
- **Docker network**: `genesis2026_production_backend_app-network`
- **Database**: DigitalOcean Managed PostgreSQL (`resonant-db`) — shared DB, own tables
- **Tables**: Auto-created on startup via `Base.metadata.create_all()` (Alembic also configured for future migrations)
- **Health check**: `GET /health` every 30s
- **Restart policy**: `unless-stopped`

### Docker Compose entry (in `RG_core/docker-compose.unified.yml`)
```yaml
user_service:
  build:
    context: /home/deploy/RG_User_Service
    dockerfile: Dockerfile
  container_name: user_service
  env_file:
    - ./.env.production
  environment:
    DATABASE_URL: ${USER_DATABASE_URL}
  networks:
    - app-network
  restart: unless-stopped
```

---

## Quick Start (local development)

```bash
cd RG_User_Service
pip install -r requirements.txt

# Set DATABASE_URL to your local postgres
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/resonant_users"

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

**Organization**: [DevSwat-ResonantGenesis](https://github.com/DevSwat-ResonantGenesis) | **Platform**: [resonant.dev-swat.com](https://resonant.dev-swat.com)
