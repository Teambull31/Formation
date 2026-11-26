// @vitest-environment jsdom
import { expect, test } from 'vitest'
import { fromUrl, saveLast, startAt } from './deeplink'

test('lien direct vers un onglet et un sous-onglet, repli sur la quête', () => {
  expect(fromUrl('?tab=ecoute')).toEqual({ tab: 'Écoute', sub: 'qcm' })
  expect(fromUrl('?tab=revisions&sub=cartes')).toEqual({ tab: 'Révisions', sub: 'cartes' })
  expect(fromUrl('?tab=nope&sub=pirate')).toEqual({ tab: 'Quête', sub: 'qcm' })
  expect(fromUrl('')).toEqual({ tab: 'Quête', sub: 'qcm' })
})

test('reprise : dernier onglet et leçon si récents, le lien explicite gagne', () => {
  localStorage.clear()
  expect(startAt('', 1000)).toEqual({ tab: 'Quête', sub: 'qcm', lessonId: null, mini: false })
  saveLast({ tab: 'Leçon', sub: 'qcm', lessonId: 'ci4' }, 1000)
  expect(startAt('', 1000 + 3600_000)).toEqual({ tab: 'Leçon', sub: 'qcm', lessonId: 'ci4', mini: false })
  expect(startAt('?tab=revisions&sub=cartes&mini=1', 1000)).toMatchObject({ tab: 'Révisions', sub: 'cartes', mini: true })
  expect(startAt('', 1000 + 13 * 3600_000).tab).toBe('Quête') // plus de 12 h : retour à la quête
  expect(startAt('?tab=ecoute', 1000).tab).toBe('Écoute')
  localStorage.setItem('reprise', '{pas du json')
  expect(startAt('', 1000).tab).toBe('Quête')
})
