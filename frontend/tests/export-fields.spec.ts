import { describe, expect, it } from 'vitest'
import type { ModuleField } from '../app/config/modules'
import { buildModuleExportFields, MODULE_EXPORT_EXTRA_FIELDS } from '../app/utils/export/fields'

const label = (field: Pick<ModuleField, 'key' | 'label'>) => `L:${field.label || field.key}`

function moduleFor(collection: string, columns: Array<{ key: string, label?: string }>) {
  const fieldLabels: Record<string, string> = {
    brand: 'Brand',
    year: 'Year',
    color: 'Color',
    currency: 'Currency',
    email: 'Email',
    identityType: 'Identity Type',
    address: 'Address',
    rateType: 'Rate Type',
    rateAmount: 'Rate Amount',
    deposit: 'Deposit',
    discount: 'Discount',
    additionalCharges: 'Additional Charges',
    returnDate: 'Actual Return',
    condition: 'Motorcycle Condition',
    createdBy: 'Created By',
  }
  return {
    collection,
    columns: columns.map(column => ({ key: column.key, label: column.label || column.key })) as ModuleField[],
    fields: Object.entries(fieldLabels).map(([key, value]) => ({ key, label: value })) as ModuleField[],
  }
}

describe('module export fields', () => {
  it('declares full-data extras for motorcycles, customers, and rentals', () => {
    expect(MODULE_EXPORT_EXTRA_FIELDS.motorcycles).toEqual(['brand', 'year', 'color', 'currency'])
    expect(MODULE_EXPORT_EXTRA_FIELDS.rentalCustomers).toEqual(['email', 'identityType', 'address'])
    expect(MODULE_EXPORT_EXTRA_FIELDS.rentals).toEqual([
      'rateType', 'rateAmount', 'deposit', 'discount', 'currency',
      'additionalCharges', 'returnDate', 'condition', 'createdBy',
    ])
  })

  it('uses visible columns first, in stable order', () => {
    const options = buildModuleExportFields(
      moduleFor('motorcycles', [
        { key: 'code', label: 'Motorcycle Code' },
        { key: 'model', label: 'Model' },
        { key: 'status', label: 'Status' },
      ]),
      label,
    )
    expect(options.slice(0, 3)).toEqual([
      { label: 'L:Motorcycle Code', value: 'code' },
      { label: 'L:Model', value: 'model' },
      { label: 'L:Status', value: 'status' },
    ])
  })

  it('appends full-data fields beyond the visible columns', () => {
    const options = buildModuleExportFields(
      moduleFor('motorcycles', [{ key: 'code' }, { key: 'model' }]),
      label,
    )
    const values = options.map(option => option.value)
    expect(values).toEqual(['code', 'model', 'brand', 'year', 'color', 'currency'])
    expect(options[2]).toEqual({ label: 'L:Brand', value: 'brand' })
  })

  it('labels extra fields from module form fields', () => {
    const options = buildModuleExportFields(
      moduleFor('rentalCustomers', [{ key: 'code' }, { key: 'fullName' }]),
      label,
    )
    const byValue = Object.fromEntries(options.map(option => [option.value, option.label]))
    expect(byValue.email).toBe('L:Email')
    expect(byValue.identityType).toBe('L:Identity Type')
    expect(byValue.address).toBe('L:Address')
  })

  it('never duplicates a field that is already a visible column', () => {
    const options = buildModuleExportFields(
      moduleFor('motorcycles', [{ key: 'code' }, { key: 'model' }, { key: 'brand' }, { key: 'currency' }]),
      label,
    )
    const values = options.map(option => option.value)
    expect(new Set(values).size).toBe(values.length)
    expect(values).toEqual(['code', 'model', 'brand', 'currency', 'year', 'color'])
  })

  it('exposes no extras for collections without full-data fields', () => {
    const options = buildModuleExportFields(moduleFor('users', [{ key: 'displayName' }]), label)
    expect(options.map(option => option.value)).toEqual(['displayName'])
  })
})
