# UI Change Plan — Sidebar Trim for Bike Rental System

> **Status: IMPLEMENTED** (was FOR REVIEW). Sidebar trim confirmed by owner: keep
> Dashboard + Administration only, remove the rest (incl. Quotations — see §1.1).
> Verified: vitest 97/102 pass (5 failures pre-existing on pristine tree, unrelated);
> visual check + ⌘K search + URL permission-guard regression all pass on the dev server.
> **Scope: UI only.** No routes, permissions, data, or business logic are touched in this change.

---

## 1. Context

The LCS Freight Forwarding app (`Freight-Forwarding/`) is the UI template being reused for the
Motorcycle (Bike) Rental system. The current sidebar (see `ui.png`) carries the full freight
navigation:

| # | Current sidebar item | Type |
|---|---|---|
| 1 | Dashboard | link → `/` |
| 2 | Quotations | link → `/quotations` |
| 3 | Service Orders | link → `/service-orders` |
| 4 | Service Charges | link → `/service-charges` |
| 5 | Finance | collapsible group (5 children) |
| 6 | Operations Reports | collapsible group (4 children) |
| 7 | Financial Reports | collapsible group (8 children) |
| 8 | Master Data | collapsible group (7 children) |
| 9 | Configuration | collapsible group (4 children) |
| 10 | Administration | collapsible group (7 children) |

**Requested change:** the vertical sidebar keeps **only Dashboard and Administration**.
All other sections are removed from the sidebar.

This matches the rental docs (`relevant_docs/06_ui_screen_specification.md` §2): the rental nav
will later be its own set of items (Motorcycles, Customers, Rentals, Income & Expense, Rental
Reports) — those are a **separate phase**, added after this trim is approved and the rental
modules exist.

### 1.1 Decision record — why Quotations is removed, not repurposed

Repurposing Quotations (e.g. into a rental "booking" page) was considered and rejected:

- The rental docs define **no quotation stage**. `03_business_process.md` (17 SOPs) goes
  Customer → Motorcycle (AVAILABLE) → **Create Rental** → Payment/Charges → Close → Invoice →
  Reports. Zero mentions of quotation across all 8 docs.
- Quotations exist in freight because pricing is negotiated per shipment. In rental, pricing
  is **fixed on the Motorcycle record** (Daily/Monthly Rate); the New Rental form (UI spec §10)
  already captures rate type, rate, deposit, discount — Quotations' job has no rental analog.
- Repurposing would drag freight machinery along: `sales.quotations.*` permissions,
  Draft→Sent→Accepted→Converted status machine, revision history, convert-to-job command,
  DB collection, i18n keys — all unused by the rental SOP.

Freight → rental module mapping (for later phases):

| Freight concept | Rental equivalent |
|---|---|
| Quotations + Service Orders | Rentals (one screen) |
| Service Charges | Additional Charges (inside Rental detail) |
| Finance / Financial Reports | Monthly Income & Expense |
| Master Data | Motorcycles, Customers |

---

## 2. Target state (after this change)

```
├── Dashboard
└── Administration          (collapsible, unchanged children)
    ├── Organizations
    ├── Branches
    ├── Users
    ├── Roles
    ├── Document Sequences
    ├── Settings
    └── Audit Logs
```

---

## 3. Files changed

### 3.1 `app/composables/layout/useMenu.ts` — the only functional edit

`links` (lines 107–162) is the **single source of truth** for the sidebar.

- **Keep:** line 109 (Dashboard) and lines 151–159 (the `administration` group).
- **Remove:** lines 110–150 — Quotations, Service Orders, Service Charges, and the
  `finance`, `operations-reports`, `financial-reports`, `master`, `configuration` groups.

Explicitly **kept untouched** in the same file:

- `ROUTE_PERMISSION` (lines 36–77): stays complete. The freight pages still exist and remain
  reachable by direct URL; the global auth middleware (`app/middleware/auth.global.ts`) still
  guards them with these permissions. Removing the map entries would only weaken URL-level
  guarding — not a UI concern, and it gets replaced wholesale when rental modules land.
- `group()`, `filterItem()`, collapse persistence logic: generic infrastructure, no change.

### 3.2 Automatic downstream effects — no edits needed

| Consumer | Why it's safe |
|---|---|
| `useGlobalSearch.ts` (`⌘K` search) | Builds its "Pages" group from `useMenu().links` → search results shrink to Dashboard + Administration automatically. |
| `AppSlidebar.vue` | Renders whatever `links[0]` contains; no hardcoded items. |
| `AppHeader.vue` / collapse button | Layout-only. |
| i18n (`km.json`, `en.json`) | Both labels kept (`freight.nav.dashboard`, `freight.nav.administration`) already exist in Khmer and English. Removed keys become unused but harmless (cleaned up in the rental-module phase, not now). |

### 3.3 Noted, not changed (dead config, out of UI scope)

- `app/config/freight-modules.ts` `freightNavGroups` (line 1512): defined but has **zero
  consumers** in the codebase. Untouched here; flagged for deletion when the rental modules
  replace freight modules.

---

## 4. Explicitly out of scope (later phases, after approval)

1. Rental navigation items (Motorcycles / Customers / Rentals / Income & Expense / Rental
   Reports) — added when their pages exist.
2. Branding: "LCS Freight / Forwarding System" title + logo in `AppSlidebar.vue` (lines 68–69).
   *(Decision needed — cheap to include in this pass if you want the shell rebranded now.)*
3. Removing freight pages/routes/permissions — replaced by rental modules, not deleted ad hoc.
4. Settings tabs restructuring (Localization / Telegram / Security) per docs §Administration.
5. Khmer-first label pass and dashboard KPI/chart content for rental.

---

## 5. Verification plan (after implementation)

1. `pnpm dev` → visual check: sidebar shows exactly Dashboard + Administration (expanded and
   collapsed states, narrow-viewport auto-collapse still works).
2. Direct URL to a trimmed section (e.g. `/quotations`) → still renders with permission guard
   intact (regression proof that only nav visibility changed).
3. `⌘K` search → "Pages" group lists only Dashboard + Administration.
4. `pnpm vitest run` → full suite stays green (nav trim should not touch any spec; `traceability`
   and `lcs-domain` specs don't read `links`).

---

## 6. Risk assessment

**Low.** One file edited; change is a pure array literal reduction in a computed. Permission
guarding, routing, and search infrastructure are untouched. Fully revertible by restoring one
array.
