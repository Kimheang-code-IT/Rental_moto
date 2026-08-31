<script setup lang="ts">
const props = defineProps<{
  rental: Record<string, unknown> | null
}>()

const preferences = usePreferencesStore()
const tenant = useTenantStore()
const store = useFreightStore()

const currencyCode = computed(() => String(props.rental?.currency || preferences.currency || 'USD'))
const money = (value: unknown) => formatMoney(value, currencyCode.value)

const invoiceNo = computed(() =>
  `INV-${String(props.rental?.rentalNo || '').replace('RNT-', '')}`,
)

const invoiceDate = computed(() => {
  if (!props.rental?.startDate) return '-'
  const d = new Date(String(props.rental.startDate))
  return isNaN(d.getTime()) ? String(props.rental.startDate) : d.toLocaleDateString('en-GB')
})

const dueDate = computed(() => {
  if (!props.rental?.dueDate) return '-'
  const d = new Date(String(props.rental.dueDate))
  return isNaN(d.getTime()) ? String(props.rental.dueDate) : d.toLocaleDateString('en-GB')
})

const charges = computed(() => {
  if (!props.rental) return []
  return store.list('rentalCharges').filter(row => String(row.rentalId || '') === String(props.rental!.id))
})

interface LineItem {
  qty: number
  description: string
  unitPrice: number
  amount: number
}

const lineItems = computed<LineItem[]>(() => {
  if (!props.rental) return []
  const items: LineItem[] = []

  const rateType = String(props.rental.rateType || 'Daily')
  const duration = Number(props.rental.durationDays || 0)
  const rateAmount = Number(props.rental.rateAmount || 0)
  const rentalCharge = Number(props.rental.rentalCharge || 0)
  const moto = String(props.rental.motorcycle || '')
  const plate = String(props.rental.plate || '')

  if (rentalCharge > 0) {
    items.push({
      qty: duration > 0 ? duration : 1,
      description: `ថ្លៃជួល (${rateType}) / Rental Charge (${rateType}) — ${moto}${plate ? ` (${plate})` : ''}`,
      unitPrice: rateAmount,
      amount: rentalCharge,
    })
  }

  const lateFee = Number(props.rental.lateFee || 0)
  if (lateFee > 0) {
    items.push({
      qty: 1,
      description: 'ថ្លៃយឺត / Late Fee',
      unitPrice: lateFee,
      amount: lateFee,
    })
  }

  for (const charge of charges.value) {
    const amt = Number(charge.amount || 0)
    if (amt > 0) {
      items.push({
        qty: 1,
        description: `${String(charge.chargeType || '')}${charge.description ? ` — ${String(charge.description)}` : ''}`,
        unitPrice: amt,
        amount: amt,
      })
    }
  }

  const discount = Number(props.rental.discount || 0)
  if (discount > 0) {
    items.push({
      qty: 1,
      description: 'បញ្ចុះតម្លៃ / Discount',
      unitPrice: -discount,
      amount: -discount,
    })
  }

  return items
})

const subtotal = computed(() => lineItems.value.reduce((sum, item) => sum + item.amount, 0))
const totalDue = computed(() => Number(props.rental?.totalDue || 0))
const paid = computed(() => Number(props.rental?.paid || 0))
const outstanding = computed(() => Number(props.rental?.outstanding || 0))

const companyName = computed(() => tenant.activeOrganization?.display_name || 'HollyWing Motor')
const companyAddress = computed(() => tenant.activeOrganization?.address || '')
const companyPhone = computed(() => tenant.activeOrganization?.phone || '')
const companyEmail = computed(() => tenant.activeOrganization?.email || '')
</script>

<template>
  <div v-if="rental" class="space-y-5 bg-white p-6 text-sm text-gray-900">
    <!-- Top: Logo + Company (left) | INVOICE title (right) -->
    <div class="flex items-start justify-between">
      <div class="flex items-center gap-3">
        <img
          src="/logo.png"
          alt="Logo"
          class="h-10 w-auto object-contain"
          onerror="this.style.display='none'"
        >
        <div>
          <p class="text-base font-bold">{{ companyName }}</p>
          <p class="text-[11px] text-gray-500">ការជួលម៉ូតូ / Motorcycle Rental</p>
        </div>
      </div>
      <div class="text-right">
        <p class="text-2xl font-bold tracking-widest text-gray-800">វិក្កយបត្រ</p>
        <p class="text-lg font-bold tracking-widest text-gray-600">INVOICE</p>
      </div>
    </div>

    <!-- Bill To (left) | Invoice Meta (right) -->
    <div class="flex justify-between gap-8">
      <div>
        <p class="text-[11px] font-bold uppercase text-gray-700">ជូនពី / Bill To</p>
        <p class="mt-1 text-base font-semibold">{{ rental.customer }}</p>
        <p v-if="rental.phone" class="text-xs text-gray-500">{{ rental.phone }}</p>
      </div>
      <div class="min-w-[260px]">
        <table class="w-full text-sm">
          <tbody>
            <tr>
              <td class="py-0.5 pr-4 text-right font-semibold text-gray-700">
                <div>លេខវិក្កយបត្រ</div>
                <div class="text-[10px] font-normal text-gray-500">Invoice No.</div>
              </td>
              <td class="py-0.5 text-right">{{ invoiceNo }}</td>
            </tr>
            <tr>
              <td class="py-0.5 pr-4 text-right font-semibold text-gray-700">
                <div>កាលបរិច្ឆេទវិក្កយបត្រ</div>
                <div class="text-[10px] font-normal text-gray-500">Invoice date</div>
              </td>
              <td class="py-0.5 text-right">{{ invoiceDate }}</td>
            </tr>
            <tr>
              <td class="py-0.5 pr-4 text-right font-semibold text-gray-700">
                <div>ថ្ងៃផុតកំណត់</div>
                <div class="text-[10px] font-normal text-gray-500">Due Date</div>
              </td>
              <td class="py-0.5 text-right">{{ dueDate }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Line Items Table -->
    <table class="w-full border-collapse border border-gray-400 text-sm">
      <thead>
        <tr class="bg-gray-100">
          <th class="border border-gray-400 px-2 py-2 text-center text-xs font-semibold">
            <div>ល.រ</div>
            <div class="text-[10px] font-normal text-gray-600">Nº</div>
          </th>
          <th class="border border-gray-400 px-3 py-2 text-center text-xs font-semibold">
            <div>បរិយាយ</div>
            <div class="text-[10px] font-normal text-gray-600">Description</div>
          </th>
          <th class="border border-gray-400 px-3 py-2 text-center text-xs font-semibold">
            <div>បរិមាណ</div>
            <div class="text-[10px] font-normal text-gray-600">Quantity</div>
          </th>
          <th class="border border-gray-400 px-3 py-2 text-center text-xs font-semibold">
            <div>តម្លៃឯកតា</div>
            <div class="text-[10px] font-normal text-gray-600">Unit Price</div>
          </th>
          <th class="border border-gray-400 px-3 py-2 text-center text-xs font-semibold">
            <div>ចំនួនទឹកប្រាក់</div>
            <div class="text-[10px] font-normal text-gray-600">Amount</div>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(item, idx) in lineItems" :key="idx">
          <td class="border border-gray-400 px-2 py-2 text-center tabular-nums">{{ idx + 1 }}</td>
          <td class="border border-gray-400 px-3 py-2">{{ item.description }}</td>
          <td class="border border-gray-400 px-3 py-2 text-center tabular-nums">{{ item.qty.toFixed(2) }}</td>
          <td class="border border-gray-400 px-3 py-2 text-right tabular-nums">{{ money(item.unitPrice) }}</td>
          <td class="border border-gray-400 px-3 py-2 text-right tabular-nums">{{ money(item.amount) }}</td>
        </tr>
        <template v-if="lineItems.length < 4">
          <tr v-for="n in (4 - lineItems.length)" :key="`spacer-${n}`">
            <td class="border border-gray-400 px-2 py-4">&nbsp;</td>
            <td class="border border-gray-400 px-3 py-4">&nbsp;</td>
            <td class="border border-gray-400 px-3 py-4">&nbsp;</td>
            <td class="border border-gray-400 px-3 py-4">&nbsp;</td>
            <td class="border border-gray-400 px-3 py-4">&nbsp;</td>
          </tr>
        </template>
      </tbody>
    </table>

    <!-- Bottom: Terms + Location (left) | Summary (right) -->
    <div class="flex justify-between gap-8 pt-2">
      <div class="max-w-[50%] space-y-4">
        <div>
          <p class="text-[11px] font-bold uppercase text-gray-700">លក្ខខណ្ឌ / Terms and Conditions</p>
          <p class="mt-1 text-xs text-gray-500">
            ត្រូវបង់ប្រាក់នៅពេលប្រគល់ម៉ូតូ។ ប្រាក់កក់នឹងត្រូវប្រគល់វិញនៅពេលត្រួតពិនិត្យរួចរាល់។
            <br>
            Payment is due on return. Deposit is refundable upon satisfactory inspection.
          </p>
        </div>
        <div>
          <p class="text-[11px] font-bold uppercase text-gray-700">ទីតាំង / Location</p>
          <p v-if="companyAddress" class="mt-1 text-xs text-gray-500">{{ companyAddress }}</p>
          <p v-if="companyPhone" class="text-xs text-gray-500">{{ companyPhone }}</p>
          <p v-if="companyEmail" class="text-xs text-gray-500">{{ companyEmail }}</p>
        </div>
      </div>

      <div class="min-w-[260px]">
        <table class="w-full text-sm">
          <tbody>
            <tr>
              <td class="py-1 pr-4 text-right">
                <div>សរុបរង</div>
                <div class="text-[10px] text-gray-500">Subtotal</div>
              </td>
              <td class="py-1 text-right tabular-nums">{{ money(subtotal) }}</td>
            </tr>
            <tr class="border-b border-gray-300">
              <td class="py-1 pr-4 text-right">
                <div>ពន្ធលក់</div>
                <div class="text-[10px] text-gray-500">Sales Tax</div>
              </td>
              <td class="py-1 text-right tabular-nums">{{ money(0) }}</td>
            </tr>
            <tr class="font-bold">
              <td class="py-2 pr-4 text-right">
                <div>សរុប</div>
                <div class="text-[10px] font-normal text-gray-500">Total ({{ currencyCode }})</div>
              </td>
              <td class="py-2 text-right tabular-nums">{{ money(totalDue) }}</td>
            </tr>
            <tr>
              <td class="py-1 pr-4 text-right">
                <div>បានបង់រួច</div>
                <div class="text-[10px] text-gray-500">Already Paid</div>
              </td>
              <td class="py-1 text-right tabular-nums">{{ money(paid) }}</td>
            </tr>
            <tr class="border-t-2 border-gray-800 font-bold">
              <td class="py-2 pr-4 text-right">
                <div>នៅជំពាក់</div>
                <div class="text-[10px] font-normal text-gray-500">Outstanding</div>
              </td>
              <td class="py-2 text-right tabular-nums">{{ money(outstanding) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
