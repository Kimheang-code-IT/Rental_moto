<script setup lang="ts">
import type { NuxtError } from '#app'

const props = defineProps<{
  error: NuxtError
}>()

const status = computed(() => Number(props.error?.statusCode) || 500)
const title = computed(() => (status.value === 404 ? 'Page not found' : 'Something went wrong'))
const description = computed(() => {
  if (status.value === 404) return 'We are sorry but this page could not be found.'
  return props.error?.statusMessage
    || props.error?.message
    || 'The app could not load. Hard-refresh (Ctrl+F5), then open the Wi-Fi URL again.'
})

// Keep error recovery free of i18n/SEO helpers — those caused nested boot failures.
useHead({ title: () => title.value })
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
    <p class="text-5xl font-semibold text-primary">{{ status }}</p>
    <h1 class="text-xl font-semibold">{{ title }}</h1>
    <p class="max-w-md text-sm text-muted">{{ description }}</p>
    <UButton to="/" color="primary" @click="clearError({ redirect: '/' })">
      Back to home
    </UButton>
  </div>
</template>
