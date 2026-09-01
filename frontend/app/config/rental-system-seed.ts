import type { AppRecord } from '~/config/admin-seed'
import { createAdminSeed } from '~/config/admin-seed'
import { permissionRowsToFlatKeys, seedRolePermissionRows } from '~/utils/role/permissions'

function stamp<T extends AppRecord>(row: T, extra: Record<string, unknown> = {}): T {
  return { createdByUserId: 1, ...row, ...extra }
}

function stampAll(rows: AppRecord[] | undefined) {
  return (rows || []).map(row => stamp(row))
}

/** Administration seed: users, roles, audit logs, sequences, and settings. */
export function createRentalSystemSeed(): Record<string, AppRecord[]> {
  const base = createAdminSeed()

  const users = stampAll(base.users).map((row, index) => {
    const rentalRoles = ['Owner', 'Rental Staff', 'Accountant', 'Report Viewer'] as const
    const role = rentalRoles[index] || 'Rental Staff'
    return {
      ...row,
      userCode: `USR-${String(index + 1).padStart(3, '0')}`,
      displayName: row.name,
      locale: 'en',
      timezone: 'Asia/Phnom_Penh',
      lastLogin: `2026-08-${String(20 - index).padStart(2, '0')}T09:30:00`,
      telegramUsername: index === 0 ? '@hollywing.admin' : '',
      telegramChatId: index === 0 ? '100000001' : '',
      role,
      roleAssignments: [{ role, effectiveDate: '2026-01-01', expiryDate: '', assignedBy: 'System Administrator' }],
      sessions: [{ startedAt: '2026-08-20 08:30', lastSeenAt: '2026-08-20 11:45', ipAddress: '10.0.0.24', device: 'Chrome on Windows', status: 'Active' }],
      auditHistory: [{ occurredAt: '2026-08-20 08:30', action: 'Signed in', result: 'SUCCESS', requestId: `req-user-${index + 1}` }],
    }
  })

  const roles = stampAll(base.roles).map((row, index) => {
    const mode = index === 0 ? 'all' : index === 1 ? 'staff' : 'viewer'
    const permissionRows = seedRolePermissionRows(mode)
    const rentalNames = ['Owner', 'Rental Staff', 'Accountant', 'Report Viewer']
    const descriptions = [
      'Full access to rental operations and administration.',
      'Day-to-day motorcycle rental and customer handling.',
      'Read-only access to rental reports and dashboards.',
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
    ...stampAll(base.auditLogs),
    stamp({
      id: 'log-004',
      occurredAt: '2026-08-20 11:41',
      user: 'Dara C.',
      action: 'Payment recorded',
      eventType: 'RENTAL_PAYMENT', entityType: 'Rental', entity: 'RNT-2026-000003', result: 'SUCCESS', reason: '', requestId: 'req-rent-0041', correlationId: 'corr-rent-0041', beforeData: '{"outstanding":250}', afterData: '{"outstanding":0}', metadata: '{"payment":"RNP-000003"}',
    } as AppRecord),
  ]

  return {
    users,
    roles,
    auditLogs,
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
      } as AppRecord)),
    ],
    systemSettings: [
      stamp({ id: 'set-001', settingKey: 'default_currency', settingValue: 'USD', displayValue: 'USD', scope: 'System', sensitive: 'No', updatedBy: 'System Administrator', updatedAt: '2026-08-20T08:00:00' } as AppRecord),
      stamp({ id: 'set-002', settingKey: 'telegram_bot_token', settingValue: '••••••••', displayValue: '••••••••', scope: 'System', sensitive: 'Yes', updatedBy: 'System Administrator', updatedAt: '2026-08-18T10:00:00' } as AppRecord),
    ],
  }
}
