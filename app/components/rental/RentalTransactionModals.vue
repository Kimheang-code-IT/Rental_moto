<script setup lang="ts">
import { formatMoney } from '~/composables/module/useModule'
import { PAYMENT_METHODS, RENTAL_CHARGE_TYPES } from '~/config/rental-options'

const props = defineProps<{
  rental: Record<string, unknown>
}>()

const open = defineModel<boolean>('open', { default: true })

const emit = defineEmits<{
  close: []
  saved: [title: string]
}>()

const { t, te } = useI18n()
const auth = useAuthStore()
const store = useAppDataStore()
const toast = useToast()
const preferences = usePreferencesStore()

function staffName() {
  return auth.user?.name || 'Staff'
}

const isOpen = computed({
  get: () => open.value,
  set: (value: boolean) => {
    open.value = value
    if (!value) emit('close')
  },
})

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

function help(key: string, fallback: string) {
  return te(`rental.fieldHelp.${key}`) ? String(t(`rental.fieldHelp.${key}`)) : fallback
}

const money = (value: unknown) => formatMoney(value, String(props.rental.currency || preferences.currency))

const returnAt = ref(new Date().toISOString().slice(0, 16))

interface ReturnChargeLine {
  key: string
  chargeType: (typeof RENTAL_CHARGE_TYPES)[number]
  description: string
  amount: number
}
let chargeSeq = 1
const returnCharges = ref<ReturnChargeLine[]>([])

const returnPaymentMethod = ref<(typeof PAYMENT_METHODS)[number]>(PAYMENT_METHODS[0])
const returnPaidAmount = ref(0)
const saving = ref(false)

const returnChargesTotal = computed(() =>
  returnCharges.value.reduce((sum, row) => sum + Math.max(0, Number(row.amount) || 0), 0),
)

const balanceDueBeforePay = computed(() =>
  Math.max(Number(props.rental.outstanding || 0) + returnChargesTotal.value, 0),
)

const projectedOutstanding = computed(() => {
  const base = Number(props.rental.outstanding || 0)
  return Math.max(base + returnChargesTotal.value - returnPaidAmount.value, 0)
})

const projectedTotalDue = computed(() => {
  const rentalCharge = Number(props.rental.rentalCharge || 0)
  const lateFee = Number(props.rental.lateFee || 0)
  const additional = Number(props.rental.additionalCharges || 0) + returnChargesTotal.value
  const discount = Number(props.rental.discount || 0)
  return Math.max(rentalCharge + lateFee + additional - discount, 0)
})

/** Keep return payment amount = outstanding + all charge lines. */
watch(balanceDueBeforePay, (due) => {
  returnPaidAmount.value = Number(due.toFixed(2))
}, { immediate: true })

function resetForm() {
  returnAt.value = new Date().toISOString().slice(0, 16)
  returnPaymentMethod.value = PAYMENT_METHODS[0]
  returnCharges.value = []
  chargeSeq = 1
  returnPaidAmount.value = Number((Number(props.rental.outstanding || 0)).toFixed(2))
}

watch(open, (isOpenNow) => {
  if (isOpenNow) resetForm()
}, { immediate: true })

function recomputeRental(rental: Record<string, unknown>, paidDelta = 0, chargeDelta = 0) {
  const paid = Number(rental.paid || 0) + paidDelta
  const additional = Number(rental.additionalCharges || 0) + chargeDelta
  const totalDue = Number(rental.rentalCharge || 0) + Number(rental.lateFee || 0) + additional - Number(rental.discount || 0)
  return {
    ...rental,
    id: String(rental.id),
    paid,
    additionalCharges: additional,
    totalDue,
    outstanding: Math.max(totalDue - paid, 0),
  }
}

function addReturnChargeLine() {
  returnCharges.value.push({
    key: `rc-${chargeSeq++}`,
    chargeType: RENTAL_CHARGE_TYPES[0],
    description: '',
    amount: 0,
  })
}

function removeReturnChargeLine(key: string) {
  returnCharges.value = returnCharges.value.filter(row => row.key !== key)
}

function saveClose() {
  const invalidCharge = returnCharges.value.some(row => row.amount > 0 && !row.chargeType)
  if (invalidCharge) return
  if (returnPaidAmount.value > balanceDueBeforePay.value + 0.001) return

  saving.value = true
  try {
    let chargeDelta = 0
    for (const row of returnCharges.value) {
      const amt = Math.max(0, Number(row.amount) || 0)
      if (amt <= 0) continue
      const seq = store.list('rentalCharges').length + 1
      store.create('rentalCharges', {
        chargeNo: `RNC-${String(seq).padStart(6, '0')}`,
        rentalId: props.rental.id,
        rentalNo: props.rental.rentalNo,
        customer: props.rental.customer,
        chargeType: row.chargeType,
        description: row.description,
        amount: amt,
        currency: props.rental.currency || preferences.currency,
        chargeToCustomer: 'Yes',
        createdBy: staffName(),
      }, 'rgc')
      chargeDelta += amt
    }

    let paidDelta = 0
    if (returnPaidAmount.value > 0) {
      paidDelta = returnPaidAmount.value
      const seq = store.list('rentalPayments').length + 1
      store.create('rentalPayments', {
        paymentNo: `RNP-${String(seq).padStart(6, '0')}`,
        rentalId: props.rental.id,
        rentalNo: props.rental.rentalNo,
        customer: props.rental.customer,
        amount: paidDelta,
        currency: props.rental.currency || preferences.currency,
        paymentMethod: returnPaymentMethod.value,
        paidAt: returnAt.value,
        reference: '',
        note: tx('rental.ui.paymentOnReturn', 'Payment on return'),
      }, 'rnp')
    }

    const updated = {
      ...recomputeRental(props.rental, paidDelta, chargeDelta),
      ...(paidDelta > 0 ? { paymentMethod: returnPaymentMethod.value } : {}),
      status: 'Completed',
      returnDate: returnAt.value,
    }
    store.save('rentals', updated)
    const motorcycle = store.get('motorcycles', String(props.rental.motorcycleId || ''))
    if (motorcycle) store.save('motorcycles', { ...motorcycle, status: 'Available' })
    store.addAudit('Rental closed', 'Rentals', String(props.rental.rentalNo))
    toast.add({ title: tx('rental.ui.rentalClosed', 'Rental closed'), color: 'success' })
    emit('saved', tx('rental.ui.rentalClosed', 'Rental closed'))
  }
  finally {
    saving.value = false
  }
}

const canConfirmClose = computed(() => Boolean(returnAt.value))
</script>

<template>
  <UModal
    v-model:open="isOpen"
    :title="tx('rental.ui.closeRental', 'Return / Close')"
    :ui="{ content: 'w-[50vw] max-w-[50vw] sm:max-w-[50vw]' }"
  >
    <template #body>
      <div class="space-y-4">
        <div class="grid grid-cols-3 gap-2 rounded-md bg-elevated/60 p-3 text-sm">
          <div>
            <p class="text-xs text-muted">{{ tx('rental.ui.totalDue', 'Total Due') }}</p>
            <p class="font-semibold">{{ money(projectedTotalDue) }}</p>
          </div>
          <div>
            <p class="text-xs text-muted">{{ tx('rental.ui.alreadyPaid', 'Already Paid') }}</p>
            <p class="font-semibold">{{ money(Number(rental.paid || 0) + returnPaidAmount) }}</p>
          </div>
          <div>
            <p class="text-xs text-muted">{{ tx('rental.ui.outstanding', 'Outstanding') }}</p>
            <p class="font-semibold" :class="projectedOutstanding > 0 ? 'text-warning' : 'text-success'">
              {{ money(projectedOutstanding) }}
            </p>
          </div>
        </div>

        <UFormField :label="tx('rental.ui.actualReturn', 'Actual Return')" :help="help('returnAt', 'Actual date and time the motorcycle was returned.')" required>
          <UInput
v-model="returnAt"
type="datetime-local"
size="md"
class="w-full max-w-sm" />
        </UFormField>

        <div>
          <div class="mb-2 flex items-center justify-between gap-2">
            <p class="text-sm font-semibold">{{ tx('rental.ui.returnCharges', 'Return charges / fines') }}</p>
            <UButton
              size="xs"
              variant="soft"
              icon="i-lucide-plus"
              :label="tx('rental.ui.addChargeLine', 'Add charge')"
              @click="addReturnChargeLine"
            />
          </div>
          <p class="mb-2 text-xs text-muted">{{ help('returnCharges', 'Add damage, cleaning, or other fines found on return.') }}</p>
          <div v-if="!returnCharges.length" class="rounded-md border border-dashed border-default px-3 py-4 text-center text-xs text-muted">
            {{ tx('rental.ui.noReturnCharges', 'No return charges') }}
          </div>
          <div v-else class="overflow-x-auto rounded-md border border-default">
            <table class="w-full min-w-md text-sm">
              <thead>
                <tr class="border-b border-default bg-elevated/40 text-left text-xs text-muted">
                  <th class="px-2 py-2 font-medium">{{ tx('rental.ui.chargeType', 'Charge Type') }}</th>
                  <th class="px-2 py-2 font-medium">{{ tx('rental.ui.description', 'Description') }}</th>
                  <th class="px-2 py-2 text-center font-medium">{{ tx('rental.ui.amount', 'Amount') }}</th>
                  <th class="w-8 px-1 py-2" />
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in returnCharges" :key="row.key" class="border-b border-default/70">
                  <td class="px-2 py-1.5">
                    <USelect
v-model="row.chargeType"
:items="[...RENTAL_CHARGE_TYPES]"
size="md"
class="w-36" />
                  </td>
                  <td class="px-2 py-1.5">
                    <UInput v-model="row.description" size="md" class="w-full min-w-40" />
                  </td>
                  <td class="px-2 py-1.5">
                    <UInput
v-model.number="row.amount"
type="number"
min="0"
size="md"
class="w-28 text-center" />
                  </td>
                  <td class="px-1 py-1.5">
                    <UButton
size="xs"
color="neutral"
variant="ghost"
icon="i-lucide-trash-2"
@click="removeReturnChargeLine(row.key)" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="returnChargesTotal > 0" class="mt-2 text-center text-sm">
            {{ tx('rental.ui.chargesTotal', 'Charges total') }}:
            <span class="font-semibold tabular-nums">{{ money(returnChargesTotal) }}</span>
          </p>
        </div>

        <div class="grid grid-cols-2 gap-3 rounded-md border border-default p-3">
          <p class="col-span-2 text-sm font-semibold">{{ tx('rental.ui.paymentOnReturn', 'Payment on return') }}</p>
          <UFormField :label="tx('rental.ui.paymentMethod', 'Payment Method')" :help="help('paymentMethod', 'How the customer pays the remaining balance or fines.')">
            <USelect
v-model="returnPaymentMethod"
:items="[...PAYMENT_METHODS]"
size="md"
class="w-full" />
          </UFormField>
          <UFormField
            :label="tx('rental.ui.amount', 'Amount')"
            :help="help('returnPaidAmountAuto', 'Auto-sums outstanding balance plus all return charges.')"
          >
            <UInput
              :model-value="returnPaidAmount"
              type="number"
              min="0"
              size="md"
              class="w-full"
              disabled
            />
          </UFormField>
          <p class="col-span-2 text-xs text-muted">
            {{ tx('rental.ui.balanceDue', 'Balance due') }}:
            <span class="font-semibold text-highlighted">{{ money(balanceDueBeforePay) }}</span>
            ·
            {{ tx('rental.ui.outstandingAfterPay', 'Outstanding after payment') }}:
            <span class="font-semibold text-highlighted">{{ money(projectedOutstanding) }}</span>
          </p>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :label="tx('common.actions.cancel', 'Cancel')"
          @click="emit('close')"
        />
        <UButton
          :loading="saving"
          :disabled="!canConfirmClose"
          color="warning"
          icon="i-lucide-circle-check"
          :label="tx('rental.ui.confirmClose', 'Confirm Close')"
          @click="saveClose"
        />
      </div>
    </template>
  </UModal>
</template>
