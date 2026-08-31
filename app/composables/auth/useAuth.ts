import type { AuthUser } from '~/types/auth-user'
import { mockLatency, ok } from '~/mocks/query'

type LoginResult = { user: AuthUser }

export function useAuth() {
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
    return ok({ verified: true })
  }

  async function resendPasswordResetCode(_email: string) {
    // Mock: resend via Telegram bot chatbot.
    await mockLatency(null, 80)
    return ok({ sent: true, channel: 'telegram' as const })
  }

  async function resetPasswordWithCode(input: {
    email: string
    code: string
    password: string
    passwordConfirmation: string
  }) {
    const { MOCK_RESET_CODE } = await import('~/utils/auth/password-reset')
    await mockLatency(null, 80)
    if (input.code !== MOCK_RESET_CODE || input.password !== input.passwordConfirmation) {
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

  return {
    loginWithCredentials,
    requestPasswordReset,
    verifyPasswordResetCode,
    resendPasswordResetCode,
    resetPasswordWithCode,
    changePassword,
    updateProfileAvatar,
    removeProfileAvatar,
  }
}
