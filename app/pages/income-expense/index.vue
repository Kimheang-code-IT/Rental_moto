<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { formatMoney } from '~/composables/freight/useFreight'
import { downloadCsv } from '~/utils/export/csv'
import { RENTAL_EXPENSE_TYPES } from '~/config/rental-options'

definePageMeta({ titleKey: 'rental.pages.incomeExpense', permission: 'rental.finance.view' })

const { t, te } = useI18n()
const store = useFreightStore()
const auth = useAuthStore()
const preferences = usePreferencesStore()
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

const now = new Date()
const year = ref(String(now.getFullYear()))
const month = ref(String(now.getMonth() + 1).padStart(2, '0'))
const canAddExpense = computed(() => auth.canAccessPage('rental.finance.create'))

const years = computed(() => {
  const values = new Set<number>([now.getFullYear()])
  for (const row of [...store.list('rentalPayments'), ...store.list('rentalExpenses')]) {
    const y = Number(String(row.paidAt || row.date || '').slice(0, 4))
    if (Number.isFinite(y) && y > 2000) values.add(y)
  }
  return [...values].sort((a, b) => b - a).map(y => ({ label: String(y), value: String(y) }))
})

const inPeriod = (day: string) => (!year.value || day.slice(0, 4) === year.value) && (month.value === 'all' || day.slice(5, 7) === month.value)

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
const rows = computed<TxRow[]>(() => [
  ...incomeRows.value.map(row => ({ ...row, kind: 'income' as const })),
  ...expenseRows.value.map(row => ({ ...row, kind: 'expense' as const })),
].sort((a, b) => String(b.paidAt || b.date || '').localeCompare(String(a.paidAt || a.date || ''))))

const columns = computed<TableColumn<TxRow>[]>(() => [
  { accessorKey: 'paidAt', header: tx('rental.ui.date', 'Date'), cell: ({ row }) => h('span', { class: 'tabular-nums' }, String(row.original.paidAt || row.original.date || '—').slice(0, 10)) },
  { accessorKey: 'docNo', header: tx('rental.ui.reference', 'Reference'), cell: ({ row }) => h('span', { class: 'font-medium' }, String(row.original.paymentNo || row.original.expenseNo || '—')) },
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
    }, `${row.original.kind === 'income' ? '+' : '-'}${money(row.original.amount, row.original.currency)}`),
  },
])

// Add Expense modal
const expenseOpen = ref(false)
const expenseSaving = ref(false)
const expenseDate = ref(new Date().toISOString().slice(0, 10))
const expenseType = ref('Maintenance')
const expenseDescription = ref('')
const expenseAmount = ref(0)

function openExpense() {
  expenseDate.value = new Date().toISOString().slice(0, 10)
  expenseType.value = 'Maintenance'
  expenseDescription.value = ''
  expenseAmount.value = 0
  expenseOpen.value = true
}

function saveExpense() {
  if (expenseAmount.value <= 0) return
  expenseSaving.value = true
  try {
    const seq = store.list('rentalExpenses').length + 1
    store.create('rentalExpenses', {
      expenseNo: `RNX-${String(seq).padStart(6, '0')}`,
      date: expenseDate.value,
      expenseType: expenseType.value,
      description: expenseDescription.value,
      amount: expenseAmount.value,
      currency: preferences.currency,
      createdBy: store.session()?.name || '',
    }, 'rxp')
    store.addAudit(`Expense ${money(expenseAmount.value)} (${expenseType.value})`, 'Income & Expense', expenseDate.value)
    toast.add({ title: tx('rental.ui.expenseSaved', 'Expense recorded'), color: 'success' })
    expenseOpen.value = false
  }
  finally {
    expenseSaving.value = false
  }
}

function exportCsv() {
  downloadCsv({
    filename: `income-expense-${year.value}-${month.value}.csv`,
    fields: [
      { label: 'Date', value: 'paidAt' },
      { label: 'Reference', value: 'docNo' },
      { label: 'Description', value: 'label' },
      { label: 'Type', value: 'kind' },
      { label: 'Amount', value: 'amount' },
    ],
    rows: rows.value as Array<Record<string, unknown>>,
  })
}
</script>
<template>
  <div class="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <div class="flex items-center justify-end gap-2 border-b border-default bg-default px-3 py-2">
      <USelect v-model="year" :items="years" class="w-24" size="sm" />
      <USelect
        v-model="month"
        :items="[{ label: tx('rental.ui.allMonths', 'All Months'), value: 'all' }, ...Array.from({ length: 12 }, (_, i) => ({ label: String(i + 1).padStart(2, '0'), value: String(i + 1).padStart(2, '0') }))]"
        class="w-32"
        size="sm"
      />
      <div class="flex-1" />
      <UButton
        v-if="canAddExpense"
        size="sm"
        icon="i-lucide-plus"
        :label="tx('rental.ui.addExpense', 'Add Expense')"
        @click="openExpense"
      />
      <UButton
        size="sm"
        variant="soft"
        icon="i-lucide-download"
        :label="tx('rental.ui.export', 'Export')"
        @click="exportCsv"
      />
    </div>

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

    <div class="min-h-0 flex-1 overflow-hidden px-1.5 pb-1.5">
      <TableAppListTable
        v-model:pagination="pagination"
        :data="rows"
        :columns="columns"
      />
    </div>

    <UModal
      v-model:open="expenseOpen"
      :title="tx('rental.ui.addExpense', 'Add Expense')"
    >
      <template #body>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.date', 'Date') }} <span class="text-error">*</span></label>
            <UInput v-model="expenseDate" type="date" class="w-full" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.expenseType', 'Expense Type') }}</label>
            <USelect v-model="expenseType" :items="[...RENTAL_EXPENSE_TYPES]" class="w-full" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.amount', 'Amount') }} <span class="text-error">*</span></label>
            <UInput v-model.number="expenseAmount" type="number" min="0" class="w-full" />
          </div>
          <div class="col-span-2">
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.description', 'Description') }}</label>
            <UInput v-model="expenseDescription" class="w-full" />
          </div>
        </div>
      </template>
      <template #footer>
        <div class="flex w-full justify-end gap-2">
          <UButton color="neutral" variant="ghost" :label="tx('common.actions.cancel', 'Cancel')" @click="expenseOpen = false" />
          <UButton :loading="expenseSaving" :disabled="expenseAmount <= 0" icon="i-lucide-check" :label="tx('common.actions.save', 'Save')" @click="saveExpense" />
        </div>
      </template>
    </UModal>
  </div>
</template>
