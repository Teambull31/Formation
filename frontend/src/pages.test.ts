import { expect, test } from 'vitest'
import { splitPages } from './pages'

test('une page par section, intro avec la première, jamais de coupe dans un bloc de code', () => {
  const md = 'Intro\n\n## Un\ntexte\n```yaml\n## pas un titre\nx: 1\n```\n## Deux\nfin'
  expect(splitPages(md, 0)).toEqual(['Intro\n\n## Un\ntexte\n```yaml\n## pas un titre\nx: 1\n```', '## Deux\nfin'])
  expect(splitPages('Sans section')).toEqual(['Sans section'])
})

test('les sections courtes sont fusionnées', () => {
  const long = 'x'.repeat(800)
  expect(splitPages(`## A\ncourt\n## B\n${long}\n## C\nfin`, 700)).toEqual([`## A\ncourt\n\n## B\n${long}`, '## C\nfin'])
})
