import { describe, expect, it } from 'vitest'
import { latestRentalPaymentMethods } from '../app/utils/rental/payments'

describe('latestRentalPaymentMethods', () => {
  it('keeps the most recent payment method for each rental', () => {
    const methods = latestRentalPaymentMethods([
      { rentalId: 'rental-1', paymentMethod: 'Cash', paidAt: '2026-08-01T09:00' },
      { rentalId: 'rental-2', paymentMethod: 'Card', paidAt: '2026-08-02T09:00' },
      { rentalId: 'rental-1', paymentMethod: 'Bank Transfer', paidAt: '2026-08-03T09:00' },
    ])

    expect(methods.get('rental-1')).toBe('Bank Transfer')
    expect(methods.get('rental-2')).toBe('Card')
  })

  it('ignores payments without a rental or method', () => {
    const methods = latestRentalPaymentMethods([
      { rentalId: '', paymentMethod: 'Cash', paidAt: '2026-08-01' },
      { rentalId: 'rental-1', paymentMethod: '', paidAt: '2026-08-01' },
    ])

    expect(methods.size).toBe(0)
  })
})
