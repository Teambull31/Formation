import { expect, test } from 'vitest'
import { bestPage, speakable, splitPages } from './pages'

test('une page par section, intro avec la première, jamais de coupe dans un bloc de code', () => {
  const md = 'Intro\n\n## Un\ntexte\n```yaml\n## pas un titre\nx: 1\n```\n## Deux\nfin'
  expect(splitPages(md, 0)).toEqual(['Intro\n\n## Un\ntexte\n```yaml\n## pas un titre\nx: 1\n```', '## Deux\nfin'])
  expect(splitPages('Sans section')).toEqual(['Sans section'])
})

test('les sections courtes sont fusionnées', () => {
  const long = 'x'.repeat(800)
  expect(splitPages(`## A\ncourt\n## B\n${long}\n## C\nfin`, 700)).toEqual([`## A\ncourt\n\n## B\n${long}`, '## C\nfin'])
})

test('la page qui explique une réponse est retrouvée', () => {
  const pages = ['## Cache\nLe cache des dépendances accélère le build.', '## Secrets\nUn secret se lit avec secrets.NOM, jamais en clair.']
  expect(bestPage(pages, 'Comment lire un secret ? secrets.NOM')).toBe(1)
  expect(bestPage(pages, 'rien à voir')).toBe(0)
})

test('texte lisible à voix haute', () => {
  const md = '## Titre\n- **gras** et `code`\n```yaml\nx: 1\n```\n| a | b |\n|---|---|\n| 1 | 2 |\n[lien](http://x)'
  expect(speakable(md)).toBe("Titre\ngras et code\n (exemple de code, à lire à l'écran) \na, b\n1, 2\nlien")
})
