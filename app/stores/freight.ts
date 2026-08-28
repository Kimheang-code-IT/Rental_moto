import { defineStore } from 'pinia'
import { freightModules, type FreightModule } from '~/config/freight-modules'
import { rentalModules } from '~/config/rental-modules'
import type { FreightRecord } from '~/config/freight-seed'
import { getLcsDb, persistLcsDb, setLcsDb } from '~/repositories/mock/db'
import { assertMutableRecord } from '~/utils/lcs/commands'
import { documentSequencePreview, normalizeDocumentSequenceRecord } from '~/utils/document-sequences'
import { matchesFilter, parseFilterQuery } from '~/utils/filter/values'
import { normalizeAuditLog } from '~/utils/freight/audit-logs'
import { filterScopedRecords, stampTenant } from '~/utils/lcs/scope'
import { sessionFromUser } from '~/utils/lcs/session-from-user'

function newId(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
}

export const useFreightStore = defineStore('freight', () => {
  const revision = ref(0)
  const hydrated = ref(false)

  function session() {
    const auth = useAuthStore()
    const tenant = useTenantStore()
    return sessionFromUser(auth.user, tenant.organizationId, tenant.branchId)
  }

  const tenant = useTenantStore()
  watch(() => [tenant.organizationId, tenant.branchId, tenant.assignedBranches.length], () => {
    revision.value += 1
  })

  function persist() {
    persistLcsDb()
    revision.value += 1
  }

  function hydrate() {
    if (hydrated.value) return
    hydrated.value = true
    getLcsDb()
    revision.value += 1
  }

  function reload() {
    getLcsDb()
    revision.value += 1
  }

  const collections = computed(() => {
    void revision.value
    return getLcsDb()
  })

  function moduleByPath(path: string) {
    return freightModules.find(module => module.path === path)
      || rentalModules.find(module => module.path === path)
  }

  function scoped(collection: string): FreightRecord[] {
    hydrate()
    const db = collections.value
    const current = session()
    const rows = filterScopedRecords(db[collection] || [], current)
    if (collection === 'documentSequences') {
      const organizationName = String(useAuthStore().user?.organizationName || '')
      return rows.map(row => ({
        ...normalizeDocumentSequenceRecord(row),
        organizationName,
        nextNumberPreview: documentSequencePreview(row),
      }))
    }
    return rows
  }

  function list(collection: string): FreightRecord[] {
    return scoped(collection)
  }

  function get(collection: string, id: string) {
    return list(collection).find(row => row.id === id) || null
  }

  function getJobByNo(jobNo: string) {
    const value = jobNo.trim()
    if (!value) return null
    return list('jobs').find(row => String(row.jobNo || '') === value) || null
  }

  function save(collection: string, record: FreightRecord): FreightRecord {
    hydrate()
    if (['receivables', 'payables', 'profitability'].includes(collection)) return record
    const db = getLcsDb()
    const existing = (db[collection] || []).find(row => row.id === record.id) || null
    if (existing) {
      const visible = filterScopedRecords([existing], session())
      if (!visible.length) return existing
    }
    assertMutableRecord(collection, existing, record)
    const next = stampTenant({ ...record, updatedAt: new Date().toISOString() } as FreightRecord, session())
    const rows = db[collection] ? [...db[collection]] : []
    const index = rows.findIndex(row => row.id === next.id)
    if (index >= 0) rows[index] = next
    else rows.unshift({ ...next, createdAt: new Date().toISOString() })
    db[collection] = rows
    setLcsDb(db)
    persist()
    return next
  }

  function create(collection: string, data: Record<string, unknown>, prefix = 'rec'): FreightRecord {
    const { id: _ignored, ...rest } = data
    const record = stampTenant({ ...rest, id: newId(prefix) } as FreightRecord, session())
    return save(collection, record)
  }

  function remove(collection: string, ids: string[]) {
    hydrate()
    const db = getLcsDb()
    const current = session()
    const rows = (db[collection] || []).filter((row) => {
      if (!ids.includes(row.id)) return true
      return !filterScopedRecords([row], current).length
    })
    db[collection] = rows
    setLcsDb(db)
    persist()
  }

  function addAudit(action: string, module: string, recordNo: string, remark = '') {
    const auth = useAuthStore()
    create('auditLogs', {
      occurredAt: new Date().toISOString().slice(0, 19),
      user: auth.user?.name || 'System',
      action,
      module,
      recordNo,
      remark,
    }, 'log')
  }

  function query(module: FreightModule, options: {
    q?: string
    filters?: Record<string, string | string[]>
    page?: number
    limit?: number
    paginate?: boolean
    dateField?: string
    dateFrom?: string
    dateTo?: string
    sortKey?: string
    sortDir?: 'asc' | 'desc'
  }) {
    const q = (options.q || '').trim().toLowerCase()
    const filters = options.filters || {}
    let rows = list(module.collection)
    if (module.collection === 'auditLogs') rows = rows.map(normalizeAuditLog)
    if (q) {
      rows = rows.filter(row => Object.values(row).some(value => String(value ?? '').toLowerCase().includes(q)))
    }
    for (const [key, value] of Object.entries(filters)) {
      if (!parseFilterQuery(value).length) continue
      rows = rows.filter(row => matchesFilter(row[key], value))
    }
    const dateField = options.dateField
    const dateFrom = (options.dateFrom || '').slice(0, 10)
    const dateTo = (options.dateTo || '').slice(0, 10)
    if (dateField && (dateFrom || dateTo)) {
      rows = rows.filter((row) => {
        const day = String(row[dateField] ?? '').slice(0, 10)
        if (!day) return false
        if (dateFrom && day < dateFrom) return false
        if (dateTo && day > dateTo) return false
        return true
      })
    }
    if (options.sortKey && options.sortDir) {
      const dir = options.sortDir === 'desc' ? -1 : 1
      const sortKey = options.sortKey
      rows = [...rows].sort((a, b) => String(a[sortKey] ?? '').localeCompare(String(b[sortKey] ?? ''), undefined, { numeric: true }) * dir)
    }
    const page = options.page || 1
    const limit = options.limit || 10
    const start = (page - 1) * limit
    return {
      rows: options.paginate === false ? rows : rows.slice(start, start + limit),
      total: rows.length,
      all: rows,
    }
  }

  function related(module: FreightModule, record: FreightRecord) {
    return (module.related || []).map((item) => {
      const target = moduleByPath(item.path)
      const rows = target ? list(target.collection).filter(row => String(row[item.foreignKey] ?? '') === String(record[item.localKey] ?? '')) : []
      return { ...item, rows, module: target }
    })
  }

  return {
    collections,
    hydrate,
    reload,
    list,
    get,
    getJobByNo,
    save,
    create,
    remove,
    addAudit,
    query,
    related,
  }
})
