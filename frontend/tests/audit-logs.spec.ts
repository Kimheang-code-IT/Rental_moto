import { describe, expect, it } from 'vitest'
import type { ModuleConfig } from '../app/config/modules'
import { normalizeAuditLog, resolveAuditEntityPath } from '../app/utils/module/audit-logs'

const moduleStub = (partial: Partial<ModuleConfig>): ModuleConfig => ({
  path: '/rentals', title: 'Rentals', titleKm: '', singular: 'Rental', singularKm: '',
  description: '', descriptionKm: '', icon: '', group: 'rental', permission: 'rental.rentals.view',
  collection: 'rentals', titleField: 'rentalNo', columns: [], fields: [], canCreate: true,
  ...partial,
})

describe('audit log table logic', () => {
  it('normalizes legacy audit rows for the table', () => {
    expect(normalizeAuditLog({ id: 'log-1', action: 'Updated service order', module: 'Service Orders', recordNo: 'JOB-1', ipAddress: '192.168.1.1' })).toMatchObject({
      eventType: 'UPDATED_SERVICE_ORDER', entityType: 'Service Orders', entity: 'JOB-1', result: 'SUCCESS', ipDevice: '192.168.1.1',
    })
  })

  it('links an entity to an existing accessible record', () => {
    const path = resolveAuditEntityPath(
      { id: 'log-1', entityType: 'Rental', entity: 'RNT-001' },
      [moduleStub({})],
      collection => collection === 'rentals' ? [{ id: 'rent-1', rentalNo: 'RNT-001' }] : [],
      () => true,
    )
    expect(path).toBe('/rentals/rent-1')
  })

  it('does not create broken or unauthorized links', () => {
    const module = moduleStub({})
    expect(resolveAuditEntityPath({ id: 'log-1', entity: 'MISSING' }, [module], () => [], () => true)).toBe('')
    expect(resolveAuditEntityPath({ id: 'log-2', entity: 'JOB-1' }, [module], () => [{ id: 'job-1', jobNo: 'JOB-1' }], () => false)).toBe('')
  })
})
