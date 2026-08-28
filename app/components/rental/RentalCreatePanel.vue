<script setup lang="ts">
import { useConfirm } from '~/composables/common/useConfirm'
import { formatMoney } from '~/composables/freight/useFreight'
const emit = defineEmits<{ cancel: [], created: [id: string] }>()

const { t, te } = useI18n()
const store = useFreightStore()
const preferences = usePreferencesStore()
const { confirm } = useConfirm()
const toast = useToast()

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

const customers = computed(() => store.list('rentalCustomers').filter(row => String(row.status || 'Active') === 'Active'))
const availableMotorcycles = computed(() => store.list('motorcycles').filter(row => String(row.status) === 'Available'))

const customerId = ref('')
const motorcycleId = ref('')
const startDate = ref(new Date().toISOString().slice(0, 16))
const dueDate = ref('')
const rateType = ref<'Daily' | 'Monthly'>('Daily')
const rateAmount = ref(0)
const deposit = ref(0)
const discount = ref(0)
const note = ref('')
const saving = ref(false)

const selectedCustomer = computed(() => customers.value.find(row => String(row.id) === customerId.value) || null)
const selectedMotorcycle = computed(() => availableMotorcycles.value.find(row => String(row.id) === motorcycleId.value) || null)

watch(selectedMotorcycle, (moto) => {
  if (!moto) return
  rateType.value = 'Daily'
  rateAmount.value = Number(moto.dailyRate || 0)
  deposit.value = Math.max(Math.round(Number(moto.dailyRate || 0) * 10), 50)
})

const durationDays = computed(() => {
  if (!startDate.value || !dueDate.value) return 0
  const ms = new Date(dueDate.value).getTime() - new Date(startDate.value).getTime()
  if (!Number.isFinite(ms) || ms <= 0) return 0
  if (rateType.value === 'Monthly') return Math.ceil(ms / (30 * 86400000))
  return Math.max(Math.ceil(ms / 86400000), 1)
})

const estimatedCharge = computed(() => durationDays.value * Number(rateAmount.value || 0))

const canCreate = computed(() => Boolean(
  customerId.value
  && motorcycleId.value
  && startDate.value
  && dueDate.value
  && rateAmount.value > 0,
))

function nextRentalNo() {
  const numbers = store.list('rentals')
    .map(row => String(row.rentalNo || ''))
    .map(no => Number(no.split('-').pop()))
    .filter(no => Number.isFinite(no))
  const next = (numbers.length ? Math.max(...numbers) : 0) + 1
  return `RNT-${new Date().getFullYear()}-${String(next).padStart(6, '0')}`
}

async function createRental() {
  if (!canCreate.value || !selectedCustomer.value || !selectedMotorcycle.value) return
  const ok = await confirm({
    kind: 'generic',
    title: tx('rental.ui.confirmCreate', 'Create this rental?'),
    description: `${selectedCustomer.value.fullName} · ${selectedMotorcycle.value.model} (${selectedMotorcycle.value.plate}) · ${tx('rental.ui.estimate', 'Estimated charge')}: ${formatMoney(estimatedCharge.value, selectedMotorcycle.value.currency || preferences.currency)}`,
    confirmLabel: tx('rental.ui.createRental', 'Create Rental'),
  })
  if (!ok) return
  saving.value = true
  try {
    const created = store.create('rentals', {
      rentalNo: nextRentalNo(),
      customerId: selectedCustomer.value.id,
      customer: selectedCustomer.value.fullName,
      phone: selectedCustomer.value.phone,
      motorcycleId: selectedMotorcycle.value.id,
      motorcycle: selectedMotorcycle.value.model,
      plate: selectedMotorcycle.value.plate,
      startDate: startDate.value,
      dueDate: dueDate.value,
      rateType: rateType.value,
      rateAmount: rateAmount.value,
      deposit: deposit.value,
      discount: discount.value,
      currency: selectedMotorcycle.value.currency || preferences.currency,
      rentalCharge: estimatedCharge.value,
      lateFee: 0,
      additionalCharges: 0,
      totalDue: total,
      paid: 0,
      outstanding: total,
      note: note.value,
      createdBy: store.session()?.name || '',
      status: 'Active',
    }, 'rt')
    store.save('motorcycles', { ...selectedMotorcycle.value, status: 'Rented' })
    store.addAudit(`Created rental ${created.rentalNo}`, 'Rentals', String(created.rentalNo))
    toast.add({ title: tx('rental.ui.rentalCreated', 'Rental created'), color: 'success' })
    emit('created', String(created.id))
  }
  finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-muted/20">
    <LayoutAppHeaderPageActions
      :show-save="canCreate"
      :save-label="tx('rental.ui.createRental', 'Create Rental')"
      :saving="saving"
      :show-cancel="true"
      cancel-to="/rentals"
      @save="createRental"
      @cancel="emit('cancel')"
    />

    <div class="mx-auto grid w-full max-w-6xl flex-1 grid-cols-1 gap-6 overflow-y-auto p-6 lg:grid-cols-3">
      <div class="space-y-4 lg:col-span-2">
        <section class="rounded-lg border border-default bg-default p-5">
          <h2 class="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">{{ tx('rental.ui.customer', 'Customer') }}</h2>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.selectCustomer', 'Select customer') }} <span class="text-error">*</span></label>
              <USelect
                v-model="customerId"
                :items="customers.map(row => ({ label: `${row.fullName} · ${row.phone}`, value: String(row.id) }))"
                placeholder="—"
                class="w-full"
              />
            </div>
            <div class="flex items-end">
              <UButton
                color="neutral"
                variant="soft"
                size="sm"
                icon="i-lucide-user-plus"
                :label="tx('rental.ui.addNewCustomer', 'Add new customer')"
                @click="navigateTo('/customers/new')"
              />
            </div>
          </div>
        </section>

        <section class="rounded-lg border border-default bg-default p-5">
          <h2 class="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">{{ tx('rental.ui.motorcycle', 'Motorcycle') }}</h2>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div class="sm:col-span-2">
              <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.selectMotorcycle', 'Select motorcycle (Available only)') }} <span class="text-error">*</span></label>
              <USelect
                v-model="motorcycleId"
                :items="availableMotorcycles.map(row => ({ label: `${row.code} · ${row.model} · ${row.plate}`, value: String(row.id) }))"
                placeholder="—"
                class="w-full"
              />
            </div>
          </div>
        </section>

        <section class="rounded-lg border border-default bg-default p-5">
          <h2 class="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">{{ tx('rental.ui.rentalSection', 'Rental') }}</h2>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.startDate', 'Start datetime') }} <span class="text-error">*</span></label>
              <UInput v-model="startDate" type="datetime-local" class="w-full" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.dueDate', 'Due datetime') }} <span class="text-error">*</span></label>
              <UInput v-model="dueDate" type="datetime-local" class="w-full" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.rateType', 'Rate type') }} <span class="text-error">*</span></label>
              <USelect v-model="rateType" :items="['Daily', 'Monthly']" class="w-full" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.rateAmount', 'Rate amount') }} <span class="text-error">*</span></label>
              <UInput v-model.number="rateAmount" type="number" min="0" class="w-full" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.deposit', 'Deposit') }}</label>
              <UInput v-model.number="deposit" type="number" min="0" class="w-full" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.discount', 'Discount') }}</label>
              <UInput v-model.number="discount" type="number" min="0" class="w-full" />
            </div>
            <div class="sm:col-span-2">
              <label class="mb-1 block text-sm font-medium">{{ tx('rental.ui.note', 'Note') }}</label>
              <UTextarea v-model="note" :rows="2" class="w-full" />
            </div>
          </div>
        </section>
      </div>

      <!-- Summary side panel -->
      <aside class="h-fit space-y-3 rounded-lg border border-default bg-default p-5 lg:sticky lg:top-0">
        <h2 class="text-sm font-semibold uppercase tracking-wide text-muted">{{ tx('rental.ui.summary', 'Summary') }}</h2>
        <dl class="space-y-2 text-sm">
          <div class="flex justify-between gap-3">
            <dt class="text-muted">{{ tx('rental.ui.motorcycle', 'Motorcycle') }}</dt>
            <dd class="text-end font-medium">{{ selectedMotorcycle ? `${selectedMotorcycle.model} · ${selectedMotorcycle.plate}` : '—' }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-muted">{{ tx('rental.ui.rateType', 'Rate') }}</dt>
            <dd class="text-end font-medium">{{ rateType }} · {{ formatMoney(rateAmount, selectedMotorcycle?.currency || preferences.currency) }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-muted">{{ tx('rental.ui.duration', 'Estimated duration') }}</dt>
            <dd class="text-end font-medium">{{ durationDays }} {{ tx('rental.ui.days', durationDays === 1 ? 'day' : 'days') }}</dd>
          </div>
          <div class="flex justify-between gap-3 border-t border-default pt-2">
            <dt class="text-muted">{{ tx('rental.ui.estimate', 'Estimated charge') }}</dt>
            <dd class="text-end text-base font-semibold">{{ formatMoney(estimatedCharge, selectedMotorcycle?.currency || preferences.currency) }}</dd>
          </div>
          <div class="flex justify-between gap-3">
            <dt class="text-muted">{{ tx('rental.ui.deposit', 'Deposit') }}</dt>
            <dd class="text-end font-medium">{{ formatMoney(deposit, selectedMotorcycle?.currency || preferences.currency) }}</dd>
          </div>
        </dl>
        <div class="flex flex-col gap-2 pt-2">
          <UButton
            block
            :loading="saving"
            :disabled="!canCreate"
            icon="i-lucide-check"
            :label="tx('rental.ui.createRental', 'Create Rental')"
            @click="createRental"
          />
          <UButton
            block
            color="neutral"
            variant="ghost"
            :label="tx('common.actions.cancel', 'Cancel')"
            @click="emit('cancel')"
          />
        </div>
      </aside>
    </div>
  </div>
</template>
