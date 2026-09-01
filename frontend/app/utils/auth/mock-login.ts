import type { AuthUser } from '~/types/auth-user'
import type { SourcePermission } from '~/types/rental/domain'
import { SOURCE_PERMISSIONS } from '~/types/rental/domain'
import { getAllSystemPermissionKeys } from '~/utils/auth/user-permissions'

export type MockLoginAccount = {
  email: string
  password: string
  user: AuthUser
}

const ALL_SOURCE = [...SOURCE_PERMISSIONS] as SourcePermission[]

const STAFF_SOURCE: SourcePermission[] = [
  'settings.read',
  'attachment.read',
  'attachment.upload',
  'report.read',
]

const VIEWER_SOURCE: SourcePermission[] = [
  'settings.read',
  'attachment.read',
  'audit_log.read',
  'report.read',
]

const RENTAL_STAFF_PAGES = [
  'dashboard.view',
  'rental.motorcycles.view',
  'rental.motorcycles.create',
  'rental.motorcycles.edit',
  'rental.customers.view',
  'rental.customers.create',
  'rental.customers.edit',
  'rental.rentals.view',
  'rental.rentals.create',
  'rental.rentals.edit',
  'rental.rentals.print',
  'rental.rentals.return',
  'rental.finance.view',
  'rental.finance.create',
  'reports.view',
  'reports.print',
]

const RENTAL_VIEWER_PAGES = [
  'dashboard.view',
  'rental.motorcycles.view',
  'rental.customers.view',
  'rental.rentals.view',
  'rental.rentals.print',
  'rental.finance.view',
  'reports.view',
  'reports.print',
]

function avatar(name: string, bg: string) {
  return `https://ui-avatars.com/api/?name=${encodeURIComponent(name)}&background=${bg}&color=fff`
}

/** All page keys except Configuration and Administration sidebar groups. */
function getStaffUserPermissionKeys(): string[] {
  return getAllSystemPermissionKeys().filter((key) => {
    if (key.startsWith('configuration.')) return false
    if (key.startsWith('admin.')) return false
    if (key.startsWith('settings.')) return false
    return true
  })
}

const STAFF_USER_PAGES = getStaffUserPermissionKeys()

/** Frontend-only demo accounts. Replace with real API auth later. */
export const MOCK_LOGIN_ACCOUNTS: MockLoginAccount[] = [
  {
    email: 'admin@gmail.com',
    password: '123456',
    user: {
      id: 1,
      name: 'System Administrator',
      email: 'admin@gmail.com',
      role: 'SuperAdmin',
      avatar: avatar('System Administrator', 'e8472a'),
      pageAccess: ['ALL_PAGES'],
      permissions: getAllSystemPermissionKeys(),
      sourcePermissions: ALL_SOURCE,
    },
  },
  {
    email: 'user@gmail.com',
    password: '123456',
    user: {
      id: 7,
      name: 'Standard User',
      email: 'user@gmail.com',
      role: 'Rental Staff',
      avatar: avatar('Standard User', '059669'),
      pageAccess: STAFF_USER_PAGES,
      permissions: STAFF_USER_PAGES,
      sourcePermissions: STAFF_SOURCE,
    },
  },
  {
    email: 'owner@rental.local',
    password: '123456',
    user: {
      id: 2,
      name: 'HollyWing Admin',
      email: 'owner@rental.local',
      role: 'Owner',
      avatar: avatar('HollyWing Admin', '3a539f'),
      pageAccess: ['ALL_PAGES'],
      permissions: getAllSystemPermissionKeys(),
      sourcePermissions: ALL_SOURCE,
    },
  },
  {
    email: 'demo@other.local',
    password: '123456',
    user: {
      id: 6,
      name: 'Demo Operator',
      email: 'demo@other.local',
      role: 'Rental Staff',
      avatar: avatar('Demo Operator', '7c3aed'),
      pageAccess: RENTAL_STAFF_PAGES,
      permissions: RENTAL_STAFF_PAGES,
      sourcePermissions: STAFF_SOURCE,
    },
  },
  {
    email: 'staff@rental.local',
    password: '123456',
    user: {
      id: 8,
      name: 'Rental Staff',
      email: 'staff@rental.local',
      role: 'Rental Staff',
      avatar: avatar('Rental Staff', 'b45309'),
      pageAccess: RENTAL_STAFF_PAGES,
      permissions: RENTAL_STAFF_PAGES,
      sourcePermissions: STAFF_SOURCE,
    },
  },
  {
    email: 'viewer@rental.local',
    password: '123456',
    user: {
      id: 9,
      name: 'Report Viewer',
      email: 'viewer@rental.local',
      role: 'Report Viewer',
      avatar: avatar('Report Viewer', '475569'),
      pageAccess: RENTAL_VIEWER_PAGES,
      permissions: RENTAL_VIEWER_PAGES,
      sourcePermissions: VIEWER_SOURCE,
    },
  },
]

export function findMockLoginAccount(email: string) {
  const normalized = email.trim().toLowerCase()
  return MOCK_LOGIN_ACCOUNTS.find(a => a.email.toLowerCase() === normalized) ?? null
}

export function authenticateMock(email: string, password: string): AuthUser | null {
  const account = findMockLoginAccount(email)
  if (!account || account.password !== password) return null
  return { ...account.user, sourcePermissions: [...(account.user.sourcePermissions || [])] }
}
