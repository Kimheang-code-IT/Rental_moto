<script setup lang="ts">
import { RENTAL_CURRENCY_OPTIONS, RENTAL_EXPENSE_TYPES } from '~/config/rental-options'
import { todayDateTimeLocal } from '~/utils/rental/pricing'

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  saved: []
}>()

const { t, te } = useI18n()
const store = useAppDataStore()
const preferences = usePreferencesStore()
const auth = useAuthStore()
const toast = useToast()

const saving = ref(false)
const date = ref('')
type ExpenseType = (typeof RENTAL_EXPENSE_TYPES)[number]
type RentalCurrency = (typeof RENTAL_CURRENCY_OPTIONS)[number]['value']

const expenseType = ref<ExpenseType>('Fuel')
const description = ref('')
const amount = ref<number | undefined>()
const currency = ref<RentalCurrency>('USD')

function tx(key: string, fallback: string) {
  return te(key) ? String(t(key)) : fallback
}

function resetForm() {
  date.value = todayDateTimeLocal().slice(0, 10)
  expenseType.value = 'Fuel'
  description.value = ''
  amount.value = undefined
  const preferred = String(preferences.currency || 'USD')
  currency.value = RENTAL_CURRENCY_OPTIONS.some(option => option.value === preferred)
    ? preferred as RentalCurrency
    : 'USD'
}

function nextExpenseNumber() {
  const sequence = store.list('rentalExpenses').reduce((max, row) => {
    const match = String(row.expenseNo || '').match(/(\d+)$/)
    return Math.max(max, match ? Number(match[1]) : 0)
  }, 0) + 1

  return `RNX-${String(sequence).padStart(6, '0')}`
}

async function saveExpense() {
  if (!date.value || !expenseType.value || !description.value.trim() || Number(amount.value || 0) <= 0) return

  saving.value = true
  try {
    const payload = {
      date: `${date.value}T00:00:00`,
      expenseType: expenseType.value,
      description: description.value.trim(),
      amount: Number(amount.value),
      currency: currency.value,
    }
    if (store.isHttpMode) {
      await store.createRemote('rentalExpenses', payload)
      await store.fetchList('rentalExpenses')
    }
    else {
      const expenseNo = nextExpenseNumber()
      store.create('rentalExpenses', {
        ...payload,
        expenseNo,
        createdBy: auth.user?.name || 'System',
      }, 'rx')
      store.addAudit('Create expense', 'Income & Expense', expenseNo, description.value.trim())
    }
    toast.add({ title: tx('rental.ui.expenseSaved', 'Expense recorded'), color: 'success' })
    open.value = false
    emit('saved')
  }
  catch (error: unknown) {
    toast.add({
      title: tx('rental.ui.expenseSaveFailed', 'Could not record expense'),
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
  <UModal v-model:open="open" :title="tx('rental.ui.addExpense', 'Add Expense')">
    <template #body>
      <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <UFormField :label="tx('rental.ui.date', 'Date')" required>
          <UInput v-model="date" type="date" class="w-full" />
        </UFormField>
        <UFormField :label="tx('rental.ui.expenseType', 'Expense Type')" required>
          <USelect v-model="expenseType" :items="[...RENTAL_EXPENSE_TYPES]" class="w-full" />
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
        <UFormField class="sm:col-span-2" :label="tx('rental.ui.description', 'Description')" required>
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
          :disabled="!date || !expenseType || !description.trim() || Number(amount || 0) <= 0"
          :label="tx('rental.ui.addExpense', 'Add Expense')"
          @click="saveExpense"
        />
      </div>
    </template>
  </UModal>
</template>
