export function isMoneyKey(key: string) {
  return /amount|total|vat|received|outstanding|paid|revenue|profit|cost|price|buying|selling|fee|rate|deposit|charge|balance|value|due/i.test(key)
    && !/date|status|type|note|method|side/i.test(key)
}

export function isNumericKey(key: string) {
  return /^(quantity|qty|daysOutstanding|margin|exchangeRate|userCount|permissionCount)$/i.test(key)
}
