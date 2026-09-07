<script setup lang="ts">
definePageMeta({ titleKey: 'rental.pages.rentals', permission: 'rental.rentals.create' })

function onCancel() {
  void navigateTo('/rentals')
}
</script>

<template>
  <RentalCreatePanel @cancel="onCancel" />
</template>
