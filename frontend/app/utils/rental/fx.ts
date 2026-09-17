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

/** A cross-currency USD/KHR rate of 1 is invalid; recover with the market fallback. */
export function exchangeRateForCurrencies(
  value: unknown,
  paymentCurrency: unknown,
  rentalCurrency: unknown,
  fallback = DEFAULT_USD_KHR_RATE,
): number {
  const rate = normalizeExchangeRate(value, fallback)
  return needsExchangeRate(
    normalizePaymentCurrency(paymentCurrency),
    normalizePaymentCurrency(rentalCurrency),
  ) && rate <= 1
    ? normalizeExchangeRate(fallback)
    : rate
}

/** Convert a tendered payment into the rental's accounting currency. */
export function toRentalCurrencyAmount(
  tenderedAmount: number,
  paymentCurrency: PaymentCurrency,
  rentalCurrency: string,
  exchangeRate: number = DEFAULT_USD_KHR_RATE,
): number {
  const tendered = Math.max(0, Number(tenderedAmount) || 0)
  const rental = normalizePaymentCurrency(rentalCurrency)
  const payment = normalizePaymentCurrency(paymentCurrency)
  const rate = exchangeRateForCurrencies(exchangeRate, payment, rental)
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
  const rental = normalizePaymentCurrency(rentalCurrency)
  const payment = normalizePaymentCurrency(paymentCurrency)
  const rate = exchangeRateForCurrencies(exchangeRate, payment, rental)
  if (payment === rental) return Number(amount.toFixed(2))
  if (rental === 'USD' && payment === 'KHR') return Number((amount * rate).toFixed(0))
  if (rental === 'KHR' && payment === 'USD') return Number((amount / rate).toFixed(2))
  return Number(amount.toFixed(2))
}

export function needsExchangeRate(paymentCurrency: PaymentCurrency, rentalCurrency: string): boolean {
  return normalizePaymentCurrency(paymentCurrency) !== normalizePaymentCurrency(rentalCurrency)
}

/**
 * Smallest editable increment for an entered amount by currency.
 * KHR has no subunit, so entered riels step by 1; USD allows cents.
 */
export function currencyInputStep(currency: unknown): number {
  return normalizePaymentCurrency(currency) === 'KHR' ? 1 : 0.01
}

/** Round an entered amount to the smallest unit of its currency. */
export function roundCurrencyAmount(amount: unknown, currency: unknown): number {
  const value = Math.max(0, Number(amount) || 0)
  return normalizePaymentCurrency(currency) === 'KHR'
    ? Math.round(value)
    : Number(value.toFixed(2))
}

/**
 * Build invoice KHR amounts from entered tendered values when available,
 * so ៛10,000 stays ៛10,000 instead of rounding back through USD as ៛10,004.
 */
export function invoiceKhrAmounts(input: {
  subtotal: number
  deposit: number
  discount?: number
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
  discountKhr: number
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
  const discountKhr = fromRentalCurrencyAmount(input.discount || 0, 'KHR', rentalCurrency, rate)

  const paidCurrency = normalizePaymentCurrency(input.paidCurrency || rentalCurrency)
  const paidTendered = Number(input.paidTendered || 0)
  const paidKhr = paidCurrency === 'KHR' && paidTendered > 0
    ? Math.round(paidTendered)
    : fromRentalCurrencyAmount(input.paid, 'KHR', rentalCurrency, rate)

  const totalKhr = Math.max(0, subtotalKhr + depositKhr - discountKhr)
  const outstandingKhr = Math.max(0, totalKhr - paidKhr)
  return { subtotalKhr, depositKhr, discountKhr, totalKhr, paidKhr, outstandingKhr }
}
