import type { AppRecord } from '~/config/admin-seed'

/** Guard against mutating records that should be read-only. */
export function assertMutableRecord(_collection: string, _existing: AppRecord | null, _next?: AppRecord) {
  // Rental and admin collections have no special immutability rules in the UI layer.
}
