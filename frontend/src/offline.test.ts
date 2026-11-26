// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest'
import { answerCard, getCards } from './api'
import { cacheable, flush, pending } from './offline'

afterEach(() => { vi.unstubAllGlobals(); localStorage.clear() })
const cards = { cards: [], boxes: [0], total: 0, unseen: 0 }

test('hors réseau : dernière lecture servie, réponse mise en file puis envoyée dans l\'ordre', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(cards), { status: 200 })))
  expect(await getCards()).toEqual(cards)
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
  expect(await getCards()).toEqual(cards) // depuis le cache
  expect((await answerCard('c1', true)) as unknown).toMatchObject({ offline: true })
  await answerCard('c2', false)
  expect(pending().map((p) => p.url)).toEqual(['/api/cards/c1', '/api/cards/c2'])
  expect(await flush()).toBe(0) // toujours hors réseau : rien ne part, rien ne se perd
  expect(pending()).toHaveLength(2)
  const sent: string[] = []
  expect(await flush((p) => { sent.push(p.url); return Promise.resolve(new Response('{}')) })).toBe(2)
  expect(sent).toEqual(['/api/cards/c1', '/api/cards/c2'])
  expect(pending()).toEqual([])
})

test('une erreur du serveur n\'est pas masquée, une route non prévue lève toujours', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{"detail":"Carte inconnue"}', { status: 404 })))
  await expect(answerCard('x', true)).rejects.toThrow('Carte inconnue')
  expect(pending()).toEqual([])
})

test('routes gardées hors ligne', () => {
  expect(cacheable('/api/lesson/ci4')).toBe(true)
  expect(cacheable('/api/lesson/ci4/keys')).toBe(true)
  expect(cacheable('/api/quest?minutes=30')).toBe(true)
  expect(cacheable('/api/missions')).toBe(false)
})
