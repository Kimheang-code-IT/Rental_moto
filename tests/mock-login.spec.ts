import { describe, expect, it } from 'vitest'
import { authenticateMock, findMockLoginAccount } from '../app/utils/auth/mock-login'
import { getAllSystemPermissionKeys } from '../app/utils/auth/user-permissions'

describe('mock login accounts', () => {
  it('authenticates admin@gmail.com with full access', () => {
    const user = authenticateMock('admin@gmail.com', '123456')
    expect(user?.email).toBe('admin@gmail.com')
    expect(user?.pageAccess).toContain('ALL_PAGES')
    expect(user?.permissions).toEqual(getAllSystemPermissionKeys())
  })

  it('authenticates user@gmail.com without configuration or administration pages', () => {
    const user = authenticateMock('user@gmail.com', '123456')
    expect(user?.email).toBe('user@gmail.com')

    const deniedPrefixes = ['configuration.', 'admin.', 'settings.']
    for (const key of user?.permissions || []) {
      expect(deniedPrefixes.some(prefix => key.startsWith(prefix))).toBe(false)
    }

    expect(user?.permissions).toContain('dashboard.view')
    expect(user?.permissions).toContain('rental.motorcycles.view')
    expect(user?.permissions).toContain('rental.customers.view')
    expect(user?.permissions).toContain('rental.rentals.edit')
    expect(user?.permissions).toContain('rental.finance.view')
    expect(user?.permissions).toContain('reports.view')
  })

  it('rejects invalid credentials', () => {
    expect(authenticateMock('user@gmail.com', 'wrong')).toBeNull()
    expect(findMockLoginAccount('unknown@example.com')).toBeNull()
  })
})
