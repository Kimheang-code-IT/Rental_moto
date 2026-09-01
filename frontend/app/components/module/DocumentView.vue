<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { useConfirm } from '~/composables/common/useConfirm'
import { usePageSeo } from '~/composables/usePageSeo'
import {
  emptyModuleRecord,
  statusColor,
  useModuleLabel,
  useModuleRoute,
} from '~/composables/module/useModule'
import type { AppRecord } from '~/config/admin-seed'
import { useModuleRecordChrome } from '~/composables/module/useModuleRecordChrome'
import { normalizePermissionRows, permissionRowsToFlatKeys } from '~/utils/role/permissions'
import type { AppRolePermissionRow } from '~/types/rental/entities'
import { documentSequencePreview, documentSequenceTypeLabel } from '~/utils/document-sequences'
import {
  moduleDocumentLineActionKey,
  moduleDocumentTabs,
  RELATED_FIELD_KEY,
} from '~/utils/module/document-tabs'

const { module, isCreate, recordId, route } = useModuleRoute()
const store = useAppDataStore()
const auth = useAuthStore()
const { t } = useI18n()
const toast = useToast()
const { moduleTitle, moduleSingular, fieldLabel } = useModuleLabel()
const { setBreadcrumbs, setBadges, clear } = useAppHeader()
const { confirm } = useConfirm()

const saving = ref(false)
const activeTab = ref('general')
const model = ref<AppRecord>({ id: '' } as AppRecord)
const originalModel = ref<AppRecord | null>(null)
const notFound = ref(false)

const {
  currentUser,
  listTo,
  canNavigatePrevious,
  canNavigateNext,
  navigatePrevious,
  navigateNext,
  attachments,
  tags,
  metaOwner,
  metaAssignee,
  setChromeField,
} = useModuleRecordChrome({ module, isCreate, recordId, model })

function applyRoleMatrix() {
  if (module.value?.collection !== 'roles') return
  const rows = normalizePermissionRows(model.value.permissionRows as AppRolePermissionRow[] | undefined)
  model.value = {
    ...model.value,
    permissionRows: rows,
    permissionCount: permissionRowsToFlatKeys(rows).length,
  }
}

function load() {
  if (!module.value) return
  if (isCreate.value) {
    model.value = emptyModuleRecord(module.value) as AppRecord
    if (module.value.collection === 'documentSequences') {
      model.value.nextNumberPreview = documentSequencePreview(model.value)
    }
    originalModel.value = null
    notFound.value = false
    const query = route.query
    for (const [key, value] of Object.entries(query)) {
      if (key === 'status') continue
      if (typeof value === 'string' && value) model.value[key] = value
    }
    applyRoleMatrix()
    return
  }
  const found = store.get(module.value.collection, recordId.value)
  if (store.isHttpMode && !found) {
    void store.fetchOne(module.value.collection, recordId.value).then((record) => {
      if (record) {
        model.value = { ...record } as AppRecord
        originalModel.value = { ...record } as AppRecord
        notFound.value = false
        applyRoleMatrix()
      }
      else {
        notFound.value = true
      }
    })
    return
  }
  notFound.value = !found
  model.value = found ? { ...found } as AppRecord : emptyModuleRecord(module.value) as AppRecord
  originalModel.value = found ? { ...found } as AppRecord : null
  applyRoleMatrix()
}

watch(
  [() => module.value?.path, recordId, isCreate, () => Boolean(module.value && store.get(module.value.collection, recordId.value))],
  load,
  { immediate: true },
)

const title = computed(() => {
  if (!module.value) return ''
  if (isCreate.value) return t('app.ui.newEntity', { entity: moduleSingular(module.value) })
  const value = model.value[module.value.titleField]
  return module.value.collection === 'documentSequences'
    ? documentSequenceTypeLabel(value || moduleSingular(module.value))
    : String(value || moduleSingular(module.value))
})

watch([title, () => module.value, () => model.value.status], () => {
  if (!module.value) return
  setBreadcrumbs([
    { label: moduleTitle(module.value), to: module.value.path },
    { label: title.value },
  ])
  setBadges(model.value.status ? [{ label: String(model.value.status), color: statusColor(String(model.value.status)) }] : [])
}, { immediate: true })

onBeforeUnmount(clear)
usePageSeo({ title: () => title.value })

const related = computed(() => module.value && !isCreate.value ? store.related(module.value, model.value) : [])
const readOnly = computed(() => {
  if (!module.value) return true
  if (module.value.readOnly) return true
  if (!auth.user?.pageAccess?.includes('ALL_PAGES')) {
    if (module.value.group === 'master' || module.value.group === 'configuration') return true
  }
  return false
})
const canMutateRecord = computed(() => Boolean(module.value) && !readOnly.value && !isCreate.value && Boolean(model.value.id))
const deactivationOnly = computed(() => module.value?.group === 'master' || module.value?.collection === 'documentSequences')

const tabs = computed(() => {
  if (!module.value) return []
  return moduleDocumentTabs(module.value, {
    isCreate: isCreate.value,
    includeRelated: related.value.length > 0,
    readOnlyKeys: module.value.collection === 'documentSequences' && !isCreate.value
      ? ['documentType', 'year']
      : [],
  })
})

watch(tabs, (value) => {
  if (!value.some(tab => tab.id === activeTab.value)) activeTab.value = value[0]?.id || 'general'
}, { immediate: true })

provide(moduleDocumentLineActionKey, () => {})

const moreItems = computed<DropdownMenuItem[][]>(() => {
  if (module.value?.collection === 'documentSequences') {
    if (!canMutateRecord.value) return []
    const active = String(model.value.status || '').toUpperCase() === 'ACTIVE'
    return [[{
      label: t(active ? 'core.rowActions.deactivate' : 'core.rowActions.activate'),
      icon: active ? 'i-lucide-circle-off' : 'i-lucide-circle-check',
      color: active ? 'warning' as const : 'success' as const,
      onSelect: () => { void setDocumentSequenceStatus(active ? 'INACTIVE' : 'ACTIVE') },
    }]]
  }

  if (canMutateRecord.value) {
    return [[{
      label: t(deactivationOnly.value ? 'app.ui.deactivate' : 'app.ui.delete'),
      icon: deactivationOnly.value ? 'i-lucide-circle-off' : 'i-lucide-trash-2',
      color: deactivationOnly.value ? 'warning' as const : 'error' as const,
      onSelect: () => { void deleteRecord() },
    }]]
  }
  return []
})

function setRolePermissions(rows: AppRolePermissionRow[]) {
  const normalized = normalizePermissionRows(rows)
  model.value = {
    ...model.value,
    permissionRows: normalized,
    permissionCount: permissionRowsToFlatKeys(normalized).length,
  }
}

function setField(key: string, value: unknown) {
  model.value = { ...model.value, [key]: value } as AppRecord
  recalculate()
}

function fieldValue(key: string) {
  if (key === RELATED_FIELD_KEY) return related.value
  if (module.value?.tables?.some(table => table.key === key)) {
    return Array.isArray(model.value[key]) ? model.value[key] : []
  }
  return model.value[key]
}

function setFieldValue(key: string, value: unknown) {
  if (key === RELATED_FIELD_KEY) return
  if (key === 'permissionRows') {
    setRolePermissions(value as AppRolePermissionRow[])
    return
  }
  if (key === 'tags' || key === 'assignee' || key === 'attachments' || key === 'favorite') {
    setChromeField(key, value)
    return
  }
  if (module.value?.tables?.some(table => table.key === key) && Array.isArray(value)) {
    model.value = { ...model.value, [key]: value }
    return
  }
  setField(key, value)
}

function recalculate() {
  if (!module.value) return
  if (module.value.collection === 'documentSequences') {
    model.value = {
      ...model.value,
      prefix: String(model.value.prefix || '').trimStart(),
      nextNumberPreview: documentSequencePreview(model.value),
    }
  }
}

async function save() {
  if (!module.value || readOnly.value) return
  saving.value = true
  try {
    recalculate()
    const payload = { ...model.value }
    if (module.value.collection === 'documentSequences') {
      payload.prefix = String(payload.prefix || '').trim()
      const sequenceYear = Number(payload.year)
      const lastValue = Number(payload.lastValue)
      const paddingLength = Number(payload.paddingLength)
      payload.year = sequenceYear
      payload.lastValue = lastValue
      payload.paddingLength = paddingLength
      payload.status = String(payload.status || 'ACTIVE').toUpperCase()
      payload.nextNumberPreview = documentSequencePreview(payload)

      if (!Number.isInteger(sequenceYear) || sequenceYear < 1000 || sequenceYear > 9999) {
        toast.add({ title: 'Year must be a positive 4-digit year.', color: 'error' })
        return
      }
      if (!Number.isInteger(lastValue) || lastValue < 0) {
        toast.add({ title: 'Last Value must be a whole number greater than or equal to 0.', color: 'error' })
        return
      }
      if (!Number.isInteger(paddingLength) || paddingLength <= 0) {
        toast.add({ title: 'Padding Length must be a whole number greater than 0.', color: 'error' })
        return
      }
      if (!['ACTIVE', 'INACTIVE'].includes(String(payload.status))) {
        toast.add({ title: 'Status must be ACTIVE or INACTIVE.', color: 'error' })
        return
      }
      const duplicate = store.list('documentSequences').find(row =>
        String(row.id) !== String(payload.id || '')
        && String(row.documentType) === String(payload.documentType)
        && Number(row.year) === Number(payload.year),
      )
      if (duplicate) {
        toast.add({
          title: 'A document sequence already exists for this document type and year.',
          description: `${documentSequenceTypeLabel(payload.documentType)} / ${payload.year}`,
          color: 'error',
        })
        return
      }
      if (!isCreate.value && originalModel.value && Number(payload.lastValue) !== Number(originalModel.value.lastValue)) {
        const ok = await confirm({
          kind: 'generic',
          title: 'Change the last sequence value?',
          description: 'Changing the last value can create duplicate or skipped document numbers. Continue only after verifying the numbering history.',
          confirmLabel: 'Change Last Value',
          confirmColor: 'warning',
        })
        if (!ok) return
      }
    }
    const missing = module.value.fields.filter(field => field.required && !field.computed && !String(payload[field.key] ?? '').trim())
    if (missing.length) {
      toast.add({ title: t('app.ui.missingRequired'), description: missing.map(fieldLabel).join(', '), color: 'error' })
      return
    }
    if (isCreate.value || !payload.id) {
      payload.createdAt ||= new Date().toISOString()
      payload.createdBy ||= String(currentUser.value?.name || 'Current User')
      payload.status ||= 'Active'
      payload.currency ||= 'USD'
    }
    let saved: AppRecord
    if (store.isHttpMode) {
      saved = isCreate.value || !payload.id
        ? await store.createRemote(module.value.collection, payload)
        : await store.updateRemote(module.value.collection, String(payload.id), payload)
    }
    else {
      saved = isCreate.value || !payload.id
        ? store.create(module.value.collection, payload, module.value.collection.slice(0, 3))
        : store.save(module.value.collection, payload as AppRecord)
    }
    store.addAudit('Saved', module.value.title, String(saved[module.value.titleField] || saved.id))
    toast.add({ title: t('app.ui.save'), color: 'success' })
    if (isCreate.value) await navigateTo(`${module.value.path}/${saved.id}`)
    else {
      model.value = saved
      originalModel.value = { ...saved }
    }
  }
  finally {
    saving.value = false
  }
}

async function setDocumentSequenceStatus(status: 'ACTIVE' | 'INACTIVE') {
  if (module.value?.collection !== 'documentSequences' || !canMutateRecord.value) return
  saving.value = true
  try {
    model.value = await store.updateRemote(module.value.collection, String(model.value.id), { status }) as AppRecord
    originalModel.value = { ...model.value }
    store.addAudit(status === 'ACTIVE' ? 'Activated' : 'Deactivated', module.value.title, String(model.value.documentType || model.value.id))
    toast.add({ title: t(status === 'ACTIVE' ? 'core.common.activated' : 'core.common.deactivated'), color: 'success' })
  }
  finally {
    saving.value = false
  }
}

async function deleteRecord() {
  if (!module.value || !canMutateRecord.value) return
  if (deactivationOnly.value) {
    saving.value = true
    try {
      const status = module.value.collection === 'documentSequences' ? 'INACTIVE' : 'Inactive'
      model.value = await store.updateRemote(module.value.collection, String(model.value.id), { status }) as AppRecord
      store.addAudit('Deactivated', module.value.title, String(model.value[module.value.titleField] || model.value.id))
      toast.add({ title: t('app.ui.recordDeactivated'), color: 'success' })
    }
    finally {
      saving.value = false
    }
    return
  }
  const ok = await confirm({ kind: 'delete', count: 1 })
  if (!ok) return
  await store.deleteRemote(module.value.collection, [String(model.value.id)])
  store.addAudit('Deleted', module.value.title, String(model.value[module.value.titleField] || model.value.id))
  toast.add({ title: t('core.actions.deletedItems', { n: 1 }), color: 'success' })
  await navigateTo(module.value.path)
}
</script>

<template>
  <template v-if="module && !notFound">
    <DocumentAppDocumentPage
      :tabs="tabs"
      :active-tab="activeTab"
      :field-value="fieldValue"
      :set-field-value="setFieldValue"
      :saving="saving"
      :read-only="readOnly"
      :can-save="!readOnly"
      :save-label="t('core.common.save')"
      :confirm-save="false"
      :show-cancel="false"
      :show-tabs="tabs.length > 1"
      show-list-nav
      content-wide
      :can-navigate-previous="canNavigatePrevious"
      :can-navigate-next="canNavigateNext"
      :list-to="listTo"
      :is-create="isCreate"
      :attachments="attachments"
      :current-user="currentUser"
      :meta-title="title"
      :meta-subtitle="moduleSingular(module)"
      :meta-icon="module.icon"
      :meta-status="String(model.status || '')"
      :meta-owner="metaOwner"
      :meta-assignee="metaAssignee"
      :meta-tags="tags"
      :meta-created-at="String(model.createdAt || '')"
      :meta-updated-at="String(model.updatedAt || '')"
      :more-items="moreItems"
      :can-export="false"
      @update:active-tab="activeTab = $event"
      @update:attachments="setChromeField('attachments', $event)"
      @save="save()"
      @refresh="load"
      @navigate-previous="navigatePrevious"
      @navigate-next="navigateNext"
    />
  </template>
  <div v-else class="p-6 text-sm text-muted">{{ t('core.document.notFound') || 'Record not found.' }}</div>
</template>
