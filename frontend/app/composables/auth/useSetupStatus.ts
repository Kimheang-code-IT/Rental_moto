import { ApiEndpoints } from '~/utils/constants/api-endpoints'
import { isAutoApiBase, isSameOriginApiBase, resolveApiBase } from '~/utils/api/base-url'

type SetupStatusPayload = { needsSetup?: boolean }

/** Module-level single-flight so parallel middleware runs share one request. */
let setupStatusInflight: Promise<boolean> | null = null

/**
 * Caches `GET /auth/setup-status` so the route guard can force first-run
 * setup without refetching on every navigation. `null` means "not known yet".
 *
 * Uses `$fetch` directly (not `useApi`) so middleware can call this before
 * toast/i18n composables are safe to instantiate.
 */
export function useSetupStatus() {
  const needsSetup = useState<boolean | null>('auth-needs-setup', () => null)

  async function fetchSetupStatusRaw(): Promise<boolean> {
    const config = useRuntimeConfig()
    const configuredBase = String(config.public.apiBase || '')
    const requireSecureApi = import.meta.env.PROD
      && config.public.useMockData === false
      && !isAutoApiBase(configuredBase)
      && !isSameOriginApiBase(configuredBase)

    const baseURL = resolveApiBase({
      configured: configuredBase,
      internalBase: import.meta.server ? String(config.apiInternalBase || '') : undefined,
      requireHttps: requireSecureApi,
    })
    if (!baseURL) {
      throw new Error('API base unavailable')
    }

    const response = await $fetch<SetupStatusPayload | { data: SetupStatusPayload }>(
      ApiEndpoints.AUTH_SETUP_STATUS,
      {
        baseURL,
        method: 'GET',
        credentials: 'omit',
        headers: { Accept: 'application/json' },
      },
    )

    const payload = response && typeof response === 'object' && 'data' in response
      ? (response as { data: SetupStatusPayload }).data
      : (response as SetupStatusPayload)

    return Boolean(payload?.needsSetup)
  }

  /**
   * Fetch once on success. Transient failures (API still booting / 502) leave
   * the cache as `null` so the next navigation retries instead of locking the
   * user on the login page.
   */
  async function ensureSetupStatus(): Promise<boolean> {
    if (import.meta.server) {
      // Do not pin a build-time answer into the SPA payload.
      return false
    }

    if (needsSetup.value !== null) return Boolean(needsSetup.value)

    if (!setupStatusInflight) {
      setupStatusInflight = fetchSetupStatusRaw()
        .then((value) => {
          needsSetup.value = value
          return value
        })
        .catch(() => false)
        .finally(() => {
          setupStatusInflight = null
        })
    }

    return Boolean(await setupStatusInflight)
  }

  function markConfigured() {
    needsSetup.value = false
  }

  return { needsSetup, ensureSetupStatus, markConfigured }
}
