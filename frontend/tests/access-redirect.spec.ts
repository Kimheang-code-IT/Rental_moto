import { describe, expect, it } from 'vitest'
import { existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { canLoadProtectedAppSettings, resolvePermissionDenialRoute } from '../app/utils/auth/access-redirect'

const appRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../app')

describe('permission-denial navigation (no modal host)', () => {
  const staff = (permission: string) =>
    [
      'dashboard.view',
      'rental.motorcycles.view',
      'rental.motorcycles.edit',
      'rental.rentals.view',
    ].includes(permission)

  it('aborts in-place navigation so the user stays on the current page', () => {
    const denial = resolvePermissionDenialRoute({
      canAccessPage: staff,
      navigatedFromAnotherPage: true,
    })
    expect(denial).toEqual({ action: 'abort' })
  })

  it('sends a direct URL to the first permitted landing route', () => {
    const denial = resolvePermissionDenialRoute({
      canAccessPage: staff,
      navigatedFromAnotherPage: false,
    })
    // dashboard.view is granted, so / is the first permitted landing route.
    expect(denial).toEqual({ action: 'redirect', to: '/' })
  })

  it('redirects past pages the user cannot open', () => {
    const withoutDashboard = (permission: string) => permission === 'rental.rentals.view'
    const denial = resolvePermissionDenialRoute({
      canAccessPage: withoutDashboard,
      navigatedFromAnotherPage: false,
    })
    expect(denial).toEqual({ action: 'redirect', to: '/rentals' })
  })

  it('clears the session and returns to login when nothing is permitted', () => {
    const denial = resolvePermissionDenialRoute({
      canAccessPage: () => false,
      navigatedFromAnotherPage: false,
    })
    expect(denial).toEqual({ action: 'clear-session-login' })
  })

  it('does not load protected app settings without view permission', () => {
    expect(canLoadProtectedAppSettings(() => false)).toBe(false)
    expect(canLoadProtectedAppSettings(staff)).toBe(false)
    expect(canLoadProtectedAppSettings(permission => permission === 'settings.app_config.view')).toBe(true)
  })

  it('the AppAccessAlertHost and its composable are removed from the app', () => {
    expect(existsSync(resolve(appRoot, 'components/common/AppAccessAlertHost.vue'))).toBe(false)
    expect(existsSync(resolve(appRoot, 'composables/common/useAccessAlert.ts'))).toBe(false)
  })
})
