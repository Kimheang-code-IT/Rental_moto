import type { AppConfigRepository, AppInfoRepository, ResetAllDataResult } from '~/repositories/contracts/settings'
import type { ApiResponse } from '~/types/rental/common'
import type { AppConfig, AppInfo, ConnectionStatus } from '~/types/rental/settings'
import { ApiEndpoints } from '~/utils/constants/api-endpoints'
import { unwrapApiData } from './response'

type ConnectionResult = { status: ConnectionStatus; message: string }

export function createHttpAppInfoRepository(): AppInfoRepository {
  const api = useApi()
  return {
    get: async () => unwrapApiData(await api.get<AppInfo | ApiResponse<AppInfo>>(ApiEndpoints.APP_INFO)),
    update: async input => unwrapApiData(await api.patch<AppInfo | ApiResponse<AppInfo>>(ApiEndpoints.APP_INFO, input)),
    reset: async () => unwrapApiData(await api.post<AppInfo | ApiResponse<AppInfo>>(ApiEndpoints.APP_INFO_RESET, {})),
  }
}

export function createHttpAppConfigRepository(): AppConfigRepository {
  const api = useApi()
  const postResult = async (endpoint: string, body: Record<string, unknown> = {}) =>
    unwrapApiData(await api.post<ConnectionResult | ApiResponse<ConnectionResult>>(endpoint, body))

  return {
    get: async () => unwrapApiData(await api.get<AppConfig | ApiResponse<AppConfig>>(ApiEndpoints.APP_CONFIG)),
    update: async input => unwrapApiData(await api.patch<AppConfig | ApiResponse<AppConfig>>(ApiEndpoints.APP_CONFIG, input)),
    resetAllData: async () => unwrapApiData(
      await api.post<ResetAllDataResult | ApiResponse<ResetAllDataResult>>(ApiEndpoints.RESET_ALL_DATA, {}),
    ),
    testEmailConnection: () => postResult(ApiEndpoints.APP_CONFIG_TEST_EMAIL),
    sendTestEmail: to => postResult(ApiEndpoints.APP_CONFIG_SEND_TEST_EMAIL, { to }),
    testTelegramConnection: () => postResult(ApiEndpoints.APP_CONFIG_TEST_TELEGRAM),
    sendTestTelegramMessage: destinationId => postResult(
      ApiEndpoints.APP_CONFIG_SEND_TEST_TELEGRAM,
      destinationId ? { destinationId } : {},
    ),
  }
}
