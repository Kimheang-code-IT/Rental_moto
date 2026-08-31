/**
 * Shared record type + administration base seed.
 * Rental demo data lives in `./rental-seed.ts`.
 */

export type AppRecord = Record<string, unknown> & { id: string }

function id(prefix: string, n: number) {
  return `${prefix}-${String(n).padStart(3, '0')}`
}

/** Administration-only base collections consumed by `createLcsSeed`. */
export function createAdminSeed(): Record<string, AppRecord[]> {
  const users: AppRecord[] = [
    { id: id('us', 1), name: 'System Administrator', username: 'admin.lcs', email: 'admin@lcs.com.kh', phone: '+855 12 000 001', role: 'Administrator', department: 'Management', status: 'Active' },
    { id: id('us', 2), name: 'Sokha Vann', username: 'sokha.ops', email: 'sokha@lcs.com.kh', phone: '+855 12 000 002', role: 'Operations', department: 'Operations', status: 'Active' },
    { id: id('us', 3), name: 'Dara Chan', username: 'dara.finance', email: 'dara@lcs.com.kh', phone: '+855 12 000 003', role: 'Finance', department: 'Finance', status: 'Active' },
    { id: id('us', 4), name: 'Lina Kim', username: 'lina.customs', email: 'lina@lcs.com.kh', phone: '+855 12 000 004', role: 'Customs', department: 'Customs', status: 'Active' },
  ]

  const roles: AppRecord[] = [
    { id: id('rl', 1), name: 'Administrator', description: 'Full system access', userCount: 1, permissionCount: 0, status: 'Active' },
    { id: id('rl', 2), name: 'Operations', description: 'Rentals, motorcycles and customers', userCount: 4, permissionCount: 0, status: 'Active' },
    { id: id('rl', 3), name: 'Finance', description: 'Income, expense and outstanding balances', userCount: 2, permissionCount: 0, status: 'Active' },
    { id: id('rl', 4), name: 'Customs', description: 'Custom role', userCount: 2, permissionCount: 0, status: 'Active' },
  ]

  const auditLogs: AppRecord[] = [
    { id: id('log', 1), occurredAt: '2026-08-20 16:20', user: 'Sokha V.', action: 'Created rental', module: 'Rentals', recordNo: 'RNT-2026-000001', result: 'SUCCESS', remark: '' },
    { id: id('log', 2), occurredAt: '2026-08-20 11:40', user: 'Dara C.', action: 'Payment recorded', module: 'Rentals', recordNo: 'RNT-2026-000002', result: 'SUCCESS', remark: '' },
    { id: id('log', 3), occurredAt: '2026-08-19 09:00', user: 'Dara C.', action: 'Registered motorcycle', module: 'Motorcycles', recordNo: 'MC-009', result: 'SUCCESS', remark: '' },
    { id: id('log', 5), occurredAt: '2026-08-20 08:00', user: 'Sokha V.', action: 'Created customer', module: 'Customers', recordNo: 'CUS-001', result: 'SUCCESS', remark: '' },
    { id: id('log', 6), occurredAt: '2026-08-20 10:12', user: 'Sokha V.', action: 'Updated motorcycle', module: 'Motorcycles', recordNo: 'MC-011', result: 'SUCCESS', remark: 'Marked for maintenance' },
    { id: id('log', 7), occurredAt: '2026-08-20 14:40', user: 'Sokha V.', action: 'Closed rental', module: 'Rentals', recordNo: 'RNT-2026-000011', result: 'SUCCESS', remark: '' },
    { id: id('log', 8), occurredAt: '2026-08-19 08:10', user: 'Dara C.', action: 'Expense recorded', module: 'Income & Expense', recordNo: 'RNX-000005', result: 'SUCCESS', remark: '' },
  ]

  return {
    users,
    roles,
    auditLogs,
  }
}
