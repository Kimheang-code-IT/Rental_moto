import { describe, expect, it } from 'vitest'
import type { ModuleConfig } from '../app/config/modules'
import { moduleDocumentTabs } from '../app/utils/module/document-tabs'

function moduleFixture(overrides: Partial<ModuleConfig> = {}): ModuleConfig {
  return {
    path: '/records',
    title: 'Records',
    titleKm: 'Records',
    singular: 'Record',
    singularKm: 'Record',
    description: '',
    descriptionKm: '',
    icon: 'i-lucide-file',
    group: 'test',
    permission: 'records.view',
    collection: 'records',
    titleField: 'name',
    columns: [],
    fields: [
      { key: 'name', label: 'Name', section: 'General', type: 'text' },
      { key: 'status', label: 'Status', section: 'Status', type: 'select', options: ['Active', 'Inactive'] },
    ],
    statuses: ['Active', 'Inactive'],
    ...overrides,
  }
}

describe('document lifecycle status', () => {
  it('omits status fields and their now-empty sections from generated forms', () => {
    const tabs = moduleDocumentTabs(moduleFixture())
    const sections = tabs.flatMap(tab => tab.sections)
    const fields = sections.flatMap(section => section.fields)

    expect(fields.some(field => field.key === 'status')).toBe(false)
    expect(sections.some(section => section.id === 'status')).toBe(false)
    expect(fields.some(field => field.key === 'name')).toBe(true)
  })

  it('omits Active/Inactive status from the user form', () => {
    const tabs = moduleDocumentTabs(moduleFixture({
      path: '/administration/users',
      collection: 'users',
      permission: 'admin.users.view',
    }))
    const fields = tabs.flatMap(tab => tab.sections.flatMap(section => section.fields))
    expect(fields.some(field => field.key === 'status')).toBe(false)
  })

  it('carries currencyField from module number fields to document fields', () => {
    const tabs = moduleDocumentTabs(moduleFixture({
      fields: [
        { key: 'dailyRate', label: '1 Day Rate', section: 'Rates', type: 'number', currencyField: 'currency' },
        { key: 'year', label: 'Year', section: 'General', type: 'number' },
        { key: 'currency', label: 'Currency', section: 'Rates', type: 'select', options: ['USD', 'KHR'] },
      ],
    }))
    const fields = tabs.flatMap(tab => tab.sections.flatMap(section => section.fields))
    expect(fields.find(field => field.key === 'dailyRate')?.currencyField).toBe('currency')
    expect(fields.find(field => field.key === 'year')?.currencyField).toBeUndefined()
  })

  it('also removes status from custom module tabs', () => {
    const tabs = moduleDocumentTabs(moduleFixture({
      tabs: [{
        id: 'details',
        sections: [{
          id: 'main',
          fields: [
            { key: 'name', labelKey: 'name', type: 'text' },
            { key: 'status', labelKey: 'status', type: 'select' },
          ],
        }],
      }],
    }))

    expect(tabs[0]?.sections[0]?.fields.map(field => field.key)).toEqual(['name'])
  })
})
