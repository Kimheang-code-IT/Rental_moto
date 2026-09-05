<script setup lang="ts">
import type { AppConfig } from '~/types/rental/settings'
import type { ConnectionStatusFieldValue } from '~/types/rental/common'
import { systemSettingsTabs } from '~/config/settings-schemas'
import { useSettingsRepositories } from '~/repositories'
import { useConfirm } from '~/composables/common/useConfirm'
import { useAppPageTitle } from '~/composables/layout/useAppPageTitle'
import { getByPath, setByPath } from '~/utils/object-path'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'

const { appConfig } = useSettingsRepositories()
const { t } = useI18n()
const toast = useToast()
const { confirm } = useConfirm()
const auth = useAuthStore()
const canEdit = computed(() => auth.canAccessPage('settings.app_config.edit'))
const canConfigure = computed(() => auth.canAccessPage('settings.app_config.configure'))
const appLocalization = useAppLocalization()

const pending = ref(true)
const saving = ref(false)
const testingEmail = ref(false)
const testingTelegram = ref(false)
const resettingData = ref(false)
const activeTab = ref('localization')
const model = ref<AppConfig | null>(null)

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback
}

async function load() {
  pending.value = true
  try {
    model.value = await appConfig.get()
  }
  catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('core.common.loadFailed')), color: 'error' })
  }
  finally {
    pending.value = false
  }
}

function fieldValue(key: string): unknown {
  if (!model.value) return undefined

  if (key === '__emailConnection') {
    const value: ConnectionStatusFieldValue = {
      status: model.value.email.connectionStatus,
      message: model.value.email.lastTestMessage,
      lastTestedAt: model.value.email.lastTestedAt,
    }
    return value
  }

  if (key === '__telegramConnection') {
    const value: ConnectionStatusFieldValue = {
      status: model.value.telegram.connectionStatus,
      message: model.value.telegram.lastTestMessage,
      lastTestedAt: model.value.telegram.lastTestedAt,
      details: model.value.telegram.botUsername
        ? [{ label: t('core.settings.botUsername'), value: model.value.telegram.botUsername }]
        : [],
    }
    return value
  }

  // Select options use string values; coerce number fields for USelect match.
  if (key === 'general.defaultPageSize' || key === 'system.paginationDefault') {
    const raw = getByPath(model.value, key)
    return raw == null || raw === '' ? undefined : String(raw)
  }

  if (key === 'localization.firstDayOfWeek') {
    const raw = getByPath(model.value, key)
    return raw == null || raw === '' ? undefined : String(raw)
  }

  if (key === 'telegram.deadlineReminderDuration') {
    const value = Number(model.value.telegram.deadlineReminderValue)
    const unit = model.value.telegram.deadlineReminderUnit
    return {
      value: Number.isFinite(value) && value >= 1 ? Math.min(Math.trunc(value), 10_080) : 1,
      unit: unit === 'minutes' || unit === 'days' ? unit : 'hours',
    }
  }

  return getByPath(model.value, key)
}

async function setFieldValue(key: string, value: unknown) {
  if (!model.value) return

  if (key === '__emailConnection' || key === '__telegramConnection') {
    return
  }

  if (key === 'system.maintenanceMode' || key === 'system.readOnlyMode') {
    if (value === true) {
      const ok = await confirm({
        kind: 'update',
        titleKey: 'core.settings.confirmModeTitle',
        descriptionKey: 'core.settings.confirmModeHelp',
        confirmColor: 'warning',
      })
      if (!ok) return
    }
    setByPath(model.value, key, value)
    return
  }

  if (key === 'general.defaultPageSize' || key === 'system.paginationDefault') {
    const n = Number(value)
    setByPath(model.value, key, Number.isFinite(n) ? n : 20)
    return
  }

  if (key === 'localization.firstDayOfWeek') {
    const day = Number(value)
    setByPath(model.value, key, day === 0 || day === 1 || day === 6 ? day : 1)
    return
  }

  if (key === 'telegram.deadlineReminderDuration') {
    const duration = value && typeof value === 'object' ? value as { value?: unknown, unit?: unknown } : {}
    const parsed = Number(duration.value)
    setByPath(model.value, 'telegram.deadlineReminderValue', Number.isFinite(parsed) ? Math.min(Math.max(Math.trunc(parsed), 1), 10_080) : 1)
    const unit = String(duration.unit || 'hours')
    setByPath(model.value, 'telegram.deadlineReminderUnit', unit === 'minutes' || unit === 'days' ? unit : 'hours')
    return
  }

  setByPath(model.value, key, value)
}

async function save() {
  if (!model.value) return
  saving.value = true
  try {
    model.value = await appConfig.update(model.value)
    appLocalization.apply(model.value.localization)
    usePreferencesStore().setCurrency(model.value.localization.currency)
    usePreferencesStore().syncLocaleWithConfig()
    toast.add({ title: t('core.common.saved'), color: 'success' })
  }
  catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('core.common.saveFailed')), color: 'error' })
  }
  finally {
    saving.value = false
  }
}

async function testEmail() {
  testingEmail.value = true
  try {
    if (model.value) await appConfig.update({ email: model.value.email })
    const result = await appConfig.testEmailConnection()
    model.value = await appConfig.get()
    toast.add({
      title: result.message,
      color: result.status === 'connected' ? 'success' : 'error',
    })
  }
  finally {
    testingEmail.value = false
  }
}

async function testTelegram() {
  testingTelegram.value = true
  try {
    if (model.value) await appConfig.update({ telegram: model.value.telegram })
    const result = await appConfig.sendTestTelegramMessage()
    model.value = await appConfig.get()
    toast.add({
      title: result.message,
      color: result.status === 'connected' ? 'success' : 'error',
    })
  }
  finally {
    testingTelegram.value = false
  }
}

async function resetAllData() {
  const ok = await confirm({
    kind: 'generic',
    titleKey: 'core.settings.resetDataConfirmTitle',
    descriptionKey: 'core.settings.resetDataConfirmHelp',
    confirmLabelKey: 'core.settings.resetDataAction',
    confirmColor: 'error',
  })
  if (!ok) return

  resettingData.value = true
  try {
    await appConfig.resetAllData()
    toast.add({ title: t('core.settings.resetDataSuccess'), color: 'success' })
    await auth.logout()
  }
  catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('core.settings.resetDataFailed')), color: 'error' })
  }
  finally {
    resettingData.value = false
  }
}

onMounted(() => void load())
useAppPageTitle(() => t('app.pages.settings'))
</script>

<template>
  <DocumentAppDocumentPage
    v-model:active-tab="activeTab"
    :tabs="systemSettingsTabs"
    :field-value="fieldValue"
    :set-field-value="setFieldValue"
    :pending="pending || !model"
    :saving="saving"
    :read-only="!canEdit"
    :can-save="canEdit"
    :show-list-nav="false"
    content-wide
    @save="save"
    @refresh="load"
  >
    <template #actions>
      <CommonAppConnectionTestButton
        v-if="activeTab === 'email' && canConfigure"
        :loading="testingEmail"
        @click="testEmail"
      />
      <CommonAppConnectionTestButton
        v-if="activeTab === 'telegram' && canConfigure"
        :loading="testingTelegram"
        @click="testTelegram"
      />
      <UButton
        v-if="canConfigure"
        color="error"
        variant="soft"
        size="sm"
        icon="i-lucide-database-zap"
        :loading="resettingData"
        :disabled="resettingData"
        :label="t('core.settings.resetDataAction')"
        @click="resetAllData"
      />
    </template>

    <template v-if="activeTab === 'security' && canConfigure" #after-form>
      <DocumentAppDocumentContentShell wide class="space-y-4 pb-6">
        <UAlert
          color="error"
          variant="subtle"
          :title="t('core.settings.resetDataTitle')"
          :description="t('core.settings.resetDataHelp')"
        />
      </DocumentAppDocumentContentShell>
    </template>
  </DocumentAppDocumentPage>
</template>
