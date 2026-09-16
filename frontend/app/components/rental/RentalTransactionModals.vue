<script setup lang="ts">
import { useConfirm } from '~/composables/common/useConfirm'
import { formatMoney } from '~/composables/module/useModule'
import { PAYMENT_METHODS, RENTAL_CHARGE_TYPES } from '~/config/rental-options'
import { useCreatableOptionList } from '~/composables/rental/useCreatableOptionList'
import { toIsoZonedOrNow } from '~/utils/api/datetime'
import {
  DEFAULT_USD_KHR_RATE,
  exchangeRateForCurrencies,
  fromRentalCurrencyAmount,
  normalizeExchangeRate,
  normalizePaymentCurrency,
  type PaymentCurrency,
} from '~/utils/rental/fx'
import { rentalReturnBalance, securityDepositSettlement } from '~/utils/rental/pricing'
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

/** Format a payment-currency amount, with a KHR equivalent when relevant. */
function moneyTender(value: unknown, khrOverride?: number) {
  const amount = Math.max(0, Number(value) || 0)
  const primary = formatMoney(amount, returnPaymentCurrency.value)
  if (!showKhrTotals.value || normalizePaymentCurrency(returnPaymentCurrency.value) === 'KHR') return primary
  const khr = khrOverride != null
    ? Math.max(0, Math.round(khrOverride))
    : fromRentalCurrencyAmount(
      amount,
      'KHR',
      returnPaymentCurrency.value,
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
const returnSettlementInput = ref(0)
const settlementTouched = ref(false)
const saving = ref(false)

const rentalCurrencyCode = computed(() =>
  normalizePaymentCurrency(props.rental.currency || preferences.currency),
)

const showKhrTotals = computed(() =>
  normalizePaymentCurrency(returnPaymentCurrency.value) === 'KHR'
  || rentalCurrencyCode.value === 'KHR',
)

/** Signed currency conversion (no zero clamping) for charge and settlement values. */
function convertSigned(amount: unknown, from: string, to: string, rate: number) {
  const value = Number(amount) || 0
  const r = normalizeExchangeRate(rate)
  const f = normalizePaymentCurrency(from)
  const t = normalizePaymentCurrency(to)
  if (f === t) return Number(value.toFixed(2))
  if (f === 'USD' && t === 'KHR') return Math.round(value * r)
  if (f === 'KHR' && t === 'USD') return Number((value / r).toFixed(2))
  return Number(value.toFixed(2))
}

/** Return charges are entered in the selected payment currency. */
const returnChargesTotal = computed(() =>
  returnCharges.value.reduce((sum, row) => sum + Math.max(0, Number(row.amount) || 0), 0),
)

/** Return charges converted into the rental currency for balance math. */
const returnChargesRental = computed(() =>
  Number(returnCharges.value.reduce((sum, row) =>
    sum + convertSigned(
      Math.max(0, Number(row.amount) || 0),
      returnPaymentCurrency.value,
      rentalCurrencyCode.value,
      returnExchangeRate.value,
    ), 0).toFixed(2)),
)

/** Base rental balance before return charges and deposit refunds. */
const baseBalance = computed(() => rentalReturnBalance(props.rental, 0, 0))
const depositAmount = computed(() => baseBalance.value.deposit)
const depositTenderAmount = computed(() => {
  const storedTendered = Math.max(0, Number(props.rental.depositTenderedAmount) || 0)
  const storedCurrency = normalizePaymentCurrency(
    props.rental.depositCurrency || rentalCurrencyCode.value,
  )
  if (storedTendered > 0 && storedCurrency === returnPaymentCurrency.value) {
    return storedTendered
  }
  return convertSigned(
    depositAmount.value,
    rentalCurrencyCode.value,
    returnPaymentCurrency.value,
    returnExchangeRate.value,
  )
})
const existingSecurityCharges = computed(() =>
  Number((Math.max(0, Number(props.rental.lateFee) || 0)
    + Math.max(0, Number(props.rental.additionalCharges) || 0)).toFixed(2)),
)
const existingSecurityChargesTender = computed(() => convertSigned(
  existingSecurityCharges.value,
  rentalCurrencyCode.value,
  returnPaymentCurrency.value,
  returnExchangeRate.value,
))
const depositSettlementTender = computed(() => securityDepositSettlement(
  depositTenderAmount.value,
  existingSecurityChargesTender.value + returnChargesTotal.value,
))
const baseRentalOutstanding = computed(() =>
  Number(Math.max(baseBalance.value.balanceDue - existingSecurityCharges.value, 0).toFixed(2)),
)

/** Security covers charges only; unpaid rent remains payable separately. */
const netSettlement = computed(() =>
  Number((baseRentalOutstanding.value + convertSigned(
    depositSettlementTender.value.customerPays,
    returnPaymentCurrency.value,
    rentalCurrencyCode.value,
    returnExchangeRate.value,
  )).toFixed(2)),
)

const rentalPayments = computed(() => {
  const rentalId = String(props.rental.id || '')
  if (!rentalId) return []
  return store.list('rentalPayments').filter(row => String(row.rentalId) === rentalId)
})

const chargesKhr = computed(() =>
  fromRentalCurrencyAmount(
    returnChargesRental.value,
    'KHR',
    rentalCurrencyCode.value,
    returnExchangeRate.value,
  ),
)

/** The editable total converted back into the rental currency. */
const settlementRental = computed(() =>
  convertSigned(
    returnSettlementInput.value,
    returnPaymentCurrency.value,
    rentalCurrencyCode.value,
    returnExchangeRate.value,
  ),
)
const returnPaidAmount = computed(() => Math.max(0, settlementRental.value))
const depositRefundTenderAmount = computed(() => depositSettlementTender.value.refundToCustomer)
const depositRefundAmount = computed(() => convertSigned(
  depositRefundTenderAmount.value,
  returnPaymentCurrency.value,
  rentalCurrencyCode.value,
  returnExchangeRate.value,
))

const projectedOutstanding = computed(() =>
  Number(Math.max(Math.max(netSettlement.value, 0) - returnPaidAmount.value, 0).toFixed(2)),
)

let syncingSettlement = false
function syncSettlementFromNet() {
  syncingSettlement = true
  returnSettlementInput.value = convertSigned(
    netSettlement.value,
    rentalCurrencyCode.value,
    returnPaymentCurrency.value,
    returnExchangeRate.value,
  )
  void nextTick(() => {
    syncingSettlement = false
  })
}

watch([netSettlement, returnPaymentCurrency, returnExchangeRate], () => {
  if (settlementTouched.value) return
  syncSettlementFromNet()
})

// Adding/changing return charges recalculates the suggested settlement.
watch(returnChargesTotal, () => {
  settlementTouched.value = false
  syncSettlementFromNet()
})

watch(returnSettlementInput, () => {
  if (syncingSettlement) return
  settlementTouched.value = true
})

// Keep charge and settlement rental-currency values stable when the tender currency changes.
watch(returnPaymentCurrency, (next, prev) => {
  if (next === prev) return

  returnCharges.value = returnCharges.value.map(row => ({
    ...row,
    amount: convertSigned(
      convertSigned(
        Math.max(0, Number(row.amount) || 0),
        prev,
        rentalCurrencyCode.value,
        returnExchangeRate.value,
      ),
      rentalCurrencyCode.value,
      next,
      returnExchangeRate.value,
    ),
  }))

  if (!settlementTouched.value) return
  const rentalValue = convertSigned(
    returnSettlementInput.value,
    prev,
    rentalCurrencyCode.value,
    returnExchangeRate.value,
  )
  syncingSettlement = true
  returnSettlementInput.value = convertSigned(
    rentalValue,
    rentalCurrencyCode.value,
    next,
    returnExchangeRate.value,
  )
  void nextTick(() => {
    syncingSettlement = false
  })
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
  const hasTenderedDeposit = Math.max(0, Number(props.rental.depositTenderedAmount) || 0) > 0
  if (hasTenderedDeposit || props.rental.depositCurrency) {
    returnPaymentCurrency.value = normalizePaymentCurrency(
      props.rental.depositCurrency || props.rental.paymentCurrency || rentalCurrencyCode.value,
    )
    returnExchangeRate.value = exchangeRateForCurrencies(
      props.rental.exchangeRate,
      returnPaymentCurrency.value,
      rentalCurrencyCode.value,
      DEFAULT_USD_KHR_RATE,
    )
  }
  else {
    const fx = latestPaymentFx()
    if (fx) {
      returnPaymentCurrency.value = normalizePaymentCurrency(fx.currency || rentalCurrencyCode.value)
      returnExchangeRate.value = exchangeRateForCurrencies(
        fx.exchangeRate,
        returnPaymentCurrency.value,
        rentalCurrencyCode.value,
        DEFAULT_USD_KHR_RATE,
      )
    }
    else {
      returnPaymentCurrency.value = rentalCurrencyCode.value
      returnExchangeRate.value = DEFAULT_USD_KHR_RATE
    }
  }
  returnCharges.value = []
  chargeSeq = 1
  settlementTouched.value = false
  syncSettlementFromNet()
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
        depositRefund: Number(depositRefundAmount.value.toFixed(2)),
        charges: returnCharges.value
          .filter(row => Number(row.amount) > 0)
          .map(row => ({
            chargeType: row.chargeType,
            description: row.description || null,
            amount: convertSigned(
              Number(row.amount),
              returnPaymentCurrency.value,
              rentalCurrencyCode.value,
              returnExchangeRate.value,
            ),
            chargeToCustomer: 'Yes',
          })),
        finalPayment: returnPaidAmount.value > 0
          ? {
              amount: Number(returnPaidAmount.value.toFixed(2)),
              paymentMethod: returnPaymentMethod.value,
              currency: returnPaymentCurrency.value,
              exchangeRate: returnExchangeRate.value,
              tenderedAmount: returnSettlementInput.value,
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
          <UFormField :label="tx('rental.ui.actualReturn', 'Actual Return')" required>
            <UInput
              v-model="returnAt"
              type="datetime-local"
              size="md"
              class="w-full"
            />
          </UFormField>
          <UFormField :label="tx('rental.ui.deposit', 'Deposit')">
            <UInput
              :model-value="formatMoney(depositTenderAmount, returnPaymentCurrency)"
              size="md"
              class="w-full"
              disabled
            />
          </UFormField>
        </div>

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
                    <RentalMoneyInput
                      v-model="row.amount"
                      :currency="returnPaymentCurrency"
                      :min="0"
                      class="w-32"
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
            <span class="font-semibold tabular-nums">{{ moneyTender(returnChargesTotal, chargesKhr) }}</span>
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
            :rental-currency="rentalCurrencyCode"
            :show-amount="false"
            :show-converted-hint="false"
          />
          <UFormField :label="tx('rental.ui.refundToCustomer', 'Refund to customer')">
            <UInput
              :model-value="formatMoney(depositRefundTenderAmount, returnPaymentCurrency)"
              size="md"
              class="w-full"
              disabled
            />
          </UFormField>
          <p v-if="returnPaidAmount > 0" class="text-xs text-muted">
            {{ tx('rental.ui.customerPays', 'Customer pays') }}:
            <span class="font-semibold tabular-nums">{{ moneyBoth(returnPaidAmount) }}</span>
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
