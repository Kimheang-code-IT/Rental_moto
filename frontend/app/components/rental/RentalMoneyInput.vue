<script setup lang="ts">
import { currencyInputStep, normalizePaymentCurrency, roundCurrencyAmount } from '~/utils/rental/fx'
import { currencySymbol, currencySymbolPosition } from '~/utils/format/format-service'

const props = withDefaults(defineProps<{
  currency?: string
  min?: number
  max?: number
  step?: number
  disabled?: boolean
  placeholder?: string
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
  class?: string
}>(), {
  currency: 'USD',
  min: 0,
  disabled: false,
  size: 'md',
})

const model = defineModel<number>({ default: 0 })

const currencyCode = computed(() => normalizePaymentCurrency(props.currency))
const symbol = computed(() => currencySymbol(currencyCode.value))
const symbolPosition = computed(() => currencySymbolPosition(currencyCode.value))
const resolvedStep = computed(() => props.step ?? currencyInputStep(currencyCode.value))

function normalize() {
  const rounded = roundCurrencyAmount(model.value, currencyCode.value)
  const bounded = props.max != null ? Math.min(rounded, props.max) : rounded
  if (bounded !== model.value) model.value = bounded
}
</script>

<template>
  <div
    class="rental-money-input relative"
    :class="[props.class, symbolPosition === 'suffix' ? 'rental-money-input--suffix' : 'rental-money-input--prefix']"
  >
    <span
      v-if="symbolPosition === 'prefix'"
      class="pointer-events-none absolute inset-y-0 start-0 z-10 flex items-center ps-2.5 text-sm font-medium text-muted"
      aria-hidden="true"
    >
      {{ symbol }}
    </span>
    <UInputNumber
      v-model="model"
      :min="min"
      :max="max"
      :step="resolvedStep"
      :increment="false"
      :decrement="false"
      :disabled="disabled"
      :placeholder="placeholder"
      :size="size"
      class="w-full"
      :ui="{ base: 'tabular-nums' }"
      @blur="normalize"
    />
    <span
      v-if="symbolPosition === 'suffix'"
      class="pointer-events-none absolute inset-y-0 end-0 z-10 flex items-center pe-2.5 text-sm font-medium text-muted"
      aria-hidden="true"
    >
      {{ symbol }}
    </span>
  </div>
</template>

<style scoped>
.rental-money-input--prefix :deep(input) {
  padding-inline-start: 1.75rem;
}

.rental-money-input--suffix :deep(input) {
  padding-inline-end: 1.75rem;
}
</style>
