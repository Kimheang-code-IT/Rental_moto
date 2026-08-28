/** Option lists for the HollyWing Motor rental modules. */

export const MOTORCYCLE_STATUS = ['Available', 'Rented', 'Maintenance', 'Inactive'] as const

export const RENTAL_STATUS = ['Active', 'Overdue', 'Completed', 'Cancelled'] as const

export const RATE_TYPES = ['Daily', 'Monthly'] as const

export const RENTAL_IDENTITY_TYPES = ['National ID', 'Passport', 'Driving License', 'Other'] as const

export const RENTAL_CUSTOMER_STATUS = ['Active', 'Inactive'] as const

export const PAYMENT_METHODS = ['Cash', 'Bank Transfer', 'Card', 'QR Payment'] as const

export const RENTAL_CHARGE_TYPES = ['Damage', 'Lost item', 'Cleaning', 'Other'] as const

export const MOTORCYCLE_CONDITIONS = ['Good', 'Minor issues', 'Damaged'] as const

export const RENTAL_EXPENSE_TYPES = ['Fuel', 'Maintenance', 'Salary', 'Rent', 'Marketing', 'Other'] as const

/** Currency preference options (owner mockup — `CODE — Name` labels). */
export const RENTAL_CURRENCY_OPTIONS = [
  { label: 'USD — US Dollar', value: 'USD' },
  { label: 'KHR — Cambodian Riel', value: 'KHR' },
  { label: 'THB — Thai Baht', value: 'THB' },
  { label: 'VND — Vietnamese Dong', value: 'VND' },
  { label: 'SGD — Singapore Dollar', value: 'SGD' },
  { label: 'EUR — Euro', value: 'EUR' },
  { label: 'GBP — British Pound', value: 'GBP' },
  { label: 'JPY — Japanese Yen', value: 'JPY' },
  { label: 'CNY — Chinese Yuan', value: 'CNY' },
  { label: 'AUD — Australian Dollar', value: 'AUD' },
] as const

/** Status → badge color mapping (template convention: color badge + text). */
export const RENTAL_STATUS_COLORS: Record<string, 'success' | 'warning' | 'error' | 'neutral' | 'primary'> = {
  Available: 'success',
  Rented: 'primary',
  Maintenance: 'warning',
  Inactive: 'neutral',
  Active: 'primary',
  Overdue: 'error',
  Completed: 'success',
  Cancelled: 'neutral',
}
