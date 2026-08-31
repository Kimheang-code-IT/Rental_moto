import type { AppRecord } from '~/config/admin-seed'
import { createAdminSeed } from '~/config/admin-seed'
import {
  BRANCH_BAVET_ID,
  BRANCH_DEMO_ID,
  BRANCH_PP_ID,
  DEMO_ORG_ID,
  LCS_ORG_ID,
} from '~/config/lcs-tenant'
import { permissionRowsToFlatKeys, seedRolePermissionRows } from '~/utils/role/permissions'

function stamp<T extends AppRecord>(row: T, organizationId: number, branchId: number, extra: Record<string, unknown> = {}): T {
  return { organizationId, branchId, createdByUserId: 1, ...row, ...extra }
}

function stampAll(rows: AppRecord[] | undefined, organizationId: number, branchId: number) {
  return (rows || []).map(row => stamp(row, organizationId, branchId))
}

/** Administration seed: users, roles, audit logs, org/branch, sequences, settings. */
export function createLcsSeed(): Record<string, AppRecord[]> {
  const base = createAdminSeed()

  const users = stampAll(base.users, LCS_ORG_ID, BRANCH_BAVET_ID).map((row, index) => {
    const rentalRoles = ['Admin', 'Rental Staff', 'Report Viewer', 'Rental Staff'] as const
    const role = rentalRoles[index] || 'Rental Staff'
    return {
      ...row,
      userCode: `USR-${String(index + 1).padStart(3, '0')}`,
      displayName: row.name,
      locale: 'en',
      timezone: 'Asia/Phnom_Penh',
      defaultBranch: index === 2 ? 'Phnom Penh' : 'Bavet',
      lastLogin: `2026-08-${String(20 - index).padStart(2, '0')}T09:30:00`,
      organization: 'HollyWing Motor',
      branch: index === 2 ? 'All branches' : 'Bavet',
      telegram: index === 0 ? '@hollywing.admin' : '',
      role,
      roleAssignments: [{ role, organization: 'HollyWing Motor', branch: index === 2 ? 'All branches' : 'Bavet', effectiveDate: '2026-01-01', expiryDate: '', assignedBy: 'System Administrator' }],
      branchAssignments: [{ organization: 'HollyWing Motor', branch: index === 2 ? 'Phnom Penh' : 'Bavet', isDefault: 'Yes', startDate: '2026-01-01', expiryDate: '' }],
      sessions: [{ startedAt: '2026-08-20 08:30', lastSeenAt: '2026-08-20 11:45', ipAddress: '10.0.0.24', device: 'Chrome on Windows', status: 'Active' }],
      auditHistory: [{ occurredAt: '2026-08-20 08:30', action: 'Signed in', result: 'SUCCESS', requestId: `req-user-${index + 1}` }],
    }
  })

  const roles = stampAll(base.roles, LCS_ORG_ID, BRANCH_BAVET_ID).map((row, index) => {
    const mode = index === 0 ? 'all' : index === 1 ? 'staff' : 'viewer'
    const permissionRows = seedRolePermissionRows(mode)
    const rentalNames = ['Admin', 'Rental Staff', 'Report Viewer']
    const descriptions = [
      'Full access to rental operations and administration.',
      'Day-to-day motorcycle rental and customer handling.',
      'Read-only access to rental reports and dashboards.',
    ]
    const name = rentalNames[index] || String(row.name || `Role ${index + 1}`)
    return {
      ...row,
      name,
      description: descriptions[index] || '',
      code: `ROLE_${name.toUpperCase().replace(/\W+/g, '_')}`,
      systemRole: index < 2 ? 'Yes' : 'No',
      permissionRows,
      permissionCount: permissionRowsToFlatKeys(permissionRows).length,
    }
  })

  const auditLogs = [
    ...stampAll(base.auditLogs, LCS_ORG_ID, BRANCH_BAVET_ID),
    stamp({
      id: 'log-004',
      occurredAt: '2026-08-20 11:41',
      user: 'Dara C.',
      action: 'Payment recorded',
      eventType: 'RENTAL_PAYMENT', entityType: 'Rental', entity: 'RNT-2026-000003', organizationName: 'HollyWing Motor', branchName: 'Bavet', result: 'SUCCESS', reason: '', requestId: 'req-rent-0041', correlationId: 'corr-rent-0041', beforeData: '{"outstanding":250}', afterData: '{"outstanding":0}', metadata: '{"payment":"RNP-000003"}',
    } as AppRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
  ]

  return {
    users,
    roles,
    auditLogs,
    organizations: [
      { id: 'org-001', organizationId: LCS_ORG_ID, branchId: BRANCH_BAVET_ID, organizationCode: 'HWM', legalName: 'HollyWing Motor Co., Ltd.', displayName: 'HollyWing Motor', taxIdentifier: 'K001-901234567', country: 'Cambodia', defaultCurrency: 'USD', timezone: 'Asia/Phnom_Penh', status: 'Active' },
      { id: 'org-002', organizationId: DEMO_ORG_ID, branchId: BRANCH_DEMO_ID, organizationCode: 'DEMO', legalName: 'Demo Rental Ltd.', displayName: 'Demo Rental', taxIdentifier: 'K001-DEMO', country: 'Cambodia', defaultCurrency: 'USD', timezone: 'Asia/Phnom_Penh', status: 'Active' },
    ],
    branches: [
      stamp({ id: 'br-001', branchCode: 'PPH', name: 'Phnom Penh', place: 'Phnom Penh', address: 'St. 271, Phnom Penh', phone: '+855 23 555 101', email: 'shop@hollywing.local', headOffice: 'Yes', status: 'Active' } as AppRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'br-002', branchCode: 'SR', name: 'Siem Reap', place: 'Siem Reap', address: 'Siem Reap, Cambodia', phone: '+855 63 555 102', email: 'sr@hollywing.local', headOffice: 'No', status: 'Active' } as AppRecord, LCS_ORG_ID, BRANCH_PP_ID),
      stamp({ id: 'br-003', branchCode: 'HQ', name: 'Demo HQ', place: 'Phnom Penh', address: 'Demo address', headOffice: 'Yes', status: 'Active' } as AppRecord, DEMO_ORG_ID, BRANCH_DEMO_ID),
    ],
    documentSequences: [
      ...['RENTAL', 'PAYMENT', 'CHARGE', 'EXPENSE'].map((documentType, index) => stamp({
        id: `seq-${index + 1}`,
        documentType,
        year: 2026,
        prefix: ['RNT', 'RNP', 'RNC', 'RNX'][index],
        lastValue: [8, 9, 4, 9][index],
        paddingLength: 6,
        resetRule: index === 0 ? 'Yearly' : 'Never',
        status: 'ACTIVE',
      } as AppRecord, LCS_ORG_ID, BRANCH_BAVET_ID)),
    ],
    systemSettings: [
      stamp({ id: 'set-001', organizationName: 'HollyWing Motor', branchName: '', settingKey: 'default_currency', settingValue: 'USD', displayValue: 'USD', scope: 'Organization', sensitive: 'No', updatedBy: 'System Administrator', updatedAt: '2026-08-20T08:00:00' } as AppRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
      stamp({ id: 'set-002', organizationName: 'HollyWing Motor', branchName: 'Phnom Penh', settingKey: 'telegram_bot_token', settingValue: '••••••••', displayValue: '••••••••', scope: 'Organization', sensitive: 'Yes', updatedBy: 'System Administrator', updatedAt: '2026-08-18T10:00:00' } as AppRecord, LCS_ORG_ID, BRANCH_BAVET_ID),
    ],
  }
}
