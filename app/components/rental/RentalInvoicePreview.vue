<script setup lang="ts">
import { nextTick, watch } from 'vue'

const props = defineProps<{
  rental: Record<string, unknown> | null
  mode?: 'preview' | 'direct-print'
}>()

const emit = defineEmits<{ close: [] }>()

function printInvoice() {
  if (!import.meta.client) return
  document.body.classList.add('rental-invoice-printing')
  window.print()
  setTimeout(() => {
    document.body.classList.remove('rental-invoice-printing')
    emit('close')
  }, 100)
}

watch(() => props.rental, (val) => {
  if (val && props.mode === 'direct-print') {
    nextTick(() => {
      setTimeout(() => printInvoice(), 300)
    })
  }
}, { immediate: true })
</script>

<template>
  <!-- On-screen view (only in preview mode) -->
  <div v-if="rental && mode !== 'direct-print'" class="bg-white p-6 text-sm text-gray-900">
    <div class="mb-4 flex gap-2 print:hidden">
      <UButton
        color="neutral"
        variant="ghost"
        icon="i-lucide-printer"
        :label="$t('rental.ui.print')"
        @click="printInvoice"
      />
      <UButton
        color="neutral"
        variant="ghost"
        icon="i-lucide-file-down"
        :label="$t('rental.ui.savePdf')"
        @click="printInvoice"
      />
      <UButton
        color="neutral"
        variant="ghost"
        icon="i-lucide-x"
        :label="$t('common.actions.close')"
        @click="emit('close')"
      />
    </div>

    <RentalInvoiceBody :rental="rental" />
  </div>

  <!-- Print-only: teleported directly to body so it isn't clipped by parent containers -->
  <Teleport to="body">
    <div v-if="rental" class="rental-invoice-print-only">
      <RentalInvoiceBody :rental="rental" />
    </div>
  </Teleport>
</template>
