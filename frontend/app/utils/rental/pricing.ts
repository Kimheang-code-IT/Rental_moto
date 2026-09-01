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

function asMoney(value: unknown) {
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? n : 0
}

function round2(value: number) {
  return Number(value.toFixed(2))
}

/** Resolve tier amounts with sensible fallbacks from dailyRate. */
export function resolveMotorcycleRates(moto: MotorcycleRates | null | undefined) {
  const daily = asMoney(moto?.dailyRate)
  const threeDay = asMoney(moto?.threeDayRate) || round2(daily * 3)
  const weekly = asMoney(moto?.weeklyRate) || round2(daily * 6.5)
  const monthly = asMoney(moto?.monthlyRate) || round2(daily * 22)
  return { daily, threeDay, weekly, monthly }
}

/**
 * Charge for a duration in days using rate tiers when days match 1 / 3 / 7 / ~30,
 * otherwise dailyRate × days.
 */
export function lineCharge(moto: MotorcycleRates | null | undefined, days: number): number {
  const d = Math.max(0, Math.floor(Number(days) || 0))
  if (d <= 0) return 0
  const rates = resolveMotorcycleRates(moto)
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
): RentalLineAmounts {
  const charge = lineCharge(moto, days)
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
  if (!start) return ''
  const base = new Date(start)
  if (!Number.isFinite(base.getTime())) return ''
  const d = Math.max(0, Math.floor(Number(days) || 0))
  base.setDate(base.getDate() + d)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${base.getFullYear()}-${pad(base.getMonth() + 1)}-${pad(base.getDate())}T${pad(base.getHours())}:${pad(base.getMinutes())}`
}

export function todayDateTimeLocal(date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
