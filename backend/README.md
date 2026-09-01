# HollyWing Motor Backend

FastAPI + PostgreSQL + Redis + RabbitMQ + Celery backend for the HollyWing Motor
motorcycle rental system. Implements the `/api/v2` contract expected by the
Nuxt frontend under `frontend/` (see `docs/BACKEND_IMPLEMENTATION_PLAN.md` and
`docs/GLM_SYSTEM_GUIDE.md`).

## Quick start

```bash
cd backend
cp .env.example .env
docker compose up -d --build
```

The API container runs `alembic upgrade head`, seeds development data, and
starts uvicorn on http://localhost:8000 (Swagger at `/docs`).

Then run the frontend from the repo root:

```bash
cp .env.example .env   # set NUXT_PUBLIC_USE_MOCK_DATA=false, NUXT_PUBLIC_API_BASE=http://localhost:8000
pnpm dev
```

## Development logins (development-only)

| Email | Password | Role |
|-------|----------|------|
| `admin@gmail.com` | `123456` | SuperAdmin (all permissions) |
| `staff@example.com` | `123456` | Rental Staff |
| `viewer@example.com` | `123456` | Report Viewer (read-only) |

All values come from `SEED_ADMIN_*` / seed constants in `.env` and must be
changed before any real deployment. Seeded demo motorcycles (`mc-001`…`mc-012`)
and demo customers are also development-only.

## Services

| Service | Purpose |
|---------|---------|
| `api` | FastAPI on :8000, migrations + seed on boot |
| `db` | PostgreSQL 16 on :5432 (authoritative store) |
| `redis` | Redis 7 on :6379 — cache, denylist, rate limits, bot state |
| `rabbitmq` | RabbitMQ 4 on :5672, management UI on :15672 (local only) |
| `worker-default` | Celery worker for `reports` + `maintenance` queues |
| `worker-telegram` | Celery worker for `critical` + `telegram` queues |
| `worker-export` | Celery worker for `exports` queue |
| `scheduler` | Celery Beat (overdue scans, outbox dispatch, summaries, cleanup) |
| `telegram-bot` | Telegram bot (polling), talks to the API with service JWTs only |

## Architecture

```
app/
├── api/v2/        thin routers (validation + one service call each)
├── core/          config, security (JWT/argon2), pricing, money, redis, errors
├── models/        SQLAlchemy 2 persistence models
├── schemas/       Pydantic v2 request/response contracts (camelCase aliases)
├── repositories/  SQLAlchemy query composition only (no commits, no Telegram)
├── services/      business transactions, authorization, cache invalidation
├── tasks/         Celery app, queues, routing, beat schedule, tasks
├── utils/         date period parsing helpers
└── seed.py        idempotent development seed
telegram_bot/      separate bot process (service JWT, Redis conversation state)
alembic/           migrations (initial schema: ab57577973e4)
tests/             unit / api / tasks / telegram test suites
```

Response envelope for every endpoint:

```json
{ "data": { }, "meta": { "page": 1, "limit": 20, "total": 1 } }
```

Errors use `{"detail": {"code": "...", "message": "..."}}` compatible with
FastAPI's `detail` field. All request/response bodies use camelCase JSON.

### Key business transactions

- **Rental creation** (`POST /api/v2/rentals`): validates an Active customer,
  locks motorcycle rows `FOR UPDATE`, rejects non-Available motorcycles,
  generates `RNT-{year}-{seq}` numbers from `document_sequences`, applies the
  pricing tiers (1 / 3 / 7 / 28–31 days, else daily × days), distributes the
  document discount across lines, records the initial payment, sets motorcycles
  to `Progressing`, writes audit logs + outbox events, and commits atomically.
- **Rental completion** (`POST /api/v2/rentals/{id}/close`): locks the rental +
  motorcycle, adds return charges and the final payment, recomputes
  `paid / additional_charges / total_due / outstanding`, sets the rental to
  `Completed` and the motorcycle to `Available` (or `Maintenance`), writes audit
  + outbox events atomically.
- **Cancellation** (`POST /api/v2/rentals/{id}/cancel`): only from
  Active/Overdue; frees the motorcycle.
- **Overdue detection**: `Active` rentals past `due_date` become `Overdue` on
  list reads and via the Celery Beat scan; each newly overdue rental emits one
  notification event.

Money is stored as PostgreSQL `Numeric(14,2)` and computed with Python
`Decimal` (ROUND_HALF_UP). No floating-point money anywhere.

### Auth

- Bearer access JWT (15 min) + rotating refresh JWT (7 days, one-time use).
- Refresh-token JTI denylist in Redis; reuse of a rotated/revoked refresh token
  revokes the whole token family.
- Argon2id password hashes. No cookie sessions, CSRF tokens, or API keys.
- Permission checks on every route (e.g. `rental.rentals.create`); `SuperAdmin`
  role or `ALL_PAGES` bypasses.
- Login/refresh/password-recovery rate limits via Redis (degrade gracefully if
  Redis is down).
- Telegram password recovery: single-use hashed six-digit codes in Redis with
  TTL and attempt limits; delivery goes to the linked private chat only through
  the `critical` queue; successful reset revokes all refresh tokens.

### Redis usage

Dashboard/report/settings caches (invalidated after mutations), refresh-token
denylist, auth rate limits, password-recovery challenges, Telegram link codes
and conversation state, Celery result backend, task idempotency keys, export
progress. PostgreSQL remains authoritative; reads fall back to the database
when Redis is unavailable.

### RabbitMQ / Celery / outbox

Durable topic exchange `rental.tasks` with queues `critical`, `telegram`,
`exports`, `reports`, `maintenance` plus per-queue DLQs. Business mutations
write `outbox_events` rows in the same PostgreSQL transaction; the dispatcher
publishes them with publisher confirms and marks them published. Telegram
delivery is idempotent per event id (Redis `SET NX`), retried with exponential
backoff, and dead-letters after bounded retries. Beat schedules: overdue scan
(5 min), outbox dispatch (30 s), daily summary, cleanup (6 h), dashboard
precompute (2 min).

### Exports

`POST /api/v2/exports` validates the request, persists an `export_jobs` row +
task-progress record, enqueues to the `exports` queue, and returns `202` with a
task id. `GET /api/v2/tasks/{taskId}` exposes safe progress; downloads are
available until expiry from `GET /api/v2/exports/{id}/download`.

## Commands

```bash
# all tests (requires Postgres/Redis/RabbitMQ reachable; see tests/conftest.py)
docker compose exec api pytest

# migrations
docker compose exec api alembic upgrade head
docker compose exec api alembic revision --autogenerate -m "change"

# reseed (idempotent)
docker compose exec api python -m app.seed
```

Local test run against temporary services:

```bash
docker run -d --name pg -e POSTGRES_USER=rental -e POSTGRES_PASSWORD=rental -e POSTGRES_DB=rental_moto -p 55432:5432 postgres:16-alpine
docker run -d --name redis -p 56379:6379 redis:7-alpine
docker run -d --name rmq -e RABBITMQ_DEFAULT_USER=rental -e RABBITMQ_DEFAULT_PASS=rental -e RABBITMQ_DEFAULT_VHOST=rental -p 55672:5672 rabbitmq:4-management-alpine
pip install -r requirements.txt -r requirements-dev.txt
pytest   # conftest defaults to the ports above
```

## Telegram bot

Set `TELEGRAM_BOT_TOKEN` in `backend/.env` and `docker compose up telegram-bot`.
The bot exchanges `TELEGRAM_BOT_CLIENT_ID`/`_SECRET` for a short-lived service
JWT (`POST /api/v2/auth/service-token`) and never touches PostgreSQL. It
supports the documented main keyboard (transactions, motorcycle status,
income/expense, account help), period presets (today / 3 days / 7 days /
1 month / custom range), Redis-backed conversation state and pagination, and
`/link CODE` account linking. English and Khmer messages follow the
localization settings from app-config.

## Assumptions and decisions

- **IDs**: business records keep string IDs matching the frontend seed format
  (`mc-001`, `rc-001`, `rt-001`…). New IDs are generated from persisted
  sequence counters so deleted IDs are never reused. Users/roles use integer
  PKs (frontend `AuthUser.id` is numeric).
- **Multi-motorcycle rentals**: one API call with `lines[]`; each line creates
  one rental record (matches the mock data model, per plan §13).
- **Rental totals**: `rental_charge = tier_charge − discount`;
  `total_due = rental_charge + tax + late_fee + additional_charges`;
  `outstanding = max(total_due − paid, 0)`. Document-level discounts and the
  initial payment are distributed across lines proportionally (last line gets
  the remainder), matching the frontend helpers in `utils/rental/pricing.ts`.
- **Password recovery** stores only code hashes in Redis; the plaintext code is
  placed in a separate short-lived Redis delivery value that the Telegram
  worker consumes atomically (GET-then-DELETE), so task messages never carry
  codes.
- **Email config test** performs a TCP connect to the configured SMTP host; it
  does not send real mail in development.
- Demo seed emails use `staff@example.com` / `viewer@example.com` because the
  login schema validates real email domains (`.local` is rejected).

## Implementation status

See `IMPLEMENTATION_STATUS.md` for the feature checklist and verification log.
