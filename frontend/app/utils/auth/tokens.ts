/**
 * Client-only bearer token storage.
 *
 * Tokens persist in localStorage for the refresh-token lifetime (7 days) so a
 * closed tab or browser restart does not force an immediate sign-in. They are
 * also mirrored in module memory so `useApi()` can attach Authorization without
 * async storage reads. Tokens never enter the readable `auth_user` cookie.
 */

const ACCESS_KEY = 'rental-moto:auth:access-token'
const REFRESH_KEY = 'rental-moto:auth:refresh-token'

let memoryAccess: string | null = null
let memoryRefresh: string | null = null

function readStored(key: string): string | null {
  if (!import.meta.client) return null
  try {
    const fromLocal = localStorage.getItem(key)
    if (fromLocal) return fromLocal
    // Migrate tokens written by older builds that used sessionStorage.
    const fromSession = sessionStorage.getItem(key)
    if (fromSession) {
      localStorage.setItem(key, fromSession)
      sessionStorage.removeItem(key)
      return fromSession
    }
  }
  catch {
    return null
  }
  return null
}

function writeStored(key: string, value: string | null) {
  if (!import.meta.client) return
  try {
    if (value) localStorage.setItem(key, value)
    else localStorage.removeItem(key)
    sessionStorage.removeItem(key)
  }
  catch {
    // Storage may be unavailable (private mode); memory mirror still works.
  }
}

export function getAccessToken(): string | null {
  if (memoryAccess === null) memoryAccess = readStored(ACCESS_KEY)
  return memoryAccess
}

export function getRefreshToken(): string | null {
  if (memoryRefresh === null) memoryRefresh = readStored(REFRESH_KEY)
  return memoryRefresh
}

export function setTokens(access: string | null, refresh: string | null) {
  memoryAccess = access
  memoryRefresh = refresh
  writeStored(ACCESS_KEY, access)
  writeStored(REFRESH_KEY, refresh)
}

export function setAccessToken(access: string | null) {
  memoryAccess = access
  writeStored(ACCESS_KEY, access)
}

export function clearTokens() {
  setTokens(null, null)
}

export function hasTokens(): boolean {
  return Boolean(getAccessToken() || getRefreshToken())
}
