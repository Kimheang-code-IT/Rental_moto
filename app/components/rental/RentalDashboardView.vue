<script setup lang="ts">
import type { EChartsCoreOption } from 'echarts/core'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { usePageSeo } from '~/composables/usePageSeo'
import { formatMoney } from '~/composables/freight/useFreight'
import { downloadCsv } from '~/utils/export/csv'

/**
 * HollyWing Motor dashboard: fleet + rentals KPIs, rentals-by-day chart,
 * income/expense chart, and an active-rental preview table.
 */
const store = useFreightStore()
const preferences = usePreferencesStore()
const { t, te, locale } = useI18n()
const { setTitle, clear } = useAppHeader()

onBeforeUnmount(clear)
usePageSeo({ title: () => t('rental.nav.dashboard') })

watch(() => t('rental.nav.dashboard'), title => setTitle(title), { immediate: true })

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

const money = (value: unknown) => formatMoney(value, preferences.currency)

const now = new Date()
const chartYear = ref(String(now.getFullYear()))
const chartMonth = ref(String(now.getMonth() + 1).padStart(2, '0'))
const ieYear = ref(String(now.getFullYear()))
const ieMonth = ref('all')

const motorcycles = computed(() => store.list('motorcycles'))
const rentals = computed(() => store.list('rentals'))
const customers = computed(() => store.list('rentalCustomers'))
const payments = computed(() => store.list('rentalPayments'))
const expenses = computed(() => store.list('rentalExpenses'))

const activeRentals = computed(() => rentals.value.filter(row => String(row.status) === 'Active'))
const overdueRentals = computed(() => rentals.value.filter(row => String(row.status) === 'Overdue'))

const monthIncome = computed(() => payments.value
  .filter(row => String(row.paidAt || '').slice(0, 7) === `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
  .reduce((sum, row) => sum + Number(row.amount || 0), 0))
const monthExpense = computed(() => expenses.value
  .filter(row => String(row.date || '').slice(0, 7) === `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`)
  .reduce((sum, row) => sum + Number(row.amount || 0), 0))
const totalOutstanding = computed(() => rentals.value
  .filter(row => ['Active', 'Overdue', 'Completed'].includes(String(row.status)))
  .reduce((sum, row) => sum + Number(row.outstanding || 0), 0))

interface KpiCard { key: string, title: string, value: string | number, to?: string, hint?: string }

const fleetCards = computed<KpiCard[]>(() => [
  { key: 'total', title: tx('rental.dashboard.totalMotos', 'Total Motorcycles'), value: motorcycles.value.length, to: '/motorcycles' },
  { key: 'available', title: tx('rental.dashboard.available', 'Available'), value: motorcycles.value.filter(row => String(row.status) === 'Available').length, to: '/motorcycles?status=Available' },
  { key: 'rented', title: tx('rental.dashboard.rented', 'Rented'), value: motorcycles.value.filter(row => String(row.status) === 'Rented').length, to: '/motorcycles?status=Rented' },
  { key: 'maintenance', title: tx('rental.dashboard.maintenance', 'Maintenance'), value: motorcycles.value.filter(row => String(row.status) === 'Maintenance').length, to: '/motorcycles?status=Maintenance' },
])

const rentalCards = computed<KpiCard[]>(() => [
  { key: 'active', title: tx('rental.dashboard.activeRentals', 'Active Rentals'), value: activeRentals.value.length, to: '/rentals' },
  { key: 'overdue', title: tx('rental.dashboard.overdueRentals', 'Overdue Rentals'), value: overdueRentals.value.length, to: '/rentals?status=Overdue' },
  { key: 'customers', title: tx('rental.dashboard.totalCustomers', 'Total Customers'), value: customers.value.length, to: '/customers' },
  { key: 'income', title: tx('rental.dashboard.incomeMonth', 'Income This Month'), value: money(monthIncome.value), to: '/income-expense' },
  { key: 'expense', title: tx('rental.dashboard.expenseMonth', 'Expense This Month'), value: money(monthExpense.value), to: '/income-expense' },
  { key: 'outstanding', title: tx('rental.dashboard.outstanding', 'Outstanding'), value: money(totalOutstanding.value), to: '/income-expense' },
])

// ---- Rentals-by-day chart ----
const chartYears = computed(() => {
  const values = new Set<number>([now.getFullYear()])
  for (const row of rentals.value) {
    const y = Number(String(row.startDate || '').slice(0, 4))
    if (Number.isFinite(y) && y > 2000) values.add(y)
  }
  return [...values].sort((a, b) => b - a).map(y => ({ label: String(y), value: String(y) }))
})
const chartMonths = computed(() => Array.from({ length: 12 }, (_, i) => ({
  label: new Date(2026, i, 1).toLocaleDateString(locale.value === 'km' ? 'km-KH' : 'en-US', { month: 'short' }),
  value: String(i + 1).padStart(2, '0'),
})))

const rentalByDay = computed(() => {
  const prefix = `${chartYear.value}-${chartMonth.value}`
  const days = new Date(Number(chartYear.value), Number(chartMonth.value), 0).getDate()
  const counts = Array.from({ length: days }, () => 0)
  for (const row of rentals.value) {
    const day = String(row.startDate || '')
    if (day.slice(0, 7) === prefix) {
      const d = Number(day.slice(8, 10))
      if (d >= 1 && d <= days) counts[d - 1] += 1
    }
  }
  return counts
})

const dark = computed(() => useColorMode().value === 'dark')
const axisColor = computed(() => (dark.value ? '#3f3f46' : '#e4e4e7'))
const labelColor = computed(() => (dark.value ? '#a1a1aa' : '#71717a'))
const splitColor = computed(() => (dark.value ? 'rgba(255,255,255,0.08)' : 'rgba(24,24,27,0.07)'))
const BRAND = '#e8472a'
const GOLD = '#d4a017'

const rentalsByDayOption = computed<EChartsCoreOption>(() => {
  const days = rentalByDay.value
  return {
    grid: { left: 8, right: 12, top: 28, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: days.map((_, i) => String(i + 1)),
      axisLine: { lineStyle: { color: axisColor.value } },
      axisTick: { show: false },
      axisLabel: { color: labelColor.value, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: splitColor.value, type: 'solid' as const } },
      axisLabel: { color: labelColor.value, fontSize: 11 },
    },
    series: [{
      name: tx('rental.dashboard.rentalsByDay', 'Rentals'),
      type: 'bar',
      data: days,
      itemStyle: { color: BRAND, borderRadius: [3, 3, 0, 0] },
      barMaxWidth: 18,
    }],
  }
})

const rentalsEmpty = computed(() => !rentalByDay.value.some(count => count > 0))

function exportRentalsByDay() {
  const prefix = `${chartYear.value}-${chartMonth.value}`
  downloadCsv({
    filename: `rentals-by-day-${prefix}.csv`,
    fields: [{ label: 'Day', value: 'day' }, { label: 'Rentals', value: 'count' }],
    rows: rentalByDay.value.map((count, i) => ({ day: `${prefix}-${String(i + 1).padStart(2, '0')}`, count })),
  })
}

// ---- Income / Expense chart ----
const ieYears = chartYears

const ieBuckets = computed(() => {
  if (ieMonth.value === 'all') {
    const income = Array.from({ length: 12 }, () => 0)
    const expense = Array.from({ length: 12 }, () => 0)
    for (const row of payments.value) {
      const day = String(row.paidAt || '')
      if (day.slice(0, 4) === ieYear.value) income[Number(day.slice(5, 7)) - 1] += Number(row.amount || 0)
    }
    for (const row of expenses.value) {
      const day = String(row.date || '')
      if (day.slice(0, 4) === ieYear.value) expense[Number(day.slice(5, 7)) - 1] += Number(row.amount || 0)
    }
    return {
      labels: chartMonths.value.map(item => item.label),
      income,
      expense,
    }
  }
  const prefix = `${ieYear.value}-${ieMonth.value}`
  const days = new Date(Number(ieYear.value), Number(ieMonth.value), 0).getDate()
  const income = Array.from({ length: days }, () => 0)
  for (const row of payments.value) {
    const day = String(row.paidAt || '')
    if (day.slice(0, 7) === prefix) income[Number(day.slice(8, 10)) - 1] += Number(row.amount || 0)
  }
  for (const row of expenses.value) {
    const day = String(row.date || '')
    if (day.slice(0, 7) === prefix) expense[Number(day.slice(8, 10)) - 1] += Number(row.amount || 0)
  }
  return { labels: income.map((_, i) => String(i + 1)), income, expense }
})

const incomeExpenseOption = computed<EChartsCoreOption>(() => ({
  grid: { left: 8, right: 12, top: 28, bottom: 4, containLabel: true },
  tooltip: { trigger: 'axis' },
  legend: { top: 0, right: 0, textStyle: { color: labelColor.value, fontSize: 11 } },
  xAxis: {
    type: 'category',
    data: ieBuckets.value.labels,
    axisLine: { lineStyle: { color: axisColor.value } },
    axisTick: { show: false },
    axisLabel: { color: labelColor.value, fontSize: 11, hideOverlap: true },
  },
  yAxis: {
    type: 'value',
    splitLine: { lineStyle: { color: splitColor.value, type: 'solid' as const } },
    axisLabel: { color: labelColor.value, fontSize: 11 },
  },
  series: [
    { name: tx('rental.ui.income', 'Income'), type: 'bar', data: ieBuckets.value.income, itemStyle: { color: GOLD, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 14 },
    { name: tx('rental.ui.expense', 'Expense'), type: 'bar', data: ieBuckets.value.expense, itemStyle: { color: BRAND, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 14 },
  ],
}))

const ieEmpty = computed(() => !ieBuckets.value.income.some(v => v > 0) && !ieBuckets.value.expense.some(v => v > 0))

function exportIncomeExpense() {
  downloadCsv({
    filename: `income-expense-${ieYear.value}-${ieMonth.value}.csv`,
    fields: [
      { label: 'Period', value: 'period' },
      { label: 'Income', value: 'income' },
      { label: 'Expense', value: 'expense' },
    ],
    rows: ieBuckets.value.labels.map((label, i) => ({
      period: label,
      income: ieBuckets.value.income[i],
      expense: ieBuckets.value.expense[i],
    })),
  })
}

// ---- Active rental preview ----
const previewRows = computed(() => [...activeRentals.value, ...overdueRentals.value]
  .sort((a, b) => String(b.startDate || '').localeCompare(String(a.startDate || '')))
  .slice(0, 5))
</script>

<template>
  <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <div class="flex w-full min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-auto px-1.5 pt-1.5 pb-3">
      <DashboardAppKpiSection :title="tx('rental.dashboard.fleet', 'Fleet')" :cards="fleetCards" />
      <DashboardAppKpiSection :title="tx('rental.dashboard.rentalsFinance', 'Rentals & Finance')" :cards="rentalCards" />

      <div class="grid grid-cols-1 gap-2 xl:grid-cols-2">
        <!-- Rentals by day -->
        <div class="flex flex-col overflow-hidden rounded-lg border border-default bg-default">
          <div class="flex flex-wrap items-center justify-between gap-2 border-b border-default px-4 py-2.5">
            <p class="text-sm font-semibold">{{ tx('rental.dashboard.rentalsByDay', 'Rentals by Day') }}</p>
            <div class="flex items-center gap-2">
              <USelect v-model="chartYear" :items="chartYears" size="xs" class="w-20" />
              <USelect v-model="chartMonth" :items="chartMonths" size="xs" class="w-24" />
              <UButton size="xs" variant="ghost" icon="i-lucide-download" :disabled="rentalsEmpty" @click="exportRentalsByDay" />
            </div>
          </div>
          <div class="h-64 p-2">
            <div v-if="rentalsEmpty" class="grid h-full place-items-center text-sm text-muted">
              {{ tx('rental.ui.noActiveRentals', 'No rentals in this month') }}
            </div>
            <DashboardAppEChart v-else :option="rentalsByDayOption" aria-label="Rentals by day" />
          </div>
        </div>

        <!-- Income / Expense -->
        <div class="flex flex-col overflow-hidden rounded-lg border border-default bg-default">
          <div class="flex flex-wrap items-center justify-between gap-2 border-b border-default px-4 py-2.5">
            <p class="text-sm font-semibold">{{ tx('rental.dashboard.incomeExpenseChart', 'Income / Expense') }}</p>
            <div class="flex items-center gap-2">
              <USelect v-model="ieYear" :items="ieYears" size="xs" class="w-20" />
              <USelect v-model="ieMonth" :items="[{ label: tx('rental.ui.allMonths', 'All Months'), value: 'all' }, ...chartMonths]" size="xs" class="w-28" />
              <UButton size="xs" variant="ghost" icon="i-lucide-download" :disabled="ieEmpty" @click="exportIncomeExpense" />
            </div>
          </div>
          <div class="h-64 p-2">
            <div v-if="ieEmpty" class="grid h-full place-items-center text-sm text-muted">
              {{ tx('rental.ui.noActiveRentals', 'No data in this period') }}
            </div>
            <DashboardAppEChart v-else :option="incomeExpenseOption" aria-label="Income and expense" />
          </div>
        </div>
      </div>

      <!-- Active rental preview -->
      <div class="overflow-hidden rounded-lg border border-default bg-default">
        <div class="flex items-center justify-between border-b border-default px-4 py-2.5">
          <p class="text-sm font-semibold">{{ tx('rental.dashboard.activePreview', 'Active Rentals') }}</p>
          <NuxtLink to="/rentals" class="text-xs font-medium text-primary hover:underline">
            {{ tx('rental.ui.viewAll', 'See all') }}
          </NuxtLink>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-default text-start text-xs uppercase text-muted">
                <th class="px-4 py-2 text-start font-medium">{{ tx('rental.ui.rentalNo', 'Rental Number') }}</th>
                <th class="px-4 py-2 text-start font-medium">{{ tx('rental.ui.customer', 'Customer') }}</th>
                <th class="px-4 py-2 text-start font-medium">{{ tx('rental.ui.motorcycle', 'Motorcycle') }}</th>
                <th class="px-4 py-2 text-start font-medium">{{ tx('rental.ui.dueDate', 'Due') }}</th>
                <th class="px-4 py-2 text-end font-medium">{{ tx('rental.ui.outstanding', 'Outstanding') }}</th>
                <th class="px-4 py-2 text-start font-medium">{{ tx('rental.ui.status', 'Status') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in previewRows" :key="String(row.id)" class="border-b border-default/60 last:border-0">
                <td class="px-4 py-2 font-medium">
                  <NuxtLink :to="`/rentals/${row.id}`" class="hover:text-primary hover:underline">{{ row.rentalNo }}</NuxtLink>
                </td>
                <td class="px-4 py-2">{{ row.customer }}</td>
                <td class="px-4 py-2">{{ row.motorcycle }}</td>
                <td class="px-4 py-2 tabular-nums">{{ String(row.dueDate || '').slice(0, 10) }}</td>
                <td class="px-4 py-2 text-end tabular-nums">{{ money(row.outstanding) }}</td>
                <td class="px-4 py-2">
                  <UBadge :color="String(row.status) === 'Overdue' ? 'error' : 'primary'" variant="subtle" size="sm">
                    {{ row.status }}
                  </UBadge>
                </td>
              </tr>
              <tr v-if="!previewRows.length">
                <td colspan="6" class="px-4 py-6 text-center text-muted">{{ tx('rental.ui.noActiveRentals', 'No active rentals') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>
