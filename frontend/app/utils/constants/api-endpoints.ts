export const ApiEndpoints = {
  AUTH_LOGIN: '/api/v2/auth/login',
  AUTH_LOGOUT: '/api/v2/auth/logout',
  AUTH_ME: '/api/v2/auth/me',
  AUTH_REFRESH: '/api/v2/auth/refresh',
  AUTH_SETUP_STATUS: '/api/v2/auth/setup-status',
  AUTH_SETUP: '/api/v2/auth/setup',
  AUTH_FORGOT_PASSWORD: '/api/v2/auth/forgot-password',
  AUTH_RESET_VERIFY: '/api/v2/auth/forgot-password/verify',
  AUTH_RESET_RESEND: '/api/v2/auth/forgot-password/resend',
  AUTH_RESET_PASSWORD: '/api/v2/auth/forgot-password/reset',
  AUTH_RESET_HANDOFF: '/api/v2/auth/forgot-password/handoff',
  AUTH_CHANGE_PASSWORD: '/api/v2/auth/change-password',
  AUTH_PROFILE_AVATAR: '/api/v2/auth/profile/avatar',
  AUTH_TELEGRAM_LINK_CODE: '/api/v2/auth/telegram/link-code',

  MOTORCYCLES: '/api/v2/motorcycles',
  MOTORCYCLE: (id: string) => `/api/v2/motorcycles/${id}`,
  MOTORCYCLE_STATUS: (id: string) => `/api/v2/motorcycles/${id}/status`,

  CUSTOMERS: '/api/v2/customers',
  CUSTOMER: (id: string) => `/api/v2/customers/${id}`,

  RENTALS: '/api/v2/rentals',
  RENTAL: (id: string) => `/api/v2/rentals/${id}`,
  RENTAL_REPORTS: '/api/v2/rentals/reports',
  RENTAL_CLOSE: (id: string) => `/api/v2/rentals/${id}/close`,
  RENTAL_CANCEL: (id: string) => `/api/v2/rentals/${id}/cancel`,

  PAYMENTS: '/api/v2/payments',
  PAYMENT: (id: string) => `/api/v2/payments/${id}`,

  CHARGES: '/api/v2/charges',
  CHARGE: (id: string) => `/api/v2/charges/${id}`,

  EXPENSES: '/api/v2/expenses',
  EXPENSE: (id: string) => `/api/v2/expenses/${id}`,

  DASHBOARD: '/api/v2/dashboard',
  FINANCE_SUMMARY: '/api/v2/finance/summary',

  USERS: '/api/v2/users',
  USER: (id: string) => `/api/v2/users/${id}`,
  USER_UNLINK_TELEGRAM: (id: string) => `/api/v2/users/${id}/unlink-telegram`,

  ROLES: '/api/v2/roles',
  ROLE: (id: string) => `/api/v2/roles/${id}`,
  ROLE_OPTIONS: '/api/v2/roles/options',
  PERMISSIONS: '/api/v2/permissions',

  AUDIT_LOGS: '/api/v2/audit-logs',

  DOCUMENT_SEQUENCES: '/api/v2/document-sequences',
  DOCUMENT_SEQUENCE: (id: string) => `/api/v2/document-sequences/${id}`,

  EXPORTS: '/api/v2/exports',
  EXPORT: (id: string) => `/api/v2/exports/${id}`,
  EXPORT_DOWNLOAD: (id: string) => `/api/v2/exports/${id}/download`,
  TASK: (taskId: string) => `/api/v2/tasks/${taskId}`,

  APP_INFO: '/api/v2/settings/app-info',
  APP_INFO_RESET: '/api/v2/settings/app-info/reset',
  RESET_ALL_DATA: '/api/v2/settings/reset-data',
  APP_CONFIG: '/api/v2/settings/app-config',
  APP_CONFIG_TEST_EMAIL: '/api/v2/settings/app-config/email/test-connection',
  APP_CONFIG_SEND_TEST_EMAIL: '/api/v2/settings/app-config/email/send-test',
  APP_CONFIG_TEST_TELEGRAM: '/api/v2/settings/app-config/telegram/test-connection',
  APP_CONFIG_SEND_TEST_TELEGRAM: '/api/v2/settings/app-config/telegram/send-test',

  SEARCH: '/api/v2/search',
  SEARCH_ASK: '/api/v2/search/ask',
} as const

/**
 * Canonical collection → endpoint mapping used by entity repositories.
 * Frontend collection names (localStorage keys) map to `/api/v2` resource paths.
 */
export const CollectionEndpoints = {
  motorcycles: ApiEndpoints.MOTORCYCLES,
  rentalCustomers: ApiEndpoints.CUSTOMERS,
  rentals: ApiEndpoints.RENTALS,
  rentalReports: ApiEndpoints.RENTAL_REPORTS,
  rentalPayments: ApiEndpoints.PAYMENTS,
  rentalCharges: ApiEndpoints.CHARGES,
  rentalExpenses: ApiEndpoints.EXPENSES,
  users: ApiEndpoints.USERS,
  roles: ApiEndpoints.ROLES,
  documentSequences: ApiEndpoints.DOCUMENT_SEQUENCES,
  auditLogs: ApiEndpoints.AUDIT_LOGS,
} as const

export type ApiCollection = keyof typeof CollectionEndpoints

export function isApiCollection(collection: string): collection is ApiCollection {
  return collection in CollectionEndpoints
}
