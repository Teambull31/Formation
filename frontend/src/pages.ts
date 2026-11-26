// Découpe une leçon en pages courtes : une page par section « ## » (hors blocs de code), l'intro reste avec la 1re.
// Les sections trop courtes (< minChars) sont fusionnées avec la suivante : pas de page de deux lignes.
export function splitPages(md: string, minChars = 700): string[] {
  const pages: string[][] = [[]]
  let fence = false
  for (const line of md.split('\n')) {
    if (line.trimStart().startsWith('```')) fence = !fence
    if (!fence && /^## /.test(line) && pages[pages.length - 1].some((l) => /^## /.test(l))) pages.push([])
    pages[pages.length - 1].push(line)
  }
  const out: string[] = []
  for (const p of pages.map((x) => x.join('\n').trim()).filter(Boolean)) {
    if (out.length && out[out.length - 1].length < minChars) out[out.length - 1] += '\n\n' + p
    else out.push(p)
  }
  return out
}

const words = (t: string) => new Set(t.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').match(/[a-z0-9]{4,}/g) ?? [])

/** Page qui explique le mieux `focus` (question + bonne réponse) : celle qui en partage le plus de mots. */
export function bestPage(pages: string[], focus: string): number {
  const want = words(focus)
  let best = 0, score = -1
  pages.forEach((p, i) => {
    const have = words(p)
    const s = [...want].filter((w) => have.has(w)).length
    if (s > score) { best = i; score = s }
  })
  return best
}
