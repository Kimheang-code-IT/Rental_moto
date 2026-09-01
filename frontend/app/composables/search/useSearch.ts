import type {
  AiSearchAnswer,
  IndexedDocument,
  SearchHit,
  SearchMode,
  SearchQueryOptions,
} from '~/types/rental/search'
import { listIndexedDocuments } from '~/utils/search/search-index'
import { ensureSearchIndexSeeded, sourceLabelFor } from '~/utils/search/seed-index'
import { makeSnippet } from '~/utils/search/text-extract'
import { mockLatency } from '~/mocks/query'
import { useSearchRepository } from '~/repositories/index'

/** Simple synonym map for mock semantic ranking. */
const SEMANTIC_SYNONYMS: Record<string, string[]> = {
  rental: ['hire', 'lease', 'booking'],
  motorcycle: ['bike', 'moto', 'scooter'],
  customer: ['client', 'renter'],
  payment: ['paid', 'receipt', 'invoice'],
  overdue: ['late', 'past due'],
  report: ['summary', 'analytics'],
  expense: ['cost', 'spend'],
  document: ['file', 'record', 'pdf'],
  upload: ['file', 'attachment'],
}

/** Backend hit type → UI search entity type (for icon rendering only). */
function entityTypeFromBackend(type: string): SearchHit['entityType'] {
  if (type === 'user') return 'user'
  return 'document'
}

function sourceLabelFromBackend(type: string): string {
  const labels: Record<string, string> = {
    motorcycle: 'Motorcycles',
    customer: 'Customers',
    rental: 'Rentals',
  }
  return labels[type] || 'Records'
}

/** Map a backend `{ hits, total }` search response to the UI hit type. */
export function adaptBackendSearchHits(
  hits: Array<{ id: string, type: string, title: string, subtitle?: string | null, url: string }>,
): SearchHit[] {
  return hits.map(hit => ({
    id: hit.id,
    entityType: entityTypeFromBackend(hit.type),
    entityId: hit.id,
    title: hit.title,
    text: hit.subtitle || '',
    url: hit.url,
    permission: '',
    updatedAt: '',
    score: 1,
    snippet: hit.subtitle || '',
    sourceLabel: sourceLabelFromBackend(hit.type),
  }))
}

export function useSearch() {
  const config = useRuntimeConfig()
  const auth = useAuthStore()

  function usesMockData() {
    return config.public.useMockData !== false
  }

  function canSee(permission: string): boolean {
    if (!permission) return true
    return auth.canAccessPage(permission) || auth.canAccessPage('ALL_PAGES')
  }

  function tokenize(q: string): string[] {
    return q
      .toLowerCase()
      .split(/[^a-z0-9\u1780-\u17FF]+/i)
      .map(t => t.trim())
      .filter(t => t.length > 1)
  }

  function expandSemanticTokens(tokens: string[]): string[] {
    const out = new Set(tokens)
    for (const t of tokens) {
      const syns = SEMANTIC_SYNONYMS[t]
      if (syns) syns.forEach(s => out.add(s))
      for (const [key, values] of Object.entries(SEMANTIC_SYNONYMS)) {
        if (values.includes(t)) {
          out.add(key)
          values.forEach(s => out.add(s))
        }
      }
    }
    return [...out]
  }

  function scoreKeyword(doc: IndexedDocument, query: string, tokens: string[]): number {
    const hay = `${doc.title}\n${doc.text}`.toLowerCase()
    const q = query.toLowerCase().trim()
    let score = 0
    if (q && hay.includes(q)) score += 40
    if (q && doc.title.toLowerCase().includes(q)) score += 30
    for (const t of tokens) {
      if (doc.title.toLowerCase().includes(t)) score += 8
      if (hay.includes(t)) score += 4
    }
    return score
  }

  function scoreSemantic(doc: IndexedDocument, tokens: string[]): number {
    const hay = `${doc.title}\n${doc.text}`.toLowerCase()
    let score = 0
    for (const t of tokens) {
      if (doc.title.toLowerCase().includes(t)) score += 10
      if (hay.includes(t)) score += 6
    }
    return score
  }

  function toHit(doc: IndexedDocument, score: number, query: string): SearchHit {
    return {
      ...doc,
      score,
      snippet: makeSnippet(doc.text || doc.title, query),
      sourceLabel: sourceLabelFor(doc.entityType),
    }
  }

  function filterAndRank(
    mode: SearchMode,
    query: string,
    limit: number,
  ): SearchHit[] {
    ensureSearchIndexSeeded()
    const q = query.trim()
    if (!q) return []

    const docs = listIndexedDocuments().filter(d => canSee(d.permission))
    const tokens = tokenize(q)
    const semanticTokens = mode === 'semantic' ? expandSemanticTokens(tokens) : tokens

    const scored = docs
      .map((doc) => {
        const score = mode === 'semantic'
          ? scoreSemantic(doc, semanticTokens)
          : scoreKeyword(doc, q, tokens)
        return toHit(doc, score, q)
      })
      .filter(h => h.score > 0)
      .sort((a, b) => b.score - a.score || b.updatedAt.localeCompare(a.updatedAt))

    return scored.slice(0, limit)
  }

  async function searchKeyword(query: string, options: SearchQueryOptions = {}) {
    const limit = options.limit ?? 12
    if (!usesMockData()) {
      // Backend search is keyword-based SQL search for every mode.
      const hits = await useSearchRepository().search(query, limit)
      return adaptBackendSearchHits(hits)
    }
    await mockLatency(null, 20)
    return filterAndRank('keyword', query, limit)
  }

  async function searchSemantic(query: string, options: SearchQueryOptions = {}) {
    const limit = options.limit ?? 12
    if (!usesMockData()) {
      // The backend has no semantic search endpoint. In HTTP mode semantic
      // queries fall back to the same honest keyword search — they are never
      // labelled as AI/semantic results here.
      const hits = await useSearchRepository().search(query, limit)
      return adaptBackendSearchHits(hits)
    }
    await mockLatency(null, 40)
    return filterAndRank('semantic', query, limit)
  }

  async function askAi(query: string, hits: SearchHit[]): Promise<AiSearchAnswer> {
    if (!usesMockData()) {
      // `/api/v2/search/ask` does not exist on the backend. Return an honest
      // unsupported answer built only from keyword hits — never fabricate an AI
      // response or label SQL search as semantic AI.
      await mockLatency(null, 20)
      const citations = hits.slice(0, 5)
      if (!citations.length) {
        return {
          answer: `No records matched “${query.trim()}”. Semantic AI answers are not available for the connected backend.`,
          citations: [],
        }
      }
      const lines = citations.map((c, i) => `${i + 1}. ${c.title} (${c.sourceLabel}) → ${c.url}`)
      return {
        answer: [
          `Semantic AI answers are not available for the connected backend.`,
          '',
          `Keyword search found ${hits.length} matching record(s) for “${query.trim()}”:`,
          ...lines,
        ].join('\n'),
        citations,
      }
    }

    await mockLatency(null, 80)
    const citations = hits.slice(0, 5)
    if (!citations.length) {
      return {
        answer: `No permitted sources matched “${query.trim()}”. Try keyword mode or a different term.`,
        citations: [],
      }
    }

    const lines = citations.map((c, i) => `${i + 1}. ${c.title} (${c.sourceLabel}) → ${c.url}`)
    return {
      answer: [
        `Based on indexed files and records you can access, here is a short summary for “${query.trim()}”:`,
        '',
        `Top matches mention ${citations.map(c => c.title).slice(0, 3).join(', ')}.`,
        'Open a source below to verify details in context.',
        '',
        'Sources:',
        ...lines,
      ].join('\n'),
      citations,
    }
  }

  return {
    searchKeyword,
    searchSemantic,
    askAi,
  }
}
