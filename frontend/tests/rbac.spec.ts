import { describe, expect, it } from 'vitest'
import { flatKeysToPermissionRows, permissionRowsToFlatKeys } from '../app/utils/role/permissions'
import { resolveUserPermissionKeys } from '../app/utils/auth/user-permissions'

describe('role-only authorization', () => {
  it('serializes the authoritative role matrix', () => {
    const keys = ['rental.finance.view', 'rental.finance.delete', 'reports.view', 'reports.export']
    expect(permissionRowsToFlatKeys(flatKeysToPermissionRows(keys))).toEqual([...keys].sort())
  })

  it('fails closed when permissions are absent', () => {
    expect(resolveUserPermissionKeys({ name: 'No access', email: 'none@example.com' })).toEqual([])
  })

  it('uses effective permissions before compatibility fields', () => {
    expect(resolveUserPermissionKeys({
      name: 'Restricted',
      email: 'restricted@example.com',
      effectivePermissions: ['reports.view'],
      permissions: ['ALL_PAGES'],
      pageAccess: ['ALL_PAGES'],
    })).toEqual(['reports.view'])
  })

  it('starts the operator role form from an empty matrix (no preset roles)', () => {
    // The new-role form starts from ROLE_DOCUMENT_TYPES with no actions checked.
    expect(permissionRowsToFlatKeys(flatKeysToPermissionRows([]))).toEqual([])
  })

  it('treats ALL_PAGES as a permission key, not a reserved role name', () => {
    const rows = flatKeysToPermissionRows(['ALL_PAGES'])
    expect(permissionRowsToFlatKeys(rows)).toEqual(resolveUserPermissionKeys({
      name: 'Owner',
      email: 'owner@example.com',
      isOwner: true,
      effectivePermissions: ['ALL_PAGES'],
    }))
  })
})
