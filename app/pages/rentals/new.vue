<script setup lang="ts">
definePageMeta({ titleKey: 'rental.pages.rentals', permission: 'rental.rentals.view' })

function onCancel() {
  void navigateTo('/rentals')
}
</script>

<template>
  <RentalCreatePanel @cancel="onCancel" @created="id => navigateTo(`/rentals/${id}`)" />
</template>
