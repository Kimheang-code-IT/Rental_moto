import type { PersonSummary, OrganizationSummary, AttachmentMeta } from '~/types/docetra/common'
import { createId, nowIso } from './query'

export const people: PersonSummary[] = [
  { id: 'p1', name: 'Sokha Chan', email: 'sokha@hollywing.local' },
  { id: 'p2', name: 'Dara Kim', email: 'dara@hollywing.local' },
  { id: 'p3', name: 'Sreymom Lim', email: 'sreymom@hollywing.local' },
  { id: 'p4', name: 'Vannak Ouk', email: 'vannak@hollywing.local' },
  { id: 'p5', name: 'Chenda Meas', email: 'chenda@hollywing.local' },
]

export const orgs: OrganizationSummary[] = [
  { id: 'o1', name: 'HollyWing Motor', code: 'HWM' },
  { id: 'o2', name: 'Demo Rental', code: 'DEMO' },
]

export function person(i = 0) {
  return people[i % people.length]!
}

export function org(i = 0) {
  return orgs[i % orgs.length]!
}

export function daysAgo(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString()
}

export function dateOnly(n: number) {
  return daysAgo(n).slice(0, 10)
}

export function seedAttachments(count = 2): AttachmentMeta[] {
  return Array.from({ length: count }, (_, i) => ({
    id: createId('att'),
    name: i === 0 ? 'cover-letter.pdf' : 'supporting-docs.zip',
    mimeType: i === 0 ? 'application/pdf' : 'application/zip',
    sizeBytes: 120_000 + i * 80_000,
    uploadedBy: person(i),
    uploadedAt: daysAgo(i),
    storageSource: i === 0 ? 'local' : 'google_drive',
  }))
}

export { nowIso, createId }
