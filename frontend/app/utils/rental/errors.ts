import type { RentalApiErrorBody, RentalErrorCode } from '~/types/rental/domain'

export class RentalDomainError extends Error {
  readonly code: string
  readonly request_id: string
  readonly field_errors?: Record<string, string>
  readonly statusCode: number

  constructor(body: RentalApiErrorBody, statusCode = 409) {
    super(body.message)
    this.name = 'RentalDomainError'
    this.code = body.code
    this.request_id = body.request_id
    this.field_errors = body.field_errors
    this.statusCode = statusCode
  }

  toBody(): RentalApiErrorBody {
    return {
      code: this.code,
      message: this.message,
      request_id: this.request_id,
      field_errors: this.field_errors,
    }
  }
}

export function newRequestId() {
  return `req_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

export function domainError(
  code: RentalErrorCode,
  message: string,
  options: { statusCode?: number, field_errors?: Record<string, string> } = {},
) {
  return new RentalDomainError({
    code,
    message,
    request_id: newRequestId(),
    field_errors: options.field_errors,
  }, options.statusCode ?? (code === 'ACCESS_DENIED' ? 403 : 409))
}

export function isRentalDomainError(error: unknown): error is RentalDomainError {
  return error instanceof RentalDomainError
}
