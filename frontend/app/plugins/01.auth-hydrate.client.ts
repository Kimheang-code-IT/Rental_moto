export default defineNuxtPlugin(async () => {
  const auth = useAuthStore()
  auth.hydrateClient()

  // HTTP mode: never trust the stored display profile as proof of
  // authentication. When bearer tokens exist, re-validate via /auth/me.
  const config = useRuntimeConfig()
  if (config.public.useMockData === false && config.public.authMode === 'bearer') {
    const { useAuth } = await import('~/composables/auth/useAuth')
    const { hydrateSessionFromApi } = useAuth()
    await hydrateSessionFromApi()
  }
})
