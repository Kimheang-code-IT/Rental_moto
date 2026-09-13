import { describe, expect, it } from 'vitest'
import {
  DEFAULT_USD_KHR_RATE,
  fromRentalCurrencyAmount,
  invoiceKhrAmounts,
  needsExchangeRate,
  toRentalCurrencyAmount,
} from '../app/utils/rental/fx'

describe('rental fx', () => {
  it('keeps same-currency amounts unchanged', () => {
    expect(toRentalCurrencyAmount(12.5, 'USD', 'USD', 4100)).toBe(12.5)
    expect(toRentalCurrencyAmount(50000, 'KHR', 'KHR', 4100)).toBe(50000)
  })

  it('converts KHR tender into USD rental credit', () => {
    expect(toRentalCurrencyAmount(8200, 'KHR', 'USD', 4100)).toBe(2)
  })

  it('converts USD tender into KHR rental credit', () => {
    expect(toRentalCurrencyAmount(2, 'USD', 'KHR', 4100)).toBe(8200)
  })

  it('suggests tendered amount from rental balance', () => {
    expect(fromRentalCurrencyAmount(2, 'KHR', 'USD', 4100)).toBe(8200)
    expect(fromRentalCurrencyAmount(8200, 'USD', 'KHR', 4100)).toBe(2)
  })

  it('requires an exchange rate only when currencies differ', () => {
    expect(needsExchangeRate('USD', 'USD')).toBe(false)
    expect(needsExchangeRate('KHR', 'USD')).toBe(true)
    expect(DEFAULT_USD_KHR_RATE).toBe(4100)
  })

  it('keeps invoice KHR amounts equal to entered tendered riels', () => {
    // 10000/4100 → $2.44; reversing would show 10004 without tendered storage.
    expect(toRentalCurrencyAmount(10000, 'KHR', 'USD', 4100)).toBe(2.44)
    expect(fromRentalCurrencyAmount(2.44, 'KHR', 'USD', 4100)).toBe(10004)

    const amounts = invoiceKhrAmounts({
      subtotal: 10,
      deposit: 2.44,
      paid: 4.88,
      rentalCurrency: 'USD',
      exchangeRate: 4100,
      depositTendered: 10000,
      depositCurrency: 'KHR',
      paidTendered: 20000,
      paidCurrency: 'KHR',
    })
    expect(amounts.subtotalKhr).toBe(41000)
    expect(amounts.depositKhr).toBe(10000)
    expect(amounts.paidKhr).toBe(20000)
    expect(amounts.totalKhr).toBe(31000)
    expect(amounts.outstandingKhr).toBe(11000)
  })
})
