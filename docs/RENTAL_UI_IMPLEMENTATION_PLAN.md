# Rental UI Implementation Plan — Phase 2 (Operational Screens)

> **Status: IMPLEMENTED (Phases 2A–2I complete).**
> Verified: vitest **31/31 pass** (freight specs removed with the freight code); all 14 routes
> render clean; role matrix scoped to rental modules (38 keys); Settings = exactly 3 tabs;
> HollyWing Motor branding + dynamic currency preference live; freight modules deleted.
> Known UI-drive limitation: the New Rental USelect pair could not be exercised via headless
> synthetic events (reka select ignores them) — logic is code-reviewed, store flows proven via
> the Payment/Close modal tests. Manual click-through recommended on first run.
> **Role scope: UI only.** All screens run on the existing **mock data layer**; no API, backend,
> or business-rule engine is built here. Numbers shown (late fees, balances, KPIs) are
> seed/mock values rendered by UI — real calculations arrive with the functional phase.
> Predecessor: `UI_CHANGE_PLAN.md` (sidebar trim — implemented).

---

## 1. Architecture we're reusing (grounded in the template)

The template is **config-driven**; we add modules, not bespoke pages:

| Template piece | File | Reused for |
|---|---|---|
| Module config factory (`createModule`, `f()`, `col()`) | `app/config/freight-modules.ts` | New `app/config/rental-modules.ts` defining Motorcycle, Customer, Rental |
| Generic list/form/detail renderer | `app/components/freight/ModulePage.vue`, `WorkspaceView.vue` | All rental list + detail screens |
| Dashboard kit | `DashboardAppKpiSection`, `DashboardAppSummaryCard`, `DashboardAppEChart` (`app/components/dashboard/`) | Rental dashboard (spec §4) |
| Table kit | `app/components/table/AppListTable.vue`, `app/utils/table/*` (badges, pagination, row actions) | All tables incl. Active Rental preview |
| Form kit | `FieldGrid.vue`, `FieldInput.vue`, `AppDocumentForm.vue` | Motorcycle/Customer/Rental forms |
| Dialogs | `AppConfirmDialog`, `AppExportDialog`, `AppDatePickerPopover`, `AppDateRangeFilter` | Close-rental confirm, exports, filters |
| Settings page | `app/components/settings/SystemSettingsPage.vue` + `app/config/settings-schemas.ts` (`systemSettingsTabs` = filtered `appConfigTabs`) | Trim to exactly 3 tabs (spec §22) |
| Permission matrix | `AppRolePermissionMatrix.vue` | Module list update (spec §19) |
| Mock data | `app/utils/freight-seed.ts`, `lcs-seed.ts`, `app/repositories/mock/db.ts` | New `rental-seed.ts` + mock repositories |
| Auth/permissions | `app/middleware/auth.global.ts`, `app/utils/auth/mock-login.ts`, `app/composables/role/permissions.ts` | New rental permission keys + mock accounts |
| i18n | `i18n/locales/en.json`, `km.json` | Khmer-first labels (spec §1) |

**Key precedent:** each page file is a thin wrapper — e.g. `pages/quotations/index.vue` is 7 lines
(`definePageMeta` + `<FreightModulePage />`). We follow the same pattern for all rental routes.

---

## 2. Target sidebar (spec §2) — replaces the interim "Dashboard + Administration only" state

| Khmer label | English | Route | Status |
|---|---|---|---|
| ផ្ទាំងគ្រប់គ្រង | Dashboard | `/` | rebuild content (§4 of this plan) |
| ម៉ូតូ | Motorcycles | `/motorcycles` | **new** |
| អតិថិជន | Customers | `/customers` | **new** |
| ការជួល | Rentals | `/rentals` | **new** (ACTIVE + OVERDUE only) |
| ចំណូល និងចំណាយ | Income & Expense | `/income-expense` | **new** |
| របាយការណ៍ការជួល | Rental Reports | `/rental-reports` | **new** |
| Administration | Administration | — | kept from Phase 1, unchanged |

Freight items stay out (removed in Phase 1). Freight modules are **deleted outright** at the end
of the build (Phase 2I — owner decision), after the rental screens are verified against them.

---

## 3. Phases

### Phase 2A — Data layer + navigation shell
**Files:**
- `app/config/rental-modules.ts` — module definitions (columns/fields/filters/statuses per spec §5–§9).
- `app/config/rental-options.ts` — option lists: motorcycle status (`AVAILABLE/RENTED/MAINTENANCE/INACTIVE`), rental status (`ACTIVE/OVERDUE/COMPLETED/CANCELLED`), payment methods, charge types (`DAMAGE/LOST_ITEM/CLEANING/OTHER`), rate types (`DAILY/MONTHLY`), identity types; **currency list per owner's mockup**: `USD, KHR, THB, VND, SGD, EUR, GBP, JPY, …` (full ISO list, `code — name` labels).
- `app/utils/rental-seed.ts` — demo data: ~12 motorcycles, ~10 customers, ~8 active/overdue rentals, ~15 completed rentals, payments/charges rows.
- `app/repositories/mock/db.ts` (+ collections type) — add `motorcycles`, `rentalCustomers`, `rentals`, `rentalPayments`, `rentalCharges`.
- `app/composables/layout/useMenu.ts` — add the 5 nav items + `ROUTE_PERMISSION` entries.
- `app/middleware/auth.global.ts` + `app/utils/auth/mock-login.ts` — permission keys (below).

**New permission keys** (page-level, mirroring template convention `module.resource.action`):
`motorcycles.view/create/edit`, `customers.view/create/edit`, `rentals.view/create/edit`,
`rentals.close`, `rentals.payment`, `rentals.charge`, `finance.view`, `finance.expense.create`,
`reports.view` (reuse). Mock accounts: `SuperAdmin` (all), `Rental Staff` (no user/role/settings),
`Report Viewer` (read-only, per spec §24).

**Mock accounts gain:** `staff@rental.local` / `viewer@rental.local`, password `123456` (same pattern as existing mocks).

**Currency preference (owner decision — dynamic, per user):**
- `app/stores/preferences.ts` gains a `currency` preference (persisted to localStorage like
  locale/font-size), default `USD`.
- Settings → Localization → Currency field (spec §22.1) binds to the same preference, using the
  full currency select from the owner's mockup (`USD — US Dollar`, `KHR — Cambodian Riel`, …).
- All rental money cells, KPI cards, modal totals, and the invoice render through the template's
  existing `formatMoney(value, currency)` (`useFreight.ts`, Intl-based) fed by the preference —
  no hardcoded `$`.
- **Assumption (flag if wrong):** no exchange-rate conversion in UI scope. Records store amounts
  in their own currency (Motorcycle form has a Currency field per spec §6); the preference drives
  *formatting and defaults for new records*. Rental seed data is single-currency (USD) so KPI
  aggregates stay consistent; real FX conversion belongs to the functional phase.

### Phase 2B — Motorcycle & Customer screens (spec §5–§8)
**Files:** `app/pages/motorcycles/index.vue`, `new.vue`, `[id].vue`; `app/pages/customers/index.vue`, `new.vue`, `[id].vue` — all thin `ModulePage` wrappers.

- **Motorcycle list:** columns Code/Model/Plate/Chassis/Engine/Daily Rate/Monthly Rate/Status/Actions; filters: search, status; row actions: View, Edit, Mark Maintenance, Activate/Deactivate (permission-gated, hidden per spec §1).
- **Motorcycle form:** fields per spec §6; validation: unique plate, rates ≥ 0, required model/code (client-side, mirroring template validation UX).
- **Customer list:** Code/Full Name/Identity/Phone/Company/Status/Actions; search.
- **Customer form:** fields per spec §8.

Status badges reuse the template's table theme mapping (color + text, spec §1).

### Phase 2C — Rental screen core (spec §9, §11)
**Files:** `app/pages/rentals/index.vue`, `new.vue`, `[id].vue`.

- **List shows only `ACTIVE`/`OVERDUE`** — enforced in the mock repository query, not just UI filter (mirrors the critical requirement in spec §9).
- Columns per spec §9.2 (15 columns; horizontal scroll on tablet/mobile per spec §24).
- Filters: search, status (ACTIVE/OVERDUE), due-date range (`AppDateRangeFilter`).
- Row actions per spec §9.3: View, Edit, Add Payment, Add Charge, Return/Close, Print Invoice. **No Print Rental Agreement** (explicit doc rule).
- **Detail screen** (`[id].vue`): 8 sections per spec §11 — summary, customer, motorcycle, dates, charges table, payments table, balance, activity history. Activity history sourced from the template's audit-trail mock pattern.

### Phase 2D — Transaction modals (spec §10, §12–§15)
New components under `app/components/rental/`:

1. **`RentalCreatePanel.vue`** (New Rental): customer search-select + "add new" shortcut; motorcycle select limited to `AVAILABLE` (repo-level filter); rental fields (start, due, rate type, rate, deposit, discount, note); right summary panel (motorcycle, rate, estimated duration, estimated charge, deposit); Cancel / Create Rental. Create requires confirm (high-impact per spec §1).
2. **`RentalPaymentModal.vue`**: amount, method, paid datetime, reference, note; header shows Total Due / Paid / Outstanding.
3. **`RentalChargeModal.vue`**: charge type (4 fixed types), description, amount, "charge to customer" toggle.
4. **`RentalCloseModal.vue`**: read-only due datetime / late fee / paid / outstanding; inputs: actual return datetime, condition, note, next motorcycle status (Available/Maintenance); Confirm Close → row leaves Rental list (repo moves it out of ACTIVE/OVERDUE), toast, record appears in Rental Reports.
5. **`RentalInvoicePreview.vue`**: read-only invoice per spec §15 content list; Print (new print stylesheet scoped to the modal) + Save PDF (browser print-to-PDF) + Close.

All modals use `AppConfirmDialog`/`UModal` conventions already in the template; permission-gated
(row action hidden when key missing, spec §1/§24).

### Phase 2E — Income & Expense + Rental Reports (spec §16–§17)
**Files:** `app/pages/income-expense/index.vue`, `app/pages/rental-reports/index.vue`.

- **Income & Expense:** month/year (+optional range) filters; KPI row Income/Expense/Net/Outstanding (`AppKpiSection`); monthly transaction table; Add Expense button (permission `finance.expense.create`); export via `AppExportDialog` (PDF/CSV).
- **Rental Reports:** completed-rentals-only query; filters date range/customer/motorcycle/payment status/created-by; 14 columns per spec §17; actions View, View Invoice, Export.

### Phase 2F — Dashboard rebuild (spec §4)
**File:** rewrite `app/components/freight/DashboardView.vue` content → rename-to/replace with `RentalDashboardView.vue` (old file deleted — clean cutover; `pages/index.vue` updated).

- **KPI row 1 (fleet):** total motorcycles, available, rented, maintenance.
- **KPI row 2 (operations/finance):** active rentals, overdue rentals, total customers, income this month, expense this month, outstanding (10 KPIs per spec §4.1).
- **Chart 1:** rentals-by-day bar chart — month (+year) selector, export, tooltip date+count.
- **Chart 2:** income/expense — year + month/All-Months selectors, export, two series.
- **Active Rental preview:** compact `AppListTable` of newest active rentals + "មើលទាំងអស់" link to `/rentals`.
- Dark/light theme handling reused from existing `DashboardView` axis-color logic.

### Phase 2G — Administration alignment (spec §18–§22)
Mostly **exists**; changes are trims/labels:

1. **Settings → exactly 3 tabs.** `SYSTEM_SETTINGS_TAB_IDS` currently includes `email`; change set to `{ localization, telegram, security }`, and drop the Email tab's connection UI from `SystemSettingsPage.vue`. Telegram tab gains the 6 rental-notify toggles + daily/monthly summary fields per spec §22.2 (UI only — toggle states, no sending logic). Security/localization field lists verified against spec §22.1/§22.3.
2. **Users screen** (spec §18): template table already covers columns/actions; verify column list matches, add Last Login display from mock data.
3. **Roles matrix** (spec §19): module rows in `AppRolePermissionMatrix` change to Dashboard/Motorcycles/Customers/Rentals/Finance/Reports/Users/Roles/Settings/Telegram Configuration; role presets renamed Admin / Rental Staff / Report Viewer.
4. **Audit Logs** (spec §20): exists; verify filters/columns/detail drawer against spec — expected no-change or minor.
5. **Document Sequences** (spec §21): add `RENTAL / RNT-{YYYY}- / padding 6 / Yearly` example to seed so the preview shows `RNT-2026-000001`.

### Phase 2H — States, responsive, polish (spec §23/§24 + ERP pattern §22)
- Empty states: Khmer messages, e.g. `មិនមានការជួលកំពុងដំណើរការ` on Rentals; loading skeletons (template pattern); retryable error banners.
- Responsive pass: tables → horizontal scroll, action column → three-dot menu on mobile, dashboard stacks.
- Print stylesheet for invoice only.
- **Branding → HollyWing Motor** (owner decision; logo provided at
  `app/assets/images/m-logo.png`):
  - `AppSlidebar.vue`: logo swap to `HollyWing Motor`, tagline
    `Forwarding System` → `MOTORCYCLE RENTAL` (assumption — confirm), aria/alt text.
  - `AppHeader.vue`: title fallbacks → `HollyWing Motor`.
  - i18n `common.brand.{name,tagline,logoAlt}`, `aboutCopyright`, login-page terms strings
    (legacy forwarding mentions), `app.description/keywords` SEO strings in `nuxt.config`.
  - Mock login and settings `applicationName` use HollyWing Motor. The final system is single-business and has no organization or branch entities.
  - `public/logo.png` + OG image regeneration (`scripts/generate-og-image.mjs`) with the new logo.

### Phase 2I — Freight module removal (owner decision: "remove, we don't need it anymore")
Runs **last**, after 2A–2H are visually approved. Delete in one clean cutover:

| Layer | Removed | Kept (shared infra) |
|---|---|---|
| Pages | `pages/quotations/*`, `service-orders/*`, `service-charges/*`, `finance/*`, `master-data/*`, `configuration/*`, `reports/*` | all rental + administration + auth pages |
| Config | Legacy forwarding module entries, reports, and options (directions/containers/customs…) | `rental-*` configs and `settings-schemas.ts` |
| Seed | Legacy quotations, jobs, shipments, customs, and accounting collections | users/roles/audit/documentSequences/systemSettings seed; no organizations or branches |
| Components | freight business components (`Job*`, `DocumentView` freight-specifics) | `ModulePage`, `WorkspaceView`, dashboard kit, table/form/dialog kit |
| i18n | Legacy forwarding keys not reused by rental/admin | `rental.*`, `core.*`, `app.*` |
| Tests | specs covering deleted routes (`job-*`, `quotations`-related, `freight` format specs) | admin/auth/table/setting specs |
| Nav | freight `ROUTE_PERMISSION` entries, freight search-index seeds | rental + admin entries |

Verification for 2I specifically: clean build, no dead links (sidebar/search/reference links),
admin screens still fully functional, vitest green.

---

## 4. i18n plan
- All new labels go into `en.json` + `km.json` under a new `rental.*` namespace (mirrors `freight.*`); Khmer strings taken verbatim from the spec (e.g. `ម៉ូតូ`, `ការជួល`, `មើលទាំងអស់`).
- Module configs carry `labelKm`/`titleKm` like `freight-modules.ts` does.
- `freight.*` keys are deleted with Phase 2I (keys the rental/admin screens reuse survive under
  their existing paths until then).

## 5. Explicitly out of scope (this phase)
1. Real API/server persistence — everything is the existing mock repo pattern.
2. Business-rule engine: late-fee accrual, conflict detection on double-booking, overdue escalation. UI renders mock/mock-computed values; the Create Rental conflict message is stubbed as a client-side check to demonstrate the spec §4 SOP error state.
3. Telegram actual sending; email anything (Email tab removed per spec §22).
4. Authentication backend — mock login accounts remain.
5. ~~Deleting freight pages/routes/modules~~ — **now in scope as Phase 2I** (owner decision).

## 6. Verification plan (per phase, before marking done)
1. `npx pnpm vitest run` — suite green except the 5 known pre-existing failures.
2. Dev-server walkthrough per role: SuperAdmin sees everything; Rental Staff sees no Administration write actions; Report Viewer sees no create/edit/close actions anywhere (spec §24).
3. Rentals list assertion: completed rental never appears; after Close, row moves to Rental Reports.
4. Modal flows: Create Rental with unavailable motorcycle → blocked; Add Payment updates Outstanding display; Close sets motorcycle to chosen next status.
5. Visual screenshots (desktop 1440px + mobile 390px) per major screen.
6. Language toggle EN/KM on every new screen.

## 7. Risks
- **Mock-layer drift:** seed data shapes must match the eventual API contract; mitigation — collections keyed and named exactly as doc `05_database_design.md` entities.
- **15-column table usability:** mitigated by template's horizontal-scroll + pinned-actions pattern; will visually verify at 1366px width.
- **Config-factory limits:** if a spec screen doesn't fit `createModule` (e.g. New Rental composite form), we build a bespoke component (2D) rather than bending the config — the template already has this split (`WorkspaceView` vs `ModulePage`).

## 9. Decisions from owner (first review round — resolved)
1. **Branding:** `HollyWing Motor`, logo `app/assets/images/m-logo.png` (already in repo) — Phase 2H.
2. **Currency:** dynamic per user preference (owner's currency-select mockup: USD/KHR/THB/VND/SGD/EUR/GBP/JPY…) — Phase 2A plumbing, bound to Settings Localization; **no FX conversion** (assumption, see §3 Phase 2A).
3. **Freight modules:** removed outright — Phase 2I, last.
4. **Build order:** 2A → 2B → 2C → 2D → 2E → 2F → 2G → 2H → 2I, as proposed.

Remaining micro-confirmations (defaults chosen, no blocker): tagline text `MOTORCYCLE RENTAL`;
brand name casing exactly `HollyWing Motor`.

