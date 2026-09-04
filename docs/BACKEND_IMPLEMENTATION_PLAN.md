# HollyWing Motor — Backend Implementation Plan

> **Status:** Plan only — no backend code yet.  
> **Goal:** FastAPI + PostgreSQL + Redis + RabbitMQ services in Docker; frontend stays on local computer (`pnpm dev`).  
> **Audience:** Developers and AI assistants (e.g. GLM 5.3 Flash). See also [`GLM_SYSTEM_GUIDE.md`](./GLM_SYSTEM_GUIDE.md) for full system context.

---

## 1. Summary

| Item | Decision |
|------|----------|
| Backend framework | **FastAPI** (Python 3.12) |
| Database | **PostgreSQL 16** |
| Cache | **Redis 7** for short-lived query caching, rate limits, and token denylisting |
| Task broker | **RabbitMQ 4** for durable Telegram, export, report, and scheduled jobs |
| Task runtime | **Celery workers + Celery Beat**; Redis stores task-result/status projections |
| ORM | **SQLAlchemy 2** + **Alembic** migrations |
| Auth | **JWT bearer tokens only** — short-lived access token + rotating refresh token |
| Deployment | **Docker Compose** — API, PostgreSQL, Redis, RabbitMQ, workers, scheduler, and Telegram bot |
| Frontend | Runs locally at `http://localhost:3000`, calls `http://localhost:8000` |
| API version | `/api/v2/*` (already defined in frontend constants) |

---

## 2. Current Frontend State (What the Backend Must Support)

The Nuxt 4 frontend today is **mock-first**:

- All rental data lives in **Pinia + localStorage** (`app/stores/app-data.ts`)
- `NUXT_PUBLIC_USE_MOCK_DATA=true` by default
- HTTP client is ready (`app/composables/useApi.ts`); API mode must attach `Authorization: Bearer <access_token>`
- Only **settings** repos have HTTP implementations; rental CRUD has none yet

**Backend work = two parts:**

1. Build the API server
2. Wire frontend repositories (later phase) to replace mock store for each collection

---

## 3. Target Architecture

```
┌──────────────────────────────────────┐
│  Developer machine                   │
│                                      │
│  ┌────────────────────────────────┐  │
│  │  Nuxt frontend (pnpm dev)      │  │
│  │  localhost:3000                │  │
│  └───────────────┬────────────────┘  │
│                  │ HTTP + JWT bearer  │
│  ┌───────────────▼────────────────┐  │
│  │  Docker Compose                │  │
│  │  ┌──────────┐  ┌────────────┐  │  │
│  │  │ FastAPI  │──│ PostgreSQL │  │  │
│  │  │ :8000    │  │ :5432      │  │  │
│  │  └────┬─────┘  └────────────┘  │  │
│  │       ├───────── Redis :6379    │  │
│  │       └──── RabbitMQ :5672      │  │
│  │            Celery workers/beat  │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
```

### Planned folder structure (when implementation starts)

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # App factory, lifespan, middleware, routers
│   ├── config.py                   # Typed environment settings
│   ├── database.py                 # Async SQLAlchemy engine/session
│   ├── cache.py                    # Redis connection and cache primitives
│   │
│   ├── models/                     # Persistence models only
│   │   ├── __init__.py
│   │   ├── base.py                 # Base, timestamps, created_by_user_id
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── motorcycle.py
│   │   ├── customer.py
│   │   ├── rental.py
│   │   ├── payment.py
│   │   ├── charge.py
│   │   ├── expense.py
│   │   ├── document_sequence.py
│   │   ├── audit_log.py
│   │   ├── export_job.py
│   │   ├── outbox_event.py
│   │   └── setting.py
│   │
│   ├── schemas/                    # Pydantic API contracts
│   │   ├── __init__.py
│   │   ├── common.py               # Response envelope, pagination, date range
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── role.py
│   │   ├── motorcycle.py
│   │   ├── customer.py
│   │   ├── rental.py
│   │   ├── payment.py
│   │   ├── charge.py
│   │   ├── expense.py
│   │   ├── dashboard.py
│   │   ├── telegram.py
│   │   ├── export.py
│   │   ├── task.py
│   │   └── setting.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                 # DB, Redis, JWT user/service dependencies
│   │   └── v2/
│   │       ├── __init__.py
│   │       ├── router.py           # Single v2 router composition point
│   │       ├── health.py
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── roles.py
│   │       ├── motorcycles.py
│   │       ├── customers.py
│   │       ├── rentals.py
│   │       ├── payments.py
│   │       ├── charges.py
│   │       ├── expenses.py
│   │       ├── dashboard.py
│   │       ├── audit_logs.py
│   │       ├── document_sequences.py
│   │       ├── exports.py
│   │       ├── tasks.py
│   │       ├── telegram.py
│   │       └── settings.py
│   │
│   ├── services/                    # Transactions and business rules
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── user_service.py
│   │   ├── motorcycle_service.py
│   │   ├── customer_service.py
│   │   ├── rental_service.py
│   │   ├── payment_service.py
│   │   ├── charge_service.py
│   │   ├── expense_service.py
│   │   ├── role_service.py
│   │   ├── document_sequence_service.py
│   │   ├── audit_service.py
│   │   ├── export_service.py
│   │   ├── task_service.py
│   │   ├── dashboard_service.py
│   │   ├── notification_service.py
│   │   ├── telegram_service.py
│   │   └── setting_service.py
│   │
│   ├── repositories/                # Reusable database queries only
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── user_repository.py
│   │   ├── motorcycle_repository.py
│   │   ├── customer_repository.py
│   │   ├── rental_repository.py
│   │   ├── payment_repository.py
│   │   ├── charge_repository.py
│   │   ├── expense_repository.py
│   │   ├── role_repository.py
│   │   ├── document_sequence_repository.py
│   │   ├── audit_repository.py
│   │   ├── export_repository.py
│   │   ├── outbox_repository.py
│   │   └── setting_repository.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py             # JWT, password hashing, reset tokens
│   │   ├── permissions.py
│   │   ├── pricing.py              # Port of frontend rental pricing
│   │   ├── exceptions.py
│   │   └── logging.py
│   │
│   ├── tasks/                       # Celery tasks delivered by RabbitMQ
│   │   ├── __init__.py
│   │   ├── celery_app.py            # Broker, routes, retries, serialization
│   │   ├── base.py                  # Idempotency + correlation ids
│   │   ├── overdue_rentals.py
│   │   ├── telegram_notifications.py
│   │   ├── exports.py
│   │   ├── reports.py
│   │   ├── file_processing.py
│   │   ├── outbox_dispatcher.py
│   │   └── scheduled_summaries.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── dates.py
│   │   ├── money.py
│   │   ├── pagination.py
│   │   └── idempotency.py
│   └── seed.py                     # Idempotent demo data loader
│
├── telegram_bot/
│   ├── __init__.py
│   ├── main.py                     # Bot lifespan, polling/webhook startup
│   ├── api_client.py               # FastAPI client + service JWT refresh
│   ├── handlers.py
│   ├── keyboards.py
│   ├── reports.py
│   ├── formatter.py
│   └── state.py                    # Redis conversation and pagination state
│
├── tests/
│   ├── conftest.py                 # Isolated DB/Redis fixtures
│   ├── factories.py
│   ├── unit/
│   │   ├── test_pricing.py
│   │   └── test_money.py
│   ├── api/
│   │   ├── test_auth.py
│   │   ├── test_motorcycles.py
│   │   ├── test_customers.py
│   │   ├── test_rentals.py
│   │   └── test_payments.py
│   └── telegram/
│       ├── test_handlers.py
│       └── test_reports.py
│
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── scripts/
│   ├── wait_for_services.py
│   └── create_admin.py
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── Dockerfile.telegram
├── .dockerignore
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml                  # Ruff, mypy, pytest configuration
├── .env.example
├── .gitignore
└── README.md
```

Use the real Python filename `__init__.py`; the `**init**.py` spelling in formatted examples is not valid. Keep `/api/v2` because it already matches the frontend endpoint constants. If a future breaking API is needed, add `v3` beside `v2` instead of renaming the current contract.

### Layer responsibilities

- **API routers:** validate requests, resolve dependencies, call one service, return a schema. No SQL and no pricing logic.
- **Services:** own transactions, permissions, rental state transitions, cache invalidation, audit events, and notification enqueueing.
- **Repositories:** contain SQLAlchemy query composition only; they do not commit transactions or call Telegram.
- **Models:** describe persistence; **schemas** describe public API contracts. Never return ORM objects directly.
- **Tasks:** Celery workers consume RabbitMQ queues for exports, reports, overdue scans, scheduled summaries, and retryable Telegram delivery outside request latency.
- **Telegram bot:** handles Telegram updates and presentation, but obtains all business data through JWT-protected FastAPI endpoints.

---

## 4. Database Schema Plan

### 4.1 Core tables

| Table | Maps to frontend collection | Key fields |
|-------|----------------------------|------------|
| `users` | `users` | id, email, password_hash, role, permissions (JSONB), status, telegram_user_id, telegram_chat_id, telegram_linked_at |
| `motorcycles` | `motorcycles` | id, code, model, brand, plate, rates, status |
| `rental_customers` | `rentalCustomers` | id, code, full_name, identity_*, phone, status |
| `rentals` | `rentals` | id, rental_no, customer_id, motorcycle_id, dates, amounts, status |
| `rental_payments` | `rentalPayments` | id, payment_no, rental_id, amount, paid_at |
| `rental_charges` | `rentalCharges` | id, charge_no, rental_id, charge_type, amount |
| `rental_expenses` | `rentalExpenses` | id, expense_no, date, expense_type, amount |
| `audit_logs` | `auditLogs` | id, occurred_at, user, action, entity_type, entity_id |
| `document_sequences` | `documentSequences` | id, document_type, prefix, last_value, year |
| `export_jobs` | export dialog/history | id, user_id, resource, format, filters, status, progress, file_key, expires_at |
| `outbox_events` | internal delivery guarantee | id, event_type, payload, queue, status, attempts, available_at, published_at |
| `app_settings` | settings | key-value JSON for app-info, app-config, storage |

### 4.2 Enums (PostgreSQL or check constraints)

**Motorcycle status:** `Available`, `Progressing`, `Maintenance`

**Customer status:** `Active`, `Inactive`

**Rental status:** `Active`, `Overdue`, `Completed`, `Cancelled`

**Payment method:** `Cash`, `Bank Transfer`, `Card`, `QR Payment`

**Charge type:** `Damage`, `Lost item`, `Cleaning`, `Other`

**Expense type:** `Fuel`, `Maintenance`, `Salary`, `Rent`, `Marketing`, `Other`

### 4.3 Record metadata

Business records use `created_by_user_id` where audit ownership matters, plus `created_at` and `updated_at`. This is a single-business system: do not create organization, branch, tenant, or tenant-scope columns and do not add tenant filters to queries.

### 4.4 ID strategy

Frontend uses string IDs like `mc-001`, `rt-001`. Options:

| Option | Pros | Cons |
|--------|------|------|
| **A. Keep string IDs** | Exact match with frontend seed | Less conventional |
| **B. UUID strings** | Standard, no collision | Frontend must adapt |
| **C. Integer PK + external code** | Clean DB | More mapping in API |

**Recommendation:** Option **A** for phase 1 (minimal frontend change). Use `VARCHAR` primary keys matching existing seed format.

### 4.5 Document numbering

| Document | Prefix | Example |
|----------|--------|---------|
| Rental | `RNT-{year}-` | RNT-2026-000001 |
| Payment | `RNP-` | RNP-000001 |
| Charge | `RNC-` | RNC-000001 |
| Expense | `RNX-` | RNX-000001 |
| Customer | `CUS-` | CUS-001 |
| Motorcycle | `MC-` | MC-001 |

Implement a `document_sequences` table + atomic increment (same idea as frontend `document-sequences.ts`).

---

## 5. API Endpoints Plan

Base: `http://localhost:8000`  
Response wrapper (matches frontend `ApiResponse<T>`):

```json
{
  "data": { },
  "meta": { "page": 1, "limit": 20, "total": 100 }
}
```

### 5.1 Auth (`/api/v2/auth/*`)

Already defined in `app/utils/constants/api-endpoints.ts`:

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/v2/auth/login` | Body: `{ email, password }`; return access token, refresh token, token type, and expiry |
| POST | `/api/v2/auth/refresh` | Rotate refresh token and return a fresh token pair |
| POST | `/api/v2/auth/logout` | Revoke the refresh token/JTI in Redis until its expiry |
| GET | `/api/v2/auth/me` | Return `AuthUser` shape from `app/types/auth-user.ts` |
| POST | `/api/v2/auth/forgot-password` | Phase 3 (optional) |
| POST | `/api/v2/auth/forgot-password/reset` | Phase 3 (optional) |
| POST | `/api/v2/auth/change-password` | Phase 2 |

**AuthUser response fields:** `id`, `name`, `email`, `role`, `avatar`, `permissions[]`, `pageAccess[]`, `sourcePermissions[]`

**Demo seed user:** `admin@gmail.com` / `123456` (from `mock-login.ts`)

### 5.2 Rental CRUD (new — not in frontend constants yet)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v2/motorcycles` | List + `?q=&page=&limit=&status=` |
| GET | `/api/v2/motorcycles/{id}` | Single record |
| POST | `/api/v2/motorcycles` | Create |
| PUT | `/api/v2/motorcycles/{id}` | Update |
| DELETE | `/api/v2/motorcycles/{id}` | Delete (only if not Progressing) |
| PATCH | `/api/v2/motorcycles/{id}/status` | Set Maintenance / Available |

Same CRUD pattern for:

- `/api/v2/customers`
- `/api/v2/rentals`
- `/api/v2/payments`
- `/api/v2/charges`
- `/api/v2/expenses`

### 5.3 Rental business actions

| Method | Path | Body | Business logic |
|--------|------|------|----------------|
| POST | `/api/v2/rentals` | customer_id, lines[], paid_amount | Create rental(s), set moto → Progressing |
| POST | `/api/v2/rentals/{id}/close` | return_date, condition, charges[], final_payment | Complete rental, moto → Available |
| GET | `/api/v2/rentals` | `?status=Active,Overdue` | Rentals page filter |
| GET | `/api/v2/rentals/reports` | `?status=Completed` | Rental reports page |

### 5.4 Dashboard & finance

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/v2/dashboard` | Fleet KPIs, rentals-by-day, finance summary |
| GET | `/api/v2/finance/summary` | Income, expense, outstanding for date range |

### 5.5 Admin (phase 2–3)

| Method | Path |
|--------|------|
| CRUD | `/api/v2/users` |
| CRUD | `/api/v2/roles` |
| GET | `/api/v2/audit-logs` |
| CRUD | `/api/v2/document-sequences` |

### 5.6 Settings (phase 2 — frontend already expects these)

| Method | Path |
|--------|------|
| GET/PUT | `/api/v2/settings/app-info` |
| GET/PUT | `/api/v2/settings/app-config` |
| CRUD | `/api/v2/settings/storage` |
| GET | `/api/v2/search` |

### 5.7 Telegram bot service

The Telegram bot runs as its own Docker service and calls FastAPI over the internal Docker network. It authenticates with a short-lived **service JWT** obtained using bot client credentials; it does not read PostgreSQL directly.

Main keyboard:

| Button | Result |
|--------|--------|
| `📋 All Rental Transactions` | Rental creations, payments, additional charges, returns/completions, cancellations, and overdue events, grouped by rental number |
| `🏍 Motorcycle Status` | Counts and grouped motorcycle lists for Available, Progressing, and Maintenance |
| `💰 Income / Expense` | Income, expense, net balance, and outstanding amount for the selected date period |
| `🔐 Account Help` | Safe instructions for linking Telegram and receiving a password-reset code |

Report period keyboard shared by transactions and finance:

- Today
- Last 3 days (inclusive)
- Last 7 days (inclusive)
- Last 1 month / 30 days
- Custom date range: bot asks for start date, then end date

Redis stores custom-range conversation state with a short TTL, callback idempotency keys, rate-limit counters, and paginated report cursors. Report queries always use the configured localization settings: language, timezone, date/time format, currency, and number format.

Bot/API endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v2/auth/service-token` | Exchange Telegram bot client credentials for a short-lived service JWT |
| POST | `/api/v2/telegram/webhook` | Receive Telegram updates in production |
| GET | `/api/v2/telegram/transactions` | Rental transaction report with `period`, `start`, and `end` filters |
| GET | `/api/v2/telegram/motorcycle-status` | Grouped fleet status summary |
| GET | `/api/v2/telegram/finance-summary` | Income/expense/net/outstanding date summary |
| POST | `/api/v2/telegram/send-test` | Admin connection test |

All report routes require a JWT permission claim such as `telegram.reports.read`. Mutation events write an outbox event in the same PostgreSQL transaction; the dispatcher publishes it to RabbitMQ so API requests are not delayed by Telegram delivery.

### 5.8 Export and task status

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v2/exports` | Validate an export request, persist `export_jobs`, enqueue to RabbitMQ, return `202` + task id |
| GET | `/api/v2/exports/{id}` | Export metadata, progress, status, and expiry |
| GET | `/api/v2/exports/{id}/download` | Signed download URL when complete |
| DELETE | `/api/v2/exports/{id}` | Cancel queued work or delete an expired result |
| GET | `/api/v2/tasks/{taskId}` | Generic safe task status for frontend polling |

Export workers apply the exact requester permissions captured by user id and re-check access before reading data. Generated files go to the configured storage provider, not RabbitMQ or Redis.

---

## 6. Business Rules to Implement in Backend

Port logic from frontend — **single source of truth should eventually be backend**.

### 6.1 Pricing (`app/utils/rental/pricing.ts`)

Staff pick **1 day / 3 days / 1 week / 1 month**. Motorcycle package rates apply. **1 month** is a calendar month (same day next month; Jan 31 → Feb 28/29), not a fixed 30-day count.

| Duration | Rate |
|-----------------|------|
| 1 day | daily_rate |
| 3 days | three_day_rate |
| 7 days | weekly_rate |
| Exact calendar month(s) | monthly_rate × months |
| 28–31 days (not an exact calendar month) | monthly_rate |
| other | daily_rate × days |

### 6.2 Rental lifecycle

```
Create rental:
  1. Validate customer.status == Active
  2. Validate motorcycle.status == Available
  3. Compute charge from pricing tiers
  4. Generate rental_no (RNT-{year}-{seq})
  5. Save rental (status = Active)
  6. Set motorcycle.status = Progressing
  7. If paid > 0 → create rental_payment
  8. Write audit_log

Close rental:
  1. Add optional charges → rental_charges
  2. Record final payment → rental_payments
  3. Recompute paid, total_due, outstanding
  4. Set rental.status = Completed, return_date
  5. Set motorcycle.status = Available
  6. Write audit_log

Overdue job (cron or on-read):
  If status == Active AND due_date < now → status = Overdue
```

### 6.3 Delete rules

| Entity | Can delete when |
|--------|-----------------|
| Customer | status == Inactive, no active rentals |
| Motorcycle | status != Progressing |
| Rental | status == Cancelled only |

### 6.4 Telegram transaction notifications

After a database transaction commits, enqueue a Telegram event for:

- rental created, overdue, completed/returned, or cancelled;
- payment recorded;
- customer charge recorded;
- operating expense recorded.

Messages include the rental/reference number, customer or expense description, motorcycle, amount/currency, status, actor, and localized timestamp as applicable. Use an event id as the Redis idempotency key so retries cannot send the same message twice. Delivery failure never rolls back the rental transaction; retry with bounded exponential backoff and record the final delivery state.

---

## 7. Auth & Security Plan

| Topic | Plan |
|-------|------|
| Authentication | `Authorization: Bearer <access_token>` on protected routes |
| Tokens | Signed JWT access token (15 minutes) + rotating refresh token (7 days) |
| Revocation | Store revoked refresh-token JTIs in Redis with TTL equal to remaining token lifetime |
| Password storage | Argon2id (preferred) or bcrypt; never store plaintext passwords |
| CSRF | Not required because authentication is not cookie-based |
| CORS | Allow the configured frontend origins; credentials are not required |
| Permissions | Check permission key on each route (e.g. `rental.rentals.create`) |

JWT is the only authentication mechanism. Do not implement server sessions, auth cookies, API keys, or organization/branch claims. Redis supports revocation and rate limiting but is not an authentication source of truth.

### 7.1 Telegram password recovery

1. An application user links an approved private Telegram chat to their account; an administrator can revoke the link.
   Recommended flow: the signed-in user requests a short-lived link code in the app, then sends `/link CODE` to the bot in a private chat. The API validates and consumes the code before storing the Telegram ids.
2. `/auth/forgot-password` always returns the same generic response to prevent account enumeration.
3. If the account is active, linked, and Telegram recovery is enabled, generate a cryptographically random six-digit code.
4. Store only a hash of the reset code in Redis with the configured TTL (default 10 minutes), attempt counter, and one-time-use flag.
5. Send the code only to the linked private Telegram chat—never to a group or channel.
6. Verification issues a short-lived, single-use password-reset JWT. The reset endpoint accepts that JWT plus the new password.
7. Successful reset deletes the Redis challenge, revokes the user’s refresh tokens, and writes an audit event.

Limit request/resend/verify attempts by account and IP. Telegram messages must never include the existing password, refresh token, or access token.

### 7.2 Redis cache policy

- Cache read-heavy dashboard, report, settings, and reference responses with explicit TTLs (typically 30–300 seconds).
- Use namespaced keys such as `rental:dashboard:v1:{filter_hash}`.
- Invalidate related keys after create, update, close-rental, payment, charge, expense, and settings mutations.
- Never cache passwords, raw JWTs, refresh tokens, or sensitive settings.
- If Redis is unavailable, normal database reads must continue; only caching/rate-limit features may degrade.

### 7.3 RabbitMQ task architecture

RabbitMQ is the durable broker; Redis is not used as the task queue. Celery uses JSON serialization only and routes tasks to dedicated queues:

| Queue | Tasks | Priority |
|-------|-------|----------|
| `critical` | Telegram password-reset delivery and security alerts | Highest |
| `telegram` | Rental/payment/charge/expense notifications and test messages | High |
| `exports` | CSV/XLSX/PDF generation and large report files | Normal |
| `reports` | Dashboard/report precomputation and scheduled summaries | Normal |
| `maintenance` | Overdue scans, cleanup, cache warming, file processing | Low |

Use durable topic exchanges (`rental.tasks`, `rental.events`), durable queues, persistent messages, publisher confirms, manual acknowledgements, prefetch limits, and queue-specific concurrency. Each work queue has retry routing with exponential backoff and a dead-letter queue such as `telegram.dlq` or `exports.dlq`.

Task rules:

- API responses return `202 Accepted` with `taskId` for long-running exports/reports.
- `GET /api/v2/tasks/{taskId}` returns queued/running/completed/failed progress without exposing Celery internals.
- `GET /api/v2/exports/{id}/download` returns a signed, expiring file URL only after completion.
- Workers receive record IDs and small immutable metadata—not complete database rows or secrets.
- Tasks are idempotent by business event/export id and safe to execute more than once.
- Store durable business status in PostgreSQL; Redis may mirror short-lived progress for fast polling.
- Never send raw JWTs, passwords, bot tokens, or reset codes through task messages. A password-reset task carries only a challenge id; the Telegram worker atomically reads and deletes a separately encrypted, very-short-lived delivery value from Redis while verification retains only the code hash.

### 7.4 Transactional outbox

When a rental/payment/charge/expense mutation commits, insert its `outbox_events` row in the same database transaction. A dispatcher publishes unpublished events to RabbitMQ with publisher confirms, then marks them published. This prevents the failure where PostgreSQL commits but a Telegram/export task is never queued. A reconciliation task retries stale outbox rows, while consumers still enforce idempotency.

---

## 8. Docker Deployment Plan

### 8.1 `docker-compose.yml` services

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: rental
      POSTGRES_PASSWORD: rental
      POSTGRES_DB: rental_moto
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"   # optional, for local DB tools

  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://rental:rental@db:5432/rental_moto
      REDIS_URL: redis://redis:6379/0
      RABBITMQ_URL: amqp://rental:rental@rabbitmq:5672/rental
      CORS_ORIGINS: http://localhost:3000
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
    command: >
      sh -c "alembic upgrade head &&
             python -m app.seed &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  rabbitmq:
    image: rabbitmq:4-management-alpine
    hostname: rabbitmq
    environment:
      RABBITMQ_DEFAULT_USER: rental
      RABBITMQ_DEFAULT_PASS: rental
      RABBITMQ_DEFAULT_VHOST: rental
    volumes:
      - rabbitmqdata:/var/lib/rabbitmq
    ports:
      - "15672:15672" # local management UI; do not expose publicly
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 5s
      timeout: 5s
      retries: 12

  worker-default:
    build: .
    restart: unless-stopped
    command: celery -A app.tasks.celery_app worker -Q reports,maintenance --loglevel=INFO
    environment:
      DATABASE_URL: postgresql://rental:rental@db:5432/rental_moto
      REDIS_URL: redis://redis:6379/0
      RABBITMQ_URL: amqp://rental:rental@rabbitmq:5672/rental
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  worker-telegram:
    build: .
    restart: unless-stopped
    command: celery -A app.tasks.celery_app worker -Q critical,telegram --concurrency=2 --loglevel=INFO
    environment:
      DATABASE_URL: postgresql://rental:rental@db:5432/rental_moto
      REDIS_URL: redis://redis:6379/0
      RABBITMQ_URL: amqp://rental:rental@rabbitmq:5672/rental
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  worker-export:
    build: .
    restart: unless-stopped
    command: celery -A app.tasks.celery_app worker -Q exports --concurrency=2 --loglevel=INFO
    environment:
      DATABASE_URL: postgresql://rental:rental@db:5432/rental_moto
      REDIS_URL: redis://redis:6379/0
      RABBITMQ_URL: amqp://rental:rental@rabbitmq:5672/rental
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  scheduler:
    build: .
    restart: unless-stopped
    command: celery -A app.tasks.celery_app beat --loglevel=INFO
    environment:
      DATABASE_URL: postgresql://rental:rental@db:5432/rental_moto
      REDIS_URL: redis://redis:6379/0
      RABBITMQ_URL: amqp://rental:rental@rabbitmq:5672/rental
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  telegram-bot:
    build:
      context: .
      dockerfile: Dockerfile.telegram
    restart: unless-stopped
    environment:
      API_INTERNAL_URL: http://api:8000
      REDIS_URL: redis://redis:6379/1
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      TELEGRAM_BOT_MODE: ${TELEGRAM_BOT_MODE:-polling}
      TELEGRAM_BOT_CLIENT_ID: ${TELEGRAM_BOT_CLIENT_ID}
      TELEGRAM_BOT_CLIENT_SECRET: ${TELEGRAM_BOT_CLIENT_SECRET}
    depends_on:
      api:
        condition: service_started
      redis:
        condition: service_healthy

volumes:
  pgdata:
  redisdata:
  rabbitmqdata:
```

### 8.2 Developer workflow

```bash
# Terminal 1 — backend
cd backend
cp .env.example .env
docker compose up

# Terminal 2 — frontend (project root)
cp .env.example .env
# Set NUXT_PUBLIC_USE_MOCK_DATA=false
# Set NUXT_PUBLIC_API_BASE=http://localhost:8000
pnpm dev
```

### 8.3 Health checks

- `GET /health` → `{ "status": "ok" }`
- PostgreSQL, Redis, and RabbitMQ readiness probes in Compose before starting API/workers
- `GET /health/ready` verifies PostgreSQL, Redis, and RabbitMQ connectivity
- `GET /health/workers` reports Celery worker heartbeats, queue depth, and oldest queued task age
- Telegram bot health reports API authentication, Redis, and Telegram `getMe` status

---

## 9. Frontend Integration Plan (After Backend Exists)

### Phase A — Auth only

1. Set `NUXT_PUBLIC_USE_MOCK_DATA=false`
2. Implement HTTP auth in `app/stores/auth.ts` (login → POST `/api/v2/auth/login`)
3. Store tokens using the selected frontend token strategy, attach the bearer access token, and rotate through `/auth/refresh`

### Phase B — Rental entities

For each collection, create `app/repositories/http/{entity}.ts`:

| Collection | New HTTP repo | Replace in |
|--------------|---------------|------------|
| motorcycles | `http/motorcycles.ts` | `app-data` store or composable |
| rentalCustomers | `http/customers.ts` | same |
| rentals | `http/rentals.ts` | `RentalCreatePanel.vue` |
| rentalPayments | `http/payments.ts` | finance page |
| rentalExpenses | `http/expenses.ts` | finance page |

Pattern: copy from existing `app/repositories/http/settings-storage.ts`.

### Phase C — Settings & admin

Wire remaining v2 endpoints already stubbed in frontend.

### Phase D — Remove mock dependency

- Keep mock mode for offline demo (`NUXT_PUBLIC_USE_MOCK_DATA=true`)
- Production / dev-with-backend uses HTTP repos only

---

## 10. Implementation Phases

### Phase 1 — Foundation (MVP backend)

**Goal:** Login + motorcycles + customers + rentals CRUD in Docker

- [ ] Docker Compose (API + PostgreSQL + Redis + RabbitMQ + Celery workers/beat)
- [ ] FastAPI project scaffold
- [ ] Alembic + initial migration (all core tables)
- [ ] Seed script (data from `app/config/rental-seed.ts`)
- [ ] Auth: login, refresh, logout, me (JWT bearer tokens)
- [ ] CRUD: motorcycles, customers
- [ ] Rentals: create, list, get, close
- [ ] CORS + bearer-token middleware
- [ ] Redis client, cache helpers, refresh-token revocation, and auth rate limiting
- [ ] RabbitMQ exchanges/queues, Celery routing, retries, dead-letter queues, and worker health
- [ ] Transactional outbox publisher and reconciliation task
- [ ] Telegram bot container, service JWT, health check, and test-message endpoint
- [ ] Swagger at `/docs`

**Exit criteria:** Frontend can login and list motorcycles from API (manual test via Swagger or curl).

### Phase 2 — Business logic & finance

- [ ] Pricing engine (port `pricing.ts`)
- [ ] Payments, charges, expenses CRUD
- [ ] Dashboard summary endpoint
- [ ] Overdue status update
- [ ] Audit log on mutations
- [ ] Document sequence generator
- [ ] Telegram events for rentals, payments, charges, expenses, overdue, and completion
- [ ] Telegram keyboards for transactions, grouped motorcycle status, and finance date summaries
- [ ] Asynchronous CSV/XLSX/PDF exports with progress and expiring downloads

**Exit criteria:** Full rental create → close flow works via API.

### Phase 3 — Admin & settings

- [ ] Users, roles CRUD
- [ ] Settings endpoints (app-info, app-config, storage)
- [ ] Permission checks on all routes
- [ ] Telegram account linking and password-reset flow

### Phase 4 — Frontend wiring

- [ ] HTTP repositories for all collections
- [ ] Switch `app-data` store to API mode
- [ ] E2E test: frontend + Docker backend
- [ ] Remove or gate mock-only code paths

### Phase 5 — Production hardening

- [ ] Strong JWT signing key, HTTPS, token rotation, and revocation checks
- [ ] Rate limiting on auth
- [ ] DB backups
- [ ] Logging / error monitoring
- [ ] CI: run tests + migrate on deploy

---

## 11. Environment Variables

### Backend `.env`

```env
DATABASE_URL=postgresql://rental:rental@db:5432/rental_moto
REDIS_URL=redis://redis:6379/0
RABBITMQ_URL=amqp://rental:rental@rabbitmq:5672/rental
CELERY_RESULT_BACKEND=redis://redis:6379/2
TASK_DEFAULT_MAX_RETRIES=5
TASK_RESULT_EXPIRE_SECONDS=86400
JWT_SECRET_KEY=<random-64-chars>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
CACHE_DEFAULT_TTL_SECONDS=60
TELEGRAM_BOT_TOKEN=<botfather-token>
TELEGRAM_BOT_MODE=polling
TELEGRAM_WEBHOOK_URL=
TELEGRAM_WEBHOOK_SECRET=<random-secret>
TELEGRAM_BOT_CLIENT_ID=rental-telegram-bot
TELEGRAM_BOT_CLIENT_SECRET=<random-64-chars>
TELEGRAM_RESET_CODE_EXPIRE_MINUTES=10
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
DEBUG=true
```

### Frontend `.env` (when using backend)

```env
NUXT_PUBLIC_API_BASE=http://localhost:8000
NUXT_PUBLIC_USE_MOCK_DATA=false
NUXT_PUBLIC_AUTH_MODE=bearer
```

---

## 12. Testing Plan

| Layer | Tool | What to test |
|-------|------|--------------|
| Unit | pytest | pricing, document sequences, permissions |
| API | pytest + httpx | auth, CRUD, rental lifecycle |
| Integration | docker compose + pytest | full flow with PostgreSQL, Redis, RabbitMQ, and Celery workers |
| Tasks | pytest + Celery test worker | routing, idempotency, retry, DLQ, outbox, export progress |
| Telegram | mocked Bot API + integration tests | callbacks, keyboards, localization, retries, reset delivery |
| Frontend | existing Vitest | keep mock tests; add API integration tests later |

Key test cases (mirror `tests/rental-payments.spec.ts`):

- Create rental sets motorcycle to Progressing
- Close rental sets motorcycle to Available
- Payment allocation across lines
- Expired/revoked JWTs are rejected and refresh-token reuse is blocked
- Cached dashboard/report results are invalidated after related mutations
- Telegram transaction events are idempotent and grouped correctly by rental
- Today/3-day/7-day/1-month/custom date periods produce correct finance totals
- Reset codes go only to the linked private Telegram chat and expire after one use
- A committed outbox event is eventually delivered after broker/API restarts without duplicate Telegram messages
- Large exports run outside API request latency and expose accurate progress/status

---

## 13. Risks & Decisions

| Risk | Mitigation |
|------|------------|
| Frontend field names are camelCase | API accepts camelCase in JSON; SQLAlchemy uses snake_case with alias |
| Mock store does rich client-side logic | Move create/close logic to backend endpoints, not generic CRUD |
| Large refactor to wire frontend | Phase incrementally: auth first, then one entity at a time |
| Token theft | Short access-token TTL, rotating refresh tokens, Redis denylist, HTTPS in production |
| Stale Redis data | Short TTLs plus explicit invalidation after every related mutation |
| RabbitMQ unavailable during DB commit | Transactional outbox retains unpublished events for later dispatch |
| Poison/repeatedly failing task | Bounded retries, dead-letter queues, alerting, and manual replay tooling |
| Worker overload | Dedicated queue workers, prefetch limits, concurrency caps, and queue-depth alerts |

**Open question:** Multi-motorcycle rental in one form (`RentalCreatePanel` supports multiple lines) — backend can either:

1. **One API call** with `lines[]` array (recommended), or
2. **Multiple rental records** per line (matches current mock data model)

Current seed has **one rental per motorcycle**. Recommend keeping that model.

---

## 14. Success Checklist

When the backend is done, you should be able to:

- [ ] `docker compose up` starts API + PostgreSQL + Redis + RabbitMQ + workers + scheduler + Telegram bot
- [ ] `http://localhost:8000/docs` shows all endpoints
- [ ] Login with `admin@gmail.com` / `123456` returns a JWT access/refresh token pair
- [ ] List 12 motorcycles from seeded data
- [ ] Create a rental → motorcycle becomes Progressing
- [ ] Close a rental → motorcycle becomes Available
- [ ] Dashboard returns correct KPI numbers
- [ ] Telegram keyboard returns transactions, grouped motorcycle status, and localized finance summaries
- [ ] Forgot-password sends a one-time code to the linked private Telegram chat
- [ ] Export requests return immediately, complete through RabbitMQ, and provide an expiring download
- [ ] Frontend with `USE_MOCK_DATA=false` works against local Docker API

---

## 15. Related Documents

| Document | Purpose |
|----------|---------|
| [`GLM_SYSTEM_GUIDE.md`](./GLM_SYSTEM_GUIDE.md) | Full system overview for AI |
| [`RENTAL_UI_IMPLEMENTATION_PLAN.md`](./RENTAL_UI_IMPLEMENTATION_PLAN.md) | Frontend rental UI plan |
| `app/utils/constants/api-endpoints.ts` | Existing v2 endpoint paths |
| `app/config/rental-seed.ts` | Seed data to replicate in backend |

---

*Plan version: 1.2 — 2026-09-01. Single-business model, Redis cache/state, RabbitMQ durable tasks, Celery workers, and JWT-only authentication. No backend code implemented yet.*
