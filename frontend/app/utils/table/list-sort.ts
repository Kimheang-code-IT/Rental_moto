/** Shared toolbar sort modes for list tables (code / date / reference). */
export type ListSortMode =
  | 'code_asc'
  | 'code_desc'
  | 'date_asc'
  | 'date_desc'
  | 'ref_asc'
  | 'ref_desc'

export type ListSortValueResolvers = {
  codeValue?: (row: Record<string, unknown>) => string
  dateValue?: (row: Record<string, unknown>) => string
  refValue?: (row: Record<string, unknown>) => string
}

export type ListSortPreset = ListSortValueResolvers & {
  modes: readonly ListSortMode[]
  defaultMode: ListSortMode
}

const MODE_I18N: Record<ListSortMode, { key: string, fallback: string }> = {
  code_asc: { key: 'rental.ui.sortSmallToLarge', fallback: 'Small to large' },
  code_desc: { key: 'rental.ui.sortLargeToSmall', fallback: 'Large to small' },
  date_asc: { key: 'rental.ui.sortOldToNew', fallback: 'Old to new' },
  date_desc: { key: 'rental.ui.sortNewToOld', fallback: 'New to old' },
  ref_asc: { key: 'rental.ui.sortSmallToLarge', fallback: 'Small to large' },
  ref_desc: { key: 'rental.ui.sortLargeToSmall', fallback: 'Large to small' },
}

export function listSortItemLabel(mode: ListSortMode): { key: string, fallback: string } {
  return MODE_I18N[mode]
}

function firstPresent(row: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = String(row[key] ?? '').trim()
    if (value) return value
  }
  return ''
}

export function codeFromKeys(...keys: string[]) {
  return (row: Record<string, unknown>) => firstPresent(row, keys)
}

export function dateFromKeys(...keys: string[]) {
  return (row: Record<string, unknown>) => firstPresent(row, keys)
}

export function refFromKeys(...keys: string[]) {
  return (row: Record<string, unknown>) => firstPresent(row, keys)
}

export function compareListSortValues(a: string, b: string, ascending: boolean): number {
  const cmp = a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' })
  return ascending ? cmp : -cmp
}

export function compareListRows(
  a: Record<string, unknown>,
  b: Record<string, unknown>,
  mode: ListSortMode,
  resolvers: ListSortValueResolvers = {},
): number {
  if (mode === 'code_asc' || mode === 'code_desc') {
    const left = resolvers.codeValue?.(a) ?? ''
    const right = resolvers.codeValue?.(b) ?? ''
    return compareListSortValues(left, right, mode === 'code_asc')
  }
  if (mode === 'ref_asc' || mode === 'ref_desc') {
    const left = resolvers.refValue?.(a) ?? ''
    const right = resolvers.refValue?.(b) ?? ''
    return compareListSortValues(left, right, mode === 'ref_asc')
  }
  const left = resolvers.dateValue?.(a) ?? ''
  const right = resolvers.dateValue?.(b) ?? ''
  return compareListSortValues(left, right, mode === 'date_asc')
}

export function sortListRows<T extends Record<string, unknown>>(
  rows: T[],
  mode: ListSortMode,
  resolvers: ListSortValueResolvers = {},
): T[] {
  return [...rows].sort((a, b) => compareListRows(a, b, mode, resolvers))
}

/** Sort presets keyed by app-data collection (or page id). */
export const LIST_SORT_PRESETS = {
  motorcycles: {
    modes: ['code_asc', 'code_desc'],
    defaultMode: 'code_asc',
    codeValue: codeFromKeys('code'),
  },
  rentalCustomers: {
    modes: ['code_asc', 'code_desc'],
    defaultMode: 'code_asc',
    codeValue: codeFromKeys('code'),
  },
  rentals: {
    modes: ['date_desc', 'date_asc', 'code_asc', 'code_desc'],
    defaultMode: 'date_desc',
    codeValue: codeFromKeys('rentalNo'),
    dateValue: dateFromKeys('startDate', 'dueDate', 'returnDate'),
  },
  rentalReports: {
    modes: ['date_desc', 'date_asc', 'code_asc', 'code_desc'],
    defaultMode: 'date_desc',
    codeValue: codeFromKeys('rentalNo'),
    dateValue: dateFromKeys('returnDate', 'dueDate', 'startDate'),
  },
  incomeExpense: {
    modes: ['date_desc', 'date_asc', 'ref_asc', 'ref_desc'],
    defaultMode: 'date_desc',
    dateValue: dateFromKeys('paidAt', 'date'),
    refValue: refFromKeys('paymentNo', 'expenseNo', 'reference'),
  },
} as const satisfies Record<string, ListSortPreset>
