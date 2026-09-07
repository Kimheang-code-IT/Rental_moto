import type { ModuleField } from '~/config/modules'
import type { ExportFieldOption } from '~/types/rental/export'

/**
 * Full-data export fields beyond the visible table columns, per module collection.
 * Module tables are the source of truth for visible columns; these extras are
 * form fields users expect in a complete data export.
 */
export const MODULE_EXPORT_EXTRA_FIELDS: Record<string, string[]> = {
  motorcycles: ['brand', 'year', 'color', 'currency'],
  rentalCustomers: ['email', 'identityType', 'address'],
  rentals: [
    'rateType',
    'rateAmount',
    'deposit',
    'discount',
    'currency',
    'additionalCharges',
    'returnDate',
    'condition',
    'createdBy',
  ],
}

function humanizeKey(key: string) {
  return key
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/^./, char => char.toUpperCase())
}

type ModuleExportSource = {
  collection?: string
  columns: ModuleField[]
  fields: ModuleField[]
}

/**
 * Build export field options for a module: visible columns first (stable order),
 * then any extra full-data fields that are not already columns.
 * UI-only columns (selection checkbox / row actions) are never part of
 * module.columns, so they are excluded by construction.
 */
export function buildModuleExportFields(
  module: ModuleExportSource,
  label: (field: Pick<ModuleField, 'key' | 'label' | 'labelKm' | 'labelKey'>) => string,
): ExportFieldOption[] {
  const options: ExportFieldOption[] = []
  const seen = new Set<string>()
  for (const column of module.columns || []) {
    if (seen.has(column.key)) continue
    seen.add(column.key)
    options.push({ label: label(column), value: column.key })
  }
  const fieldByKey = new Map((module.fields || []).map(field => [field.key, field]))
  for (const key of MODULE_EXPORT_EXTRA_FIELDS[module.collection || ''] || []) {
    if (seen.has(key)) continue
    seen.add(key)
    const field = fieldByKey.get(key)
    options.push({
      label: field ? label(field) : humanizeKey(key),
      value: key,
    })
  }
  return options
}
