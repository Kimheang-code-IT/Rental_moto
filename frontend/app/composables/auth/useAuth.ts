import type { AuthUser } from '~/types/auth-user'
import { mockLatency, ok } from '~/mocks/query'
import { clearTokens, getAccessToken, hasTokens, setTokens } from '~/utils/auth/tokens'
import { ApiEndpoints } from '~/utils/constants/api-endpoints'

type LoginResult = { user: AuthUser }

interface AuthTokenPairResponse {
  accessToken: string
  refreshToken: string
  tokenType: string
  expiresIn: number
  refreshExpiresIn?: number
  user?: AuthUser
}

/**
 * Mock-mode auth operations. The six-digit code is fixed for offline demos and
 * the mock backend keeps password/avatar edits in the mock account fixtures.
 */
function useMockAuth() {
  async function loginWithCredentials(email: string, password: string) {
    const { authenticateMock } = await import('~/utils/auth/mock-login')
    await mockLatency(null, 80)
    const user = authenticateMock(email, password)
    if (!user) throw createError({ statusCode: 401, statusMessage: 'Invalid credentials' })
    return ok<LoginResult>({ user })
  }

  async function requestPasswordReset(_email: string) {
    // Mock: reset code is delivered via Telegram bot (not email).
    await mockLatency(null, 80)
    return ok({ sent: true, channel: 'telegram' as const })
  }

  async function verifyPasswordResetCode(_email: string, code: string) {
    const { MOCK_RESET_CODE } = await import('~/utils/auth/password-reset')
    await mockLatency(null, 80)
    if (code !== MOCK_RESET_CODE) throw createError({ statusCode: 400, statusMessage: 'Invalid code' })
    return ok({ verified: true, resetToken: `mock-reset-${MOCK_RESET_CODE}` })
  }

  async function resendPasswordResetCode(_email: string) {
    // Mock: resend via Telegram bot chatbot.
    await mockLatency(null, 80)
    return ok({ sent: true, channel: 'telegram' as const })
  }

  async function resetPasswordWithCode(input: {
    email: string
    resetToken?: string
    code?: string
    password: string
    passwordConfirmation: string
  }) {
    const { MOCK_RESET_CODE } = await import('~/utils/auth/password-reset')
    await mockLatency(null, 80)
    const tokenValid = input.resetToken === `mock-reset-${MOCK_RESET_CODE}`
    if (!tokenValid || input.password !== input.passwordConfirmation) {
      throw createError({ statusCode: 400, statusMessage: 'Invalid reset request' })
    }
    return ok({ reset: true })
  }

  async function changePassword(input: {
    currentPassword: string
    password: string
    passwordConfirmation: string
  }) {
    const auth = useAuthStore()
    const email = auth.user?.email
    if (!email) throw createError({ statusCode: 401, statusMessage: 'Not signed in' })
    if (input.password !== input.passwordConfirmation) {
      throw createError({ statusCode: 400, statusMessage: 'Passwords do not match' })
    }
    const { findMockLoginAccount } = await import('~/utils/auth/mock-login')
    await mockLatency(null, 80)
    const account = findMockLoginAccount(email)
    if (!account || account.password !== input.currentPassword) {
      throw createError({ statusCode: 401, statusMessage: 'Current password is incorrect' })
    }
    account.password = input.password
    return ok({ changed: true })
  }

  async function updateProfileAvatar(avatar: string) {
    const auth = useAuthStore()
    const email = auth.user?.email
    if (!email) throw createError({ statusCode: 401, statusMessage: 'Not signed in' })
    const { findMockLoginAccount } = await import('~/utils/auth/mock-login')
    await mockLatency(null, 80)
    const account = findMockLoginAccount(email)
    if (account) account.user.avatar = avatar
    auth.updateUser({ avatar })
    return ok({ avatar })
  }

  async function removeProfileAvatar() {
    const auth = useAuthStore()
    const email = auth.user?.email
    if (!email) throw createError({ statusCode: 401, statusMessage: 'Not signed in' })
    const { findMockLoginAccount } = await import('~/utils/auth/mock-login')
    await mockLatency(null, 80)
    const account = findMockLoginAccount(email)
    if (account) delete account.user.avatar
    auth.updateUser({ avatar: undefined })
    return ok({ removed: true })
  }

  async function logoutServer() {
    await mockLatency(null, 40)
    return ok({ message: 'Logged out' })
  }

  return {
    loginWithCredentials,
    requestPasswordReset,
    verifyPasswordResetCode,
    resendPasswordResetCode,
    resetPasswordWithCode,
    changePassword,
    updateProfileAvatar,
    removeProfileAvatar,
    logoutServer,
  }
}

/**
 * HTTP-mode auth operations against `/api/v2/auth/*`.
 * `useApi()` handles bearer attachment, refresh rotation, and error shapes.
 */
function useHttpAuth() {
  const api = useApi()

  async function unwrap<T>(response: { data: T } | T): Promise<T> {
    if (response && typeof response === 'object' && 'data' in (response as object)) {
      return (response as { data: T }).data
    }
    return response as T
  }

  async function loginWithCredentials(email: string, password: string) {
    const payload = await unwrap<AuthTokenPairResponse>(await api.post<AuthTokenPairResponse | { data: AuthTokenPairResponse }>(
      ApiEndpoints.AUTH_LOGIN,
      { email, password },
      { isAuthRequest: true, suppressErrorToast: true },
    ))
    setTokens(payload.accessToken, payload.refreshToken)
    const user = payload.user
    if (!user) throw createError({ statusCode: 401, statusMessage: 'Invalid credentials' })
    return ok<LoginResult>({ user })
  }

  async function requestPasswordReset(email: string) {
    await api.post(ApiEndpoints.AUTH_FORGOT_PASSWORD, { email }, { isAuthRequest: true })
    return ok({ sent: true, channel: 'telegram' as const })
  }

  async function verifyPasswordResetCode(email: string, code: string) {
    const result = await unwrap<{ resetToken: string }>(await api.post<{ resetToken: string } | { data: { resetToken: string } }>(
      ApiEndpoints.AUTH_RESET_VERIFY,
      { email, code },
      { isAuthRequest: true, suppressErrorToast: true },
    ))
    return ok({ verified: true, resetToken: result.resetToken })
  }

  async function resendPasswordResetCode(email: string) {
    await api.post(ApiEndpoints.AUTH_RESET_RESEND, { email }, { isAuthRequest: true })
    return ok({ sent: true, channel: 'telegram' as const })
  }

  async function resetPasswordWithCode(input: {
    email: string
    resetToken?: string
    code?: string
    password: string
    passwordConfirmation: string
  }) {
    if (!input.resetToken) {
      throw createError({ statusCode: 400, statusMessage: 'Reset session expired. Verify the code again.' })
    }
    if (input.password !== input.passwordConfirmation) {
      throw createError({ statusCode: 400, statusMessage: 'Passwords do not match' })
    }
    await api.post(ApiEndpoints.AUTH_RESET_PASSWORD, {
      email: input.email,
      resetToken: input.resetToken,
      newPassword: input.password,
    }, { isAuthRequest: true })
    return ok({ reset: true })
  }

  async function changePassword(input: {
    currentPassword: string
    password: string
    passwordConfirmation: string
  }) {
    const auth = useAuthStore()
    if (!auth.user) throw createError({ statusCode: 401, statusMessage: 'Not signed in' })
    if (input.password !== input.passwordConfirmation) {
      throw createError({ statusCode: 400, statusMessage: 'Passwords do not match' })
    }
    await api.post(ApiEndpoints.AUTH_CHANGE_PASSWORD, {
      currentPassword: input.currentPassword,
      newPassword: input.password,
    })
    return ok({ changed: true })
  }

  async function updateProfileAvatar(avatar: string) {
    const auth = useAuthStore()
    if (!auth.user) throw createError({ statusCode: 401, statusMessage: 'Not signed in' })
    await api.patch(ApiEndpoints.AUTH_PROFILE_AVATAR, { avatar })
    auth.updateUser({ avatar })
    return ok({ avatar })
  }

  async function removeProfileAvatar() {
    const auth = useAuthStore()
    if (!auth.user) throw createError({ statusCode: 401, statusMessage: 'Not signed in' })
    await api.patch(ApiEndpoints.AUTH_PROFILE_AVATAR, { avatar: null })
    auth.updateUser({ avatar: undefined })
    return ok({ removed: true })
  }

  async function logoutServer(refreshToken: string | null) {
    if (!refreshToken) return ok({ message: 'Logged out' })
    try {
      await api.post(ApiEndpoints.AUTH_LOGOUT, { refreshToken }, { isAuthRequest: true, suppressErrorToast: true, suppressAccessAlert: true })
    }
    catch {
      // Server logout is best-effort; client state is cleared regardless.
    }
    return ok({ message: 'Logged out' })
  }

  return {
    loginWithCredentials,
    requestPasswordReset,
    verifyPasswordResetCode,
    resendPasswordResetCode,
    resetPasswordWithCode,
    changePassword,
    updateProfileAvatar,
    removeProfileAvatar,
    logoutServer,
  }
}

export function useAuth() {
  const config = useRuntimeConfig()
  const useHttp = config.public.useMockData === false

  const implementation = useHttp ? useHttpAuth() : useMockAuth()

  /** Refresh the stored user profile from `GET /auth/me` (HTTP mode only). */
  async function hydrateSessionFromApi(): Promise<AuthUser | null> {
    if (!useHttp || !hasTokens()) return null
    try {
      const api = useApi()
      const me = await api.get<AuthUser | { data: AuthUser }>(ApiEndpoints.AUTH_ME, {
        suppressAccessAlert: true,
        suppressErrorToast: true,
      })
      const user = me && typeof me === 'object' && 'data' in (me as object)
        ? (me as { data: AuthUser }).data
        : me as AuthUser
      if (user?.email) {
        useAuthStore().login(user)
        return user
      }
    }
    catch {
      // Expired/invalid session: /auth/me returned 401 and useApi() already
      // attempted one refresh. Clear stale display data when still unauthorized.
      if (!getAccessToken()) clearTokens()
    }
    return null
  }

  /** Server logout with the refresh token, then always clear client state. */
  async function logout() {
    const { getRefreshToken } = await import('~/utils/auth/tokens')
    await implementation.logoutServer(useHttp ? getRefreshToken() : null)
    await useAuthStore().logout()
  }

  return {
    ...implementation,
    logout,
    hydrateSessionFromApi,
    isHttpMode: useHttp,
  }
}
