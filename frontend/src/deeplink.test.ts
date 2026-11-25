import { expect, test } from 'vitest'
import { fromUrl } from './deeplink'

test('lien direct vers un onglet et un sous-onglet, repli sur la quête', () => {
  expect(fromUrl('?tab=ecoute')).toEqual({ tab: 'Écoute', sub: 'qcm' })
  expect(fromUrl('?tab=revisions&sub=cartes')).toEqual({ tab: 'Révisions', sub: 'cartes' })
  expect(fromUrl('?tab=nope&sub=pirate')).toEqual({ tab: 'Quête', sub: 'qcm' })
  expect(fromUrl('')).toEqual({ tab: 'Quête', sub: 'qcm' })
})
