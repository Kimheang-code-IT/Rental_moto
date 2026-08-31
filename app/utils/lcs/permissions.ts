import type { PermissionScope, SourcePermission } from '~/types/lcs/domain'
import { SOURCE_PERMISSIONS } from '~/types/lcs/domain'
import type { AuthUser } from '~/types/auth-user'

/** Map UI page keys to source permission codes. Frontend hiding is not authorization. */
export const PAGE_TO_SOURCE: Record<string, SourcePermission | SourcePermission[]> = {
  'dashboard.view': 'report.read',
  'rental.motorcycles.view': 'report.read',
  'rental.customers.view': 'report.read',
  'rental.rentals.view': 'report.read',
  'rental.finance.view': 'report.read',
  'reports.view': 'report.read',
  'admin.users.view': 'user.read',
  'admin.roles.view': 'role.read',
  'admin.audit_logs.view': 'audit_log.read',
  'configuration.view': 'organization.read',
  'configuration.manage': 'organization.read',
  'settings.app_config.view': 'organization.read',
}

export function allSourcePermissions(): SourcePermission[] {
  return [...SOURCE_PERMISSIONS]
}

export function userSourcePermissions(user: AuthUser | null | undefined): SourcePermission[] {
  if (!user) return []
  if (user.pageAccess?.includes('ALL_PAGES') || user.permissions?.includes('ALL_PAGES')) {
    return allSourcePermissions()
  }
  if (user.sourcePermissions?.length) {
    return user.sourcePermissions.filter((code): code is SourcePermission =>
      (SOURCE_PERMISSIONS as readonly string[]).includes(code),
    )
  }
  return []
}

export function hasSourcePermission(user: AuthUser | null | undefined, code: SourcePermission) {
  return userSourcePermissions(user).includes(code)
}

export function userPermissionScope(user: AuthUser | null | undefined): PermissionScope {
  if (!user) return 'NONE'
  return user.permissionScope || 'BRANCH'
}

export function canSelectAllBranches(user: AuthUser | null | undefined) {
  return userPermissionScope(user) === 'ORGANIZATION'
}
