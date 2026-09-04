/** Motorcycle rate-tier pricing for rental create / return totals. */

export interface MotorcycleRates {
  dailyRate?: unknown
  threeDayRate?: unknown
  weeklyRate?: unknown
  monthlyRate?: unknown
  [key: string]: unknown
}

export interface RentalLineAmounts {
  charge: number
  discount: number
  lineTotal: number
}

export interface DocumentTotals {
  subtotal: number
  discount: number
  taxPercent: number
  tax: number
  total: number
}

export type RentalRatePlan = '1d' | '3d' | '1w' | '1m' | 'custom'
export type RentalRateType = 'Daily' | 'ThreeDay' | 'Weekly' | 'Monthly'

function asMoney(value: unknown) {
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? n : 0
}

function round2(value: number) {
  return Number(value.toFixed(2))
}

function pad2(n: number) {
  return String(n).padStart(2, '0')
}

function parseDateTime(value: string) {
  if (!value) return null
  const date = new Date(value)
  return Number.isFinite(date.getTime()) ? date : null
}

export function formatDateTimeLocal(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}T${pad2(date.getHours())}:${pad2(date.getMinutes())}`
}

function dateTimeMinuteKey(value: string) {
  const date = parseDateTime(value)
  return date ? formatDateTimeLocal(date) : ''
}

/** Resolve tier amounts with sensible fallbacks from dailyRate. */
export function resolveMotorcycleRates(moto: MotorcycleRates | null | undefined) {
  const daily = asMoney(moto?.dailyRate)
  const threeDay = asMoney(moto?.threeDayRate) || round2(daily * 3)
  const weekly = asMoney(moto?.weeklyRate) || round2(daily * 6.5)
  const monthly = asMoney(moto?.monthlyRate) || round2(daily * 22)
  return { daily, threeDay, weekly, monthly }
}

/** Add calendar months, clamping to the last day of the target month (Jan 31 → Feb 28/29). */
export function addMonthsToDateTime(start: string, months: number): string {
  const base = parseDateTime(start)
  if (!base) return ''
  const m = Math.max(0, Math.floor(Number(months) || 0))
  const day = base.getDate()
  const result = new Date(base)
  result.setDate(1)
  result.setMonth(result.getMonth() + m)
  const lastDay = new Date(result.getFullYear(), result.getMonth() + 1, 0).getDate()
  result.setDate(Math.min(day, lastDay))
  return formatDateTimeLocal(result)
}

/** Exact calendar-month count when due matches start plus n months at the same clock time. */
export function calendarMonthsBetween(start: string, due: string): number {
  const dueKey = dateTimeMinuteKey(due)
  if (!start || !dueKey) return 0
  for (let n = 1; n <= 36; n++) {
    if (dateTimeMinuteKey(addMonthsToDateTime(start, n)) === dueKey) return n
  }
  return 0
}

export function detectRatePlan(start: string, due: string, days = 0): RentalRatePlan {
  if (start && due && calendarMonthsBetween(start, due) === 1) return '1m'
  const d = days || (start && due ? daysBetween(start, due) : 0)
  if (d === 1) return '1d'
  if (d === 3) return '3d'
  if (d === 7) return '1w'
  return 'custom'
}

export function dueDateFromRatePlan(start: string, plan: RentalRatePlan, days = 1): string {
  if (!start) return ''
  if (plan === '1m') return addMonthsToDateTime(start, 1)
  if (plan === '1w') return addDaysToDateTime(start, 7)
  if (plan === '3d') return addDaysToDateTime(start, 3)
  if (plan === '1d') return addDaysToDateTime(start, 1)
  return addDaysToDateTime(start, Math.max(1, Math.floor(Number(days) || 1)))
}

export function rentalRateType(days: number, start = '', due = ''): RentalRateType {
  const months = start && due ? calendarMonthsBetween(start, due) : 0
  if (months >= 1) return 'Monthly'
  const d = Math.max(0, Math.floor(Number(days) || 0))
  if (d === 3) return 'ThreeDay'
  if (d === 7) return 'Weekly'
  if (d >= 28 && d <= 31) return 'Monthly'
  return 'Daily'
}

/**
 * Package rate shown in the unit-price field: daily / 3-day / weekly / monthly.
 * Custom durations use the daily rate except the 28–31 day monthly band.
 */
export function appliedUnitPrice(
  moto: MotorcycleRates | null | undefined,
  days: number,
  start = '',
  due = '',
): number {
  const rates = resolveMotorcycleRates(moto)
  const months = start && due ? calendarMonthsBetween(start, due) : 0
  if (months >= 1) return rates.monthly
  const d = Math.max(0, Math.floor(Number(days) || 0))
  if (d === 3) return rates.threeDay
  if (d === 7) return rates.weekly
  if (d >= 28 && d <= 31) return rates.monthly
  return rates.daily
}

/**
 * Charge for a duration using motorcycle packages:
 * 1 day, 3 days, 1 week, and calendar month(s) when start/due match.
 * 28–31 day spans still use monthly_rate when they are not an exact calendar month.
 * Other durations use dailyRate × days.
 */
export function lineCharge(
  moto: MotorcycleRates | null | undefined,
  days: number,
  start = '',
  due = '',
): number {
  const d = Math.max(0, Math.floor(Number(days) || 0))
  if (d <= 0) return 0
  const rates = resolveMotorcycleRates(moto)
  const months = start && due ? calendarMonthsBetween(start, due) : 0
  if (months >= 1) return round2(rates.monthly * months)
  if (d === 1) return rates.daily
  if (d === 3) return rates.threeDay
  if (d === 7) return rates.weekly
  if (d >= 28 && d <= 31) return rates.monthly
  return round2(rates.daily * d)
}

export function lineAmounts(
  moto: MotorcycleRates | null | undefined,
  days: number,
  discount: number = 0,
  start = '',
  due = '',
): RentalLineAmounts {
  const charge = lineCharge(moto, days, start, due)
  const disc = Math.min(Math.max(0, Number(discount) || 0), charge)
  return {
    charge,
    discount: round2(disc),
    lineTotal: round2(Math.max(charge - disc, 0)),
  }
}

/** Suggest deposit from motorcycle daily rate. */
export function suggestedDeposit(moto: MotorcycleRates | null | undefined) {
  const daily = resolveMotorcycleRates(moto).daily
  return Math.max(Math.round(daily * 10), 50)
}

export function documentTotals(input: {
  lineTotals: number[]
  discount?: number
  taxPercent?: number
}): DocumentTotals {
  const subtotal = round2(input.lineTotals.reduce((sum, n) => sum + (Number(n) || 0), 0))
  const discount = Math.min(Math.max(0, Number(input.discount) || 0), subtotal)
  const taxable = Math.max(subtotal - discount, 0)
  const taxPercent = Math.max(0, Number(input.taxPercent) || 0)
  const tax = round2(taxable * taxPercent / 100)
  return {
    subtotal,
    discount: round2(discount),
    taxPercent,
    tax,
    total: round2(taxable + tax),
  }
}

/** Allocate a payment amount across line totals by share (last line gets remainder). */
export function allocateRentalPayment(lineTotals: number[], paidAmount: number): number[] {
  const total = lineTotals.reduce((sum, n) => sum + n, 0)
  const paid = Math.max(0, Number(paidAmount) || 0)
  if (total <= 0 || paid <= 0 || !lineTotals.length) return lineTotals.map(() => 0)
  const capped = Math.min(paid, total)
  const shares = lineTotals.map((line, index) => {
    if (index === lineTotals.length - 1) return 0
    return round2(capped * (line / total))
  })
  const allocated = shares.reduce((sum, n) => sum + n, 0)
  shares[shares.length - 1] = round2(capped - allocated)
  return shares
}

/** Days between two datetime-local strings (ceil, min 1 when positive). */
export function daysBetween(start: string, due: string): number {
  if (!start || !due) return 0
  const ms = new Date(due).getTime() - new Date(start).getTime()
  if (!Number.isFinite(ms) || ms <= 0) return 0
  return Math.max(Math.ceil(ms / 86400000), 1)
}

/** Add days to a datetime-local string, preserving time portion. */
export function addDaysToDateTime(start: string, days: number): string {
  const base = parseDateTime(start)
  if (!base) return ''
  const d = Math.max(0, Math.floor(Number(days) || 0))
  base.setDate(base.getDate() + d)
  return formatDateTimeLocal(base)
}

export function todayDateTimeLocal(date = new Date()): string {
  return formatDateTimeLocal(date)
}
