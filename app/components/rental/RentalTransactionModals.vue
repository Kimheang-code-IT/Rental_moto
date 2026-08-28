<script setup lang="ts">
import { formatMoney } from '~/composables/freight/useFreight'
const props = defineProps<{
  rental: Record<string, unknown>
  mode: 'payment' | 'charge' | 'close' | null
}>()

const emit = defineEmits<{
  close: []
  saved: [title: string]
}>()

const { t, te } = useI18n()
const store = useFreightStore()
const toast = useToast()

const isOpen = computed({
  get: () => props.mode !== null,
  set: (value: boolean) => { if (!value) emit('close') },
})
const preferences = usePreferencesStore()

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

const money = (value: unknown) => formatMoney(value, String(props.rental.currency || preferences.currency))

const outstanding = computed(() => Number(props.rental.outstanding || 0))
const amount = ref(0)
const paymentMethod = ref('Cash')
const paidAt = ref(new Date().toISOString().slice(0, 16))
const reference = ref('')
const note = ref('')

const chargeType = ref('Damage')
const description = ref('')
const chargeAmount = ref(0)
const chargeToCustomer = ref(true)

const returnAt = ref(new Date().toISOString().slice(0, 16))
const condition = ref('Good')
const returnNote = ref('')
const nextStatus = ref('Available')

const saving = ref(false)

watch(() => props.mode, (mode) => {
  if (!mode) return
  amount.value = outstanding.value
  chargeAmount.value = 0
  description.value = ''
  chargeType.value = 'Damage'
  chargeToCustomer.value = true
  reference.value = ''
  note.value = ''
  returnNote.value = ''
  condition.value = 'Good'
  nextStatus.value = 'Available'
  returnAt.value = new Date().toISOString().slice(0, 16)
  paidAt.value = new Date().toISOString().slice(0, 16)
})

function recomputeRental(rental: Record<string, unknown>, paidDelta = 0, chargeDelta = 0) {
  const paid = Number(rental.paid || 0) + paidDelta
  const additional = Number(rental.additionalCharges || 0) + chargeDelta
  const totalDue = Number(rental.rentalCharge || 0) + Number(rental.lateFee || 0) + additional - Number(rental.discount || 0)
  return {
    ...rental,
    paid,
    additionalCharges: additional,
    totalDue,
    outstanding: Math.max(totalDue - paid, 0),
  }
}

function savePayment() {
  if (amount.value <= 0) return
  saving.value = true
  try {
    const seq = store.list('rentalPayments').length + 1
    store.create('rentalPayments', {
      paymentNo: `RNP-${String(seq).padStart(6, '0')}`,
      rentalId: props.rental.id,
      rentalNo: props.rental.rentalNo,
      customer: props.rental.customer,
      amount: amount.value,
      currency: props.rental.currency || preferences.currency,
      paymentMethod: paymentMethod.value,
      paidAt: paidAt.value,
      reference: reference.value,
      note: note.value,
    }, 'rnp')
    const updated = recomputeRental(props.rental, amount.value)
    store.save('rentals', updated as FreightRecord)
    store.addAudit(`Payment ${money(amount.value)} recorded`, 'Rentals', String(props.rental.rentalNo))
    toast.add({ title: tx('rental.ui.paymentSaved', 'Payment recorded'), color: 'success' })
    emit('saved', tx('rental.ui.paymentSaved', 'Payment recorded'))
  }
  finally {
    saving.value = false
  }
}

function saveCharge() {
  if (chargeAmount.value <= 0) return
  saving.value = true
  try {
    const seq = store.list('rentalCharges').length + 1
    store.create('rentalCharges', {
      chargeNo: `RNC-${String(seq).padStart(6, '0')}`,
      rentalId: props.rental.id,
      rentalNo: props.rental.rentalNo,
      customer: props.rental.customer,
      chargeType: chargeType.value,
      description: description.value,
      amount: chargeAmount.value,
      currency: props.rental.currency || preferences.currency,
      chargeToCustomer: chargeToCustomer.value ? 'Yes' : 'No',
      createdBy: store.session()?.name || '',
    }, 'rgc')
    const updated = recomputeRental(props.rental, 0, chargeToCustomer.value ? chargeAmount.value : 0)
    store.save('rentals', updated as FreightRecord)
    store.addAudit(`Additional charge ${money(chargeAmount.value)} (${chargeType.value})`, 'Rentals', String(props.rental.rentalNo))
    toast.add({ title: tx('rental.ui.chargeSaved', 'Charge recorded'), color: 'success' })
    emit('saved', tx('rental.ui.chargeSaved', 'Charge recorded'))
  }
  finally {
    saving.value = false
  }
}

function saveClose() {
  saving.value = true
  try {
    const updated = {
      ...recomputeRental(props.rental),
      status: 'Completed',
      returnDate: returnAt.value,
      condition: condition.value,
      returnNote: returnNote.value,
    }
    store.save('rentals', updated as FreightRecord)
    const motorcycle = store.get('motorcycles', String(props.rental.motorcycleId || ''))
    if (motorcycle) store.save('motorcycles', { ...motorcycle, status: nextStatus.value })
    store.addAudit('Rental closed', 'Rentals', String(props.rental.rentalNo))
    toast.add({ title: tx('rental.ui.rentalClosed', 'Rental closed'), color: 'success' })
    emit('saved', tx('rental.ui.rentalClosed', 'Rental closed'))
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <UModal
    v-model:open="isOpen"
    :title="mode === 'payment'
      ? tx('rental.ui.addPayment', 'Add Payment')
      : mode === 'charge'
        ? tx('rental.ui.addCharge', 'Add Charge')
        : tx('rental.ui.closeRental', 'Return / Close')"
  >
    <template #body>
      <div class="space-y-4">
        <div class="grid grid-cols-3 gap-2 rounded-md bg-elevated/60 p-3 text-sm">
          <div>
            <p class="text-xs text-muted">{{ tx('rental.ui.totalDue', 'Total Due') }}</p>
            <p class="font-semibold">{{ money(rental.totalDue) }}</p>
          </div>
          <div>
            <p class="text-xs text-muted">{{ tx('rental.ui.alreadyPaid', 'Already Paid') }}</p>
            <p class="font-semibold">{{ money(rental.paid) }}</p>
          </div>
          <div>
            <p class="text-xs text-muted">{{ tx('rental.ui.outstanding', 'Outstanding') }}</p>
            <p class="font-semibold" :class="Number(rental.outstanding) > 0 ? 'text-warning' : 'text-success'">
              {{ money(rental.outstanding) }}
            </p>
          </div>
        </div>

        <!-- Payment -->
        <div v-if="mode === 'payment'" class="grid grid-cols-2 gap-3">
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.amount', 'Amount') }} <span class="text-error">*</span></label>
            <UInput v-model.number="amount" type="number" min="0" class="w-full" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.paymentMethod', 'Payment Method') }}</label>
            <USelect v-model="paymentMethod" :items="['Cash', 'Bank Transfer', 'Card', 'QR Payment']" class="w-full" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.paidAt', 'Paid Date/Time') }}</label>
            <UInput v-model="paidAt" type="datetime-local" class="w-full" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.reference', 'Reference') }}</label>
            <UInput v-model="reference" class="w-full" />
          </div>
          <div class="col-span-2">
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.note', 'Note') }}</label>
            <UTextarea v-model="note" :rows="2" class="w-full" />
          </div>
        </div>

        <!-- Charge -->
        <div v-else-if="mode === 'charge'" class="grid grid-cols-2 gap-3">
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.chargeType', 'Charge Type') }} <span class="text-error">*</span></label>
            <USelect v-model="chargeType" :items="['Damage', 'Lost item', 'Cleaning', 'Other']" class="w-full" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.amount', 'Amount') }} <span class="text-error">*</span></label>
            <UInput v-model.number="chargeAmount" type="number" min="0" class="w-full" />
          </div>
          <div class="col-span-2">
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.description', 'Description') }}</label>
            <UInput v-model="description" class="w-full" />
          </div>
          <div class="col-span-2 flex items-center gap-2">
            <USwitch v-model="chargeToCustomer" />
            <span class="text-sm">{{ tx('rental.ui.chargeToCustomer', 'Charge to customer') }}</span>
          </div>
        </div>

        <!-- Close -->
        <div v-else class="grid grid-cols-2 gap-3">
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.actualReturn', 'Actual Return') }} <span class="text-error">*</span></label>
            <UInput v-model="returnAt" type="datetime-local" class="w-full" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.condition', 'Motorcycle Condition') }}</label>
            <USelect v-model="condition" :items="['Good', 'Minor issues', 'Damaged']" class="w-full" />
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.nextStatus', 'Next Motorcycle Status') }}</label>
            <USelect v-model="nextStatus" :items="['Available', 'Maintenance']" class="w-full" />
          </div>
          <div class="col-span-2">
            <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.returnNote', 'Return Note') }}</label>
            <UTextarea v-model="returnNote" :rows="2" class="w-full" />
          </div>
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
          v-if="mode === 'payment'"
          :loading="saving"
          :disabled="amount <= 0"
          icon="i-lucide-hand-coins"
          :label="tx('rental.ui.savePayment', 'Save Payment')"
          @click="savePayment"
        />
        <UButton
          v-else-if="mode === 'charge'"
          :loading="saving"
          :disabled="chargeAmount <= 0"
          icon="i-lucide-receipt"
          :label="tx('rental.ui.saveCharge', 'Save Charge')"
          @click="saveCharge"
        />
        <UButton
          v-else
          :loading="saving"
          color="warning"
          icon="i-lucide-circle-check"
          :label="tx('rental.ui.confirmClose', 'Confirm Close')"
          @click="saveClose"
        />
      </div>
    </template>
  </UModal>
</template>
