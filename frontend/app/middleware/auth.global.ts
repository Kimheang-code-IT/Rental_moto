import { useSetupStatus } from '~/composables/auth/useSetupStatus'
import { safeInternalPath } from '~/utils/auth/session'
import { resolvePermissionDenialRoute } from '~/utils/auth/access-redirect'

export default defineNuxtRouteMiddleware(async (to, from) => {
  const auth = useAuthStore()
  const { ensureSetupStatus, needsSetup } = useSetupStatus()

  if (import.meta.client && auth.user && !auth.hasSessionTokens()) {
    auth.clearSession()
  }

  const path = to.path.replace(/\/+$/, '') || '/'
  const isSetupPage = path === '/auth/setup'

  // First-run bootstrap: while no user exists, everything routes to /auth/setup.
  // Skip on server/prerender so a build-time miss is not frozen into the SPA.
  if (import.meta.client) {
    try {
      await ensureSetupStatus()
    }
    catch {
      // Unreachable API must not crash boot; fall through to login.
    }
  }
  if (needsSetup.value) {
    if (!isSetupPage) return navigateTo('/auth/setup', { replace: true })
    return
  }
  if (isSetupPage) return navigateTo('/auth/login', { replace: true })

  const publicPaths = [
    '/auth/login',
    '/auth/forget-password',
    '/auth/verify-code',
    '/auth/reset-password',
  ]
  const isPublicPage = publicPaths.includes(path)

  if (!auth.isLoggedIn && !isPublicPage) {
    return navigateTo({
      path: '/auth/login',
      query: { redirect: to.fullPath },
    }, { replace: true })
  }

  if (auth.isLoggedIn && isPublicPage) {
    return navigateTo(safeInternalPath(to.query.redirect) || '/', { replace: true })
  }

  const permission = typeof to.meta.permission === 'string' ? to.meta.permission : ''
  if (auth.isLoggedIn && permission && !auth.canAccessPage(permission)) {
    // Fail closed without a modal: abort in-place navigation, send a direct
    // URL to the first permitted landing route, or back to sign-in.
    const denial = resolvePermissionDenialRoute({
      canAccessPage: permissionKey => auth.canAccessPage(permissionKey),
      navigatedFromAnotherPage: Boolean(from.matched.length) && from.path !== to.path,
    })

    if (denial.action === 'abort') {
      try {
        const toast = useToast()
        const { t } = useI18n()
        toast.add({
          title: t('core.states.accessDeniedTitle'),
          description: t('core.states.accessDeniedDescription'),
          color: 'error',
        })
      }
      catch {
        // Toast/i18n must never block navigation denial handling.
      }
      return abortNavigation()
    }

    if (denial.action === 'redirect') return navigateTo(denial.to, { replace: true })

    auth.clearSession()
    return navigateTo('/auth/login', { replace: true })
  }
})
