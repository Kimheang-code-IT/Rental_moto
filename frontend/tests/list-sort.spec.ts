import { describe, expect, it } from 'vitest'
import {
  compareListRows,
  LIST_SORT_PRESETS,
  sortListRows,
} from '~/utils/table/list-sort'

describe('list-sort', () => {
  it('sorts motorcycle codes small to large / large to small', () => {
    const rows = [{ code: 'MC-10' }, { code: 'MC-2' }, { code: 'MC-1' }]
    const preset = LIST_SORT_PRESETS.motorcycles
    expect(sortListRows(rows, 'code_asc', preset).map(r => r.code)).toEqual(['MC-1', 'MC-2', 'MC-10'])
    expect(sortListRows(rows, 'code_desc', preset).map(r => r.code)).toEqual(['MC-10', 'MC-2', 'MC-1'])
  })

  it('sorts rentals by start date with due/return fallback', () => {
    const rows = [
      { rentalNo: 'RNT-3', dueDate: '2026-03-01' },
      { rentalNo: 'RNT-1', startDate: '2026-01-15' },
      { rentalNo: 'RNT-2', returnDate: '2026-02-01' },
    ]
    const preset = LIST_SORT_PRESETS.rentals
    expect(sortListRows(rows, 'date_asc', preset).map(r => r.rentalNo)).toEqual(['RNT-1', 'RNT-2', 'RNT-3'])
    expect(sortListRows(rows, 'date_desc', preset).map(r => r.rentalNo)).toEqual(['RNT-3', 'RNT-2', 'RNT-1'])
  })

  it('sorts rental reports by return date then rental number', () => {
    const rows = [
      { rentalNo: 'RNT-2', returnDate: '2026-02-01' },
      { rentalNo: 'RNT-10', returnDate: '2026-01-01' },
      { rentalNo: 'RNT-1', dueDate: '2026-03-01' },
    ]
    const preset = LIST_SORT_PRESETS.rentalReports
    expect(sortListRows(rows, 'date_asc', preset).map(r => r.rentalNo)).toEqual(['RNT-10', 'RNT-2', 'RNT-1'])
    expect(sortListRows(rows, 'code_asc', preset).map(r => r.rentalNo)).toEqual(['RNT-1', 'RNT-2', 'RNT-10'])
  })

  it('sorts income/expense by date and reference', () => {
    const rows = [
      { paymentNo: 'PAY-2', paidAt: '2026-02-01' },
      { expenseNo: 'EXP-1', date: '2026-01-15' },
      { paymentNo: 'PAY-10', paidAt: '2026-03-01' },
    ]
    const preset = LIST_SORT_PRESETS.incomeExpense
    expect(sortListRows(rows, 'date_asc', preset).map(r => String(r.paymentNo || r.expenseNo)))
      .toEqual(['EXP-1', 'PAY-2', 'PAY-10'])
    expect(sortListRows(rows, 'ref_asc', preset).map(r => String(r.paymentNo || r.expenseNo)))
      .toEqual(['EXP-1', 'PAY-2', 'PAY-10'])
  })

  it('compares empty values consistently', () => {
    expect(compareListRows({ code: '' }, { code: 'A' }, 'code_asc', LIST_SORT_PRESETS.motorcycles)).toBeLessThan(0)
  })
})
