<script setup lang="ts">
import { formatMoney } from '~/composables/module/useModule'

const props = defineProps<{
  rental: Record<string, unknown> | null
}>()

const preferences = usePreferencesStore()
const store = useAppDataStore()

const DEFAULT_ADDRESS = 'St. 271, Toul Tum Poung, Phnom Penh, Cambodia'
const DEFAULT_PHONE = '+855 23 555 123'
const DEFAULT_EMAIL = 'info@hollywingmotor.com'

/** Bilingual invoice labels — Khmer always on top, English below. */
const L = {
  invoice: { km: 'វិក្កយបត្រ', en: 'INVOICE' },
  motorcycleRental: { km: 'ការជួលម៉ូតូ', en: 'Motorcycle Rental' },
  invoiceInfo: { km: 'ព័ត៌មានវិក្កយបត្រ', en: 'Invoice Info' },
  customerInfo: { km: 'ព័ត៌មានអតិថិជន', en: 'Customer Info' },
  invoiceNo: { km: 'លេខវិក្កយបត្រ', en: 'Invoice No.' },
  paymentMethod: { km: 'វិធីបង់ប្រាក់', en: 'Payment Method' },
  created: { km: 'ថ្ងៃបង្កើត', en: 'Created' },
  depositDate: { km: 'ថ្ងៃដាក់ប្រាក់កក់', en: 'Deposit Date' },
  customer: { km: 'អតិថិជន', en: 'Customer' },
  phone: { km: 'ទូរស័ព្ទ', en: 'Phone' },
  startDate: { km: 'ថ្ងៃចាប់ផ្តើម', en: 'Start Date' },
  returnDate: { km: 'ថ្ងៃប្រគល់', en: 'Return Date' },
  invoiceLocation: { km: 'ទីតាំងវិក្កយបត្រ', en: 'Invoice location' },
  no: { km: 'ល.រ', en: 'No' },
  motorcycle: { km: 'ម៉ូតូ', en: 'Motorcycle' },
  plate: { km: 'លេខផ្ទាំង', en: 'Plate' },
  days: { km: 'ថ្ងៃ', en: 'Day(s)' },
  unitPrice: { km: 'តម្លៃឯកតា', en: 'Unit price' },
  amount: { km: 'ចំនួនទឹកប្រាក់', en: 'Amount' },
  subtotal: { km: 'សរុបរង', en: 'Subtotal' },
  deposit: { km: 'ប្រាក់កក់', en: 'Deposit' },
  discount: { km: 'បញ្ចុះតម្លៃ', en: 'Discount' },
  tax: { km: 'ពន្ធ', en: 'Tax' },
  total: { km: 'សរុប', en: 'Total' },
  paid: { km: 'បានបង់', en: 'Paid' },
  outstanding: { km: 'នៅជំពាក់', en: 'Outstanding' },
  terms: { km: 'លក្ខខណ្ឌ', en: 'Terms & Conditions' },
  paymentTerms: {
    km: 'ត្រូវបង់ប្រាក់តាមកិច្ចសន្យាជួល។ ប្រាក់កក់នឹងប្រគល់វិញបន្ទាប់ពីត្រួតពិនិត្យម៉ូតូរួច។',
    en: 'Payment is due according to the rental agreement. The deposit is refundable after the motorcycle passes return inspection.',
  },
  noItems: { km: 'មិនមានធាតុវិក្កយបត្រ', en: 'No invoice items' },
  thankYou: { km: 'អរគុណដែលបានជ្រើសរើស', en: 'Thank you for choosing' },
  lateFee: { km: 'ថ្លៃយឺត', en: 'Late fee' },
  additionalCharges: { km: 'ការគិតថ្លៃបន្ថែម', en: 'Additional charges' },
} as const

const currencyCode = computed(() => String(props.rental?.currency || preferences.currency || 'USD'))
const money = (value: unknown) => formatMoney(value, currencyCode.value)

function dateTime(value: unknown) {
  if (!value) return '—'
  const parsed = new Date(String(value))
  if (Number.isNaN(parsed.getTime())) return String(value)
  return parsed.toLocaleString('en-GB', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const invoiceNo = computed(() =>
  String(props.rental?.invoiceNo || `INV-${String(props.rental?.rentalNo || '').replace('RNT-', '')}`),
)

const payments = computed(() => {
  if (!props.rental) return []
  return store.list('rentalPayments')
    .filter(row => String(row.rentalId || '') === String(props.rental!.id))
    .sort((a, b) => String(a.paidAt || '').localeCompare(String(b.paidAt || '')))
})

const paymentMethod = computed(() => {
  const methods = [...new Set(payments.value.map(row => String(row.paymentMethod || '')).filter(Boolean))]
  return methods.join(', ') || String(props.rental?.paymentMethod || '—')
})

const createdAt = computed(() => dateTime(props.rental?.createdAt || props.rental?.startDate))
const depositAmount = computed(() => Math.max(0, Number(props.rental?.deposit || 0)))
const depositDate = computed(() => {
  if (depositAmount.value <= 0) return ''
  return dateTime(props.rental?.depositDate || payments.value[0]?.paidAt || props.rental?.startDate)
})
const returnDate = computed(() => dateTime(props.rental?.returnDate || props.rental?.dueDate))
const paidAmount = computed(() => Math.max(0, Number(props.rental?.paid || 0)))
const outstandingAmount = computed(() => Math.max(0, Number(props.rental?.outstanding || 0)))

const charges = computed(() => {
  if (!props.rental) return []
  return store.list('rentalCharges').filter(row =>
    String(row.rentalId || '') === String(props.rental!.id)
    && String(row.chargeToCustomer || 'Yes') !== 'No',
  )
})

interface LineItem {
  motorcycle: string
  plate: string
  days: number | string
  unitPrice: number
  amount: number
}

const lineItems = computed<LineItem[]>(() => {
  if (!props.rental) return []
  const items: LineItem[] = []
  const rentalCharge = Number(props.rental.rentalCharge || 0)
  const startTime = new Date(String(props.rental.startDate || '')).getTime()
  const returnTime = new Date(String(props.rental.returnDate || props.rental.dueDate || '')).getTime()
  const calculatedDays = Number.isFinite(startTime) && Number.isFinite(returnTime) && returnTime > startTime
    ? Math.ceil((returnTime - startTime) / 86_400_000)
    : 1
  const duration = Math.max(1, Number(props.rental.durationDays || calculatedDays))
  const motorcycle = String(props.rental.motorcycle || '')
  const plate = String(props.rental.plate || '')

  if (rentalCharge > 0 || motorcycle) {
    items.push({
      motorcycle: motorcycle || '—',
      plate: plate || '—',
      days: duration,
      unitPrice: Number(props.rental.rateAmount || 0),
      amount: rentalCharge || Number((duration * Number(props.rental.rateAmount || 0)).toFixed(2)),
    })
  }

  const lateFee = Number(props.rental.lateFee || 0)
  if (lateFee > 0) {
    items.push({
      motorcycle: `${L.lateFee.km} / ${L.lateFee.en}`,
      plate: '—',
      days: '—',
      unitPrice: lateFee,
      amount: lateFee,
    })
  }

  let recordedAdditional = 0
  for (const charge of charges.value) {
    const amount = Number(charge.amount || 0)
    if (amount <= 0) continue
    recordedAdditional += amount
    const label = [charge.chargeType, charge.description].filter(Boolean).map(String).join(' · ')
    items.push({
      motorcycle: label || `${L.additionalCharges.km} / ${L.additionalCharges.en}`,
      plate: '—',
      days: '—',
      unitPrice: amount,
      amount,
    })
  }

  const additionalFallback = Math.max(Number(props.rental.additionalCharges || 0) - recordedAdditional, 0)
  if (additionalFallback > 0) {
    items.push({
      motorcycle: `${L.additionalCharges.km} / ${L.additionalCharges.en}`,
      plate: '—',
      days: '—',
      unitPrice: additionalFallback,
      amount: additionalFallback,
    })
  }

  return items
})

const subtotal = computed(() => lineItems.value.reduce((sum, item) => sum + item.amount, 0))
const discount = computed(() => Math.max(0, Number(props.rental?.discount || 0)))
const tax = computed(() => {
  const stored = Number(props.rental?.tax || 0)
  if (stored > 0) return stored
  return Math.max(Number(props.rental?.totalDue || 0) - (subtotal.value - discount.value), 0)
})
const total = computed(() => Number(props.rental?.totalDue || subtotal.value - discount.value + tax.value))

const companyName = 'HollyWing Motor'
const companyAddress = DEFAULT_ADDRESS
const companyPhone = DEFAULT_PHONE
const companyEmail = DEFAULT_EMAIL
const companyContact = [companyPhone, companyEmail].filter(Boolean).join(' · ')
</script>

<template>
  <article v-if="rental" class="rental-invoice-sheet bg-white text-[#172033]">
    <header class="grid grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] items-start gap-3 border-b border-[#172033] pb-3">
      <div class="flex min-w-0 items-center gap-2.5">
        <img
          src="/logo.png"
          alt="Company logo"
          class="h-14 w-14 shrink-0 rounded-full object-contain"
          onerror="this.style.display='none'"
        >
        <div class="min-w-0">
          <p class="truncate text-[15px] font-extrabold text-[#0b4f91]">{{ companyName }}</p>
          <p class="text-[8px] leading-tight text-slate-500">
            <span class="block uppercase tracking-[0.12em]">{{ L.motorcycleRental.en }}</span>
          </p>
        </div>
      </div>

      <div class="min-w-0 text-right text-[9px] leading-snug text-slate-700">
        <p>{{ companyAddress }}</p>
        <p class="tabular-nums">{{ companyContact }}</p>
      </div>
    </header>

    <section class="py-3">
      <div class="mb-3 text-center">
        <p class="text-[13px] font-extrabold leading-tight text-[#101827]">{{ L.invoice.km }}</p>
        <p class="text-[11px] font-black uppercase tracking-[0.14em] text-[#101827]">{{ L.invoice.en }}</p>
      </div>

      <div class="grid grid-cols-2 gap-6">
        <div>
          <h2 class="mb-2 text-[6px] font-extrabold uppercase tracking-wide text-slate-500">
            <span class="block">{{ L.invoiceInfo.en }}</span>
          </h2>
          <dl class="space-y-1.5 text-[9px]">
            <div class="grid grid-cols-[6.5rem_1fr] gap-2">
              <dt class="leading-tight">
                <span class="block font-bold">{{ L.invoiceNo.km }}</span>
                <span class="block text-[8px] text-slate-500">{{ L.invoiceNo.en }}</span>
              </dt>
              <dd class="self-center text-right font-medium tabular-nums">{{ invoiceNo }}</dd>
            </div>
            <div class="grid grid-cols-[6.5rem_1fr] gap-2">
              <dt class="leading-tight">
                <span class="block font-bold">{{ L.paymentMethod.km }}</span>
                <span class="block text-[8px] text-slate-500">{{ L.paymentMethod.en }}</span>
              </dt>
              <dd class="self-center text-right">{{ paymentMethod }}</dd>
            </div>
            <div class="grid grid-cols-[6.5rem_1fr] gap-2">
              <dt class="leading-tight">
                <span class="block font-bold">{{ L.created.km }}</span>
                <span class="block text-[8px] text-slate-500">{{ L.created.en }}</span>
              </dt>
              <dd class="self-center text-right tabular-nums">{{ createdAt }}</dd>
            </div>
            <div v-if="depositDate" class="grid grid-cols-[6.5rem_1fr] gap-2">
              <dt class="leading-tight">
                <span class="block font-bold">{{ L.depositDate.km }}</span>
                <span class="block text-[8px] text-slate-500">{{ L.depositDate.en }}</span>
              </dt>
              <dd class="self-center text-right tabular-nums">{{ depositDate }}</dd>
            </div>
          </dl>
        </div>

        <div>
          <h2 class="mb-2 text-[6px] font-extrabold uppercase tracking-wide text-slate-500">
            <span class="block">{{ L.customerInfo.en }}</span>
          </h2>
          <dl class="space-y-1.5 text-[9px]">
            <div class="grid grid-cols-[5.5rem_1fr] gap-2">
              <dt class="leading-tight">
                <span class="block font-bold">{{ L.customer.km }}</span>
                <span class="block text-[8px] text-slate-500">{{ L.customer.en }}</span>
              </dt>
              <dd class="self-center text-right font-medium">{{ rental.customer || '—' }}</dd>
            </div>
            <div class="grid grid-cols-[5.5rem_1fr] gap-2">
              <dt class="leading-tight">
                <span class="block font-bold">{{ L.phone.km }}</span>
                <span class="block text-[8px] text-slate-500">{{ L.phone.en }}</span>
              </dt>
              <dd class="self-center text-right tabular-nums">{{ rental.phone || '—' }}</dd>
            </div>
            <div class="grid grid-cols-[5.5rem_1fr] gap-2">
              <dt class="leading-tight">
                <span class="block font-bold">{{ L.startDate.km }}</span>
                <span class="block text-[8px] text-slate-500">{{ L.startDate.en }}</span>
              </dt>
              <dd class="self-center text-right tabular-nums">{{ dateTime(rental.startDate) }}</dd>
            </div>
            <div class="grid grid-cols-[5.5rem_1fr] gap-2">
              <dt class="leading-tight">
                <span class="block font-bold">{{ L.returnDate.km }}</span>
                <span class="block text-[8px] text-slate-500">{{ L.returnDate.en }}</span>
              </dt>
              <dd class="self-center text-right tabular-nums">{{ returnDate }}</dd>
            </div>
          </dl>
        </div>
      </div>
    </section>

    <table class="invoice-lines w-full table-fixed border-collapse text-[8px]">
      <colgroup>
        <col class="w-[8%]">
        <col class="w-[28%]">
        <col class="w-[16%]">
        <col class="w-[12%]">
        <col class="w-[18%]">
        <col class="w-[18%]">
      </colgroup>
      <thead>
        <tr class="bg-[#2463df] text-white">
          <th class="px-1.5 py-1.5 text-center font-bold leading-tight">
            <span class="block">{{ L.no.km }}</span>
            <span class="block text-[7px] font-semibold opacity-90">{{ L.no.en }}</span>
          </th>
          <th class="px-1.5 py-1.5 text-center font-bold leading-tight">
            <span class="block">{{ L.motorcycle.km }}</span>
            <span class="block text-[7px] font-semibold opacity-90">{{ L.motorcycle.en }}</span>
          </th>
          <th class="px-1.5 py-1.5 text-center font-bold leading-tight">
            <span class="block">{{ L.plate.km }}</span>
            <span class="block text-[7px] font-semibold opacity-90">{{ L.plate.en }}</span>
          </th>
          <th class="px-1.5 py-1.5 text-center font-bold leading-tight">
            <span class="block">{{ L.days.km }}</span>
            <span class="block text-[7px] font-semibold opacity-90">{{ L.days.en }}</span>
          </th>
          <th class="px-1.5 py-1.5 text-center font-bold leading-tight">
            <span class="block">{{ L.unitPrice.km }}</span>
            <span class="block text-[7px] font-semibold opacity-90">{{ L.unitPrice.en }}</span>
          </th>
          <th class="px-1.5 py-1.5 text-center font-bold leading-tight">
            <span class="block">{{ L.amount.km }}</span>
            <span class="block text-[7px] font-semibold opacity-90">{{ L.amount.en }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(item, index) in lineItems" :key="`${item.motorcycle}-${item.plate}-${index}`">
          <td class="border border-slate-200 px-1.5 py-1.5 text-center tabular-nums">{{ index + 1 }}</td>
          <td class="border border-slate-200 px-1.5 py-1.5 leading-snug">{{ item.motorcycle }}</td>
          <td class="border border-slate-200 px-1.5 py-1.5 tabular-nums">{{ item.plate }}</td>
          <td class="border border-slate-200 px-1.5 py-1.5 text-center tabular-nums">{{ item.days }}</td>
          <td class="border border-slate-200 px-1.5 py-1.5 text-right tabular-nums">{{ money(item.unitPrice) }}</td>
          <td class="border border-slate-200 px-1.5 py-1.5 text-right font-semibold tabular-nums">{{ money(item.amount) }}</td>
        </tr>
        <tr v-if="!lineItems.length">
          <td colspan="6" class="border border-slate-200 px-3 py-5 text-center text-slate-400">
            <span class="block">{{ L.noItems.km }}</span>
            <span class="block">{{ L.noItems.en }}</span>
          </td>
        </tr>
      </tbody>
    </table>

    <section class="mt-3 grid grid-cols-[1fr_14rem] gap-5">
      <div class="text-[8px] leading-relaxed text-slate-600">
        <h2 class="inline-block border-b border-slate-500 pb-1 font-extrabold tracking-wide text-slate-500">
          <span class="block">{{ L.terms.km }}</span>
          <span class="block uppercase">{{ L.terms.en }}</span>
        </h2>
        <p class="mt-1.5">{{ L.paymentTerms.km }}</p>
        <p class="mt-1">{{ L.paymentTerms.en }}</p>
      </div>

      <dl class="text-[9px]">
        <div class="flex justify-between gap-3 py-0.5">
          <dt class="leading-tight">
            <span class="block font-semibold">{{ L.subtotal.km }}</span>
            <span class="block text-[7px] text-slate-500">{{ L.subtotal.en }}</span>
          </dt>
          <dd class="self-center font-medium tabular-nums">{{ money(subtotal) }}</dd>
        </div>
        <div class="flex justify-between gap-3 py-0.5">
          <dt class="leading-tight">
            <span class="block font-semibold">{{ L.deposit.km }}</span>
            <span class="block text-[7px] text-slate-500">{{ L.deposit.en }}</span>
          </dt>
          <dd class="self-center font-medium tabular-nums">{{ money(depositAmount) }}</dd>
        </div>
        <div class="flex justify-between gap-3 py-0.5">
          <dt class="leading-tight">
            <span class="block font-semibold">{{ L.discount.km }}</span>
            <span class="block text-[7px] text-slate-500">{{ L.discount.en }}</span>
          </dt>
          <dd class="self-center font-medium tabular-nums">{{ money(discount) }}</dd>
        </div>
        <div class="flex justify-between gap-3 border-b border-[#172033] py-0.5">
          <dt class="leading-tight">
            <span class="block font-semibold">{{ L.tax.km }}</span>
            <span class="block text-[7px] text-slate-500">{{ L.tax.en }}</span>
          </dt>
          <dd class="self-center font-medium tabular-nums">{{ money(tax) }}</dd>
        </div>
        <div class="flex justify-between gap-3 py-1.5 text-[12px] font-extrabold">
          <dt class="leading-tight">
            <span class="block">{{ L.total.km }}</span>
            <span class="block text-[8px] font-bold uppercase tracking-wide">{{ L.total.en }}</span>
          </dt>
          <dd class="self-center tabular-nums">{{ money(total) }}</dd>
        </div>
        <div class="flex justify-between gap-3 py-0.5">
          <dt class="leading-tight">
            <span class="block font-semibold">{{ L.paid.km }}</span>
            <span class="block text-[7px] text-slate-500">{{ L.paid.en }}</span>
          </dt>
          <dd class="self-center font-medium tabular-nums">{{ money(paidAmount) }}</dd>
        </div>
        <div class="flex justify-between gap-3 py-0.5">
          <dt class="leading-tight">
            <span class="block font-semibold">{{ L.outstanding.km }}</span>
            <span class="block text-[7px] text-slate-500">{{ L.outstanding.en }}</span>
          </dt>
          <dd class="self-center font-medium tabular-nums">{{ money(outstandingAmount) }}</dd>
        </div>
      </dl>
    </section>

    <footer class="mt-4 bg-[#2463df] px-3 py-2 text-center text-[8px] font-bold text-white">
      <span class="block">{{ L.thankYou.km }} {{ companyName }}</span>
      <span class="block">{{ L.thankYou.en }} {{ companyName }}</span>
    </footer>
  </article>
</template>
