/** Tenant/auth permission types for the HollyWing Motor rental system. */

export type PermissionScope = 'ORGANIZATION' | 'BRANCH' | 'OWN' | 'NONE'

export type LcsErrorCode =
  | 'AUTH_REQUIRED'
  | 'ACCESS_DENIED'
  | 'ORGANIZATION_CONTEXT_REQUIRED'
  | 'BRANCH_SCOPE_DENIED'
  | 'REFERENCE_NOT_FOUND'
  | 'REFERENCE_OUT_OF_SCOPE'

export interface LcsApiErrorBody {
  code: LcsErrorCode | string
  message: string
  request_id: string
  field_errors?: Record<string, string>
}

export interface LcsOrganization {
  id: number
  organization_code: string
  legal_name: string
  display_name: string
  address?: string
  phone?: string
  email?: string
  default_currency_code: string
  timezone: string
  status: string
}

export interface LcsBranch {
  id: number
  organization_id: number
  branch_code: string
  name: string
  is_head_office: boolean
  status: string
}

/** Source permission codes used by mock auth / tenant scope. */
export const SOURCE_PERMISSIONS = [
  'organization.read',
  'organization.update',
  'branch.read',
  'branch.manage',
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
