import type { SourcePermission } from '~/types/rental/domain'

export interface AuthUser {
  id?: number
  name: string
  email: string
  role?: string
  roleId?: number
  /** True for the first-setup system owner; has ALL_PAGES without a role. */
  isOwner?: boolean
  avatar?: string
  telegramLinked?: boolean
  /** Flat UI page keys. Frontend hiding is not authorization. */
  permissions?: string[]
  effectivePermissions?: string[]
  /** Legacy mirror of effectivePermissions. */
  pageAccess?: string[]
  sourcePermissions?: SourcePermission[]
}
