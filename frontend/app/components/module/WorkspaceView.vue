<script setup lang="ts">
import type { DropdownMenuItem, TableColumn, TableRow } from '@nuxt/ui'
import type { PaginationState } from '@tanstack/vue-table'
import { h } from 'vue'
import { UBadge, ULink } from '#components'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { useConfirm } from '~/composables/common/useConfirm'
import { usePageSeo } from '~/composables/usePageSeo'
import {
  formatModuleCell,
  moduleStatusBadge,
  useModuleLabel,
  useModuleRoute,
} from '~/composables/module/useModule'
import type { AppRecord } from '~/config/admin-seed'
import { appModules, type ModuleSelectOption } from '~/config/modules'
import { isMoneyKey, isNumericKey } from '~/utils/module/field-keys'
import { limitFilterSelects, parseFilterQuery } from '~/utils/filter/values'
import { isFilterValueActive } from '~/utils/filter/select-ui'
import { listTableRowMetaColumn, listTableSelectColumn } from '~/utils/table/list-columns'
import { listTablePageSummary, listTableSelectedIds } from '~/utils/table/list-table'
import { documentSequenceTypeLabel, isDocumentSequenceType } from '~/utils/document-sequences'
import { normalizeAuditLog, resolveAuditEntityPath } from '~/utils/module/audit-logs'
import { latestRentalPaymentMethods } from '~/utils/rental/payments'
import { useRentalCommands } from '~/repositories/index'
import { PAYMENT_METHODS, RENTAL_CHARGE_TYPES } from '~/config/rental-options'
import { toIsoZonedOrNow } from '~/utils/api/datetime'

const { module, route } = useModuleRoute()
const store = useAppDataStore()
const auth = useAuthStore()
const { t } = useI18n()
const { fieldLabel, moduleTitle, moduleSingular } = useModuleLabel()
const { setTitle, setBreadcrumbs, clear } = useAppHeader()
const { confirm } = useConfirm()
const toast = useToast()

const q = ref('')
const pagination = ref<PaginationState>({ pageIndex: 0, pageSize: 20 })
const filters = reactive<Record<string, string[]>>({})
const rowSelection = ref<Record<string, boolean>>({})
const busyId = ref('')
const preferences = usePreferencesStore()
const rentalCloseOpen = ref(false)
const rentalModalRow = ref<Record<string, unknown> | null>(null)
const rentalInvoiceRow = ref<Record<string, unknown> | null>(null)
const motorcycleMaintenanceOpen = ref(false)
const motorcycleMaintenanceRow = ref<Record<string, unknown> | null>(null)
const rentalPaymentRow = ref<Record<string, unknown> | null>(null)
const rentalChargeRow = ref<Record<string, unknown> | null>(null)
const financeModalBusy = ref(false)
const financePaymentMethod = ref<(typeof PAYMENT_METHODS)[number]>(PAYMENT_METHODS[0])
const financePaymentAmount = ref<number | undefined>()
const financePaymentReference = ref('')
const financeChargeType = ref<(typeof RENTAL_CHARGE_TYPES)[number]>(RENTAL_CHARGE_TYPES[0])
const financeChargeDescription = ref('')
const financeChargeAmount = ref<number | undefined>()
const dateFrom = ref('')
const dateTo = ref('')

const current = computed(() => module.value)
const isHttpMode = computed(() => store.isHttpMode)
const pending = computed(() => Boolean(current.value && store.isLoading(current.value.collection)))
const isTableOnly = computed(() => Boolean(current.value?.tableOnly))
const canManageModule = computed(() => {
  if (!current.value) return false
  if (auth.user?.pageAccess?.includes('ALL_PAGES')) return true
  if (current.value.group === 'master' || current.value.group === 'configuration') return false
  return true
})
const canCreate = computed(() => Boolean(current.value?.canCreate && !current.value.readOnly && canManageModule.value))
const canMutate = computed(() => Boolean(current.value) && !current.value?.readOnly && canManageModule.value)
const deactivationOnly = computed(() => current.value?.group === 'master' || current.value?.collection === 'documentSequences')
const dateField = computed(() => {
  const fields = current.value?.fields || []
  return fields.find(field => field.type === 'date' || field.type === 'datetime' || field.key === 'date' || /date$/i.test(field.key))?.key
    || current.value?.columns.find(column => /date/i.test(column.key))?.key
})

const result = computed(() => {
  if (!current.value) return { rows: [], total: 0, all: [] }
  const queried = store.query(current.value, {
    q: q.value,
    filters,
    paginate: false,
    dateField: dateField.value,
    dateFrom: dateFrom.value,
    dateTo: dateTo.value,
  })
  if (current.value?.collection === 'rentals') {
    const paymentMethods = latestRentalPaymentMethods(store.list('rentalPayments'))
    const all = queried.all
      .filter(row => ['Active', 'Overdue'].includes(String(row.status)))
      .map((row) => {
        const ms = new Date(String(row.dueDate || '')).getTime() - new Date(String(row.startDate || '')).getTime()
        const days = Number.isFinite(ms) && ms > 0 ? Math.ceil(ms / 86400000) : 0
        return {
          ...row,
          durationDays: days,
          paymentMethod: paymentMethods.get(String(row.id || '')) || row.paymentMethod || '—',
        }
      })
    return { rows: all, total: all.length, all }
  }
  return queried
})
const selectedIds = computed(() => listTableSelectedIds(rowSelection.value))

const hasActiveFilters = computed(() => Boolean(
  Object.values(filters).some(value => isFilterValueActive(value))
  || isFilterValueActive(dateFrom.value)
  || isFilterValueActive(dateTo.value),
))

const visibleFilters = computed(() => limitFilterSelects(
  current.value?.filters || [],
  Boolean(dateField.value),
  filter => filter.key === 'status' || filter.key === 'workflowStatus',
))

watch(current, (value) => {
  if (!value) return
  setTitle(moduleTitle(value))
  setBreadcrumbs([{ label: moduleTitle(value) }])
  rowSelection.value = {}
  for (const key of Object.keys(filters)) Reflect.deleteProperty(filters, key)
  for (const filter of value.filters || []) {
    filters[filter.key] = parseFilterQuery(route.query[filter.key])
  }
}, { immediate: true })

onBeforeUnmount(clear)

usePageSeo({
  title: () => current.value ? moduleTitle(current.value) : t('app.pages.dashboard'),
})

watch([q, filters, dateFrom, dateTo], () => {
  rowSelection.value = {}
  pagination.value = { ...pagination.value, pageIndex: 0 }
}, { deep: true })

// HTTP mode: reload the server-backed collection when transport-level filters
// change or the module switches. Client-side filters keep filtering the
// fetched rows locally.
watch(
  [current, q, dateFrom, dateTo],
  () => {
    if (!isHttpMode.value || !current.value) return
    const collection = current.value.collection
    void store.fetchList(collection, {
      q: q.value || undefined,
      startDate: dateFrom.value || undefined,
      endDate: dateTo.value || undefined,
    })
    // Dependent collections used for derived columns and row guards.
    if (collection === 'rentals') void store.fetchList('rentalPayments')
  },
  { immediate: true },
)

function recordPath(id: unknown) {
  if (!current.value) return '/'
  return `${current.value.path}/${id}`
}

function cellText(row: Record<string, unknown>, key: string) {
  const source = current.value?.collection === 'auditLogs' ? normalizeAuditLog(row as AppRecord) : row
  return formatModuleCell(source[key], key, isMoneyKey(key) ? String(source.currency || preferences.currency) : undefined)
}

function auditEntityLinkFor(row: Record<string, unknown>) {
  if (current.value?.collection !== 'auditLogs') return ''
  return resolveAuditEntityPath(
    normalizeAuditLog(row as AppRecord),
    appModules,
    collection => store.list(collection),
    permission => auth.canAccessPage(permission),
  )
}

const pageSummary = computed(() =>
  listTablePageSummary(t, result.value.total, pagination.value),
)

function rowMenuItems(row: Record<string, unknown>): DropdownMenuItem[][] {
  const items: DropdownMenuItem[] = [
    {
      label: t('app.ui.open'),
      icon: 'i-lucide-eye',
      onSelect: () => openRow(row),
    },
  ]
  const collection = current.value?.collection
  if (collection === 'documentSequences') {
    items[0] = {
      label: t('core.rowActions.detail'),
      icon: 'i-lucide-eye',
      onSelect: () => openRow(row),
    }
    if (canMutate.value) {
      items.push({
        label: 'Edit',
        icon: 'i-lucide-pencil',
        onSelect: () => openRow(row),
      })
      const active = String(row.status || '').toUpperCase() === 'ACTIVE'
      items.push({
        label: t(active ? 'core.rowActions.deactivate' : 'core.rowActions.activate'),
        icon: active ? 'i-lucide-circle-off' : 'i-lucide-circle-check',
        color: active ? 'warning' : 'success',
        onSelect: () => setDocumentSequenceStatus(row, active ? 'INACTIVE' : 'ACTIVE'),
      })
    }
    return [items]
  }
  if (collection === 'rentals') {
    if (auth.canAccessPage('rental.rentals.return')) {
      items.push({ label: t('rental.ui.closeRental'), icon: 'i-lucide-circle-check', color: 'success', onSelect: () => { rentalModalRow.value = row; rentalCloseOpen.value = true } })
    }
    if (auth.canAccessPage('rental.finance.create')) {
      items.push({ label: t('rental.ui.recordPayment', 'Record payment'), icon: 'i-lucide-hand-coins', onSelect: () => { openRentalPayment(row) } })
      items.push({ label: t('rental.ui.addCharge', 'Add charge'), icon: 'i-lucide-receipt-text', onSelect: () => { openRentalCharge(row) } })
    }
    if (auth.canAccessPage('rental.rentals.edit')) {
      const status = String(row.status || '')
      if (['Active', 'Overdue'].includes(status)) {
        items.push({ label: t('rental.ui.cancelRental', 'Cancel rental'), icon: 'i-lucide-ban', color: 'error', onSelect: () => { void cancelRental(row) } })
      }
    }
    if (auth.canAccessPage('rental.rentals.print')) {
      items.push({ label: t('rental.ui.printInvoice'), icon: 'i-lucide-printer', onSelect: () => { rentalInvoiceRow.value = row } })
    }
  }
  else if (collection === 'motorcycles') {
    const status = String(row.status || '')
    const canEditMoto = auth.canAccessPage('rental.motorcycles.edit')
    if (canEditMoto && status === 'Available') {
      items.push({
        label: t('rental.ui.setMaintenance', 'Maintenance'),
        icon: 'i-lucide-wrench',
        color: 'warning',
        onSelect: () => openMotorcycleMaintenance(row),
      })
    }
    if (canEditMoto && status === 'Maintenance') {
      items.push({
        label: t('rental.ui.setAvailable', 'Available'),
        icon: 'i-lucide-circle-check',
        color: 'success',
        onSelect: () => setMotorcycleStatus(row, 'Available'),
      })
    }
    if (canMutate.value && status !== 'Progressing') {
      items.push({
        label: t('app.ui.delete'),
        icon: 'i-lucide-trash-2',
        color: 'error',
        onSelect: () => { void deleteIds([String(row.id)]) },
      })
    }
    return [items]
  }
  else if (collection === 'rentalCustomers') {
    const status = String(row.status || 'Active')
    const canEditCustomer = auth.canAccessPage('rental.customers.edit')
    if (canEditCustomer && status === 'Active') {
      items.push({
        label: t('rental.ui.setInactive', 'Inactive'),
        icon: 'i-lucide-circle-off',
        color: 'warning',
        onSelect: () => setCustomerStatus(row, 'Inactive'),
      })
    }
    if (canEditCustomer && status === 'Inactive') {
      items.push({
        label: t('rental.ui.setActive', 'Active'),
        icon: 'i-lucide-circle-check',
        color: 'success',
        onSelect: () => setCustomerStatus(row, 'Active'),
      })
    }
    if (canMutate.value && status === 'Inactive') {
      items.push({
        label: t('app.ui.delete'),
        icon: 'i-lucide-trash-2',
        color: 'error',
        onSelect: () => { void deleteIds([String(row.id)]) },
      })
    }
    return [items]
  }
  if (canMutate.value && collection !== 'rentals' && collection !== 'motorcycles' && collection !== 'rentalCustomers') {
    items.push({
      label: deactivationOnly.value ? t('app.ui.deactivate') : t('app.ui.delete'),
      icon: deactivationOnly.value ? 'i-lucide-circle-off' : 'i-lucide-trash-2',
      color: deactivationOnly.value ? 'warning' : 'error',
      onSelect: () => { void (deactivationOnly.value ? deactivateIds([String(row.id)]) : deleteIds([String(row.id)])) },
    })
  }
  return [items]
}

const columns = computed<TableColumn<Record<string, unknown>>[]>(() => {
  if (!current.value) return []
  const titleKey = current.value.titleField
  const dataColumns = current.value.columns.map((column, index) => ({
    accessorKey: column.key,
    enableSorting: false,
    header: fieldLabel(column),
    meta: isNumericKey(column.key) || isMoneyKey(column.key) || column.key === 'tasksProgress' || column.key === 'containersCount'
      ? { class: { td: 'text-end tabular-nums whitespace-nowrap', th: 'text-end' } }
      : undefined,
    cell: ({ row }: { row: { original: Record<string, unknown> } }) => {
      const text = cellText(row.original, column.key)
      const isTitle = column.key === titleKey || (index === 0 && !current.value!.columns.some(item => item.key === titleKey))
      const isRecordLink = isTitle
        || (current.value!.collection === 'rentalCustomers' && column.key === 'code')
      const entityTo = column.key === 'entity' ? auditEntityLinkFor(row.original) : ''
      if (entityTo) {
        return h(ULink, {
          to: entityTo,
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      if (isRecordLink && !isTableOnly.value) {
        return h(ULink, {
          to: recordPath(row.original.id),
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => text)
      }
      if (column.key === 'status' || column.key.toLowerCase().includes('status')) {
        return moduleStatusBadge(
          row.original[column.key] || row.original.workflowStatus || row.original.status,
          column.key,
          text,
        )
      }
      if (column.key === 'direction' || column.key === 'stage') {
        return h(UBadge, { color: 'info', variant: 'subtle', size: 'sm' }, () => text)
      }
      if (column.key === 'customer') {
        return h('span', { class: 'block max-w-48 truncate text-default', title: text }, text)
      }
      return h('span', { class: 'text-sm text-default' }, text)
    },
  }))

  return [
    ...(!isTableOnly.value ? [listTableSelectColumn<Record<string, unknown>>(t)] : []),
    ...dataColumns,
    ...(!isTableOnly.value
      ? [listTableRowMetaColumn<Record<string, unknown>>({
          summary: pageSummary.value,
          items: rowMenuItems,
          loadingId: busyId.value,
        })]
      : []),
  ]
})

function openCreate() {
  if (!current.value) return
  navigateTo(`${current.value.path}/new`)
}

function openRow(row: Record<string, unknown>) {
  if (!current.value || !row.id) return
  navigateTo(recordPath(row.id))
}

function openMotorcycleMaintenance(row: Record<string, unknown>) {
  motorcycleMaintenanceRow.value = row
  motorcycleMaintenanceOpen.value = true
}

async function setMotorcycleStatus(row: Record<string, unknown>, status: 'Available' | 'Maintenance') {
  if (!current.value || current.value.collection !== 'motorcycles') return
  const id = String(row.id || '')
  busyId.value = id
  try {
    await store.setStatusRemote('motorcycles', id, status)
    store.addAudit(`Motorcycle set to ${status}`, 'Motorcycles', String(row.code || row.plate || id))
    toast.add({
      title: status === 'Available'
        ? t('rental.ui.motorcycleAvailable', 'Motorcycle set to Available')
        : t('rental.ui.motorcycleMaintenance', 'Motorcycle set to Maintenance'),
      color: 'success',
    })
  }
  finally {
    busyId.value = ''
  }
}

function customerHasOpenRentals(customerId: string) {
  return store.list('rentals').some(row =>
    String(row.customerId || '') === customerId
    && ['Active', 'Overdue'].includes(String(row.status || '')),
  )
}

async function setCustomerStatus(row: Record<string, unknown>, status: 'Active' | 'Inactive') {
  if (!current.value || current.value.collection !== 'rentalCustomers') return
  const id = String(row.id || '')
  if (status === 'Inactive' && customerHasOpenRentals(id)) {
    toast.add({
      title: t('rental.ui.cannotInactivateCustomerOpenRentals', 'Cannot set Inactive while the customer has open rentals'),
      color: 'warning',
    })
    return
  }
  busyId.value = id
  try {
    await store.updateRemote('rentalCustomers', id, { status })
    store.addAudit(`Customer set to ${status}`, 'Customers', String(row.code || row.fullName || id))
    toast.add({
      title: status === 'Active'
        ? t('rental.ui.customerActive', 'Customer set to Active')
        : t('rental.ui.customerInactive', 'Customer set to Inactive'),
      color: 'success',
    })
  }
  finally {
    busyId.value = ''
  }
}

function onMotorcycleMaintenanceSaved() {
  motorcycleMaintenanceOpen.value = false
  motorcycleMaintenanceRow.value = null
}

function onRowSelect(event: Event, row: TableRow<Record<string, unknown>>) {
  if (isTableOnly.value) return
  const target = event.target as HTMLElement | null
  if (target?.closest('a, button, input, [role="checkbox"], [role="menuitem"], [data-slot="dropdown-menu"]')) return
  openRow(row.original)
}

async function deleteIds(ids: string[]) {
  if (!current.value || !canMutate.value || !ids.length) return
  let targetIds = ids
  if (current.value.collection === 'motorcycles') {
    targetIds = ids.filter((id) => {
      const row = store.get('motorcycles', id)
      return String(row?.status || '') !== 'Progressing'
    })
    if (!targetIds.length) {
      toast.add({
        title: t('rental.ui.cannotDeleteProgressing', 'Cannot delete a motorcycle that is Progressing'),
        color: 'warning',
      })
      return
    }
  }
  if (current.value.collection === 'rentalCustomers') {
    targetIds = ids.filter((id) => {
      const row = store.get('rentalCustomers', id)
      return String(row?.status || '') === 'Inactive' && !customerHasOpenRentals(id)
    })
    if (!targetIds.length) {
      toast.add({
        title: t('rental.ui.cannotDeleteActiveCustomer', 'Only Inactive customers without open rentals can be deleted'),
        color: 'warning',
      })
      return
    }
  }
  const ok = await confirm({ kind: 'delete', count: targetIds.length })
  if (!ok) return
  busyId.value = targetIds[0] || ''
  try {
    await store.deleteRemote(current.value.collection, targetIds)
    store.addAudit('Deleted', current.value.title, targetIds.join(', '))
    rowSelection.value = {}
    toast.add({ title: t('core.actions.deletedItems', { n: targetIds.length }), color: 'success' })
  }
  catch (error: unknown) {
    toast.add({
      title: t('api.errorTitle', { status: (error as { statusCode?: number })?.statusCode || 400 }),
      description: error instanceof Error ? error.message : String(error),
      color: 'error',
    })
  }
  finally {
    busyId.value = ''
  }
}

async function deactivateIds(ids: string[]) {
  if (!current.value || !canMutate.value || !ids.length) return
  busyId.value = ids[0] || ''
  try {
    for (const id of ids) {
      const status = current.value.collection === 'documentSequences' ? 'INACTIVE' : 'Inactive'
      await store.updateRemote(current.value.collection, id, { status })
    }
    store.addAudit('Deactivated', current.value.title, ids.join(', '))
    rowSelection.value = {}
    toast.add({ title: t('app.ui.deactivated'), color: 'success' })
  }
  finally {
    busyId.value = ''
  }
}

function closeRentalModal() {
  rentalCloseOpen.value = false
  rentalModalRow.value = null
}

function onRentalSaved() {
  closeRentalModal()
  if (isHttpMode.value) {
    void store.reloadCollections(['rentals', 'motorcycles', 'rentalPayments', 'rentalCharges'])
    return
  }
  store.reload()
}

async function setDocumentSequenceStatus(row: Record<string, unknown>, status: 'ACTIVE' | 'INACTIVE') {
  if (!current.value || !canMutate.value) return
  busyId.value = String(row.id || '')
  try {
    await store.updateRemote(current.value.collection, String(row.id || ''), { status })
    store.addAudit(status === 'ACTIVE' ? 'Activated' : 'Deactivated', current.value.title, String(row.documentType || row.id || ''))
    toast.add({ title: t(status === 'ACTIVE' ? 'core.common.activated' : 'core.common.deactivated'), color: 'success' })
  }
  finally {
    busyId.value = ''
  }
}

function refresh() {
  if (isHttpMode.value && current.value) {
    void store.reloadCollection(current.value.collection)
    return
  }
  store.reload()
}

async function cancelRental(row: Record<string, unknown>) {
  const ok = await confirm({
    kind: 'generic',
    title: t('rental.ui.cancelRentalConfirm', 'Cancel this rental?'),
    description: String(row.rentalNo || ''),
    confirmLabel: t('rental.ui.cancelRental', 'Cancel rental'),
    confirmColor: 'error' as const,
  })
  if (!ok) return
  busyId.value = String(row.id || '')
  try {
    await useRentalCommands().cancel(String(row.id), null)
    store.addAudit('Rental cancelled', 'Rentals', String(row.rentalNo || ''))
    await store.fetchList('rentals', { status: 'Active,Overdue' })
    await store.fetchList('motorcycles')
    toast.add({ title: t('rental.ui.rentalCancelled', 'Rental cancelled'), color: 'success' })
  }
  catch (error: unknown) {
    toast.add({
      title: t('rental.ui.rentalCancelFailed', 'Could not cancel rental'),
      description: error instanceof Error ? error.message : String(error),
      color: 'error',
    })
  }
  finally {
    busyId.value = ''
  }
}

function openRentalPayment(row: Record<string, unknown>) {
  rentalPaymentRow.value = row
  financePaymentAmount.value = Number(row.outstanding || 0) || undefined
  financePaymentMethod.value = PAYMENT_METHODS[0]
  financePaymentReference.value = ''
}

async function submitRentalPayment() {
  const rental = rentalPaymentRow.value
  if (!rental || !financePaymentAmount.value || financePaymentAmount.value <= 0) return
  financeModalBusy.value = true
  try {
    await store.createRemote('rentalPayments', {
      rentalId: String(rental.id),
      amount: Number(financePaymentAmount.value),
      paymentMethod: financePaymentMethod.value,
      paidAt: toIsoZonedOrNow(),
      reference: financePaymentReference.value || null,
      note: null,
    })
    await store.fetchOne('rentals', String(rental.id))
    await store.fetchList('rentalPayments')
    rentalPaymentRow.value = null
    toast.add({ title: t('rental.ui.paymentRecorded', 'Payment recorded'), color: 'success' })
  }
  catch (error: unknown) {
    toast.add({
      title: t('rental.ui.paymentFailed', 'Could not record payment'),
      description: error instanceof Error ? error.message : String(error),
      color: 'error',
    })
  }
  finally {
    financeModalBusy.value = false
  }
}

function openRentalCharge(row: Record<string, unknown>) {
  rentalChargeRow.value = row
  financeChargeType.value = RENTAL_CHARGE_TYPES[0]
  financeChargeDescription.value = ''
  financeChargeAmount.value = undefined
}

async function submitRentalCharge() {
  const rental = rentalChargeRow.value
  if (!rental || !financeChargeAmount.value || financeChargeAmount.value <= 0) return
  financeModalBusy.value = true
  try {
    await store.createRemote('rentalCharges', {
      rentalId: String(rental.id),
      chargeType: financeChargeType.value,
      description: financeChargeDescription.value || null,
      amount: Number(financeChargeAmount.value),
      chargeToCustomer: 'Yes',
    })
    await store.fetchOne('rentals', String(rental.id))
    await store.fetchList('rentalCharges')
    rentalChargeRow.value = null
    toast.add({ title: t('rental.ui.chargeRecorded', 'Charge recorded'), color: 'success' })
  }
  catch (error: unknown) {
    toast.add({
      title: t('rental.ui.chargeFailed', 'Could not record charge'),
      description: error instanceof Error ? error.message : String(error),
      color: 'error',
    })
  }
  finally {
    financeModalBusy.value = false
  }
}

function optionValue(option: ModuleSelectOption) {
  return typeof option === 'string' ? option : option.value
}

function filterItems(filter: { options?: readonly ModuleSelectOption[] | ModuleSelectOption[], key: string }) {
  const fromOptions = (filter.options || []).map(optionValue)
  const sourceRows = current.value
    ? store.list(current.value.collection).map(row => current.value?.collection === 'auditLogs' ? normalizeAuditLog(row) : row)
    : []
  const fromData = [...new Set(sourceRows.map(row => String(row[filter.key] ?? '').trim()).filter(Boolean))]
  return [...new Set([...fromOptions, ...fromData])]
    .map(value => String(value).trim())
    .filter(Boolean)
    .map((value) => {
      const label = filter.key === 'documentType' && isDocumentSequenceType(value)
        ? documentSequenceTypeLabel(value)
        : filter.key === 'workflowStatus'
          ? value.replaceAll('_', ' ')
          : value
      return { label, value }
    })
}
</script>

<template>
  <div v-if="current" class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions
      :can-create="canCreate"
      :create-label="t('app.ui.newEntity', { entity: moduleSingular(current) })"
      :refreshing="pending"
      @create="openCreate"
      @refresh="refresh"
    />

    <TableAppListTable
      v-model:search="q"
      v-model:date-start="dateFrom"
      v-model:date-end="dateTo"
      v-model:row-selection="rowSelection"
      v-model:pagination="pagination"
      :data="result.all"
      :columns="columns"
      :loading="pending"
      :show-date-range="Boolean(dateField)"
      :filters-active="hasActiveFilters"
      :empty-actions="canCreate ? [{ icon: 'i-lucide-plus', label: t('app.ui.newEntity', { entity: moduleSingular(current) }), onClick: openCreate }] : []"
      @select="onRowSelect"
    >
      <template #filters="{ compact }">
        <CommonAppFilterSelect
          v-for="filter in visibleFilters"
          :key="filter.key"
          :model-value="filters[filter.key] ?? []"
          :items="filterItems(filter)"
          :placeholder="fieldLabel(filter)"
          :class="compact ? 'w-full' : 'w-40'"
          @update:model-value="filters[filter.key] = parseFilterQuery($event)"
        />
      </template>
      <template #actions>
        <template v-if="selectedIds.length && canMutate">
          <UButton
            :color="deactivationOnly ? 'warning' : 'error'"
            variant="soft"
            size="sm"
            :icon="deactivationOnly ? 'i-lucide-circle-off' : 'i-lucide-trash-2'"
            class="shrink-0"
            :label="`${deactivationOnly ? t('app.ui.deactivate') : t('app.ui.delete')} (${selectedIds.length})`"
            @click="deactivationOnly ? deactivateIds(selectedIds) : deleteIds(selectedIds)"
          />
          <UButton
            color="neutral"
            variant="ghost"
            size="sm"
            class="shrink-0"
            :label="t('app.ui.clear')"
            @click="rowSelection = {}"
          />
        </template>
      </template>
    </TableAppListTable>
    <RentalTransactionModals
      v-if="rentalModalRow !== null"
      v-model:open="rentalCloseOpen"
      :rental="rentalModalRow"
      @close="closeRentalModal"
      @saved="onRentalSaved"
    />
    <RentalInvoicePreview
      v-if="rentalInvoiceRow !== null"
      :rental="rentalInvoiceRow"
      mode="direct-print"
      @close="rentalInvoiceRow = null"
    />
    <RentalMotorcycleMaintenanceModal
      v-model:open="motorcycleMaintenanceOpen"
      :motorcycle="motorcycleMaintenanceRow"
      @saved="onMotorcycleMaintenanceSaved"
    />

    <UModal
      :open="rentalPaymentRow !== null"
      :title="t('rental.ui.recordPayment', 'Record payment')"
      @update:open="(value: boolean) => { if (!value) rentalPaymentRow = null }"
    >
      <template #body>
        <div class="space-y-3">
          <p class="text-sm text-muted">{{ rentalPaymentRow?.rentalNo }} · {{ rentalPaymentRow?.customer }}</p>
          <UFormField :label="t('rental.ui.amount', 'Amount')" required>
            <UInputNumber
              v-model="financePaymentAmount"
              :min="0"
              :step="0.01"
              :increment="false"
              :decrement="false"
              class="w-full"
            />
          </UFormField>
          <UFormField :label="t('rental.ui.paymentMethod', 'Payment Method')">
            <USelect v-model="financePaymentMethod" :items="[...PAYMENT_METHODS]" class="w-full" />
          </UFormField>
          <UFormField :label="t('rental.ui.reference', 'Reference')">
            <UInput v-model="financePaymentReference" class="w-full" />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('common.actions.cancel', 'Cancel')"
            @click="rentalPaymentRow = null"
          />
          <UButton
            color="primary"
            icon="i-lucide-hand-coins"
            :loading="financeModalBusy"
            :disabled="!financePaymentAmount || financePaymentAmount <= 0"
            :label="t('rental.ui.recordPayment', 'Record payment')"
            @click="submitRentalPayment"
          />
        </div>
      </template>
    </UModal>

    <UModal
      :open="rentalChargeRow !== null"
      :title="t('rental.ui.addCharge', 'Add charge')"
      @update:open="(value: boolean) => { if (!value) rentalChargeRow = null }"
    >
      <template #body>
        <div class="space-y-3">
          <p class="text-sm text-muted">{{ rentalChargeRow?.rentalNo }} · {{ rentalChargeRow?.customer }}</p>
          <UFormField :label="t('rental.ui.chargeType', 'Charge Type')" required>
            <USelect v-model="financeChargeType" :items="[...RENTAL_CHARGE_TYPES]" class="w-full" />
          </UFormField>
          <UFormField :label="t('rental.ui.description', 'Description')">
            <UInput v-model="financeChargeDescription" class="w-full" />
          </UFormField>
          <UFormField :label="t('rental.ui.amount', 'Amount')" required>
            <UInputNumber
              v-model="financeChargeAmount"
              :min="0"
              :step="0.01"
              :increment="false"
              :decrement="false"
              class="w-full"
            />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            :label="t('common.actions.cancel', 'Cancel')"
            @click="rentalChargeRow = null"
          />
          <UButton
            color="warning"
            icon="i-lucide-receipt-text"
            :loading="financeModalBusy"
            :disabled="!financeChargeAmount || financeChargeAmount <= 0"
            :label="t('rental.ui.addCharge', 'Add charge')"
            @click="submitRentalCharge"
          />
        </div>
      </template>
    </UModal>
  </div>
  <div v-else class="grid h-full min-h-0 flex-1 place-items-center p-8">
    <UEmpty
      variant="naked"
      icon="i-lucide-unplug"
      :title="t('app.ui.pageNotWired')"
      :description="t('app.ui.pageNotWiredHint')"
    />
  </div>
</template>
