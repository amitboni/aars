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
- docker compose up -d postgres redis — Start postgres, redis
- alembic upgrade head — Run migrations
- python scripts/seed_db.py — Seed platform defaults only
- python scripts/seed_db.py --demo — Seed full demo (tenant, agents, playbooks, training, signals)
- python scripts/simulate_signals.py --demo — Generate realistic signals for demo agents
- uvicorn api.app:create_app --factory --reload — Dev server
- celery -A config.celery_app worker -l info — Background workers
- celery -A config.celery_app beat -l info — Scheduler
- pytest — All tests
- pytest tests/test_integration/ — Integration tests only
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
- WhatsApp (Gupshup): Verify X-Hub-Signature header using HMAC-SHA256
- WhatsApp (Meta): Verify X-Hub-Signature-256 header
- Voice AI: Verify provider-specific signature header
- Webhook secret stored per-tenant in tenant config
- If verification fails: return 401, log attempt, do NOT process payload

## Signal Processing — Dual Path
Signals are processed through TWO paths:
1. FAST PATH: When a signal originates in-process (webhook handler), publish SignalReceived
   event on internal event bus -> handler immediately runs lifecycle check + understanding update.
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
2. Tenant isolation (create in Tenant A, query as Tenant B -> empty)
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

## Build Progress — ALL SLICES COMPLETE
- Slice 0: Foundation (DB, auth, config, base models, enums)
- Slice 1: Signal Stream (append-only event log, dual-path processing, idempotency)
- Slice 2: Agent Module (CRUD, lifecycle state machine, engagement scoring)
- Slice 3: Channel — WhatsApp (Gupshup provider, templates, webhook receiver)
- Slice 4: Channel — Voice AI (provider interface, TRAI compliance, conversation analysis)
- Slice 5: ADM Experience (morning briefings, alerts, actions, weekly summaries)
- Slice 6: Playbook Engine (CRUD, trigger, step execution, branching, condition evaluator)
- Slice 7: Decision Engine (rule chain, batch evaluation, Celery scheduled task)
- Slice 8: Analytics (snapshots, dormancy analytics, reactivation funnels, trends API)
- Slice 9: Integration Framework (CSV/Excel uploads, webhooks, PAS/LMS/Commission adapters)
- Slice 10: End-to-End (demo tenant, seeds, signal simulator, integration tests)

## Modules
- `modules/agent/` — Agent CRUD, lifecycle state machine, engagement scoring
- `modules/signal/` — Signal emission, dual-path processing, idempotency
- `modules/playbook/` — Playbook CRUD, trigger, step runs, branching conditions
- `modules/decision/` — Rule chain evaluation, batch processing, Celery task
- `modules/channel/whatsapp/` — WhatsApp provider (Gupshup), templates, webhook
- `modules/channel/voice/` — Voice AI provider, TRAI compliance, conversation analysis
- `modules/adm/` — ADM morning briefings, alerts, actions, weekly summaries
- `modules/analytics/` — Snapshots, dormancy analytics, reactivation funnels
- `modules/integration/` — CSV/Excel uploads, webhooks, PAS/LMS/Commission adapters
- `modules/tenant/` — Tenant model and config
- `modules/user/` — User model, roles, authentication

## Seeds & Scripts
- `seeds/platform_defaults.py` — Default thresholds, scoring weights, contact rules, TRAI hours
- `seeds/dormancy_taxonomy.py` — All 27 dormancy reasons across 7 categories
- `seeds/default_playbooks.py` — 6 default playbooks with branching
- `seeds/default_training.py` — 7 training modules with quizzes
- `seeds/demo_tenant.py` — Full demo: 50 agents, 5 ADMs, region hierarchy
- `scripts/seed_db.py` — Master idempotent seeder (--demo for full data)
- `scripts/simulate_signals.py` — Realistic signal generator per lifecycle state

## Celery Tasks
- `tasks/signal_processing.py` — Process unprocessed signals (every 60s)
- `tasks/decision_batch.py` — Batch evaluate agents needing decisions (every 15m)
- `tasks/integration_sync.py` — External data sync placeholder (daily at 00:00 UTC)

## API Endpoints
- `POST /api/v1/auth/login` — JWT login
- `GET/POST /api/v1/agents` — Agent CRUD
- `GET/PUT/DELETE /api/v1/agents/{id}` — Agent detail
- `POST /api/v1/signals` — Emit signal
- `GET /api/v1/signals` — List signals
- `GET/POST /api/v1/playbooks` — Playbook CRUD
- `POST /api/v1/playbooks/trigger` — Trigger playbook run
- `GET /api/v1/playbooks/runs` — List playbook runs
- `GET /api/v1/adm/briefing` — Morning briefing
- `GET /api/v1/adm/alerts` — ADM alerts
- `POST /api/v1/adm/actions` — Log ADM action
- `GET /api/v1/analytics/snapshot` — Analytics snapshot
- `GET /api/v1/analytics/dormancy` — Dormancy analytics
- `GET /api/v1/analytics/reactivation` — Reactivation funnel
- `GET /api/v1/analytics/trends` — Trend data
- `POST /api/v1/integration/upload` — CSV/Excel upload
- `GET /api/v1/integration/jobs` — Integration job list
- `POST /api/v1/integration/webhooks/{slug}/{system}` — External webhook receiver
- `GET /health` — Health check

## Frontend
- cd frontend && npm run dev — Start frontend on http://localhost:3000
- cd frontend && npm run build — Production build
- cd frontend && npm run lint — Lint

## Reference Documents
- domain-foundation.md — Entities, types, state machines, signals, taxonomies
- system-behavior-design.md — Conversation flows, ADM experience, decision rules
- technical-design.md — Architecture, build sequence, implementation details
