import type { AppRecord } from '~/config/admin-seed'
import type {
  DashboardSummary,
  EntityListQuery,
  EntityListResult,
  EntityRepository,
  FinanceRepository,
  FinanceSummary,
  RentalCloseInput,
  RentalCommandRepository,
  RentalCreateInput,
  SearchRepository,
  SearchHitItem,
} from '~/repositories/contracts/entities'
import { getRentalDb, setRentalDb } from '~/repositories/mock/db'
import { documentSequencePreview } from '~/utils/document-sequences'
import { resolveMotorcycleRates, lineCharge, daysBetween } from '~/utils/rental/pricing'

function collectionRows(collection: string): AppRecord[] {
  return getRentalDb()[collection] || []
}

function writeRows(collection: string, rows: AppRecord[]) {
  const db = getRentalDb()
  db[collection] = rows
  setRentalDb(db)
}

function newId(prefix: string) {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`
}

function stripUiOnlyFields(input: Record<string, unknown>): Record<string, unknown> {
  const output: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(input)) {
    if (!['nextNumberPreview', 'resetRule', 'userCount', 'permissionCount', 'permissionRows'].includes(key)) {
      output[key] = value
    }
  }
  return output
}

/** Mock-mode entity CRUD over the localStorage mock database. */
export function createMockEntityRepository(): EntityRepository {
  async function list(collection: string, query: EntityListQuery = {}): Promise<EntityListResult> {
    const q = String(query.q || '').trim().toLowerCase()
    let rows = [...collectionRows(collection)]

    if (collection === 'rentals') {
      rows = rows.filter(row => ['Active', 'Overdue'].includes(String(row.status)))
    }
    if (query.status) {
      const statuses = String(query.status).split(',').filter(Boolean)
      rows = rows.filter(row => statuses.includes(String(row.status || '')))
    }
    if (query.rentalId) {
      rows = rows.filter(row => String(row.rentalId || '') === query.rentalId)
    }
    if (query.customerId) {
      rows = rows.filter(row => String(row.customerId || '') === query.customerId)
    }
    if (query.motorcycleId) {
      rows = rows.filter(row => String(row.motorcycleId || '') === query.motorcycleId)
    }
    if (query.expenseType) {
      rows = rows.filter(row => String(row.expenseType || '') === query.expenseType)
    }
    if (q) {
      rows = rows.filter(row => Object.values(row).some(value => String(value ?? '').toLowerCase().includes(q)))
    }

    let adapted = rows.map(row => ({ ...row }))
    if (collection === 'users') {
      adapted = adapted.map(row => ({ ...row, lastLogin: row.lastLogin ?? row.lastLoginAt ?? null }))
    }
    if (collection === 'auditLogs') {
      adapted = adapted.map(row => ({
        ...row,
        user: row.userName ?? row.user ?? null,
        entity: row.entityLabel ?? row.entity ?? row.recordNo ?? '',
      }))
    }
    if (collection === 'documentSequences') {
      adapted = adapted.map(row => ({ ...row, nextNumberPreview: documentSequencePreview(row) }))
    }

    const page = Number(query.page || 1)
    const limit = Number(query.limit || 100)
    const total = adapted.length
    const start = (page - 1) * limit
    return {
      items: adapted.slice(start, start + limit),
      meta: { page, limit, total, totalPages: Math.max(1, Math.ceil(total / limit)) },
    }
  }

  async function get(collection: string, id: string): Promise<AppRecord | null> {
    return collectionRows(collection).find(row => String(row.id) === id) || null
  }

  async function create(collection: string, input: Record<string, unknown>): Promise<AppRecord> {
    const clean = stripUiOnlyFields(input)
    const { id: _ignored, ...rest } = clean
    const record = {
      ...rest,
      id: String(input.id || newId(collection.slice(0, 2))),
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    } as AppRecord
    const rows = collectionRows(collection)
    rows.unshift(record)
    writeRows(collection, rows)
    return record
  }

  async function update(collection: string, id: string, input: Record<string, unknown>): Promise<AppRecord> {
    const rows = collectionRows(collection)
    const index = rows.findIndex(row => String(row.id) === id)
    if (index < 0) throw new Error(`${collection} record ${id} not found`)
    const next = { ...rows[index], ...stripUiOnlyFields(input), id, updatedAt: new Date().toISOString() } as AppRecord
    rows[index] = next
    writeRows(collection, rows)
    return next
  }

  async function remove(collection: string, id: string): Promise<void> {
    writeRows(collection, collectionRows(collection).filter(row => String(row.id) !== id))
  }

  async function setStatus(collection: string, id: string, status: string): Promise<AppRecord> {
    return update(collection, id, { status })
  }

  return { list, get, create, update, remove, setStatus }
}

/** Mock rental commands mirror the backend transaction semantics locally. */
export function createMockRentalCommandRepository(): RentalCommandRepository {
  async function create(input: RentalCreateInput): Promise<AppRecord[]> {
    const customers = collectionRows('rentalCustomers')
    const customer = customers.find(row => String(row.id) === input.customerId)
    const motorcycles = collectionRows('motorcycles')
    const payments = collectionRows('rentalPayments')
    const rentals = collectionRows('rentals')
    const year = new Date().getFullYear()
    const maxNo = rentals.reduce((max, row) => {
      const match = String(row.rentalNo || '').match(/(\d+)$/)
      return Math.max(max, match ? Number(match[1]) : 0)
    }, 0)
    const totalLines = input.lines.length
    const lineDiscount = (Number(input.discount) || 0) / totalLines
    const paidShares = allocateMock(input.lines.length, Number(input.paidAmount) || 0)
    const created: AppRecord[] = []
    let seq = maxNo

    input.lines.forEach((line, index) => {
      const moto = motorcycles.find(row => String(row.id) === line.motorcycleId)
      if (!moto) throw new Error(`Motorcycle ${line.motorcycleId} not found`)
      seq += 1
      const days = Math.max(1, daysBetween(line.startDate, line.dueDate))
      const rates = resolveMotorcycleRates(moto)
      const charge = lineCharge(rates, days)
      const rentalCharge = Math.max(charge - lineDiscount, 0)
      const totalDue = Number(rentalCharge.toFixed(2))
      const paid = Number(paidShares[index] || 0)
      const record = {
        id: `rt-${String(rentals.length + created.length + 1).padStart(3, '0')}`,
        rentalNo: `RNT-${year}-${String(seq).padStart(6, '0')}`,
        customerId: String(customer?.id || input.customerId),
        customer: String(customer?.fullName || ''),
        phone: String(customer?.phone || ''),
        motorcycleId: String(moto.id),
        motorcycle: String(moto.model || ''),
        plate: String(moto.plate || ''),
        startDate: line.startDate,
        dueDate: line.dueDate,
        durationDays: days,
        rateType: 'Daily',
        rateAmount: Number(rates.daily.toFixed(2)),
        deposit: Number(line.deposit || 0),
        discount: Number(lineDiscount.toFixed(2)),
        taxPercent: Number(input.taxPercent || 0),
        tax: 0,
        currency: String(input.currency || moto.currency || 'USD'),
        rentalCharge,
        lateFee: 0,
        additionalCharges: 0,
        totalDue,
        paid,
        outstanding: Math.max(totalDue - paid, 0),
        paymentMethod: paid > 0 ? String(input.paymentMethod || 'Cash') : '',
        note: line.note || '',
        createdByUserId: 1,
        status: 'Active',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      } as unknown as AppRecord
      created.push(record)
      moto.status = 'Progressing'

      if (paid > 0) {
        const paymentNo = `RNP-${String(payments.length + 1).padStart(6, '0')}`
        payments.push({
          id: `rnp-${payments.length + 1}`,
          paymentNo,
          rentalId: String(record.id),
          rentalNo: String(record.rentalNo),
          customer: String(record.customer),
          amount: paid,
          currency: String(record.currency),
          paymentMethod: String(input.paymentMethod || 'Cash'),
          paidAt: line.startDate,
          reference: '',
          note: 'Payment on register',
          createdByUserId: 1,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        } as unknown as AppRecord)
      }
    })

    writeRows('rentals', [...created, ...rentals])
    writeRows('motorcycles', motorcycles)
    writeRows('rentalPayments', payments)
    return created
  }

  function allocateMock(count: number, paid: number): number[] {
    if (paid <= 0 || count <= 0) return Array.from({ length: count }, () => 0)
    const share = Math.round((paid / count) * 100) / 100
    const shares = Array.from({ length: count }, () => share)
    const allocated = share * count
    shares[count - 1] = Math.round((paid - (allocated - share)) * 100) / 100
    return shares
  }

  async function close(id: string, input: RentalCloseInput): Promise<AppRecord> {
    const rentals = collectionRows('rentals')
    const rental = rentals.find(row => String(row.id) === id)
    if (!rental) throw new Error(`Rental ${id} not found`)
    if (String(rental.status) === 'Completed') throw new Error('Rental is already completed')

    const charges = collectionRows('rentalCharges')
    const payments = collectionRows('rentalPayments')
    const motorcycles = collectionRows('motorcycles')
    for (const chargeInput of input.charges || []) {
      const amount = Math.max(0, Number(chargeInput.amount) || 0)
      if (amount <= 0) continue
      charges.push({
        id: `rgc-${charges.length + 1}`,
        chargeNo: `RNC-${String(charges.length + 1).padStart(6, '0')}`,
        rentalId: id,
        rentalNo: String(rental.rentalNo || ''),
        customer: String(rental.customer || ''),
        chargeType: chargeInput.chargeType,
        description: chargeInput.description || '',
        amount,
        currency: String(rental.currency || 'USD'),
        chargeToCustomer: chargeInput.chargeToCustomer || 'Yes',
        createdByUserId: 1,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      } as unknown as AppRecord)
    }

    if (input.finalPayment && Number(input.finalPayment.amount) > 0) {
      const finalPayment = Number(input.finalPayment.amount)
      payments.push({
        id: `rnp-${payments.length + 1}`,
        paymentNo: `RNP-${String(payments.length + 1).padStart(6, '0')}`,
        rentalId: id,
        rentalNo: String(rental.rentalNo || ''),
        customer: String(rental.customer || ''),
        amount: finalPayment,
        currency: String(rental.currency || 'USD'),
        paymentMethod: input.finalPayment.paymentMethod || 'Cash',
        paidAt: input.finalPayment.paidAt || input.returnDate,
        reference: input.finalPayment.reference || '',
        note: input.finalPayment.note || '',
        createdByUserId: 1,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      } as unknown as AppRecord)
    }

    const paidTotal = payments
      .filter(row => String(row.rentalId) === id)
      .reduce((sum, row) => sum + Number(row.amount || 0), 0)
    const additionalCharges = charges
      .filter(row => String(row.rentalId) === id && String(row.chargeToCustomer) === 'Yes')
      .reduce((sum, row) => sum + Number(row.amount || 0), 0)
    const totalDue = Number(rental.rentalCharge || 0) + Number(rental.tax || 0) + Number(rental.lateFee || 0) + additionalCharges

    rental.paid = Math.round(paidTotal * 100) / 100
    rental.additionalCharges = additionalCharges
    rental.totalDue = totalDue
    rental.outstanding = Math.max(totalDue - Number(rental.paid || 0), 0)
    rental.status = 'Completed'
    rental.returnDate = input.returnDate
    rental.condition = input.condition || null
    rental.returnNote = input.returnNote || null
    rental.paymentStatus = Number(rental.outstanding) <= 0 ? 'Paid' : 'Partial'
    rental.updatedAt = new Date().toISOString()

    const moto = motorcycles.find(row => String(row.id) === String(rental.motorcycleId || ''))
    if (moto) moto.status = input.motorcycleStatus || 'Available'

    writeRows('rentals', rentals)
    writeRows('rentalCharges', charges)
    writeRows('rentalPayments', payments)
    writeRows('motorcycles', motorcycles)
    return rental
  }

  async function cancel(id: string, reason?: string | null): Promise<AppRecord> {
    const rentals = collectionRows('rentals')
    const rental = rentals.find(row => String(row.id) === id)
    if (!rental) throw new Error(`Rental ${id} not found`)
    rental.status = 'Cancelled'
    rental.cancelledAt = new Date().toISOString()
    rental.cancelReason = reason || null
    rental.outstanding = 0
    const motorcycles = collectionRows('motorcycles')
    const moto = motorcycles.find(row => String(row.id) === String(rental.motorcycleId || ''))
    if (moto) moto.status = 'Available'
    writeRows('rentals', rentals)
    writeRows('motorcycles', motorcycles)
    return rental
  }

  return { create, close, cancel }
}

export function createMockFinanceRepository(): FinanceRepository {
  return {
    async dashboard(): Promise<DashboardSummary> {
      const motorcycles = collectionRows('motorcycles')
      const rentals = collectionRows('rentals')
      const payments = collectionRows('rentalPayments')
      const expenses = collectionRows('rentalExpenses')
      const byStatus = (rows: AppRecord[], key: string) => rows.reduce<Record<string, number>>((acc, row) => {
        const status = String(row[key] || 'Unknown')
        acc[status] = (acc[status] || 0) + 1
        return acc
      }, {})

      const income = payments.reduce((sum, row) => sum + Number(row.amount || 0), 0)
      const expense = expenses.reduce((sum, row) => sum + Number(row.amount || 0), 0)
      const outstanding = rentals
        .filter(row => ['Active', 'Overdue', 'Completed'].includes(String(row.status)))
        .reduce((sum, row) => sum + Number(row.outstanding || 0), 0)

      return {
        motorcycleStatus: byStatus(motorcycles, 'status'),
        rentalsActive: rentals.filter(row => String(row.status) === 'Active').length,
        rentalsOverdue: rentals.filter(row => String(row.status) === 'Overdue').length,
        rentalsCompleted: rentals.filter(row => String(row.status) === 'Completed').length,
        income,
        expense,
        netIncome: income - expense,
        outstanding,
        rentalsByDay: [],
      }
    },
    async financeSummary(): Promise<FinanceSummary> {
      const payments = collectionRows('rentalPayments')
      const expenses = collectionRows('rentalExpenses')
      const rentals = collectionRows('rentals')
      const income = payments.reduce((sum, row) => sum + Number(row.amount || 0), 0)
      const expense = expenses.reduce((sum, row) => sum + Number(row.amount || 0), 0)
      const outstanding = rentals
        .filter(row => ['Active', 'Overdue', 'Completed'].includes(String(row.status)))
        .reduce((sum, row) => sum + Number(row.outstanding || 0), 0)
      return {
        income,
        expense,
        net: income - expense,
        outstanding,
      }
    },
  }
}

export function createMockSearchRepository(): SearchRepository {
  return {
    async search(q: string, limit = 12): Promise<SearchHitItem[]> {
      const term = q.trim().toLowerCase()
      if (!term) return []
      const hits: SearchHitItem[] = []
      const addRows = (type: string, collection: string, titleKey: string, subtitleKey: string, urlPrefix: string) => {
        for (const row of collectionRows(collection)) {
          const title = String(row[titleKey] || '')
          const subtitle = String(row[subtitleKey] || '')
          if (title.toLowerCase().includes(term) || subtitle.toLowerCase().includes(term)) {
            hits.push({ id: String(row.id), type, title, subtitle, url: `${urlPrefix}/${String(row.id)}` })
          }
        }
      }
      addRows('motorcycle', 'motorcycles', 'model', 'code', '/motorcycles')
      addRows('customer', 'rentalCustomers', 'fullName', 'code', '/customers')
      addRows('rental', 'rentals', 'rentalNo', 'customer', '/rentals')
      return hits.slice(0, limit)
    },
  }
}
