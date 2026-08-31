/** Resolve the most recent recorded payment method for each rental. */
export function latestRentalPaymentMethods(payments: Array<Record<string, unknown>>) {
  const latest = new Map<string, { method: string, paidAt: string }>()
  for (const payment of payments) {
    const rentalId = String(payment.rentalId || '')
    const method = String(payment.paymentMethod || '')
    const paidAt = String(payment.paidAt || '')
    if (!rentalId || !method) continue
    const current = latest.get(rentalId)
    if (!current || paidAt >= current.paidAt) latest.set(rentalId, { method, paidAt })
  }
  return new Map([...latest].map(([rentalId, value]) => [rentalId, value.method]))
}
