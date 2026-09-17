import type { AppRecord } from '~/config/admin-seed'
import type { ApiMeta, ApiResponse } from '~/types/rental/common'
import type { AppRolePermissionRow } from '~/types/rental/entities'
import type {
  DashboardSummary,
  EntityListQuery,
  EntityListResult,
  EntityRepository,
  FinanceRepository,
  FinanceSummary,
  RentalCloseInput,
  RentalCommandRepository,
  RentalCreateInput,
  RentalUpdateInput,
  SearchRepository,
  SearchHitItem,
} from '~/repositories/contracts/entities'
import { ApiEndpoints, CollectionEndpoints, type ApiCollection } from '~/utils/constants/api-endpoints'
import { documentSequencePreview } from '~/utils/document-sequences'
import { ROLE_DOCUMENT_TYPES, normalizePermissionRows } from '~/utils/role/permissions'

function metaOf(response: unknown): ApiMeta | null {
  const meta = (response as ApiResponse<unknown>)?.meta
  return meta ? { ...meta } : null
}

function unwrap<T>(response: unknown): T {
  if (response && typeof response === 'object' && 'data' in (response as object)) {
    return (response as ApiResponse<T>).data
  }
  return response as T
}

/** Fields the UI keeps locally but the backend does not accept on writes. */
const UI_ONLY_FIELDS = new Set([
  'nextNumberPreview',
  'resetRule',
  'userCount',
  'permissionCount',
  'permissionRows',
  'telegramUsername',
  'telegramChatId',
  'lastLogin',
  'telegramLinked',
])

function stripUiOnlyFields(input: Record<string, unknown>): Record<string, unknown> {
  const output: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(input)) {
    if (!UI_ONLY_FIELDS.has(key)) output[key] = value
  }
  return output
}

/** Flat backend permission keys â†’ UI permission-matrix rows. */
let ROLE_DOCUMENT_TYPES_CACHE: Array<{ value: string, permissionPrefix: string, actions: readonly string[] }> = []

/** Injected once by the repository selector to avoid import cycles. */
export function configureRoleMatrix(
  definitions: Array<{ value: string, permissionPrefix: string, actions: readonly string[] }>,
) {
  ROLE_DOCUMENT_TYPES_CACHE = definitions
}

function permissionRowsFromFlatKeys(keys: string[] | null | undefined): AppRolePermissionRow[] {
  if (keys?.includes('ALL_PAGES')) {
    return normalizePermissionRows(ROLE_DOCUMENT_TYPES_CACHE.map(definition => ({
      id: `perm_${definition.value}`,
      documentType: definition.value,
      onlyIfCreator: false,
      level: 0,
      actions: [...definition.actions],
    })), true)
  }
  const rows: AppRolePermissionRow[] = []
  for (const key of keys || []) {
    const separator = key.lastIndexOf('.')
    if (separator <= 0) continue
    const prefix = key.slice(0, separator)
    const action = key.slice(separator + 1)
    const definition = ROLE_DOCUMENT_TYPES_CACHE.find(item => item.permissionPrefix === prefix)
    if (!definition) continue
    rows.push({
      id: `perm_${definition.value}`,
      documentType: definition.value,
      onlyIfCreator: false,
      level: 0,
      actions: [action],
    })
  }
  return normalizePermissionRows(rows, true)
}

function permissionRowsToFlatKeys(rows: AppRolePermissionRow[]): string[] {
  const definitions = new Map(ROLE_DOCUMENT_TYPES_CACHE.map(item => [item.value, item]))
  const keys = new Set<string>()
  for (const row of rows) {
    const prefix = definitions.get(row.documentType)?.permissionPrefix
    if (!prefix) continue
    for (const action of row.actions || []) keys.add(`${prefix}.${action}`)
  }
  return [...keys].sort()
}

// Seed the matrix catalog used by both adapters.
configureRoleMatrix(
  ROLE_DOCUMENT_TYPES.map(definition => ({
    value: definition.value,
    permissionPrefix: definition.permissionPrefix,
    actions: definition.actions as readonly string[],
  })),
)

function asRecordId(value: unknown): string {
  return value == null ? '' : String(value)
}

function asRoleId(value: unknown): number | undefined {
  if (value == null || value === '') return undefined
  const parsed = typeof value === 'number' ? value : Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : undefined
}

/** Map backend user fields to the UI column keys (no fabricated data). */
function adaptUserOut(user: Record<string, unknown>): Record<string, unknown> {
  const effectivePermissions = Array.isArray(user.effectivePermissions)
    ? user.effectivePermissions.map(String)
    : []
  const roleId = asRoleId(user.roleId)
  return {
    ...user,
    id: asRecordId(user.id),
    roleId: roleId != null ? String(roleId) : '',
    effectivePermissions,
    permissionRows: permissionRowsFromFlatKeys(effectivePermissions),
    lastLogin: user.lastLoginAt ?? user.lastLogin ?? null,
    // Telegram linking is server-managed; show chat ID when linked.
    telegramUsername: user.telegramLinked
      ? String(user.telegramChatId || 'Linked')
      : '',
  }
}

/** Only the fields UserCreate / UserUpdate accept (`extra="forbid"`). */
function adaptUserIn(input: Record<string, unknown>): Record<string, unknown> {
  const output: Record<string, unknown> = {}
  const username = String(input.username ?? '').trim()
  const displayName = String(input.displayName ?? '').trim()
  const email = String(input.email ?? '').trim()
  const status = String(input.status ?? '').trim()
  const password = String(input.password ?? '')
  const roleId = asRoleId(input.roleId)
  const avatar = typeof input.avatar === 'string'
    ? input.avatar.trim()
    : typeof input.avatarUrl === 'string' ? input.avatarUrl.trim() : ''

  if (username) output.username = username
  if (displayName) output.displayName = displayName
  if (email) output.email = email
  if (status) output.status = status
  if (roleId != null) output.roleId = roleId
  if (password.trim()) output.password = password
  if (avatar) output.avatar = avatar
  return output
}

/** Map backend role fields onto the permission-matrix UI shape. */
function adaptRoleOut(role: Record<string, unknown>): Record<string, unknown> {
  const permissions = Array.isArray(role.permissions) ? role.permissions.map(String) : []
  return {
    ...role,
    id: asRecordId(role.id),
    permissions,
    permissionRows: permissionRowsFromFlatKeys(permissions),
    permissionCount: Number(role.permissionCount ?? permissions.length),
    status: 'Active',
  }
}

/** UI permission-matrix rows â†’ flat backend permission keys. */
function adaptRoleIn(input: Record<string, unknown>): Record<string, unknown> {
  const output = stripUiOnlyFields(input)
  // status is a UI-only column for roles; the backend has no such field.
  delete output.status
  if (Array.isArray(input.permissionRows)) {
    output.permissions = permissionRowsToFlatKeys(input.permissionRows as AppRolePermissionRow[])
  }
  return output
}

/** Backend audit log fields â†’ the audit-logs UI template fields. */
function adaptAuditLogOut(row: Record<string, unknown>): Record<string, unknown> {
  return {
    ...row,
    user: row.userName ?? row.user ?? null,
    entity: row.entityLabel ?? row.entityId ?? '',
    ipDevice: row.ipAddress ?? row.ipDevice ?? '',
  }
}

function adaptEntityOut(collection: ApiCollection, row: Record<string, unknown>): Record<string, unknown> {
  if (collection === 'users') return adaptUserOut(row)
  if (collection === 'roles') return adaptRoleOut(row)
  if (collection === 'auditLogs') return adaptAuditLogOut(row)
  if (collection === 'documentSequences') {
    return {
      ...row,
      nextNumberPreview: documentSequencePreview(row as AppRecord),
    }
  }
  return row
}

function adaptEntityIn(collection: ApiCollection, input: Record<string, unknown>): Record<string, unknown> {
  if (collection === 'roles') return adaptRoleIn(input)
  if (collection === 'users') return adaptUserIn(input)
  return stripUiOnlyFields(input)
}

function statusEndpoint(collection: ApiCollection, id: string): string | null {
  if (collection === 'motorcycles') return ApiEndpoints.MOTORCYCLE_STATUS(id)
  return null
}

export function createHttpEntityRepository(): EntityRepository {
  const api = useApi()

  async function list(collection: string, query: EntityListQuery = {}): Promise<EntityListResult> {
    const endpoint = CollectionEndpoints[collection as ApiCollection]
    if (!endpoint) return { items: [], meta: null }
    const response = await api.get<unknown>(endpoint, {
      query: { ...query, limit: query.limit ?? 100 },
      requestKey: `entity-list:${collection}`,
    })
    const items = unwrap<Record<string, unknown>[]>(response)
    return {
      items: (Array.isArray(items) ? items : []).map(row => adaptEntityOut(collection as ApiCollection, row)) as AppRecord[],
      meta: metaOf(response),
    }
  }

  async function get(collection: string, id: string): Promise<AppRecord | null> {
    const endpoint = CollectionEndpoints[collection as ApiCollection]
    if (!endpoint) return null
    try {
      const response = await api.get<unknown>(`${endpoint}/${id}`, {
        suppressErrorToast: true,
        cancelPrevious: false,
        requestKey: `entity-get:${collection}:${id}`,
      })
      return adaptEntityOut(collection as ApiCollection, unwrap<Record<string, unknown>>(response)) as AppRecord
    }
    catch {
      return null
    }
  }

  async function create(collection: string, input: Record<string, unknown>): Promise<AppRecord> {
    const endpoint = CollectionEndpoints[collection as ApiCollection]
    const response = await api.post<unknown>(endpoint, adaptEntityIn(collection as ApiCollection, input))
    return adaptEntityOut(collection as ApiCollection, unwrap<Record<string, unknown>>(response)) as AppRecord
  }

  async function update(collection: string, id: string, input: Record<string, unknown>): Promise<AppRecord> {
    const endpoint = CollectionEndpoints[collection as ApiCollection]
    const response = await api.put<unknown>(`${endpoint}/${id}`, adaptEntityIn(collection as ApiCollection, input))
    return adaptEntityOut(collection as ApiCollection, unwrap<Record<string, unknown>>(response)) as AppRecord
  }

  async function remove(collection: string, id: string): Promise<void> {
    const endpoint = CollectionEndpoints[collection as ApiCollection]
    // Caller shows one friendly toast; avoid duplicate technical API toasts.
    await api.delete(`${endpoint}/${id}`, { suppressErrorToast: true })
  }

  async function setStatus(collection: string, id: string, status: string): Promise<AppRecord> {
    const endpoint = statusEndpoint(collection as ApiCollection, id)
    if (!endpoint) throw new Error(`Status updates are not supported for ${collection}`)
    const response = await api.patch<unknown>(endpoint, { status })
    return adaptEntityOut(collection as ApiCollection, unwrap<Record<string, unknown>>(response)) as AppRecord
  }

  return { list, get, create, update, remove, setStatus }
}

export function createHttpRentalCommandRepository(): RentalCommandRepository {
  const api = useApi()

  async function create(input: RentalCreateInput): Promise<AppRecord[]> {
    const items = unwrap<Record<string, unknown>[]>(await api.post<unknown>(ApiEndpoints.RENTALS, input as unknown as Record<string, unknown>))
    return (Array.isArray(items) ? items : []) as AppRecord[]
  }

  async function update(id: string, input: RentalUpdateInput): Promise<AppRecord> {
    return unwrap<Record<string, unknown>>(await api.put<unknown>(ApiEndpoints.RENTAL(id), input as unknown as Record<string, unknown>)) as AppRecord
  }

  async function close(id: string, input: RentalCloseInput): Promise<AppRecord> {
    return unwrap<Record<string, unknown>>(await api.post<unknown>(ApiEndpoints.RENTAL_CLOSE(id), input as unknown as Record<string, unknown>)) as AppRecord
  }

  async function cancel(id: string, reason?: string | null): Promise<AppRecord> {
    return unwrap<Record<string, unknown>>(await api.post<unknown>(ApiEndpoints.RENTAL_CANCEL(id), { reason: reason ?? null })) as AppRecord
  }

  return { create, update, close, cancel }
}

export function createHttpFinanceRepository(): FinanceRepository {
  const api = useApi()

  return {
    async dashboard(startDate?: string, endDate?: string, requestKey = 'dashboard'): Promise<DashboardSummary> {
      const data = unwrap<DashboardSummary>(await api.get<unknown>(ApiEndpoints.DASHBOARD, {
        query: { startDate, endDate },
        requestKey,
        cancelPrevious: true,
      }))
      return {
        motorcycleStatus: data.motorcycleStatus || {},
        rentalsActive: Number(data.rentalsActive || 0),
        rentalsOverdue: Number(data.rentalsOverdue || 0),
        rentalsCompleted: Number(data.rentalsCompleted || 0),
        income: Number(data.income || 0),
        expense: Number(data.expense || 0),
        netIncome: Number(data.netIncome || 0),
        outstanding: Number(data.outstanding || 0),
        rentalsByDay: Array.isArray(data.rentalsByDay) ? data.rentalsByDay : [],
        incomeByDay: Array.isArray(data.incomeByDay) ? data.incomeByDay : [],
        expenseByDay: Array.isArray(data.expenseByDay) ? data.expenseByDay : [],
        startDate: data.startDate ?? null,
        endDate: data.endDate ?? null,
      }
    },
    async financeSummary(startDate?: string, endDate?: string): Promise<FinanceSummary> {
      const data = unwrap<FinanceSummary>(await api.get<unknown>(ApiEndpoints.FINANCE_SUMMARY, {
        query: { startDate, endDate },
        requestKey: 'finance-summary',
        cancelPrevious: true,
      }))
      return {
        income: Number(data.income || 0),
        expense: Number(data.expense || 0),
        net: Number(data.net || 0),
        outstanding: Number(data.outstanding || 0),
        startDate: data.startDate ?? null,
        endDate: data.endDate ?? null,
      }
    },
  }
}

export function createHttpSearchRepository(): SearchRepository {
  const api = useApi()

  return {
    async search(q: string, limit = 12): Promise<SearchHitItem[]> {
      const data = unwrap<{ hits?: SearchHitItem[], total?: number }>(await api.get<unknown>(ApiEndpoints.SEARCH, {
        query: { q, limit },
        requestKey: 'search-keyword',
        cancelPrevious: true,
      }))
      return (data?.hits || []).map(hit => ({
        id: String(hit.id),
        type: String(hit.type),
        title: String(hit.title),
        subtitle: hit.subtitle ?? null,
        url: String(hit.url),
      }))
    },
  }
}
