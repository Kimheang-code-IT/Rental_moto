export type ConnectionStatus =
  | 'not_tested'
  | 'testing'
  | 'connected'
  | 'failed'
  | 'disabled'

export type EncryptionType = 'none' | 'ssl' | 'tls' | 'starttls'

export type TelegramConnectionMode = 'bot_api' | 'webhook'

export type TelegramDestinationType = 'chat' | 'channel' | 'group'

export type NotificationChannel = 'in_app' | 'email' | 'telegram'

export type NotificationEvent =
  | 'rental_created'
  | 'rental_overdue'
  | 'rental_completed'
  | 'payment_recorded'
  | 'charge_recorded'
  | 'expense_recorded'
  | 'password_reset_requested'
  | 'record_created'
  | 'record_assigned'
  | 'stage_changed'
  | 'deadline_approaching'
  | 'record_overdue'
  | 'meeting_created'
  | 'file_uploaded'

export type AppFontSize = 'sm' | 'md' | 'lg' | 'xl'

export interface AppBranding {
  mainLogoUrl?: string
  sidebarLogoUrl?: string
  faviconUrl?: string
  loginBackgroundUrl?: string
  /** System primary color (hex, e.g. #e8472a). */
  primaryColor: string
  secondaryColor: string
  /** @deprecated Per-user preference — use preferences store / user menu. */
  fontSize?: AppFontSize
}

export interface AppFooterInfo {
  copyrightText: string
  privacyPolicyUrl?: string
  termsUrl?: string
}

export interface AppInfo {
  applicationName: string
  shortName: string
  businessName: string
  description?: string
  supportEmail?: string
  supportPhone?: string
  website?: string
  address?: string
  branding: AppBranding
  footer: AppFooterInfo
  updatedAt: string
}

export interface EmailConfig {
  enabled: boolean
  smtpHost: string
  smtpPort: number
  username: string
  /** Masked in UI; never log plaintext. */
  password: string
  encryption: EncryptionType
  fromName: string
  fromEmail: string
  replyToEmail?: string
  timeoutSeconds: number
  connectionStatus: ConnectionStatus
  lastTestedAt?: string
  lastTestMessage?: string
}

export interface TelegramUserAccess {
  id: string
  userId?: number
  userName: string
  chatId: string
  chatbotEnabled: boolean
  groupEnabled: boolean
}

export interface TelegramDestination {
  id: string
  name: string
  type: TelegramDestinationType
  chatId: string
  recordTypeId?: string
  recordTypeName?: string
  enabledEvents: NotificationEvent[]
  status: ConnectionStatus
  enabled: boolean
  isInteractiveGroup?: boolean
}

export interface TelegramModulePolicy {
  finance: boolean
  motorcycles: boolean
  customers: boolean
  rentals: boolean
}

export interface TelegramSensitiveFields {
  customerName: boolean
  customerPhone: boolean
  financialTotals: boolean
  rentalBalances: boolean
}

export interface TelegramConfig {
  enabled: boolean
  botDisplayName: string
  botToken: string
  botUsername?: string
  connectionMode: TelegramConnectionMode
  defaultDestinationId?: string
  chatId: string
  interactiveGroupEnabled: boolean
  interactiveGroupId: string
  allowedModules: TelegramModulePolicy
  sensitiveFields: TelegramSensitiveFields
  messageLanguage: 'en' | 'km'
  includeRecordLink: boolean
  includeBusinessName: boolean
  includeAssignedOfficer: boolean
  notifyNewRental: boolean
  notifyOverdueRental: boolean
  notifyRentalCompleted: boolean
  notifyPayment: boolean
  notifyCharge: boolean
  notifyExpense: boolean
  deadlineReminderEnabled: boolean
  deadlineReminderValue: number
  deadlineReminderUnit: 'minutes' | 'hours' | 'days'
  dailySummaryEnabled: boolean
  dailySummaryTime: string
  monthlySummaryEnabled: boolean
  inlineKeyboardEnabled: boolean
  showTransactionsButton: boolean
  showMotorcycleStatusButton: boolean
  showFinanceSummaryButton: boolean
  defaultReportPeriod: 'today' | '3_days' | '7_days' | '1_month'
  passwordResetEnabled: boolean
  connectionStatus: ConnectionStatus
  lastTestedAt?: string
  lastTestMessage?: string
  destinations: TelegramDestination[]
  userAccess: TelegramUserAccess[]
  messageTemplate: string
}

export interface NotificationRule {
  id: string
  event: NotificationEvent
  channels: NotificationChannel[]
  enabled: boolean
}

export interface AppConfigGeneral {
  defaultLandingPage: string
  defaultPageSize: number
  defaultRecordView: 'table' | 'kanban'
  enableComments: boolean
  enableSharing: boolean
  enableExport: boolean
  maxUploadSizeMb: number
}

export interface AppConfigLocalization {
  defaultLanguage: 'en' | 'km'
  availableLanguages: Array<'en' | 'km'>
  timezone: string
  dateFormat: string
  timeFormat: string
  firstDayOfWeek: 0 | 1 | 6
  numberFormat: string
  currency: string
  locale: string
}

export interface AppConfigNotifications {
  inAppEnabled: boolean
  emailEnabled: boolean
  telegramEnabled: boolean
  deliveryRetries: number
  quietHoursEnabled: boolean
  quietHoursStart?: string
  quietHoursEnd?: string
  language: 'en' | 'km'
  rules: NotificationRule[]
}

export interface AppConfigSecurity {
  sessionTimeoutMinutes: number
  maxLoginAttempts: number
  accountLockMinutes: number
  passwordExpiryDays: number
  requirePasswordChange: boolean
  allowedUploadExtensions: string[]
  auditRetentionDays: number
  passwordResetChannel: 'telegram'
  passwordResetCodeExpiryMinutes: number
  jwtAccessTokenMinutes: number
  jwtRefreshTokenDays: number
  /** UI disclaimer: not enforced without backend. */
  frontendOnly: true
}

export interface AppConfigSystem {
  maintenanceMode: boolean
  readOnlyMode: boolean
  paginationDefault: number
  configurationVersion: string
  environment: 'development' | 'staging' | 'production'
  cacheStatus: 'healthy' | 'degraded' | 'unknown'
  backgroundJobStatus: 'idle' | 'running' | 'failed' | 'unknown'
}

export interface AppConfig {
  general: AppConfigGeneral
  localization: AppConfigLocalization
  email: EmailConfig
  telegram: TelegramConfig
  notifications: AppConfigNotifications
  security: AppConfigSecurity
  system: AppConfigSystem
  updatedAt: string
}

export const NOTIFICATION_EVENTS: NotificationEvent[] = [
  'rental_created',
  'rental_overdue',
  'rental_completed',
  'payment_recorded',
  'charge_recorded',
  'expense_recorded',
  'password_reset_requested',
  'record_created',
  'record_assigned',
  'stage_changed',
  'deadline_approaching',
  'record_overdue',
  'meeting_created',
  'file_uploaded',
]

export const TELEGRAM_NOTIFICATION_EVENTS: NotificationEvent[] = NOTIFICATION_EVENTS.filter(
  event => event !== 'password_reset_requested',
)

export const TELEGRAM_TEMPLATE_VARIABLES = [
  '{{record_number}}',
  '{{record_title}}',
  '{{record_type}}',
  '{{status}}',
  '{{stage}}',
  '{{business_name}}',
  '{{assigned_officer}}',
  '{{due_at}}',
  '{{created_by}}',
  '{{record_url}}',
] as const

export const DEFAULT_TELEGRAM_TEMPLATE = [
  '[{{record_type}}] {{record_number}}',
  '{{record_title}}',
  'Status: {{status}} · Stage: {{stage}}',
  'Business: {{business_name}} · Assignee: {{assigned_officer}}',
  '{{record_url}}',
].join('\n')
