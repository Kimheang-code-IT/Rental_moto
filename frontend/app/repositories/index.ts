import type { AppConfigRepository, AppInfoRepository } from '~/repositories/contracts/settings'
import type {
  EntityRepository,
  FinanceRepository,
  RentalCommandRepository,
  SearchRepository,
} from '~/repositories/contracts/entities'
import { createHttpAppConfigRepository, createHttpAppInfoRepository } from '~/repositories/http/settings'
import {
  createHttpEntityRepository,
  createHttpFinanceRepository,
  createHttpRentalCommandRepository,
  createHttpSearchRepository,
} from '~/repositories/http/entities'

let appInfoRepo: AppInfoRepository
let appConfigRepo: AppConfigRepository
let entityRepo: EntityRepository
let rentalCommandRepo: RentalCommandRepository
let financeRepo: FinanceRepository
let searchRepo: SearchRepository
let initialized = false

function ensureRepositories() {
  if (initialized) return
  initialized = true
  appInfoRepo = createHttpAppInfoRepository()
  appConfigRepo = createHttpAppConfigRepository()
  entityRepo = createHttpEntityRepository()
  rentalCommandRepo = createHttpRentalCommandRepository()
  financeRepo = createHttpFinanceRepository()
  searchRepo = createHttpSearchRepository()
}

export function useSettingsRepositories() {
  ensureRepositories()
  return { appInfo: appInfoRepo!, appConfig: appConfigRepo! }
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
