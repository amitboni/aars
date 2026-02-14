# Agent Activation & Retention System (AARS)
# Phase 4: Technical Design — Claude Code Project Specification

## Purpose

This document is the COMPLETE specification for building AARS. It is designed to be fed directly to Claude Code. Every section is implementable. Every type is concrete. Every service boundary is explicit. The build sequence at the end defines exactly what to implement first.

References:
- Phase 1-2: `domain-foundation.md` (entities, types, state machines, signals, taxonomies)
- Phase 3: `system-behavior-design.md` (conversation flows, ADM experience, decision rules)

---

## 4.1 Architecture Decision: Modular Monolith

**We are NOT building microservices.** We are building a modular monolith — a single deployable application with clear internal module boundaries that can be extracted into services later if needed.

Why:
- Startup speed: one repo, one deploy, one database, simple debugging
- Claude Code works best with a single coherent codebase
- Premature microservices kill startups
- Module boundaries are enforced by code structure, not network calls

The monolith has internal modules that communicate through:
- Direct function calls (within the same process)
- An internal event bus (for decoupled signal processing)
- Shared database with schema-level separation

When a module needs to become a service later, the event bus becomes Kafka and function calls become HTTP/gRPC. The code structure makes this migration straightforward.

```
┌─────────────────────────────────────────────────────────┐
│                    AARS Monolith                          │
│                                                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │  API     │ │  Signal  │ │ Decision │ │ Channel  │   │
│  │  Layer   │ │  Engine  │ │  Engine  │ │ Services │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘   │
│       │            │            │            │           │
│  ┌────┴────────────┴────────────┴────────────┴─────┐    │
│  │              Internal Event Bus                   │    │
│  │         (in-process, upgradable to Kafka)        │    │
│  └────┬────────────┬────────────┬────────────┬─────┘    │
│       │            │            │            │           │
│  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌──┴───────┐  │
│  │  Tenant  │ │  Agent   │ │ Playbook │ │ Training │  │
│  │  Module  │ │  Module  │ │  Module  │ │  Module  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                           │
│  ┌───────────────────────────────────────────────────┐   │
│  │               Data Layer (PostgreSQL + Redis)      │   │
│  └───────────────────────────────────────────────────┘   │
│                                                           │
│  ┌───────────────────────────────────────────────────┐   │
│  │         Background Workers (Celery + Redis)        │   │
│  └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         │                    │
    ┌────┴────┐          ┌────┴────┐
    │ Voice AI│          │WhatsApp │
    │Provider │          │Provider │
    │(Vibrium/│          │(Meta    │
    │  mock)  │          │Cloud API│
    └─────────┘          └─────────┘
```

---

## 4.2 Technology Stack

```yaml
Runtime:
  language: Python 3.12
  framework: FastAPI 0.110+
  async: "Yes — uvicorn with async SQLAlchemy for API, sync SQLAlchemy for Celery"

Database:
  primary: PostgreSQL 16
  extensions: [uuid-ossp, pgcrypto, btree_gist]
  orm: SQLAlchemy 2.0 (async for API, sync for Celery workers)
  migrations: Alembic
  drivers:
    async: asyncpg (for FastAPI request handlers)
    sync: psycopg2-binary (for Celery tasks)
  
Cache & Queues:
  cache: Redis 7
  task_queue: Celery 5.3 with Redis broker
  rate_limiting: Redis (sliding window)
  
Search:
  full_text: PostgreSQL tsvector (built-in, no Elasticsearch initially)

Authentication:
  jwt: PyJWT
  password_hashing: bcrypt via passlib
  
API:
  rest: FastAPI with Pydantic v2 models
  docs: Auto-generated OpenAPI (Swagger)
  
External Integrations:
  voice_ai: "Provider-abstracted (Vibrium — primary, mock for testing)"
  whatsapp: "Provider-abstracted (Meta Cloud API — primary, mock for testing)"
  sms: "Provider-abstracted (MSG91, Twilio, or mock)"
  storage: "S3-compatible (AWS S3, MinIO for local dev)"
  
Development:
  containerization: Docker + docker-compose
  linting: ruff
  formatting: black
  type_checking: mypy (strict)
  testing: pytest + pytest-asyncio
  
Frontend (dashboards only — built AFTER backend is stable):
  framework: "React 18 + Next.js 14"
  styling: "Tailwind CSS"
  charts: "Recharts"
```

---

## 4.3 Project Structure

```
aars/
├── README.md
├── CLAUDE.md                          # Claude Code instructions file
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile
├── .env.example                       # Template for environment variables
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│
├── config/
│   ├── __init__.py
│   ├── settings.py                    # App settings (from env vars via pydantic-settings)
│   ├── database.py                    # DB engines + session factories (async AND sync)
│   ├── redis.py                       # Redis connection
│   ├── celery_app.py                  # Celery configuration
│   └── logging.py                     # Structured logging setup
│
├── core/                              # Shared kernel — used by all modules
│   ├── __init__.py
│   ├── types.py                       # Semantic domain types (Pydantic)
│   ├── enums.py                       # All enums (lifecycle states, channels, etc.)
│   ├── events.py                      # Internal event bus
│   ├── exceptions.py                  # Domain exceptions
│   ├── security.py                    # Auth, JWT, password hashing
│   ├── tenant_context.py             # Tenant context propagation
│   ├── permissions.py                 # RBAC engine
│   ├── encryption.py                  # Field-level encryption (PAN, Aadhaar)
│   └── base_models.py                # SQLAlchemy base, common mixins
│
├── modules/
│   ├── tenant/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── router.py
│   │   └── config_defaults.py
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── router.py
│   │   ├── lifecycle.py
│   │   └── understanding.py
│   │
│   ├── signal/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── router.py
│   │   ├── processor.py
│   │   └── handlers/
│   │       ├── __init__.py
│   │       ├── voice_signals.py
│   │       ├── whatsapp_signals.py
│   │       ├── business_signals.py
│   │       ├── adm_signals.py
│   │       └── system_signals.py
│   │
│   ├── conversation/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── router.py
│   │
│   ├── playbook/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── router.py
│   │   ├── executor.py
│   │   ├── condition_evaluator.py     # Safe playbook branching evaluator
│   │   └── default_playbooks.py
│   │
│   ├── decision/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── engine.py
│   │   ├── rules.py
│   │   ├── constraints.py
│   │   └── tasks.py
│   │
│   ├── training/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── router.py
│   │   └── pathway.py
│   │
│   ├── channel/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── rate_limiter.py            # Outbound rate limiting
│   │   ├── voice/
│   │   │   ├── __init__.py
│   │   │   ├── provider.py
│   │   │   ├── vibrium.py              # Vibrium integration (webhook-driven)
│   │   │   ├── mock.py
│   │   │   ├── conversation_flows.py
│   │   │   └── nlu.py
│   │   ├── whatsapp/
│   │   │   ├── __init__.py
│   │   │   ├── provider.py
│   │   │   ├── meta_cloud.py            # Meta Cloud API integration (primary)
│   │   │   ├── mock.py
│   │   │   ├── templates.py
│   │   │   ├── bot.py
│   │   │   └── webhook.py
│   │   └── sms/
│   │       ├── __init__.py
│   │       ├── provider.py
│   │       └── mock.py
│   │
│   ├── adm/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── router.py
│   │   ├── briefing.py
│   │   ├── alerts.py
│   │   └── action_logger.py
│   │
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── pas_adapter.py
│   │   ├── lms_adapter.py
│   │   ├── commission_adapter.py
│   │   ├── batch_processor.py
│   │   └── webhook_receiver.py
│   │
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   ├── router.py
│   │   └── reports.py
│   │
│   └── audit/
│       ├── __init__.py
│       ├── models.py
│       ├── service.py
│       └── middleware.py
│
├── tasks/                             # Celery task definitions
│   ├── __init__.py
│   ├── signal_processing.py
│   ├── decision_engine.py
│   ├── playbook_execution.py
│   ├── adm_briefing.py
│   ├── integration_sync.py
│   └── analytics_aggregation.py
│
├── api/
│   ├── __init__.py
│   ├── app.py                         # FastAPI app factory
│   ├── middleware.py                  # Tenant context, auth, logging, CORS
│   ├── dependencies.py               # FastAPI dependency injection
│   └── health.py
│
├── seeds/
│   ├── platform_defaults.py
│   ├── default_playbooks.py
│   ├── default_training.py
│   ├── dormancy_taxonomy.py
│   └── demo_tenant.py
│
├── tests/
│   ├── conftest.py
│   ├── factories.py
│   ├── test_core/
│   ├── test_modules/
│   │   ├── test_agent/
│   │   ├── test_signal/
│   │   ├── test_decision/
│   │   └── ...
│   └── test_integration/
│
└── scripts/
    ├── seed_db.py
    ├── create_tenant.py
    └── simulate_signals.py
```

---

## 4.4 CLAUDE.md (Claude Code Instructions)

```markdown
# AARS — Agent Activation & Retention System

## What This Project Is
A multi-tenant SaaS platform that helps Indian life insurance companies retain and
reactivate their agent workforce using Voice AI, WhatsApp, and predictive analytics.

## Architecture
Modular monolith in Python (FastAPI). Modules in `modules/`. Each module has:
models.py (SQLAlchemy), schemas.py (Pydantic), service.py (logic), router.py (API).

## Key Principles
1. EVERY table has tenant_id. No exceptions. RLS enforced at DB level.
2. ALL state derived from Signal Stream. Never set lifecycle states directly.
3. ALL thresholds/taxonomies/playbooks are tenant-configurable with platform defaults.
4. External integrations behind abstract provider interfaces with mock implementations.
5. Semantic types from core/types.py — use everywhere, never raw strings for domain values.

## Commands
- docker-compose up -d — Start postgres, redis, minio
- alembic upgrade head — Run migrations
- python scripts/seed_db.py — Seed platform defaults
- uvicorn api.app:create_app --factory --reload — Dev server
- celery -A config.celery_app worker -l info — Background workers
- celery -A config.celery_app beat -l info — Scheduler
- pytest — Tests
- ruff check . — Lint
- mypy . — Type check

## Schema Strategy
SQLAlchemy models are the schema source of truth. NEVER write raw SQL for table creation.
Generate Alembic migrations from models. Then manually add RLS policies in migration files:
```sql
ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table_name}
    USING (tenant_id = current_setting('app.tenant_id')::uuid);
```
Do this for EVERY table that uses TenantScopedMixin.
Exception: signals table uses service-layer tenant filtering, NOT RLS (performance reasons).

## Database Sessions — CRITICAL
- FastAPI handlers: use ASYNC sessions (asyncpg) via `get_db` dependency
- Celery tasks: use SYNC sessions (psycopg2) via `sync_session_factory`
- NEVER use async sessions inside Celery tasks — Celery workers are synchronous
- Both session factories are in config/database.py

## API Pagination
All list endpoints use cursor-based pagination:
```
GET /api/v1/agents?limit=50&cursor=<opaque_cursor>

Response: { "data": [...], "next_cursor": "...", "has_more": true, "total_count": 12345 }
```
Default limit: 50. Max limit: 200.
For agents: support filtering by lifecycle_state, adm_id, region_node_id.
For signals: support filtering by signal_type, agent_id, date range.

## Error Response Format
All errors return:
```json
{
  "error": {
    "code": "AGENT_NOT_FOUND",
    "message": "Agent with id {id} not found in this tenant",
    "details": {}
  }
}
```
HTTP status codes: 400 validation, 401 auth, 403 forbidden, 404 not found, 409 conflict, 422 unprocessable, 500 server.

## Webhook Security
All webhook endpoints MUST verify the provider's signature before processing:
- WhatsApp (Meta Cloud API): Verify X-Hub-Signature-256 header using HMAC-SHA256 with APP_SECRET
- WhatsApp webhook verification: Handle GET requests with hub.verify_token for Meta setup
- Voice AI (Vibrium): Verify provider-specific signature header
- Webhook secret stored per-tenant in tenant config
- If verification fails: return 401, log attempt, do NOT process payload

## Signal Processing — Dual Path
Signals are processed through TWO paths:
1. FAST PATH: When a signal originates in-process (webhook handler), publish SignalReceived
   event on internal event bus → handler immediately runs lifecycle check + understanding update.
2. SLOW PATH: Celery task polls for signals where processed=false every 60 seconds.
   Catches anything missed by fast path (batch imports, external signals, crash recovery).
Both paths are idempotent. Processing a signal twice is harmless.

## Playbook Branching
Playbook step conditions are simple key-value matches evaluated against a context dict.
Use a SAFE evaluator — NEVER use eval(). Implement with straightforward if/elif matching:
```python
context = {"outcome": "answered", "sentiment": "positive", "quiz_score": 80}
# Parse conditions into rules:
# [{"field": "outcome", "op": "==", "value": "answered"}, ...]
```
Keep it simple. This is NOT a general-purpose rule engine.
Implement in modules/playbook/condition_evaluator.py.

## Module Dependency Rules
Modules can depend on:
- core/ — Always allowed
- modules/signal — Most modules read signals
- modules/agent — Most modules reference agents

Modules MUST NOT:
- Import from modules/channel inside modules/decision (use events instead)
- Import from modules/analytics inside any other module
- Create circular dependencies between modules

## Soft Delete
Tables that need soft delete: agents, users, playbooks, training_modules.
Add `deleted_at TIMESTAMPTZ NULL` column. Non-null = soft-deleted.
All queries exclude soft-deleted records by default via a SQLAlchemy query mixin.
Never truly DELETE rows in these tables.

## Testing Patterns
Every module must have tests for:
1. Happy path CRUD operations
2. Tenant isolation (create in Tenant A, query as Tenant B → empty)
3. Input validation (invalid phone numbers, missing required fields)
4. Signal emission (operations that should produce signals DO produce them)

Use factories.py for test data: `agent = AgentFactory(tenant_id=tenant.id, lifecycle_state="dormant")`

## Common Gotchas
1. ALWAYS filter by tenant_id in queries, even with RLS enabled (belt + suspenders)
2. Signal table uses VARCHAR for signal_type, not a DB enum — enums evolve but DB columns don't
3. JSONB fields (config, payload, context) should have Pydantic schemas for validation
   at the application layer even though Postgres stores them as free-form JSON
4. When emitting a signal, ALWAYS emit through SignalService.emit() — never insert
   directly into the signals table. The service handles event publishing and processing.
5. Celery tasks must be idempotent. Use the idempotency_key on signals to detect duplicates.
6. All timestamps are UTC in the database. Convert to tenant timezone only at API response
   serialization or in WhatsApp message formatting.
7. TRAI calling hours (09:00-21:00 IST) apply ONLY to voice calls, NOT to WhatsApp messages.

## Reference Documents
- domain-foundation.md — Entities, types, state machines, signals, taxonomies
- system-behavior-design.md — Conversation flows, ADM experience, decision rules
```

---

## 4.5 Config Layer Implementation

### 4.5.1 Settings (`config/settings.py`)

```python
"""config/settings.py — Application settings from environment variables."""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://aars:aars_dev@localhost:5432/aars"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://aars:aars_dev@localhost:5432/aars"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 480  # 8 hours

    # S3 / MinIO
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET_RECORDINGS: str = "recordings"
    S3_BUCKET_TRAINING: str = "training-content"

    # Channel Providers
    VOICE_PROVIDER: str = "mock"       # "mock", "vibrium"
    WHATSAPP_PROVIDER: str = "mock"    # "mock", "meta"

    # WhatsApp — Meta Cloud API
    META_WHATSAPP_API_VERSION: str = "v21.0"
    META_WHATSAPP_PHONE_NUMBER_ID: str = ""   # From Meta Business dashboard
    META_WHATSAPP_ACCESS_TOKEN: str = ""       # Permanent system user token
    META_WHATSAPP_VERIFY_TOKEN: str = ""       # Webhook verification token (you define this)
    META_WHATSAPP_APP_SECRET: str = ""         # For webhook signature verification

    # Voice AI — Vibrium
    # Vibrium is webhook-driven: bots are configured on Vibrium dashboard,
    # Vibrium calls agents, then POSTs results to our webhook endpoint.
    VIBRIUM_WEBHOOK_SECRET: str = ""           # For verifying Vibrium webhook signatures
    VIBRIUM_API_URL: str = ""                  # If Vibrium provides an API to trigger calls
    VIBRIUM_API_KEY: str = ""                  # If Vibrium provides an API key

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"

    # Environment
    ENV: str = "development"  # development, staging, production
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # CORS
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"

settings = Settings()
```

### 4.5.2 Database (`config/database.py`)

```python
"""
config/database.py — Database engine and session factories.

CRITICAL: Two separate session factories exist:
1. async_session_factory — for FastAPI request handlers (uses asyncpg)
2. sync_session_factory  — for Celery tasks (uses psycopg2)

NEVER use async sessions in Celery. NEVER use sync sessions in FastAPI handlers.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config.settings import settings

# ── Async engine (FastAPI) ──
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=10,
)
async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Sync engine (Celery tasks) ──
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=5,
)
sync_session_factory = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
)
```

---

## 4.6 Core Layer Implementation

### 4.6.1 Semantic Types (`core/types.py`)

```python
"""
core/types.py — Semantic domain types.
Every domain value uses one of these types. They carry validation and documentation.
Import these EVERYWHERE — never use raw str/int for domain values.
"""
from __future__ import annotations
import re, uuid
from decimal import Decimal
from datetime import time
from typing import Annotated, Any
from pydantic import AfterValidator, BaseModel, BeforeValidator, Field

# ─── Identity Types ───
def _validate_uuid(v: Any) -> uuid.UUID:
    if isinstance(v, uuid.UUID): return v
    return uuid.UUID(str(v))

TenantId = Annotated[uuid.UUID, BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for an insurer tenant")]
AgentId = Annotated[uuid.UUID, BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for an insurance agent")]
ADMId = Annotated[uuid.UUID, BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for an ADM user")]
UserId = Annotated[uuid.UUID, BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for any platform user")]
SignalId = Annotated[uuid.UUID, BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for a signal event")]
ConversationId = Annotated[uuid.UUID, BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for a conversation thread")]
PlaybookId = Annotated[uuid.UUID, BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for a playbook definition")]
RegionNodeId = Annotated[uuid.UUID, BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for a node in region hierarchy")]
TrainingModuleId = Annotated[uuid.UUID, BeforeValidator(_validate_uuid),
    Field(description="Unique identifier for a training module")]

# ─── Personal Information Types ───
def _validate_indian_mobile(v: str) -> str:
    cleaned = re.sub(r'[\s\-\(\)]', '', str(v))
    if cleaned.startswith('0'): cleaned = '+91' + cleaned[1:]
    elif cleaned.startswith('91') and len(cleaned) == 12: cleaned = '+' + cleaned
    elif len(cleaned) == 10 and cleaned[0] in '6789': cleaned = '+91' + cleaned
    if not re.match(r'^\+91[6-9]\d{9}$', cleaned):
        raise ValueError(f'Invalid Indian mobile number: {v}')
    return cleaned

IndianMobileNumber = Annotated[str, AfterValidator(_validate_indian_mobile),
    Field(description="Indian mobile number in E.164 (+91XXXXXXXXXX)",
          json_schema_extra={"pattern": r"^\+91[6-9]\d{9}$"})]

def _validate_email(v: str) -> str:
    v = str(v).strip().lower()
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
        raise ValueError(f'Invalid email: {v}')
    return v
EmailAddress = Annotated[str, AfterValidator(_validate_email),
    Field(description="Email address, normalized to lowercase")]

def _validate_pan(v: str) -> str:
    v = str(v).strip().upper()
    if not re.match(r'^[A-Z]{5}\d{4}[A-Z]$', v):
        raise ValueError(f'Invalid PAN: {v}')
    return v
IndianPAN = Annotated[str, AfterValidator(_validate_pan),
    Field(description="Indian PAN. PII — encrypt at rest.")]

def _validate_aadhaar(v: str) -> str:
    v = re.sub(r'[\s\-]', '', str(v))
    if not re.match(r'^\d{12}$', v):
        raise ValueError(f'Invalid Aadhaar: must be 12 digits')
    return v
AadhaarNumber = Annotated[str, AfterValidator(_validate_aadhaar),
    Field(description="Aadhaar (12 digits). PII — encrypt, never display full.")]

PersonName = Annotated[str, Field(max_length=200, description="Full name")]
AgentCode = Annotated[str, Field(max_length=50, description="Agent code from insurer PAS")]
IrdaiLicenseNumber = Annotated[str, Field(max_length=50, description="IRDAI license number")]
ProductCode = Annotated[str, Field(max_length=50, description="Product code from insurer catalog")]

# ─── Monetary Types ───
class Money(BaseModel):
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    currency: str = Field(default="INR", pattern=r'^[A-Z]{3}$')
    def __str__(self) -> str: return f"₹{self.amount:,.2f}"

# ─── Temporal Types ───
class TimeWindow(BaseModel):
    start: time
    end: time
    timezone: str = Field(default="Asia/Kolkata")
    def contains(self, t: time) -> bool:
        if self.start <= self.end: return self.start <= t <= self.end
        return t >= self.start or t <= self.end

# ─── Language ───
SUPPORTED_LANGUAGES = {"hi","en","ta","te","kn","mr","bn","ml","gu","pa","or","as"}
def _validate_language(v: str) -> str:
    v = str(v).lower().strip()
    if v not in SUPPORTED_LANGUAGES:
        raise ValueError(f'Unsupported language: {v}')
    return v
Language = Annotated[str, AfterValidator(_validate_language),
    Field(description="ISO 639-1 language code")]
```

### 4.6.2 All Enums (`core/enums.py`)

```python
"""core/enums.py — All domain enums. Central location."""
from enum import StrEnum

class AgentLifecycleState(StrEnum):
    ONBOARDED = "onboarded"
    LICENSED = "licensed"
    FIRST_SALE = "first_sale"
    ACTIVE = "active"
    PRODUCTIVE = "productive"
    AT_RISK = "at_risk"
    DORMANT = "dormant"
    LAPSED = "lapsed"
    TERMINATED = "terminated"

class ChannelType(StrEnum):
    VOICE_AI = "voice_ai"
    WHATSAPP_BOT = "whatsapp_bot"
    WHATSAPP_ADM = "whatsapp_adm"
    ADM_CALL = "adm_call"
    ADM_VISIT = "adm_visit"
    SMS = "sms"
    EMAIL = "email"
    SELF_SERVICE = "self_service"

class ContactOutcome(StrEnum):
    ANSWERED = "answered"
    NOT_ANSWERED = "not_answered"
    BUSY = "busy"
    SWITCHED_OFF = "switched_off"
    WRONG_NUMBER = "wrong_number"
    DND_BLOCKED = "dnd_blocked"
    OPTED_OUT = "opted_out"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED_TECHNICAL = "failed_technical"

class ConsentStatus(StrEnum):
    NOT_ASKED = "not_asked"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"

class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    FRUSTRATED = "frustrated"
    INTERESTED = "interested"
    CONFUSED = "confused"

class SignalSource(StrEnum):
    """What system or actor generated this signal."""
    VOICE_AI = "voice_ai"
    WHATSAPP_BOT = "whatsapp_bot"
    ADM_REPORT = "adm_report"
    PAS_SYNC = "pas_sync"
    LMS_SYNC = "lms_sync"
    COMMISSION_SYNC = "commission_sync"
    SYSTEM = "system"
    MANUAL = "manual"
    BATCH_IMPORT = "batch_import"

class SignalType(StrEnum):
    # Voice AI
    VOICE_CALL_INITIATED = "voice_call_initiated"
    VOICE_CALL_OUTCOME = "voice_call_outcome"
    VOICE_CONVERSATION_ANALYZED = "voice_conversation_analyzed"
    VOICE_CALL_RECORDING_STORED = "voice_call_recording_stored"
    # WhatsApp
    WHATSAPP_MESSAGE_SENT = "whatsapp_message_sent"
    WHATSAPP_MESSAGE_DELIVERED = "whatsapp_message_delivered"
    WHATSAPP_MESSAGE_READ = "whatsapp_message_read"
    WHATSAPP_AGENT_REPLIED = "whatsapp_agent_replied"
    WHATSAPP_TRAINING_INTERACTION = "whatsapp_training_interaction"
    # ADM Activity
    ADM_AGENT_CALL_LOGGED = "adm_agent_call_logged"
    ADM_AGENT_VISIT_LOGGED = "adm_agent_visit_logged"
    ADM_NUDGE_RECEIVED = "adm_nudge_received"
    ADM_NUDGE_ACTED_ON = "adm_nudge_acted_on"
    ADM_BRIEFING_OPENED = "adm_briefing_opened"
    # Business Events
    POLICY_SOLD = "policy_sold"
    COMMISSION_CREDITED = "commission_credited"
    LICENSE_STATUS_CHANGED = "license_status_changed"
    AGENT_DATA_UPDATED = "agent_data_updated"
    TRAINING_COMPLETED_EXTERNAL = "training_completed_external"
    # System Events
    LIFECYCLE_STATE_CHANGED = "lifecycle_state_changed"
    PLAYBOOK_STARTED = "playbook_started"
    PLAYBOOK_STEP_EXECUTED = "playbook_step_executed"
    PLAYBOOK_COMPLETED = "playbook_completed"
    ESCALATION_CREATED = "escalation_created"
    CONSENT_CHANGED = "consent_changed"

class CallPurpose(StrEnum):
    """Purpose of a voice AI call."""
    CHECK_IN = "check_in"
    TRAINING = "training"
    REACTIVATION = "reactivation"
    CONGRATULATION = "congratulation"
    SURVEY = "survey"
    LICENSE_RENEWAL = "license_renewal"
    FIRST_CONTACT = "first_contact"

class DormancyReasonCategory(StrEnum):
    TRAINING_GAP = "training_gap"
    ENGAGEMENT_GAP = "engagement_gap"
    ECONOMIC = "economic"
    OPERATIONAL = "operational"
    PERSONAL = "personal"
    REGULATORY = "regulatory"
    UNKNOWN = "unknown"

class DormancyReasonCode(StrEnum):
    PRODUCT_KNOWLEDGE_INSUFFICIENT = "training_gap.product_knowledge_insufficient"
    SALES_SKILLS_LACKING = "training_gap.sales_skills_lacking"
    EXAM_NOT_ATTEMPTED = "training_gap.exam_not_attempted"
    EXAM_FAILED = "training_gap.exam_failed"
    PROCESS_UNCLEAR = "training_gap.process_unclear"
    ADM_NEVER_CONTACTED = "engagement_gap.adm_never_contacted"
    ADM_NO_FOLLOWTHROUGH = "engagement_gap.adm_no_followthrough"
    FEELS_UNSUPPORTED = "engagement_gap.feels_unsupported"
    NO_RECOGNITION = "engagement_gap.no_recognition"
    COMMISSION_TOO_LOW = "economic.commission_too_low"
    COMPETITOR_BETTER_COMMISSION = "economic.competitor_better_commission"
    IRREGULAR_PAYMENTS = "economic.irregular_payments"
    INSUFFICIENT_INCOME = "economic.insufficient_income"
    PROPOSAL_PROCESS_COMPLEX = "operational.proposal_process_complex"
    TECHNOLOGY_BARRIERS = "operational.technology_barriers"
    CLAIM_EXPERIENCE_BAD = "operational.claim_experience_bad"
    SLOW_ISSUANCE = "operational.slow_issuance"
    KYC_ISSUES = "operational.kyc_issues"
    HEALTH_ISSUES = "personal.health_issues"
    RELOCATED = "personal.relocated"
    FAMILY_OBLIGATIONS = "personal.family_obligations"
    LOST_INTEREST = "personal.lost_interest"
    OTHER_EMPLOYMENT = "personal.other_employment"
    LICENSE_EXPIRED = "regulatory.license_expired"
    LICENSE_EXPIRING_SOON = "regulatory.license_expiring_soon"
    COMPLIANCE_ISSUE = "regulatory.compliance_issue"
    UNKNOWN = "unknown"

class TrainingTopic(StrEnum):
    """Training content topic categories."""
    PRODUCT_TERM_LIFE = "product_term_life"
    PRODUCT_ENDOWMENT = "product_endowment"
    PRODUCT_ULIP = "product_ulip"
    PRODUCT_HEALTH = "product_health"
    PRODUCT_PENSION = "product_pension"
    SALES_PROSPECTING = "sales_prospecting"
    SALES_PITCH = "sales_pitch"
    SALES_OBJECTION_HANDLING = "sales_objection_handling"
    SALES_CLOSING = "sales_closing"
    PROCESS_PROPOSAL_FILLING = "process_proposal_filling"
    PROCESS_KYC = "process_kyc"
    PROCESS_DIGITAL_TOOLS = "process_digital_tools"
    COMPLIANCE_BASICS = "compliance_basics"
    COMPLIANCE_MIS_SELLING = "compliance_mis_selling"
    SOFT_SKILLS_COMMUNICATION = "soft_skills_communication"
    SOFT_SKILLS_TRUST_BUILDING = "soft_skills_trust_building"

class PlaybookActionType(StrEnum):
    VOICE_CALL = "voice_call"
    WHATSAPP_MESSAGE = "whatsapp_message"
    WHATSAPP_TRAINING = "whatsapp_training"
    ADM_NUDGE = "adm_nudge"
    WAIT = "wait"
    ESCALATE = "escalate"

class DecisionAction(StrEnum):
    DO_NOTHING = "do_nothing"
    START_PLAYBOOK = "start_playbook"
    CONTINUE_PLAYBOOK = "continue_playbook"
    SEND_NUDGE_TO_ADM = "send_nudge_to_adm"
    SCHEDULE_VOICE_CALL = "schedule_voice_call"
    SEND_WHATSAPP = "send_whatsapp"
    SEND_TRAINING = "send_training"
    ESCALATE = "escalate"
    CELEBRATE = "celebrate"
    PAUSE_OUTREACH = "pause_outreach"
    CLOSE_AND_ARCHIVE = "close_and_archive"

class RegionHierarchyLevel(StrEnum):
    ZONE = "zone"
    REGION = "region"
    BRANCH = "branch"
    AREA = "area"

class SubscriptionTier(StrEnum):
    TRIAL = "trial"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    REGIONAL_MANAGER = "regional_manager"
    ADM = "adm"
    COMPLIANCE_OFFICER = "compliance_officer"
    ANALYST = "analyst"
    SUPPORT_ENGINEER = "support_engineer"

class ProductCategory(StrEnum):
    TERM_LIFE = "term_life"
    ENDOWMENT = "endowment"
    ULIP = "ulip"
    WHOLE_LIFE = "whole_life"
    PENSION = "pension"
    HEALTH = "health"
    GROUP = "group"
```

### 4.6.3 Internal Event Bus (`core/events.py`)

```python
"""
core/events.py — Internal event bus for module-to-module communication.
In-process async bus. Replace with Kafka adapter by changing only this file.
NOT the Signal Stream — signals are domain events in the database.
"""
from __future__ import annotations
import asyncio, logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

@dataclass
class Event:
    event_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tenant_id: UUID | None = None
    payload: dict[str, Any] = field(default_factory=dict)

@dataclass
class SignalReceived(Event):
    signal_id: UUID = field(default_factory=uuid4)
    signal_type: str = ""
    agent_id: UUID | None = None

@dataclass
class LifecycleStateChanged(Event):
    agent_id: UUID = field(default_factory=uuid4)
    previous_state: str = ""
    new_state: str = ""

@dataclass
class PlaybookStepDue(Event):
    execution_id: UUID = field(default_factory=uuid4)
    playbook_id: UUID = field(default_factory=uuid4)
    agent_id: UUID = field(default_factory=uuid4)
    step_number: int = 0

@dataclass
class ADMNudgeRequired(Event):
    adm_id: UUID = field(default_factory=uuid4)
    agent_id: UUID | None = None
    nudge_type: str = ""
    message: str = ""

EventHandler = Callable[[Event], Coroutine[Any, Any, None]]

class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[Event], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        for handler in self._handlers.get(type(event), []):
            try:
                await handler(event)
            except Exception:
                logger.exception(f"Event handler error: {handler.__name__}")

event_bus = EventBus()
```

### 4.6.4 Tenant Context (`core/tenant_context.py`)

```python
"""core/tenant_context.py — Tenant context propagation via contextvars."""
from __future__ import annotations
import uuid
from contextvars import ContextVar
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

_current_tenant_id: ContextVar[uuid.UUID | None] = ContextVar('tenant_id', default=None)
_current_user_id: ContextVar[uuid.UUID | None] = ContextVar('user_id', default=None)
_current_user_roles: ContextVar[list[str]] = ContextVar('user_roles', default=[])

def get_tenant_id() -> uuid.UUID:
    tid = _current_tenant_id.get()
    if tid is None: raise RuntimeError("Tenant context not set")
    return tid

def get_user_id() -> uuid.UUID:
    uid = _current_user_id.get()
    if uid is None: raise RuntimeError("User context not set")
    return uid

def get_user_roles() -> list[str]:
    return _current_user_roles.get()

def set_context(tenant_id: uuid.UUID, user_id: uuid.UUID, roles: list[str]) -> None:
    _current_tenant_id.set(tenant_id)
    _current_user_id.set(user_id)
    _current_user_roles.set(roles)

def clear_context() -> None:
    _current_tenant_id.set(None)
    _current_user_id.set(None)
    _current_user_roles.set([])

async def set_rls_context_async(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Set PostgreSQL session variable for RLS. Used in FastAPI handlers."""
    await session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})

def set_rls_context_sync(session: Session, tenant_id: uuid.UUID) -> None:
    """Set PostgreSQL session variable for RLS. Used in Celery tasks."""
    session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
```

### 4.6.5 Base Models (`core/base_models.py`)

```python
"""core/base_models.py — SQLAlchemy base classes with tenant isolation and soft delete."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False)

class SoftDeleteMixin:
    """Add to models that need soft delete. Query with .filter(Model.deleted_at.is_(None))"""
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None)

class TenantScopedMixin(TimestampMixin):
    """ALL tenant-specific tables MUST use this. Adds tenant_id + RLS."""
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True)
```

### 4.6.6 API Dependencies (`api/dependencies.py`)

```python
"""api/dependencies.py — FastAPI dependency injection."""
from __future__ import annotations
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from config.database import async_session_factory
from core.security import decode_jwt
from core.tenant_context import set_context, set_rls_context_async, get_tenant_id

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session with RLS context set."""
    async with async_session_factory() as session:
        tenant_id = get_tenant_id()
        await set_rls_context_async(session, tenant_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def get_current_user(authorization: str = Header(...)) -> dict:
    """Extract and validate JWT, set tenant context."""
    token = authorization.replace("Bearer ", "")
    try:
        payload = decode_jwt(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    set_context(
        tenant_id=payload["tenant_id"],
        user_id=payload["user_id"],
        roles=payload["roles"]
    )
    return payload

def require_role(*roles: str):
    """Dependency that checks the user has one of the required roles."""
    async def checker(user: dict = Depends(get_current_user)):
        if not any(r in user["roles"] for r in roles):
            raise HTTPException(403, "Insufficient permissions")
        return user
    return checker
```

### 4.6.7 Health Check (`api/health.py`)

```python
"""api/health.py — Health check that verifies all dependencies."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from config.database import async_engine
from config.redis import redis_client
from sqlalchemy import text

router = APIRouter()

@router.get("/health")
async def health():
    checks = {}
    # Postgres
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False
    # Redis
    try:
        await redis_client.ping()
        checks["redis"] = True
    except Exception:
        checks["redis"] = False

    healthy = all(checks.values())
    checks["status"] = "healthy" if healthy else "degraded"
    return JSONResponse(checks, status_code=200 if healthy else 503)
```

---

## 4.7 Positive Signal Definition

This is critical — the lifecycle engine uses this concept everywhere.

```python
"""
Used by modules/agent/lifecycle.py and modules/agent/understanding.py
to determine if an agent has shown positive engagement.
"""

# Signals that count as POSITIVE (agent is engaged or progressing)
POSITIVE_SIGNAL_TYPES: set[str] = {
    "voice_call_outcome",           # Only when outcome IN (answered, completed)
    "whatsapp_agent_replied",       # Any reply from agent
    "whatsapp_training_interaction", # Only when completion > 50%
    "policy_sold",                  # Strongest positive signal
    "training_completed_external",  # Agent completed external training
    "adm_agent_call_logged",        # Only when outcome == DETAILED_DISCUSSION
    "adm_agent_visit_logged",       # Any in-person visit
}

# Signals that are NOT positive (must be explicit to avoid ambiguity)
NOT_POSITIVE: set[str] = {
    "whatsapp_message_delivered",   # Delivery without read/reply is not engagement
    "whatsapp_message_read",        # Read without reply is WEAK (see note below)
    "voice_call_outcome",           # When outcome == NOT_ANSWERED / BUSY / etc.
    "whatsapp_message_sent",        # System sending a message is not agent engagement
    "adm_nudge_received",           # ADM receiving a nudge is not agent activity
}

# SPECIAL CASE: WHATSAPP_MESSAGE_READ
# Read-only (no reply) counts as positive ONLY if:
#   - Message was read within 24 hours of delivery
#   - AND agent has been dormant for 30+ days
# This detects "re-engagement signals" from dormant agents even without an explicit reply.

def is_positive_signal(signal_type: str, payload: dict) -> bool:
    """Evaluate whether a specific signal instance is positive."""
    if signal_type == "voice_call_outcome":
        return payload.get("outcome") in ("answered", "completed")
    elif signal_type == "whatsapp_training_interaction":
        return (payload.get("completion_percentage", 0) > 50
                or payload.get("interaction_type") == "QUIZ_COMPLETED")
    elif signal_type == "adm_agent_call_logged":
        return payload.get("outcome") in ("CONNECTED", "DETAILED_DISCUSSION")
    elif signal_type in POSITIVE_SIGNAL_TYPES:
        return True
    return False
```

---

## 4.8 Engagement Score Computation

```python
"""
Used by modules/agent/understanding.py to compute the engagement score.

Score: 0-100. Recomputed hourly for agents with recent signals.

Components (weights are tenant-configurable, these are platform defaults):
"""

ENGAGEMENT_SCORE_WEIGHTS = {
    "call_answer_rate": 0.25,
    "whatsapp_response_rate": 0.25,
    "training_completion": 0.20,
    "recency": 0.30,
}

def compute_engagement_score(
    calls_attempted_30d: int,
    calls_answered_30d: int,
    whatsapp_sent_30d: int,
    whatsapp_replied_30d: int,
    training_started_30d: int,
    training_completed_30d: int,
    days_since_last_positive_signal: int | None,
    decay_rate: float = 0.02,  # per day, tenant-configurable
) -> float:
    """
    Returns engagement score 0-100.

    1. call_answer_rate: calls_answered / calls_attempted
       If no calls attempted: 0.5 (neutral — don't punish if system hasn't called)

    2. whatsapp_response_rate: whatsapp_replied / whatsapp_sent
       Training videos watched >50% count as implicit response

    3. training_completion: completed / started
       If none started: 0.0

    4. recency: max(0, 1.0 - (days_since_last_positive * decay_rate))
       50 days of silence = score of 0 for this component (at default decay)
       None (no positive signal ever) = 0.0
    """
    # Component 1: Call answer rate
    if calls_attempted_30d > 0:
        call_rate = calls_answered_30d / calls_attempted_30d
    else:
        call_rate = 0.5  # Neutral

    # Component 2: WhatsApp response rate
    if whatsapp_sent_30d > 0:
        wa_rate = whatsapp_replied_30d / whatsapp_sent_30d
    else:
        wa_rate = 0.5  # Neutral

    # Component 3: Training completion
    if training_started_30d > 0:
        training_rate = training_completed_30d / training_started_30d
    else:
        training_rate = 0.0

    # Component 4: Recency
    if days_since_last_positive_signal is not None:
        recency = max(0.0, 1.0 - (days_since_last_positive_signal * decay_rate))
    else:
        recency = 0.0

    w = ENGAGEMENT_SCORE_WEIGHTS
    score = (
        call_rate * w["call_answer_rate"]
        + wa_rate * w["whatsapp_response_rate"]
        + training_rate * w["training_completion"]
        + recency * w["recency"]
    ) * 100

    return round(max(0.0, min(100.0, score)), 2)
```

---

## 4.9 Outbound Rate Limiting

```yaml
rate_limiting:
  voice_calls:
    max_concurrent_per_tenant: "tenant.quotas.max_concurrent_voice_calls (default: 5)"
    max_per_hour_per_tenant: 50
    implementation: "Redis-based semaphore for concurrency, sliding window for rate"

  whatsapp_messages:
    max_per_second_per_tenant: 80   # WhatsApp Business API tier-dependent
    max_per_day_per_agent: 3        # Don't spam individual agents
    implementation: "Redis sliding window"

  implementation_location: "modules/channel/rate_limiter.py"
  pattern: |
    Before any outbound action:
    1. Check rate limit via Redis INCR + EXPIRE
    2. If limit exceeded: queue for later execution (don't drop)
    3. Log rate limit hits for monitoring
```

---

## 4.10 DND Registry Check

```yaml
dnd_check:
  when: "Before EVERY voice call"
  flow:
    - During agent import: batch check all phone numbers against NCPR registry
    - Store result in agent_understanding: dnd_registered (bool), dnd_checked_at (timestamp)
    - Before each call: if dnd_checked_at > 30 days ago, re-check
    - If DND registered: classify call as transactional (agent-insurer service relationship)
      or promotional. Only transactional calls are allowed.
    - Our calls are "service" calls (existing business relationship), not promotional.
      Flag this for each tenant's legal team to confirm.
  provider: "NCPR API or third-party DND scrub service (tenant-configured)"
  field_additions:
    agent_understanding:
      dnd_registered: Boolean (default false)
      dnd_checked_at: Timestamptz (nullable)
```

---

## 4.11 Channel Provider Interfaces

### Voice AI Provider — Vibrium Integration

Vibrium is **webhook-driven**: bots are configured on their dashboard, Vibrium conducts the
calls, then POSTs results (transcript + analysis) to our webhook endpoint. Our adapter
receives, parses, and emits signals.

```python
"""modules/channel/voice/provider.py — Abstract Voice AI provider."""
from __future__ import annotations
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from core.enums import ContactOutcome, SentimentLabel

@dataclass
class VoiceCallRequest:
    call_id: uuid.UUID
    tenant_id: uuid.UUID
    agent_id: uuid.UUID
    agent_phone: str
    caller_id: str
    language: str
    conversation_guide: str
    context: dict
    max_duration_seconds: int = 300
    persona_name: str = "Priya"

@dataclass
class VoiceCallResult:
    call_id: uuid.UUID
    outcome: ContactOutcome
    duration_seconds: int
    language_detected: str
    transcript_text: str | None = None
    transcript_summary: str | None = None
    sentiment: SentimentLabel | None = None
    analysis: dict | None = None  # Full NLU extraction from provider
    recording_url: str | None = None

class VoiceProvider(ABC):
    @abstractmethod
    async def initiate_call(self, request: VoiceCallRequest) -> str:
        """Trigger a call. Returns provider's call ID.
        For Vibrium: may call their API if available, or return a tracking ID
        for calls configured via dashboard campaigns."""
        ...
    @abstractmethod
    async def get_call_result(self, provider_call_id: str) -> VoiceCallResult | None:
        """Poll for call result. For webhook-driven providers like Vibrium,
        this checks our local cache of received webhook results."""
        ...
    @abstractmethod
    async def handle_callback(self, payload: dict) -> VoiceCallResult:
        """Parse webhook payload from provider into VoiceCallResult.
        This is the PRIMARY integration path for Vibrium."""
        ...
    @abstractmethod
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool: ...
```

```python
"""modules/channel/voice/vibrium.py — Vibrium Voice AI integration.

Integration pattern:
1. Bots are configured on Vibrium's dashboard (conversation flows, personas, languages)
2. Calls are triggered either:
   a. By Vibrium campaigns (configured on their dashboard, they batch-call agents)
   b. By our system if Vibrium exposes a trigger API (optional)
3. When a call completes, Vibrium POSTs to our webhook:
   POST /api/v1/webhooks/voice/{tenant_slug}
4. Webhook payload includes: transcript, analysis, sentiment, duration, outcome
5. We parse this into VoiceCallResult and emit signals

Integration steps for Claude Code:
- Create a Pydantic schema for Vibrium's webhook payload (get sample from their docs/dashboard)
- Map Vibrium's call outcome codes → our ContactOutcome enum
- Map Vibrium's sentiment labels → our SentimentLabel enum
- Extract structured data from Vibrium's analysis for our NLU layer
- Store the raw Vibrium payload in VoiceCallResult.analysis for debugging

Our NLU layer (nlu.py) then adds domain-specific extraction on top of Vibrium's analysis:
- Dormancy reason classification
- Product interest signals
- ADM relationship quality signals
- Preferred contact time / language preferences

NOTE: Until we have Vibrium's exact webhook payload schema, implement the adapter
with a flexible dict-based parser. Add strict Pydantic validation once we have
sample payloads from Vibrium.
"""

class VibriumProvider(VoiceProvider):
    pass  # Implement once Vibrium webhook payload schema is available
```

### WhatsApp Provider — Meta Cloud API Integration

Meta Cloud API is our **primary** WhatsApp provider. We send messages via their Graph API,
they send agent replies + delivery/read receipts to our webhook.

```python
"""modules/channel/whatsapp/provider.py — Abstract WhatsApp provider."""
from __future__ import annotations
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class WhatsAppMessage:
    message_id: uuid.UUID
    to_phone: str
    template_name: str | None = None
    template_language: str | None = None
    template_params: dict | None = None
    text: str | None = None
    media_url: str | None = None
    media_type: str | None = None
    buttons: list[dict] | None = None

@dataclass
class WhatsAppIncomingMessage:
    from_phone: str
    message_type: str
    text: str | None = None
    button_payload: str | None = None
    media_url: str | None = None

class WhatsAppProvider(ABC):
    @abstractmethod
    async def send_message(self, message: WhatsAppMessage) -> str: ...
    @abstractmethod
    async def send_template(self, message: WhatsAppMessage) -> str: ...
    @abstractmethod
    async def handle_webhook(self, payload: dict) -> list: ...
    @abstractmethod
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool: ...
```

```python
"""modules/channel/whatsapp/meta_cloud.py — Meta Cloud API integration.

Integration:
1. OUTBOUND: Send messages via Meta Graph API
   POST https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages
   Headers: Authorization: Bearer {ACCESS_TOKEN}

2. INBOUND: Receive agent replies + delivery/read receipts via webhook
   POST /api/v1/webhooks/whatsapp/{tenant_slug}
   Verify: X-Hub-Signature-256 header using HMAC-SHA256 with APP_SECRET

3. WEBHOOK VERIFICATION: Meta sends GET on webhook setup
   GET /api/v1/webhooks/whatsapp/{tenant_slug}?hub.mode=subscribe&hub.verify_token=...
   Respond with hub.challenge if token matches META_WHATSAPP_VERIFY_TOKEN

4. TEMPLATES: Must be pre-approved on Meta Business Manager
   Send via same endpoint with type: "template", template name + language + parameters

Message types supported:
- Template messages (required outside 24-hour conversation window)
- Text messages (within 24-hour window after agent replies)
- Interactive messages: buttons (max 3), list menus (max 10 items)
- Media messages: image, video, document, audio
- Reaction messages

Status webhooks provide: sent, delivered, read, failed (with error codes)
"""
import hashlib, hmac, httpx
from config.settings import settings

class MetaCloudProvider(WhatsAppProvider):
    BASE_URL = f"https://graph.facebook.com/{settings.META_WHATSAPP_API_VERSION}"

    async def send_message(self, message: WhatsAppMessage) -> str:
        """Send text/interactive/media message via Meta Graph API.
        Returns Meta's message ID (wamid)."""
        url = f"{self.BASE_URL}/{settings.META_WHATSAPP_PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {settings.META_WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        # Build payload based on message type (text, interactive, media)
        ...

    async def send_template(self, message: WhatsAppMessage) -> str:
        """Send template message. Required for first contact (outside 24h window).
        template_name and template_language are required.
        template_params map to positional parameters in the approved template."""
        ...

    async def handle_webhook(self, payload: dict) -> list:
        """Parse Meta's webhook format:
        payload.entry[].changes[].value.messages[]  — incoming messages
        payload.entry[].changes[].value.statuses[]   — delivery/read receipts
        Returns list of WhatsAppIncomingMessage or status update dicts."""
        ...

    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify X-Hub-Signature-256 header using APP_SECRET."""
        expected = hmac.new(
            settings.META_WHATSAPP_APP_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)
```

---

## 4.12 Signal Idempotency

External systems (PAS webhooks, batch imports) may send the same event twice. Without idempotency, you get duplicate signals and double state transitions.

```yaml
signal_idempotency:
  field: "idempotency_key VARCHAR(200) NULL on signals table"
  format: "{source}:{external_id}:{event_type}"
  example: "pas_sync:POL-2024-001234:policy_sold"
  index: "CREATE UNIQUE INDEX idx_signal_idempotency ON signals (tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL"
  behavior:
    - If a signal is emitted with an idempotency_key that already exists for that tenant:
      return the existing signal, do NOT create a new one, do NOT re-process
    - idempotency_key is optional — internal system signals don't need it
    - Batch imports ALWAYS set idempotency_key
```

---

## 4.13 API Routes Summary

```yaml
# All prefixed /api/v1, all tenant-scoped routes require JWT

# Health (no auth required)
GET  /health

# Auth
POST /api/v1/auth/login
POST /api/v1/auth/refresh

# Tenant
POST /api/v1/tenants                          # Create (super_admin)
GET  /api/v1/tenants/{id}
PUT  /api/v1/tenants/{id}/config

# Agent (all paginated with cursor)
GET  /api/v1/agents                           # List (role-scoped, filterable)
GET  /api/v1/agents/{id}                      # Detail + understanding
GET  /api/v1/agents/{id}/signals              # Signal history (paginated)
GET  /api/v1/agents/{id}/conversations        # Conversations (paginated)
POST /api/v1/agents/import                    # Bulk CSV import

# Signals
POST /api/v1/signals                          # Emit (integrations, supports idempotency_key)
GET  /api/v1/signals                          # Query (paginated, filterable)

# Playbooks
GET  /api/v1/playbooks
POST /api/v1/playbooks
GET  /api/v1/playbooks/executions

# Training
GET  /api/v1/training/modules
POST /api/v1/training/modules

# ADM (consumed by WhatsApp bot)
GET  /api/v1/adm/briefing
GET  /api/v1/adm/agents
GET  /api/v1/adm/agents/{id}/detail
POST /api/v1/adm/actions

# Analytics
GET  /api/v1/analytics/dashboard
GET  /api/v1/analytics/dormancy
GET  /api/v1/analytics/reactivation
GET  /api/v1/analytics/adm-performance

# Webhooks (incoming — verify signature before processing)
POST /api/v1/webhooks/whatsapp/{tenant_slug}
POST /api/v1/webhooks/voice/{tenant_slug}

# Integration
POST /api/v1/integration/sync
POST /api/v1/integration/upload
```

---

## 4.14 Background Tasks (Celery)

```yaml
# IMPORTANT: Daily tasks are ordered so decisions run BEFORE briefings.
# Briefings must incorporate today's decisions to show correct priorities.

every_minute:
  - process_pending_signals          # SLOW PATH: pick up signals where processed=false
  - execute_due_playbook_steps       # Run playbook steps where next_step_due_at <= now
  - execute_pending_decisions        # Execute decisions from decision_logs where executed=false

hourly:
  - update_agent_understanding       # Recompute for agents with recent signals

daily (ordered sequence — order matters):
  - "00:00 UTC (05:30 IST): sync_external_data"     # PAS, LMS, commission sync
  - "01:00 UTC (06:30 IST): decision_engine_batch"   # Evaluate all agents due
  - "02:00 UTC (07:30 IST): generate_morning_briefings"  # Incorporates today's decisions

weekly:
  - "Monday 02:30 UTC (08:00 IST): generate_weekly_summaries"
  - "Monday 04:00 UTC (09:30 IST): aggregate_analytics"
  - "Monday 05:00 UTC (10:30 IST): update_playbook_metrics"
```

---

## 4.15 Build Sequence: Vertical Slices

**Build thin vertical slices, not horizontal layers.**

### Slice 0: Project Skeleton (Day 1)
```
Build: Project structure, pyproject.toml (with psycopg2-binary + asyncpg), docker-compose,
config/ (settings.py, database.py, redis.py, celery_app.py), core/ (types, enums,
base_models, events, tenant_context, exceptions), alembic setup, FastAPI app with /health
endpoint that checks postgres + redis, CLAUDE.md, .env.example
Verify: docker-compose up, alembic upgrade head, uvicorn starts, GET /health → 200 with
{"postgres": true, "redis": true, "status": "healthy"}
```

### Slice 1: Tenant + Agent Data (Days 2-4)
```
Build: All SQLAlchemy models (generates DB schema via Alembic), tenant module, agent module
(CRUD), auth (JWT), middleware, api/dependencies.py, seed scripts, bulk agent CSV import,
RLS policies in migration
Verify: Create tenant, import 100 agents, tenant isolation works, two tenants don't see
each other's agents. Pagination works on agent list.
```

### Slice 2: Signal Store + Lifecycle (Days 5-8)
```
Build: Signal module (emit with idempotency, query, process), lifecycle state machine,
agent understanding computation (with engagement score formula), positive signal classification,
dual-path signal processing (fast + slow), Celery signal processing tasks (using sync sessions),
signal simulation script
Verify: POLICY_SOLD → agent becomes FIRST_SALE. No activity 90 days → DORMANT.
Understanding updates: engagement_score, last_contact. State changes emit their own signals.
Duplicate signal with same idempotency_key → rejected.
```

### Slice 3: WhatsApp Channel — Meta Cloud API (Days 9-12)
```
Build: WhatsApp provider interface + Meta Cloud API implementation + mock,
Meta webhook handler (GET for verification + POST for messages/statuses),
X-Hub-Signature-256 verification, bot logic, message templates (pre-approve on
Meta Business Manager), webhook handler converting incoming messages → signals,
rate limiter, training quiz flow over WhatsApp interactive buttons
Verify: Send real template message to a test phone number via Meta Cloud API.
Webhook receives delivery + read receipts → signals emitted. Simulate agent reply →
signal captured → engagement score updates. Training quiz works end-to-end with
interactive buttons. Rate limiter prevents > 3 messages/day to same agent.
Mock provider still works for automated tests.
```

### Slice 4: Voice AI Channel — Vibrium (Days 13-16)
```
Build: Voice provider interface + Vibrium webhook adapter + mock, Vibrium webhook endpoint
(receives transcript + analysis after each call), parse Vibrium payload into VoiceCallResult,
NLU extraction layer (dormancy reasons, product mentions, sentiment from Vibrium's analysis),
DND check stub, conversation_flows.py (guides for Vibrium dashboard bot configuration)
Verify: Simulate Vibrium webhook POST with sample payload → VoiceCallResult parsed →
signals emitted (VOICE_CALL_OUTCOME, VOICE_CONVERSATION_ANALYZED) → agent understanding
updated with dormancy reasons from transcript. TRAI hours enforced for voice only.
Once Vibrium webhook is live: real call → real transcript → real signals.
NOTE: Vibrium bot conversation design happens on their dashboard, not in our code.
Our code receives results and extracts intelligence from them.
```

### Slice 5: ADM Experience (Days 17-20)
```
Build: ADM module, morning briefing (generated AFTER decision engine), agent detail, alerts,
action logging, Celery briefing tasks (using sync sessions), ADM effectiveness computation
Verify: Briefing generates correctly with today's decision priorities, ADM queries agent
details, ADM logs actions → signals emitted
```

### Slice 6: Playbook Engine (Days 21-25)
```
Build: Playbook module (definition, execution, branching via condition_evaluator.py — NO eval()),
default playbooks from Phase 3, executor integrates with channel providers, Celery execution tasks
Verify: Training Gap playbook runs: WhatsApp → quiz → ADM nudge. Handles non-response
and opt-out correctly. Branching logic works with safe evaluator.
```

### Slice 7: Decision Engine (Days 26-30)
```
Build: Decision module (engine, rules, constraints), batch evaluation, decision → action
execution, decision logging with reasoning
Verify: DORMANT agent → START_PLAYBOOK. Opted-out agent → DO_NOTHING. Productive agent
declining → urgent ADM nudge. TRAI constraint blocks voice calls outside hours but allows
WhatsApp. All decisions logged with reasoning.
```

### Slice 8: Analytics (Days 31-35)
```
Build: Analytics module, dashboard API (paginated), aggregation tasks, basic React dashboard
Verify: Activation rate, dormancy reasons, reactivation funnel all render correctly.
Data is tenant and role scoped.
```

### Slice 9: Integration Framework (Days 36-40)
```
Build: Integration adapters, CSV/Excel upload with idempotency keys, webhook receiver with
signature verification, field mapping, reconciliation logic
Verify: Agent CSV → agents created. Policy CSV → POLICY_SOLD signals with idempotency keys →
lifecycle updates. Same CSV uploaded twice → no duplicates.
```

### Slice 10: End-to-End (Days 41-45)
```
Build: Demo tenant with full data, enhanced signal simulator, integration tests,
tenant isolation tests, soft delete tests, error handling, API docs review
Verify: Full journey works: onboard → dormant → voice call → reason identified →
playbook → training → ADM nudge → sale → celebration → active.
Soft-deleted agents excluded from all queries. Error responses use standard format.
```

---

## 4.16 Development Environment Setup

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: aars
      POSTGRES_USER: aars
      POSTGRES_PASSWORD: aars_dev
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - miniodata:/data

volumes:
  pgdata:
  miniodata:
```

```toml
# pyproject.toml key dependencies
[project]
name = "aars"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    # Web framework
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "python-multipart>=0.0.6",
    # Database — BOTH async and sync drivers
    "sqlalchemy[asyncio]>=2.0.25",
    "asyncpg>=0.29.0",
    "psycopg2-binary>=2.9.9",
    "alembic>=1.13.0",
    # Cache & Queue
    "redis>=5.0.0",
    "celery[redis]>=5.3.0",
    # Auth
    "pyjwt>=2.8.0",
    "passlib[bcrypt]>=1.7.4",
    # Data validation
    "pydantic>=2.5.0",
    "pydantic-settings>=2.1.0",
    # File processing
    "openpyxl>=3.1.0",
    # Storage
    "boto3>=1.34.0",
    # HTTP client
    "httpx>=0.26.0",
    # Encryption
    "cryptography>=41.0.0",
    # Utilities
    "python-dateutil>=2.8.0",
    "structlog>=24.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
    "factory-boy>=3.3.0",
    "ruff>=0.2.0",
    "mypy>=1.8.0",
    "black>=24.1.0",
]
```

---

## 4.17 Non-Negotiable Engineering Rules

```
1. TENANT ISOLATION: Every query filters by tenant_id. RLS on all tables. Tests verify.
2. SIGNALS ARE SACRED: Append-only. Never update/delete. All state derived from signals.
3. TYPES ARE DOCUMENTATION: Use core/types.py everywhere. Never raw str for domain values.
4. CONFIGURABILITY: Hard-code nothing insurer-specific. Tenant config with platform defaults.
5. PROVIDERS ABSTRACT: Voice/WhatsApp/SMS behind interfaces. Mock for every provider.
6. DECISIONS LOGGED: Every system decision recorded with reasoning in decision_logs.
7. ERRORS HANDLED: No bare except. Timeouts on external calls. Failed signals don't block.
8. TASKS IDEMPOTENT: Every Celery task safe to retry. Use sync sessions in Celery.
9. WEBHOOKS VERIFIED: Every incoming webhook verified with signature before processing.
10. TRAI IS VOICE-ONLY: Calling hour restrictions apply to voice calls, not WhatsApp.
```
