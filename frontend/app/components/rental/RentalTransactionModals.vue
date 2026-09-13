<script setup lang="ts">
import { useConfirm } from '~/composables/common/useConfirm'
import { formatMoney } from '~/composables/module/useModule'
import { PAYMENT_METHODS, RENTAL_CHARGE_TYPES } from '~/config/rental-options'
import { useCreatableOptionList } from '~/composables/rental/useCreatableOptionList'
import { toIsoZonedOrNow } from '~/utils/api/datetime'
import {
  DEFAULT_USD_KHR_RATE,
  fromRentalCurrencyAmount,
  invoiceKhrAmounts,
  normalizeExchangeRate,
  normalizePaymentCurrency,
  toRentalCurrencyAmount,
  type PaymentCurrency,
} from '~/utils/rental/fx'
import { rentalReturnBalance } from '~/utils/rental/pricing'
import { useRentalCommands } from '~/repositories/index'

const props = defineProps<{
  rental: Record<string, unknown>
}>()

const open = defineModel<boolean>('open', { default: true })

const emit = defineEmits<{
  close: []
  saved: [title: string]
}>()

const { t, te } = useI18n()
const store = useAppDataStore()
const toast = useToast()
const preferences = usePreferencesStore()
const rentalCommands = useRentalCommands()
const { confirm } = useConfirm()


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

const money = (value: unknown) => formatMoney(value, String(props.rental.currency || preferences.currency))

function moneyBoth(value: unknown, khrOverride?: number) {
  const amount = Math.max(0, Number(value) || 0)
  const primary = money(amount)
  if (!showKhrTotals.value) return primary
  const khr = khrOverride != null
    ? Math.max(0, Math.round(khrOverride))
    : fromRentalCurrencyAmount(
      amount,
      'KHR',
      rentalCurrencyCode.value,
      returnExchangeRate.value,
    )
  return `${primary} · ${formatMoney(khr, 'KHR')}`
}

const returnAt = ref(new Date().toISOString().slice(0, 16))

interface ReturnChargeLine {
  key: string
  chargeType: string
  description: string
  amount: number
}
let chargeSeq = 1
const returnCharges = ref<ReturnChargeLine[]>([])

const chargeTypeOptions = useCreatableOptionList(RENTAL_CHARGE_TYPES)
const paymentMethodOptions = useCreatableOptionList(PAYMENT_METHODS)
const returnPaymentMethod = ref<string>(PAYMENT_METHODS[0])
const returnPaymentCurrency = ref<PaymentCurrency>(
  normalizePaymentCurrency(props.rental.currency || preferences.currency),
)
const returnExchangeRate = ref(DEFAULT_USD_KHR_RATE)
const returnTenderedAmount = ref(0)
const returnPaidAmount = ref(0)
const saving = ref(false)

const rentalCurrencyCode = computed(() =>
  normalizePaymentCurrency(props.rental.currency || preferences.currency),
)

const showKhrTotals = computed(() =>
  normalizePaymentCurrency(returnPaymentCurrency.value) === 'KHR'
  || rentalCurrencyCode.value === 'KHR',
)

const returnChargesTotal = computed(() =>
  returnCharges.value.reduce((sum, row) => sum + Math.max(0, Number(row.amount) || 0), 0),
)

const closeBalance = computed(() =>
  rentalReturnBalance(props.rental, returnChargesTotal.value, returnPaidAmount.value),
)

const balanceDueBeforePay = computed(() => closeBalance.value.balanceDue)
const projectedOutstanding = computed(() => closeBalance.value.outstandingAfterPay)
const projectedTotalDue = computed(() => closeBalance.value.totalDue)
const depositAmount = computed(() => closeBalance.value.deposit)
const alreadyPaid = computed(() => closeBalance.value.alreadyPaid)

const rentalPayments = computed(() => {
  const rentalId = String(props.rental.id || '')
  if (!rentalId) return []
  return store.list('rentalPayments').filter(row => String(row.rentalId) === rentalId)
})

const paidTenderedKhr = computed(() =>
  rentalPayments.value.reduce((sum, row) => {
    if (normalizePaymentCurrency(row.currency) !== 'KHR') return sum
    const tendered = Number(row.tenderedAmount || 0)
    return sum + (tendered > 0 ? tendered : 0)
  }, 0),
)

const returnKhr = computed(() => {
  const rentalBaseTotal = Math.max(0, projectedTotalDue.value - returnChargesTotal.value)
  const base = invoiceKhrAmounts({
    subtotal: rentalBaseTotal,
    deposit: depositAmount.value,
    paid: alreadyPaid.value,
    rentalCurrency: rentalCurrencyCode.value,
    exchangeRate: returnExchangeRate.value,
    depositTendered: Number(props.rental.depositTenderedAmount || 0),
    depositCurrency: String(props.rental.depositCurrency || props.rental.paymentCurrency || rentalCurrencyCode.value),
    paidTendered: paidTenderedKhr.value,
    paidCurrency: paidTenderedKhr.value > 0 ? 'KHR' : rentalCurrencyCode.value,
  })
  const chargesKhr = fromRentalCurrencyAmount(
    returnChargesTotal.value,
    'KHR',
    rentalCurrencyCode.value,
    returnExchangeRate.value,
  )
  const totalDueKhr = base.subtotalKhr + chargesKhr
  const balanceDueKhr = Math.max(0, base.outstandingKhr + chargesKhr)
  const outstandingAfterPayKhr = normalizePaymentCurrency(returnPaymentCurrency.value) === 'KHR'
    ? Math.max(0, balanceDueKhr - Math.round(Number(returnTenderedAmount.value) || 0))
    : Math.max(0, balanceDueKhr - fromRentalCurrencyAmount(
      returnPaidAmount.value,
      'KHR',
      rentalCurrencyCode.value,
      returnExchangeRate.value,
    ))
  return {
    totalDueKhr,
    depositKhr: base.depositKhr,
    paidKhr: base.paidKhr,
    balanceDueKhr,
    outstandingAfterPayKhr,
    chargesKhr,
  }
})

watch([returnTenderedAmount, returnPaymentCurrency, returnExchangeRate], () => {
  returnPaidAmount.value = toRentalCurrencyAmount(
    returnTenderedAmount.value,
    returnPaymentCurrency.value,
    rentalCurrencyCode.value,
    returnExchangeRate.value,
  )
})

function onCreateReturnChargeType(item: string, row: ReturnChargeLine) {
  const value = chargeTypeOptions.onCreate(item)
  if (value) row.chargeType = value
}

function onCreateReturnPaymentMethod(item: string) {
  const value = paymentMethodOptions.onCreate(item)
  if (value) returnPaymentMethod.value = value
}

function latestPaymentFx() {
  return rentalPayments.value.find(row => Number(row.exchangeRate || 0) > 1)
    || rentalPayments.value[0]
    || null
}

function resetForm() {
  returnAt.value = new Date().toISOString().slice(0, 16)
  returnPaymentMethod.value = PAYMENT_METHODS[0]
  const fx = latestPaymentFx()
  if (fx) {
    returnPaymentCurrency.value = normalizePaymentCurrency(fx.currency || rentalCurrencyCode.value)
    returnExchangeRate.value = normalizeExchangeRate(fx.exchangeRate, DEFAULT_USD_KHR_RATE)
  }
  else if (props.rental.depositCurrency || props.rental.exchangeRate) {
    returnPaymentCurrency.value = normalizePaymentCurrency(
      props.rental.depositCurrency || props.rental.paymentCurrency || rentalCurrencyCode.value,
    )
    returnExchangeRate.value = normalizeExchangeRate(props.rental.exchangeRate, DEFAULT_USD_KHR_RATE)
  }
  else {
    returnPaymentCurrency.value = rentalCurrencyCode.value
    returnExchangeRate.value = DEFAULT_USD_KHR_RATE
  }
  returnCharges.value = []
  chargeSeq = 1
  returnPaidAmount.value = rentalReturnBalance(props.rental, 0, 0).suggestedPayment
}

watch(open, (isOpenNow) => {
  if (isOpenNow) resetForm()
}, { immediate: true })


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

async function saveClose() {
  const invalidCharge = returnCharges.value.some(row => row.amount > 0 && !row.chargeType)
  if (invalidCharge) return
  if (returnPaidAmount.value > balanceDueBeforePay.value + 0.001) return

  const rentalNo = String(props.rental.rentalNo || props.rental.id || '')
  const ok = await confirm({
    kind: 'generic',
    titleKey: 'rental.ui.confirmCloseTitle',
    descriptionKey: 'rental.ui.confirmCloseDescription',
    descriptionParams: {
      rentalNo,
      outstanding: money(projectedOutstanding.value),
    },
    confirmLabelKey: 'rental.ui.confirmClose',
    confirmColor: 'warning',
  })
  if (!ok) return

  saving.value = true
  try {
    const closed = await rentalCommands.close(String(props.rental.id), {
        returnDate: toIsoZonedOrNow(returnAt.value),
        condition: null,
        returnNote: null,
        lateFee: 0,
        charges: returnCharges.value
          .filter(row => Number(row.amount) > 0)
          .map(row => ({
            chargeType: row.chargeType,
            description: row.description || null,
            amount: Number(row.amount),
            chargeToCustomer: 'Yes',
          })),
        finalPayment: returnPaidAmount.value > 0
          ? {
              amount: Number(returnPaidAmount.value),
              paymentMethod: returnPaymentMethod.value,
              currency: returnPaymentCurrency.value,
              exchangeRate: returnExchangeRate.value,
              tenderedAmount: returnTenderedAmount.value,
              reference: null,
              note: tx('rental.ui.paymentOnReturn', 'Payment on return'),
              paidAt: toIsoZonedOrNow(returnAt.value),
            }
          : null,
        motorcycleStatus: 'Available',
      })
      await store.fetchOne('rentals', String(closed.id))
      await store.fetchList('motorcycles')
      await store.fetchList('rentalPayments', { rentalId: String(closed.id) })
      await store.fetchList('rentalCharges', { rentalId: String(closed.id) })
      toast.add({ title: tx('rental.ui.rentalClosed', 'Rental closed'), color: 'success' })
      emit('saved', tx('rental.ui.rentalClosed', 'Rental closed'))
  }
  catch (error: unknown) {
    toast.add({
      title: tx('rental.ui.rentalCloseFailed', 'Could not close rental'),
      description: error instanceof Error ? error.message : String(error),
      color: 'error',
    })
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
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <UFormField :label="tx('rental.ui.rentalNo', 'Rental Number')">
            <UInput
              :model-value="String(rental.rentalNo || rental.id || '—')"
              size="md"
              class="w-full"
              disabled
            />
          </UFormField>
          <UFormField :label="tx('rental.ui.customer', 'Customer')">
            <UInput
              :model-value="String(rental.customer || '—')"
              size="md"
              class="w-full"
              disabled
            />
          </UFormField>
        </div>

        <div class="grid grid-cols-2 gap-2 rounded-md bg-elevated/60 p-3 text-sm sm:grid-cols-4">
          <div>
            <p class="text-xs text-muted">{{ tx('rental.ui.totalDue', 'Total Due') }}</p>
            <p class="font-semibold tabular-nums">{{ moneyBoth(projectedTotalDue, returnKhr.totalDueKhr) }}</p>
          </div>
          <div>
            <p class="text-xs text-muted">{{ tx('rental.ui.deposit', 'Deposit') }}</p>
            <p class="font-semibold tabular-nums">{{ moneyBoth(depositAmount, returnKhr.depositKhr) }}</p>
          </div>
          <div>
            <p class="text-xs text-muted">{{ tx('rental.ui.alreadyPaid', 'Already Paid') }}</p>
            <p class="font-semibold tabular-nums">{{ moneyBoth(alreadyPaid, returnKhr.paidKhr) }}</p>
          </div>
          <div>
            <p class="text-xs text-muted">{{ tx('rental.ui.outstanding', 'Outstanding') }}</p>
            <p class="font-semibold tabular-nums" :class="balanceDueBeforePay > 0 ? 'text-warning' : 'text-success'">
              {{ moneyBoth(balanceDueBeforePay, returnKhr.balanceDueKhr) }}
            </p>
          </div>
        </div>
        <p v-if="showKhrTotals" class="text-xs text-muted">
          {{ tx('rental.ui.exchangeRate', 'Exchange rate') }}:
          1 USD = {{ returnExchangeRate }} KHR
        </p>

        <UFormField :label="tx('rental.ui.actualReturn', 'Actual Return')" required>
          <UInput
            v-model="returnAt"
            type="datetime-local"
            size="md"
            class="w-full max-w-sm"
          />
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
                    <UInputMenu
                      v-model="row.chargeType"
                      create-item
                      :items="chargeTypeOptions.items.value"
                      size="md"
                      class="w-36"
                      @create="(item: string) => onCreateReturnChargeType(item, row)"
                    />
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
                      class="w-28 text-center"
                    />
                  </td>
                  <td class="px-1 py-1.5">
                    <UButton
                      size="xs"
                      color="neutral"
                      variant="ghost"
                      icon="i-lucide-trash-2"
                      @click="removeReturnChargeLine(row.key)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="returnChargesTotal > 0" class="mt-2 text-center text-sm">
            {{ tx('rental.ui.chargesTotal', 'Charges total') }}:
            <span class="font-semibold tabular-nums">{{ moneyBoth(returnChargesTotal, returnKhr.chargesKhr) }}</span>
          </p>
        </div>

        <div class="space-y-3 rounded-md border border-default p-3">
          <UFormField :label="tx('rental.ui.paymentMethod', 'Payment Method')">
            <UInputMenu
              v-model="returnPaymentMethod"
              create-item
              :items="paymentMethodOptions.items.value"
              size="md"
              class="w-full"
              @create="onCreateReturnPaymentMethod"
            />
          </UFormField>
          <RentalPaymentCurrencyFields
            v-model:payment-currency="returnPaymentCurrency"
            v-model:exchange-rate="returnExchangeRate"
            v-model:tendered-amount="returnTenderedAmount"
            :rental-currency="rentalCurrencyCode"
            :target-rental-amount="balanceDueBeforePay"
          />
          <p class="text-xs text-muted">
            {{ tx('rental.ui.balanceDue', 'Balance due') }}:
            <span class="font-semibold text-highlighted tabular-nums">{{ moneyBoth(balanceDueBeforePay, returnKhr.balanceDueKhr) }}</span>
            ·
            {{ tx('rental.ui.outstandingAfterPay', 'Outstanding after payment') }}:
            <span class="font-semibold text-highlighted tabular-nums">{{ moneyBoth(projectedOutstanding, returnKhr.outstandingAfterPayKhr) }}</span>
          </p>
          <p v-if="showKhrTotals" class="text-xs text-muted">
            {{ tx('rental.ui.exchangeRate', 'Exchange rate') }}:
            1 USD = {{ returnExchangeRate }} KHR
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
