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
