# HollyWing Motor — agent guide

Motorcycle rental SaaS. Nuxt 4 static SPA (`frontend/`) + FastAPI `/api/v2` backend
(`backend/`), wired together by Docker Compose at the repo root.

## Layout

- `frontend/` — Nuxt 4, Vue 3, TS, Pinia, Nuxt UI, Vitest, en/km i18n. `~` aliases `frontend/app`.
- `backend/` — FastAPI, SQLAlchemy 2 async, Alembic, PostgreSQL, Redis-only Celery. Layered: `api/v2` routers → `services` → `repositories` → `models`.
- `docker-compose.yml` — canonical runtime (services: `frontend`, `api`, `db`, `redis`, `worker-telegram`, `telegram-bot`). No RabbitMQ.
- `scripts/` — Windows install/startup + `deploy-local.*` production scripts.

## Commands

Run frontend commands from the repo root (there is no root `package.json`):

```powershell
pnpm --dir frontend install --frozen-lockfile   # then: pnpm --dir frontend prepare:nuxt
pnpm --dir frontend test                        # vitest run; add a path to run one file
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build                       # nuxt generate (static SPA, ssr:false)
```

Backend, from `backend/` (or `docker compose exec api ...`):

```powershell
pytest tests/unit -q            # no services needed; this is what CI runs
pytest                          # full suite needs Postgres :55432 + Redis :56379 (see tests/conftest.py)
alembic upgrade head
alembic revision --autogenerate -m "change"
python -m app.seed               # idempotent; seeds sequences/settings only
```

- Single test: `pnpm --dir frontend test tests/rental-pricing.spec.ts`, `pytest tests/unit/test_pricing.py -k name`.
- CI (`.github/workflows/ci.yml`): frontend `prepare:nuxt → test → typecheck`; backend `pytest tests/unit` only. No backend lint/format command is wired (ruff is installed but unconfigured).

## Contracts that must not drift

- Every response uses `{ "data": ..., "meta": ... }`; errors use `{"detail": {"code", "message"}}`; all JSON is camelCase (Pydantic aliases).
- Auth is bearer access + rotating refresh JWT (Redis denylist, family revocation on reuse). Never add cookie sessions, CSRF-token auth, or user API keys.
- Permission check on every route (`is_owner` / `ALL_PAGES` bypass). Add new permissions to backend `core/permissions.py` and keep `frontend/app/utils/rental/permissions.ts` aligned.
- Money: PostgreSQL `Numeric(14,2)` + Python `Decimal` (ROUND_HALF_UP). No floats for persisted money.
- Pricing exists twice and must stay in sync: `backend/app/core/pricing.py` ↔ `frontend/app/utils/rental/pricing.ts`.
- Business IDs are string prefixes (`mc-`, `rc-`, `rt-`, `rp-`, `rg-`, `rx-`) from `document_sequences`; users/roles use integer PKs.
- `POST /rentals` takes `lines[]` and creates **one rental per line**. Mutations write audit + outbox rows in the same transaction; APScheduler dispatches outbox to Celery.
- PostgreSQL is authoritative; Redis is cache/transient state only (fall back to DB when Redis is down).

## Frontend conventions

- Components/pages do not call HTTP directly — extend `app/repositories/contracts/*` **and** `app/repositories/http/*` (accessed via `~/repositories`).
- A new screen usually means touching the module registry: `app/config/modules.ts`, `rental-modules.ts`/`admin-modules.ts`, plus matching keys in both `i18n/locales/en.json` and `km.json` (never hard-code user text in one language only).

## Gotchas

- `backend/README.md` and `backend/IMPLEMENTATION_STATUS.md` still reference a `docs/` folder that no longer exists and mention RabbitMQ/9 services/old services; trust `docker-compose.yml` and the code over those docs.
- First admin is registered through the public `/auth/setup` page while the users table is empty (owner gets `ALL_PAGES`). There are no seeded users, roles, or default passwords; seed only creates sequences, settings, and demo domain data.
- Production refuses to boot with dev secrets (`Settings.assert_safe_for_production`); deploy with `scripts/deploy-local.ps1` using `docker-compose.prod.yml` (API not published on :8000 there).
- `NUXT_PUBLIC_API_BASE=auto` (dev) resolves API calls to the page host on :8000; the Docker frontend uses `same-origin` through nginx.
- Full backend tests mutate a real DB (`create_all`/`drop_all` on `rental_moto_test`); never point `DATABASE_URL` at a database you care about.
