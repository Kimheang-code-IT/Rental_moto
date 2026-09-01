<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type { EChartsCoreOption } from 'echarts/core'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { usePageSeo } from '~/composables/usePageSeo'
import { formatMoney } from '~/composables/module/useModule'
import { useFinanceRepository } from '~/repositories/index'
import type { DashboardSummary } from '~/repositories/contracts/entities'
import { downloadCsv } from '~/utils/export/csv'

/**
 * HollyWing Motor dashboard: four fleet KPIs, a rentals-by-day chart,
 * and a compact rental/finance summary list.
 */
const store = useAppDataStore()
const preferences = usePreferencesStore()
const { t, te } = useI18n()
const { setTitle, clear } = useAppHeader()

onBeforeUnmount(clear)
usePageSeo({ title: () => t('rental.nav.dashboard') })

watch(() => t('rental.nav.dashboard'), title => setTitle(title), { immediate: true })

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

const money = (value: unknown) => formatMoney(value, preferences.currency)

// HTTP mode: the dashboard is a server aggregate, not a localStorage loop.
const serverSummary = ref<DashboardSummary | null>(null)
const summaryLoading = ref(false)
const summaryError = ref<string | null>(null)

async function loadServerSummary() {
  if (!store.isHttpMode) return
  summaryLoading.value = true
  summaryError.value = null
  try {
    const { start, end } = chartRange.value
    serverSummary.value = await useFinanceRepository().dashboard(start, end)
  }
  catch (error: unknown) {
    summaryError.value = error instanceof Error ? error.message : String(error)
  }
  finally {
    summaryLoading.value = false
  }
}

const now = new Date()
const pad2 = (n: number) => String(n).padStart(2, '0')
function monthBounds(date = new Date()) {
  const y = date.getFullYear()
  const m = date.getMonth()
  const last = new Date(y, m + 1, 0).getDate()
  return {
    start: `${y}-${pad2(m + 1)}-01`,
    end: `${y}-${pad2(m + 1)}-${pad2(last)}`,
  }
}

const initialMonth = monthBounds(now)
const chartDateStart = ref(initialMonth.start)
const chartDateEnd = ref(initialMonth.end)

const motorcycles = computed(() => store.list('motorcycles'))
const rentals = computed(() => store.list('rentals'))
const customers = computed(() => store.list('rentalCustomers'))
const payments = computed(() => store.list('rentalPayments'))
const expenses = computed(() => store.list('rentalExpenses'))

onMounted(() => {
  if (store.isHttpMode) {
    void store.fetchList('motorcycles')
    void store.fetchList('rentals', { status: 'Active,Overdue' })
    void store.fetchList('rentalCustomers')
    void loadServerSummary()
  }
})

watch([chartDateStart, chartDateEnd], () => {
  void loadServerSummary()
})

const activeRentals = computed(() => rentals.value.filter(row => String(row.status) === 'Active'))
const overdueRentals = computed(() => rentals.value.filter(row => String(row.status) === 'Overdue'))

const monthIncome = computed(() => {
  if (serverSummary.value) return serverSummary.value.income
  return payments.value
    .filter(row => String(row.paidAt || '').slice(0, 7) === `${now.getFullYear()}-${pad2(now.getMonth() + 1)}`)
    .reduce((sum, row) => sum + Number(row.amount || 0), 0)
})
const monthExpense = computed(() => {
  if (serverSummary.value) return serverSummary.value.expense
  return expenses.value
    .filter(row => String(row.date || '').slice(0, 7) === `${now.getFullYear()}-${pad2(now.getMonth() + 1)}`)
    .reduce((sum, row) => sum + Number(row.amount || 0), 0)
})
const totalOutstanding = computed(() => {
  if (serverSummary.value) return serverSummary.value.outstanding
  return rentals.value
    .filter(row => ['Active', 'Overdue', 'Completed'].includes(String(row.status)))
    .reduce((sum, row) => sum + Number(row.outstanding || 0), 0)
})

interface KpiCard { key: string, title: string, value: string | number, to?: string, hint?: string }

const fleetCards = computed<KpiCard[]>(() => {
  const statusCount = (status: string) => serverSummary.value
    ? (serverSummary.value.motorcycleStatus[status] || 0)
    : motorcycles.value.filter(row => String(row.status) === status).length
  const total = serverSummary.value
    ? Object.values(serverSummary.value.motorcycleStatus).reduce((sum, n) => sum + Number(n || 0), 0)
    : motorcycles.value.length
  return [
    { key: 'total', title: tx('rental.dashboard.totalMotos', 'Total Motorcycles'), value: total, to: '/motorcycles' },
    { key: 'available', title: tx('rental.dashboard.available', 'Available'), value: statusCount('Available'), to: '/motorcycles?status=Available' },
    { key: 'progressing', title: tx('rental.dashboard.progressing', 'Progressing'), value: statusCount('Progressing'), to: '/motorcycles?status=Progressing' },
    { key: 'maintenance', title: tx('rental.dashboard.maintenance', 'Maintenance'), value: statusCount('Maintenance'), to: '/motorcycles?status=Maintenance' },
  ]
})

const rentalSummary = computed<KpiCard[]>(() => [
  {
    key: 'active',
    title: tx('rental.dashboard.activeRentals', 'Active Rentals'),
    value: serverSummary.value ? serverSummary.value.rentalsActive : activeRentals.value.length,
    to: '/rentals',
  },
  {
    key: 'overdue',
    title: tx('rental.dashboard.overdueRentals', 'Overdue Rentals'),
    value: serverSummary.value ? serverSummary.value.rentalsOverdue : overdueRentals.value.length,
    to: '/rentals?status=Overdue',
  },
  { key: 'customers', title: tx('rental.dashboard.totalCustomers', 'Total Customers'), value: customers.value.length, to: '/customers' },
  { key: 'income', title: tx('rental.dashboard.incomeMonth', 'Income This Month'), value: money(monthIncome.value), to: '/income-expense' },
  { key: 'expense', title: tx('rental.dashboard.expenseMonth', 'Expense This Month'), value: money(monthExpense.value), to: '/income-expense' },
  { key: 'outstanding', title: tx('rental.dashboard.outstanding', 'Outstanding'), value: money(totalOutstanding.value), to: '/income-expense' },
])

// ---- Rentals-by-day chart (date-range filter) ----
const chartRange = computed(() => {
  const fallback = monthBounds(now)
  let start = (chartDateStart.value || fallback.start).slice(0, 10)
  let end = (chartDateEnd.value || fallback.end).slice(0, 10)
  if (start > end) [start, end] = [end, start]
  return { start, end }
})

function eachDay(start: string, end: string) {
  const days: string[] = []
  const cursor = new Date(`${start}T00:00:00`)
  const last = new Date(`${end}T00:00:00`)
  if (!Number.isFinite(cursor.getTime()) || !Number.isFinite(last.getTime())) return days
  while (cursor <= last) {
    days.push(`${cursor.getFullYear()}-${pad2(cursor.getMonth() + 1)}-${pad2(cursor.getDate())}`)
    cursor.setDate(cursor.getDate() + 1)
  }
  return days
}

const rentalByDay = computed(() => {
  if (serverSummary.value?.rentalsByDay?.length) {
    return serverSummary.value.rentalsByDay.map(row => ({ day: String(row.date), count: Number(row.count || 0) }))
  }
  const days = eachDay(chartRange.value.start, chartRange.value.end)
  const counts = Object.fromEntries(days.map(day => [day, 0])) as Record<string, number>
  for (const row of rentals.value) {
    const day = String(row.startDate || '').slice(0, 10)
    if (day in counts) counts[day] = (counts[day] ?? 0) + 1
  }
  return days.map(day => ({ day, count: counts[day] ?? 0 }))
})

const dark = computed(() => useColorMode().value === 'dark')
const axisColor = computed(() => (dark.value ? '#3f3f46' : '#e4e4e7'))
const labelColor = computed(() => (dark.value ? '#a1a1aa' : '#71717a'))
const splitColor = computed(() => (dark.value ? 'rgba(255,255,255,0.08)' : 'rgba(24,24,27,0.07)'))
const BRAND = '#e8472a'

const rentalsByDayOption = computed<EChartsCoreOption>(() => {
  const rows = rentalByDay.value
  return {
    grid: { left: 8, right: 12, top: 28, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: rows.map(row => row.day.slice(8, 10)),
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
      data: rows.map(row => row.count),
      itemStyle: { color: BRAND, borderRadius: [3, 3, 0, 0] },
      barMaxWidth: 18,
    }],
  }
})

const rentalsEmpty = computed(() => !rentalByDay.value.some(row => row.count > 0))

function exportRentalsByDay() {
  if (rentalsEmpty.value) return
  const { start, end } = chartRange.value
  downloadCsv({
    filename: `rentals-by-day-${start}_${end}.csv`,
    fields: [{ label: 'Day', value: 'day' }, { label: 'Rentals', value: 'count' }],
    rows: rentalByDay.value,
  })
}

const chartMoreItems = computed<DropdownMenuItem[][]>(() => [[
  {
    label: tx('rental.ui.export', 'Export'),
    icon: 'i-lucide-download',
    disabled: rentalsEmpty.value,
    onSelect: exportRentalsByDay,
  },
]])
</script>

<template>
  <div class="flex h-full min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <div class="flex w-full min-h-0 min-w-0 flex-1 flex-col gap-2 overflow-y-auto px-1.5 pt-1.5 pb-3">
      <DashboardAppKpiSection :cards="fleetCards" />

      <!-- Fills remaining viewport height; stacks on small screens, side-by-side on xl+ -->
      <div class="grid min-h-72 flex-1 grid-cols-1 grid-rows-2 gap-2 xl:min-h-0 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)] xl:grid-rows-1">
        <!-- Rentals by day -->
        <div class="flex min-h-0 flex-col overflow-hidden rounded-lg border border-default bg-default">
          <div class="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-default px-4 py-2.5">
            <p class="text-sm font-semibold">{{ tx('rental.dashboard.rentalsByDay', 'Rentals by Day') }}</p>
            <div class="flex items-center gap-1.5">
              <CommonAppDateRangeFilter
                v-model:start="chartDateStart"
                v-model:end="chartDateEnd"
                granularity="day"
                size="xs"
                :label="tx('rental.ui.date', 'Date')"
              />
              <UDropdownMenu :items="chartMoreItems" :content="{ align: 'end' }">
                <UButton
                  icon="i-lucide-ellipsis"
                  color="neutral"
                  variant="ghost"
                  size="xs"
                  square
                  :aria-label="tx('app.ui.actions', 'Actions')"
                />
              </UDropdownMenu>
            </div>
          </div>
          <div class="min-h-0 flex-1 p-2">
            <div v-if="rentalsEmpty" class="grid h-full place-items-center text-sm text-muted">
              {{ tx('rental.dashboard.noRentalsInRange', 'No rentals in this period') }}
            </div>
            <DashboardAppEChart v-else :option="rentalsByDayOption" aria-label="Rentals by day" />
          </div>
        </div>

        <!-- Rental and finance summaries -->
        <div class="flex min-h-0 flex-col overflow-hidden rounded-lg border border-default bg-default">
          <div class="shrink-0 border-b border-default px-4 py-2.5">
            <p class="text-sm font-semibold">{{ tx('rental.dashboard.rentalsFinance', 'Rentals & Finance') }}</p>
          </div>
          <div class="flex min-h-0 flex-1 flex-col overflow-y-auto px-4">
            <NuxtLink
              v-for="item in rentalSummary"
              :key="item.key"
              :to="item.to"
              class="group flex min-h-10 flex-1 items-center justify-between gap-4 border-b border-default/70 py-2.5 last:border-0"
            >
              <span class="text-sm text-muted transition-colors group-hover:text-highlighted">{{ item.title }}</span>
              <span class="flex items-center gap-1.5 text-sm font-semibold tabular-nums text-highlighted">
                {{ item.value }}
                <UIcon name="i-lucide-chevron-right" class="size-3.5 text-dimmed" />
              </span>
            </NuxtLink>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
