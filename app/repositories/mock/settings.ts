import { createId, mockLatency, nowIso } from '~/mocks/query'
import type {
  AppConfigRepository,
  AppInfoRepository,
  StorageRepository,
} from '~/repositories/contracts/settings'
import type {
  AppConfig,
  AppInfo,
  ConnectionStatus,
  CreateStorageProviderInput,
  StorageProvider,
  UpdateStorageProviderInput,
} from '~/types/docetra/settings'
import type { NotificationChannel } from '~/types/docetra/settings'
import { DEFAULT_TELEGRAM_TEMPLATE, NOTIFICATION_EVENTS } from '~/types/docetra/settings'

const INFO_KEY = 'docetra:settings:app-info'
const CONFIG_KEY = 'docetra:settings:app-config'
const STORAGE_KEY = 'docetra:settings:storage'

function readJson<T>(key: string, fallback: T): T {
  if (!import.meta.client) return structuredClone(fallback)
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return structuredClone(fallback)
    return JSON.parse(raw) as T
  }
  catch {
    return structuredClone(fallback)
  }
}

function writeJson<T>(key: string, value: T) {
  if (!import.meta.client) return
  localStorage.setItem(key, JSON.stringify(value))
}

function seedAppInfo(): AppInfo {
  return {
    applicationName: 'HollyWing Motor',
    shortName: 'HWM',
    organizationName: 'HollyWing Motor',
    description: 'Motorcycle rental management system',
    supportEmail: 'support@lcs.com.kh',
    supportPhone: '+855 23 000 000',
    website: 'https://docetra.local',
    address: 'Phnom Penh, Cambodia',
    branding: {
      primaryColor: '#e8472a',
      secondaryColor: '#1b2b5e',
    },
    footer: {
      copyrightText: `© ${new Date().getFullYear()} Docetra`,
      privacyPolicyUrl: '/privacy',
      termsUrl: '/terms',
    },
    updatedAt: nowIso(),
  }
}

function seedAppConfig(): AppConfig {
  return {
    general: {
      defaultLandingPage: '/',
      defaultPageSize: 20,
      defaultRecordView: 'table',
      enableComments: true,
      enableSharing: true,
      enableExport: true,
      maxUploadSizeMb: 50,
    },
    localization: {
      defaultLanguage: 'en',
      availableLanguages: ['en', 'km'],
      timezone: 'Asia/Phnom_Penh',
      dateFormat: 'YYYY-MM-DD',
      timeFormat: 'HH:mm',
      firstDayOfWeek: 1,
      numberFormat: '1,234.56',
      currency: 'USD',
      locale: 'en-US',
    },
    email: {
      enabled: false,
      smtpHost: '',
      smtpPort: 587,
      username: '',
      password: '',
      encryption: 'tls',
      fromName: 'Docetra',
      fromEmail: 'noreply@docetra.local',
      replyToEmail: '',
      timeoutSeconds: 30,
      connectionStatus: 'not_tested',
    },
    telegram: {
      enabled: false,
      botDisplayName: '',
      botToken: '',
      botUsername: '',
      connectionMode: 'bot_api',
      messageLanguage: 'en',
      includeRecordLink: true,
      includeOrganization: true,
      includeAssignedOfficer: true,
      connectionStatus: 'not_tested',
      destinations: [],
      messageTemplate: DEFAULT_TELEGRAM_TEMPLATE,
    },
    notifications: {
      inAppEnabled: true,
      emailEnabled: false,
      telegramEnabled: false,
      deliveryRetries: 3,
      quietHoursEnabled: false,
      language: 'en',
      rules: NOTIFICATION_EVENTS.map((event, i) => ({
        id: `nr_${i}`,
        event,
        channels: ['in_app'] as NotificationChannel[],
        enabled: true,
      })),
    },
    security: {
      sessionTimeoutMinutes: 60,
      maxLoginAttempts: 5,
      accountLockMinutes: 15,
      passwordExpiryDays: 90,
      requirePasswordChange: false,
      allowedUploadExtensions: ['pdf', 'docx', 'xlsx', 'png', 'jpg'],
      auditRetentionDays: 365,
      frontendOnly: true,
    },
    system: {
      maintenanceMode: false,
      readOnlyMode: false,
      paginationDefault: 20,
      configurationVersion: '0.1.0',
      environment: 'development',
      cacheStatus: 'healthy',
      backgroundJobStatus: 'idle',
    },
    updatedAt: nowIso(),
  }
}

/** Merge older localStorage payloads onto the current AppConfig shape. */
function normalizeAppConfig(raw: AppConfig & { display?: unknown }): AppConfig {
  const seed = seedAppConfig()
  const rest = { ...raw }
  delete rest.display
  return {
    ...seed,
    ...rest,
    general: { ...seed.general, ...raw.general },
    localization: { ...seed.localization, ...raw.localization },
    email: { ...seed.email, ...raw.email },
    telegram: { ...seed.telegram, ...raw.telegram },
    notifications: { ...seed.notifications, ...raw.notifications },
    security: { ...seed.security, ...raw.security },
    system: { ...seed.system, ...raw.system },
    updatedAt: raw.updatedAt || seed.updatedAt,
  }
}

function seedStorage(): StorageProvider[] {
  const now = nowIso()
  return [
    {
      id: 'st_local',
      name: 'Local Storage',
      type: 'local',
      active: true,
      isDefault: true,
      maxFileSizeMb: 50,
      allowedFileTypes: ['pdf', 'docx', 'png', 'jpg'],
      accessMode: 'private',
      uploadPathPattern: '/uploads/{yyyy}/{mm}/{filename}',
      connectionStatus: 'connected',
      lastTestedAt: now,
      updatedAt: now,
    },
    {
      id: 'st_r2',
      name: 'Cloudflare R2',
      type: 'cloudflare_r2',
      active: false,
      isDefault: false,
      maxFileSizeMb: 100,
      allowedFileTypes: ['pdf', 'docx', 'xlsx', 'png', 'jpg', 'zip'],
      accessMode: 'private',
      uploadPathPattern: 'docetra/{yyyy}/{mm}/{filename}',
      endpoint: '',
      region: 'auto',
      bucket: '',
      accessKey: '',
      secretKey: '',
      pathStyle: false,
      connectionStatus: 'not_tested',
      updatedAt: now,
    },
    {
      id: 'st_s3',
      name: 'Amazon S3',
      type: 'amazon_s3',
      active: false,
      isDefault: false,
      maxFileSizeMb: 100,
      allowedFileTypes: ['pdf', 'docx', 'xlsx', 'png', 'jpg'],
      accessMode: 'private',
      uploadPathPattern: 'docetra/{yyyy}/{mm}/{filename}',
      region: 'ap-southeast-1',
      bucket: '',
      accessKey: '',
      secretKey: '',
      pathStyle: false,
      connectionStatus: 'not_tested',
      updatedAt: now,
    },
    {
      id: 'st_minio',
      name: 'MinIO',
      type: 'minio',
      active: false,
      isDefault: false,
      maxFileSizeMb: 100,
      allowedFileTypes: ['pdf', 'docx', 'png', 'jpg'],
      accessMode: 'private',
      uploadPathPattern: 'docetra/{yyyy}/{mm}/{filename}',
      endpoint: 'http://localhost:9000',
      region: 'us-east-1',
      bucket: 'docetra',
      accessKey: '',
      secretKey: '',
      pathStyle: true,
      connectionStatus: 'not_tested',
      updatedAt: now,
    },
    {
      id: 'st_gdrive',
      name: 'Google Drive',
      type: 'google_drive',
      active: false,
      isDefault: false,
      maxFileSizeMb: 50,
      allowedFileTypes: ['pdf', 'docx', 'xlsx', 'png', 'jpg'],
      accessMode: 'private',
      uploadPathPattern: 'Docetra/{yyyy}/{mm}',
      folderId: '',
      credentialStatus: 'not_tested',
      syncStatus: 'not_tested',
      syncSchedule: '0 */6 * * *',
      connectionStatus: 'not_tested',
      updatedAt: now,
    },
  ]
}

async function simulateConnection(forceFail = false): Promise<{ status: ConnectionStatus, message: string }> {
  await mockLatency(null, 350)
  if (forceFail) {
    return { status: 'failed', message: 'Mock connection failed (simulated).' }
  }
  return { status: 'connected', message: 'Mock connection succeeded (simulated — no real backend).' }
}

export function createMockAppInfoRepository(): AppInfoRepository {
  let value = readJson(INFO_KEY, seedAppInfo())
  const defaults = seedAppInfo()

  return {
    async get() {
      return mockLatency(structuredClone(value))
    },
    async update(input) {
      value = {
        ...value,
        ...input,
        branding: { ...value.branding, ...input.branding },
        footer: { ...value.footer, ...input.footer },
        updatedAt: nowIso(),
      }
      writeJson(INFO_KEY, value)
      return mockLatency(structuredClone(value))
    },
    async reset() {
      value = structuredClone(defaults)
      value.updatedAt = nowIso()
      writeJson(INFO_KEY, value)
      return mockLatency(structuredClone(value))
    },
  }
}

export function createMockAppConfigRepository(): AppConfigRepository {
  let value = normalizeAppConfig(readJson(CONFIG_KEY, seedAppConfig()))

  return {
    async get() {
      value = normalizeAppConfig(value)
      return mockLatency(structuredClone(value))
    },
    async update(input) {
      value = normalizeAppConfig({
        ...value,
        ...input,
        general: { ...value.general, ...input.general },
        localization: { ...value.localization, ...input.localization },
        email: { ...value.email, ...input.email },
        telegram: { ...value.telegram, ...input.telegram },
        notifications: { ...value.notifications, ...input.notifications },
        security: { ...value.security, ...input.security },
        system: { ...value.system, ...input.system },
        updatedAt: nowIso(),
      })
      writeJson(CONFIG_KEY, value)
      return mockLatency(structuredClone(value))
    },
    async testEmailConnection() {
      value.email.connectionStatus = 'testing'
      writeJson(CONFIG_KEY, value)
      const result = await simulateConnection(!value.email.smtpHost)
      value.email.connectionStatus = result.status
      value.email.lastTestedAt = nowIso()
      value.email.lastTestMessage = result.message
      writeJson(CONFIG_KEY, value)
      return result
    },
    async sendTestEmail(to) {
      if (!to) return { status: 'failed', message: 'Recipient email is required (mock).' }
      return simulateConnection(!value.email.enabled)
    },
    async testTelegramConnection() {
      value.telegram.connectionStatus = 'testing'
      writeJson(CONFIG_KEY, value)
      const result = await simulateConnection(!value.telegram.botToken)
      value.telegram.connectionStatus = result.status
      value.telegram.lastTestedAt = nowIso()
      value.telegram.lastTestMessage = result.message
      if (result.status === 'connected' && !value.telegram.botUsername) {
        value.telegram.botUsername = '@docetra_mock_bot'
      }
      writeJson(CONFIG_KEY, value)
      return result
    },
    async sendTestTelegramMessage(destinationId) {
      if (!value.telegram.enabled) {
        return { status: 'disabled', message: 'Telegram is disabled (mock).' }
      }
      if (destinationId) {
        const dest = value.telegram.destinations.find(d => d.id === destinationId)
        if (!dest) return { status: 'failed', message: 'Destination not found (mock).' }
      }
      return simulateConnection(!value.telegram.botToken)
    },
  }
}

export function createMockStorageRepository(): StorageRepository {
  let items = readJson(STORAGE_KEY, seedStorage())
  const persist = () => writeJson(STORAGE_KEY, items)

  return {
    async list() {
      return mockLatency(structuredClone(items))
    },
    async getById(id) {
      const found = items.find(i => i.id === id)
      if (!found) throw new Error('Storage provider not found')
      return mockLatency(structuredClone(found))
    },
    async create(input: CreateStorageProviderInput) {
      const row: StorageProvider = {
        ...input,
        id: createId('st'),
        isDefault: false,
        connectionStatus: 'not_tested',
        updatedAt: nowIso(),
      }
      items = [row, ...items]
      persist()
      return mockLatency(structuredClone(row))
    },
    async update(id, input: UpdateStorageProviderInput) {
      const idx = items.findIndex(i => i.id === id)
      if (idx < 0) throw new Error('Storage provider not found')
      const next = { ...items[idx]!, ...input, updatedAt: nowIso() }
      items[idx] = next
      persist()
      return mockLatency(structuredClone(next))
    },
    async setDefault(id) {
      items = items.map(item => ({
        ...item,
        isDefault: item.id === id,
        updatedAt: nowIso(),
      }))
      persist()
      const found = items.find(i => i.id === id)
      if (!found) throw new Error('Storage provider not found')
      return mockLatency(structuredClone(found))
    },
    async setActive(id, active) {
      return this.update(id, { active })
    },
    async testConnection(id) {
      const idx = items.findIndex(i => i.id === id)
      if (idx < 0) throw new Error('Storage provider not found')
      items[idx] = { ...items[idx]!, connectionStatus: 'testing' }
      persist()
      const provider = items[idx]!
      const missingS3 = ['cloudflare_r2', 'amazon_s3', 'minio'].includes(provider.type)
        && (!provider.bucket || !provider.accessKey)
      const missingDrive = provider.type === 'google_drive' && !provider.folderId
      const result = await simulateConnection(missingS3 || missingDrive)
      items[idx] = {
        ...items[idx]!,
        connectionStatus: result.status,
        lastTestedAt: nowIso(),
        lastTestMessage: result.message,
        updatedAt: nowIso(),
      }
      persist()
      return result
    },
    async remove(id) {
      const target = items.find(i => i.id === id)
      if (target?.isDefault) throw new Error('Cannot delete the default storage provider')
      items = items.filter(i => i.id !== id)
      persist()
      await mockLatency(undefined)
    },
  }
}
