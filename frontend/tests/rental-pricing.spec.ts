import { describe, expect, it } from 'vitest'
import {
  addMonthsToDateTime,
  appliedUnitPrice,
  calendarMonthsBetween,
  detectRatePlan,
  dueDateFromRatePlan,
  lineCharge,
  rentalRateType,
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
})
