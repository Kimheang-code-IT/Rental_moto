import type { ApiMeta } from '~/types/rental/common'
import type { AppRecord } from '~/config/admin-seed'

/** Query translation of the workspace list controls into named API parameters. */
export interface EntityListQuery {
  q?: string
  page?: number
  limit?: number
  sort?: string
  status?: string
  startDate?: string
  endDate?: string
  customerId?: string
  motorcycleId?: string
  rentalId?: string
  paymentMethod?: string
  chargeType?: string
  expenseType?: string
}

export interface EntityListResult<T extends Record<string, unknown> = AppRecord> {
  items: T[]
  meta: ApiMeta | null
}

/** Typed CRUD contract shared by every `/api/v2` entity collection. */
export interface EntityRepository {
  list(collection: string, query?: EntityListQuery): Promise<EntityListResult>
  get(collection: string, id: string): Promise<AppRecord | null>
  create(collection: string, input: Record<string, unknown>): Promise<AppRecord>
  update(collection: string, id: string, input: Record<string, unknown>): Promise<AppRecord>
  remove(collection: string, id: string): Promise<void>
  setStatus?(collection: string, id: string, status: string): Promise<AppRecord>
}

export interface RentalLineInput {
  motorcycleId: string
  startDate: string
  dueDate: string
  deposit?: number
  discount?: number
  note?: string | null
}

export interface RentalCreateInput {
  customerId: string
  lines: RentalLineInput[]
  discount?: number
  taxPercent?: number
  paidAmount?: number
  paymentMethod?: string
  currency?: string
  note?: string | null
}

export interface RentalCloseChargeInput {
  chargeType: string
  description?: string | null
  amount: number
  chargeToCustomer?: string
}

export interface RentalCloseInput {
  returnDate: string
  condition?: string | null
  returnNote?: string | null
  lateFee?: number
  charges?: RentalCloseChargeInput[]
  finalPayment?: {
    amount: number
    paymentMethod: string
    reference?: string | null
    note?: string | null
    paidAt?: string
  } | null
  motorcycleStatus?: 'Available' | 'Maintenance' | null
}

export interface RentalUpdateInput {
  customerId?: string
  motorcycleId?: string
  startDate?: string
  dueDate?: string
  deposit?: number
  discount?: number
  taxPercent?: number
  note?: string | null
}

export interface RentalCommandRepository {
  create(input: RentalCreateInput): Promise<AppRecord[]>
  update(id: string, input: RentalUpdateInput): Promise<AppRecord>
  close(id: string, input: RentalCloseInput): Promise<AppRecord>
  cancel(id: string, reason?: string | null): Promise<AppRecord>
}

export interface DashboardSummary {
  motorcycleStatus: Record<string, number>
  rentalsActive: number
  rentalsOverdue: number
  rentalsCompleted: number
  income: number
  expense: number
  netIncome: number
  outstanding: number
  rentalsByDay: Array<{ date: string, count: number }>
  incomeByDay: Array<{ date: string, amount: number }>
  expenseByDay: Array<{ date: string, amount: number }>
  startDate?: string | null
  endDate?: string | null
}

export interface FinanceSummary {
  income: number
  expense: number
  net: number
  outstanding: number
  startDate?: string | null
  endDate?: string | null
}

export interface FinanceRepository {
  dashboard(startDate?: string, endDate?: string, requestKey?: string): Promise<DashboardSummary>
  financeSummary(startDate?: string, endDate?: string): Promise<FinanceSummary>
}

export interface SearchHitItem {
  id: string
  type: string
  title: string
  subtitle?: string | null
  url: string
}

export interface SearchRepository {
  search(q: string, limit?: number): Promise<SearchHitItem[]>
}
