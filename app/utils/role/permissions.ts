import type { AppRolePermissionRow } from '~/types/docetra/entities'

/** Canonical action codes accepted by the future authorization API. */
export const ROLE_PERMISSION_ACTIONS = [
  'view',
  'create',
  'edit',
  'archive',
  'restore',
  'delete',
  'purge',
  'assign',
  'share',
  'export',
  'comment',
  'transition',
  'configure',
] as const

export type RolePermissionAction = (typeof ROLE_PERMISSION_ACTIONS)[number]

export interface RoleDocumentTypeDefinition {
  value: string
  labelKey: string
  permissionPrefix: string
  actions: readonly RolePermissionAction[]
}

/** Matrix rows map to the same namespace used by page and API authorization. */
const FREIGHT_ACTIONS: readonly RolePermissionAction[] = ['view', 'create', 'edit', 'delete', 'export']
const FREIGHT_VIEW_ACTIONS: readonly RolePermissionAction[] = ['view', 'export']

export const ROLE_DOCUMENT_TYPES: readonly RoleDocumentTypeDefinition[] = [
  { value: 'dashboard', labelKey: 'freight.pages.dashboard', permissionPrefix: 'dashboard', actions: ['view'] },
  { value: 'rental_motorcycles', labelKey: 'rental.pages.motorcycles', permissionPrefix: 'rental.motorcycles', actions: FREIGHT_ACTIONS },
  { value: 'rental_customers', labelKey: 'rental.pages.customers', permissionPrefix: 'rental.customers', actions: FREIGHT_ACTIONS },
  { value: 'rental_rentals', labelKey: 'rental.pages.rentals', permissionPrefix: 'rental.rentals', actions: FREIGHT_ACTIONS },
  { value: 'rental_finance', labelKey: 'rental.pages.incomeExpense', permissionPrefix: 'rental.finance', actions: ['view', 'create', 'export'] },
  { value: 'reports', labelKey: 'rental.nav.rentalReports', permissionPrefix: 'reports', actions: FREIGHT_VIEW_ACTIONS },
  { value: 'admin_organization', labelKey: 'freight.pages.organizations', permissionPrefix: 'admin.organization', actions: FREIGHT_VIEW_ACTIONS },
  { value: 'admin_users', labelKey: 'freight.pages.users', permissionPrefix: 'admin.users', actions: FREIGHT_ACTIONS },
  { value: 'admin_roles', labelKey: 'freight.pages.roles', permissionPrefix: 'admin.roles', actions: FREIGHT_ACTIONS },
  { value: 'admin_audit', labelKey: 'freight.pages.auditLogs', permissionPrefix: 'admin.audit_logs', actions: FREIGHT_VIEW_ACTIONS },
  { value: 'app_config', labelKey: 'docetra.pages.appConfig', permissionPrefix: 'settings.app_config', actions: ['view', 'edit', 'configure'] },
] as const

const ACTION_SET = new Set<string>(ROLE_PERMISSION_ACTIONS)
const LEGACY_ACTION_MAP: Record<string, RolePermissionAction | undefined> = {
  select: 'view',
  read: 'view',
  write: 'edit',
  email: 'comment',
  report: 'view',
  import: 'create',
  mask: 'view',
}

export function normalizePermissionActions(actions: readonly string[] | null | undefined): RolePermissionAction[] {
  const normalized = new Set<RolePermissionAction>()
  for (const raw of actions || []) {
    const action = ACTION_SET.has(raw)
      ? raw as RolePermissionAction
      : LEGACY_ACTION_MAP[raw]
    if (action) normalized.add(action)
  }
  if ([...normalized].some(action => action !== 'view')) normalized.add('view')
  return ROLE_PERMISSION_ACTIONS.filter(action => normalized.has(action))
}

/** Merge API rows with the current matrix catalog and discard unknown rows/actions. */
export function normalizePermissionRows(
  rows: readonly AppRolePermissionRow[] | null | undefined,
  includeEmpty = true,
): AppRolePermissionRow[] {
  const byType = new Map((rows || []).map(row => [row.documentType, row]))
  const normalized = ROLE_DOCUMENT_TYPES.map((definition) => {
    const existing = byType.get(definition.value)
    const actions = normalizePermissionActions(existing?.actions)
      .filter(action => definition.actions.includes(action))
    return {
      id: existing?.id || `perm_${definition.value}`,
      documentType: definition.value,
      onlyIfCreator: actions.length && !actions.includes('purge') ? Boolean(existing?.onlyIfCreator) : false,
      level: Math.min(9, Math.max(0, Number(existing?.level || 0))),
      actions,
    }
  })
  return includeEmpty ? normalized : normalized.filter(row => row.actions.length > 0)
}

/** Enforce action dependencies consistently for checkbox and API payload flows. */
export function setPermissionAction(
  row: AppRolePermissionRow,
  action: string,
  enabled: boolean,
): AppRolePermissionRow {
  const normalizedAction = ACTION_SET.has(action)
    ? action as RolePermissionAction
    : LEGACY_ACTION_MAP[action]
  if (!normalizedAction) return row
  const actions = new Set(normalizePermissionActions(row.actions))
  if (enabled) {
    actions.add(normalizedAction)
    actions.add('view')
  }
  else if (normalizedAction === 'view') {
    actions.clear()
  }
  else {
    actions.delete(normalizedAction)
  }
  const ordered = ROLE_PERMISSION_ACTIONS.filter(item => actions.has(item))
  return {
    ...row,
    actions: ordered,
    onlyIfCreator: ordered.length && !ordered.includes('purge') ? Boolean(row.onlyIfCreator) : false,
  }
}

/** Expanded capabilities sent with structured rows for fast authorization checks. */
export function permissionRowsToFlatKeys(rows: AppRolePermissionRow[]): string[] {
  const definitions = new Map(ROLE_DOCUMENT_TYPES.map(item => [item.value, item]))
  const keys = new Set<string>()
  for (const row of normalizePermissionRows(rows, false)) {
    const prefix = definitions.get(row.documentType)?.permissionPrefix
    if (!prefix) continue
    for (const action of row.actions) keys.add(`${prefix}.${action}`)
  }
  return [...keys].sort()
}

export type SeedRolePermissionMode = 'all' | 'operations' | 'finance' | 'customs'

/** Fixture rows for seeded roles in the mock workspace. */
export function seedRolePermissionRows(mode: SeedRolePermissionMode): AppRolePermissionRow[] {
  const allow = (prefix: string) => {
    if (mode === 'all') return true
    if (mode === 'operations') return prefix.startsWith('rental') || prefix === 'reports' || prefix === 'dashboard'
    if (mode === 'finance') return prefix.startsWith('rental') || prefix === 'reports' || prefix === 'dashboard' || prefix.startsWith('admin.audit')
    return prefix.startsWith('rental') || prefix === 'reports'
  }
  const allowedActions = (prefix: string, actions: readonly RolePermissionAction[]) => {
    if (mode === 'finance') return actions.filter(action => action === 'view' || action === 'export')
    return [...actions]
  }
  return normalizePermissionRows(
    ROLE_DOCUMENT_TYPES.map(definition => ({
      id: `perm_${definition.value}`,
      documentType: definition.value,
      onlyIfCreator: false,
      level: 0,
      actions: allow(definition.permissionPrefix) ? allowedActions(definition.permissionPrefix, definition.actions) : [],
    })),
  )
}
