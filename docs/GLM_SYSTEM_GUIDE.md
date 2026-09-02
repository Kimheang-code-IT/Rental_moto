# HollyWing Motor — System Guide for GLM 5.3 Flash

> **Purpose:** This document helps AI models (especially GLM 5.3 Flash) quickly understand the HollyWing Motor motorcycle rental system — frontend code, business rules, data shapes, and backend API.

---

## 1. What Is This System?

**HollyWing Motor** is a single-business motorcycle rental management app for Cambodia. Staff can:

- Manage motorcycle fleet (add bikes, set rates, track status)
- Register customers (ID, phone, address)
- Create and close rental agreements
- Record payments, extra charges, and operating expenses
- View dashboard KPIs and rental reports
- Admin: users, roles, document numbering, system settings

**Languages:** English + Khmer (i18n).

---



## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (Nuxt 4 + Vue 3) — runs on local computer         │
│  pnpm dev → http://localhost:3000                           │
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │   Pages     │───▶│ Pinia Stores │───▶│ useApi()      │  │
│  │  Components │    │ app-data     │    │ $fetch HTTP   │  │
│  └─────────────┘    └──────────────┘    └───────┬───────┘  │
└─────────────────────────────────────────────────┼──────────┘
                                                  │ HTTP
                                                  ▼
┌─────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI + PostgreSQL + Redis + RabbitMQ)        │
│  http://localhost:8000                                      │
│                                                             │
│  /api/v2/auth/*     Authentication                          │
│  /api/v2/motorcycles, /rentals, /customers, etc.            │
│  /api/v2/dashboard  KPIs (Redis-cached)                     │
└─────────────────────────────────────────────────────────────┘
```



### Key folders (frontend)


| Path                           | What it does                       |
| ------------------------------ | ---------------------------------- |
| `app/pages/`                   | Routes (file-based routing)        |
| `app/components/rental/`       | Rental-specific UI                 |
| `app/components/module/`       | Generic CRUD list/form for modules |
| `app/config/rental-modules.ts` | Field definitions for each entity  |
| `app/config/rental-seed.ts`    | Demo seed data                     |
| `app/stores/app-data.ts`       | Mock data CRUD (localStorage)      |
| `app/composables/useApi.ts`    | HTTP client for backend            |
| `app/utils/rental/pricing.ts`  | Rate tier pricing logic            |
|                                |                                    |


---

### Backend layering

The planned backend uses `app/api/v2/` for thin FastAPI routers, `app/services/` for business transactions, `app/repositories/` for SQLAlchemy queries, `app/models/` for persistence, and `app/schemas/` for public request/response contracts. Celery tasks in `app/tasks/` use RabbitMQ for durable delivery; Redis remains the cache, JWT denylist, rate-limit, conversation-state, and short-lived task-progress store. The separate `telegram_bot/` package communicates with FastAPI using service JWTs. Keep `/api/v2` because it matches the existing frontend constants.



## 3. Environment Variables



### Frontend (`.env`)

```env
NUXT_PUBLIC_API_BASE=http://localhost:8000
NUXT_PUBLIC_USE_MOCK_DATA=false   # set false to use real backend
NUXT_PUBLIC_AUTH_MODE=bearer
```



### Backend (`backend/.env`)

```env
DATABASE_URL=postgresql://rental:rental@db:5432/rental_moto
REDIS_URL=redis://redis:6379/0
RABBITMQ_URL=amqp://rental:rental@rabbitmq:5672/rental
CELERY_RESULT_BACKEND=redis://redis:6379/2
JWT_SECRET_KEY=change-me-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
TELEGRAM_BOT_TOKEN=<botfather-token>
TELEGRAM_BOT_MODE=polling
TELEGRAM_BOT_CLIENT_ID=rental-telegram-bot
TELEGRAM_BOT_CLIENT_SECRET=<random-secret>
CORS_ORIGINS=http://localhost:3000
```

---



## 4. Data Entities

Records have `id`, `created_at`, and `updated_at`; auditable records may also have `created_by_user_id`. This system has no organization, branch, or tenant entities.

### 4.1 Motorcycle (`motorcycles`)


| Field                                                 | Type    | Notes                                     |
| ----------------------------------------------------- | ------- | ----------------------------------------- |
| code                                                  | string  | MC-001                                    |
| model, brand, color                                   | string  |                                           |
| year                                                  | int     |                                           |
| plate, chassis_no, engine_no                          | string  | Registration                              |
| daily_rate, three_day_rate, weekly_rate, monthly_rate | decimal | Pricing tiers                             |
| asset_value                                           | decimal |                                           |
| currency                                              | string  | USD, KHR, THB                             |
| status                                                | enum    | `Available`, `Progressing`, `Maintenance` |


**Status rules:**

- `Available` → can rent or set Maintenance
- `Progressing` → currently rented (auto on rental create)
- `Maintenance` → repair; cannot rent



### 4.2 Customer (`rental_customers`)


| Field                          | Type   | Notes                                         |
| ------------------------------ | ------ | --------------------------------------------- |
| code                           | string | CUS-001                                       |
| full_name                      | string |                                               |
| identity_type                  | enum   | National ID, Passport, Driving License, Other |
| identity_number                | string |                                               |
| phone, email, company, address | string |                                               |
| status                         | enum   | `Active`, `Inactive`                          |


Only **Active** customers appear in rental create form.

### 4.3 Rental (`rentals`)


| Field                                            | Type     | Notes                                         |
| ------------------------------------------------ | -------- | --------------------------------------------- |
| rental_no                                        | string   | RNT-2026-000001                               |
| customer_id                                      | FK       |                                               |
| motorcycle_id                                    | FK       |                                               |
| start_date, due_date                             | datetime |                                               |
| duration_days                                    | int      | Computed                                      |
| rate_type                                        | enum     | Daily, Monthly                                |
| rate_amount, deposit, discount, tax_percent, tax | decimal  |                                               |
| rental_charge, late_fee, additional_charges      | decimal  |                                               |
| total_due, paid, outstanding                     | decimal  | Balance                                       |
| payment_method                                   | enum     | Cash, Bank Transfer, Card, QR Payment,other   |
| return_date, condition, return_note, note        |          | On close                                      |
| payment_status                                   | enum     | Paid, Partial (completed only)                |
| status                                           | enum     | `Active`, `Overdue`, `Completed`, `Cancelled` |


**List filters:**

- `/rentals` page → Active + Overdue only
- `/rental-reports` page → Completed only



### 4.4 Rental Payment (`rental_payments`)

`payment_no`, `rental_id`, `amount`, `payment_method`, `paid_at`, `reference`, `note`

### 4.5 Rental Charge (`rental_charges`)

`charge_no`, `rental_id`, `charge_type` (Damage, Lost item, Cleaning, Other), `amount`, `charge_to_customer`

### 4.6 Rental Expense (`rental_expenses`)

`expense_no`, `date`, `expense_type` (Fuel, Maintenance, Salary, Rent, Marketing, Other), `amount`

### 4.7 User (`users`)

`username`, `display_name`, `email`, `password_hash`, `role`, `status`, `permissions` (JSON array)

**Demo login:** `admin@gmail.com` / `123456`

---



## 5. Business Logic (Critical)



### 5.1 Pricing (`app/utils/rental/pricing.ts` + `backend/app/core/pricing.py`)

Rate tiers for duration in days:


| Days  | Rate used         |
| ----- | ----------------- |
| 1     | daily_rate        |
| 3     | three_day_rate    |
| 7     | weekly_rate       |
| 28–31 | monthly_rate      |
| other | daily_rate × days |




### 5.2 Create Rental Flow

1. Validate: customer (Active) + at least 1 motorcycle line
2. For each motorcycle:
  - Generate `RNT-{year}-{seq}`
  - Compute charge from pricing tiers
  - Apply discount/tax share
3. Save rental with status `Active`
4. Set motorcycle status → `Progressing`
5. If paid > 0 → create `rental_payment` record
6. Write audit log



### 5.3 Close Rental Flow

1. Optional return charges → `rental_charges`
2. Final payment → `rental_payments`
3. Recompute: paid, additional_charges, total_due, outstanding
4. Set rental status → `Completed`, set return_date
5. Set motorcycle → `Available`
6. Audit log



### 5.4 Finance Dashboard

- **Income** = sum of `rental_payments` in date range
- **Expense** = sum of `rental_expenses`
- **Outstanding** = sum of `outstanding` on Active/Overdue/Completed rentals



### 5.5 Overdue Detection

Rental is `Overdue` when `due_date < now` and status is still `Active`.

---



## 6. Frontend Code Patterns



### 6.1 Module Registry

Entities are defined in `app/config/rental-modules.ts`:

```typescript
{
  path: '/motorcycles',
  collection: 'motorcycles',  // localStorage key / API collection
  permission: 'rental.motorcycles.view',
  columns: [...],
  fields: [...],
}
```



### 6.2 Generic CRUD

Most pages use `ModuleWorkspaceView` (list) + `ModulePage` (form). Rentals use custom `RentalCreatePanel`.

### 6.3 Mock vs API Mode

```typescript
// app/stores/app-data.ts — mock mode
const db = getRentalDb()  // localStorage key: rental-moto-data-v9

// When NUXT_PUBLIC_USE_MOCK_DATA=false:
// Frontend should call backend /api/v2/* endpoints instead
```



### 6.4 Auth

```typescript
// app/composables/useApi.ts
headers: { Authorization: `Bearer ${accessToken}` }
// On 401 caused by expiry: rotate via /api/v2/auth/refresh, then retry once.
```

JWT bearer authentication is the only backend auth mechanism. Do not add cookie sessions, CSRF-token auth, API keys, or organization/branch claims. Access tokens are short-lived; refresh tokens rotate and their JTIs are denylisted in Redis on logout or detected reuse.

### 6.5 Redis

- Cache dashboard, report, settings, and reference reads for 30–300 seconds.
- Invalidate affected cache keys after any related mutation.
- Use Redis for auth rate limits and revoked refresh-token JTIs.
- Never cache raw JWTs, passwords, or sensitive configuration.
- PostgreSQL remains the source of truth; the API must still read from PostgreSQL if Redis is unavailable.

### 6.6 Telegram chatbot

Telegram runs in a separate `telegram-bot` Docker container. It calls FastAPI using a short-lived service JWT and never queries PostgreSQL directly.

Main keyboard buttons:

- `📋 All Rental Transactions`: group rental creation, payment, charge, return/completion, cancellation, and overdue events by rental number.
- `🏍 Motorcycle Status`: show Available, Progressing, and Maintenance counts with buttons to open each grouped list.
- `💰 Income / Expense`: show income, expense, net, and outstanding totals.
- Date keyboard for finance and transactions: Today, 3 Days, 7 Days, 1 Month, and Custom Range.

Custom-range conversation state and pagination cursors live in Redis with TTLs. Messages follow Localization settings for English/Khmer, timezone, date/time format, number format, and currency.

Every committed rental, payment, charge, expense, overdue, completion, and cancellation event writes a PostgreSQL outbox event that is dispatched to RabbitMQ. Celery workers use Redis idempotency keys and bounded retries so Telegram failures do not slow down or roll back business transactions.

Forgot-password codes may be delivered only to the application user’s linked **private** Telegram chat. Store only a hash of the code in Redis, expire it after 10 minutes by default, make it single-use, rate-limit attempts, and revoke refresh tokens after a successful reset.

---



## 7. Backend API Reference

Base URL: `http://localhost:8000`

### Response format

```json
{
  "data": { ... },
  "meta": { "page": 1, "limit": 20, "total": 100 }
}
```

Error:

```json
{
  "detail": "Error message"
}
```



### Auth endpoints


| Method | Path                  | Body                  | Response                          |
| ------ | --------------------- | --------------------- | --------------------------------- |
| POST   | `/api/v2/auth/login`  | `{ email, password }` | Access token + rotating refresh token |
| POST   | `/api/v2/auth/refresh` | `{ refreshToken }`   | Fresh access/refresh token pair   |
| POST   | `/api/v2/auth/logout` | `{ refreshToken }`    | Revoke refresh-token JTI in Redis |
| GET    | `/api/v2/auth/me`     | Bearer access token   | `{ data: AuthUser }`              |

The Telegram container obtains its JWT from `/api/v2/auth/service-token`. Telegram report endpoints are `/api/v2/telegram/transactions`, `/api/v2/telegram/motorcycle-status`, and `/api/v2/telegram/finance-summary`.




### Rental CRUD (all support `?q=&page=&limit=&sort=`)


| Method | Path                         | Description                     |
| ------ | ---------------------------- | ------------------------------- |
| GET    | `/api/v2/motorcycles`        | List motorcycles                |
| GET    | `/api/v2/motorcycles/{id}`   | Get one                         |
| POST   | `/api/v2/motorcycles`        | Create                          |
| PUT    | `/api/v2/motorcycles/{id}`   | Update                          |
| DELETE | `/api/v2/motorcycles/{id}`   | Delete                          |
| GET    | `/api/v2/customers`          | List customers                  |
| GET    | `/api/v2/rentals`            | List rentals (`?status=Active`) |
| POST   | `/api/v2/rentals`            | Create rental                   |
| POST   | `/api/v2/rentals/{id}/close` | Close rental                    |
| GET    | `/api/v2/payments`           | List payments                   |
| POST   | `/api/v2/payments`           | Record payment                  |
| GET    | `/api/v2/charges`            | List charges                    |
| POST   | `/api/v2/charges`            | Add charge                      |
| GET    | `/api/v2/expenses`           | List expenses                   |
| POST   | `/api/v2/expenses`           | Add expense                     |
| GET    | `/api/v2/dashboard`          | KPI summary                     |




### Settings (existing frontend endpoints)


| Method  | Path                          |
| ------- | ----------------------------- |
| GET/PUT | `/api/v2/settings/app-info`   |
| GET/PUT | `/api/v2/settings/app-config` |


---



## 8. Permissions

Page permission keys (checked in `auth.global.ts` middleware):

```
dashboard.view
rental.motorcycles.view|create|edit|delete
rental.customers.view|create|edit|delete
rental.rentals.view|create|edit|return|print
rental.finance.view|create
reports.view|print
admin.users.view|create|edit|delete
admin.roles.view|create|edit
admin.audit_logs.view
settings.app_config.view|edit
configuration.view
```

`ALL_PAGES` = super admin bypass.

---



## 9. Docker Deployment (Full Stack)

```bash
docker compose up -d
```

Services:

- `api` — FastAPI on port 8000
- `db` — PostgreSQL on port 5432
- `redis` — Redis cache and token denylist on port 6379 (internal Docker network)
- `rabbitmq` — durable task broker; management UI is local-only on port 15672
- `worker-default` — reports, overdue scans, cleanup, and maintenance tasks
- `worker-telegram` — critical password-reset and Telegram notification queues
- `worker-export` — CSV/XLSX/PDF export generation
- `scheduler` — Celery Beat scheduled summaries and maintenance jobs
- `telegram-bot` — Telegram commands, keyboards, summaries, notifications, and password-reset delivery
- `frontend` — statically generated Nuxt client served by nginx (no Node runtime)

For local frontend development outside Docker:

```bash
# In project root
cp .env.example .env
# Set NUXT_PUBLIC_USE_MOCK_DATA=false
pnpm dev
```

---



## 10. Common Tasks for AI



### Add a new field to Motorcycle

1. Add column in `app/config/rental-modules.ts` → `fields` array
2. Add to `backend/app/models/motorcycle.py`
3. Add to `backend/app/schemas/motorcycle.py`
4. Run migration: `docker compose exec api alembic revision --autogenerate -m "add field"`



### Wire frontend to backend

1. Set `NUXT_PUBLIC_USE_MOCK_DATA=false` in `.env`
2. Create HTTP repository in `app/repositories/http/` (copy pattern from `settings-storage.ts`)
3. Update store or composable to use HTTP repo when mock is off



### Debug API connection

1. Check `http://localhost:8000/docs` (Swagger UI)
2. Check CORS: backend `CORS_ORIGINS` must include `http://localhost:3000`
3. Check the `Authorization: Bearer` header, token expiry, and `/auth/refresh` response
4. Check Redis readiness if cached endpoints or refresh-token revocation fails

---



## 11. File Quick Reference


| Need to change…        | Edit this file                                |
| ---------------------- | --------------------------------------------- |
| Rental create UI       | `app/components/rental/RentalCreatePanel.vue` |
| Pricing logic          | `app/utils/rental/pricing.ts`                 |
| Demo data              | `app/config/rental-seed.ts`                   |
| Module fields          | `app/config/rental-modules.ts`                |
| API endpoints constant | `app/utils/constants/api-endpoints.ts`        |
| Auth mock accounts     | `app/utils/auth/mock-login.ts`                |
| Backend routes         | `backend/app/api/v2/`                         |
| DB models              | `backend/app/models/`                         |
| Docker config          | `docker-compose.yml`                          |


---



## 12. Glossary


| Term         | Meaning                                                |
| ------------ | ------------------------------------------------------ |
| Module       | A CRUD entity (motorcycles, customers, etc.)           |
| Collection   | Database table / localStorage key name                 |
| Rate tier    | 1-day / 3-day / 7-day / monthly pricing                |
| Access token | Short-lived JWT sent in the bearer authorization header |
| Refresh token | Rotating JWT used only to obtain a new token pair      |
| Redis cache  | Temporary acceleration layer; PostgreSQL remains authoritative |
| RabbitMQ     | Durable broker for Telegram, export, report, and maintenance tasks |
| Celery worker | Process that consumes routed RabbitMQ tasks outside API latency |
| Outbox event | PostgreSQL row written with a business transaction and later published reliably |


---

*Last updated: 2026-09-01. For backend setup see* `backend/README.md`*. For the audited frontend HTTP integration contract, see* `docs/GLM_FRONTEND_BACKEND_INTEGRATION_GUIDE.md`*.*
