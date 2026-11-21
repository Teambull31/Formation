import { describe, expect, it } from 'vitest'
import { ficheHtml } from './fiche'

describe('ficheHtml', () => {
  it('produit une page autonome, échappée', () => {
    const h = ficheHtml('Fiches <x>', [{ id: 'a', title: 'A', body_md: '# Titre\n- **gras** <script>' }])
    expect(h.startsWith('<!doctype html>')).toBe(true)
    expect(h).toContain('<strong>gras</strong>')
    expect(h).not.toContain('<script>')
    expect(h).toContain('Fiches &lt;x&gt;')
  })
})
