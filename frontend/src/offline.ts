// Hors réseau (tunnel, parking) : les dernières lectures restent servies, les réponses partent au retour du réseau.
// Seules les pannes réseau (fetch qui lève) sont concernées : une erreur HTTP du serveur reste une erreur.
const CACHE = 'hl-cache:'
const QUEUE = 'hl-file'
const CACHEABLE = [/^\/api\/(quest|cards|lessons|reviews|team|plan|oral|today|glossary)(\?|$)/, /^\/api\/lesson\/[^/]+(\/keys)?$/]
const QUEUEABLE = [/^\/api\/cards\/[^/]+$/, /^\/api\/podcast\/[^/]+\/done$/, /^\/api\/revision\/done$/, /^\/api\/quest\/step$/]
export interface Pending { method: string; url: string; body?: unknown }

const get = (k: string) => { try { return localStorage.getItem(k) } catch { return null } }
const set = (k: string, v: string) => { try { localStorage.setItem(k, v) } catch { /* plein ou interdit : tant pis */ } }

export const cacheable = (url: string) => CACHEABLE.some((r) => r.test(url))
export const queueable = (method: string, url: string) => method === 'POST' && QUEUEABLE.some((r) => r.test(url))
export const remember = (url: string, data: unknown) => set(CACHE + url, JSON.stringify(data))
export function recall(url: string): unknown {
  const v = get(CACHE + url)
  return v === null ? undefined : JSON.parse(v)
}
export const pending = (): Pending[] => { try { return JSON.parse(get(QUEUE) ?? '[]') } catch { return [] } }
export const enqueue = (p: Pending) => set(QUEUE, JSON.stringify([...pending(), p]))

/** Réponse locale en attendant le serveur : de quoi laisser l'écran continuer. */
export const offlineReply = (url: string) =>
  /^\/api\/cards\//.test(url) ? { box: 0, due: '', mastered: false, offline: true } : { ok: true, xp: 0, offline: true }

/** Envoie la file dans l'ordre ; s'arrête à la première panne réseau (le reste attend), retire le reste une fois traité. */
export async function flush(send: (p: Pending) => Promise<Response> = (p) =>
  fetch(p.url, { method: p.method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p.body ?? {}) })): Promise<number> {
  let q = pending()
  let sent = 0
  while (q.length) {
    try {
      await send(q[0]) // 2xx comme 4xx : traité (un 4xx ne passerait jamais)
    } catch {
      break
    }
    q = q.slice(1)
    set(QUEUE, JSON.stringify(q))
    sent++
  }
  return sent
}
