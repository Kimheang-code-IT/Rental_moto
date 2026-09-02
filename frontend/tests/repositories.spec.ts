import { afterEach, describe, expect, it, vi } from 'vitest'
import { CollectionEndpoints, isApiCollection } from '../app/utils/constants/api-endpoints'
import { createHttpEntityRepository, createHttpRentalCommandRepository } from '../app/repositories/http/entities'

interface CapturedRequest {
  method: string
  url: string
  query?: Record<string, unknown>
  body?: unknown
}

function withFakeApi(handler: (request: CapturedRequest) => unknown) {
  const captured: CapturedRequest[] = []
  const fakeApi = () => ({
    get: async (url: string, options?: { query?: Record<string, unknown> }) => {
      captured.push({ method: 'GET', url, query: options?.query })
      return handler(captured[captured.length - 1]!)
    },
    post: async (url: string, body?: unknown) => {
      captured.push({ method: 'POST', url, body })
      return handler(captured[captured.length - 1]!)
    },
    put: async (url: string, body?: unknown) => {
      captured.push({ method: 'PUT', url, body })
      return handler(captured[captured.length - 1]!)
    },
    patch: async (url: string, body?: unknown) => {
      captured.push({ method: 'PATCH', url, body })
      return handler(captured[captured.length - 1]!)
    },
    delete: async (url: string) => {
      captured.push({ method: 'DELETE', url })
      return handler(captured[captured.length - 1]!)
    },
  })
  vi.stubGlobal('useApi', fakeApi)
  return captured
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('collection → endpoint mapping', () => {
  it('maps every frontend collection to its /api/v2 resource', () => {
    expect(CollectionEndpoints.motorcycles).toBe('/api/v2/motorcycles')
    expect(CollectionEndpoints.rentalCustomers).toBe('/api/v2/customers')
    expect(CollectionEndpoints.rentals).toBe('/api/v2/rentals')
    expect(CollectionEndpoints.rentalReports).toBe('/api/v2/rentals/reports')
    expect(CollectionEndpoints.rentalPayments).toBe('/api/v2/payments')
    expect(CollectionEndpoints.rentalCharges).toBe('/api/v2/charges')
    expect(CollectionEndpoints.rentalExpenses).toBe('/api/v2/expenses')
    expect(CollectionEndpoints.users).toBe('/api/v2/users')
    expect(CollectionEndpoints.roles).toBe('/api/v2/roles')
    expect(CollectionEndpoints.documentSequences).toBe('/api/v2/document-sequences')
    expect(CollectionEndpoints.auditLogs).toBe('/api/v2/audit-logs')
  })

  it('rejects unknown collections', () => {
    expect(isApiCollection('motorcycles')).toBe(true)
    expect(isApiCollection('unknownCollection')).toBe(false)
  })
})

describe('http entity repository', () => {
  it('translates list queries into named parameters and keeps pagination meta', async () => {
    const captured = withFakeApi(() => ({
      data: [{ id: 'mc-001', code: 'MC-001' }],
      meta: { page: 2, limit: 50, total: 123, totalPages: 3 },
    }))
    const repository = createHttpEntityRepository()
    const result = await repository.list('motorcycles', {
      q: 'honda',
      status: 'Available',
      startDate: '2026-01-01',
      endDate: '2026-02-01',
      page: 2,
      limit: 50,
    })

    expect(captured[0]?.url).toBe('/api/v2/motorcycles')
    expect(captured[0]?.query).toMatchObject({
      q: 'honda',
      status: 'Available',
      startDate: '2026-01-01',
      endDate: '2026-02-01',
      page: 2,
      limit: 50,
    })
    expect(result.items).toHaveLength(1)
    expect(result.items[0]?.id).toBe('mc-001')
    expect(result.meta?.total).toBe(123)
    expect(result.meta?.page).toBe(2)
  })

  it('unwraps single-record envelopes on create', async () => {
    withFakeApi(() => ({ data: { id: 'rc-099', code: 'CUS-099' }, meta: { page: 1, limit: 1, total: 1 } }))
    const repository = createHttpEntityRepository()
    const created = await repository.create('rentalCustomers', { code: 'CUS-099', fullName: 'New Customer' })
    expect(created.id).toBe('rc-099')
  })

    it('adapts backend user fields for the UI without fabricating data', async () => {
    withFakeApi(() => ({
      data: [{ id: 1, email: 'a@b.com', roleId: 1, lastLoginAt: '2026-09-01T09:00:00Z', telegramLinked: true, telegramChatId: '900001' }],
      meta: { page: 1, limit: 100, total: 1 },
    }))
    const repository = createHttpEntityRepository()
    const result = await repository.list('users')
    const user = result.items[0] as Record<string, unknown>
    expect(user.id).toBe('1')
    expect(user.roleId).toBe('1')
    expect(user.lastLogin).toBe('2026-09-01T09:00:00Z')
    expect(user.telegramUsername).toBe('900001')
  })

  it('sends only backend-accepted user fields and a numeric roleId', async () => {
    const captured = withFakeApi(() => ({
      data: { id: 9, username: 'tester', displayName: 'API Tester', roleId: 2 },
    }))
    const repository = createHttpEntityRepository()
    await repository.create('users', {
      id: '',
      username: 'tester',
      displayName: 'API Tester',
      email: 'tester@example.com',
      password: 'secret123',
      roleId: '2',
      role: 'Rental Staff',
      status: 'Active',
      createdAt: '2026-09-02T00:00:00Z',
      createdBy: 'Admin',
      currency: 'USD',
      permissionRows: [],
      effectivePermissions: ['ALL_PAGES'],
      telegramUsername: '',
      telegramChatId: '',
    })

    const body = captured[0]?.body as Record<string, unknown>
    expect(body).toEqual({
      username: 'tester',
      displayName: 'API Tester',
      email: 'tester@example.com',
      password: 'secret123',
      roleId: 2,
      status: 'Active',
    })
  })

  it('omits an empty password and extra user fields on update', async () => {
    const captured = withFakeApi(() => ({
      data: { id: 9, username: 'tester', displayName: 'API Tester', roleId: 3 },
    }))
    const repository = createHttpEntityRepository()
    await repository.update('users', '9', {
      id: 9,
      username: 'tester',
      displayName: 'API Tester',
      email: 'tester@example.com',
      password: '',
      roleId: 3,
      lastLoginAt: '2026-09-01T09:00:00Z',
      createdAt: '2026-09-01T08:00:00Z',
      updatedAt: '2026-09-01T09:00:00Z',
      permissions: ['ALL_PAGES'],
      status: 'Inactive',
    })

    const body = captured[0]?.body as Record<string, unknown>
    expect(body).toEqual({
      username: 'tester',
      displayName: 'API Tester',
      email: 'tester@example.com',
      roleId: 3,
      status: 'Inactive',
    })
    expect(body.password).toBeUndefined()
  })

  it('adapts UI permission-matrix rows to flat backend permission keys on write', async () => {
    const captured = withFakeApi(() => ({ data: { id: 5, name: 'Staff', permissions: [] } }))
    const repository = createHttpEntityRepository()
    await repository.update('roles', '5', {
      name: 'Staff',
      description: 'Rental staff',
      status: 'Active',
      permissionRows: [
        { id: 'perm_dashboard', documentType: 'dashboard', onlyIfCreator: false, actions: ['view'] },
        { id: 'perm_rental_motorcycles', documentType: 'rental_motorcycles', onlyIfCreator: false, actions: ['view', 'create'] },
      ],
      userCount: 3,
      permissionCount: 3,
    })

    const body = captured[0]?.body as Record<string, unknown>
    expect(body.permissions).toEqual([
      'dashboard.view',
      'rental.motorcycles.create',
      'rental.motorcycles.view',
    ])
    expect(body.status).toBeUndefined()
    expect(body.userCount).toBeUndefined()
    expect(body.permissionRows).toBeUndefined()
    expect(body.name).toBe('Staff')
  })

  it('computes next-number previews for document sequences without submitting them', async () => {
    const captured = withFakeApi(() => ({
      data: [{ id: 'ds-rental', documentType: 'RENTAL', prefix: 'RNT', year: 2026, lastValue: 5, paddingLength: 6, status: 'ACTIVE' }],
      meta: { page: 1, limit: 100, total: 1 },
    }))
    const repository = createHttpEntityRepository()
    const result = await repository.list('documentSequences')
    expect(result.items[0]?.nextNumberPreview).toBe('RNT-2026-000006')

    await repository.update('documentSequences', 'ds-rental', {
      lastValue: 10,
      nextNumberPreview: 'RNT-2026-000011',
      resetRule: 'Yearly',
    })
    const body = captured[1]?.body as Record<string, unknown>
    expect(body.lastValue).toBe(10)
    expect(body.nextNumberPreview).toBeUndefined()
    expect(body.resetRule).toBeUndefined()
  })
})

describe('http rental command payloads', () => {
  it('sends one atomic POST /rentals with lines and returns the created rentals', async () => {
    const captured = withFakeApi(() => ({
      data: [
        { id: 'rt-001', rentalNo: 'RNT-2026-000001', status: 'Active' },
        { id: 'rt-002', rentalNo: 'RNT-2026-000002', status: 'Active' },
      ],
      meta: { page: 1, limit: 2, total: 2 },
    }))
    const repository = createHttpRentalCommandRepository()
    const created = await repository.create({
      customerId: 'rc-001',
      lines: [
        { motorcycleId: 'mc-001', startDate: '2026-09-01T08:00:00+07:00', dueDate: '2026-09-04T08:00:00+07:00', deposit: 100 },
        { motorcycleId: 'mc-002', startDate: '2026-09-01T08:00:00+07:00', dueDate: '2026-09-04T08:00:00+07:00' },
      ],
      discount: 10,
      taxPercent: 0,
      paidAmount: 20,
      paymentMethod: 'Cash',
      currency: 'USD',
    })

    expect(captured).toHaveLength(1)
    expect(captured[0]?.method).toBe('POST')
    expect(captured[0]?.url).toBe('/api/v2/rentals')
    const body = captured[0]?.body as Record<string, unknown>
    expect(body.customerId).toBe('rc-001')
    expect(Array.isArray(body.lines)).toBe(true)
    expect((body.lines as unknown[]).length).toBe(2)
    expect((body.paidAmount)).toBe(20)
    expect(created).toHaveLength(2)
    expect(created[0]?.rentalNo).toBe('RNT-2026-000001')
  })

  it('sends one atomic close request with charges and final payment', async () => {
    const captured = withFakeApi(() => ({
      data: { id: 'rt-001', status: 'Completed', outstanding: '0.00' },
      meta: { page: 1, limit: 1, total: 1 },
    }))
    const repository = createHttpRentalCommandRepository()
    const closed = await repository.close('rt-001', {
      returnDate: '2026-09-04T10:30:00+07:00',
      condition: null,
      returnNote: null,
      lateFee: 5,
      charges: [
        { chargeType: 'Cleaning', description: 'wash', amount: 5, chargeToCustomer: 'Yes' },
      ],
      finalPayment: {
        amount: 20,
        paymentMethod: 'Cash',
        reference: null,
        note: 'Payment on return',
        paidAt: '2026-09-04T10:30:00+07:00',
      },
      motorcycleStatus: 'Available',
    })

    expect(captured[0]?.method).toBe('POST')
    expect(captured[0]?.url).toBe('/api/v2/rentals/rt-001/close')
    const body = captured[0]?.body as Record<string, unknown>
    expect(body.returnDate).toBe('2026-09-04T10:30:00+07:00')
    expect((body.charges as unknown[]).length).toBe(1)
    expect((body.finalPayment as Record<string, unknown>).amount).toBe(20)
    expect(body.motorcycleStatus).toBe('Available')
    expect(closed.status).toBe('Completed')
  })

  it('sends cancellation with a reason', async () => {
    const captured = withFakeApi(() => ({ data: { id: 'rt-001', status: 'Cancelled' }, meta: null }))
    const repository = createHttpRentalCommandRepository()
    await repository.cancel('rt-001', 'Customer changed mind')
    expect(captured[0]?.url).toBe('/api/v2/rentals/rt-001/cancel')
    expect(captured[0]?.body).toEqual({ reason: 'Customer changed mind' })
  })
})
