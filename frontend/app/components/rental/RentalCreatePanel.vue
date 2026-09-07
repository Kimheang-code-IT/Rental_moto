<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type { ExportFieldOption, ExportRequest } from '~/types/rental/export'
import { useConfirm } from '~/composables/common/useConfirm'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { usePageSeo } from '~/composables/usePageSeo'
import { formatMoney, statusColor, statusLabel } from '~/composables/module/useModule'
import { PAYMENT_METHODS, RENTAL_IDENTITY_TYPES } from '~/config/rental-options'
import { useCreatableOptionList } from '~/composables/rental/useCreatableOptionList'
import { downloadCsv } from '~/utils/export/csv'
import {
  addDaysToDateTime,
  appliedUnitPrice,
  daysBetween,
  detectRatePlan,
  documentTotals,
  applySharedDurationToLines,
  dueDateFromRatePlan,
  latestLineDueDate,
  lineAmounts,
  lineCharge,
  lineDueFromPlan,
  rentalRateType,
  todayDateTimeLocal,
  type RentalRatePlan,
} from '~/utils/rental/pricing'
import { toIsoZoned } from '~/utils/api/datetime'
import { useRentalCommands } from '~/repositories/index'

const props = withDefaults(defineProps<{
  mode?: 'create' | 'detail'
  rentalId?: string
}>(), {
  mode: 'create',
})

const emit = defineEmits<{ cancel: [] }>()

const { t, te } = useI18n()
const auth = useAuthStore()
const store = useAppDataStore()
const preferences = usePreferencesStore()
const { confirm } = useConfirm()
const rentalCommands = useRentalCommands()
const toast = useToast()
const { setBreadcrumbs, setBadges, clear: clearHeader } = useAppHeader()

const isDetail = computed(() => props.mode === 'detail')
const detailRental = computed(() =>
  props.rentalId ? store.get('rentals', props.rentalId) : null,
)
const isEditable = computed(() =>
  isDetail.value
  && ['Active', 'Overdue'].includes(rentalStatus.value)
  && auth.canAccessPage('rental.rentals.edit'),
)
const isFormReadOnly = computed(() => isDetail.value && !isEditable.value)


function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

function help(key: string, fallback: string) {
  if (te(`rental.fieldHelp.${key}`)) return String(t(`rental.fieldHelp.${key}`))
  if (te(`core.fieldHelp.${key}`)) return String(t(`core.fieldHelp.${key}`))
  return fallback
}

interface RentalLine {
  key: string
  model: string
  motorcycleId: string
  /** Per-line package; independent from other motorcycle rows. */
  ratePlan: RentalRatePlan
  days: number
  unitPrice: number
  /** Per-motorcycle discount (currency amount). */
  discount: number
}

const customers = computed(() => store.list('rentalCustomers').filter(row => String(row.status || 'Active') === 'Active'))
const availableMotorcycles = computed(() => store.list('motorcycles').filter(row => String(row.status) === 'Available'))

onMounted(() => {
  if (store.isHttpMode) {
    void store.fetchList('rentalCustomers', { status: 'Active' })
    void store.fetchList('motorcycles')
  }
})

const customerId = ref('')
const startDate = ref(todayDateTimeLocal())
const dueDate = ref(addDaysToDateTime(todayDateTimeLocal(), 1))
const depositDate = ref(todayDateTimeLocal().slice(0, 10))
const deposit = ref(0)
const headerDiscount = ref(0)
const taxPercent = ref(0)
const paymentMethodOptions = useCreatableOptionList(PAYMENT_METHODS)
const paymentMethod = ref<string>(PAYMENT_METHODS[0])
const paidAmount = ref(0)
const existingPaid = ref(0)
const outstandingBalance = ref(0)
const rentalNo = ref('')
const rentalStatus = ref('Active')
const currency = ref(preferences.currency)
const lateFee = ref(0)
const additionalCharges = ref(0)
const saving = ref(false)
const syncingDates = ref(false)
const notFound = ref(false)
const invoiceRental = ref<Record<string, unknown> | null>(null)
const chargesReviewOpen = ref(false)
const listNavigationDirection = ref<'previous' | 'next' | null>(null)

let lineSeq = 1
function newLine(): RentalLine {
  return {
    key: `line-${lineSeq++}`,
    model: '',
    motorcycleId: '',
    ratePlan: '1d',
    days: 1,
    unitPrice: 0,
    discount: 0,
  }
}
const lines = ref<RentalLine[]>([newLine()])

/** Due datetime for one line from shared start + that line's plan/days. */
function lineDueDate(line: RentalLine) {
  return lineDueFromPlan(startDate.value, line)
}

function daysForRatePlan(plan: RentalRatePlan, fallbackDays = 1) {
  if (plan === '1d') return 1
  if (plan === '3d') return 3
  if (plan === '1w') return 7
  if (plan === '1m') {
    if (!startDate.value) return Math.max(1, fallbackDays)
    const due = dueDateFromRatePlan(startDate.value, '1m', fallbackDays)
    return Math.max(1, daysBetween(startDate.value, due) || fallbackDays)
  }
  return Math.max(1, Math.floor(Number(fallbackDays) || 1))
}

function repriceLine(line: RentalLine) {
  const due = lineDueDate(line)
  const moto = motoById(line.motorcycleId)
  line.unitPrice = moto
    ? appliedUnitPrice(moto, line.days, startDate.value, due)
    : line.unitPrice
  const gross = moto ? lineCharge(moto, line.days, startDate.value, due) : 0
  if (line.discount > gross) line.discount = gross
}

/** Header Due mirrors the latest line due; does not rewrite other lines. */
function refreshHeaderDueFromLines() {
  if (!startDate.value || !lines.value.length) return
  const latest = latestLineDueDate(startDate.value, lines.value)
  if (!latest || latest === dueDate.value) return
  syncingDates.value = true
  dueDate.value = latest
  void nextTick(() => {
    syncingDates.value = false
  })
}

const selectedCustomer = computed(() =>
  store.list('rentalCustomers').find(row => String(row.id) === customerId.value) || null,
)

const customerNameItems = computed(() => customers.value.map(row => ({
  label: String(row.fullName || ''),
  value: String(row.id),
})))

const customerPassportItems = computed(() => customers.value.map(row => ({
  label: String(row.identityNumber || ''),
  value: String(row.id),
})))

const detailCustomerNameItems = computed(() => {
  if (!selectedCustomer.value) return customerNameItems.value
  const id = String(selectedCustomer.value.id)
  if (customerNameItems.value.some(item => item.value === id)) return customerNameItems.value
  return [{ label: String(selectedCustomer.value.fullName || ''), value: id }, ...customerNameItems.value]
})

const detailCustomerPassportItems = computed(() => {
  if (!selectedCustomer.value) return customerPassportItems.value
  const id = String(selectedCustomer.value.id)
  if (customerPassportItems.value.some(item => item.value === id)) return customerPassportItems.value
  return [{ label: String(selectedCustomer.value.identityNumber || ''), value: id }, ...customerPassportItems.value]
})

const modelItems = computed(() => {
  const models = [...new Set([
    ...availableMotorcycles.value.map(row => String(row.model || '')),
    ...lines.value.map(row => row.model),
  ].filter(Boolean))]
  return models.sort().map(model => ({ label: model, value: model }))
})

function motoById(id: string) {
  return availableMotorcycles.value.find(row => String(row.id) === id)
    || store.list('motorcycles').find(row => String(row.id) === id)
    || null
}

function plateItemsFor(line: RentalLine) {
  if (!line.model) return []
  const taken = new Set(lines.value.filter(row => row.key !== line.key && row.motorcycleId).map(row => row.motorcycleId))
  const available = availableMotorcycles.value
    .filter(row => String(row.model) === line.model)
    .filter(row => !taken.has(String(row.id)) || String(row.id) === line.motorcycleId)
    .map(row => ({ label: String(row.plate || ''), value: String(row.id) }))

  if (line.motorcycleId && !available.some(item => item.value === line.motorcycleId)) {
    const moto = motoById(line.motorcycleId)
    if (moto) available.unshift({ label: String(moto.plate || line.motorcycleId), value: String(moto.id) })
  }
  return available
}

function onSelectModel(line: RentalLine, model: string | number) {
  if (isFormReadOnly.value) return
  line.model = String(model || '')
  line.motorcycleId = ''
  line.unitPrice = 0
  const first = availableMotorcycles.value.find(row => String(row.model) === line.model)
  if (first) {
    repriceLine(line)
  }
}

function onSelectPlate(line: RentalLine, motorcycleId: string | number) {
  if (isFormReadOnly.value) return
  line.motorcycleId = String(motorcycleId || '')
  const moto = motoById(line.motorcycleId)
  if (!moto) return
  line.model = String(moto.model || line.model)
  if (!line.days) line.days = daysForRatePlan(line.ratePlan, daysBetween(startDate.value, dueDate.value) || 1)
  repriceLine(line)
}

const lineComputed = computed(() => lines.value.map(line => {
  const moto = motoById(line.motorcycleId)
  const due = lineDueDate(line)
  const priced = moto
    ? lineAmounts(moto, line.days, line.discount, startDate.value, due)
    : { charge: 0, discount: 0, lineTotal: 0 }
  return {
    line,
    moto,
    due,
    gross: priced.charge,
    discount: priced.discount,
    amount: priced.lineTotal,
  }
}))

const totals = computed(() => {
  const base = documentTotals({
    lineTotals: lineComputed.value.map(row => row.amount),
    discount: headerDiscount.value,
    taxPercent: taxPercent.value,
  })
  if (!isDetail.value || isEditable.value) return base
  const extras = Math.max(0, Number(lateFee.value) || 0) + Math.max(0, Number(additionalCharges.value) || 0)
  return {
    ...base,
    total: Number((base.total + extras).toFixed(2)),
  }
})

const depositError = computed(() => {
  if (deposit.value > totals.value.subtotal + 0.001) {
    return tx('rental.ui.depositExceedsSubtotal', 'Deposit cannot exceed subtotal.')
  }
  return undefined
})

const paidError = computed(() => {
  if (isDetail.value) return undefined
  if (paidAmount.value > totals.value.total + 0.001) {
    return tx('rental.ui.paidExceedsTotal', 'Paid now cannot exceed total.')
  }
  return undefined
})

const outstandingPreview = computed(() => {
  if (isFormReadOnly.value) return Math.max(0, Number(outstandingBalance.value) || 0)
  if (isEditable.value) return Math.max(totals.value.total - existingPaid.value, 0)
  return Math.max(totals.value.total - paidAmount.value, 0)
})

const rentalSiblingIds = computed(() => store.list('rentals').map(row => String(row.id)))
const rentalSiblingIndex = computed(() => rentalSiblingIds.value.indexOf(String(props.rentalId || '')))
const canNavigatePrevious = computed(() => isDetail.value && rentalSiblingIndex.value > 0)
const canNavigateNext = computed(() =>
  isDetail.value
  && rentalSiblingIndex.value >= 0
  && rentalSiblingIndex.value < rentalSiblingIds.value.length - 1,
)

async function navigateRental(direction: 'previous' | 'next') {
  const offset = direction === 'previous' ? -1 : 1
  const id = rentalSiblingIds.value[rentalSiblingIndex.value + offset]
  if (!id) return

  listNavigationDirection.value = direction
  try {
    await navigateTo(`/rentals/${id}`)
  }
  finally {
    listNavigationDirection.value = null
  }
}

const createCustomerButtons = computed(() => {
  if (isDetail.value) return []
  return [{
    label: tx('rental.ui.addNewCustomer', 'Create customer'),
    icon: 'i-lucide-user-plus',
  }]
})

watch(() => totals.value.subtotal, (subtotal) => {
  if (isFormReadOnly.value) return
  if (deposit.value > subtotal) deposit.value = subtotal
})

watch(() => totals.value.total, (total) => {
  if (isFormReadOnly.value) return
  if (!isDetail.value && paidAmount.value > total) paidAmount.value = total
})

const ratePlanItems = computed(() => [
  { label: tx('rental.ui.ratePlan1Day', '1 day'), value: '1d' },
  { label: tx('rental.ui.ratePlan3Days', '3 days'), value: '3d' },
  { label: tx('rental.ui.ratePlan1Week', '1 week'), value: '1w' },
  { label: tx('rental.ui.ratePlan1Month', '1 month'), value: '1m' },
  { label: tx('rental.ui.ratePlanCustom', 'Custom dates'), value: 'custom' },
])

/** Header Start changed: keep each line's own plan/days, only reprice. */
watch(startDate, () => {
  if (isFormReadOnly.value || syncingDates.value || !startDate.value) return
  for (const line of lines.value) repriceLine(line)
  refreshHeaderDueFromLines()
})

/** Staff edited the header Due field: apply that duration to every motorcycle line. */
function onHeaderDueChange(value: string) {
  if (isFormReadOnly.value || syncingDates.value) return
  dueDate.value = String(value || '')
  if (!startDate.value || !dueDate.value) return
  const nextLines = applySharedDurationToLines(lines.value, startDate.value, dueDate.value)
  nextLines.forEach((row, index) => {
    const line = lines.value[index]
    if (!line) return
    line.days = row.days
    line.ratePlan = row.ratePlan
    repriceLine(line)
  })
}

function onRatePlanChange(line: RentalLine, plan: string) {
  if (isFormReadOnly.value || !startDate.value) return
  const next = String(plan || '') as RentalRatePlan
  line.ratePlan = next
  if (next !== 'custom') {
    line.days = daysForRatePlan(next, line.days)
  }
  repriceLine(line)
  refreshHeaderDueFromLines()
}

function onLineDaysChange(line: RentalLine, daysValue?: number | null) {
  if (isFormReadOnly.value || !startDate.value) return
  const days = Math.max(1, Math.floor(Number(daysValue ?? line.days) || 1))
  line.days = days
  // Manual day edits stay on Custom unless they exactly match a package.
  const due = addDaysToDateTime(startDate.value, days)
  const detected = detectRatePlan(startDate.value, due, days)
  line.ratePlan = detected === 'custom' ? 'custom' : detected
  repriceLine(line)
  refreshHeaderDueFromLines()
}

function addLine() {
  if (isFormReadOnly.value) return
  const row = newLine()
  // New row starts from the first line's duration, but keeps its own ratePlan state.
  const template = lines.value[0]
  if (template) {
    row.days = template.days
    row.ratePlan = template.ratePlan
  } else {
    row.days = daysBetween(startDate.value, dueDate.value) || 1
    row.ratePlan = detectRatePlan(startDate.value, dueDate.value, row.days)
  }
  lines.value.push(row)
}

function removeLine(key: string) {
  if (isFormReadOnly.value || lines.value.length <= 1) return
  lines.value = lines.value.filter(row => row.key !== key)
  refreshHeaderDueFromLines()
}

const canEditRental = computed(() => Boolean(
  isEditable.value
  && customerId.value
  && startDate.value
  && dueDate.value
  && lines.value.every(line => line.motorcycleId && line.days > 0 && line.unitPrice > 0)
  && totals.value.total >= 0
  && deposit.value <= totals.value.subtotal + 0.001,
))

const canCreate = computed(() => Boolean(
  !isDetail.value
  && customerId.value
  && startDate.value
  && dueDate.value
  && lines.value.every(line => line.motorcycleId && line.days > 0 && line.unitPrice > 0)
  && totals.value.total >= 0
  && deposit.value <= totals.value.subtotal + 0.001
  && paidAmount.value <= totals.value.total + 0.001,
))

const customerModalOpen = ref(false)
const savingCustomer = ref(false)
const newCustomer = reactive({
  fullName: '',
  phone: '',
  company: '',
  identityType: RENTAL_IDENTITY_TYPES[0] as (typeof RENTAL_IDENTITY_TYPES)[number],
  identityNumber: '',
  address: '',
})

const canSaveCustomer = computed(() => Boolean(
  newCustomer.fullName.trim()
  && newCustomer.phone.trim()
  && newCustomer.identityNumber.trim(),
))

function openCustomerModal() {
  newCustomer.fullName = ''
  newCustomer.phone = ''
  newCustomer.company = ''
  newCustomer.identityType = RENTAL_IDENTITY_TYPES[0]
  newCustomer.identityNumber = ''
  newCustomer.address = ''
  customerModalOpen.value = true
}

async function saveNewCustomer() {
  if (!canSaveCustomer.value) return
  const ok = await confirm({
    kind: 'submit',
    titleKey: 'rental.ui.confirmAddCustomer',
    description: newCustomer.fullName.trim(),
    confirmLabelKey: 'rental.ui.saveCustomer',
  })
  if (!ok) return
  savingCustomer.value = true
  try {
    const created = await store.createRemote('rentalCustomers', {
      fullName: newCustomer.fullName.trim(),
      phone: newCustomer.phone.trim(),
      company: newCustomer.company.trim(),
      identityType: newCustomer.identityType,
      identityNumber: newCustomer.identityNumber.trim(),
      email: '',
      address: newCustomer.address.trim(),
      status: 'Active',
    })
    customerId.value = String(created.id)
    customerModalOpen.value = false
    toast.add({ title: tx('rental.ui.customerCreated', 'Customer added'), color: 'success' })
  }
  catch (error: unknown) {
    toast.add({
      title: tx('rental.ui.customerCreateFailed', 'Could not save customer'),
      description: error instanceof Error ? error.message : String(error),
      color: 'error',
    })
  }
  finally {
    savingCustomer.value = false
  }
}

function loadDetail() {
  if (!isDetail.value || !props.rentalId) return
  const hydrateFromServer = () => {
    if (!store.isHttpMode) return
    void store.fetchOne('rentals', props.rentalId!).then(() => {
      if (store.get('rentals', props.rentalId!)) {
        notFound.value = false
        hydrateDetail()
      }
    })
  }
  const found = store.get('rentals', props.rentalId)
  if (!found && store.isHttpMode) {
    notFound.value = false
    hydrateFromServer()
    void store.fetchList('rentalPayments', { rentalId: props.rentalId })
    void store.fetchList('rentalCharges', { rentalId: props.rentalId })
    return
  }
  hydrateDetail()
  void store.fetchList('rentalPayments', { rentalId: props.rentalId })
  void store.fetchList('rentalCharges', { rentalId: props.rentalId })
}

function hydrateDetail() {
  if (!isDetail.value || !props.rentalId) return
  const found = store.get('rentals', props.rentalId)
  notFound.value = !found
  if (!found) return

  rentalNo.value = String(found.rentalNo || '')
  rentalStatus.value = String(found.status || 'Active')
  customerId.value = String(found.customerId || '')
  syncingDates.value = true
  startDate.value = String(found.startDate || '')
  dueDate.value = String(found.dueDate || '')
  depositDate.value = String(found.depositDate || String(found.startDate || '').slice(0, 10))
  deposit.value = Number(found.deposit || 0)
  taxPercent.value = Number(found.taxPercent || 0)
  existingPaid.value = Number(found.paid || 0)
  paidAmount.value = existingPaid.value
  outstandingBalance.value = Number(found.outstanding || 0)
  currency.value = String(found.currency || preferences.currency)
  lateFee.value = Number(found.lateFee || 0)
  additionalCharges.value = Number(found.additionalCharges || 0)

  const payments = store.list('rentalPayments')
    .filter(row => String(row.rentalId) === String(found.id))
    .sort((a, b) => String(b.paidAt || '').localeCompare(String(a.paidAt || '')))
  const lastMethod = String(payments[0]?.paymentMethod || '')
  if (lastMethod) {
    paymentMethod.value = lastMethod
    if (!paymentMethodOptions.items.value.includes(lastMethod)) {
      paymentMethodOptions.items.value.push(lastMethod)
    }
  }

  const savedLines = Array.isArray(found.lines) ? found.lines as Array<Record<string, unknown>> : []
  if (savedLines.length) {
    lines.value = savedLines.map((row) => {
      const start = String(row.startDate || found.startDate || '')
      const due = String(row.dueDate || found.dueDate || '')
      const days = Math.max(1, Number(row.durationDays || daysBetween(start, due) || 1))
      return {
        key: `line-${lineSeq++}`,
        model: String(row.motorcycle || ''),
        motorcycleId: String(row.motorcycleId || ''),
        days,
        ratePlan: detectRatePlan(start, due, days),
        unitPrice: Number(row.rateAmount || 0),
        discount: Math.max(0, Number(row.discount || 0)),
      }
    })
  }
  else {
    lines.value = [{
      key: `line-${lineSeq++}`,
      model: String(found.motorcycle || ''),
      motorcycleId: String(found.motorcycleId || ''),
      days: Math.max(1, Number(found.durationDays || daysBetween(String(found.startDate || ''), String(found.dueDate || '')) || 1)),
      ratePlan: detectRatePlan(
        String(found.startDate || ''),
        String(found.dueDate || ''),
        Math.max(1, Number(found.durationDays || 1)),
      ),
      unitPrice: Number(found.rateAmount || 0),
      discount: Math.max(0, Number(found.discount || 0)),
    }]
  }
  for (const line of lines.value) repriceLine(line)
  // Detail stores discount on the rental line; keep header extra at 0 so totals do not double-count.
  headerDiscount.value = 0
  void nextTick(() => {
    refreshHeaderDueFromLines()
    syncingDates.value = false
  })
}

watch(
  [() => props.mode, () => props.rentalId, () => (props.rentalId ? store.get('rentals', props.rentalId) : null)],
  loadDetail,
  { immediate: true },
)

const rentalsListLabel = computed(() => tx('rental.pages.rentals', 'Rentals'))
const headerTitle = computed(() => {
  if (isDetail.value) {
    if (notFound.value) return tx('rental.ui.rentalNotFound', 'Rental not found')
    return rentalNo.value || tx('rental.ui.rentalNo', 'Rental Number')
  }
  return tx('rental.ui.newRental', 'New Rental')
})

watch([headerTitle, isDetail, rentalNo, rentalStatus, notFound, rentalsListLabel], () => {
  setBreadcrumbs([
    { label: rentalsListLabel.value, to: '/rentals' },
    { label: headerTitle.value },
  ])
  if (isDetail.value && rentalStatus.value && !notFound.value) {
    setBadges([{ label: statusLabel(rentalStatus.value, t, te), color: statusColor(rentalStatus.value) }])
  }
  else {
    setBadges([])
  }
}, { immediate: true })

onBeforeUnmount(clearHeader)
usePageSeo({ title: () => headerTitle.value })

function buildInvoicePayload(): Record<string, unknown> | null {
  if (isDetail.value && props.rentalId) {
    const found = store.get('rentals', props.rentalId)
    return found ? { ...found } : null
  }
  if (!selectedCustomer.value || !lineComputed.value.some(row => row.moto || row.line.motorcycleId)) return null
  const first = lineComputed.value[0]
  const moto = first?.moto
  const invoiceLines = lineComputed.value
    .filter(row => row.moto || row.line.motorcycleId)
    .map(row => ({
      motorcycle: row.line.model || row.moto?.model || '',
      plate: row.moto?.plate || '',
      days: row.line.days,
      unitPrice: row.gross || row.line.unitPrice,
      discount: row.discount,
      amount: row.amount,
    }))
  const lineDiscountTotal = invoiceLines.reduce((sum, row) => sum + Number(row.discount || 0), 0)
  return {
    id: 'draft',
    rentalNo: 'DRAFT',
    invoiceNo: 'INV-DRAFT',
    customerId: selectedCustomer.value.id,
    customer: selectedCustomer.value.fullName,
    phone: selectedCustomer.value.phone,
    motorcycleId: first?.line.motorcycleId || '',
    motorcycle: first?.line.model || moto?.model || '',
    plate: moto?.plate || '',
    startDate: startDate.value,
    dueDate: dueDate.value,
    durationDays: first?.line.days || 1,
    rateType: rentalRateType(first?.line.days || 1, startDate.value, dueDate.value),
    rateAmount: first?.gross || first?.line.unitPrice || 0,
    deposit: deposit.value,
    depositDate: depositDate.value,
    discount: Number((lineDiscountTotal + headerDiscount.value).toFixed(2)),
    taxPercent: taxPercent.value,
    tax: totals.value.tax,
    currency: moto?.currency || preferences.currency,
    rentalCharge: first?.amount || totals.value.subtotal,
    lateFee: 0,
    additionalCharges: 0,
    totalDue: totals.value.total,
    paid: paidAmount.value,
    outstanding: outstandingPreview.value,
    paymentMethod: paymentMethod.value,
    status: 'Draft',
    invoiceLines,
  }
}

const canPrintInvoice = computed(() => auth.canAccessPage('rental.rentals.print'))

function printInvoice() {
  if (!canPrintInvoice.value) return
  const payload = buildInvoicePayload()
  if (!payload) {
    toast.add({
      title: tx('rental.ui.printNeedsData', 'Select customer and motorcycle before printing.'),
      color: 'warning',
    })
    return
  }
  invoiceRental.value = payload
}

const headerMoreItems = computed<DropdownMenuItem[][]>(() => {
  if (!canPrintInvoice.value) return []
  return [[
    {
      label: tx('rental.ui.printInvoice', 'Print Invoice'),
      icon: 'i-lucide-printer',
      onSelect: printInvoice,
    },
  ]]
})

const rentalExportFields = computed<ExportFieldOption[]>(() => [
  { label: tx('rental.ui.rentalNo', 'Rental Number'), value: 'rentalNo' },
  { label: tx('rental.ui.customer', 'Customer'), value: 'customer' },
  { label: tx('rental.ui.phone', 'Phone'), value: 'phone' },
  { label: tx('rental.ui.motorcycle', 'Motorcycle'), value: 'motorcycle' },
  { label: tx('rental.ui.plate', 'Plate'), value: 'plate' },
  { label: tx('rental.ui.startDate', 'Start Date'), value: 'startDate' },
  { label: tx('rental.ui.returnDate', 'Return Date'), value: 'dueDate' },
  { label: tx('rental.ui.paymentMethod', 'Payment Method'), value: 'paymentMethod' },
  { label: tx('rental.ui.total', 'Total'), value: 'totalDue' },
  { label: tx('rental.ui.paid', 'Paid'), value: 'paid' },
  { label: tx('rental.ui.outstanding', 'Outstanding'), value: 'outstanding' },
  { label: tx('rental.ui.status', 'Status'), value: 'status' },
])

function exportRental(request: ExportRequest) {
  const payload = buildInvoicePayload()
  if (!payload) return
  const selected = new Set(request.fieldCodes)
  downloadCsv({
    filename: `${String(payload.rentalNo || 'rental')}.csv`,
    fields: rentalExportFields.value.filter(field => selected.has(field.value)),
    rows: [payload],
  })
}

function onCreatePaymentMethod(item: string) {
  const value = paymentMethodOptions.onCreate(item)
  if (value) paymentMethod.value = value
}

async function createRental() {
  if (!canCreate.value || !selectedCustomer.value) return
  const validLines = lineComputed.value.filter(row => row.moto)
  if (!validLines.length) return

  const ok = await confirm({
    kind: 'submit',
    title: tx('rental.ui.confirmCreate', 'Create this rental?'),
    description: `${selectedCustomer.value.fullName} · ${validLines.length} ${tx('rental.ui.motorcycles', 'motorcycles')} · ${tx('rental.ui.total', 'Total')}: ${formatMoney(totals.value.total, preferences.currency)}`,
    confirmLabel: tx('rental.ui.createRental', 'Create Rental'),
  })
  if (!ok) return

  saving.value = true
  try {
    await rentalCommands.create({
        customerId: String(selectedCustomer.value.id),
        lines: validLines.map((row, index) => ({
          motorcycleId: String(row.line.motorcycleId),
          startDate: toIsoZoned(startDate.value)!,
          dueDate: toIsoZoned(row.due || lineDueDate(row.line))!,
          deposit: index === 0 ? Number(deposit.value || 0) : 0,
          discount: Number(row.line.discount || 0),
          note: null,
        })),
        discount: headerDiscount.value,
        taxPercent: taxPercent.value,
        paidAmount: paidAmount.value,
        paymentMethod: paymentMethod.value,
        currency: currency.value,
        note: null,
      })
      await store.fetchList('motorcycles')
      await store.fetchList('rentals', { status: 'Active,Overdue' })
      toast.add({ title: tx('rental.ui.rentalCreated', 'Rental created'), color: 'success' })
      await navigateTo('/rentals')
  }
  catch (error: unknown) {
    toast.add({
      title: tx('rental.ui.rentalCreateFailed', 'Could not create rental'),
      description: error instanceof Error ? error.message : String(error),
      color: 'error',
    })
  }
  finally {
    saving.value = false
  }
}

async function updateRental() {
  if (!canEditRental.value || !props.rentalId) return
  const validLines = lineComputed.value.filter(row => row.moto)
  if (!validLines.length) return

  const ok = await confirm({
    kind: 'update',
    title: tx('rental.ui.confirmUpdate', 'Update this rental?'),
    description: String(rentalNo.value || props.rentalId),
    confirmLabel: tx('core.confirm.update', 'Update'),
  })
  if (!ok) return

  saving.value = true
  try {
    await rentalCommands.update(String(props.rentalId), {
      customerId: customerId.value,
      startDate: toIsoZoned(startDate.value)!,
      dueDate: toIsoZoned(dueDate.value)!,
      deposit: deposit.value,
      discount: headerDiscount.value,
      taxPercent: taxPercent.value,
      note: null,
      lines: validLines.map((row, index) => ({
        motorcycleId: String(row.line.motorcycleId),
        startDate: toIsoZoned(startDate.value)!,
        dueDate: toIsoZoned(row.due || lineDueDate(row.line))!,
        deposit: index === 0 ? Number(deposit.value || 0) : 0,
        discount: Number(row.line.discount || 0),
        note: null,
      })),
    })
    await store.fetchOne('rentals', String(props.rentalId))
    await store.fetchList('motorcycles')
    toast.add({ title: tx('rental.ui.rentalUpdated', 'Rental updated'), color: 'success' })
    await navigateTo('/rentals')
  }
  catch (error: unknown) {
    toast.add({
      title: tx('rental.ui.rentalUpdateFailed', 'Could not update rental'),
      description: error instanceof Error ? error.message : String(error),
      color: 'error',
    })
  }
  finally {
    saving.value = false
  }
}

async function saveRental() {
  if (isEditable.value) await updateRental()
  else await createRental()
}

const money = (value: unknown) => formatMoney(value, currency.value || preferences.currency)
</script>

<template>
  <div class="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-default">
    <LayoutAppHeaderPageActions
      :allow-print-in-more="canPrintInvoice"
      :more-items="headerMoreItems"
      :export-fields="rentalExportFields"
      :show-list-nav="isDetail"
      list-to="/rentals"
      :can-navigate-previous="canNavigatePrevious"
      :can-navigate-next="canNavigateNext"
      :list-navigation-direction="listNavigationDirection"
      :show-save="(!isDetail && canCreate) || (isEditable && canEditRental)"
      :is-create="!isDetail"
      :saving="saving"
      :show-cancel="true"
      cancel-to="/rentals"
      :create-buttons="createCustomerButtons"
      @save="saveRental"
      @cancel="emit('cancel')"
      @create-button="openCustomerModal"
      @export="exportRental"
      @navigate-previous="navigateRental('previous')"
      @navigate-next="navigateRental('next')"
    />

    <div v-if="isDetail && notFound" class="grid flex-1 place-items-center p-8">
      <UEmpty
        variant="naked"
        icon="i-lucide-search-x"
        :title="tx('rental.ui.rentalNotFound', 'Rental not found')"
        :description="tx('rental.ui.rentalNotFoundHelp', 'This rental may have been removed.')"
      />
    </div>

    <div v-else class="min-h-0 flex-1 overflow-y-auto">
      <DocumentAppDocumentContentShell wide>
        <div class="flex flex-col gap-5 py-6">
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <UFormField
              :label="tx('rental.ui.fullName', 'Customer name')"
              :help="help('customerName', 'Select customer by name.')"
              required
            >
              <USelect
                v-model="customerId"
                :items="isDetail ? detailCustomerNameItems : customerNameItems"
                placeholder="—"
                size="md"
                class="w-full"
                :disabled="isFormReadOnly"
              />
            </UFormField>
            <UFormField
              :label="tx('app.modules.rentalCustomers.fields.identityNumber', 'Identity Number')"
              :help="help('customerPassport', 'Select customer by identity number.')"
              required
            >
              <USelect
                v-model="customerId"
                :items="isDetail ? detailCustomerPassportItems : customerPassportItems"
                placeholder="—"
                size="md"
                class="w-full"
                :disabled="isFormReadOnly"
              />
            </UFormField>
            <UFormField
              :label="tx('rental.ui.startDate', 'Start')"
              :help="help('startDate', 'Rental start date and time. Defaults to now.')"
              required
            >
              <CommonAppInputDate
                v-model="startDate"
                granularity="minute"
                required
                size="md"
                class="w-full"
                :disabled="isFormReadOnly"
              />
            </UFormField>
            <UFormField
              :label="tx('rental.ui.dueDate', 'Due')"
              :help="help('dueDate', 'Latest motorcycle return. Each line keeps its own package unless you edit this date.')"
              required
            >
              <CommonAppInputDate
                :model-value="dueDate"
                granularity="minute"
                required
                size="md"
                class="w-full"
                :disabled="isFormReadOnly"
                @update:model-value="onHeaderDueChange"
              />
            </UFormField>
            <UFormField
              :label="tx('rental.ui.depositDate', 'Deposit date')"
              :help="help('depositDate', 'Date the deposit was received.')"
            >
              <CommonAppInputDate
                v-model="depositDate"
                granularity="day"
                size="md"
                class="w-full"
                :disabled="isFormReadOnly"
              />
            </UFormField>
          </div>

          <div>
            <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p class="text-sm font-semibold text-highlighted">{{ tx('rental.ui.motorcycle', 'Motorcycle') }}</p>
              <UButton
                v-if="!isFormReadOnly"
                size="sm"
                variant="soft"
                icon="i-lucide-plus"
                :label="tx('rental.ui.addLine', 'Add motorcycle')"
                @click="addLine"
              />
            </div>

            <div class="overflow-x-auto">
              <table class="w-full min-w-3xl border-collapse text-sm">
                <thead>
                  <tr class="border-b border-default text-left text-xs uppercase tracking-wide text-muted">
                    <th class="px-2 py-2 font-medium">{{ tx('rental.ui.model', 'Motorcycle Model') }}</th>
                    <th class="px-2 py-2 font-medium">{{ tx('rental.ui.plate', 'Plate') }}</th>
                    <th class="px-2 py-2 font-medium">{{ tx('rental.ui.ratePlan', 'Rate') }}</th>
                    <th class="px-2 py-2 font-medium">{{ tx('rental.ui.daysCount', 'Days') }}</th>
                    <th class="px-2 py-2 font-medium">{{ tx('rental.ui.unitPrice', 'Rate amount') }}</th>
                    <th class="px-2 py-2 font-medium">{{ tx('rental.ui.discount', 'Discount') }}</th>
                    <th class="px-2 py-2 text-right font-medium">{{ tx('rental.ui.amount', 'Amount') }}</th>
                    <th class="w-10 px-1 py-2" />
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in lineComputed"
                    :key="row.line.key"
                    class="border-b border-default/70 align-top"
                  >
                    <td class="px-2 py-2">
                      <USelect
                        :model-value="row.line.model"
                        :items="modelItems"
                        placeholder="—"
                        size="md"
                        class="w-48"
                        :disabled="isFormReadOnly"
                        @update:model-value="(v: string) => onSelectModel(row.line, v)"
                      />
                    </td>
                    <td class="px-2 py-2">
                      <USelect
                        :model-value="row.line.motorcycleId"
                        :items="plateItemsFor(row.line)"
                        placeholder="—"
                        size="md"
                        class="w-40"
                        :disabled="isFormReadOnly || !row.line.model"
                        @update:model-value="(v: string) => onSelectPlate(row.line, v)"
                      />
                    </td>
                    <td class="px-2 py-2">
                      <USelect
                        :model-value="row.line.ratePlan"
                        :items="ratePlanItems"
                        size="md"
                        class="w-40"
                        :disabled="isFormReadOnly"
                        @update:model-value="(v: string) => onRatePlanChange(row.line, v)"
                      />
                    </td>
                    <td class="px-2 py-2">
                      <UInputNumber
                        v-model="row.line.days"
                        :min="1"
                        :increment="false"
                        :decrement="false"
                        size="md"
                        class="ml-auto w-24"
                        :disabled="isFormReadOnly"
                        @update:model-value="(v: number | null) => onLineDaysChange(row.line, v)"
                      />
                    </td>
                    <td class="px-2 py-2">
                      <UInputNumber
                        v-model="row.line.unitPrice"
                        :min="0"
                        :step="0.01"
                        :increment="false"
                        :decrement="false"
                        size="md"
                        class="ml-auto w-32"
                        :disabled="isFormReadOnly"
                      />
                    </td>
                    <td class="px-2 py-2">
                      <UInputNumber
                        v-model="row.line.discount"
                        :min="0"
                        :max="Math.max(row.gross, 0)"
                        :step="0.01"
                        :increment="false"
                        :decrement="false"
                        size="md"
                        class="ml-auto w-28"
                        :disabled="isFormReadOnly"
                      />
                    </td>
                    <td class="px-2 py-2 text-right font-semibold tabular-nums">
                      {{ money(row.amount) }}
                    </td>
                    <td class="px-1 py-2">
                      <UButton
                        v-if="!isFormReadOnly && lines.length > 1"
                        size="xs"
                        color="neutral"
                        variant="ghost"
                        icon="i-lucide-trash-2"
                        @click="removeLine(row.line.key)"
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="mt-2 text-xs text-muted">{{ help('lines', 'Select model, then plate. Each motorcycle has its own rate package and days. Amount uses that motorcycle package rate minus any line discount.') }}</p>

            <div class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <UFormField
                :label="tx('rental.ui.deposit', 'Deposit amount')"
                :help="help('deposit', 'Deposit amount held for this rental. Cannot exceed subtotal.')"
                :error="depositError"
              >
                <UInputNumber
                  v-model="deposit"
                  :min="0"
                  :max="totals.subtotal"
                  :increment="false"
                  :decrement="false"
                  size="md"
                  class="w-full"
                  :disabled="isFormReadOnly"
                />
              </UFormField>

              <div class="flex items-center justify-between gap-4 rounded-md bg-elevated/40 px-3 py-2.5 text-sm">
                <span class="text-muted">{{ tx('rental.ui.subtotal', 'Subtotal') }}</span>
                <span class="font-semibold tabular-nums">{{ money(totals.subtotal) }}</span>
              </div>

              <UFormField
                :label="tx('rental.ui.extraDiscount', 'Extra discount')"
                :help="help('headerDiscount', 'Optional document-level discount shared across motorcycles, applied after each line discount.')"
              >
                <UInputNumber
                  v-model="headerDiscount"
                  :min="0"
                  :max="totals.subtotal"
                  :increment="false"
                  :decrement="false"
                  size="md"
                  class="w-full"
                  :disabled="isFormReadOnly"
                />
              </UFormField>

              <UFormField
                :label="tx('rental.ui.taxPercent', 'Tax %')"
                :help="help('taxPercent', 'Sales tax percent applied after discount.')"
              >
                <UInputNumber
                  v-model="taxPercent"
                  :min="0"
                  :increment="false"
                  :decrement="false"
                  size="md"
                  class="w-full"
                  :disabled="isFormReadOnly"
                />
              </UFormField>

              <UFormField
                :label="tx('rental.ui.paymentMethod', 'Payment Method')"
                :help="help('paymentMethod', 'Choose a preset method or type a custom payment method.')"
              >
                <UInputMenu
                  v-model="paymentMethod"
                  create-item
                  :items="paymentMethodOptions.items.value"
                  size="md"
                  class="w-full"
                  :disabled="isFormReadOnly"
                  @create="onCreatePaymentMethod"
                />
              </UFormField>

              <UFormField
                :label="isDetail ? tx('rental.ui.paid', 'Paid') : tx('rental.ui.paidNow', 'Paid now')"
                :help="isDetail
                  ? help('paidTotal', 'Total paid so far on this rental.')
                  : help('paidAmount', 'Optional payment when creating. Leave 0 to pay later. Cannot exceed total.')"
                :error="paidError"
              >
                <UInputNumber
                  v-model="paidAmount"
                  :min="0"
                  :max="isDetail ? undefined : totals.total"
                  :increment="false"
                  :decrement="false"
                  size="md"
                  class="w-full"
                  :disabled="isDetail"
                />
              </UFormField>

              <div class="flex items-center justify-between gap-4 border-t border-default pt-3 text-base sm:col-span-2">
                <span class="font-semibold">{{ tx('rental.ui.total', 'Total') }}</span>
                <span class="font-semibold tabular-nums">{{ money(totals.total) }}</span>
              </div>

              <p class="text-xs text-muted sm:col-span-2">
                {{ isDetail
                  ? tx('rental.ui.outstanding', 'Outstanding')
                  : tx('rental.ui.outstandingAfterPay', 'Outstanding after payment') }}:
                <span class="font-semibold text-highlighted">{{ money(outstandingPreview) }}</span>
              </p>

              <template v-if="isDetail">
                <div class="rounded-md border border-default bg-elevated/30 p-3 sm:col-span-2">
                  <p class="mb-2 text-xs font-medium uppercase tracking-wide text-muted">
                    {{ tx('rental.ui.balanceSummary', 'Balance summary') }}
                  </p>
                  <div class="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
                    <div class="flex items-center justify-between gap-3">
                      <span class="text-muted">{{ tx('rental.ui.rentalCharge', 'Rental Charge') }}</span>
                      <span class="tabular-nums font-medium">{{ money(Number(detailRental?.rentalCharge || 0)) }}</span>
                    </div>
                    <div class="flex items-center justify-between gap-3">
                      <span class="text-muted">{{ tx('rental.ui.lateFee', 'Late Fee') }}</span>
                      <span class="tabular-nums font-medium">{{ money(lateFee) }}</span>
                    </div>
                    <div class="flex items-center justify-between gap-3">
                      <span class="text-muted">{{ tx('rental.ui.additionalCharges', 'Additional Charges') }}</span>
                      <UButton
                        v-if="additionalCharges > 0"
                        variant="link"
                        color="primary"
                        class="p-0 font-medium tabular-nums"
                        :label="money(additionalCharges)"
                        @click="chargesReviewOpen = true"
                      />
                      <span v-else class="tabular-nums font-medium">{{ money(additionalCharges) }}</span>
                    </div>
                    <div class="flex items-center justify-between gap-3">
                      <span class="text-muted">{{ tx('rental.ui.paid', 'Paid') }}</span>
                      <span class="tabular-nums font-medium">{{ money(existingPaid) }}</span>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>
      </DocumentAppDocumentContentShell>
    </div>

    <UModal
      v-model:open="customerModalOpen"
      :title="tx('rental.ui.addNewCustomer', 'Create customer')"
      :ui="{ content: 'w-[calc(100%-2rem)] max-w-3xl sm:max-w-3xl' }"
    >
      <template #body>
        <div class="flex flex-col gap-4">
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <UFormField
              :label="tx('rental.ui.fullName', 'Full name')"
              :help="help('fullName', 'Customer full name as shown on ID.')"
              required
            >
              <UInput v-model="newCustomer.fullName" size="md" class="w-full" />
            </UFormField>
            <UFormField
              :label="tx('rental.ui.phone', 'Phone')"
              :help="help('phone', 'Primary contact phone number.')"
              required
            >
              <UInput v-model="newCustomer.phone" size="md" class="w-full" />
            </UFormField>
          </div>
          <UFormField
            :label="tx('rental.ui.company', 'Company')"
            :help="help('company', 'Optional company or shop name.')"
          >
            <UInput v-model="newCustomer.company" size="md" class="w-full" />
          </UFormField>
          <UFormField
            :label="tx('rental.ui.identityType', 'Identity type')"
            :help="help('identityType', 'Type of identity document.')"
          >
            <USelect
v-model="newCustomer.identityType"
:items="[...RENTAL_IDENTITY_TYPES]"
size="md"
class="w-full" />
          </UFormField>
          <UFormField
            :label="tx('app.modules.rentalCustomers.fields.identityNumber', 'Identity Number')"
            :help="help('identityNumber', 'ID / passport / license number.')"
            required
          >
            <UInput v-model="newCustomer.identityNumber" size="md" class="w-full" />
          </UFormField>
          <UFormField
            :label="tx('app.modules.rentalCustomers.fields.address', 'Address')"
            :help="help('address', 'Customer home or business address.')"
          >
            <UTextarea
              v-model="newCustomer.address"
              :rows="3"
              size="md"
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
:label="tx('common.actions.cancel', 'Cancel')"
@click="customerModalOpen = false" />
          <UButton
            :loading="savingCustomer"
            :disabled="!canSaveCustomer"
            icon="i-lucide-user-plus"
            :label="tx('rental.ui.saveCustomer', 'Save customer')"
            @click="saveNewCustomer"
          />
        </div>
      </template>
    </UModal>

    <RentalChargesReviewModal
      v-if="isDetail && detailRental"
      v-model:open="chargesReviewOpen"
      :rental="detailRental"
    />

    <RentalInvoicePreview
      v-if="invoiceRental"
      :rental="invoiceRental"
      mode="direct-print"
      @close="invoiceRental = null"
    />
  </div>
</template>
