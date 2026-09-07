/**
 * Pure decision logic for permission-denied navigation. Used by the global
 * auth middleware; the backend 403 remains the real deny, this is UX only.
 * No permission keys or request paths are shown to the user.
 */
export const PERMITTED_LANDING_ROUTES: ReadonlyArray<readonly [string, string]> = [
  ['/', 'dashboard.view'],
  ['/motorcycles', 'rental.motorcycles.view'],
  ['/rentals', 'rental.rentals.view'],
  ['/income-expense', 'rental.finance.view'],
  ['/rental-reports', 'reports.view'],
  ['/administration/users', 'admin.users.view'],
  ['/administration/system-settings', 'settings.app_config.view'],
] as const

export type PermissionDenialAction =
  | { action: 'abort' }
  | { action: 'redirect', to: string }
  | { action: 'clear-session-login' }

export function resolvePermissionDenialRoute(options: {
  canAccessPage: (permission: string) => boolean
  /** True when the user navigated from another page (vs. opening a URL directly). */
  navigatedFromAnotherPage: boolean
}): PermissionDenialAction {
  if (options.navigatedFromAnotherPage) return { action: 'abort' }
  const landing = PERMITTED_LANDING_ROUTES.find(([, required]) => options.canAccessPage(required))
  if (landing) return { action: 'redirect', to: landing[0] }
  return { action: 'clear-session-login' }
}

/** App-info/app-config GETs are settings-protected; skip them on boot without this permission. */
export function canLoadProtectedAppSettings(canAccessPage: (permission: string) => boolean) {
  return canAccessPage('settings.app_config.view')
}
