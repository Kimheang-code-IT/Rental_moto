<script setup lang="ts">
import type { DropdownMenuItem, TableColumn } from '@nuxt/ui'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { formatMoney } from '~/composables/freight/useFreight'
import { listTableRowMetaColumn } from '~/utils/table/list-columns'
import { downloadCsv } from '~/utils/export/csv'

definePageMeta({ titleKey: 'rental.nav.rentalReports', permission: 'reports.view' })

const { t, te } = useI18n()
const store = useFreightStore()
const preferences = usePreferencesStore()
const { setTitle, setBreadcrumbs, clear } = useAppHeader()
const invoiceRow = ref<Record<string, unknown> | null>(null)

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
const customer = ref<string[]>([])
const motorcycle = ref<string[]>([])
const paymentStatus = ref<string[]>([])
const createdBy = ref<string[]>([])
const dateFrom = ref('')
const dateTo = ref('')
const pagination = ref({ pageIndex: 0, pageSize: 20 })

const completed = computed(() => store.list('rentals').filter(row => String(row.status) === 'Completed'))

const customerItems = computed(() => [...new Set(completed.value.map(row => String(row.customer || '')).filter(Boolean))])
const motorcycleItems = computed(() => [...new Set(completed.value.map(row => String(row.motorcycle || '')).filter(Boolean))])
const paymentStatusItems = computed(() => [...new Set(completed.value.map(row => String(row.paymentStatus || 'Paid')).filter(Boolean))])
const createdByItems = computed(() => [...new Set(completed.value.map(row => String(row.createdBy || '')).filter(Boolean))])

const rows = computed(() => completed.value
  .filter(row => !q.value || JSON.stringify(row).toLowerCase().includes(q.value.toLowerCase()))
  .filter(row => !customer.value.length || customer.value.includes(String(row.customer)))
  .filter(row => !motorcycle.value.length || motorcycle.value.includes(String(row.motorcycle)))
  .filter(row => !paymentStatus.value.length || paymentStatus.value.includes(String(row.paymentStatus || 'Paid')))
  .filter(row => !createdBy.value.length || createdBy.value.includes(String(row.createdBy)))
  .filter((row) => {
    const day = String(row.returnDate || row.dueDate || '').slice(0, 10)
    if (!dateFrom.value && !dateTo.value) return true
    if (!day) return false
    if (dateFrom.value && day < dateFrom.value) return false
    if (dateTo.value && day > dateTo.value) return false
    return true
  }))

function moneyCell(row: Record<string, unknown>, key: string) {
  return h('span', { class: 'block text-end tabular-nums' }, money(row[key], row.currency))
}

const columns = computed<TableColumn<Record<string, unknown>>[]>(() => [
  {
    accessorKey: 'rentalNo',
    header: tx('rental.ui.rentalNo', 'Rental Number'),
    cell: ({ row }) => h('span', { class: 'font-medium' }, String(row.original.rentalNo || '—')),
  },
  { accessorKey: 'customer', header: tx('rental.ui.customer', 'Customer') },
  { accessorKey: 'motorcycle', header: tx('rental.ui.motorcycle', 'Motorcycle') },
  { accessorKey: 'startDate', header: tx('rental.ui.startDate', 'Start') },
  { accessorKey: 'dueDate', header: tx('rental.ui.dueDate', 'Due') },
  { accessorKey: 'returnDate', header: tx('rental.ui.returnDate', 'Returned') },
  { accessorKey: 'rentalCharge', header: tx('rental.ui.rentalCharge', 'Rental Charge'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => moneyCell(row.original, 'rentalCharge') },
  { accessorKey: 'lateFee', header: tx('rental.ui.lateFee', 'Late Fee'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => moneyCell(row.original, 'lateFee') },
  { accessorKey: 'additionalCharges', header: tx('rental.ui.additionalCharges', 'Additional Charges'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => moneyCell(row.original, 'additionalCharges') },
  { accessorKey: 'totalDue', header: tx('rental.ui.totalDue', 'Total'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => moneyCell(row.original, 'totalDue') },
  { accessorKey: 'paid', header: tx('rental.ui.paid', 'Paid'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => moneyCell(row.original, 'paid') },
  { accessorKey: 'outstanding', header: tx('rental.ui.outstanding', 'Outstanding'), meta: { class: { td: 'text-end tabular-nums', th: 'text-end' } }, cell: ({ row }) => moneyCell(row.original, 'outstanding') },
  {
    accessorKey: 'paymentStatus',
    header: tx('rental.ui.paymentStatus', 'Payment Status'),
    cell: ({ row }) => {
      const status = String(row.original.paymentStatus || (Number(row.original.outstanding) > 0 ? 'Partial' : 'Paid'))
      return h(UBadge, { color: status === 'Paid' ? 'success' : 'warning', variant: 'subtle', size: 'sm' }, () => status)
    },
  },
  { accessorKey: 'createdBy', header: tx('rental.ui.staff', 'Staff') },
  listTableRowMetaColumn<Record<string, unknown>>({
    summary: '',
    items: rowMenuItems,
    loadingId: '',
  }),
])

function rowMenuItems(row: Record<string, unknown>): DropdownMenuItem[][] {
  return [[
    {
      label: tx('freight.ui.open', 'Open'),
      icon: 'i-lucide-eye',
      onSelect: () => { void navigateTo(`/rentals/${String(row.id)}`) },
    },
    {
      label: tx('rental.ui.printInvoice', 'Print Invoice'),
      icon: 'i-lucide-printer',
      onSelect: () => { invoiceRow.value = row },
    },
  ]]
}

function exportCsv() {
  downloadCsv({
    filename: `rental-reports-${new Date().toISOString().slice(0, 10)}.csv`,
    fields: [
      { label: 'Rental Number', value: 'rentalNo' },
      { label: 'Customer', value: 'customer' },
      { label: 'Motorcycle', value: 'motorcycle' },
      { label: 'Start', value: 'startDate' },
      { label: 'Due', value: 'dueDate' },
      { label: 'Returned', value: 'returnDate' },
      { label: 'Rental Charge', value: 'rentalCharge' },
      { label: 'Late Fee', value: 'lateFee' },
      { label: 'Additional Charges', value: 'additionalCharges' },
      { label: 'Total', value: 'totalDue' },
      { label: 'Paid', value: 'paid' },
      { label: 'Outstanding', value: 'outstanding' },
      { label: 'Payment Status', value: 'paymentStatus' },
      { label: 'Staff', value: 'createdBy' },
    ],
    rows: rows.value as Array<Record<string, unknown>>,
  })
}
</script>

<template>
  <div class="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <TableAppListTable
      v-model:search="q"
      v-model:date-start="dateFrom"
      v-model:date-end="dateTo"
      v-model:pagination="pagination"
      :data="rows"
      :columns="columns"
      :show-date-range="true"
      :filters-active="Boolean(customer.length || motorcycle.length || paymentStatus.length || createdBy.length || dateFrom || dateTo)"
    >
      <template #filters="{ compact }">
        <CommonAppFilterSelect
          v-model="customer"
          :items="customerItems"
          :placeholder="tx('rental.ui.customer', 'Customer')"
          :class="compact ? 'w-full' : 'w-40'"
        />
        <CommonAppFilterSelect
          v-model="motorcycle"
          :items="motorcycleItems"
          :placeholder="tx('rental.ui.motorcycle', 'Motorcycle')"
          :class="compact ? 'w-full' : 'w-44'"
        />
        <CommonAppFilterSelect
          v-model="paymentStatus"
          :items="paymentStatusItems"
          :placeholder="tx('rental.ui.paymentStatus', 'Payment Status')"
          :class="compact ? 'w-full' : 'w-36'"
        />
        <CommonAppFilterSelect
          v-model="createdBy"
          :items="createdByItems"
          :placeholder="tx('rental.ui.staff', 'Staff')"
          :class="compact ? 'w-full' : 'w-36'"
        />
      </template>
      <template #actions>
        <UButton
          size="sm"
          variant="soft"
          icon="i-lucide-download"
          :label="tx('rental.ui.export', 'Export')"
          class="shrink-0"
          @click="exportCsv"
        />
      </template>
    </TableAppListTable>

    <RentalInvoicePreview :rental="invoiceRow" mode="direct-print" @close="invoiceRow = null" />
  </div>
</template>
