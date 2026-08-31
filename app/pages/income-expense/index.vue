<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { ULink } from '#components'
import type { ExportFieldOption, ExportRequest } from '~/types/docetra/export'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { formatMoney } from '~/composables/module/useModule'
import { RENTAL_EXPENSE_TYPES } from '~/config/rental-options'
import { downloadCsv } from '~/utils/export/csv'

definePageMeta({ titleKey: 'rental.pages.incomeExpense', permission: 'rental.finance.view' })

const { t, te } = useI18n()
const store = useAppDataStore()
const preferences = usePreferencesStore()
const auth = useAuthStore()
const { setTitle, setBreadcrumbs, clear } = useAppHeader()

onBeforeUnmount(clear)

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

watch(() => t('rental.pages.incomeExpense'), (title) => {
  setTitle(title)
  setBreadcrumbs([{ label: title }])
}, { immediate: true })

const money = (value: unknown, currency?: string) => formatMoney(value, currency || preferences.currency)

const q = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const typeFilter = ref<string[]>([])
const expenseModalOpen = ref(false)
const pagination = ref({ pageIndex: 0, pageSize: 20 })
const canCreateExpense = computed(() => auth.canAccessPage('rental.finance.create'))

const inPeriod = (day: string) => {
  if (dateFrom.value && day < dateFrom.value) return false
  if (dateTo.value && day > dateTo.value) return false
  return true
}

const incomeRows = computed(() => store.list('rentalPayments').filter((row) => {
  const day = String(row.paidAt || '').slice(0, 10)
  return day && inPeriod(day)
}))
const expenseRows = computed(() => store.list('rentalExpenses').filter((row) => {
  const day = String(row.date || '').slice(0, 10)
  return day && inPeriod(day)
}))

const totalIncome = computed(() => incomeRows.value.reduce((sum, row) => sum + Number(row.amount || 0), 0))
const totalExpense = computed(() => expenseRows.value.reduce((sum, row) => sum + Number(row.amount || 0), 0))
const net = computed(() => totalIncome.value - totalExpense.value)
const outstanding = computed(() => store.list('rentals')
  .filter(row => ['Active', 'Overdue', 'Completed'].includes(String(row.status)))
  .reduce((sum, row) => sum + Number(row.outstanding || 0), 0))

const kpis = computed(() => [
  { key: 'income', label: tx('rental.ui.income', 'Income'), value: money(totalIncome.value), color: 'text-success' },
  { key: 'expense', label: tx('rental.ui.expense', 'Expense'), value: money(totalExpense.value), color: 'text-error' },
  { key: 'net', label: tx('rental.ui.net', 'Net'), value: money(net.value), color: net.value >= 0 ? 'text-success' : 'text-error' },
  { key: 'outstanding', label: tx('rental.ui.outstanding', 'Outstanding'), value: money(outstanding.value), color: 'text-warning' },
])

type TxRow = Record<string, unknown> & { kind: 'income' | 'expense' }
const transactionDate = (row: Record<string, unknown>) => String(row.paidAt || row.date || '')
const transactionRows = computed<TxRow[]>(() => [
  ...incomeRows.value.map(row => ({ ...row, kind: 'income' as const })),
  ...expenseRows.value.map(row => ({ ...row, kind: 'expense' as const })),
].sort((a, b) => transactionDate(b).localeCompare(transactionDate(a))))

const rows = computed(() => transactionRows.value.filter((row) => {
  if (!typeFilter.value.length) return true
  const type = row.kind === 'income' ? 'income' : String(row.expenseType || 'expense')
  return typeFilter.value.includes(type)
}))

const typeFilterItems = computed(() => [
  { label: tx('rental.ui.income', 'Income'), value: 'income' },
  ...RENTAL_EXPENSE_TYPES.map(value => ({ label: value, value })),
])

const columns = computed<TableColumn<TxRow>[]>(() => [
  { accessorKey: 'paidAt', header: tx('rental.ui.date', 'Date'), cell: ({ row }) => h('span', { class: 'tabular-nums' }, String(row.original.paidAt || row.original.date || '—').slice(0, 10)) },
  {
    accessorKey: 'docNo',
    header: tx('rental.ui.reference', 'Reference'),
    cell: ({ row }) => {
      const record = row.original
      const label = String(record.paymentNo || record.expenseNo || '—')

      if (record.kind === 'income' && record.rentalId) {
        return h(ULink, {
          to: `/rentals/${String(record.rentalId)}`,
          class: 'font-medium text-highlighted hover:text-primary hover:underline',
        }, () => label)
      }

      return h('span', { class: 'font-medium' }, label)
    },
  },
  { accessorKey: 'label', header: tx('rental.ui.description', 'Description'), cell: ({ row }) => h('span', { class: 'block max-w-72 truncate' }, String(row.original.customer || row.original.description || '—')) },
  {
    accessorKey: 'kind',
    header: tx('rental.ui.type', 'Type'),
    cell: ({ row }) => h('span', {
      class: row.original.kind === 'income' ? 'text-success font-medium' : 'text-error font-medium',
    }, row.original.kind === 'income' ? tx('rental.ui.income', 'Income') : String(row.original.expenseType || tx('rental.ui.expense', 'Expense'))),
  },
  {
    accessorKey: 'amount',
    header: tx('rental.ui.amount', 'Amount'),
    meta: { class: { td: 'text-end', th: 'text-end' } },
    cell: ({ row }) => h('span', {
      class: `block text-end tabular-nums font-medium ${row.original.kind === 'income' ? 'text-success' : 'text-error'}`,
    }, `${row.original.kind === 'income' ? '+' : '-'}${money(row.original.amount, String(row.original.currency || preferences.currency))}`),
  },
])

const exportFields = computed<ExportFieldOption[]>(() => [
  { label: tx('rental.ui.date', 'Date'), value: 'date' },
  { label: tx('rental.ui.reference', 'Reference'), value: 'reference' },
  { label: tx('rental.ui.description', 'Description'), value: 'description' },
  { label: tx('rental.ui.type', 'Type'), value: 'type' },
  { label: tx('rental.ui.amount', 'Amount'), value: 'amount' },
])

function refresh() {
  store.reload()
}

function exportCsv(request: ExportRequest) {
  let exportRows = rows.value.map(row => ({
    date: transactionDate(row).slice(0, 10),
    reference: String(row.paymentNo || row.expenseNo || ''),
    description: String(row.customer || row.description || ''),
    type: row.kind === 'income' ? tx('rental.ui.income', 'Income') : String(row.expenseType || tx('rental.ui.expense', 'Expense')),
    amount: row.kind === 'income' ? Number(row.amount || 0) : -Number(row.amount || 0),
  }))
  if (request.startDate) exportRows = exportRows.filter(row => row.date >= request.startDate!)
  if (request.endDate) exportRows = exportRows.filter(row => row.date <= request.endDate!)
  if (request.scope === 'current_page') {
    const start = pagination.value.pageIndex * pagination.value.pageSize
    exportRows = exportRows.slice(start, start + pagination.value.pageSize)
  }
  const selected = new Set(request.fieldCodes)
  downloadCsv({
    filename: `income-expense-${dateFrom.value || 'all'}-${dateTo.value || 'all'}.csv`,
    fields: exportFields.value.filter(field => selected.has(field.value)),
    rows: exportRows,
  })
}
</script>
<template>
  <div class="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions
      :can-create="canCreateExpense"
      :create-label="tx('rental.ui.addExpense', 'Add Expense')"
      :export-fields="exportFields"
      @create="expenseModalOpen = true"
      @refresh="refresh"
      @export="exportCsv"
    />

    <div class="grid grid-cols-2 gap-3 p-3 lg:grid-cols-4">
      <div
        v-for="kpi in kpis"
        :key="kpi.key"
        class="rounded-lg border border-default bg-default p-4"
      >
        <p class="text-xs uppercase tracking-wide text-muted">{{ kpi.label }}</p>
        <p class="mt-1 text-xl font-semibold tabular-nums" :class="kpi.color">{{ kpi.value }}</p>
      </div>
    </div>

    <TableAppListTable
      v-model:search="q"
      v-model:date-start="dateFrom"
      v-model:date-end="dateTo"
      v-model:pagination="pagination"
      :data="rows"
      :columns="columns"
      :show-date-range="true"
      :filters-active="Boolean(dateFrom || dateTo || typeFilter.length)"
    >
      <template #filters="{ compact }">
        <CommonAppFilterSelect
          v-model="typeFilter"
          :items="typeFilterItems"
          :placeholder="tx('rental.ui.type', 'Type')"
          :class="compact ? 'w-full' : 'w-40'"
        />
      </template>
    </TableAppListTable>

    <RentalExpenseModal v-model:open="expenseModalOpen" />
  </div>
</template>
