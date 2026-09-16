<script setup lang="ts">
import { RENTAL_CURRENCY_OPTIONS } from '~/config/rental-options'
import {
  DEFAULT_USD_KHR_RATE,
  fromRentalCurrencyAmount,
  needsExchangeRate,
  normalizeExchangeRate,
  normalizePaymentCurrency,
  toRentalCurrencyAmount,
  type PaymentCurrency,
} from '~/utils/rental/fx'
import { formatMoney } from '~/composables/module/useModule'

const props = withDefaults(defineProps<{
  rentalCurrency?: string
  /** When set, keeps tendered amount synced from this rental-currency target. */
  targetRentalAmount?: number | null
  disabled?: boolean
  /** Disable only the tendered amount field (currency/rate stay editable). */
  amountDisabled?: boolean
  amountLabel?: string
  showConvertedHint?: boolean
  showAmount?: boolean
}>(), {
  rentalCurrency: 'USD',
  targetRentalAmount: null,
  disabled: false,
  amountDisabled: false,
  showConvertedHint: true,
  showAmount: true,
})

const paymentCurrency = defineModel<PaymentCurrency>('paymentCurrency', { default: 'USD' })
const exchangeRate = defineModel<number>('exchangeRate', { default: DEFAULT_USD_KHR_RATE })
const tenderedAmount = defineModel<number>('tenderedAmount', { default: 0 })

const { t, te } = useI18n()

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

const rentalCurrency = computed(() => normalizePaymentCurrency(props.rentalCurrency))
const showRate = computed(() => needsExchangeRate(paymentCurrency.value, rentalCurrency.value))

const creditedAmount = computed(() =>
  toRentalCurrencyAmount(
    tenderedAmount.value,
    paymentCurrency.value,
    rentalCurrency.value,
    exchangeRate.value,
  ),
)

watch(paymentCurrency, (next, prev) => {
  if (next === prev) return
  if (props.targetRentalAmount != null) {
    tenderedAmount.value = fromRentalCurrencyAmount(
      props.targetRentalAmount,
      next,
      rentalCurrency.value,
      exchangeRate.value,
    )
    return
  }
  // Keep the rental-currency credit stable when switching tender currency.
  const credited = toRentalCurrencyAmount(
    tenderedAmount.value,
    prev,
    rentalCurrency.value,
    exchangeRate.value,
  )
  tenderedAmount.value = fromRentalCurrencyAmount(
    credited,
    next,
    rentalCurrency.value,
    exchangeRate.value,
  )
})

watch(() => props.targetRentalAmount, (target) => {
  if (target == null) return
  tenderedAmount.value = fromRentalCurrencyAmount(
    target,
    paymentCurrency.value,
    rentalCurrency.value,
    exchangeRate.value,
  )
}, { immediate: true })

watch(exchangeRate, (rate) => {
  const next = normalizeExchangeRate(rate)
  if (next !== rate) exchangeRate.value = next
  if (props.targetRentalAmount == null) return
  tenderedAmount.value = fromRentalCurrencyAmount(
    props.targetRentalAmount,
    paymentCurrency.value,
    rentalCurrency.value,
    next,
  )
})
</script>

<template>
  <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
    <UFormField :label="tx('rental.ui.paymentCurrency', 'Payment currency')" required>
      <USelect
        v-model="paymentCurrency"
        :items="[...RENTAL_CURRENCY_OPTIONS]"
        value-key="value"
        size="md"
        class="w-full"
        :disabled="disabled"
      />
    </UFormField>

    <UFormField
      v-if="showRate"
      :label="tx('rental.ui.exchangeRate', 'Exchange rate')"
      :help="tx('rental.ui.exchangeRateHelp', 'KHR per 1 USD')"
    >
      <UInputNumber
        v-model="exchangeRate"
        :min="1"
        :step="1"
        :increment="false"
        :decrement="false"
        size="md"
        class="w-full"
        :disabled="disabled"
      />
    </UFormField>

    <UFormField
      v-if="showAmount"
      :label="amountLabel || tx('rental.ui.amountPaid', 'Amount paid')"
      class="sm:col-span-2"
    >
      <UInputNumber
        v-model="tenderedAmount"
        :min="0"
        :step="paymentCurrency === 'KHR' ? 100 : 0.01"
        :increment="false"
        :decrement="false"
        size="md"
        class="w-full"
        :disabled="disabled || amountDisabled"
      />
    </UFormField>

    <p
      v-if="showConvertedHint && showRate"
      class="text-xs text-muted sm:col-span-2"
    >
      {{ tx('rental.ui.creditedInRentalCurrency', 'Credited to rental') }}:
      <span class="font-semibold tabular-nums text-highlighted">
        {{ formatMoney(creditedAmount, rentalCurrency) }}
      </span>
      <span v-if="showRate">
        · 1 USD = {{ exchangeRate }} KHR
      </span>
    </p>
  </div>
</template>
