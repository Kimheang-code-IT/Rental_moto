import type { DocumentTabSchema } from '~/types/docetra/common'
import { adminModules } from './admin-modules'
import { rentalModules } from './rental-modules'

/**
 * Module registry types + helpers for the HollyWing Motor rental system.
 * The freight module catalog was removed in the rental cutover; the admin
 * and rental modules are the only registered modules.
 */

export type FreightFieldType = 'text' | 'date' | 'datetime' | 'number' | 'select' | 'multiselect' | 'textarea' | 'file' | 'password' | 'checkbox'

export type FreightSelectOption = string | { label: string, value: string }

export type FreightField = {
  key: string
  label: string
  labelKm?: string
  section?: string
  sectionKm?: string
  type?: FreightFieldType
  options?: readonly FreightSelectOption[] | FreightSelectOption[]
  required?: boolean
  colSpan?: 1 | 2
  computed?: boolean
  helpKey?: string
  help?: string
  /** Prefer this i18n key for list/filter labels when collection-level field copy differs. */
  labelKey?: string
}

export type FreightLineColumn = {
  key: string
  label: string
  labelKm?: string
  type?: 'text' | 'number' | 'select' | 'textarea' | 'checkbox' | 'date' | 'datetime'
  options?: readonly string[] | string[]
  /** Select labels when they differ from stored values (e.g. container requirement id). */
  optionItems?: Array<{ label: string, value: string }>
  width?: string
  computed?: boolean
  required?: boolean
  labelKey?: string
  /** Small editable money fields rendered inside the same cell under the main value. */
  inlineFields?: Array<{ key: string, label: string, labelKm?: string, labelKey?: string }>
}

export type FreightTable = {
  key: string
  title: string
  titleKm?: string
  columns: FreightLineColumn[]
  addLabel?: string
  addLabelKey?: string
  presets?: Array<Record<string, unknown>>
  lockedPresets?: boolean
  /** Native file picker + File name / By / Created columns. */
  kind?: 'files'
}

export const FILE_ATTACHMENT_COLUMNS: FreightLineColumn[] = [
  { key: 'fileName', label: 'File name', labelKm: 'ឈ្មោះឯកសារ', labelKey: 'freight.ui.fileNameCol', computed: true },
  { key: 'uploadedBy', label: 'By', labelKm: 'ដោយ', labelKey: 'freight.ui.byCol', computed: true },
  { key: 'uploadedAt', label: 'Created', labelKm: 'បង្កើត', labelKey: 'freight.ui.createdCol', type: 'datetime', computed: true },
]

export const SOURCE_RELATIONSHIP_COLUMNS: FreightLineColumn[] = [
  { key: 'sourceType', label: 'Source Type', labelKm: 'ប្រភេទប្រភព', labelKey: 'freight.fields.sourceType' },
  { key: 'sourceNo', label: 'Source Record', labelKm: 'កំណត់ត្រាប្រភព', labelKey: 'freight.fields.sourceNo' },
  { key: 'createdAt', label: 'Linked At', labelKm: 'ភ្ជាប់នៅ', labelKey: 'freight.ui.createdCol' },
]

export type FreightRelated = {
  path: string
  title: string
  titleKm?: string
  foreignKey: string
  localKey: string
}

export type FreightAction = {
  key: string
  label: string
  labelKm?: string
  icon: string
  color?: 'primary' | 'neutral' | 'success' | 'warning' | 'error'
}

/** Named document-form recipes compiled by `moduleDocumentTabs`. */
export type FreightDocumentForm = 'quotation' | 'charges' | 'finance' | 'roles'

export type FreightModule = {
  path: string
  title: string
  titleKm: string
  singular: string
  singularKm: string
  description: string
  descriptionKm: string
  icon: string
  group: string
  permission: string
  collection: string
  titleField: string
  columns: FreightField[]
  fields: FreightField[]
  filters?: FreightField[]
  tables?: FreightTable[]
  /** Nested document tabs (tab → section → field). When omitted, compiled from `documentForm` or fields/tables. */
  tabs?: DocumentTabSchema[]
  /** Quotation / charge / finance / roles tab recipes. Master data omits this (one Details tab). */
  documentForm?: FreightDocumentForm
  /** Hide line-table tabs on the create form (rows can be added after saving). */
  hideTablesOnCreate?: boolean
  related?: FreightRelated[]
  actions?: FreightAction[]
  progress?: readonly string[]
  statuses?: readonly string[] | string[]
  readOnly?: boolean
  /** Render records as a non-navigable table without selection or row actions. */
  tableOnly?: boolean
  canCreate?: boolean
  /** i18n key for the list/header title when collection-level copy is shared (e.g. jobs vs service orders). */
  titleKey?: string
  kind?: 'standard' | 'job' | 'quotation' | 'debit-note' | 'job-charges' | 'reports'
}

const f = (
  key: string,
  label: string,
  labelKm: string,
  section = 'General Information',
  sectionKm = 'ព័ត៌មានទូទៅ',
  type: FreightFieldType = 'text',
  options?: readonly FreightSelectOption[] | FreightSelectOption[],
  extra: Partial<FreightField> = {},
): FreightField => ({ key, label, labelKm, section, sectionKm, type, options, ...extra })

const col = (key: string, label: string, labelKm?: string, extra: Partial<FreightField> = {}): FreightField => ({
  key,
  label,
  labelKm: labelKm || label,
  ...extra,
})

function createModule(partial: Omit<FreightModule, 'canCreate'> & { canCreate?: boolean }): FreightModule {
  return {
    canCreate: partial.readOnly ? false : partial.canCreate !== false,
    kind: partial.kind || 'standard',
    ...partial,
  }
}

/** Registry consumed by generic renderers, route resolution and audit-link resolution. */
export const freightModules: FreightModule[] = [...adminModules, ...rentalModules]

export { f, col, createModule }

export function getFreightModule(path: string) {
  const clean = path.replace(/\/$/, '') || '/'
  const sorted = freightModules
    .slice()
    .sort((a, b) => b.path.length - a.path.length)
  const exact = sorted.find(module => clean === module.path || clean.startsWith(`${module.path}/`))
  if (exact) return exact
  const compact = (value: string) => value.replace(/-/g, '')
  const needle = compact(clean)
  return sorted.find(module => {
    const candidate = compact(module.path)
    return needle === candidate || needle.startsWith(`${candidate}/`)
  })
}
