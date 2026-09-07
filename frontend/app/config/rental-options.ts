/** Option lists for the HollyWing Motor rental modules. */

export const MOTORCYCLE_STATUS = ['Available', 'Progressing', 'Maintenance'] as const

export const RENTAL_STATUS = ['Active', 'Overdue', 'Completed', 'Cancelled'] as const

export const RATE_TYPES = ['Daily', 'ThreeDay', 'Weekly', 'Monthly'] as const

export const RENTAL_IDENTITY_TYPES = ['National ID', 'Passport', 'Driving License', 'Other'] as const

export const RENTAL_CUSTOMER_STATUS = ['Active', 'Inactive'] as const

export const PAYMENT_METHODS = ['Cash', 'Bank Transfer', 'Card', 'QR Payment'] as const

export const RENTAL_CHARGE_TYPES = ['Damage', 'Lost item', 'Cleaning', 'Other'] as const

export const MOTORCYCLE_CONDITIONS = ['Good', 'Minor issues', 'Damaged'] as const

export const RENTAL_EXPENSE_TYPES = ['Fuel', 'Maintenance', 'Salary', 'Rent', 'Marketing', 'Other'] as const

/** Statuses staff can set after return (Progressing is rental-driven). */
export const MOTORCYCLE_RETURN_STATUSES = ['Available', 'Maintenance'] as const

/** Currency options (USD and KHR only). */
export const RENTAL_CURRENCY_OPTIONS = [
  { label: 'USD — US Dollar', value: 'USD' },
  { label: 'KHR — Cambodian Riel', value: 'KHR' },
] as const

/** Status → badge color mapping (template convention: color badge + text). */
export const RENTAL_STATUS_COLORS: Record<string, 'success' | 'warning' | 'error' | 'neutral' | 'primary'> = {
  Available: 'success',
  Progressing: 'primary',
  Maintenance: 'warning',
  Active: 'success',
  Inactive: 'neutral',
  Overdue: 'error',
  Completed: 'success',
  Cancelled: 'neutral',
}
