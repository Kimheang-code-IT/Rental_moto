<script setup lang="ts">
import { formatMoney } from '~/composables/module/useModule'

const props = defineProps<{
  rental: Record<string, unknown> | null
}>()

const open = defineModel<boolean>('open', { default: false })

const { t, te } = useI18n()
const store = useAppDataStore()
const preferences = usePreferencesStore()
const loading = ref(false)

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

const rentalId = computed(() => String(props.rental?.id || ''))
const currency = computed(() => String(props.rental?.currency || preferences.currency))

const charges = computed(() =>
  store.list('rentalCharges')
    .filter(row =>
      String(row.rentalId || '') === rentalId.value
      && String(row.chargeToCustomer || 'Yes') !== 'No',
    )
    .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || ''))),
)

const chargesTotal = computed(() =>
  charges.value.reduce((sum, row) => sum + Math.max(0, Number(row.amount) || 0), 0),
)

const summaryAmount = computed(() => Number(props.rental?.additionalCharges || 0))

const money = (value: unknown) => formatMoney(value, currency.value)

async function loadCharges() {
  if (!rentalId.value) return
  loading.value = true
  try {
    await store.fetchList('rentalCharges', { rentalId: rentalId.value, limit: 100 })
  }
  finally {
    loading.value = false
  }
}

watch(open, (isOpen) => {
  if (isOpen) void loadCharges()
})
</script>

<template>
  <UModal
    v-model:open="open"
    :title="tx('rental.ui.additionalChargesDetail', 'Additional charges')"
    :ui="{ content: 'w-[50vw] max-w-[50vw] sm:max-w-[50vw]' }"
  >
    <template #body>
      <div class="space-y-4">
        <div class="rounded-md bg-elevated/60 px-3 py-2 text-sm text-muted">
          <span class="font-medium text-highlighted">{{ rental?.rentalNo || '—' }}</span>
          <span v-if="rental?.customer"> · {{ rental.customer }}</span>
        </div>

        <div v-if="loading" class="flex justify-center py-8">
          <UIcon name="i-lucide-loader-circle" class="size-6 animate-spin text-muted" />
        </div>

        <div
          v-else-if="!charges.length"
          class="rounded-md border border-dashed border-default px-3 py-6 text-center text-sm text-muted"
        >
          {{ tx('rental.ui.noAdditionalCharges', 'No additional charges recorded for this rental.') }}
        </div>

        <div v-else class="overflow-x-auto rounded-md border border-default">
          <table class="w-full min-w-md text-sm">
            <thead>
              <tr class="border-b border-default bg-elevated/40 text-left text-xs text-muted">
                <th class="px-3 py-2 font-medium">{{ tx('rental.ui.chargeType', 'Charge Type') }}</th>
                <th class="px-3 py-2 font-medium">{{ tx('rental.ui.description', 'Description') }}</th>
                <th class="px-3 py-2 text-end font-medium">{{ tx('rental.ui.amount', 'Amount') }}</th>
                <th class="px-3 py-2 font-medium">{{ tx('rental.ui.date', 'Date') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in charges"
                :key="String(row.id)"
                class="border-b border-default/70"
              >
                <td class="px-3 py-2 text-default">{{ row.chargeType || '—' }}</td>
                <td class="px-3 py-2 text-default">{{ row.description || '—' }}</td>
                <td class="px-3 py-2 text-end tabular-nums font-medium">{{ money(row.amount) }}</td>
                <td class="px-3 py-2 tabular-nums text-muted">{{ String(row.createdAt || '').slice(0, 10) || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="flex flex-wrap items-center justify-between gap-2 rounded-md border border-default px-3 py-2 text-sm">
          <span class="text-muted">{{ tx('rental.ui.chargesTotal', 'Charges total') }}</span>
          <span class="font-semibold tabular-nums">{{ money(chargesTotal) }}</span>
        </div>
        <p
          v-if="summaryAmount > 0 && Math.abs(summaryAmount - chargesTotal) > 0.01"
          class="text-xs text-muted"
        >
          {{ tx('rental.ui.additionalChargesSummaryHint', 'Rental summary total') }}:
          <span class="font-medium tabular-nums">{{ money(summaryAmount) }}</span>
        </p>
      </div>
    </template>
    <template #footer>
      <div class="flex w-full justify-end">
        <UButton
          color="neutral"
          variant="ghost"
          :label="tx('common.actions.close', 'Close')"
          @click="open = false"
        />
      </div>
    </template>
  </UModal>
</template>
