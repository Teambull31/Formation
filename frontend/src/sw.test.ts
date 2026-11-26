import { expect, test } from 'vitest'
import src from '../public/sw.js?raw'

// sw.js exécuté avec un faux `self` : notification avec actions, et le bouton choisi ouvre le bon onglet
test('notification : actions et lien vers le bon onglet', async () => {
  const h: Record<string, (e: unknown) => void> = {}
  let shown: { o: { data: { url: string }; actions: unknown[] } } | null = null
  let opened = ''
  const self = {
    addEventListener: (t: string, f: (e: unknown) => void) => { h[t] = f }, location: { origin: 'https://x' }, skipWaiting: () => {},
    registration: { showNotification: (_t: string, o: { data: { url: string }; actions: unknown[] }) => { shown = { o }; return Promise.resolve() } },
    clients: { matchAll: () => Promise.resolve([]), openWindow: (u: string) => { opened = u; return Promise.resolve() }, claim: () => {} },
  }
  new Function('self', 'caches', 'fetch', src)(self, {}, () => {})
  const wait: Promise<unknown>[] = []
  h.push({ data: { json: () => ({ title: 'T', body: 'B', url: '/?tab=revisions', actions: [{ action: 'ecoute', title: 'É' }] }) }, waitUntil: (p: Promise<unknown>) => wait.push(p) })
  await Promise.all(wait)
  expect(shown!.o.data.url).toBe('/?tab=revisions')
  expect(shown!.o.actions).toHaveLength(1)
  h.notificationclick({ action: 'ecoute', notification: { close() {}, data: shown!.o.data }, waitUntil: (p: Promise<unknown>) => wait.push(p) })
  await Promise.all(wait)
  expect(opened).toBe('/?tab=ecoute')
  h.notificationclick({ action: 'mini', notification: { close() {}, data: shown!.o.data }, waitUntil: (p: Promise<unknown>) => wait.push(p) })
  await Promise.all(wait)
  expect(opened).toBe('/?tab=revisions&sub=cartes&mini=1')
  h.notificationclick({ action: '', notification: { close() {}, data: shown!.o.data }, waitUntil: (p: Promise<unknown>) => wait.push(p) })
  await Promise.all(wait)
  expect(opened).toBe('/?tab=revisions')
})
