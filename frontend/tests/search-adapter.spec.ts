import { describe, expect, it } from 'vitest'
import { adaptBackendSearchHits } from '../app/composables/search/useSearch'

describe('backend search response adapter', () => {
  it('maps the { hits, total } backend contract to UI search hits', () => {
    const hits = adaptBackendSearchHits([
      { id: 'rt-001', type: 'rental', title: 'RNT-2026-000001', subtitle: 'Sok Dara', url: '/rentals/rt-001' },
      { id: 'mc-001', type: 'motorcycle', title: 'Honda Click', subtitle: 'MC-001', url: '/motorcycles/mc-001' },
      { id: '1', type: 'user', title: 'Admin', subtitle: 'owner@example.com', url: '/administration/users/1' },
    ])

    expect(hits).toHaveLength(3)
    expect(hits[0]).toMatchObject({
      id: 'rt-001',
      entityType: 'document',
      entityId: 'rt-001',
      title: 'RNT-2026-000001',
      snippet: 'Sok Dara',
      url: '/rentals/rt-001',
    })
    expect(hits[0]?.sourceLabel).toBe('Rentals')
    expect(hits[1]?.sourceLabel).toBe('Motorcycles')
    expect(hits[2]?.entityType).toBe('user')
    expect(hits.every(hit => typeof hit.score === 'number')).toBe(true)
  })

  it('maps an empty hit list to an empty array', () => {
    expect(adaptBackendSearchHits([])).toEqual([])
  })
})
