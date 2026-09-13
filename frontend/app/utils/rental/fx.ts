/** Default Cambodia market rate: how many KHR equal 1 USD. */
export const DEFAULT_USD_KHR_RATE = 4100

export type PaymentCurrency = 'USD' | 'KHR'

export function normalizePaymentCurrency(value: unknown): PaymentCurrency {
  return String(value || '').toUpperCase() === 'KHR' ? 'KHR' : 'USD'
}

export function normalizeExchangeRate(value: unknown, fallback = DEFAULT_USD_KHR_RATE): number {
  const rate = Number(value)
  if (!Number.isFinite(rate) || rate <= 0) return fallback
  return Number(rate.toFixed(4))
}

/** Convert a tendered payment into the rental's accounting currency. */
export function toRentalCurrencyAmount(
  tenderedAmount: number,
  paymentCurrency: PaymentCurrency,
  rentalCurrency: string,
  exchangeRate: number = DEFAULT_USD_KHR_RATE,
): number {
  const tendered = Math.max(0, Number(tenderedAmount) || 0)
  const rate = normalizeExchangeRate(exchangeRate)
  const rental = normalizePaymentCurrency(rentalCurrency)
  const payment = normalizePaymentCurrency(paymentCurrency)
  if (payment === rental) return Number(tendered.toFixed(2))
  if (rental === 'USD' && payment === 'KHR') return Number((tendered / rate).toFixed(2))
  if (rental === 'KHR' && payment === 'USD') return Number((tendered * rate).toFixed(2))
  return Number(tendered.toFixed(2))
}

/** Convert a rental-currency amount into the selected payment currency. */
export function fromRentalCurrencyAmount(
  rentalAmount: number,
  paymentCurrency: PaymentCurrency,
  rentalCurrency: string,
  exchangeRate: number = DEFAULT_USD_KHR_RATE,
): number {
  const amount = Math.max(0, Number(rentalAmount) || 0)
  const rate = normalizeExchangeRate(exchangeRate)
  const rental = normalizePaymentCurrency(rentalCurrency)
  const payment = normalizePaymentCurrency(paymentCurrency)
  if (payment === rental) return Number(amount.toFixed(2))
  if (rental === 'USD' && payment === 'KHR') return Number((amount * rate).toFixed(0))
  if (rental === 'KHR' && payment === 'USD') return Number((amount / rate).toFixed(2))
  return Number(amount.toFixed(2))
}

export function needsExchangeRate(paymentCurrency: PaymentCurrency, rentalCurrency: string): boolean {
  return normalizePaymentCurrency(paymentCurrency) !== normalizePaymentCurrency(rentalCurrency)
}

/**
 * Build invoice KHR amounts from entered tendered values when available,
 * so ៛10,000 stays ៛10,000 instead of rounding back through USD as ៛10,004.
 */
export function invoiceKhrAmounts(input: {
  subtotal: number
  deposit: number
  paid: number
  rentalCurrency?: string
  exchangeRate?: number
  depositTendered?: number | null
  depositCurrency?: string | null
  paidTendered?: number | null
  paidCurrency?: string | null
}): {
  subtotalKhr: number
  depositKhr: number
  totalKhr: number
  paidKhr: number
  outstandingKhr: number
} {
  const rentalCurrency = normalizePaymentCurrency(input.rentalCurrency || 'USD')
  const rate = normalizeExchangeRate(input.exchangeRate)
  const subtotalKhr = fromRentalCurrencyAmount(input.subtotal, 'KHR', rentalCurrency, rate)

  const depositCurrency = normalizePaymentCurrency(input.depositCurrency || rentalCurrency)
  const depositTendered = Number(input.depositTendered || 0)
  const depositKhr = depositCurrency === 'KHR' && depositTendered > 0
    ? Math.round(depositTendered)
    : fromRentalCurrencyAmount(input.deposit, 'KHR', rentalCurrency, rate)

  const paidCurrency = normalizePaymentCurrency(input.paidCurrency || rentalCurrency)
  const paidTendered = Number(input.paidTendered || 0)
  const paidKhr = paidCurrency === 'KHR' && paidTendered > 0
    ? Math.round(paidTendered)
    : fromRentalCurrencyAmount(input.paid, 'KHR', rentalCurrency, rate)

  const totalKhr = Math.max(0, subtotalKhr - depositKhr)
  const outstandingKhr = Math.max(0, totalKhr - paidKhr)
  return { subtotalKhr, depositKhr, totalKhr, paidKhr, outstandingKhr }
}
