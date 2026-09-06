import type {
  AppConfig,
  AppInfo,
  ConnectionStatus,
} from '~/types/rental/settings'

export interface AppInfoRepository {
  get: () => Promise<AppInfo>
  update: (input: Partial<AppInfo>) => Promise<AppInfo>
  reset: () => Promise<AppInfo>
}

export interface ResetAllDataResult {
  message: string
  requiresReauth?: boolean
  requiresSetup?: boolean
  removedExports?: number
}

export interface AppConfigRepository {
  get: () => Promise<AppConfig>
  update: (input: Partial<AppConfig>) => Promise<AppConfig>
  resetAllData: () => Promise<ResetAllDataResult>
  testEmailConnection: () => Promise<{ status: ConnectionStatus, message: string }>
  sendTestEmail: (to: string) => Promise<{ status: ConnectionStatus, message: string }>
  testTelegramConnection: () => Promise<{ status: ConnectionStatus, message: string }>
  sendTestTelegramMessage: (destinationId?: string) => Promise<{ status: ConnectionStatus, message: string }>
}
