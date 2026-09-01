import type { AppRecord } from '~/config/admin-seed'
import { createRentalSystemSeed } from '~/config/rental-system-seed'
import { createRentalSeed } from '~/config/rental-seed'
import { normalizeDocumentSequenceRecord } from '~/utils/document-sequences'

export const RENTAL_STORAGE_KEY = 'rental-moto-data-v9'

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

let memory: Record<string, AppRecord[]> | null = null

export function createFreshRentalDb() {
  const seed = { ...createRentalSystemSeed(), ...createRentalSeed() }
  seed.idempotency = []
  return clone(seed)
}

export function getRentalDb(): Record<string, AppRecord[]> {
  if (memory) return memory
  if (import.meta.client) {
    try {
      const raw = localStorage.getItem(RENTAL_STORAGE_KEY)
      if (raw) {
        memory = JSON.parse(raw) as Record<string, AppRecord[]>
        const fresh = createRentalSystemSeed()
        for (const [collection, rows] of Object.entries(fresh)) {
          if (!Array.isArray(memory[collection])) memory[collection] = clone(rows)
        }
        for (const collection of ['users', 'auditLogs', 'documentSequences']) {
          const freshRows = fresh[collection] || []
          const existingRows = memory[collection] || []
          const merged = freshRows.map((freshRow) => {
            const existing = existingRows.find(row => row.id === freshRow.id)
            return existing ? { ...clone(freshRow), ...existing } : clone(freshRow)
          })
          memory[collection] = [...merged, ...existingRows.filter(row => !freshRows.some(freshRow => freshRow.id === row.id))]
        }
        memory.documentSequences = (memory.documentSequences || []).map(normalizeDocumentSequenceRecord)
        if (!memory.idempotency) memory.idempotency = []
        return memory
      }
    }
    catch {
      // Fall through to seed.
    }
  }
  memory = createFreshRentalDb()
  persistRentalDb()
  return memory
}

export function setRentalDb(next: Record<string, AppRecord[]>) {
  memory = next
  persistRentalDb()
}

export function persistRentalDb() {
  if (!import.meta.client || !memory) return
  localStorage.setItem(RENTAL_STORAGE_KEY, JSON.stringify(memory))
}

export function resetRentalDb() {
  memory = createFreshRentalDb()
  persistRentalDb()
  return memory
}

export function delay(ms = 40) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
