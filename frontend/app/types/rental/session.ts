import type { SourcePermission } from '~/types/rental/domain'

export interface RentalSession {
  userId: number
  userName: string
  sourcePermissions: SourcePermission[]
}
