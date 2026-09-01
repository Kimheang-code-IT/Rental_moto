import { sessionFromUser } from '~/utils/rental/session-from-user'
import type { RentalSession } from '~/types/rental/session'
import type { SourcePermission } from '~/types/rental/domain'

export { sessionFromUser }

export function currentRentalSession(): RentalSession {
  const auth = useAuthStore()
  return sessionFromUser(auth.user)
}

export function hasSessionPermission(code: SourcePermission) {
  return currentRentalSession().sourcePermissions.includes(code)
}
