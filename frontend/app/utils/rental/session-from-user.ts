import type { AuthUser } from '~/types/auth-user'
import type { RentalSession } from '~/types/rental/session'
import { allSourcePermissions, userSourcePermissions } from '~/utils/rental/permissions'

export function sessionFromUser(
  user: AuthUser | null | undefined,
): RentalSession {
  const source = userSourcePermissions(user)
  return {
    userId: user?.id || 0,
    userName: user?.name || 'System',
    sourcePermissions: source.length ? source : (user?.pageAccess?.includes('ALL_PAGES') ? allSourcePermissions() : []),
  }
}
