import { useEffect, useState } from 'react'
import { getGlossary, type GlossEntry } from '../api'

const MAX = 30 // au-delà, affiner la recherche

// Retrouver un terme vu en cours : sa phrase de définition et la leçon qui l'introduit.
export default function Glossary({ onOpen }: { onOpen: (lessonId: string, focus?: string) => void }) {
  const [all, setAll] = useState<GlossEntry[] | null>(null)
  const [q, setQ] = useState('')
  useEffect(() => {
    getGlossary().then((g) => setAll(Object.values(g).sort((a, b) => a.term.localeCompare(b.term, 'fr')))).catch(() => setAll([]))
  }, [])
  if (!all) return <section className="screen wrap"><p className="note">Chargement…</p></section>
  const needle = q.trim().toLowerCase()
  const hits = needle ? all.filter((e) => e.term.toLowerCase().includes(needle) || e.sentence.toLowerCase().includes(needle)) : []
  return (
    <section className="screen wrap">
      <h1>Glossaire</h1>
      <input type="search" placeholder={`Chercher parmi ${all.length} termes…`} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Chercher un terme" />
      {needle && !hits.length && <p className="note">Aucun terme trouvé.</p>}
      {hits.slice(0, MAX).map((e) => (
        <div className="card" key={e.term}>
          <p><b>{e.term}</b> : {e.sentence}</p>
          <button className="chip" onClick={() => onOpen(e.lesson_id, e.sentence)}>{e.title} →</button>
        </div>
      ))}
      {hits.length > MAX && <p className="time">{hits.length - MAX} autres : précise ta recherche.</p>}
    </section>
  )
}
