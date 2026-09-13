<script setup lang="ts">
import type { DropdownMenuItem, TableColumn } from '@nuxt/ui'
import { UBadge, ULink } from '#components'
import type { ExportFieldOption, ExportRequest } from '~/types/rental/export'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { formatMoney, statusLabel } from '~/composables/module/useModule'
import { useAppLocalization } from '~/composables/settings/useAppLocalization'
import { listTableRowMetaColumn } from '~/utils/table/list-columns'
import { useServerExport } from '~/composables/common/useServerExport'
import { downloadCsv } from '~/utils/export/csv'
import { latestRentalPaymentMethods } from '~/utils/rental/payments'
import { daysBetween } from '~/utils/rental/pricing'
import {
  LIST_SORT_PRESETS,
  listSortItemLabel,
  sortListRows,
  type ListSortMode,
} from '~/utils/table/list-sort'

definePageMeta({ titleKey: 'rental.nav.rentalReports', permission: 'reports.view' })

const { t, te } = useI18n()
const auth = useAuthStore()
const store = useAppDataStore()
const preferences = usePreferencesStore()
const { setTitle, setBreadcrumbs, clear } = useAppHeader()
const { request: requestServerExport } = useServerExport()
const { formatDateTime, localization } = useAppLocalization()
const canExport = computed(() => auth.canAccessPage('reports.export'))
const invoiceRow = ref<Record<string, unknown> | null>(null)
const chargesReviewRental = ref<Record<string, unknown> | null>(null)
const chargesReviewOpen = ref(false)
const canPrintInvoice = computed(() =>
  auth.canAccessPage('reports.print') || auth.canAccessPage('rental.rentals.print'),
)

onBeforeUnmount(clear)

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

watch(() => t('rental.nav.rentalReports'), (title) => {
  setTitle(title)
  setBreadcrumbs([{ label: title }])
}, { immediate: true })

const money = (value: unknown, currency?: string) =>
  formatMoney(value, currency || preferences.currency)

const q = ref('')
const paymentStatus = ref<string[]>([])
const paymentMethod = ref<string[]>([])
const dateFrom = ref('')
const dateTo = ref('')
const pagination = ref({ pageIndex: 0, pageSize: 20 })

const reportSortPreset = LIST_SORT_PRESETS.rentalReports
const sortMode = ref<ListSortMode>(reportSortPreset.defaultMode)
const sortItems = computed(() => reportSortPreset.modes.map((mode: ListSortMode) => {
  const label = listSortItemLabel(mode)
  return { label: tx(label.key, label.fallback), value: mode }
}))

const paymentMethods = computed(() => latestRentalPaymentMethods(store.list('rentalPayments')))
const completed = computed<Array<Record<string, unknown>>>(() => {
  if (store.isHttpMode) {
    // Reports come from the server-backed reports collection, not a client scan.
    const rows = store.list('rentalReports')
    return rows
      .filter(row => String(row.status) === 'Completed')
      .map(row => ({
        ...row,
        paymentMethod: paymentMethods.value.get(String(row.id || '')) || row.paymentMethod || '—',
      }) as Record<string, unknown>)
  }
  return store.list('rentals')
    .filter(row => String(row.status) === 'Completed')
    .map(row => ({
      ...row,
      paymentMethod: paymentMethods.value.get(String(row.id || '')) || row.paymentMethod || '—',
    }) as Record<string, unknown>)
})

// Client-only: reports data loads in the browser after mount.
function reloadReports() {
  if (!import.meta.client || !store.isHttpMode) return
  void store.fetchList('rentalReports', {
    q: q.value || undefined,
    status: 'Completed',
    startDate: dateFrom.value || undefined,
    endDate: dateTo.value || undefined,
  })
  void store.fetchList('rentalPayments')
}

onMounted(() => {
  reloadReports()
})

watch([q, dateFrom, dateTo], () => {
  reloadReports()
})

watch(sortMode, () => {
  pagination.value = { ...pagination.value, pageIndex: 0 }
})

const selectItems = (values: string[]) => [...new Set(values.filter(Boolean))]
  .sort((a, b) => a.localeCompare(b))
  .map(value => ({ label: value, value }))

const paymentStatusItems = computed(() => [...new Set(
  completed.value.map(row => String(row.paymentStatus || (Number(row.outstanding) > 0 ? 'Partial' : 'Paid'))).filter(Boolean),
)].map(value => ({
  label: statusLabel(value, t, te),
  value,
})))
const paymentMethodItems = computed(() => selectItems(completed.value.map(row => String(row.paymentMethod || ''))))

const rows = computed(() => {
  const filtered = completed.value
    .filter(row => !q.value || JSON.stringify(row).toLowerCase().includes(q.value.toLowerCase()))
    .filter(row => !paymentStatus.value.length || paymentStatus.value.includes(String(row.paymentStatus || 'Paid')))
    .filter(row => !paymentMethod.value.length || paymentMethod.value.includes(String(row.paymentMethod)))
    .filter((row) => {
      const day = String(row.returnDate || row.dueDate || '').slice(0, 10)
      if (!dateFrom.value && !dateTo.value) return true
      if (!day) return false
      if (dateFrom.value && day < dateFrom.value) return false
      if (dateTo.value && day > dateTo.value) return false
      return true
    })

  return sortListRows(filtered, sortMode.value, reportSortPreset)
})

function openChargesReview(row: Record<string, unknown>) {
  chargesReviewRental.value = row
  chargesReviewOpen.value = true
}

function moneyCell(row: Record<string, unknown>, key: string) {
  return h('span', { class: 'block text-end tabular-nums' }, money(row[key], String(row.currency || preferences.currency)))
}

function dateTimeCell(value: unknown) {
  return h('span', { class: 'whitespace-nowrap' }, formatDateTime(value))
}

/** Final rental length for completed returns: start → return, else stored durationDays. */
function finalDurationDays(row: Record<string, unknown>) {
  const start = String(row.startDate || '')
  const returned = String(row.returnDate || '')
  if (start && returned) {
    const actual = daysBetween(start, returned)
    if (actual > 0) return actual
  }
  const stored = Math.max(0, Number(row.durationDays) || 0)
  return stored > 0 ? stored : null
}

function durationCell(row: Record<string, unknown>) {
  const days = finalDurationDays(row)
  return h('span', { class: 'block text-end tabular-nums' }, days == null ? '—' : String(days))
}

function additionalChargesCell(row: Record<string, unknown>) {
  const amount = Number(row.additionalCharges || 0)
  const text = money(row.additionalCharges, String(row.currency || preferences.currency))
  if (amount <= 0) {
    return h('span', { class: 'block text-end tabular-nums text-muted' }, text)
  }
  return h('button', {
    type: 'button',
    class: 'block w-full text-end tabular-nums font-medium text-primary hover:underline',
    title: tx('rental.ui.viewAdditionalCharges', 'View charge details'),
    onClick: (event: Event) => {
      event.stopPropagation()
      openChargesReview(row)
    },
  }, text)
}

function entityLinkCell(
  row: Record<string, unknown>,
  options: {
    idKey: 'customerId' | 'motorcycleId'
    labelKey: 'customer' | 'motorcycle'
    path: '/customers' | '/motorcycles'
    permission: string
  },
) {
  const id = String(row[options.idKey] || '')
  const label = String(row[options.labelKey] || '—')
  const className = 'block max-w-48 truncate'
  if (!id || !auth.canAccessPage(options.permission)) {
    return h('span', { class: `${className} text-default`, title: label }, label)
  }
  return h(ULink, {
    to: `${options.path}/${id}`,
    class: `font-medium text-highlighted hover:text-primary hover:underline ${className}`,
    title: label,
    onClick: (event: Event) => event.stopPropagation(),
  }, () => label)
}

const columns = computed<TableColumn<Record<string, unknown>>[]>(() => {
  void localization.value.dateFormat
  void localization.value.timeFormat
  void localization.value.timezone
  return [
    {
    accessorKey: 'rentalNo',
    header: tx('rental.ui.rentalNo', 'Rental Number'),
    cell: ({ row }) => h(ULink, {
      to: `/rentals/${String(row.original.id)}`,
      class: 'font-medium text-highlighted hover:text-primary hover:underline',
      onClick: (event: Event) => event.stopPropagation(),
    }, () => String(row.original.rentalNo || '—')),
  },
  {
    accessorKey: 'customer',
    header: tx('rental.ui.customer', 'Customer'),
    cell: ({ row }) => entityLinkCell(row.original, {
      idKey: 'customerId',
      labelKey: 'customer',
      path: '/customers',
      permission: 'rental.customers.view',
    }),
  },
  {
    accessorKey: 'motorcycle',
    header: tx('rental.ui.motorcycle', 'Motorcycle'),
    cell: ({ row }) => entityLinkCell(row.original, {
      idKey: 'motorcycleId',
      labelKey: 'motorcycle',
      path: '/motorcycles',
      permission: 'rental.motorcycles.view',
    }),
  },
  { accessorKey: 'plate', header: tx('rental.ui.plate', 'Plate') },
  {
    accessorKey: 'startDate',
    header: tx('rental.ui.startDate', 'Start'),
    cell: ({ row }) => dateTimeCell(row.original.startDate),
  },
  {
    accessorKey: 'dueDate',
    header: tx('rental.ui.dueDate', 'Due'),
    cell: ({ row }) => dateTimeCell(row.original.dueDate),
  },
  {
    accessorKey: 'returnDate',
    header: tx('rental.ui.returnDate', 'Returned'),
    cell: ({ row }) => dateTimeCell(row.original.returnDate),
  },
  {
    accessorKey: 'durationDays',
    header: tx('rental.ui.duration', 'Duration'),
    meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } },
    cell: ({ row }) => durationCell(row.original),
  },
  { accessorKey: 'rentalCharge', header: tx('rental.ui.rentalCharge', 'Rental Charge'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => moneyCell(row.original, 'rentalCharge') },
  { accessorKey: 'discount', header: tx('rental.ui.discount', 'Discount'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => moneyCell(row.original, 'discount') },
  { accessorKey: 'additionalCharges', header: tx('rental.ui.additionalCharges', 'Additional Charges'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => additionalChargesCell(row.original) },
  { accessorKey: 'totalDue', header: tx('rental.ui.totalDue', 'Total'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => moneyCell(row.original, 'totalDue') },
  { accessorKey: 'paid', header: tx('rental.ui.paid', 'Paid'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => moneyCell(row.original, 'paid') },
  { accessorKey: 'outstanding', header: tx('rental.ui.outstanding', 'Outstanding'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => moneyCell(row.original, 'outstanding') },
  {
    accessorKey: 'paymentStatus',
    header: tx('rental.ui.paymentStatus', 'Payment Status'),
    cell: ({ row }) => {
      const status = String(row.original.paymentStatus || (Number(row.original.outstanding) > 0 ? 'Partial' : 'Paid'))
      return h(UBadge, {
        color: status === 'Paid' ? 'success' : 'warning',
        variant: 'subtle',
        size: 'sm',
      }, () => statusLabel(status, t, te))
    },
  },
  { accessorKey: 'paymentMethod', header: tx('rental.ui.paymentMethod', 'Payment Method') },
  listTableRowMetaColumn<Record<string, unknown>>({
    summary: '',
    items: rowMenuItems,
    loadingId: '',
  }),
  ]
})

function rowMenuItems(row: Record<string, unknown>): DropdownMenuItem[][] {
  const items: DropdownMenuItem[] = [
    {
      label: tx('app.ui.open', 'Open'),
      icon: 'i-lucide-eye',
      onSelect: () => { void navigateTo(`/rentals/${String(row.id)}`) },
    },
  ]
  if (canPrintInvoice.value) {
    items.push({
      label: tx('rental.ui.printInvoice', 'Print Invoice'),
      icon: 'i-lucide-printer',
      onSelect: () => { invoiceRow.value = row },
    })
  }
  if (Number(row.additionalCharges || 0) > 0) {
    items.push({
      label: tx('rental.ui.viewAdditionalCharges', 'View charge details'),
      icon: 'i-lucide-list',
      onSelect: () => openChargesReview(row),
    })
  }
  return [items]
}

const exportFields = computed<ExportFieldOption[]>(() => [
  { label: tx('rental.ui.rentalNo', 'Rental Number'), value: 'rentalNo' },
  { label: tx('rental.ui.customer', 'Customer'), value: 'customer' },
  { label: tx('rental.ui.motorcycle', 'Motorcycle'), value: 'motorcycle' },
  { label: tx('rental.ui.startDate', 'Start'), value: 'startDate' },
  { label: tx('rental.ui.dueDate', 'Due'), value: 'dueDate' },
  { label: tx('rental.ui.returnDate', 'Returned'), value: 'returnDate' },
  { label: tx('rental.ui.duration', 'Duration'), value: 'durationDays' },
  { label: tx('rental.ui.rentalCharge', 'Rental Charge'), value: 'rentalCharge' },
  { label: tx('rental.ui.discount', 'Discount'), value: 'discount' },
  { label: tx('rental.ui.additionalCharges', 'Additional Charges'), value: 'additionalCharges' },
  { label: tx('rental.ui.totalDue', 'Total'), value: 'totalDue' },
  { label: tx('rental.ui.paid', 'Paid'), value: 'paid' },
  { label: tx('rental.ui.outstanding', 'Outstanding'), value: 'outstanding' },
  { label: tx('rental.ui.paymentStatus', 'Payment Status'), value: 'paymentStatus' },
  { label: tx('rental.ui.paymentMethod', 'Payment Method'), value: 'paymentMethod' },
])

async function refresh() {
  if (store.isHttpMode) {
    await store.fetchList('rentalReports', {
      status: 'Completed',
      startDate: dateFrom.value || undefined,
      endDate: dateTo.value || undefined,
    })
    return
  }
  store.reload()
}

const currentPageRowIds = computed(() => {
  const start = pagination.value.pageIndex * pagination.value.pageSize
  return rows.value.slice(start, start + pagination.value.pageSize)
    .map(row => String(row.id || '')).filter(Boolean)
})

async function exportCsv(request: ExportRequest) {
  if (store.isHttpMode) {
    // Server export job through the API (in-process); filters ride along in `query`.
    const query: Record<string, unknown> = {
      q: q.value || undefined,
      status: 'Completed',
      paymentStatus: [...paymentStatus.value],
      paymentMethod: [...paymentMethod.value],
    }
    if (request.scope === 'current_page') query.ids = currentPageRowIds.value
    await requestServerExport('rental_reports', request, `rental-reports-${new Date().toISOString().slice(0, 10)}.csv`, {
      query,
      selectedIds: request.scope === 'selected'
        ? rows.value.map(row => String(row.id || '')).filter(Boolean)
        : undefined,
    })
    return
  }
  let exportRows = [...rows.value]
  if (request.startDate) {
    exportRows = exportRows.filter(row => String(row.returnDate || row.dueDate || '').slice(0, 10) >= request.startDate!)
  }
  if (request.endDate) {
    exportRows = exportRows.filter(row => String(row.returnDate || row.dueDate || '').slice(0, 10) <= request.endDate!)
  }
  if (request.scope === 'current_page') {
    const start = pagination.value.pageIndex * pagination.value.pageSize
    exportRows = exportRows.slice(start, start + pagination.value.pageSize)
  }
  const selected = new Set(request.fieldCodes)
  downloadCsv({
    filename: `rental-reports-${new Date().toISOString().slice(0, 10)}.csv`,
    fields: exportFields.value.filter(field => selected.has(field.value)),
    rows: exportRows.map(row => ({
      ...row,
      durationDays: finalDurationDays(row) ?? row.durationDays,
    })) as Array<Record<string, unknown>>,
  })
}
</script>

<template>
  <div class="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions
      :can-export="canExport"
      :export-fields="exportFields"
      @refresh="refresh"
      @export="exportCsv"
    />

    <TableAppListTable
      v-model:search="q"
      v-model:date-start="dateFrom"
      v-model:date-end="dateTo"
      v-model:pagination="pagination"
      :data="rows"
      :columns="columns"
      :show-date-range="true"
      :filters-active="Boolean(paymentStatus.length || paymentMethod.length || dateFrom || dateTo)"
    >
      <template #filters="{ compact }">
        <CommonAppFilterSelect
          v-model="paymentStatus"
          :items="paymentStatusItems"
          :placeholder="tx('rental.ui.paymentStatus', 'Payment Status')"
          :class="compact ? 'w-full' : 'w-36'"
        />
        <CommonAppFilterSelect
          v-model="paymentMethod"
          :items="paymentMethodItems"
          :placeholder="tx('rental.ui.paymentMethod', 'Payment Method')"
          :class="compact ? 'w-full' : 'w-36'"
        />
      </template>
      <template #actions>
        <USelect
          v-model="sortMode"
          :items="sortItems"
          :placeholder="tx('rental.ui.sort', 'Sort')"
          icon="i-lucide-arrow-up-down"
          size="sm"
          class="w-44 shrink-0"
        />
      </template>
    </TableAppListTable>

    <RentalInvoicePreview :rental="invoiceRow" mode="direct-print" @close="invoiceRow = null" />
    <RentalChargesReviewModal
      v-model:open="chargesReviewOpen"
      :rental="chargesReviewRental"
    />
  </div>
</template>
