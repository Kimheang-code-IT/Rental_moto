<script setup lang="ts">
import { useConfirm } from '~/composables/common/useConfirm'
import { RENTAL_CURRENCY_OPTIONS, RENTAL_EXPENSE_TYPES } from '~/config/rental-options'
import { todayDateTimeLocal } from '~/utils/rental/pricing'

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
const date = ref('')
type RentalCurrency = (typeof RENTAL_CURRENCY_OPTIONS)[number]['value']

const expenseTypeItems = ref<string[]>([...RENTAL_EXPENSE_TYPES])
const expenseType = ref('Fuel')
const description = ref('')
const amount = ref<number | undefined>()
const currency = ref<RentalCurrency>('USD')

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

function resetForm() {
  date.value = todayDateTimeLocal().slice(0, 10)
  expenseTypeItems.value = [...RENTAL_EXPENSE_TYPES]
  expenseType.value = 'Fuel'
  description.value = ''
  amount.value = undefined
  const preferred = String(preferences.currency || 'USD')
  currency.value = RENTAL_CURRENCY_OPTIONS.some(option => option.value === preferred)
    ? preferred as RentalCurrency
    : 'USD'
}

function onCreateExpenseType(item: string) {
  const trimmed = item.trim()
  if (!trimmed) return
  if (!expenseTypeItems.value.includes(trimmed)) {
    expenseTypeItems.value.push(trimmed)
  }
  expenseType.value = trimmed
}


async function saveExpense() {
  const type = expenseType.value.trim()
  if (!date.value || !type || !description.value.trim() || Number(amount.value || 0) <= 0) return

  const ok = await confirm({
    kind: 'submit',
    titleKey: 'rental.ui.confirmAddExpense',
    descriptionKey: 'rental.ui.confirmAddExpenseDescription',
    descriptionParams: {
      type,
      amount: Number(amount.value).toFixed(2),
      currency: currency.value,
    },
    confirmLabelKey: 'rental.ui.addExpense',
  })
  if (!ok) return

  saving.value = true
  try {
    const payload = {
      date: `${date.value}T00:00:00`,
      expenseType: type,
      description: description.value.trim(),
      amount: Number(amount.value),
      currency: currency.value,
    }
    await store.createRemote('rentalExpenses', payload)
    await store.fetchList('rentalExpenses')
    toast.add({ title: tx('rental.ui.expenseSaved', 'Expense recorded'), color: 'success' })
    open.value = false
    emit('saved')
  }
  catch (error: unknown) {
    // useApi already shows the API validation toast; avoid a third duplicate here.
    if (import.meta.dev) console.error(error)
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
    :title="tx('rental.ui.addExpense', 'Add Expense')"
    :ui="{ content: 'w-[calc(100%-2rem)] max-w-3xl sm:max-w-3xl' }"
  >
    <template #body>
      <div class="flex flex-col gap-4">
        <UFormField :label="tx('rental.ui.date', 'Date')" required>
          <UInput v-model="date" type="date" class="w-full" />
        </UFormField>
        <UFormField
          :label="tx('rental.ui.expenseName', 'Expense name')"
          :help="tx('rental.fieldHelp.expenseName', 'Choose a preset type or type a custom expense name.')"
          required
        >
          <UInputMenu
            v-model="expenseType"
            create-item
            :items="expenseTypeItems"
            class="w-full"
            @create="onCreateExpenseType"
          />
        </UFormField>
        <UFormField :label="tx('rental.ui.amount', 'Amount')" required>
          <UInput
v-model.number="amount"
type="number"
min="0"
step="0.01"
class="w-full" />
        </UFormField>
        <UFormField :label="tx('rental.ui.currency', 'Currency')" required>
          <USelect
v-model="currency"
value-key="value"
:items="[...RENTAL_CURRENCY_OPTIONS]"
class="w-full" />
        </UFormField>
        <UFormField :label="tx('rental.ui.description', 'Description')" required>
          <UTextarea v-model="description" :rows="3" class="w-full" />
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
          icon="i-lucide-plus"
          :loading="saving"
          :disabled="!date || !expenseType.trim() || !description.trim() || Number(amount || 0) <= 0"
          :label="tx('rental.ui.addExpense', 'Add Expense')"
          @click="saveExpense"
        />
      </div>
    </template>
  </UModal>
</template>
