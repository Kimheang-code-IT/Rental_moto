import { describe, expect, it } from 'vitest'
import { compactQuery } from '../app/utils/api/query'
import { safeInternalPath } from '../app/utils/auth/session'
import { safeApiBase, safeExternalUrl, sameOriginApiUrl } from '../app/utils/security/url'

describe('security boundaries', () => {
  it('accepts only safe internal redirects', () => {
    expect(safeInternalPath('/rentals/123')).toBe('/rentals/123')
    expect(safeInternalPath('//evil.example')).toBeNull()
    expect(safeInternalPath('/auth/login')).toBeNull()
    expect(safeInternalPath('/rentals\u0000/123')).toBeNull()
  })

  it('rejects executable and credential-bearing external URLs', () => {
    expect(safeExternalUrl('javascript:alert(1)')).toBeNull()
    expect(safeExternalUrl('https://user:secret@example.com/file')).toBeNull()
    expect(safeExternalUrl('https://example.com/file')).toBe('https://example.com/file')
  })

  it('requires HTTPS for a production API base', () => {
    expect(safeApiBase('http://localhost:8000', false)).toBe('http://localhost:8000')
    expect(safeApiBase('http://api.example.com', true)).toBeNull()
    expect(safeApiBase('https://api.example.com/', true)).toBe('https://api.example.com')
  })

  it('prevents requests from escaping the configured API origin', () => {
    expect(sameOriginApiUrl('/api/v1/rentals', 'https://api.example.com')).toBe('https://api.example.com/api/v1/rentals')
    expect(sameOriginApiUrl('https://evil.example/rentals', 'https://api.example.com')).toBeNull()
  })

  it('removes empty query values without changing valid filters', () => {
    expect(compactQuery({ q: 'bike', empty: '', none: null, page: 1, status: [] })).toEqual({ q: 'bike', page: 1 })
  })
})
