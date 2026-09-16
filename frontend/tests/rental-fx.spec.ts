import { describe, expect, it } from 'vitest'
import {
  currencyInputStep,
  DEFAULT_USD_KHR_RATE,
  exchangeRateForCurrencies,
  fromRentalCurrencyAmount,
  invoiceKhrAmounts,
  needsExchangeRate,
  roundCurrencyAmount,
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

  it('repairs rate 1 when USD and KHR differ', () => {
    expect(exchangeRateForCurrencies(1, 'KHR', 'USD')).toBe(4100)
    expect(exchangeRateForCurrencies(4200, 'KHR', 'USD')).toBe(4200)
    expect(exchangeRateForCurrencies(1, 'USD', 'USD')).toBe(1)
  })

  it('steps entered amounts by currency subunit', () => {
    expect(currencyInputStep('KHR')).toBe(1)
    expect(currencyInputStep('USD')).toBe(0.01)
  })

  it('rounds entered amounts to the currency smallest unit', () => {
    expect(roundCurrencyAmount(2550.6, 'KHR')).toBe(2551)
    expect(roundCurrencyAmount(12.345, 'USD')).toBe(12.35)
    expect(roundCurrencyAmount(-5, 'USD')).toBe(0)
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
    expect(amounts.totalKhr).toBe(41000)
    expect(amounts.outstandingKhr).toBe(21000)
  })
})
