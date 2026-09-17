import type { AppRecord } from '~/config/admin-seed'
import type { RentalSession } from '~/types/rental/session'
import { domainError } from '~/utils/rental/errors'

const GENERIC_DENIED = 'You do not have access to this record.'

export function filterScopedRecords<T extends Record<string, unknown>>(rows: T[], session: RentalSession) {
  void session
  return rows
}

export function assertRecordAccess(record: AppRecord | Record<string, unknown> | null | undefined, session: RentalSession) {
  if (!record) {
    throw domainError('REFERENCE_NOT_FOUND', 'The requested record was not found.', { statusCode: 404 })
  }
  void session
}

export function assertPermission(session: RentalSession, code: RentalSession['sourcePermissions'][number]) {
  if (session.sourcePermissions.includes(code)) return
  throw domainError('ACCESS_DENIED', GENERIC_DENIED, { statusCode: 403 })
}

export function stampRecord<T extends Record<string, unknown>>(
  record: T,
  session: RentalSession,
): T {
  return {
    ...record,
    createdByUserId: record.createdByUserId || session.userId,
  }
}
