# HollyWing Motor agent instructions

These instructions apply to all work in this repository.

## Start with repository evidence

- Inspect the relevant implementation before editing it.
- Read only the applicable sections of `docs/GLM_SYSTEM_GUIDE.md` for domain behavior.
- For backend work, also read `docs/BACKEND_IMPLEMENTATION_PLAN.md`.
- For frontend/backend HTTP integration, follow `docs/GLM_FRONTEND_BACKEND_INTEGRATION_GUIDE.md`.
- Search for existing types, utilities, repositories, components, tests, and translations before adding new patterns.
- Keep changes focused and preserve unrelated user edits.

For implementation, debugging, or review work in OpenCode, load the `rental-moto-development` skill.

## Repository structure

- `frontend/` is the active Nuxt 4, Vue 3, TypeScript, Pinia, Nuxt UI, Vitest, and English/Khmer i18n application.
- Documentation paths written as `app/...` refer to `frontend/app/...`.
- `backend/` is reserved for the planned FastAPI, PostgreSQL, Redis, RabbitMQ, and Celery implementation. Inspect it before assuming backend code exists.

## Required invariants

- Reuse existing module, table, form, composable, store, and repository patterns.
- Keep English and Khmer translation keys synchronized. Avoid hard-coded UI text where i18n is used.
- Preserve `/api/v2` endpoints and the `{ data, meta }` response envelope.
- Preserve bearer access tokens and rotating refresh tokens. Do not introduce cookie sessions, CSRF-token authentication, end-user API keys, or tenant/branch claims.
- PostgreSQL is authoritative. Use Redis only for caching, revocation, rate limits, transient state, progress, and idempotency.
- Keep rental, payment, charge, completion, motorcycle-status, pricing, audit, and outbox changes transactionally consistent.
- Use decimal-safe values for persisted backend money calculations.
- Add or update tests for changed business logic, regressions, permissions, and API contracts.
- Avoid destructive Git or filesystem operations unless the user explicitly requests them.

## Verification

Run the checks relevant to the change from the repository root:

```text
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend build
```

Prefer focused tests while iterating. Never claim a check passed unless it was run successfully. If verification is blocked, report the exact unverified command and reason.
