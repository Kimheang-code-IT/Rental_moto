<script setup lang="ts">
definePageMeta({ titleKey: 'rental.pages.rentals', permission: 'rental.rentals.view' })

const route = useRoute()
const rentalId = computed(() => String(route.params.id || ''))

function onCancel() {
  void navigateTo('/rentals')
}
</script>

<template>
  <RentalCreatePanel
    mode="detail"
    :rental-id="rentalId"
    @cancel="onCancel"
  />
</template>
