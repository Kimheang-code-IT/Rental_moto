/** JWT user permission types for the HollyWing Motor rental system. */

export type RentalErrorCode =
  | 'AUTH_REQUIRED'
  | 'ACCESS_DENIED'
  | 'REFERENCE_NOT_FOUND'

export interface RentalApiErrorBody {
  code: RentalErrorCode | string
  message: string
  request_id: string
  field_errors?: Record<string, string>
}

/** Permission codes carried by the authenticated user's JWT claims. */
export const SOURCE_PERMISSIONS = [
  'settings.read',
  'settings.update',
  'user.read',
  'user.manage',
  'role.read',
  'role.manage',
  'attachment.read',
  'attachment.upload',
  'attachment.delete',
  'audit_log.read',
  'report.read',
] as const

export type SourcePermission = typeof SOURCE_PERMISSIONS[number]
