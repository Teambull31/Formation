// Lien direct (raccourcis de l'appli installée, notification) : /?tab=ecoute, /?tab=revisions&sub=cartes
export const TABS = ['Quête', 'Leçon', 'Équipe', 'Boss', 'Révisions', 'Écoute', 'Semaine'] as const
export type Tab = (typeof TABS)[number]
const SLUG: Record<string, Tab> = { quete: 'Quête', lecon: 'Leçon', equipe: 'Équipe', boss: 'Boss', revisions: 'Révisions', ecoute: 'Écoute', semaine: 'Semaine' }
const SUBS = ['qcm', 'cartes', 'examen', 'entretien'] as const
export type Sub = (typeof SUBS)[number]

export function fromUrl(search = typeof window === 'undefined' ? '' : window.location.search): { tab: Tab; sub: Sub } {
  const q = new URLSearchParams(search)
  const sub = q.get('sub') as Sub | null
  return { tab: SLUG[q.get('tab') ?? ''] ?? 'Quête', sub: sub && SUBS.includes(sub) ? sub : 'qcm' }
}

// Reprise : l'appli rouvre l'onglet (et la leçon) quittés il y a moins de RESUME_H heures. Stockage facultatif.
const KEY = 'reprise'
const RESUME_H = 12
export interface Last { tab: Tab; sub: Sub; lessonId: string | null; at: number }

export function saveLast(l: Omit<Last, 'at'>, now = Date.now()) {
  try { localStorage.setItem(KEY, JSON.stringify({ ...l, at: now })) } catch { /* navigation privée */ }
}

export function loadLast(now = Date.now()): Last | null {
  try {
    const l = JSON.parse(localStorage.getItem(KEY) ?? 'null') as Last | null
    return l && TABS.includes(l.tab) && now - l.at < RESUME_H * 3600_000 ? l : null
  } catch { return null }
}

/** Où démarrer : un lien explicite (?tab=) gagne, sinon la reprise, sinon la quête. */
export function startAt(search = typeof window === 'undefined' ? '' : window.location.search, now = Date.now()) {
  if (new URLSearchParams(search).has('tab')) return { ...fromUrl(search), lessonId: null }
  const l = loadLast(now)
  return l ? { tab: l.tab, sub: l.sub, lessonId: l.lessonId } : { tab: 'Quête' as Tab, sub: 'qcm' as Sub, lessonId: null }
}
