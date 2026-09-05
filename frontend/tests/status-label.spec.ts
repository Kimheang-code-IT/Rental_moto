import { describe, expect, it } from 'vitest'
import { statusLabel, statusSlug } from '../app/utils/module/format'

const en: Record<string, string> = {
  'app.statuses.available': 'Available',
  'app.statuses.progressing': 'Progressing',
  'app.statuses.active': 'Active',
  'app.statuses.overdue': 'Overdue',
  'app.statuses.paid': 'Paid',
  'app.statuses.partial': 'Partial',
}

const km: Record<string, string> = {
  'app.statuses.available': 'ទំនេរ',
  'app.statuses.progressing': 'កំពុងជួល',
  'app.statuses.active': 'សកម្ម',
  'app.statuses.overdue': 'ហួសកំណត់',
  'app.statuses.paid': 'បានបង់',
  'app.statuses.partial': 'បង់មួយផ្នែក',
}

function makeI18n(map: Record<string, string>) {
  return {
    t: (key: string) => map[key] || key,
    te: (key: string) => key in map,
  }
}

describe('statusLabel', () => {
  it('slugs mixed casing and spaces', () => {
    expect(statusSlug('Progressing')).toBe('progressing')
    expect(statusSlug('Minor issues')).toBe('minor_issues')
    expect(statusSlug('ACTIVE')).toBe('active')
  })

  it('returns English labels', () => {
    const { t, te } = makeI18n(en)
    expect(statusLabel('Available', t, te)).toBe('Available')
    expect(statusLabel('ACTIVE', t, te)).toBe('Active')
    expect(statusLabel('Partial', t, te)).toBe('Partial')
  })

  it('returns Khmer labels', () => {
    const { t, te } = makeI18n(km)
    expect(statusLabel('Available', t, te)).toBe('ទំនេរ')
    expect(statusLabel('Progressing', t, te)).toBe('កំពុងជួល')
    expect(statusLabel('Overdue', t, te)).toBe('ហួសកំណត់')
    expect(statusLabel('Paid', t, te)).toBe('បានបង់')
  })
})
