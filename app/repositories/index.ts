import type { AppConfigRepository, AppInfoRepository, StorageRepository } from '~/repositories/contracts/settings'
import { createHttpAppConfigRepository, createHttpAppInfoRepository } from '~/repositories/http/settings'
import { createHttpStorageRepository } from '~/repositories/http/settings-storage'
import { createMockAppConfigRepository, createMockAppInfoRepository, createMockStorageRepository } from '~/repositories/mock/settings'

let mode: 'mock' | 'http' | null = null
let appInfoRepo: AppInfoRepository
let appConfigRepo: AppConfigRepository
let storageRepo: StorageRepository

function ensureRepositories() {
  const nextMode = useRuntimeConfig().public.useMockData !== false ? 'mock' : 'http'
  if (mode === nextMode) return
  mode = nextMode
  const mock = nextMode === 'mock'
  appInfoRepo = mock ? createMockAppInfoRepository() : createHttpAppInfoRepository()
  appConfigRepo = mock ? createMockAppConfigRepository() : createHttpAppConfigRepository()
  storageRepo = mock ? createMockStorageRepository() : createHttpStorageRepository()
}

export function useSettingsRepositories() {
  ensureRepositories()
  return { appInfo: appInfoRepo!, appConfig: appConfigRepo!, storage: storageRepo! }
}
