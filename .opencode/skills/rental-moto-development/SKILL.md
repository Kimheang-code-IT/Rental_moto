---
name: rental-moto-development
description: Implement, debug, or review HollyWing Motor frontend and backend work while preserving its rental, payment, authentication, localization, and API contracts. Use for code changes in this repository; do not use for unrelated generic questions.
metadata:
  project: rental-moto
  primary-model: glm-5.3-flash
---

# HollyWing Motor development

Work from evidence in the repository. Before changing code, inspect the relevant implementation and read only the applicable sections of `docs/GLM_SYSTEM_GUIDE.md`. Use `docs/BACKEND_IMPLEMENTATION_PLAN.md` when the task affects the planned backend.

For frontend/backend HTTP integration, read and follow `docs/GLM_FRONTEND_BACKEND_INTEGRATION_GUIDE.md` before editing transport, authentication, repositories, stores, or API-connected components.

## Repository map

- `frontend/` is the active Nuxt 4, Vue 3, TypeScript, Pinia, Nuxt UI, and i18n application.
- `frontend/app/` contains pages, components, composables, stores, repositories, and business utilities.
- `frontend/tests/` contains Vitest tests.
- `backend/` is reserved for the planned FastAPI, PostgreSQL, Redis, RabbitMQ, and Celery implementation. Do not invent an existing backend structure.
- `docs/GLM_SYSTEM_GUIDE.md` is the main domain and integration reference.

Some documentation still shows frontend paths without the `frontend/` prefix. Resolve those paths under `frontend/` before deciding a file is missing.

## Workflow

1. Restate the requested outcome internally and identify the smallest affected surface.
2. Search for existing types, utilities, repositories, tests, translations, and UI patterns before adding new ones.
3. Make a focused change that preserves public contracts and current behavior outside the request.
4. Add or update tests for business logic, regressions, permission boundaries, or API contracts.
5. Run the narrowest relevant checks, then report what changed and what was verified. Never claim a command passed unless it was run successfully.

Ask one concise question only when a missing product decision would materially change the implementation. Otherwise, state a safe assumption and proceed.

## Project invariants

- Keep English and Khmer translation keys synchronized; do not hard-code user-facing text when the surrounding feature uses i18n.
- Reuse existing module, table, form, repository, and composable patterns instead of creating parallel abstractions.
- Preserve `/api/v2` endpoint contracts and the `{ data, meta }` response envelope.
- Use bearer access tokens with rotating refresh tokens. Do not introduce cookie sessions, CSRF-token authentication, API keys for users, or tenant/branch claims.
- PostgreSQL is authoritative. Redis is only for caching, token revocation, rate limits, transient state, progress, and idempotency.
- Keep rental creation, payment, charge, completion, motorcycle-status, pricing, audit, and outbox changes transactionally consistent.
- Never use JavaScript floating-point arithmetic for persisted money in backend code; use decimal-safe values.
- Preserve unrelated user changes. Do not perform destructive Git or filesystem operations unless explicitly requested.

## Verification

Run commands from the repository root with `pnpm --dir frontend <script>`.

- Logic or test change: `pnpm --dir frontend test`
- Type-sensitive change: `pnpm --dir frontend typecheck`
- Style or source change: `pnpm --dir frontend lint`
- Build/configuration change: `pnpm --dir frontend build`

Prefer a focused Vitest invocation during iteration when only one test file is affected. If a required service or dependency is unavailable, describe the exact unverified check rather than guessing.
