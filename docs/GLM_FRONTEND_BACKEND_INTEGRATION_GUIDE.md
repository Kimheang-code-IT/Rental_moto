# HollyWing Motor — Complete Frontend/Backend Integration Guide for GLM 5.3 Flash

> **Purpose:** Give GLM 5.3 Flash an evidence-based, file-by-file contract for replacing the Nuxt frontend's mock data path with the implemented FastAPI `/api/v2` backend.
>
> **Scope:** Frontend integration, integration tests, and only the smallest backend compatibility fixes that the audit identifies. This is not permission to rebuild the backend or redesign the UI.
>
> **Audit date:** 2026-09-01

---

## 1. Required reading and execution rule

Before editing, read:

1. `AGENTS.md`
2. `.opencode/skills/rental-moto-development/SKILL.md`
3. `docs/GLM_SYSTEM_GUIDE.md`
4. This document
5. The exact frontend and backend files named in the active phase

When using OpenCode, load the `rental-moto-development` skill.

This is an implementation guide. Do not stop after producing another plan. Work one phase at a time, run its checks, update the checklist in section 15, and continue while a safe in-scope task remains.

---

## 2. Audit verdict

The backend is implemented and its normal development stack is running. The frontend is **not yet integrated completely**: settings have HTTP repositories, but authentication and the main rental/admin data flows still use mock/localStorage implementations.

| Area | Current state | Integration consequence |
| --- | --- | --- |
| Backend Docker stack | Nine services running; API, PostgreSQL, Redis, RabbitMQ, workers, and bot report healthy | Use the backend as the source of truth; do not recreate it |
| API base | `http://localhost:8000/api/v2` | Compatible with frontend development |
| Response fields | Resource serializers use camelCase | Matches most current module field keys |
| Response envelope | `{ data, meta }` | Use `unwrapApiData` for single records and retain `meta` for lists |
| Authentication | Bearer access JWT plus rotating refresh JWT | Frontend must add token storage, authorization headers, refresh, retry, and server logout |
| Frontend auth | `useAuth()` is mock-only | Must branch by `useMockData` and implement HTTP mode |
| Frontend entity data | `useAppDataStore()` reads/writes localStorage mock DB | Must add HTTP repositories and asynchronous loading/mutations |
| Settings | HTTP repository already exists | Keep it and fix auth/error handling underneath `useApi()` |
| Search | Request/response contract differs; `/search/ask` is absent | Add an adapter and remove or replace the unsupported call |
| Error body | Backend returns `{ detail: { code, message, field_errors? } }` | Frontend currently reads a nonexistent top-level `message`; normalize errors centrally |
| Environment example | Defaults to cookie/CSRF mode | Change real API mode to bearer |
| Frontend dependencies | `node_modules` is incomplete in the audited workspace | Run `pnpm --dir frontend install` before frontend checks |

### Evidence verified during this audit

- `docker compose config --quiet` passed from the repository root.
- `/health/ready` returned `postgres: ok`, `redis: ok`, and `rabbitmq: ok`.
- Live authenticated GET smoke checks passed for `/auth/me`, `/motorcycles`, `/customers`, `/rentals`, `/dashboard`, `/settings/app-info`, and `/search`.
- Backend dependency-free tests passed: 22/22.
- The complete local backend test command collected 83 tests, but 61 database-backed tests could not start because the fixture expects isolated services on ports `55432`, `56379`, and `55672`. Do not reinterpret this infrastructure error as an application assertion failure.
- Frontend typecheck and tests could not start because the local Nuxt/Vitest executables were missing from `frontend/node_modules`.

Do not run the backend test suite inside the normal API container without checking its environment: `tests/conftest.py` drops and recreates the configured database schema. Use isolated test infrastructure as documented in `backend/README.md`.

---

## 3. Non-negotiable integration decisions

1. Keep `/api/v2`; do not invent `/api/v1` or remove the prefix.
2. Use bearer authentication. The backend intentionally does not implement cookie sessions or CSRF authentication.
3. Keep mock mode working when `NUXT_PUBLIC_USE_MOCK_DATA=true`.
4. When mock mode is false, PostgreSQL through FastAPI is authoritative. Do not also write the localStorage mock database.
5. Let the backend calculate rental numbers, pricing, tax, balances, payment numbers, charge numbers, expense numbers, status transitions, audit events, and outbox events.
6. Never perform those business transactions separately from the frontend when one backend transaction endpoint exists.
7. Keep camelCase at the frontend boundary. Backend Pydantic schemas accept camelCase request aliases and return camelCase resource fields.
8. Preserve English/Khmer UI behavior and existing page layouts.
9. Backend `403` is authoritative. Frontend permission hiding remains only a usability feature.
10. Preserve unrelated working-tree changes and the ongoing root-to-`frontend/` move.

---

## 4. Target data flow

```text
Page / component
    ↓
feature composable or Pinia store
    ↓
repository contract
    ├── mock repository when useMockData=true
    └── HTTP repository when useMockData=false
            ↓
          useApi()
            ├── Authorization: Bearer <accessToken>
            ├── one refresh + one retry after an expired access token
            ├── normalized FastAPI error
            └── request cancellation/timeout behavior already present
                    ↓
             FastAPI /api/v2
                    ↓
        PostgreSQL (authoritative) + Redis/RabbitMQ side effects
```

Components should not know token formats, response envelopes, or backend snake_case field names.

---

## 5. Environment configuration

For real backend development, use:

```env
NUXT_PUBLIC_API_BASE=http://localhost:8000
NUXT_PUBLIC_API_TIMEOUT_MS=30000
NUXT_PUBLIC_AUTH_MODE=bearer
NUXT_PUBLIC_USE_MOCK_DATA=false
NUXT_PUBLIC_APP_VERSION=0.1.0
```

Update `frontend/.env.example` so bearer is the documented default for real API mode. CSRF names may remain for future compatibility, but `useApi()` must not generate CSRF headers in bearer mode.

Production must use an HTTPS API origin because `safeApiBase()` intentionally rejects insecure production API URLs.

Backend CORS must contain the exact frontend origin. The current development configuration includes `http://localhost:3000` and `http://127.0.0.1:3000`.

---

## 6. API envelope, errors, dates, and money

### Success

Single record:

```json
{
  "data": { "id": "mc-001", "code": "MC-001" },
  "meta": { "page": 1, "limit": 1, "total": 1 }
}
```

List:

```json
{
  "data": [],
  "meta": { "page": 1, "limit": 20, "total": 0 }
}
```

Use a typed `ApiResponse<T>`. Do not discard list metadata; the server owns pagination totals.

### Error

The backend error shape is:

```json
{
  "detail": {
    "code": "AUTH_REQUIRED",
    "message": "Missing bearer token",
    "field_errors": {
      "currentPassword": "Incorrect password"
    }
  }
}
```

Add one normalizer in the HTTP layer that returns a frontend error with:

- `statusCode`
- `code`
- `message`
- `fieldErrors`
- original payload for diagnostics

`useApi()` must read `response._data.detail.message`, not only `response._data.message`. It should also accept ordinary FastAPI validation details, which may be an array.

### Dates

- Send ISO 8601 strings.
- Convert `datetime-local` values to an ISO value deliberately; do not append `Z` without understanding the configured timezone.
- Display using the existing localization/formatting utilities.
- Do not compare localized display strings.

### Money

- JSON responses may contain decimal values as JSON strings or numbers depending on serialization.
- Keep raw API money types tolerant (`string | number`) and normalize only for display/input.
- Do not recompute authoritative balances after a mutation. Replace cached records with the backend response.

---

## 7. Authentication integration

### Endpoints

| Action | Method and path | Request body | Important response data |
| --- | --- | --- | --- |
| Login | `POST /api/v2/auth/login` | `{ email, password }` | `accessToken`, `refreshToken`, expiry values, `user` |
| Rotate | `POST /api/v2/auth/refresh` | `{ refreshToken }` | new access and refresh tokens |
| Logout | `POST /api/v2/auth/logout` | `{ refreshToken }` | message |
| Current user | `GET /api/v2/auth/me` | bearer header | current `AuthUser` |
| Change password | `POST /api/v2/auth/change-password` | `{ currentPassword, newPassword }` | message |
| Avatar | `PATCH /api/v2/auth/profile/avatar` | `{ avatar }` | avatar |
| Begin recovery | `POST /api/v2/auth/forgot-password` | `{ email }` | generic message |
| Verify code | `POST /api/v2/auth/forgot-password/verify` | `{ email, code }` | `resetToken` |
| Resend code | `POST /api/v2/auth/forgot-password/resend` | `{ email }` | generic message |
| Reset password | `POST /api/v2/auth/forgot-password/reset` | `{ email, resetToken, newPassword }` | message |
| Link Telegram | `POST /api/v2/auth/telegram/link-code` | bearer header | code and expiry |

### Required frontend changes

1. Add `AUTH_REFRESH` and `AUTH_TELEGRAM_LINK_CODE` to `frontend/app/utils/constants/api-endpoints.ts`.
2. Add a small client-only token utility, for example `frontend/app/utils/auth/tokens.ts`.
3. Keep the access and rotating refresh token in `sessionStorage`; keep the access token in Pinia memory while the app is running. Do not put either token in the readable `auth_user` cookie.
4. Treat the existing `auth_user` cookie/localStorage profile as display/hydration data only, never proof of authentication.
5. Change `useApi()` to attach `Authorization: Bearer <accessToken>` in bearer mode.
6. Implement one module-level refresh promise so concurrent `401` responses cause one rotation request, not several.
7. Retry the original request once after successful rotation. Mark refresh/login requests so they are never recursively refreshed.
8. If rotation fails, clear tokens and user state, show the session-expired UI once, and navigate to login.
9. `logout()` should attempt server logout with the refresh token, then clear client state in `finally`.
10. On client hydration, if tokens exist, call `/auth/me`; do not accept a stale locally stored user indefinitely.

### Mock/HTTP auth adapter

Refactor `frontend/app/composables/auth/useAuth.ts` so each operation selects mock or HTTP behavior using `runtimeConfig.public.useMockData`.

Do not delete the mock implementation. Keep it in a separate module if that makes the branch easier to verify.

### Password-reset correction

The current frontend stores the six-digit verification code and resubmits it. The backend requires the short-lived `resetToken` returned by verification.

Change `PasswordResetSession` in `frontend/app/utils/auth/password-reset.ts`:

```ts
interface PasswordResetSession {
  email: string
  verified: boolean
  resetToken?: string
  updatedAt: string
}
```

After verify, store `response.data.resetToken`. On reset, submit `{ email, resetToken, newPassword }`. Clear the session after success or expiry. Never store the new password.

---

## 8. Endpoint and collection map

Expand `ApiEndpoints` and use this single mapping in HTTP repositories:

| Frontend collection/feature | Backend path | Notes |
| --- | --- | --- |
| `motorcycles` | `/api/v2/motorcycles` | CRUD plus `PATCH /{id}/status` |
| `rentalCustomers` | `/api/v2/customers` | Keep frontend collection name; path is `customers` |
| `rentals` | `/api/v2/rentals` | List defaults to Active/Overdue |
| Rental reports | `/api/v2/rentals/reports` | Defaults to Completed |
| Close rental | `/api/v2/rentals/{id}/close` | One atomic transaction |
| Cancel rental | `/api/v2/rentals/{id}/cancel` | Body `{ reason }` |
| `rentalPayments` | `/api/v2/payments` | Use `rentalId` filter |
| `rentalCharges` | `/api/v2/charges` | Use `rentalId` filter |
| `rentalExpenses` | `/api/v2/expenses` | Date-range and type filters |
| `users` | `/api/v2/users` | Telegram fields are restricted/computed |
| `roles` | `/api/v2/roles` | Adapter needed for permission matrix |
| `documentSequences` | `/api/v2/document-sequences` | Adapter computes preview-only UI fields |
| `auditLogs` | `/api/v2/audit-logs` | Read-only adapter needed |
| Dashboard | `/api/v2/dashboard` | Optional `startDate`, `endDate` |
| Finance summary | `/api/v2/finance/summary` | Optional date range |
| App info/config | `/api/v2/settings/*` | Existing repositories already cover these |
| Storage | `/api/v2/settings/storage` | Existing repository already covers this |
| Search | `/api/v2/search` | Adapter required; see section 12 |
| Exports | `/api/v2/exports` | Async job plus task/download endpoints |

List query names are camelCase at the HTTP boundary: `q`, `page`, `limit`, `sort`, `status`, `startDate`, and `endDate`. Resource-specific filters include `customerId`, `motorcycleId`, `rentalId`, `paymentMethod`, `chargeType`, and `expenseType`.

Do not send TanStack's `ColumnFiltersState` array directly as `filters`. Translate supported filters into named API parameters.

---

## 9. Repository and store migration

### Add typed contracts

Create focused contracts under `frontend/app/repositories/contracts/` for:

- paginated entity CRUD
- rental commands
- finance/dashboard
- auth
- administration
- search/exports if used

A list result should contain both `items` and `meta`.

### Add HTTP implementations

Create HTTP repositories under `frontend/app/repositories/http/`. They should:

- call `useApi()`
- unwrap single-record envelopes
- retain list metadata
- map collection names to endpoints
- adapt only known UI/backend field differences
- never implement business transactions locally

### Preserve mock mode

Keep mock repositories under `frontend/app/repositories/mock/`. The repository selector should choose one mode from `useRuntimeConfig().public.useMockData`.

### Refactor `useAppDataStore()` deliberately

The current store API is synchronous and localStorage-backed. Real HTTP operations are asynchronous. Do not hide HTTP promises behind the existing synchronous `save()`/`create()` functions.

Add explicit asynchronous operations such as:

- `fetchList(collection, query)`
- `fetchOne(collection, id)`
- `createRemote(collection, input)`
- `updateRemote(collection, id, input)`
- `deleteRemote(collection, id)`
- `reloadCollection(collection)`

Maintain a reactive in-memory cache for rendering. In mock mode, delegate to the existing synchronous functions. In HTTP mode, update the cache only from successful API responses.

Update callers in:

- `frontend/app/components/module/WorkspaceView.vue`
- `frontend/app/components/module/DocumentView.vue`
- `frontend/app/components/module/ModulePage.vue` if it owns loading state
- `frontend/app/components/rental/*`
- dashboard, income/expense, reports, and related-record views

Add loading, empty, error, and retry states. Disable repeated mutation buttons while a request is pending.

---

## 10. Resource adapters

Most rental resource fields already match because the backend returns camelCase. Use narrow adapters only for these differences.

### Users

- Backend returns `lastLoginAt`; UI currently displays `lastLogin`.
- Backend returns `telegramLinked`, not editable Telegram username/chat fields.
- Map `lastLoginAt → lastLogin` for the existing column or update the column key.
- Render Telegram as Linked/Not linked. Do not submit `telegramUsername` or `telegramChatId` in user create/update requests.
- Use `POST /users/{id}/unlink-telegram` for unlinking.

### Roles

- Backend stores flat `permissions` and `pageAccess` arrays.
- Existing UI uses permission-matrix rows and derived `permissionCount`/`userCount`.
- Reuse `frontend/app/utils/role/permissions.ts` to map the matrix to flat permission strings.
- Compute `permissionCount` client-side.
- Do not submit UI-only `status`, `userCount`, `permissionCount`, or `permissionRows` unless transformed to backend fields.

### Document sequences

- Backend fields: `documentType`, `prefix`, `year`, `paddingLength`, `lastValue`, `status`, `note`.
- `nextNumberPreview` is UI-only; compute it from prefix/year/next value/padding.
- `resetRule` is not a backend field. Do not submit it unless a backend feature is explicitly added.

### Audit logs

- Backend returns `occurredAt`, `userId`, `userName`, `action`, `entityType`, `entityId`, `entityLabel`, and `details`.
- Existing UI expects additional template-era fields. Prefer updating the UI module to the real backend fields rather than fabricating trace data.
- Do not invent `requestId`, `correlationId`, before/after values, or failed/success states that the backend did not return.

---

## 11. Rental and finance transactions

### Create rental

Replace the local loop in `RentalCreatePanel.vue` with one request:

```json
{
  "customerId": "rc-001",
  "lines": [
    {
      "motorcycleId": "mc-001",
      "startDate": "2026-09-01T08:00:00+07:00",
      "dueDate": "2026-09-04T08:00:00+07:00",
      "deposit": "20.00",
      "discount": "0.00",
      "note": null
    }
  ],
  "discount": "0.00",
  "taxPercent": "0.00",
  "paidAmount": "10.00",
  "paymentMethod": "Cash",
  "currency": "USD",
  "note": null
}
```

The response `data` is an array because one request can create multiple rentals. Navigate to the first returned rental when appropriate. Replace cached motorcycles/rentals from server responses or reload affected lists.

Remove client-side generation of rental/payment numbers and client-side status persistence in HTTP mode.

### Close rental

Replace the multiple local writes in `RentalTransactionModals.vue` with:

```json
{
  "returnDate": "2026-09-04T10:30:00+07:00",
  "condition": "Good",
  "returnNote": null,
  "lateFee": "0.00",
  "charges": [
    {
      "chargeType": "Cleaning",
      "description": "Cleaning fee",
      "amount": "5.00",
      "chargeToCustomer": "Yes"
    }
  ],
  "finalPayment": {
    "amount": "15.00",
    "paymentMethod": "Cash",
    "reference": null,
    "note": "Payment on return",
    "paidAt": "2026-09-04T10:30:00+07:00"
  },
  "motorcycleStatus": "Available"
}
```

Call `POST /rentals/{id}/close` exactly once. Do not separately create charges, payments, or motorcycle status updates for the same close operation.

### Standalone finance operations

- Payment: `POST /payments` with `rentalId`, positive `amount`, `paymentMethod`, optional date/reference/note.
- Charge: `POST /charges` with `rentalId`, `chargeType`, positive `amount`, and `chargeToCustomer`.
- Expense: `POST /expenses` with `date`, `expenseType`, positive `amount`, and `currency`.

After success, use the returned record and reload the affected rental/dashboard/finance summary. Do not update totals optimistically using JavaScript arithmetic.

---

## 12. Dashboard, reports, search, and exports

### Dashboard and finance

Replace localStorage aggregations with:

- `GET /api/v2/dashboard`
- `GET /api/v2/finance/summary`

Both accept `startDate` and `endDate`. Use backend values for income, expense, net, outstanding, fleet counts, rental counts, and chart series.

### Rental reports

Use `GET /api/v2/rentals/reports` with server pagination, sort, status, and date range. Do not derive completed reports by loading every rental into the browser.

### Search contract gap

Current backend search returns:

```json
{
  "data": {
    "hits": [
      { "id": "...", "type": "rental", "title": "...", "subtitle": "...", "url": "/rentals/..." }
    ],
    "total": 1
  }
}
```

Current frontend expects `data` to be an array of richer indexed documents. Add a search adapter that maps backend hits to the UI type, or simplify the UI type to the real contract.

`POST /api/v2/search/ask` does not exist. Choose one honest behavior:

1. Hide/disable Ask AI in HTTP mode and keep keyword results, or
2. Add a separately reviewed backend endpoint with a real implementation and permission boundary.

Do not silently label ordinary SQL `LIKE` search as semantic AI search. Until backend semantic search exists, map both frontend modes to keyword search or hide the semantic mode.

### Exports

For server exports:

1. `POST /api/v2/exports`
2. Read the returned export and task identifiers.
3. Poll `GET /api/v2/tasks/{taskId}` or `GET /api/v2/exports/{id}` with bounded intervals.
4. Download only after completion.
5. Stop polling on completion, failure, component unmount, or timeout.

Keep the current client CSV export only in mock mode if desired.

---

## 13. Recommended implementation phases for GLM 5.3 Flash

### Phase 1 — Transport and auth

Files:

- `frontend/.env.example`
- `frontend/app/utils/constants/api-endpoints.ts`
- `frontend/app/composables/useApi.ts`
- `frontend/app/stores/auth.ts`
- `frontend/app/composables/auth/useAuth.ts`
- `frontend/app/utils/auth/password-reset.ts`
- auth pages and focused tests

Acceptance:

- Real login works.
- `/auth/me` hydrates the user.
- Bearer header is attached.
- One expired access token produces one refresh and one retry.
- Refresh reuse/failure clears the session.
- Logout revokes the refresh token.
- Telegram password recovery stores and uses `resetToken`.
- Mock auth still works.

### Phase 2 — Read-only entity integration

Add contracts and HTTP repositories. Integrate server-backed lists/details for motorcycles, customers, rentals, users, roles, sequences, and audit logs.

Acceptance:

- Server pagination total is used.
- Filters and sort are translated to named query parameters.
- Refreshing the browser retains only server-backed data in HTTP mode.
- Empty/error/loading states work.

### Phase 3 — CRUD

Integrate motorcycle, customer, user, role, sequence, expense, payment, and charge mutations.

Acceptance:

- Forms submit only backend-supported fields.
- Returned server records replace cache entries.
- Validation errors appear at the appropriate form/global level.
- Permission-denied operations remain denied even if UI controls are forced visible.

### Phase 4 — Rental lifecycle

Integrate rental creation, close/return, cancellation, payment, and charge flows using atomic command endpoints.

Acceptance:

- A rented motorcycle becomes Progressing after one server transaction.
- Double rental returns a conflict and does not corrupt UI state.
- Close creates charges/payment, completes rental, and updates motorcycle in one request.
- The UI reloads authoritative balances.

### Phase 5 — Dashboard, reports, settings, search, exports

Acceptance:

- Dashboard and reports no longer aggregate mock DB rows in HTTP mode.
- Existing settings repositories work through authenticated `useApi()`.
- Search uses the actual `{ hits, total }` response.
- Unsupported Ask AI/semantic behavior is not misrepresented.
- Export polling has bounded stopping conditions.

### Phase 6 — Full verification and cleanup

- Remove HTTP-mode dependencies on `getRentalDb()`.
- Keep mock-only code clearly isolated.
- Remove obsolete cookie-auth comments and HTTP-mode CSRF behavior.
- Verify English and Khmer keys for any new messages.
- Update `docs/GLM_SYSTEM_GUIDE.md` only where the final code now differs.

---

## 14. Verification procedure

### Infrastructure and backend smoke checks

```powershell
docker compose config --quiet
docker compose ps
Invoke-RestMethod http://localhost:8000/health/ready
```

Use `backend/README.md` to start isolated test dependencies before running all backend tests locally:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests
```

Do not point destructive test schema setup at the normal development database.

### Frontend setup and checks

```powershell
pnpm --dir frontend install
pnpm --dir frontend typecheck
pnpm --dir frontend lint
pnpm --dir frontend test
pnpm --dir frontend build
```

### Required integration tests

Add mocked-HTTP tests for:

- bearer header attachment
- one refresh for simultaneous 401 responses
- single retry limit
- failed refresh session cleanup
- FastAPI nested error normalization
- login/logout/me
- password recovery token handoff
- entity envelope and pagination mapping
- collection-to-endpoint mapping
- filter translation
- create and close rental payloads
- search response mapping

Add browser or manual smoke verification for:

1. Login as admin.
2. Load dashboard.
3. Create motorcycle and customer.
4. Create rental and confirm motorcycle is Progressing.
5. Record/close rental and confirm motorcycle is Available.
6. View completed rental report and finance totals.
7. Refresh browser and confirm data remains from PostgreSQL.
8. Logout and confirm protected requests fail.

---

## 15. Completion checklist

GLM must update this list as work is verified. Do not mark an item complete based only on file existence.

- [x] Bearer environment documented and enabled in real API mode
- [x] Central token utility added (`frontend/app/utils/auth/tokens.ts`; sessionStorage + memory mirror, never the `auth_user` cookie)
- [x] Authorization header added (`useApi()` attaches `Authorization: Bearer` in bearer mode)
- [x] Refresh rotation is single-flight and retries once (`app/utils/api/auth-refresher.ts` + useApi retry-once; covered by `tests/auth-refresher.spec.ts`)
- [x] Logout revokes server refresh token (`useAuth().logout()` posts `/auth/logout` with the refresh token, then clears client state in `finally`; verified live — refresh after logout returns 401)
- [x] `/auth/me` hydration implemented (`plugins/01.auth-hydrate.client.ts` re-validates stored display profiles via `/auth/me` when tokens exist)
- [x] Password-reset `resetToken` handoff implemented (`password-reset.ts` stores the verification-returned `resetToken`; reset submits `{ email, resetToken, newPassword }`)
- [x] FastAPI error normalization implemented (`app/utils/api/errors.ts`; nested `detail`, `field_errors`, and validation arrays; covered by `tests/api-errors.spec.ts`)
- [x] All required endpoint constants added (`AUTH_REFRESH`, `AUTH_TELEGRAM_LINK_CODE`, entity/finance/export paths, and the `CollectionEndpoints` map)
- [x] Typed entity repository contracts added (`app/repositories/contracts/entities.ts`)
- [x] HTTP repositories added (`app/repositories/http/entities.ts`, `http/settings.ts`, `http/settings-storage.ts`)
- [x] Mock repositories preserved (`app/repositories/mock/entities.ts` and existing mock settings repositories)
- [x] Store/components support asynchronous HTTP loading and mutation (`useAppDataStore` gains `fetchList/fetchOne/createRemote/updateRemote/deleteRemote/setStatusRemote/reloadCollection`; HTTP mode never writes localStorage; components show loading/error/retry states)
- [x] Motorcycles integrated
- [x] Customers integrated
- [x] Rentals list/detail integrated
- [x] Atomic rental creation integrated (one `POST /api/v2/rentals` with `lines[]`; no client-side numbering/pricing/status in HTTP mode)
- [x] Atomic rental close integrated (one `POST /api/v2/rentals/{id}/close` with charges + final payment; no separate writes)
- [x] Rental cancellation integrated (row action → `POST /api/v2/rentals/{id}/cancel`)
- [x] Payments integrated (atomic close payment + standalone "Record payment" action → `POST /api/v2/payments`)
- [x] Charges integrated (atomic close charges + standalone "Add charge" action → `POST /api/v2/charges`)
- [x] Expenses integrated (`RentalExpenseModal` + maintenance modal → `POST /api/v2/expenses`)
- [x] Dashboard and finance summary integrated (`GET /api/v2/dashboard`, `GET /api/v2/finance/summary`; no localStorage aggregation in HTTP mode)
- [x] Rental reports integrated (`GET /api/v2/rentals/reports` with server filters)
- [x] Users integrated with field adapter (`lastLoginAt → lastLogin`, Telegram rendered Linked/Not linked, UI-only fields stripped on write)
- [x] Roles/permission matrix integrated (flat backend permissions ↔ UI matrix rows via `utils/role/permissions.ts`; UI-only fields stripped on write)
- [x] Document sequences integrated (`nextNumberPreview` computed UI-only; `resetRule` never submitted)
- [x] Audit logs integrated to real fields (`userName → user`, `entityLabel → entity`; no fabricated trace fields)
- [x] Settings and storage verified with bearer auth (live: `/settings/app-info`, `/settings/app-config` with masked secrets, `/settings/storage` all 200)
- [x] Search response mismatch resolved (`adaptBackendSearchHits` maps `{ hits, total }` to the UI hit type; covered by `tests/search-adapter.spec.ts`)
- [x] Unsupported Ask AI/semantic behavior handled honestly (Ask AI hidden and semantic control removed in HTTP mode; `useSearch` maps both modes to the keyword backend and returns an explicit "not available" answer instead of calling the nonexistent `/search/ask`)
- [x] Export jobs integrated (HTTP mode: `POST /api/v2/exports` → bounded polling of `GET /api/v2/exports/{id}` → authenticated blob download; mock mode keeps client CSV)
- [x] English and Khmer messages synchronized (verified programmatically: 0 keys missing in either locale)
- [x] Frontend typecheck passed
- [x] Frontend lint passed
- [x] Frontend tests passed (67/67, including new transport/repo/adapter suites)
- [x] Frontend production build passed
- [x] End-to-end rental lifecycle smoke check passed (login → `/auth/me` → dashboard → create motorcycle/customer → create rental (motorcycle Progressing) → close (Completed, Paid) → motorcycle Available → dashboard/finance totals update → records persist across a fresh session → logout revokes the refresh token (401))

### Verification notes (2026-09-01)

- Frontend: `pnpm install`, `typecheck`, `lint`, `test` (67/67), and `build` all passed.
- Backend: repository-root `docker compose config --quiet` and `ps` passed; all nine services healthy.
- Live smoke: 11-step lifecycle above passed. Note on step 11: logout revokes the **refresh token** (subsequent `/auth/refresh` returns 401). The already-issued short-lived access token remains valid until its 15-minute expiry by design — bearer logout cannot retroactively invalidate stateless access tokens; the backend plan documents exactly this revocation model.
- One pre-existing workspace issue fixed to unblock the build: `frontend/app/assets/images/logo.png` was missing from the moved frontend tree and is restored from `public/logo.png`.

---

## 16. Ready-to-paste OpenCode prompt for GLM 5.3 Flash

```text
Load the `rental-moto-development` skill and implement the complete frontend/backend integration described in `docs/GLM_FRONTEND_BACKEND_INTEGRATION_GUIDE.md`.

This is an implementation task, not a planning-only response. Read `AGENTS.md`, the skill, `docs/GLM_SYSTEM_GUIDE.md`, and the integration guide before editing.

The FastAPI backend is already implemented and healthy. Do not recreate it. Treat `/api/v2` and PostgreSQL as authoritative. Preserve mock mode, but when `NUXT_PUBLIC_USE_MOCK_DATA=false`, authentication, CRUD, rental transactions, dashboard, reports, administration, settings, search, and exports must use HTTP repositories.

Work in the phases defined by the guide. For each phase:

1. Inspect every named file and its relevant tests.
2. Implement the smallest coherent change.
3. Add meaningful tests for transport, adapters, payloads, errors, and behavior.
4. Run focused checks and fix failures.
5. Update the completion checklist only for verified behavior.
6. Continue to the next phase while safe in-scope work remains.

Do not generate rental/payment/charge numbers or authoritative balances in HTTP mode. Use the atomic rental create and close endpoints. Implement bearer attachment, single-flight refresh rotation, one retry, server logout, `/auth/me` hydration, and the password-reset `resetToken` handoff exactly as documented.

Do not invent a `/search/ask` response or call SQL keyword search semantic AI. Use an honest fallback unless you separately implement and test a real backend capability.

Preserve unrelated changes and never point destructive backend tests at the normal development database.

Before finishing, run frontend typecheck, lint, tests, and build; perform the documented live rental lifecycle smoke check; and report exact results plus any unchecked checklist item. Do not claim integration is complete while required items remain unchecked.
```

