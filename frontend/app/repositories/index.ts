import type { AppConfigRepository, AppInfoRepository, StorageRepository } from '~/repositories/contracts/settings'
import type {
  EntityRepository,
  FinanceRepository,
  RentalCommandRepository,
  SearchRepository,
} from '~/repositories/contracts/entities'
import { createHttpAppConfigRepository, createHttpAppInfoRepository } from '~/repositories/http/settings'
import { createHttpStorageRepository } from '~/repositories/http/settings-storage'
import { createMockAppConfigRepository, createMockAppInfoRepository, createMockStorageRepository } from '~/repositories/mock/settings'
import {
  createHttpEntityRepository,
  createHttpFinanceRepository,
  createHttpRentalCommandRepository,
  createHttpSearchRepository,
} from '~/repositories/http/entities'
import {
  createMockEntityRepository,
  createMockFinanceRepository,
  createMockRentalCommandRepository,
  createMockSearchRepository,
} from '~/repositories/mock/entities'

let mode: 'mock' | 'http' | null = null
let appInfoRepo: AppInfoRepository
let appConfigRepo: AppConfigRepository
let storageRepo: StorageRepository
let entityRepo: EntityRepository
let rentalCommandRepo: RentalCommandRepository
let financeRepo: FinanceRepository
let searchRepo: SearchRepository

/** Allow tests (or future re-init) to force a repository mode. */
export function setRepositoryMode(next: 'mock' | 'http' | null) {
  mode = next
}

export function currentRepositoryMode(): 'mock' | 'http' {
  return mode || (useRuntimeConfig().public.useMockData !== false ? 'mock' : 'http')
}

function ensureRepositories() {
  const nextMode = useRuntimeConfig().public.useMockData !== false ? 'mock' : 'http'
  if (mode === nextMode) return
  mode = nextMode
  const mock = nextMode === 'mock'
  appInfoRepo = mock ? createMockAppInfoRepository() : createHttpAppInfoRepository()
  appConfigRepo = mock ? createMockAppConfigRepository() : createHttpAppConfigRepository()
  storageRepo = mock ? createMockStorageRepository() : createHttpStorageRepository()
  entityRepo = mock ? createMockEntityRepository() : createHttpEntityRepository()
  rentalCommandRepo = mock ? createMockRentalCommandRepository() : createHttpRentalCommandRepository()
  financeRepo = mock ? createMockFinanceRepository() : createHttpFinanceRepository()
  searchRepo = mock ? createMockSearchRepository() : createHttpSearchRepository()
}

export function useSettingsRepositories() {
  ensureRepositories()
  return { appInfo: appInfoRepo!, appConfig: appConfigRepo!, storage: storageRepo! }
}

export function useEntityRepository(): EntityRepository {
  ensureRepositories()
  return entityRepo!
}

export function useRentalCommands(): RentalCommandRepository {
  ensureRepositories()
  return rentalCommandRepo!
}

export function useFinanceRepository(): FinanceRepository {
  ensureRepositories()
  return financeRepo!
}

export function useSearchRepository(): SearchRepository {
  ensureRepositories()
  return searchRepo!
}
