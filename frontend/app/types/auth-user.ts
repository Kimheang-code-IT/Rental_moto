import type { SourcePermission } from '~/types/rental/domain'

export interface AuthUser {
  id?: number
  name: string
  email: string
  role?: string
  avatar?: string
  /** Flat UI page keys. Frontend hiding is not authorization. */
  permissions?: string[]
  /** Route/page ids the user may access. Empty/undefined = no frontend restriction. */
  pageAccess?: string[]
  sourcePermissions?: SourcePermission[]
}
