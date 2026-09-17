/** Shared display formatting for rental tables, strips, and badges. */

import { formatDate } from '~/utils/format/format-service'

type Translate = (key: string) => string
type TranslateExists = (key: string) => boolean

/**
 * Compact day cell via System Settings date format.
 * Pass `fallback` explicitly when a page needs `''` instead of `—`.
 */
export function shortDay(value: unknown, fallback = '—') {
  return formatDate(value, fallback)
}

/** Normalize status codes for i18n lookup (`Progressing` → `progressing`, `ACTIVE` → `active`). */
export function statusSlug(value: unknown) {
  return String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
}

/**
 * Localized label for status / result codes shown in tables and badges.
 * Values stored in the DB stay English; only the display label is translated.
 */
export function statusLabel(value: unknown, t: Translate, te: TranslateExists) {
  const raw = String(value ?? '').trim()
  if (!raw) return '—'
  const slug = statusSlug(raw)
  const keys = [
    `app.statuses.${slug}`,
    `app.reportCatalog.statuses.${slug}`,
  ]
  for (const key of keys) {
    if (te(key)) return String(t(key))
  }
  if (/^[A-Z0-9_]+$/.test(raw)) return codeTitle(raw)
  return raw
}

/** Select items for status constants, using `app.statuses.*` when present. */
export function labeledStatusOptions(
  values: readonly string[],
  t: Translate,
  te: TranslateExists,
) {
  return values.map(value => ({
    label: statusLabel(value, t, te),
    value,
  }))
}

/** Title-cased label for UPPER_SNAKE codes (e.g. `CUSTOMER_INVOICE` → `Customer Invoice`). */
export function codeTitle(value: unknown) {
  return String(value ?? '')
    .replaceAll('_', ' ')
    .toLowerCase()
    .replace(/\b\w/g, ch => ch.toUpperCase())
}
