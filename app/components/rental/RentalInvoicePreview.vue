<script setup lang="ts">
const props = defineProps<{
  rental: Record<string, unknown> | null
}>()

const emit = defineEmits<{ close: [] }>()

const { t, te } = useI18n()
const preferences = usePreferencesStore()

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

const money = (value: unknown) => formatMoney(value, String(props.rental?.currency || preferences.currency))

const store = useFreightStore()

const payments = computed(() => {
  if (!props.rental) return []
  return store.list('rentalPayments').filter(row => String(row.rentalId || '') === String(props.rental!.id))
})
const charges = computed(() => {
  if (!props.rental) return []
  return store.list('rentalCharges').filter(row => String(row.rentalId || '') === String(props.rental!.id))
})

const invoiceNo = computed(() =>
  `INV-${String(props.rental?.rentalNo || '').replace('RNT-', '')}`,
)

const isOpen = computed({
  get: () => props.rental !== null,
  set: (value: boolean) => { if (!value) emit('close') },
})

function printInvoice() {
  window.print()
}

watch(() => props.rental !== null, (open) => {
  if (import.meta.client) document.body.classList.toggle('rental-invoice-open', open)
})

onBeforeUnmount(() => {
  if (import.meta.client) document.body.classList.remove('rental-invoice-open')
})
</script>

<template>
  <UModal
    v-model:open="isOpen"
    :ui="{ content: 'rental-invoice-print' }"
  >
    <template #header>
      <div class="flex w-full items-center justify-between">
        <div>
          <p class="text-xs uppercase tracking-wide text-muted">{{ tx('rental.ui.invoice', 'Invoice') }}</p>
          <p class="text-lg font-semibold">{{ invoiceNo }}</p>
        </div>
        <div class="flex gap-2 print:hidden">
          <UButton color="neutral" variant="ghost" icon="i-lucide-printer" :label="tx('rental.ui.print', 'Print')" @click="printInvoice" />
          <UButton color="neutral" variant="ghost" icon="i-lucide-file-down" :label="tx('rental.ui.savePdf', 'Save PDF')" @click="printInvoice" />
          <UButton color="neutral" variant="ghost" icon="i-lucide-x" :label="tx('common.actions.close', 'Close')" @click="emit('close')" />
        </div>
      </div>
    </template>

    <template #body>
      <div v-if="rental" class="space-y-5 text-sm">
        <div class="flex items-start justify-between border-b border-default pb-4">
          <div>
            <p class="text-base font-bold">HollyWing Motor</p>
            <p class="text-xs text-muted">Motorcycle Rental</p>
          </div>
          <div class="text-end">
            <p class="font-medium">{{ tx('rental.ui.rentalNo', 'Rental Number') }}: {{ rental.rentalNo }}</p>
            <p class="text-xs text-muted">{{ new Date().toISOString().slice(0, 10) }}</p>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <p class="text-xs uppercase text-muted">{{ tx('rental.ui.customer', 'Customer') }}</p>
            <p class="font-medium">{{ rental.customer }}</p>
            <p class="text-muted">{{ rental.phone }}</p>
          </div>
          <div>
            <p class="text-xs uppercase text-muted">{{ tx('rental.ui.motorcycle', 'Motorcycle') }}</p>
            <p class="font-medium">{{ rental.motorcycle }}</p>
            <p class="text-muted">{{ rental.plate }}</p>
          </div>
          <div>
            <p class="text-xs uppercase text-muted">{{ tx('rental.ui.startDate', 'Start') }}</p>
            <p>{{ rental.startDate }}</p>
          </div>
          <div>
            <p class="text-xs uppercase text-muted">{{ tx('rental.ui.returnDate', 'Return') }}</p>
            <p>{{ rental.returnDate || rental.dueDate }} <span v-if="!rental.returnDate" class="text-warning">({{ tx('rental.ui.dueDate', 'Due') }})</span></p>
          </div>
        </div>

        <table class="w-full border-t border-default pt-3 text-sm">
          <tbody>
            <tr><td class="py-1">{{ tx('rental.ui.rentalCharge', 'Rental Charge') }}</td><td class="py-1 text-end tabular-nums">{{ money(rental.rentalCharge) }}</td></tr>
            <tr><td class="py-1">{{ tx('rental.ui.lateFee', 'Late Fee') }}</td><td class="py-1 text-end tabular-nums">{{ money(rental.lateFee) }}</td></tr>
            <tr><td class="py-1">{{ tx('rental.ui.additionalCharges', 'Additional Charges') }}</td><td class="py-1 text-end tabular-nums">{{ money(rental.additionalCharges) }}</td></tr>
            <tr><td class="py-1">{{ tx('rental.ui.discount', 'Discount') }}</td><td class="py-1 text-end tabular-nums">-{{ money(rental.discount) }}</td></tr>
            <tr class="border-t border-default font-semibold"><td class="py-1.5">{{ tx('rental.ui.totalDue', 'Total') }}</td><td class="py-1.5 text-end tabular-nums">{{ money(rental.totalDue) }}</td></tr>
            <tr><td class="py-1">{{ tx('rental.ui.alreadyPaid', 'Paid') }}</td><td class="py-1 text-end tabular-nums">{{ money(rental.paid) }}</td></tr>
            <tr class="font-semibold"><td class="py-1">{{ tx('rental.ui.outstanding', 'Outstanding') }}</td><td class="py-1 text-end tabular-nums">{{ money(rental.outstanding) }}</td></tr>
          </tbody>
        </table>

        <div v-if="payments.length" class="border-t border-default pt-3">
          <p class="mb-1 text-xs uppercase text-muted">{{ tx('rental.ui.paymentHistory', 'Payment history') }}</p>
          <ul class="space-y-1">
            <li v-for="payment in payments" :key="String(payment.id)" class="flex justify-between">
              <span class="text-muted">{{ payment.paidAt }} · {{ payment.paymentMethod }}<template v-if="payment.reference"> · {{ payment.reference }}</template></span>
              <span class="tabular-nums">{{ money(payment.amount) }}</span>
            </li>
          </ul>
        </div>

        <div v-if="charges.length" class="border-t border-default pt-3">
          <p class="mb-1 text-xs uppercase text-muted">{{ tx('rental.ui.additionalCharges', 'Additional charges') }}</p>
          <ul class="space-y-1">
            <li v-for="charge in charges" :key="String(charge.id)" class="flex justify-between">
              <span class="text-muted">{{ charge.chargeType }}<template v-if="charge.description"> · {{ charge.description }}</template></span>
              <span class="tabular-nums">{{ money(charge.amount) }}</span>
            </li>
          </ul>
        </div>
      </div>
    </template>
  </UModal>
</template>
