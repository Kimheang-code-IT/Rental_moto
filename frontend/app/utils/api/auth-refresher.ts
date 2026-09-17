/**
 * Testable single-flight refresh-token rotation used by `useApi()`.
 *
 * Concurrent 401 responses share one rotation request; the original request is
 * retried at most once after a successful rotation. On rotation failure the
 * session is cleared exactly once through `onSessionExpired`.
 */

export interface AuthRefresherOptions {
  refreshEndpoint: string | (() => string)
  timeoutMs?: number
  getRefreshToken: () => string | null
  setTokens: (access: string, refresh: string | null) => void
  onSessionExpired: () => void
  /** Injectable request function returning the refresh response payload. */
  post?: (url: string, body: Record<string, unknown>, timeoutMs: number) => Promise<PostRefreshResponse>
}

export type PostRefreshResponse = {
  data?: { accessToken?: string, refreshToken?: string }
  accessToken?: string
  refreshToken?: string
}

export function createAuthRefresher(options: AuthRefresherOptions) {
  let refreshPromise: Promise<boolean> | null = null

  const defaultPost = async (url: string, body: Record<string, unknown>, timeoutMs: number): Promise<PostRefreshResponse> => {
    // Uses Nuxt's global $fetch; overridden in tests.
    return await $fetch<PostRefreshResponse>(url, {
      method: 'POST',
      body,
      timeout: timeoutMs,
    })
  }

  const post = options.post || defaultPost

  /**
   * Rotate the refresh token for a fresh access/refresh pair.
   * Returns true only when a new access token is stored.
   */
  function rotate(): Promise<boolean> {
    if (refreshPromise) return refreshPromise
    const refreshToken = options.getRefreshToken()
    if (!refreshToken) {
      options.onSessionExpired()
      return Promise.resolve(false)
    }
    refreshPromise = (async () => {
      try {
        const endpoint = typeof options.refreshEndpoint === 'function'
          ? options.refreshEndpoint()
          : options.refreshEndpoint
        const response = await post(endpoint, { refreshToken }, options.timeoutMs || 30000)
        const accessToken = response?.data?.accessToken || response?.accessToken
        const nextRefresh = response?.data?.refreshToken || response?.refreshToken || null
        if (!accessToken) {
          options.onSessionExpired()
          return false
        }
        options.setTokens(accessToken, nextRefresh)
        return true
      }
      catch {
        options.onSessionExpired()
        return false
      }
      finally {
        // Release the single-flight slot on the next macrotask so a request
        // failing right after a successful refresh can rotate again cleanly.
        setTimeout(() => {
          refreshPromise = null
        }, 0)
      }
    })()
    return refreshPromise
  }

  /** Test hook: clear the in-flight promise between scenarios. */
  function reset() {
    refreshPromise = null
  }

  return { rotate, reset }
}
