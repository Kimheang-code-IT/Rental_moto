import { defineStore } from 'pinia'
import { appModules, type ModuleConfig } from '~/config/modules'
import { rentalModules } from '~/config/rental-modules'
import type { AppRecord } from '~/config/admin-seed'
import type { ApiMeta } from '~/types/rental/common'
import type { EntityListQuery } from '~/repositories/contracts/entities'
import { isApiCollection } from '~/utils/constants/api-endpoints'
import { getRentalDb, persistRentalDb, setRentalDb } from '~/repositories/mock/db'
import { assertMutableRecord } from '~/utils/rental/mutable'
import { documentSequencePreview, normalizeDocumentSequenceRecord } from '~/utils/document-sequences'
import { matchesFilter, parseFilterQuery } from '~/utils/filter/values'
import { normalizeAuditLog } from '~/utils/module/audit-logs'
import { filterScopedRecords, stampRecord } from '~/utils/rental/scope'
import { sessionFromUser } from '~/utils/rental/session-from-user'

function newId(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
}

export const useAppDataStore = defineStore('app-data', () => {
  const revision = ref(0)
  const hydrated = ref(false)

  // HTTP-mode server cache. Only successful API responses write here.
  const remoteCache = ref<Record<string, AppRecord[]>>({})
  const remoteMeta = ref<Record<string, ApiMeta | null>>({})
  const loadingCollections = ref<Record<string, boolean>>({})
  const collectionErrors = ref<Record<string, string | null>>({})

  const config = useRuntimeConfig()
  const isHttpMode = config.public.useMockData === false

  function session() {
    const auth = useAuthStore()
    return sessionFromUser(auth.user)
  }

  function persist() {
    if (isHttpMode) return
    persistRentalDb()
    revision.value += 1
  }

  function hydrate() {
    if (isHttpMode) return
    if (hydrated.value) return
    hydrated.value = true
    getRentalDb()
    revision.value += 1
  }

  function reload() {
    if (isHttpMode) {
      void reloadCollections(Object.keys(remoteCache.value))
      return
    }
    getRentalDb()
    revision.value += 1
  }

  const collections = computed(() => {
    void revision.value
    if (isHttpMode) return remoteCache.value
    return getRentalDb()
  })

  function moduleByPath(path: string) {
    return appModules.find(module => module.path === path)
      || rentalModules.find(module => module.path === path)
  }

  function decorate(collection: string, rows: AppRecord[]): AppRecord[] {
    if (collection === 'documentSequences') {
      return rows.map(row => ({
        ...normalizeDocumentSequenceRecord(row),
        nextNumberPreview: documentSequencePreview(row),
      }))
    }
    return rows
  }

  function scoped(collection: string): AppRecord[] {
    if (isHttpMode) {
      return decorate(collection, remoteCache.value[collection] || [])
    }
    hydrate()
    const db = collections.value
    const current = session()
    const rows = filterScopedRecords(db[collection] || [], current)
    return decorate(collection, rows)
  }

  function list(collection: string): AppRecord[] {
    return scoped(collection)
  }

  /** Server pagination total for a collection in HTTP mode (null otherwise). */
  function listMeta(collection: string): ApiMeta | null {
    return remoteMeta.value[collection] || null
  }

  function isLoading(collection: string): boolean {
    return Boolean(loadingCollections.value[collection])
  }

  function collectionError(collection: string): string | null {
    return collectionErrors.value[collection] || null
  }

  function get(collection: string, id: string) {
    return list(collection).find(row => row.id === id) || null
  }

  async function fetchList(collection: string, query: EntityListQuery = {}): Promise<AppRecord[]> {
    if (!isApiCollection(collection)) return []
    const { useEntityRepository } = await import('~/repositories/index')
    loadingCollections.value = { ...loadingCollections.value, [collection]: true }
    collectionErrors.value = { ...collectionErrors.value, [collection]: null }
    try {
      const result = await useEntityRepository().list(collection, query)
      remoteCache.value = { ...remoteCache.value, [collection]: result.items }
      remoteMeta.value = { ...remoteMeta.value, [collection]: result.meta }
      revision.value += 1
      return result.items
    }
    catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error)
      collectionErrors.value = { ...collectionErrors.value, [collection]: message }
      return []
    }
    finally {
      loadingCollections.value = { ...loadingCollections.value, [collection]: false }
    }
  }

  async function reloadCollection(collection: string) {
    return fetchList(collection)
  }

  async function reloadCollections(collections: string[]) {
    await Promise.all(collections.map(collection => fetchList(collection)))
  }

  async function fetchOne(collection: string, id: string): Promise<AppRecord | null> {
    if (!isApiCollection(collection)) return get(collection, id)
    const { useEntityRepository } = await import('~/repositories/index')
    const record = await useEntityRepository().get(collection, id)
    if (record) {
      const rows = remoteCache.value[collection] || []
      const index = rows.findIndex(row => String(row.id) === String(id))
      const next = index >= 0 ? rows.map((row, i) => i === index ? record : row) : [record, ...rows]
      remoteCache.value = { ...remoteCache.value, [collection]: next }
      revision.value += 1
    }
    return record
  }

  async function createRemote(collection: string, input: Record<string, unknown>): Promise<AppRecord> {
    if (!isApiCollection(collection)) {
      return create(collection, input, collection.slice(0, 3))
    }
    const { useEntityRepository } = await import('~/repositories/index')
    const created = await useEntityRepository().create(collection, input)
    const rows = remoteCache.value[collection] || []
    remoteCache.value = { ...remoteCache.value, [collection]: [created, ...rows.filter(row => String(row.id) !== String(created.id))] }
    revision.value += 1
    return created
  }

  async function updateRemote(collection: string, id: string, input: Record<string, unknown>): Promise<AppRecord> {
    if (!isApiCollection(collection)) {
      return save(collection, { ...input, id } as AppRecord)
    }
    const { useEntityRepository } = await import('~/repositories/index')
    const updated = await useEntityRepository().update(collection, id, input)
    const rows = remoteCache.value[collection] || []
    const index = rows.findIndex(row => String(row.id) === String(id))
    const next = index >= 0 ? rows.map((row, i) => i === index ? updated : row) : [updated, ...rows]
    remoteCache.value = { ...remoteCache.value, [collection]: next }
    revision.value += 1
    return updated
  }

  async function deleteRemote(collection: string, ids: string[]): Promise<void> {
    if (!isApiCollection(collection)) {
      remove(collection, ids)
      return
    }
    const { useEntityRepository } = await import('~/repositories/index')
    for (const id of ids) {
      await useEntityRepository().remove(collection, id)
    }
    const rows = remoteCache.value[collection] || []
    remoteCache.value = { ...remoteCache.value, [collection]: rows.filter(row => !ids.includes(String(row.id))) }
    revision.value += 1
  }

  async function setStatusRemote(collection: string, id: string, status: string): Promise<AppRecord> {
    if (!isApiCollection(collection)) {
      const record = get(collection, id)
      return save(collection, { ...record, id, status } as AppRecord)
    }
    const { useEntityRepository } = await import('~/repositories/index')
    const repository = useEntityRepository()
    if (!repository.setStatus) throw new Error(`Status updates are not supported for ${collection}`)
    const updated = await repository.setStatus(collection, id, status)
    const rows = remoteCache.value[collection] || []
    const index = rows.findIndex(row => String(row.id) === String(id))
    const next = index >= 0 ? rows.map((row, i) => i === index ? updated : row) : [updated, ...rows]
    remoteCache.value = { ...remoteCache.value, [collection]: next }
    revision.value += 1
    return updated
  }

  // ---- Mock-mode synchronous mutations (localStorage) ----

  function save(collection: string, record: AppRecord): AppRecord {
    if (isHttpMode) return record
    hydrate()
    const db = getRentalDb()
    const existing = (db[collection] || []).find(row => row.id === record.id) || null
    if (existing) {
      const visible = filterScopedRecords([existing], session())
      if (!visible.length) return existing
    }
    assertMutableRecord(collection, existing, record)
    const next = stampRecord({ ...record, updatedAt: new Date().toISOString() } as AppRecord, session())
    const rows = db[collection] ? [...db[collection]] : []
    const index = rows.findIndex(row => row.id === next.id)
    if (index >= 0) rows[index] = next
    else rows.unshift({ ...next, createdAt: new Date().toISOString() })
    db[collection] = rows
    setRentalDb(db)
    persist()
    return next
  }

  function create(collection: string, data: Record<string, unknown>, prefix = 'rec'): AppRecord {
    if (isHttpMode) return data as AppRecord
    const { id: _ignored, ...rest } = data
    const record = stampRecord({ ...rest, id: newId(prefix) } as AppRecord, session())
    return save(collection, record)
  }

  function remove(collection: string, ids: string[]) {
    if (isHttpMode) return
    hydrate()
    const db = getRentalDb()
    const current = session()
    const rows = (db[collection] || []).filter((row) => {
      if (!ids.includes(row.id)) return true
      return !filterScopedRecords([row], current).length
    })
    db[collection] = rows
    setRentalDb(db)
    persist()
  }

  /** Audit trails are written server-side in HTTP mode. */
  function addAudit(_action: string, _module: string, _recordNo: string, _remark = '') {
    if (isHttpMode) return
    const auth = useAuthStore()
    create('auditLogs', {
      occurredAt: new Date().toISOString().slice(0, 19),
      user: auth.user?.name || 'System',
      action: _action,
      module: _module,
      recordNo: _recordNo,
      remark: _remark,
    }, 'log')
  }

  function query(module: ModuleConfig, options: {
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
    const meta = isHttpMode ? listMeta(module.collection) : null
    // Server pagination total is authoritative when the workspace shows the
    // unfiltered server page without extra client-side narrowing.
    const clientNarrowed = Boolean(q) || Object.keys(filters).length > 0 || Boolean(dateField && (dateFrom || dateTo))
    const total = isHttpMode && meta && !clientNarrowed ? meta.total : rows.length
    return {
      rows: options.paginate === false ? rows : rows.slice(start, start + limit),
      total,
      all: rows,
    }
  }

  function related(module: ModuleConfig, record: AppRecord) {
    return (module.related || []).map((item) => {
      const target = moduleByPath(item.path)
      const rows = target ? list(target.collection).filter(row => String(row[item.foreignKey] ?? '') === String(record[item.localKey] ?? '')) : []
      return { ...item, rows, module: target }
    })
  }

  return {
    collections,
    isHttpMode,
    hydrate,
    reload,
    list,
    listMeta,
    isLoading,
    collectionError,
    get,
    save,
    create,
    remove,
    addAudit,
    query,
    related,
    fetchList,
    fetchOne,
    createRemote,
    updateRemote,
    deleteRemote,
    setStatusRemote,
    reloadCollection,
    reloadCollections,
  }
})
