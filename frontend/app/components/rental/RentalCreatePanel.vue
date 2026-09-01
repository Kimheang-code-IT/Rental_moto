<script setup lang="ts">
import type { DropdownMenuItem } from '@nuxt/ui'
import type { ExportFieldOption, ExportRequest } from '~/types/rental/export'
import { useConfirm } from '~/composables/common/useConfirm'
import { useAppHeader } from '~/composables/layout/useAppHeader'
import { usePageSeo } from '~/composables/usePageSeo'
import { formatMoney, statusColor } from '~/composables/module/useModule'
import { PAYMENT_METHODS, RENTAL_IDENTITY_TYPES } from '~/config/rental-options'
import { downloadCsv } from '~/utils/export/csv'
import {
  addDaysToDateTime,
  allocateRentalPayment,
  daysBetween,
  documentTotals,
  resolveMotorcycleRates,
  todayDateTimeLocal,
} from '~/utils/rental/pricing'
import { toIsoZoned } from '~/utils/api/datetime'
import { useRentalCommands } from '~/repositories/index'

const props = withDefaults(defineProps<{
  mode?: 'create' | 'detail'
  rentalId?: string
}>(), {
  mode: 'create',
})

const emit = defineEmits<{ cancel: [], created: [id: string] }>()

const { t, te } = useI18n()
const auth = useAuthStore()
const store = useAppDataStore()
const preferences = usePreferencesStore()
const { confirm } = useConfirm()
const toast = useToast()
const { setBreadcrumbs, setBadges, clear: clearHeader } = useAppHeader()

const isDetail = computed(() => props.mode === 'detail')

function staffName() {
  return auth.user?.name || 'Staff'
}

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

function help(key: string, fallback: string) {
  return te(`core.fieldHelp.${key}`) ? String(t(`core.fieldHelp.${key}`)) : fallback
}

interface RentalLine {
  key: string
  model: string
  motorcycleId: string
  days: number
  unitPrice: number
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
const paymentMethod = ref<(typeof PAYMENT_METHODS)[number]>(PAYMENT_METHODS[0])
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
const listNavigationDirection = ref<'previous' | 'next' | null>(null)

let lineSeq = 1
function newLine(): RentalLine {
  return { key: `line-${lineSeq++}`, model: '', motorcycleId: '', days: 1, unitPrice: 0 }
}
const lines = ref<RentalLine[]>([newLine()])

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
  if (isDetail.value) return
  line.model = String(model || '')
  line.motorcycleId = ''
  line.unitPrice = 0
  const first = availableMotorcycles.value.find(row => String(row.model) === line.model)
  if (first) {
    const rates = resolveMotorcycleRates(first)
    line.unitPrice = rates.daily
  }
}

function onSelectPlate(line: RentalLine, motorcycleId: string | number) {
  if (isDetail.value) return
  line.motorcycleId = String(motorcycleId || '')
  const moto = motoById(line.motorcycleId)
  if (!moto) return
  line.model = String(moto.model || line.model)
  line.unitPrice = resolveMotorcycleRates(moto).daily
  if (!line.days) line.days = 1
}

function lineAmount(line: RentalLine) {
  const days = Math.max(0, Number(line.days) || 0)
  const price = Math.max(0, Number(line.unitPrice) || 0)
  return Number((days * price).toFixed(2))
}

const lineComputed = computed(() => lines.value.map(line => ({
  line,
  moto: motoById(line.motorcycleId),
  amount: lineAmount(line),
})))

const totals = computed(() => {
  const base = documentTotals({
    lineTotals: lineComputed.value.map(row => row.amount),
    discount: headerDiscount.value,
    taxPercent: taxPercent.value,
  })
  if (!isDetail.value) return base
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
  if (isDetail.value) return Math.max(0, Number(outstandingBalance.value) || 0)
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
  if (isDetail.value) return
  if (deposit.value > subtotal) deposit.value = subtotal
})

watch(() => totals.value.total, (total) => {
  if (isDetail.value) return
  if (paidAmount.value > total) paidAmount.value = total
})

watch(startDate, () => {
  if (isDetail.value || syncingDates.value) return
  const days = lines.value[0]?.days || daysBetween(startDate.value, dueDate.value) || 1
  if (days > 0 && startDate.value) {
    syncingDates.value = true
    dueDate.value = addDaysToDateTime(startDate.value, days)
    syncingDates.value = false
  }
})

watch(dueDate, () => {
  if (isDetail.value || syncingDates.value || !startDate.value || !dueDate.value) return
  const days = daysBetween(startDate.value, dueDate.value)
  if (days > 0) {
    syncingDates.value = true
    for (const line of lines.value) line.days = days
    syncingDates.value = false
  }
})

function onLineDaysChange(line: RentalLine) {
  if (isDetail.value || syncingDates.value || !startDate.value) return
  const days = Math.max(1, Math.floor(Number(line.days) || 1))
  line.days = days
  syncingDates.value = true
  dueDate.value = addDaysToDateTime(startDate.value, days)
  for (const other of lines.value) {
    if (other.key !== line.key) other.days = days
  }
  syncingDates.value = false
}

function addLine() {
  if (isDetail.value) return
  const days = lines.value[0]?.days || daysBetween(startDate.value, dueDate.value) || 1
  const row = newLine()
  row.days = days
  lines.value.push(row)
}

function removeLine(key: string) {
  if (isDetail.value || lines.value.length <= 1) return
  lines.value = lines.value.filter(row => row.key !== key)
}

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

function nextCustomerCode() {
  const numbers = store.list('rentalCustomers')
    .map(row => String(row.code || ''))
    .map(code => Number(code.split('-').pop()))
    .filter(no => Number.isFinite(no))
  const next = (numbers.length ? Math.max(...numbers) : 0) + 1
  return `CUS-${String(next).padStart(3, '0')}`
}

const customerModalOpen = ref(false)
const savingCustomer = ref(false)
const newCustomer = reactive({
  fullName: '',
  phone: '',
  identityType: RENTAL_IDENTITY_TYPES[0] as (typeof RENTAL_IDENTITY_TYPES)[number],
  identityNumber: '',
  company: '',
})

const canSaveCustomer = computed(() => Boolean(
  newCustomer.fullName.trim()
  && newCustomer.phone.trim()
  && newCustomer.identityNumber.trim(),
))

function openCustomerModal() {
  newCustomer.fullName = ''
  newCustomer.phone = ''
  newCustomer.identityType = RENTAL_IDENTITY_TYPES[0]
  newCustomer.identityNumber = ''
  newCustomer.company = ''
  customerModalOpen.value = true
}

async function saveNewCustomer() {
  if (!canSaveCustomer.value) return
  savingCustomer.value = true
  try {
    const created = await store.createRemote('rentalCustomers', {
      code: nextCustomerCode(),
      fullName: newCustomer.fullName.trim(),
      phone: newCustomer.phone.trim(),
      identityType: newCustomer.identityType,
      identityNumber: newCustomer.identityNumber.trim(),
      company: newCustomer.company.trim(),
      email: '',
      address: '',
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
    return
  }
  hydrateDetail()
  void store.fetchList('rentalPayments', { rentalId: props.rentalId })
}

function hydrateDetail() {
  if (!isDetail.value || !props.rentalId) return
  const found = store.get('rentals', props.rentalId)
  notFound.value = !found
  if (!found) return

  rentalNo.value = String(found.rentalNo || '')
  rentalStatus.value = String(found.status || 'Active')
  customerId.value = String(found.customerId || '')
  startDate.value = String(found.startDate || '')
  dueDate.value = String(found.dueDate || '')
  depositDate.value = String(found.depositDate || String(found.startDate || '').slice(0, 10))
  deposit.value = Number(found.deposit || 0)
  headerDiscount.value = Number(found.discount || 0)
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
  if (PAYMENT_METHODS.includes(lastMethod as typeof PAYMENT_METHODS[number])) {
    paymentMethod.value = lastMethod as typeof PAYMENT_METHODS[number]
  }

  lines.value = [{
    key: `line-${lineSeq++}`,
    model: String(found.motorcycle || ''),
    motorcycleId: String(found.motorcycleId || ''),
    days: Math.max(1, Number(found.durationDays || daysBetween(String(found.startDate || ''), String(found.dueDate || '')) || 1)),
    unitPrice: Number(found.rateAmount || 0),
  }]
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
    setBadges([{ label: rentalStatus.value, color: statusColor(rentalStatus.value) }])
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
    rateType: 'Daily',
    rateAmount: first?.line.unitPrice || 0,
    deposit: deposit.value,
    depositDate: depositDate.value,
    discount: headerDiscount.value,
    taxPercent: taxPercent.value,
    tax: totals.value.tax,
    currency: moto?.currency || preferences.currency,
    rentalCharge: totals.value.subtotal,
    lateFee: 0,
    additionalCharges: 0,
    totalDue: totals.value.total,
    paid: paidAmount.value,
    outstanding: outstandingPreview.value,
    paymentMethod: paymentMethod.value,
    status: 'Draft',
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

async function createRental() {
  if (!canCreate.value || !selectedCustomer.value) return
  const validLines = lineComputed.value.filter(row => row.moto)
  if (!validLines.length) return

  const ok = await confirm({
    kind: 'generic',
    title: tx('rental.ui.confirmCreate', 'Create this rental?'),
    description: `${selectedCustomer.value.fullName} · ${validLines.length} ${tx('rental.ui.motorcycles', 'motorcycles')} · ${tx('rental.ui.total', 'Total')}: ${formatMoney(totals.value.total, preferences.currency)}`,
    confirmLabel: tx('rental.ui.createRental', 'Create Rental'),
  })
  if (!ok) return

  saving.value = true
  try {
    if (store.isHttpMode) {
      // One atomic server transaction: numbering, pricing, balances, payment,
      // motorcycle status, audit, and outbox all happen in the backend.
      const created = await useRentalCommands().create({
        customerId: String(selectedCustomer.value.id),
        lines: validLines.map(row => ({
          motorcycleId: String(row.line.motorcycleId),
          startDate: toIsoZoned(startDate.value)!,
          dueDate: toIsoZoned(dueDate.value)!,
          deposit: Number((deposit.value / validLines.length).toFixed(2)),
          discount: 0,
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
      emit('created', String(created[0]?.id || ''))
      return
    }

    const lineTotals = validLines.map(row => row.amount)
    const paymentShares = allocateRentalPayment(lineTotals, paidAmount.value)
    const headerShare = totals.value.subtotal > 0
      ? validLines.map(row => row.amount / totals.value.subtotal)
      : validLines.map(() => 1 / validLines.length)

    let firstId = ''
    const rentalSeq = store.list('rentals')
      .map(row => Number(String(row.rentalNo || '').split('-').pop()))
      .filter(no => Number.isFinite(no))
    let nextNum = (rentalSeq.length ? Math.max(...rentalSeq) : 0) + 1

    validLines.forEach((row, index) => {
      const moto = row.moto!
      const lineHeaderDiscount = Number((totals.value.discount * headerShare[index]!).toFixed(2))
      const lineTax = Number((totals.value.tax * headerShare[index]!).toFixed(2))
      const lineDeposit = Number((deposit.value * headerShare[index]!).toFixed(2))
      const rentalCharge = row.amount
      const discount = lineHeaderDiscount
      const totalDue = Number((Math.max(rentalCharge - discount, 0) + lineTax).toFixed(2))
      const paid = paymentShares[index] || 0
      const nextRentalNo = `RNT-${new Date().getFullYear()}-${String(nextNum++).padStart(6, '0')}`

      const created = store.create('rentals', {
        rentalNo: nextRentalNo,
        customerId: selectedCustomer.value!.id,
        customer: selectedCustomer.value!.fullName,
        phone: selectedCustomer.value!.phone,
        motorcycleId: moto.id,
        motorcycle: moto.model,
        plate: moto.plate,
        startDate: startDate.value,
        dueDate: dueDate.value,
        durationDays: row.line.days,
        rateType: 'Daily',
        rateAmount: row.line.unitPrice,
        deposit: lineDeposit,
        depositDate: depositDate.value,
        discount,
        taxPercent: taxPercent.value,
        tax: lineTax,
        currency: moto.currency || preferences.currency,
        rentalCharge,
        lateFee: 0,
        additionalCharges: 0,
        totalDue,
        paid,
        outstanding: Math.max(totalDue - paid, 0),
        paymentMethod: paymentMethod.value,
        note: '',
        createdBy: staffName(),
        status: 'Active',
      }, 'rt')

      store.save('motorcycles', { ...moto, status: 'Progressing' })

      if (paid > 0) {
        const seq = store.list('rentalPayments').length + 1
        store.create('rentalPayments', {
          paymentNo: `RNP-${String(seq).padStart(6, '0')}`,
          rentalId: created.id,
          rentalNo: created.rentalNo,
          customer: created.customer,
          amount: paid,
          currency: created.currency,
          paymentMethod: paymentMethod.value,
          paidAt: startDate.value,
          reference: '',
          note: tx('rental.ui.paymentOnRegister', 'Payment on register'),
        }, 'rnp')
      }

      store.addAudit(`Created rental ${created.rentalNo}`, 'Rentals', String(created.rentalNo))
      if (!firstId) firstId = String(created.id)
    })

    toast.add({ title: tx('rental.ui.rentalCreated', 'Rental created'), color: 'success' })
    emit('created', firstId)
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
      :show-save="!isDetail && canCreate"
      :save-label="tx('rental.ui.createRental', 'Create Rental')"
      :saving="saving"
      :show-cancel="true"
      cancel-to="/rentals"
      :create-buttons="createCustomerButtons"
      @save="createRental"
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
                :disabled="isDetail"
              />
            </UFormField>
            <UFormField
              :label="tx('rental.ui.passport', 'Passport')"
              :help="help('customerPassport', 'Select customer by passport / ID number.')"
              required
            >
              <USelect
                v-model="customerId"
                :items="isDetail ? detailCustomerPassportItems : customerPassportItems"
                placeholder="—"
                size="md"
                class="w-full"
                :disabled="isDetail"
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
                :disabled="isDetail"
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
                :disabled="isDetail"
              />
            </UFormField>
          </div>

          <div>
            <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p class="text-sm font-semibold text-highlighted">{{ tx('rental.ui.motorcycle', 'Motorcycle') }}</p>
              <UButton
                v-if="!isDetail"
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
                    <th class="px-2 py-2 font-medium">{{ tx('rental.ui.daysCount', 'Days') }}</th>
                    <th class="px-2 py-2 font-medium">{{ tx('rental.ui.unitPrice', 'Unit price / day') }}</th>
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
                        :disabled="isDetail"
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
                        :disabled="isDetail || !row.line.model"
                        @update:model-value="(v: string) => onSelectPlate(row.line, v)"
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
                        :disabled="isDetail"
                        @update:model-value="onLineDaysChange(row.line)"
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
                        :disabled="isDetail"
                      />
                    </td>
                    <td class="px-2 py-2 text-right font-semibold tabular-nums">
                      {{ money(row.amount) }}
                    </td>
                    <td class="px-1 py-2">
                      <UButton
                        v-if="!isDetail && lines.length > 1"
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
            <p class="mt-2 text-xs text-muted">{{ help('lines', 'Select model, then plate. Amount = days × unit price per day.') }}</p>

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
                  :disabled="isDetail"
                />
              </UFormField>

              <div class="flex items-center justify-between gap-4 rounded-md bg-elevated/40 px-3 py-2.5 text-sm">
                <span class="text-muted">{{ tx('rental.ui.subtotal', 'Subtotal') }}</span>
                <span class="font-semibold tabular-nums">{{ money(totals.subtotal) }}</span>
              </div>

              <UFormField
                :label="tx('rental.ui.discount', 'Discount')"
                :help="help('headerDiscount', 'Document-level discount applied after line totals.')"
              >
                <UInputNumber
                  v-model="headerDiscount"
                  :min="0"
                  :max="totals.subtotal"
                  :increment="false"
                  :decrement="false"
                  size="md"
                  class="w-full"
                  :disabled="isDetail"
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
                  :disabled="isDetail"
                />
              </UFormField>

              <UFormField
                :label="tx('rental.ui.paymentMethod', 'Payment Method')"
                :help="help('paymentMethod', 'How the customer pays.')"
              >
                <USelect
                  v-model="paymentMethod"
                  :items="[...PAYMENT_METHODS]"
                  size="md"
                  class="w-full"
                  :disabled="isDetail"
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
            </div>
          </div>
        </div>
      </DocumentAppDocumentContentShell>
    </div>

    <UModal v-model:open="customerModalOpen" :title="tx('rental.ui.addNewCustomer', 'Create customer')">
      <template #body>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <UFormField
            :label="tx('rental.ui.fullName', 'Full name')"
            :help="help('fullName', 'Customer full name as shown on ID.')"
            required
            class="sm:col-span-2"
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
            :label="tx('rental.ui.passport', 'Passport')"
            :help="help('identityNumber', 'ID / passport / license number.')"
            required
            class="sm:col-span-2"
          >
            <UInput v-model="newCustomer.identityNumber" size="md" class="w-full" />
          </UFormField>
          <UFormField
            :label="tx('rental.ui.company', 'Company')"
            :help="help('company', 'Optional company or shop name.')"
            class="sm:col-span-2"
          >
            <UInput v-model="newCustomer.company" size="md" class="w-full" />
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

    <RentalInvoicePreview
      v-if="invoiceRental"
      :rental="invoiceRental"
      mode="direct-print"
      @close="invoiceRental = null"
    />
  </div>
</template>
