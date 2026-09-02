import type { DocumentTabSchema } from '~/types/rental/common'
import {
  AWS_REGION_OPTIONS,
  CURRENCY_OPTIONS,
  DATE_FORMAT_OPTIONS,
  LANDING_PAGE_OPTIONS,
  FIRST_DAY_OF_WEEK_OPTIONS,
  LOCALE_OPTIONS,
  NUMBER_FORMAT_OPTIONS,
  PAGE_SIZE_OPTIONS,
  SYNC_SCHEDULE_OPTIONS,
  TIME_FORMAT_OPTIONS,
  TIMEZONE_OPTIONS,
} from '~/utils/constants/select-options'

/** App Info — flat form (no tabs UI when single tab). */
export const appInfoTabs: DocumentTabSchema[] = [
  {
    id: 'info',
    labelKey: 'core.pages.appInfo',
    sections: [
      {
        id: 'info',
        fields: [
          { key: 'applicationName', labelKey: 'core.settings.applicationName', type: 'text', required: true, colSpan: 2 },
          { key: 'description', labelKey: 'core.fields.description', type: 'textarea', colSpan: 2, rows: 3 },
          { key: 'supportEmail', labelKey: 'core.settings.supportEmail', type: 'text' },
          { key: 'supportPhone', labelKey: 'core.settings.supportPhone', type: 'text' },
          { key: 'website', labelKey: 'core.settings.website', type: 'url' },
          { key: 'address', labelKey: 'core.settings.address', type: 'text' },
          { key: 'footer.copyrightText', labelKey: 'core.settings.copyright', type: 'text', colSpan: 2 },
          {
            key: 'branding.primaryColor',
            labelKey: 'core.settings.primaryColor',
            type: 'color',
          },
          { key: 'branding.mainLogoUrl', labelKey: 'core.settings.logo', type: 'image', colSpan: 2 },
        ],
      },
    ],
  },
]

/** App Config tabs. */
export const appConfigTabs: DocumentTabSchema[] = [
  {
    id: 'general',
    labelKey: 'core.settings.tabs.general',
    sections: [
      {
        id: 'general',
        titleKey: 'core.settings.tabs.general',
        fields: [
          {
            key: 'general.defaultLandingPage',
            labelKey: 'core.settings.defaultLandingPage',
            type: 'select',
            options: LANDING_PAGE_OPTIONS,
          },
          {
            key: 'general.defaultPageSize',
            labelKey: 'core.settings.defaultPageSize',
            type: 'select',
            options: PAGE_SIZE_OPTIONS,
          },
          {
            key: 'general.defaultRecordView',
            labelKey: 'core.settings.defaultRecordView',
            type: 'select',
            options: [
              { label: 'Table', value: 'table' },
              { label: 'Kanban', value: 'kanban' },
            ],
          },
          { key: 'general.maxUploadSizeMb', labelKey: 'core.config.maxFileSizeMb', type: 'number' },
          { key: 'general.enableSharing', labelKey: 'core.config.feature.sharing', type: 'boolean' },
          { key: 'general.enableExport', labelKey: 'core.config.feature.export', type: 'boolean' },
        ],
      },
    ],
  },
  {
    id: 'localization',
    labelKey: 'core.settings.tabs.localization',
    sections: [
      {
        id: 'localization',
        titleKey: 'core.settings.tabs.localization',
        fields: [
          {
            key: 'localization.defaultLanguage',
            labelKey: 'core.settings.defaultLanguage',
            type: 'select',
            options: [
              { label: 'English', value: 'en' },
              { label: 'Khmer', value: 'km' },
            ],
          },
          {
            key: 'localization.timezone',
            labelKey: 'core.settings.timezone',
            type: 'select',
            options: TIMEZONE_OPTIONS,
          },
          {
            key: 'localization.dateFormat',
            labelKey: 'core.settings.dateFormat',
            type: 'select',
            options: DATE_FORMAT_OPTIONS,
          },
          {
            key: 'localization.timeFormat',
            labelKey: 'core.settings.timeFormat',
            type: 'select',
            options: TIME_FORMAT_OPTIONS,
          },
          {
            key: 'localization.firstDayOfWeek',
            labelKey: 'core.settings.firstDayOfWeek',
            type: 'select',
            options: FIRST_DAY_OF_WEEK_OPTIONS,
          },
          {
            key: 'localization.locale',
            labelKey: 'core.settings.locale',
            type: 'select',
            options: LOCALE_OPTIONS,
          },
          {
            key: 'localization.numberFormat',
            labelKey: 'core.settings.numberFormat',
            type: 'select',
            options: NUMBER_FORMAT_OPTIONS,
          },
          {
            key: 'localization.currency',
            labelKey: 'core.settings.currency',
            type: 'select',
            options: CURRENCY_OPTIONS,
          },
        ],
      },
    ],
  },
  {
    id: 'email',
    labelKey: 'core.settings.tabs.email',
    sections: [
      {
        id: 'email',
        titleKey: 'core.settings.tabs.email',
        fields: [
          { key: 'email.enabled', labelKey: 'core.settings.enableEmail', type: 'boolean' },
          { key: 'email.smtpHost', labelKey: 'core.settings.smtpHost', type: 'text' },
          { key: 'email.smtpPort', labelKey: 'core.settings.smtpPort', type: 'number' },
          { key: 'email.username', labelKey: 'core.settings.username', type: 'text' },
          { key: 'email.password', labelKey: 'core.settings.password', type: 'secret' },
          {
            key: 'email.encryption',
            labelKey: 'core.settings.encryption',
            type: 'select',
            options: [
              { label: 'None', value: 'none' },
              { label: 'SSL', value: 'ssl' },
              { label: 'TLS', value: 'tls' },
              { label: 'STARTTLS', value: 'starttls' },
            ],
          },
          { key: 'email.fromName', labelKey: 'core.settings.fromName', type: 'text' },
          { key: 'email.fromEmail', labelKey: 'core.settings.fromEmail', type: 'text' },
          { key: 'email.replyToEmail', labelKey: 'core.settings.replyTo', type: 'text' },
          { key: '__emailConnection', labelKey: 'core.connection.title', type: 'connection-status', colSpan: 2 },
        ],
      },
    ],
  },
  {
    id: 'telegram',
    labelKey: 'core.settings.tabs.telegram',
    sections: [
      {
        id: 'telegram',
        titleKey: 'core.settings.tabs.telegram',
        fields: [
          { key: 'telegram.enabled', labelKey: 'core.settings.enableTelegram', type: 'boolean' },
          { key: 'telegram.botToken', labelKey: 'core.settings.botToken', type: 'secret' },
          { key: 'telegram.chatId', labelKey: 'rental.settings.groupId', type: 'text' },
          { key: 'telegram.deadlineReminderEnabled', labelKey: 'rental.settings.deadlineReminderEnabled', type: 'boolean' },
          { key: 'telegram.deadlineReminderValue', labelKey: 'rental.settings.deadlineReminderValue', type: 'number', helpKey: 'rental.settings.deadlineReminderHelp' },
          {
            key: 'telegram.deadlineReminderUnit',
            labelKey: 'rental.settings.deadlineReminderUnit',
            type: 'select',
            options: [
              { label: 'Minutes', value: 'minutes' },
              { label: 'Hours', value: 'hours' },
              { label: 'Days', value: 'days' },
            ],
          },
          { key: 'telegram.dailySummaryEnabled', labelKey: 'rental.settings.dailySummaryEnabled', type: 'boolean' },
          { key: 'telegram.monthlySummaryEnabled', labelKey: 'rental.settings.monthlySummaryEnabled', type: 'boolean' },
          { key: 'telegram.userAccess', labelKey: 'rental.settings.telegramUserAccess', type: 'telegram-user-access', colSpan: 2, helpKey: 'rental.settings.telegramUserAccessHelp' },
        ],
      },
    ],
  },
  {
    id: 'notifications',
    labelKey: 'core.settings.tabs.notifications',
    sections: [
      {
        id: 'notifications',
        titleKey: 'core.settings.tabs.notifications',
        fields: [
          { key: 'notifications.inAppEnabled', labelKey: 'core.settings.inApp', type: 'boolean' },
          { key: 'notifications.emailEnabled', labelKey: 'core.settings.emailChannel', type: 'boolean' },
          { key: 'notifications.telegramEnabled', labelKey: 'core.settings.telegramChannel', type: 'boolean' },
          { key: 'notifications.deliveryRetries', labelKey: 'core.settings.deliveryRetries', type: 'number' },
          {
            key: 'notifications.rules',
            labelKey: 'core.settings.eventRules',
            type: 'notification-rules',
            colSpan: 2,
          },
        ],
      },
    ],
  },
  {
    id: 'security',
    labelKey: 'core.settings.tabs.security',
    sections: [
      {
        id: 'security',
        titleKey: 'core.settings.tabs.security',
        fields: [
          { key: 'security.maxLoginAttempts', labelKey: 'core.settings.maxLoginAttempts', type: 'number' },
          { key: 'security.accountLockMinutes', labelKey: 'core.settings.accountLockMinutes', type: 'number' },
          { key: 'security.passwordExpiryDays', labelKey: 'core.settings.passwordExpiryDays', type: 'number' },
          { key: 'security.auditRetentionDays', labelKey: 'core.settings.auditRetentionDays', type: 'number' },
          { key: 'security.requirePasswordChange', labelKey: 'core.settings.requirePasswordChange', type: 'boolean' },
          {
            key: 'security.passwordResetChannel',
            labelKey: 'rental.settings.passwordResetChannel',
            type: 'select',
            options: [{ label: 'Telegram', value: 'telegram' }],
          },
          { key: 'security.passwordResetCodeExpiryMinutes', labelKey: 'rental.settings.passwordResetCodeExpiryMinutes', type: 'number' },
          { key: 'security.jwtRefreshTokenDays', labelKey: 'rental.settings.jwtRefreshTokenDays', type: 'number' },
          {
            key: 'security.allowedUploadExtensions',
            labelKey: 'core.config.allowedExtensions',
            type: 'csv-list',
            colSpan: 2,
          },
        ],
      },
    ],
  },
  {
    id: 'system',
    labelKey: 'core.settings.tabs.system',
    sections: [
      {
        id: 'system',
        titleKey: 'core.settings.tabs.system',
        fields: [
          { key: 'system.maintenanceMode', labelKey: 'core.settings.maintenanceMode', type: 'boolean' },
          { key: 'system.readOnlyMode', labelKey: 'core.settings.readOnlyMode', type: 'boolean' },
          {
            key: 'system.paginationDefault',
            labelKey: 'core.settings.paginationDefault',
            type: 'select',
            options: PAGE_SIZE_OPTIONS,
          },
          { key: 'system.configurationVersion', labelKey: 'core.settings.configurationVersion', type: 'text', readOnly: true },
          { key: 'system.environment', labelKey: 'core.settings.environment', type: 'text', readOnly: true },
          { key: 'system.cacheStatus', labelKey: 'core.settings.cacheStatus', type: 'text', readOnly: true },
          { key: 'system.backgroundJobStatus', labelKey: 'core.settings.jobStatus', type: 'text', readOnly: true },
        ],
      },
    ],
  },
]

const SYSTEM_SETTINGS_TAB_IDS = new Set(['localization', 'telegram', 'security'])
const SETTINGS_FIELD_HELP: Record<string, string> = {
  'localization.timezone': 'core.fieldHelp.timezone',
  'localization.dateFormat': 'core.fieldHelp.dateFormat',
  'localization.timeFormat': 'core.fieldHelp.timeFormat',
  'localization.firstDayOfWeek': 'core.fieldHelp.firstDayOfWeek',
  'localization.locale': 'core.fieldHelp.locale',
  'localization.numberFormat': 'core.fieldHelp.numberFormat',
  'email.enabled': 'core.fieldHelp.enableEmail',
  'email.replyToEmail': 'core.fieldHelp.replyTo',
  'telegram.enabled': 'core.fieldHelp.enableTelegram',
}

/** Administration system settings — Localization, Email, Telegram, Security only. */
export const systemSettingsTabs: DocumentTabSchema[] = appConfigTabs
  .filter(tab => SYSTEM_SETTINGS_TAB_IDS.has(tab.id))
  .map(tab => ({
    ...tab,
    sections: tab.sections.map(section => ({
      ...section,
      fields: section.fields.map(field => ({
        ...field,
        helpKey: field.helpKey || SETTINGS_FIELD_HELP[field.key],
      })),
    })),
  }))

const storageCommonFields = [
  { key: 'name', labelKey: 'core.fields.name', type: 'text' as const, required: true },
  { key: 'active', labelKey: 'core.status.active', type: 'boolean' as const },
  {
    key: 'accessMode',
    labelKey: 'core.settings.accessMode',
    type: 'select' as const,
    options: [
      { label: 'Private', value: 'private' },
      { label: 'Public', value: 'public' },
    ],
  },
  { key: 'maxFileSizeMb', labelKey: 'core.config.maxFileSizeMb', type: 'number' as const },
  { key: 'allowedFileTypes', labelKey: 'core.config.allowedExtensions', type: 'csv-list' as const, colSpan: 2 as const },
  { key: 'uploadPathPattern', labelKey: 'core.settings.uploadPathPattern', type: 'text' as const, colSpan: 2 as const },
]

const storageConnectionField = {
  key: '__storageConnection',
  labelKey: 'core.connection.title',
  type: 'connection-status' as const,
  colSpan: 2 as const,
}

/** Storage settings — S3 and Google Drive only. */
export const storageSettingsTabs: DocumentTabSchema[] = [
  {
    id: 'amazon_s3',
    labelKey: 'core.settings.storageTabs.amazonS3',
    sections: [
      {
        id: 's3-connection',
        titleKey: 'core.settings.connectionSettings',
        fields: [
          {
            key: 'region',
            labelKey: 'core.settings.region',
            type: 'select',
            required: true,
            options: AWS_REGION_OPTIONS,
          },
          { key: 'bucket', labelKey: 'core.settings.bucket', type: 'text', required: true },
          { key: 'endpoint', labelKey: 'core.settings.endpoint', type: 'text', colSpan: 2 },
          { key: 'publicUrl', labelKey: 'core.settings.publicUrl', type: 'url', colSpan: 2 },
          { key: 'accessKey', labelKey: 'core.settings.accessKey', type: 'text', required: true },
          { key: 'secretKey', labelKey: 'core.settings.secretKey', type: 'secret', required: true },
        ],
      },
      {
        id: 's3-options',
        titleKey: 'core.settings.tabs.general',
        fields: [...storageCommonFields],
      },
      {
        id: 's3-status',
        titleKey: 'core.connection.title',
        fields: [storageConnectionField],
      },
    ],
  },
  {
    id: 'google_drive',
    labelKey: 'core.settings.storageTabs.googleDrive',
    sections: [
      {
        id: 'drive-connection',
        titleKey: 'core.settings.connectionSettings',
        fields: [
          { key: 'clientId', labelKey: 'core.settings.clientId', type: 'text', required: true, colSpan: 2 },
          { key: 'clientSecret', labelKey: 'core.settings.clientSecret', type: 'secret', required: true, colSpan: 2 },
          { key: 'folderId', labelKey: 'core.settings.folderId', type: 'text', required: true },
          {
            key: 'syncSchedule',
            labelKey: 'core.settings.syncSchedule',
            type: 'select',
            options: SYNC_SCHEDULE_OPTIONS,
          },
        ],
      },
      {
        id: 'drive-options',
        titleKey: 'core.settings.tabs.general',
        fields: [...storageCommonFields],
      },
      {
        id: 'drive-status',
        titleKey: 'core.connection.title',
        fields: [storageConnectionField],
      },
    ],
  },
]

