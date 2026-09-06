import { describe, expect, it } from 'vitest'
import {
  addMonthsToDateTime,
  appliedUnitPrice,
  applySharedDurationToLines,
  calendarMonthsBetween,
  detectRatePlan,
  dueDateFromRatePlan,
  latestLineDueDate,
  lineCharge,
  lineAmounts,
  rentalRateType,
  rentalReturnBalance,
} from '../app/utils/rental/pricing'

const moto = {
  dailyRate: 10,
  threeDayRate: 27,
  weeklyRate: 60,
  monthlyRate: 200,
}

describe('rental package pricing', () => {
  it('uses motorcycle package rates for 1 day, 3 days, and 1 week', () => {
    expect(lineCharge(moto, 1)).toBe(10)
    expect(lineCharge(moto, 3)).toBe(27)
    expect(lineCharge(moto, 7)).toBe(60)
    expect(lineCharge(moto, 2)).toBe(20)
    expect(lineCharge(moto, 10)).toBe(100)
  })

  it('adds a calendar month and charges the monthly rate', () => {
    const start = '2026-01-15T09:00'
    const due = addMonthsToDateTime(start, 1)
    expect(due).toBe('2026-02-15T09:00')
    expect(detectRatePlan(start, due)).toBe('1m')
    expect(lineCharge(moto, 31, start, due)).toBe(200)
    expect(appliedUnitPrice(moto, 31, start, due)).toBe(200)
    expect(rentalRateType(31, start, due)).toBe('Monthly')
  })

  it('clamps January 31 to the last day of February', () => {
    expect(addMonthsToDateTime('2026-01-31T10:00', 1)).toBe('2026-02-28T10:00')
    expect(addMonthsToDateTime('2028-01-31T10:00', 1)).toBe('2028-02-29T10:00')
    expect(calendarMonthsBetween('2026-01-31T10:00', '2026-02-28T10:00')).toBe(1)
    expect(lineCharge(moto, 28, '2026-01-31T10:00', '2026-02-28T10:00')).toBe(200)
  })

  it('charges two monthly packages for exactly two calendar months', () => {
    const start = '2026-01-15T09:00'
    const due = addMonthsToDateTime(start, 2)
    expect(due).toBe('2026-03-15T09:00')
    expect(calendarMonthsBetween(start, due)).toBe(2)
    expect(lineCharge(moto, 59, start, due)).toBe(400)
  })

  it('maps rate plan presets to due dates', () => {
    const start = '2026-09-04T08:00'
    expect(dueDateFromRatePlan(start, '1d')).toBe('2026-09-05T08:00')
    expect(dueDateFromRatePlan(start, '3d')).toBe('2026-09-07T08:00')
    expect(dueDateFromRatePlan(start, '1w')).toBe('2026-09-11T08:00')
    expect(dueDateFromRatePlan(start, '1m')).toBe('2026-10-04T08:00')
    expect(detectRatePlan(start, dueDateFromRatePlan(start, '3d'))).toBe('3d')
    expect(rentalRateType(3, start, dueDateFromRatePlan(start, '3d'))).toBe('ThreeDay')
    expect(rentalRateType(7, start, dueDateFromRatePlan(start, '1w'))).toBe('Weekly')
  })

  it('detects custom spans and applies per-line discounts', () => {
    const start = '2026-09-04T08:00'
    const due = '2026-09-09T08:00'
    expect(detectRatePlan(start, due)).toBe('custom')
    expect(lineAmounts(moto, 5, 7, start, due)).toEqual({
      charge: 50,
      discount: 7,
      lineTotal: 43,
    })
  })
})

describe('rentalReturnBalance', () => {
  const rental = {
    rentalCharge: 30,
    lateFee: 0,
    additionalCharges: 0,
    discount: 0,
    totalDue: 30,
    paid: 16.22,
    outstanding: 13.78,
  }

  it('keeps already paid separate from the return payment amount', () => {
    const beforePay = rentalReturnBalance(rental)
    expect(beforePay.totalDue).toBe(30)
    expect(beforePay.alreadyPaid).toBe(16.22)
    expect(beforePay.balanceDue).toBe(13.78)
    expect(beforePay.suggestedPayment).toBe(13.78)

    const afterSuggestedPay = rentalReturnBalance(rental, 0, beforePay.suggestedPayment)
    expect(afterSuggestedPay.alreadyPaid).toBe(16.22)
    expect(afterSuggestedPay.outstandingAfterPay).toBe(0)
  })

  it('adds return charges onto total due and the remaining payment', () => {
    const result = rentalReturnBalance(rental, 5, 0)
    expect(result.totalDue).toBe(35)
    expect(result.alreadyPaid).toBe(16.22)
    expect(result.balanceDue).toBe(18.78)
    expect(result.suggestedPayment).toBe(18.78)
  })

  it('suggests no payment when the rental is already paid in full', () => {
    const result = rentalReturnBalance({ ...rental, paid: 30, outstanding: 0 })
    expect(result.alreadyPaid).toBe(30)
    expect(result.balanceDue).toBe(0)
    expect(result.suggestedPayment).toBe(0)
    expect(result.outstandingAfterPay).toBe(0)
  })
})

describe('independent motorcycle line durations', () => {
  const start = '2026-09-06T08:00'

  it('keeps a 3-day line and a 1-week line on the same rental', () => {
    const lines = [
      { ratePlan: '3d' as const, days: 3 },
      { ratePlan: '1w' as const, days: 7 },
    ]
    expect(dueDateFromRatePlan(start, '3d')).toBe('2026-09-09T08:00')
    expect(dueDateFromRatePlan(start, '1w')).toBe('2026-09-13T08:00')
    expect(latestLineDueDate(start, lines)).toBe('2026-09-13T08:00')
    expect(lines[0]?.ratePlan).toBe('3d')
    expect(lines[0]?.days).toBe(3)
    expect(lines[1]?.ratePlan).toBe('1w')
    expect(lines[1]?.days).toBe(7)
  })

  it('applies a shared header due to every line only when requested', () => {
    const mixed = [
      { key: 'a', ratePlan: '3d' as const, days: 3 },
      { key: 'b', ratePlan: '1w' as const, days: 7 },
    ]
    const synced = applySharedDurationToLines(mixed, start, dueDateFromRatePlan(start, '1w'))
    expect(synced).toEqual([
      { key: 'a', ratePlan: '1w', days: 7 },
      { key: 'b', ratePlan: '1w', days: 7 },
    ])
    expect(mixed[0]?.ratePlan).toBe('3d')
  })
})
