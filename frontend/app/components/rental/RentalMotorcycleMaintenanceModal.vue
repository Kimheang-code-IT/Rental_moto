<script setup lang="ts">
import { useConfirm } from '~/composables/common/useConfirm'
import { todayDateTimeLocal } from '~/utils/rental/pricing'

const props = defineProps<{
  motorcycle: Record<string, unknown> | null
}>()

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  saved: []
}>()

const { t, te } = useI18n()
const store = useAppDataStore()
const preferences = usePreferencesStore()
const toast = useToast()
const { confirm } = useConfirm()

const saving = ref(false)
const description = ref('')
const amount = ref(0)

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

function help(key: string, fallback: string) {
  if (te(`rental.fieldHelp.${key}`)) return String(t(`rental.fieldHelp.${key}`))
  if (te(`core.fieldHelp.${key}`)) return String(t(`core.fieldHelp.${key}`))
  return fallback
}

const motorcycleLabel = computed(() => {
  const row = props.motorcycle
  if (!row) return ''
  return [row.code, row.model, row.plate].filter(Boolean).map(String).join(' · ')
})

const canSave = computed(() =>
  Boolean(props.motorcycle?.id)
  && description.value.trim().length > 0
  && Number(amount.value || 0) > 0,
)

function resetForm() {
  const label = motorcycleLabel.value
  description.value = label
    ? tx('rental.ui.maintenanceDefaultDescription', 'Maintenance for {moto}').replace('{moto}', label)
    : ''
  amount.value = 0
}


async function save() {
  if (!canSave.value || !props.motorcycle) return

  const ok = await confirm({
    kind: 'submit',
    titleKey: 'rental.ui.confirmMaintenance',
    descriptionKey: 'rental.ui.confirmMaintenanceDescription',
    descriptionParams: {
      motorcycle: motorcycleLabel.value,
      amount: Number(amount.value).toFixed(2),
    },
    confirmLabelKey: 'rental.ui.confirmMaintenance',
    confirmColor: 'warning',
  })
  if (!ok) return

  saving.value = true
  try {
    const moto = props.motorcycle
    const id = String(moto.id)
    const desc = description.value.trim()
    const spent = Number(Number(amount.value).toFixed(2))

    await store.createRemote('rentalExpenses', {
      date: `${todayDateTimeLocal().slice(0, 10)}T00:00:00`,
      expenseType: 'Maintenance',
      description: desc,
      amount: spent,
      currency: String(moto.currency || preferences.currency || 'USD'),
    })
    await store.setStatusRemote('motorcycles', id, 'Maintenance')
    await store.fetchList('rentalExpenses')

    toast.add({
      title: tx('rental.ui.motorcycleMaintenanceSaved', 'Maintenance recorded and motorcycle set to Maintenance'),
      color: 'success',
    })
    open.value = false
    emit('saved')
  }
  catch (error: unknown) {
    toast.add({
      title: tx('rental.ui.maintenanceSaveFailed', 'Could not record maintenance'),
      description: error instanceof Error ? error.message : String(error),
      color: 'error',
    })
  }
  finally {
    saving.value = false
  }
}

watch(open, (isOpen) => {
  if (isOpen) resetForm()
})
</script>

<template>
  <UModal
    v-model:open="open"
    :title="tx('rental.ui.maintenanceExpense', 'Motorcycle maintenance')"
  >
    <template #body>
      <div class="space-y-4">
        <p v-if="motorcycleLabel" class="text-sm text-muted">{{ motorcycleLabel }}</p>

        <UFormField
          :label="tx('rental.ui.description', 'Description')"
          :help="help('maintenanceDescription', 'What work is being done on this motorcycle.')"
          required
        >
          <UTextarea
v-model="description"
:rows="3"
size="md"
class="w-full" />
        </UFormField>

        <UFormField
          :label="tx('rental.ui.amount', 'Amount')"
          :help="help('maintenanceAmount', 'Maintenance cost recorded as an expense.')"
          required
        >
          <UInputNumber
            v-model="amount"
            :min="0"
            :step="0.01"
            :increment="false"
            :decrement="false"
            size="md"
            class="w-full"
          />
        </UFormField>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          :label="tx('common.actions.cancel', 'Cancel')"
          @click="open = false"
        />
        <UButton
          color="warning"
          icon="i-lucide-wrench"
          :loading="saving"
          :disabled="!canSave"
          :label="tx('rental.ui.confirmMaintenance', 'Send to maintenance')"
          @click="save"
        />
      </div>
    </template>
  </UModal>
</template>
