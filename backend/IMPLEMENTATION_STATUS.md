# Backend Implementation Status

Last verified: 2026-09-01 (Python 3.12.10, Docker 29.1.3 / Compose v2.40.3 on Windows).

## Foundation

- [x] FastAPI app factory with lifespan, CORS, logging, Swagger `/docs`
- [x] Typed settings via pydantic-settings (`app/core/config.py`)
- [x] SQLAlchemy 2 async engine/session (`app/core/database.py`)
- [x] Redis client with graceful degradation (`app/core/redis.py`)
- [x] Layered structure: api/v2 routers → services → repositories → models
- [x] Pinned dependencies (`requirements.txt`, `requirements-dev.txt`)
- [x] Initial Alembic migration for all 18 tables (`alembic/versions/ab57577973e4_initial_schema.py`)

## Entities (models + schemas + repositories + endpoints + tests)

- [x] Users (integer PK, argon2 hashes, telegram link fields)
- [x] Roles + permissions (JSONB lists, permission enforcement on all routes)
- [x] Motorcycles (string IDs `mc-xxx`, status lifecycle, delete rules)
- [x] Rental customers (`rc-xxx`, Active/Inactive, delete rules)
- [x] Rentals (`rt-xxx`, denormalized display fields, full balance columns)
- [x] Rental payments (`rp-xxx` / `RNP-` numbering)
- [x] Rental charges (`rg-xxx` / `RNC-` numbering)
- [x] Rental expenses (`rx-xxx` / `RNX-` numbering)
- [x] Audit logs (UUID, entity filters, written by every mutation)
- [x] Document sequences (atomic increment, prefix/year/padding)
- [x] Application settings (JSONB key-value, cached, masked secrets)
- [x] Telegram chat links (user fields + Redis link codes)
- [x] Refresh-token sessions (token families, rotation, reuse detection)
- [x] Password recovery state (Redis hashes + TTL + attempts; delivery envelope)
- [x] Transactional outbox events (`outbox_events`)
- [x] Export jobs + task progress records (`export_jobs`, `task_progress`)

## Authentication

- [x] `POST /auth/login` (email + password, bearer pair + user payload)
- [x] `POST /auth/refresh` (rotation, family revocation on reuse, Redis denylist)
- [x] `POST /auth/logout` (JTI revoke until expiry)
- [x] `GET /auth/me` (AuthUser shape: id/name/email/role/avatar/permissions/pageAccess/sourcePermissions)
- [x] `POST /auth/change-password` (revokes sessions)
- [x] `POST /auth/forgot-password` (+ `/verify`, `/resend`, `/reset`) — generic responses, hashed single-use codes, TTL, attempt limits, private-chat-only delivery
- [x] `PATCH /auth/profile/avatar`
- [x] `POST /auth/service-token` (Telegram container service JWT)
- [x] Rate limits (login, refresh, recovery) via Redis
- [x] Role/permission enforcement + `SuperAdmin`/`ALL_PAGES` bypass
- [x] No cookie sessions / CSRF / tenant claims / end-user API keys

## Rental business transactions

- [x] Create rentals: Active customer, locked motorcycle rows, Available-only,
      collision-safe numbering, pricing tiers, discount/tax/deposit/initial
      payment, motorcycles → Progressing, payments, audit, outbox, atomic commit
- [x] Complete rental: locks, duplicate-completion guard, return charges, final
      payment, balance recalculation, Completed status, return metadata,
      motorcycle → Available/Maintenance, audit + outbox, atomic commit
- [x] Cancel rental: only Active/Overdue, frees motorcycle
- [x] Overdue detection: on-list refresh + Beat scan, single notification per rental
- [x] Decimal-safe money everywhere (`Numeric(14,2)`, ROUND_HALF_UP)

## API surface (`/api/v2`)

- [x] `{ data, meta }` envelope on every response; FastAPI-compatible errors
- [x] CRUD for motorcycles, customers, payments, charges, expenses, users, roles, document sequences, storage providers
- [x] `POST /rentals` (multi-line), `/rentals/{id}/close`, `/rentals/{id}/cancel`, `/rentals/reports`
- [x] List filtering: `q`, `page`, `limit`, `sort` (validated whitelist), `status`, date ranges, entity-specific filters
- [x] `GET /dashboard`, `GET /finance/summary` (income, expenses, net, outstanding, fleet + rental totals, date-range summaries)
- [x] `GET /audit-logs`
- [x] `GET/PUT /settings/app-info`, `/reset`; `GET/PUT /settings/app-config`; email/telegram test-connection endpoints; storage CRUD + test + default/active
- [x] `GET /search`
- [x] `POST/GET/DELETE /exports`, `/exports/{id}/download`, `GET /tasks/{taskId}`
- [x] `/telegram/transactions`, `/telegram/motorcycle-status`, `/telegram/finance-summary`, `/telegram/send-test`, `/telegram/link`
- [x] `/health`, `/health/live`, `/health/ready` (Postgres/Redis/RabbitMQ checks), `/health/workers`

## Redis

- [x] Dashboard/report + settings/reference caches with TTLs and invalidation after mutations
- [x] Refresh-token JTI denylist
- [x] Auth rate limits
- [x] Telegram conversation state, pagination cursors, callback idempotency
- [x] Password recovery codes (hash + TTL + attempts) and delivery envelopes
- [x] Celery result backend
- [x] Task idempotency keys
- [x] PostgreSQL fallback when Redis is unavailable (cache/rate-limit features degrade)

## RabbitMQ / Celery / outbox

- [x] Durable topic exchange + queues (`critical`, `telegram`, `exports`, `reports`, `maintenance`) + DLQs
- [x] Task routing per queue, JSON-only serialization, publisher confirms, `acks_late`, prefetch limits
- [x] Celery Beat: overdue scan, outbox dispatch, daily summary, cleanup, dashboard precompute
- [x] Bounded retries with exponential backoff + jitter (BaseTask)
- [x] Idempotent Telegram delivery (Redis SET NX per event id)
- [x] Outbox dispatcher + reconciliation via pending scan; transactional outbox writes
- [x] CSV/XLSX export generation with progress + expiring downloads

## Telegram bot

- [x] Separate container (`Dockerfile.telegram`), polling mode
- [x] Service-JWT API client with auto-refresh; no direct PostgreSQL access
- [x] English + Khmer messages; localization-driven date/time/number/currency formatting
- [x] Main keyboard: transactions, motorcycle status, income/expense, account help
- [x] Period presets + custom range flow (Redis state with TTL)
- [x] Pagination cursors, idempotent callbacks
- [x] `/link CODE` account linking (service-authenticated API call)
- [x] Password-reset codes delivered only to linked private chats

## Docker & operations

- [x] `Dockerfile` (API + workers), `Dockerfile.telegram`
- [x] `docker-compose.yml`: db, redis, api, worker-telegram, telegram-bot, frontend (no RabbitMQ / MinIO / Beat scheduler)
- [x] Health checks for all infrastructure services + API container healthcheck
- [x] Persistent volumes (pgdata, redisdata, appdata)
- [x] Dependency-based startup ordering; api runs migrations + seed before serving
- [x] `.env.example` with development-only credentials
- [x] Idempotent seed: roles/permissions, admin + demo users, document sequences, settings, demo fleet/customers

## Tests (83 passed)

- [x] Pricing tiers, money rounding, allocation, discounts
- [x] Rental creation, double-rental prevention, completion, cancellation
- [x] Payments, charges, expenses, balances
- [x] Overdue detection (API read path + service, single notification)
- [x] Auth: login, rotation, reuse/family revocation, logout, change-password
- [x] Permission enforcement (staff/viewer boundaries)
- [x] Password recovery (generic responses, bad-code rejection, link flow)
- [x] Pagination, filtering, sort validation
- [x] Settings: app-info, app-config masking, storage, sequences, search
- [x] Outbox write + pending/publish flow, task progress upsert
- [x] Export request validation + status flow
- [x] Telegram API/service boundary (service JWT scope limits, link flow, formatter, API client)
- [x] Health endpoints + OpenAPI generation

## Verification log

| Check | Result |
|-------|--------|
| `pytest` (83 tests, local temp Postgres+Redis+RabbitMQ) | PASS |
| `docker compose config` (repository root) | PASS |
| `docker compose build` (repository root) | PASS (api + telegram images) |
| `docker compose up -d` (repository root; all 9 services healthy) | PASS |
| `alembic upgrade head` (in api container) | PASS |
| `pytest` (in api container, 83 tests) | PASS |
| `/health/live`, `/health/ready` (postgres/redis/celery_broker) | PASS |
| `/health/workers` (3 Celery workers respond to ping) | PASS |
| Auth flow (login → me → refresh → logout) over HTTP | PASS |
| Full rental lifecycle (create → Progressing → close → Completed → Available) over HTTP | PASS |
| Outbox events published to RabbitMQ by dispatcher; Telegram worker consumed them | PASS |
| Celery Beat schedules firing (dispatch-outbox, overdue scan, precompute-dashboard) | PASS |
| Export flow: 202 → queued → completed → CSV download (1753 bytes) | PASS |
| Service-token flow (bot boundary: reports readable, mutations denied) | PASS |
| OpenAPI generation (69 paths) | PASS |
| Telegram bot container healthy (idle until `TELEGRAM_BOT_TOKEN` is set) | PASS |

## Known gaps / incomplete items

- PDF export format is not implemented (frontend export contract only uses
  CSV; XLSX included).
- Email sending is not implemented (SMTP settings + TCP connection test only;
  no notification email channel yet).
- Telegram webhook mode is stubbed in settings; the bot container ships with
  polling mode only.
- The Telegram bot pagination cursor buttons are stored but inline pagination
  for long transaction lists is only partially wired (page state stored,
  next/prev rendering pending).
- Worker health endpoint reports Celery ping/stats but not queue depth or
  oldest-task age.
